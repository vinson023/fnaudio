# fnAudio · R124 修改审核对照（接管取证 + 逐 hunk）

生成时间：2026-09-20（Asia/Shanghai）。仓库 `C:\path\to\fnAudio`，分支 `main`。
本文件是**给人逐 hunk 审核的交付物**，不是文件清单；每个 hunk 都带磁盘证据、具名杀手测试与变异编号。
本文件本身不入库（与 `artifacts/`、`music/`、`_external/` 同批未跟踪件）。

---

## 0 接管取证（当场实测，不引用任何历史快照）

| 项 | 磁盘读数 |
| --- | --- |
| 起始 HEAD（接管时） | `701c817` chore: record R123 closure |
| 未完成 Git 状态 | 无 merge / rebase / cherry-pick（`.git/MERGE_HEAD`、`rebase-merge`、`rebase-apply`、`CHERRY_PICK_HEAD` 全部不存在） |
| 接管时已跟踪改动 | 7 个（`SOURCE_MANIFEST.sha256`、`src/app/server/{library.py,server.py}`、`src/app/ui/{app.js,index.html}`、`src/tests/test_http_integration.py`）+ 1 个未跟踪新测试 `src/tests/test_ui_runtime_settings.js` |
| 本轮终跑门禁 | `artifacts/offline-20260920-round190.log`（2585 行，mtime 19:21:05，晚于全部文档编辑）⇒ Python `Ran 2443 tests in 111.515s` + `OK (skipped=2)`；JS 段 73 个文件全绿（含 `Runtime settings regression checks passed.`）；退出码 0 |
| 清单 | `SOURCE_MANIFEST.sha256` **704 条**；`tools/takeover_forensics.py` ⇒ `drift 0 / stale 0 / unlisted 0` |
| `git status --porcelain -uno` | 两笔提交之后**空** |
| 半截文件 | `.new` / `.orig` / `.rej` 递归扫描仅命中 `_external/` 里 `modernc.org/libc@v1.67.6/surface.new` 两处（未跟踪外部依赖，非本轮产物） |

本轮落地的两笔提交（逐文件显式 pathspec，未用 `git add -A`，未碰 `.gitignore`）：

1. `cb5370b` feat(ui): expose the library connection pool switch on the runtime settings pane
   ⇒ `SOURCE_MANIFEST.sha256`、`src/app/server/library.py`、`src/app/server/server.py`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_http_integration.py`、`src/tests/test_ui_runtime_settings.js`（7 files，+354 / -37）
2. `03d0ce3` chore: record R124 closure ⇒ `TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`（3 files，+8 / -1）

### 0.1 四桶复算（按行首勾选标记 + 节标题文本锚定；行号只是当轮线索）

`TODO.md` 盘上 2213 行（按换行符分割，含末尾空行），`- [ ] ` 行首前缀 **76** 条，`- [x] ` **1463** 条，CRLF **0**。76 条的真实归属：

| 桶 | 条数 | 锚定方式（节标题 + 当轮行号） |
| --- | --- | --- |
| 可离线代码项 | **18** | 主表 16（L38、L39、L72、L89、L101、L103、L105、L112、L116、L119、L140、L150、L153、L154、L158、L175）+ L546（持续审查未完成范围）+ L794（按可测试边界继续拆分） |
| 设备/外部验收项 | **44** | L811..L843（宿主 MediaSession 10）+ L974..L1174（Android 等价 MediaSession 6）+ L1826..L1828（P2 段 3）+ L1837（P3 段 1）+ L1842..L1866（P0 外部验收 24） |
| 需项目负责人决策 | **1** | L1878（R73 `allow_disk=False` 不生效的取舍，需真机取证） |
| 台账/历史叙述项 | **13** | L1884「完成定义」之后各「持续推进」段（L2071..L2153） |

=> **76 = 18 + 44 + 1 + 13**。

历史计数快照**并存、不合并、不覆盖**：`155=64+82+9`、`115=51+43+8+13`、`88=24+43+8+13`、`82=22+44+3+13`、`80=20+44+3+13`、`77=18+44+2+13`、`76=18+44+1+13`（本轮）。
差异的来源是逐轮关闭与桶重划（R121 从代码桶拆出 D9 并新增决策段、R123 关闭 D1/L71/L74、R124 关闭 D9），不是同一时刻的两个口径。

设备段核对：本轮 `TODO.md` 中 P0 段 24 条、P2 段 3 条、P3 段 1 条、宿主 MediaSession 段 10 条、Android 段 6 条，**正文一字未改**（只作为分类锚点读取）。

---
## T1 `src/app/server/library.py` —— 配置键的唯一公开出口（盘上 L1905-L1914，新增 12 行）

```python
def library_connection_pool_config_key():
    """The one public spelling of the switch's configuration key.

    The runtime settings pane has to name this key inside a request payload, but the
    key and its default stay owned by this module.  The startup path once seeded its
    own copy of the value, which `save_config` then dropped from disk; the guard test
    for that bug keeps the name out of the server module, and this accessor is how the
    pane reaches the switch without reviving the bug or loosening the guard.
    """
    return LIBRARY_CONNECTION_POOL_CONFIG_KEY
