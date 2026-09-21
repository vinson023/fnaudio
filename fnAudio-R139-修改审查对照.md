# fnAudio R139 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮 9 个被跟踪源/测试文件改动，源码与测试合计 **+582 −12**；另 1 份清单（+9 −9）。三份根文档本轮只追加记录，`TODO.md` 未动（净关闭 0 条，见文末）。对照 md 按裁定 Q5=B 以独立 pathspec 入库。

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | src/app/server/metadata_local_lyrics_cache.py | +39 −3 | Q6=A 预算校验器 + 在线施加器 |
| 2 | src/app/server/metadata_service.py | +45 −0 | Q6=A 两条道接线与真值读回 |
| 3 | src/app/server/server.py | +76 −1 | Q6=A 提交钩子 / GET / POST |
| 4 | src/app/ui/app.js | +35 −2 | Q6=A 设置页读写 |
| 5 | src/app/ui/index.html | +1 −1 | Q6=A 「运行」pane 新增 select（L85 单巨行） |
| 6-9 | test_metadata_local_lyrics_cache / test_metadata_service / test_http_integration / test_ui_runtime_settings | +386 −5 | 19 枚 Python + 11 组 JS 判别断言 |
| 10 | SOURCE_MANIFEST.sha256 | +9 −9 | 9 个改动文件摘要刷新 |

---

## H1 `C:\path\to\fnAudio\src\app\server\metadata_local_lyrics_cache.py` L60-75 — 外部预算「只拒不夹」
```
+def strict_bytes_limit_from_payload(value):
+    if isinstance(value, bool) or not isinstance(value, int):
+        return None
+    if value < MIN_MAX_BYTES or value > MAX_MAX_BYTES:
+        return None
+    return value
```
审核：与既有 `bytes_limit_from_config`（L43-57，对**落库值**夹取）刻意分工不同。边界复用模块自带 `MIN_MAX_BYTES`/`MAX_MAX_BYTES`，未新增常量；`isinstance(value, bool)` 前置是因 `True` 是 `int` 子类，漏掉它会把「true」读成 1 字节。变异 V1/V4 的落点。

## H2 `metadata_local_lyrics_cache.py` L134-149 — 在线重设预算
```
+    def apply_bytes_limit(self, value):
+        limit = _bounded_bytes(value)
+        with self._lock:
+            if limit == self._bytes_limit:
+                return self._bytes_limit
+            self._bytes_limit = limit
+            self._enforce_budget()
+            return self._bytes_limit
```
审核：等值早退是必需路径，不是优化——每次保存任何运行设置都会重推整个 config，缺这道比较就会让「改端口」顺带清空歌词缓存（`test_reapplying_the_current_budget_evicts_nothing` 判别）。淘汰复用读侧同一个 `_enforce_budget()`，故淘汰序与运维在诊断页看到的口径一致；全程持 `self._lock`，无新锁序。变异 V2 的落点。

## H3 `metadata_local_lyrics_cache.py` L234-239 — `__all__` 补 3 个名字
```
+    "CONFIG_BYTES_KEY", "DEFAULT_LIMIT", "DEFAULT_MAX_BYTES", "MAX_LIMIT",
+    "MAX_BYTES_COUNTER", "MAX_COUNTER", "MAX_MAX_BYTES", "MIN_MAX_BYTES",
+    "LocalLyricsCache", "bytes_limit_from_config", "combined_snapshot",
+    "strict_bytes_limit_from_payload",
```
审核：本模块无 `import *` 使用者，扩 `__all__` 的唯一作用是让 HTTP 层显式 `from ... import` 时名单与实现同源。−3 是重排同批旧条目，无名字被删除。

## H4 `C:\path\to\fnAudio\src\app\server\metadata_service.py` L1979-1993 — lane 枚举
```
+    def _lyrics_cache_lanes(self):
+        lanes = []
+        own = getattr(self, "_local_lyrics_cache", None)
+        if own is not None:
+            lanes.append(own)
+        provider_cache = getattr(getattr(self, "providers", None), "_local_lyrics_cache", None)
+        if provider_cache is not None and provider_cache not in lanes:
+            lanes.append(provider_cache)
+        return lanes
```
审核：歌词缓存是**两个独立构造点**（R138 H9 已登记），故预算必须同时到达两处；`not in lanes` 防两处复用同一实例时重复施加。取不到 lane 时返回空表而不是抛，R138 之前 `status()` 用的是同一防御口径。

## H5 `metadata_service.py` L1995-2006 / L2008-2021 — 施加器与「最紧一条」读回
```
+    def apply_lyrics_cache_config(self, config=None):
+        source = self.config if config is None else config
+        limit = bytes_limit_from_config(source)
+        for lane in self._lyrics_cache_lanes():
+            lane.apply_bytes_limit(limit)
+        return limit
+
+    def lyrics_cache_bytes_limit(self):
+        ...
+        if limits:
+            return min(limits)
+        return bytes_limit_from_config(self.config)
```
审核：**有意收敛**——不复用 `combined_snapshot()`。那个快照的 `bytes_limit` 是两条 lane 之和（进程真实占用口径），拿来当设置页回显会显示 16 MiB 而用户选的是 8 MiB。故读回取 `min`，聚合口径仍完整保留在 `/api/diagnostics` 与 `status()` 里。变异 V3 指向此处。