```

位置：紧接既有私有谓词 `_library_connection_pool_enabled()` 之后、`library_connection_pool_status()` 之前。

**为什么必须有这一处**：设置页要在请求体里点名这个键，但既有守卫 `src/tests/test_server_lifecycle.py:175`
`test_the_pool_default_is_no_longer_invented_at_startup` 断言 `server.py` **全文不得出现**
`LIBRARY_CONNECTION_POOL_CONFIG_KEY` 与字面量 `"library_connection_pool"`（它是历史缺陷「启动路径自己造默认值、
`save_config` 再把它从盘上丢掉」的守门人）。本轮**没有放宽这条守卫**，而是让键名继续只属于 `library.py`，
服务端经函数取。收口复核：`server.py` 全文对这两个字面量 **0 命中**（已实测）。

- 判别测试：`src/tests/test_ui_runtime_settings.js` 第 36-38 行 —— 既断言 `library.py` 里
  `LIBRARY_CONNECTION_POOL_CONFIG_KEY = "library_connection_pool"` 仍然存在，又断言 `server.py` 里出现的是
  `_library_connection_pool_enabled as library_connection_pool_enabled` 这一复用而非新造默认。
- 变异 **V6**（常量与服务端键脱钩）由同一套件杀灭；把本函数改回字面量 ⇒ `test_server_lifecycle` 立即红。

---

## T2 `src/app/server/server.py` hunk `@@ -29,12 +29,18 @@` —— 两个导入（盘上 L36、L43）

```python
 from library import (
     SCAN_STATE,
     cancel_library_refresh,
     apply_library_connection_pool_config,
+    # Not a private-access shortcut: this is the *same* predicate the reader path
+    # uses to decide whether to borrow a pooled handle, so the settings pane cannot
+    # report an enabled state the running pool would not honour.  A second
+    # defaulting rule here is exactly the drift that kept the switch hidden.
+    _library_connection_pool_enabled as library_connection_pool_enabled,
     stop_library_connections,
     library_items,
     library_query_cache_status,
     invalidate_library_query_cache,
     library_search_index_status,
     library_connection_pool_status,
+    library_connection_pool_config_key,
     library_storage_status,
```

审核要点（**这是本轮最需要人眼判断的一处取舍**）：导入下划线开头的私有谓词，通常应当被拒。这里成立的条件有三条，
缺一不可 —— ① 该谓词是**读侧唯一的真值来源**：它决定「是否借用池化句柄」，界面若另写一套判断，就会出现
「界面显示开、池实际关」；② `config.py` 的 `DEFAULT_LIBRARY_CONNECTION_POOL = True` 与 `_library_connection_pool_enabled()`
对**缺键字典返回 False** 是两个不同默认值，本轮实测确认二者不一致，因此绝不能从加载器默认回显；
③ 用 `as` 重命名后，`server.py` 内不出现 `LIBRARY_CONNECTION_POOL_CONFIG_KEY` 字面量，既有守卫不被绕过。
替代方案（在 `library.py` 另写一个 `is_enabled()` 公开包装）同样可行，但会再多一个公开面；本轮选择最小新增。

---

## T3 `src/app/server/server.py` hunk `@@ -864,6 +870,18 @@` —— `GET /api/config/runtime`（盘上 L873-L884）

```python
         if path == "/api/config/runtime":
             # The pane has to show what the process actually does right now, so the
             # value is read through the pool's own predicate instead of a default the
             # handler invents; `status` rides along because the drain on the way off
             # is the observable proof the toggle was not a no-op.
             return self.send_json({
                 "ok": True,
                 "config": {
                     library_connection_pool_config_key(): library_connection_pool_enabled(self.server.config),
                 },
                 "status": library_connection_pool_status(),
             })
```

- 位置：插在 `http_workers` / `playback_command_cache` 那段响应之后、`if path == "/api/access":` 之前。
- 鉴权：**没有新增规则**。`src/app/server/api_route_policy.py:48` 已按 `/api/config/` 前缀判成
  `settings.read`（GET）/ `settings.write`（POST），该文件本轮未改；`V12` 变异（把它塞进 `PUBLIC_API_PATHS`）由具名测试杀灭。
- `status` 字段只是**行为证据**（`LibraryConnectionPool.snapshot()` 不含 `enabled`），不是状态来源；界面上没有任何一处读它。

---

## T4 `src/app/server/server.py` hunk `@@ -1491,6 +1509,37 @@` —— `POST /api/config/runtime`（盘上 L1512-L1542）

```python
         if parsed.path == "/api/config/runtime":
             pool_key = library_connection_pool_config_key()
             try:
                 pool_enabled = payload_bool(
                     payload,
                     pool_key,
                     library_connection_pool_enabled(self.server.config),
                 )
             except (TypeError, ValueError):
                 # Reject, never coerce: `"false"` and `0` must not flip a switch that
                 # decides whether the library index stays open on disk.
                 return self.send_json(
                     {"ok": False, "message": "运行设置包含无效值：曲库连接池必须是布尔值"}, 400
                 )
             if not commit_config_update(
                 self.server,
                 lambda candidate: candidate.update({pool_key: pool_enabled}),
             ):
                 return self.send_json({"ok": False, "message": "保存运行设置失败"}, 500)
             # commit_config_update already re-applied the pool switch against the
             # committed dictionary, so a turn-off has drained its idle handles before
             # this response claims success.  No restart is needed for this key; the
             # port in the same pane still is, and that wording stays where it is.
             return self.send_json({
                 "ok": True,
                 "restart_required": False,
                 "config": {
                     pool_key: library_connection_pool_enabled(self.server.config),
                 },
                 "status": library_connection_pool_status(),
             })
```

逐条审核要点：

1. **拒绝而不强转**：`payload_bool` 只认 JSON 真布尔。`"false"` / `0` / `"0"` / `None` / `1` 一律 400，
   且断言「现值未被触碰」——因为这三个值在 Python 布尔语义里分别会被读成 True/False/True/False/True，
   一个字符串 `false` 反而能把池打开。
2. **默认值来自运行谓词**，不是硬编码 `True`：缺键提交（`{}`）必须保持当前开关，而不是顺手打开。
3. **提交与排空的先后**：`commit_config_update()`（`server.py` L597-L613，排空点在 L612）先 `config.clear()/update()`
   原地提交、再调 `apply_library_connection_pool_config(server.config)`。因此「关闭成功」的响应不可能早于句柄排空。
   这条顺序**只有本轮新增的 `test_runtime_config_turning_the_pool_off_drains_handles_after_the_commit` 杀得动**：
   变异 V10 把排空挪到提交之前，旧的 `test_server_lifecycle` 测试 rc=0 存活，新测试指名报错。这是本轮唯一一处
   「新测试提供了旧守卫给不了的判别力」的证据。
4. **`restart_required: False` 的作用域**：只对这个键成立。同屏的端口修改仍需重启，HTML 里那句提示原样保留。
5. **500 分支**：`save_config` 失败时 `commit_config_update` 返回 False，此路由直接 500 且**不改运行值**；
   界面靠 `saveRuntimeSettings()` 抛异常决定不关对话框（见 T7）。
---

## T5 `src/app/ui/index.html` L85（1 行替换 / 1/1）—— 「运行」pane 末尾追加控件

`index.html` 的整个设置对话框是**一行**（盘上 L85，2322 字符），因此 diff 显示为整行替换。实际新增内容只有下面这一段，
插在 runtime pane 的收尾 `</section>` 之前：

```html
<label class="metadata-toggle"><input id="libraryConnectionPoolInput" type="checkbox"><span>启用曲库连接池</span></label>
<p class="dialog-help">开启时曲库查询会复用已打开的数据库句柄，翻页更快；关闭后每次查询都重新打开曲库，用于排查文件被长期占用。这个开关即时生效，不需要重启 fnAudio。</p>
```

审核要点：

- **pane 归属**：控件在 `data-settings-pane="runtime"` 内，不在 metadata pane。判别测试第 27 行专门断言
  metadata pane 里**不得**出现 `libraryConnectionPoolInput`（变异 V7 就是把它挪过去）。
- **复用既有形状**：`class="metadata-toggle"` 是既有全局类，`src/app/ui/app.css` **一字未改**；文案说「即时生效」是
  本轮服务端确实做到不需要重启（见 T4 第 4 点），不是营销话术。
- **原有内容未被挤掉**：端口那两句（含「修改端口后，请停止并重新启动 fnAudio」）仍在同一 pane 内，测试第 29 行钉住。
- **行尾纪律**：`index.html` 盘上 **12 个 CRLF / 172 个 LF** 的既有混合保持不变（本轮未新增 CR），该文件属既有例外，按项目纪律不顺手归一化。
- 该文件被 `.gitattributes` 归一化，行尾污染在 `git diff` 里看不见，所以这 12/172 的计数是**按字节**读出来的。

---

## T6 `src/app/ui/app.js` hunk `@@ -6423,6 +6423,40 @@` —— 接线 + 四个新函数（盘上 L6426-L6460）

```javascript
  if (name === "metadata") loadMetadataStatus();
  if (name === "runtime") loadRuntimeSettings();          // L6426 新增接线
}
const LIBRARY_CONNECTION_POOL_SETTING_KEY = "library_connection_pool";   // L6428
function runtimeConnectionPoolInput() {                    // L6429
  return $("libraryConnectionPoolInput");
}
async function loadRuntimeSettings() {                     // L6432
  const input = runtimeConnectionPoolInput();
  if (!input) return null;
  try {
    const response = await apiFetch("api/config/runtime", { cache: "no-store" });
    const data = await readResponseJsonBounded(response);
    if (!response.ok || data.ok !== true) throw new Error(data.message || "");
    // Echo the server value rather than assuming the click stuck: a config the
    // loader had to coerce is not the config the pool is honouring.
    input.checked = data?.config?.[LIBRARY_CONNECTION_POOL_SETTING_KEY] === true;
    return data;
  } catch (error) {
    $("folderSaveStatus").textContent = "无法读取运行设置，当前显示的是上一次已知状态";
    return null;
  }
}
async function saveRuntimeSettings() {                     // L6448
  const input = runtimeConnectionPoolInput();
  if (!input) throw new Error("运行设置控件不可用");
  const response = await apiFetch("api/config/runtime", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ [LIBRARY_CONNECTION_POOL_SETTING_KEY]: input.checked === true }),
  });
  const data = await readResponseJsonBounded(response);
  if (!response.ok || data.ok !== true) throw new Error(data.message || "保存运行设置失败");
  input.checked = data?.config?.[LIBRARY_CONNECTION_POOL_SETTING_KEY] === true;
  return data;
}
```

审核要点：

1. **只带一个键**。请求体是计算属性单键对象，值为真布尔；测试 5c 断言 `Object.keys(body)` 恰为该一键，
   5d 断言未勾选时**发 false 而不是省略键**（省略键会被服务端当「保持现值」）。
2. **回显以服务端为准**：读回与保存后都用 `=== true` 覆写 `checked`，因此「用户点了但服务端没接受」会被纠正回真值。
   变异 V2（保存后相信自己的点击）与 V8（GET 硬编码 True）分别杀 UI 侧与服务端侧。
3. **失败不编值**：`loadRuntimeSettings()` 读失败时**保留上一次显示状态**并只写一句提示，返回 `null`；
   `saveRuntimeSettings()` 失败时**抛异常**，不静默返回 —— 静默返回会让调用方关掉对话框，把失败说成成功（变异 V4）。
4. **不新造轮子**：走既有的 `apiFetch`（带鉴权头）与 `readResponseJsonBounded`（带尺寸上限），不直接 `fetch`。
   同屏的元数据读回 `loadMetadataStatus()`（L6575-L6603）用的是裸 `fetch` + 响应加载器，本轮未动它。
5. **已知残余风险（请审）**：catch 分支里 `$("folderSaveStatus").textContent = ...` 与该函数开头的 `if (!input)` 守卫
   **不同源** —— 若 `#folderSaveStatus` 缺失（该 ID 由对话框提供，正常存在），此处会抛 `TypeError` 并沿
   `setSettingsTab()` 变成未处理拒绝。既有 `loadMetadataStatus()` 用的是「先取节点、再判空」的同形写法，
   本轮沿用其形状未额外加固。若要收口，判据与改法见 R125 排期附注。

---

## T7 `src/app/ui/app.js` hunk `@@ -6697,7 +6731,10 @@` —— 保存路由（盘上 L6734-L6736）

改前：

```javascript
    if (state.settingsTab === "metadata") {
      await saveMetadataSettings();
      $("folderDialog").close();
    } else if (await saveLibraryPathsFromDialog()) {
```

改后：

```javascript
    if (state.settingsTab === "runtime") {          // L6734 新增
      await saveRuntimeSettings();                  // L6735
      $("folderDialog").close();                   // L6736
    } else if (state.settingsTab === "metadata") {
      await saveMetadataSettings();
      $("folderDialog").close();
    } else if (await saveLibraryPathsFromDialog()) {
```

**这是本轮最容易做错的一处**：`chooseCurrentFolder()` 的最后一条分支是「音乐库路径兜底」，
任何未被前面分支认领的 tab 都会走去保存音乐库路径。若把 runtime 分支排在兜底之后，
在「运行」pane 点保存会**改掉音乐库目录**而不动池开关 —— 变异 V1（删掉该分支）正是这一形状，由新增 JS 套件杀灭。

---

## T8 `src/tests/test_http_integration.py` hunk `@@ -1037,6 +1037,88 @@` —— 6 项判别测试（盘上 L1040-L1120）