## H6 `C:\path\to\fnAudio\src\app\server\server.py` L128-136 — 只引名不抄数
```
+from metadata_local_lyrics_cache import (
+    CONFIG_BYTES_KEY as LYRICS_CACHE_BYTES_CONFIG_KEY,
+    bytes_limit_from_config,
+    strict_bytes_limit_from_payload,
+)
```
审核：`server.py` 全文不出现 `"metadata_lyrics_cache_max_bytes"` 字面量，也不出现 64 KiB/8 MiB/64 MiB 任何边界数——这条由 `test_server_source_names_the_cache_budget_only_through_the_shared_constant` 以源码级断言把守，键名或区间日后改名，服务端会先红。

## H7 `server.py` L621-624 — 提交成功后才施加
```
         apply_library_connection_pool_config(server.config)
+        apply_lyrics_cache_config(server.config)
```
审核：位置在 `commit_config_update()` 成功分支内、连接池之后。写盘失败时该函数提前返回 `False`，预算绝不会被施加（`test_runtime_config_budget_untouched_when_the_save_fails` 判别）。与 R124 连接池开关同一条纪律。

## H8 `server.py` L628-641 — 缺键=不动，有键=合法
```
+def payload_bytes_limit(payload, key, default=None):
+    if key not in payload:
+        return default
+    value = strict_bytes_limit_from_payload(payload.get(key))
+    if value is None:
+        raise ValueError("%s must be an integer byte count inside the supported range" % key)
+    return value
```
审核：`key not in payload` 与「键存在但值为 null」严格区分，前者回落到**当前运行值**。POST 传入的 default 是 `bytes_limit_from_config(self.server.config)`，因此「只改开关、不带预算键」的老请求不会把预算重置成默认——`test_runtime_config_budget_and_pool_do_not_clobber_each_other` 双向判别。变异 V5 的落点。

## H9 `server.py` L644-653 / L656-671 — 未初始化与 mock 兜底
```
+def runtime_lyrics_cache_bytes_limit(config):
+    reader = getattr(METADATA_SERVICE, "lyrics_cache_bytes_limit", None)
+    if callable(reader):
+        try:
+            value = reader()
+        except (TypeError, ValueError):
+            value = None
+        if isinstance(value, int) and not isinstance(value, bool):
+            return value
+    return bytes_limit_from_config(config)
```
审核：只信非 bool 的 int，其它一律回落落库值；`except` 只收 `TypeError/ValueError`，不用裸 `except`，真出 bug 仍会抛出。`apply_lyrics_cache_config()`（L644）在服务尚未构建时退化为纯读，与构造期 `bytes_limit_from_config` 接的同一个值。

## H10 `server.py` L940（GET）/ L1614（POST 回显） — 两出口同源
```
+                    LYRICS_CACHE_BYTES_CONFIG_KEY: runtime_lyrics_cache_bytes_limit(self.server.config),
```
审核：两处用**同一个函数**，杜绝「保存返回新值、刷新又显示旧值」；键名与 `library_connection_pool` 并列在 `config` 字典内，客户端读取路径不变。

## H11 `server.py` L1585-1596 — 拒绝态用独立文案
```
+            try:
+                lyrics_budget = payload_bytes_limit(
+                    payload,
+                    LYRICS_CACHE_BYTES_CONFIG_KEY,
+                    bytes_limit_from_config(self.server.config),
+                )
+            except (TypeError, ValueError):
+                return self.send_json(
+                    {"ok": False, "message": "运行设置包含无效值：歌词缓存预算必须是范围内的整数字节数"}, 400
+                )
```
审核：校验在 `commit_config_update()` **之前**，非法值既不落盘也不施加。拒绝消息与 L1585 之上池开关那句分开，用户能分辨改错了哪一个；池开关原文案一字未动，向后兼容既有测试。

## H12 `C:\path\to\fnAudio\src\app\ui\app.js` L6495 / L6499-6517 — 键名常量 + 回填
```
+const LYRICS_CACHE_BUDGET_SETTING_KEY = "metadata_lyrics_cache_max_bytes";
+function applyRuntimeLyricsBudget(budget, limit) {
+  if (!budget || !Number.isInteger(limit) || limit <= 0) return false;
+  const wanted = String(limit);
+  budget.value = wanted;
+  if (budget.value === wanted) return true;
+  const option = document.createElement("option");
+  option.value = wanted;
+  option.textContent = `自定义 · ${formatSize(limit)}`;
+  budget.appendChild(option);
+```
审核：不可用值**零写入**并返回 false——不拿 markup 的 `selected` 冒充服务端答案（5i 断言 `writes.length === 0`）。非预设值追加「自定义 · X」而非静默跳回 8 MiB，因为**手工编辑过的 config 是合法状态**，闪回默认值等于谎报。`formatSize` 是文件内既有格式化函数，未新增工具。变异 V6/V8 落点。