| 测试（盘上行号） | 断言的方向 | 杀灭的变异 |
| --- | --- | --- |
| `runtime_post()` 辅助（L1046） | 统一带 `settings.write` 作用域发 POST | —— |
| `test_runtime_config_reports_the_value_the_pool_actually_honours`（L1054） | 键缺失时必须报 **False**（不是加载器默认 True）；显式 True/False 各自回读正确 | V8 |
| `test_runtime_config_requires_the_settings_scopes`（L1073） | 无凭证 GET 401、只读作用域 POST 403 | V12 |
| `test_runtime_config_rejects_text_boolean_without_changing_the_switch`（L1079） | `"false"` / `0` / `"0"` / `None` / `1` 一律 400 且**现值不变** | V9 |
| `test_runtime_config_omitting_the_key_keeps_the_current_switch`（L1087） | 缺键提交保持现值，不默认打开 | —— |
| `test_runtime_config_turning_the_pool_off_drains_handles_after_the_commit`（L1094） | 排空发生在**原地提交之后**；`restart_required` 为 False；回显为服务端真值 | V10（唯一杀手） |
| `test_runtime_config_persistence_failure_leaves_the_running_switch_alone`（L1114） | `save_config` 失败 ⇒ 500 且运行值未被改动 | V11 |

纪律：这 6 项**只用字面键名** `library_connection_pool`，不 import 常量 —— 与被禁的「启动路径自造默认值」相反，
测试必须能从外部钉住字符串本身，否则 `library.py` 改名将无人发现。
---

## T9 `src/tests/test_ui_runtime_settings.js`（**新增文件**，盘上 137 行 / 0 CRLF）

未跟踪 → 入库。前 4 行是具名说明注释，之后分 5 组断面：

| 组（盘上行号） | 断言 | 杀灭的变异 |
| --- | --- | --- |
| 1) pane 归属（L22-L30） | `libraryConnectionPoolInput` 必须在 runtime pane 内；必须复用 `.metadata-toggle` 形状；**不得**出现在 metadata pane；端口重启提示与新文案都还留在同屏 | V7 |
| 2) 键口径（L32-L37） | UI 常量必须是**单个顶层常量**且值逐字为 `library_connection_pool`；`library.py` 必须仍是键的定义者；`server.py` 必须复用 `_library_connection_pool_enabled` 而非自造默认 | V6 |
| 3) 接线顺序（L39-L45） | `setSettingsTab` 内必须有 `if (name === "runtime") loadRuntimeSettings();`；`chooseCurrentFolder` 里 runtime 分支的下标必须**早于** `saveLibraryPathsFromDialog()` | V5、V1 |
| 4) 路由两端对齐（L47-L50） | `app.js` 里 `"api/config/runtime"` 恰好 2 处（一读一写）；服务端必须同时注册 GET 与 POST | —— |
| 5) `vm` 真跑（L52-L136） | 以假 DOM 节点 + 假 `apiFetch` 实际执行 `loadRuntimeSettings()` / `saveRuntimeSettings()`：5a 服务端说关则界面不许留「开」；5b 读失败不许编值且必须报话；5c 请求体**只有一个键**且值为真布尔、复选框跟随服务端回显；5d 未勾选发 `false` 而非省略；5e 保存失败必须**抛出**；5f 控件缺失时读为 no-op | V2、V3、V4 |