## H13 `app.js` L6519-6521（读）/ L6538-6550（写） — 两控件同生共死
```
+  if (!input || !budget) throw new Error("运行设置控件不可用");
+  const lyricsBudget = Number(budget.value);
+  if (!Number.isInteger(lyricsBudget) || lyricsBudget <= 0) throw new Error("运行设置控件不可用");
+    body: JSON.stringify({
+      [LIBRARY_CONNECTION_POOL_SETTING_KEY]: input.checked === true,
+      [LYRICS_CACHE_BUDGET_SETTING_KEY]: lyricsBudget,
+    }),
```
审核：沿用该函数既有纪律——**先校验、后发请求**，抛错时 `calls.length === 0`（5k）。`<select>` 的 `value` 是字符串，这里转成正整数再出门，保证 HTTP 层收到 JSON number，`strict_bytes_limit_from_payload` 才不会退给数字串。请求体恰两键由 JS 与 `test_http_integration` 两侧分别把守。

## H14 `C:\path\to\fnAudio\src\app\ui\index.html` L85（单巨行，2322 → 2792 字符）
```
+<div class="metadata-settings-grid"><label><span>歌词缓存上限</span><select id="lyricsCacheBudgetInput">
+  <option value="65536">64 KiB</option> ... <option value="8388608" selected>8 MiB（默认）</option>
+  ... <option value="67108864">64 MiB</option></select></label></div>
+<p class="dialog-help">本地歌词正文的内存缓存上限，...调小会立刻淘汰已缓存的歌词。</p>
```
审核：插入位置在 `libraryConnectionPoolInput` 所属 `<section>` 内、`</section>` 之前，pane 归属由 `test_ui_runtime_settings.js` L32/L40 双向断言（运行 pane 必须有、元数据 pane 必须没有）。沿用既有 `.metadata-settings-grid` / `.dialog-help` 类，**未新增任何 CSS**。选项值即服务端允许区间端点。变异 V7 落点。

## H15 测试侧（+386 −5）
- `test_metadata_local_lyrics_cache.py` +62：L262 夹取并回报、L275 调小淘汰最旧且计数器不动、L292 等值零淘汰、L306 校验器拒 bool/数字串/越界、L316 键名单一来源。
- `test_metadata_service.py` +68：L98/L111/L125/L135/L143/L157，覆盖两 lane 达到、淘汰、缺 providers 存活、无参读存量 config、min 口径、无 lane 回落。
- `test_http_integration.py` +163：L1160-L1273 共 8 枚，含 GET 报**真实执行值**、无 service 回落、mock 答案不信、非法值 400 且缓存不动、提交后淘汰、两键互不覆写、落盘失败不施加、源码级键名断言。
- `test_ui_runtime_settings.js` +93 −5：pane 归属/六档预设/常量同源/回填五类/自定义档/零写入/两键出门/失败必抛/控件缺失即不可用。−5 是把原来「body 只能有一键」的三行改成「恰两键」——**需求变了，口径跟着变**，不是放宽。

## 证据
- 控制组 `%TEMP%\r139_ctrl.log`：Ran 2510，OK (skipped=3)。
- 主仓全量 `%TEMP%\r139_py_after_manifest.log`：**Ran 2510 tests in 119.351s / OK (skipped=2)**（基线 2491，+19 枚）。
- JS：`src/tests` 74 个 `test_*.js` 逐文件实跑 **PASS=74 FAIL=0**。
- 仓库外副本 `%TEMP%\r139mut2` 变异 **V1-V8 全 KILLED，killed=8 survived=0 broken=0**（`%TEMP%\r139_mut_result2.txt`）。
- 清单 `SOURCE_MANIFEST.sha256`：707 条 / 76,638 B / 全 CRLF，sha256 `19C4D9AFCC0F08B7B2013F3B508B86FDFFBB85DCDDB0B761A6FBB7F2A15039CE`，`tools/update_source_manifest.ps1` 连跑两次逐字节幂等。
- TODO 四桶实测：开放 60 = 代码 2（L99、L150）+ 设备/外部 45 + 需决策 0 + 长期观察/台账 13，与 R138 登记一致，**本轮净关闭 0 条**。

## 本轮踩坑（已同步 PROJECT_CONTEXT.md L2）
第一版变异驱动用 `git checkout --` 复位，而副本目录根本没有 `.git`：控制组自红、8 例全 BROKEN（`r139_mut_control.log` 的 `FileNotFoundError ... r139_mut\.git\config`）。第二版改为驱动启动时把工作树文件快照到 `%TEMP%\r139_pristine`，每例前后从快照恢复。**结论：控制组红时不得宣布变异结论。**