纪律说明（与项目既有做法一致）：
- 第 5 组是**真执行**而不是正则——写次数、请求体形状、异常传播这类性质用静态匹配钉不住。
- vm 上下文里**没有 `Date`**（既有两套 UI 测试同样如此），新代码不得依赖它。
- 注释里不出现以 `return` 开头的行；不把调用插进 `syncPlayerProgress();` 与 `updateNowMarquee();` 之间
  （`test_ui_renderer_transport.js:197` 断言该相邻模式恰 6 处）。

---

## T10 变异矩阵（在仓库外副本 `%TEMP%\fnaudio-r124-copy` 执行，12 条全灭）

控制组**先绿**：Python `Ran 2443 OK (skipped=3)`、Node **73** 个 JS 文件 0 失败。
副本 `skipped=3` 比本机 `skipped=2` 多的那 1 项是 `src/tests/test_offline_verification_script.py:236`
——副本不含 `artifacts/`，发布证据索引按设计跳过，属环境差异，已在根文档写明而不是当失败排查。

| 编号 | 变异 | 杀手 | 结果 |
| --- | --- | --- | --- |
| V1 | 删掉 `chooseCurrentFolder` 的 runtime 分支（保存落回音乐库兜底） | `test_ui_runtime_settings.js` 第 3 组 | 红（杀灭） |
| V2 | 保存后相信自己的点击而非服务端回显 | 同上 5c | 红（杀灭） |
| V3 | 请求体发文本布尔 `String(input.checked)` | 同上 5c | 红（杀灭） |
| V4 | 被拒绝的保存不再抛出、静默 `return null` | 同上 5e | 红（杀灭） |
| V5 | 切到运行 pane 不再回读 | 同上第 3 组 | 红（杀灭） |
| V6 | UI 常量改成 `libraryConnectionPool`（与服务端键脱钩） | 同上第 2 组 | 红（杀灭） |
| V7 | 复选框从 runtime pane 移入 metadata pane | 同上第 1 组 | 红（杀灭） |
| V8 | GET 硬编码 `True` 而非运行谓词 | `test_runtime_config_reports_the_value_the_pool_actually_honours` | 红（杀灭） |
| V9 | POST 强转 `bool(payload.get(...))` | `test_runtime_config_rejects_text_boolean_without_changing_the_switch` | 红（杀灭） |
| V10 | 把排空挪到原地提交**之前** | `test_runtime_config_turning_the_pool_off_drains_handles_after_the_commit`（+ `test_a_config_commit_hands_the_committed_config_to_the_pool_applier`） | 红（杀灭） |
| V11 | 短路掉 `commit_config_update` | `test_runtime_config_persistence_failure_leaves_the_running_switch_alone` | 红（杀灭） |
| V12 | 把 `/api/config/runtime` 加进 `PUBLIC_API_PATHS` | `test_runtime_config_requires_the_settings_scopes` | 红（杀灭） |

`SURVIVORS=none`；每条变异当场还原并复绿。

**本轮唯一的真实回归不是变异抓到的，是控制组抓到的**：`src/tests/test_server_lifecycle.py:175`
`test_the_pool_default_is_no_longer_invented_at_startup` 禁止 `server.py` 出现该键字面量，
新路由初版直接 import 常量并按字面名写盘 ⇒ 全量套件红。本地当时只单跑本轮 6 项新测试，全绿，漏判。
处理：**不放宽旧守卫**，改由 `library.py:1905` 提供键的唯一公开出口（T1），`server.py` 两个字面量复核 0 命中，
旧守卫 + 6 项新测试 `Ran 7 OK`。
另一面同样值得记：V10 这个真实缺陷方向，旧 lifecycle 测试面对它 **rc=0 杀不动**，只有本轮新增用例抓得到 ——
「旧测试全绿」不等于「旧测试有判别力」。

---

## T11 清单与三份根文档（`03d0ce3`）

| 文件 | 本轮改动 | 盘上取证 |
| --- | --- | --- |
| `SOURCE_MANIFEST.sha256` | 全部源码编辑完成后用 `tools/update_source_manifest.ps1` 刷新 ⇒ **704 条**（原 703） | 6 个改动文件逐文件 sha **MATCH**；`takeover_forensics` ⇒ drift 0 / stale 0 / unlisted 0；全文件 CRLF + 大写 hex 形状保持不变 |
| `TODO.md` | **L2 插入**本轮记录（1 行）；原 D9 条目（R123 记为 L1881，插入后在 **L1882**）按文本锚点翻成 `- [x]`，收口说明写在**同一行末尾**，不新增行 | 2213 行；开放 76 / 已关闭 1463；CRLF 0；控制字符 0 |
| `CHANGELOG_AI.md` | L2 插入 3 条（实现 / 测试+控制组+变异矩阵 / 收口+清单+提交） | 6709 行；flat run 855 条；newest-first True；0 CR / 0 换页符 / 0 NUL |
| `PROJECT_CONTEXT.md` | L2 插入 3 条规则：① 「本轮测试绿」没有全量套件背书就不算证据；② 副本纪律＝先刷清单再复制，`skipped` 差是环境差异；③ 同一配置键可在两条路径上有两个默认值，界面必须读运行进程 honour 的那个 | 0 CR |
| 校验 | `python -m tests.test_change_record` ⇒ `Ran 3 OK`；自制 flat-run 校验器三文件均 newest-first True | 行号因插入整体下移 1，后续定位一律用文本锚点 |

**未做也不该被误读为已做的事**：本条关闭**不**改池的默认值，**不**主张「池在真机上长期安全」——
那条证据仍在 P0 段真机半（R121 从代码桶 L154 拆出的同源条目）挂着，设备段一行未改。

---

## 1 这个目标还剩多少没完成（按四项终止条件逐条回答）

磁盘取证（R124 收口后）：

1. **可离线代码项清零：未完成。** 仍开 **18** 条（主表 16 + L546 审查范围 + L794 拆分）。
   本轮 18 → 18（关闭的是决策项，不是代码项），新立 0 条 ⇒ 反增长约束满足（新立 ≤ 关闭）。
2. **设备/外部项移出逐轮任务：已达成，须保持。** 44 条全部留在设备段，36+ 轮无一条被盲改；本轮同样 0 改动。
3. **需产品决策项全部落地：接近完成。** 决策段从 2 条降到 **1** 条：仅剩 L1878
   （R73 `allow_disk=False` 不生效的取舍）。该条**不能靠离线测试关闭**——它要的是真机上
   「翻页是否真的不打磁盘」的行为证据；测试机已授权（fnOS `198.51.100.24:5666`、SSH 22、样本
   `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`），可在下一轮取证。
4. **终止前完整离线门禁：本轮已过一次**（round190：exit 0 / Python 2443 OK / JS 73 / 清单 704 / `diff --check` 空）。
   但它只是每轮动作；终止要求第 1、3 项成立之后再跑一次。

=> **距终止的最小工作量 = 代码 18 条 + 决策 1 条 = 19 条**，按每轮净关闭 1～3 条的节奏粗估 **8～14 轮**。
其中 4 条依赖真机/外部材料，这类只能真机取证或并入设备段，**不得为凑数关闭**。
`maxGoalRounds = 72`、已完成 36+ 轮（本轮 R124） ⇒ 不据此终止，也不修改终止条件。

### R125 排期（已裁定，按文本锚点定位）

1. **原 L69 投送三段口径（现主表 L72 区）**：负责人裁定 D —— 投送即停本机 + 本机播放意图抢占投送 + 投送结束不自动续播。
   需补 `isIncomingRendererSession()` 的消费者：`loadCurrent()` 非 remote 分支、`audio.ontimeupdate`、MediaSession play/pause。
2. **原 L150 分页口径（现主表 L153 区）**：负责人裁定 A+C —— 口径写进 docs 后关闭 + 写路径 `None`→`""` 与旧库一次性收敛。
3. **可选并行**：真机取证 L1878 `allow_disk=False`（`cover_cache._cache_key` 内部 `cover_source_version(item)`
   用了默认 `allow_disk=True`）与 D5 封面缓存口径。
4. **R124 附注的残余风险**（若排到）：`loadRuntimeSettings()` catch 里对 `#folderSaveStatus` 的无守卫写入。