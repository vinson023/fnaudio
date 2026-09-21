# fnAudio R138 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮共 12 个被跟踪文件改动，源码与测试合计 **+155 −5**；另 3 份根文档与 1 份清单。未跟踪文件一律不入库。

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | src/app/server/config.py | +3 −0 | X7=A 设置项三处注册 |
| 2 | src/app/server/cue_parser.py | +12 −2 | X10=A CUE 重复 INDEX 01 |
| 3 | src/app/server/metadata_local_lyrics_cache.py | +21 −0 | X7=A 读取器 |
| 4 | src/app/server/metadata_service.py | +9 −3 | X7=A 两条道接线 |
| 5-8 | src/tests/test_{config,cue_parser,metadata_local_lyrics_cache,metadata_service}.py | +110 −0 | 8 枚判别测试 |
| 9-12 | TODO.md / CHANGELOG_AI.md / PROJECT_CONTEXT.md / SOURCE_MANIFEST.sha256 | 记录 | 收口 |

---

## H1 `C:\path\to\fnAudio\src\app\server\config.py` L48 — 默认表登记
```
+        "metadata_lyrics_cache_max_bytes": 8 * 1024 * 1024,
```
审核：默认值与缓存模块自带 `DEFAULT_MAX_BYTES` 同数（8 MiB），落位紧邻 `metadata_cache_max_bytes` 之后，保持「同类相邻」既有排布。若只登记此处而不登记区间表，用户写的值就不会被夹取——见 H2/H3。

## H2 `config.py` L127 — `load_config` 区间表
```
+        "metadata_lyrics_cache_max_bytes": (8 * 1024 * 1024, 64 * 1024, 64 * 1024 * 1024),
```
审核：**读侧**夹取。区间 `[64 KiB, 64 MiB]` 与 `metadata_local_lyrics_cache` 的 `MIN_MAX_BYTES`/`MAX_MAX_BYTES` 逐字相同；这一枚是变异 V2 的目标（删掉即被 `test_lyrics_cache_budget_is_clamped_on_load_alone` 杀）。

## H3 `config.py` L176 — `save_config` 写侧夹取
```
+        "metadata_lyrics_cache_max_bytes": _bounded_int(config.get("metadata_lyrics_cache_max_bytes"), 8 * 1024 * 1024, 64 * 1024, 64 * 1024 * 1024),
```
审核：**写侧**夹取，与 H2 同区间。V2/V8 首轮曾在「只考验 save 侧」的断言下存活，教训已写入 `PROJECT_CONTEXT.md` L2。

## H4 `C:\path\to\fnAudio\src\app\server\cue_parser.py` L98-104 — 循环局部旗标
```
+    index01_seen = False
```
审核：刻意**不**挂到 `current` 字典上——`library.py` 按键读取这些 dict，多一个字段会外溢到解析器之外（注释 L99-103 已写明该理由）。

## H5 `cue_parser.py` L135 — 轨边界复位
```
+            index01_seen = False
```
审核：本 hunk 是 V6 的目标。若不在 `TRACK` 分支复位，轨 1 的答案会污染整张谱，后续轨全部退回 `start 0.0`；由 `test_the_repeated_index_guard_resets_for_the_next_track`（`test_cue_parser.py` L344）判别。

## H6 `cue_parser.py` L145-147 — 「取首个、拒后续」
```
-            if index_line and int(index_line.group(1)) == 1:
+            if index_line and int(index_line.group(1)) == 1 and not index01_seen:
                 current["start"] = cue_time_seconds(index_line.group(2))
+                index01_seen = True
```
审核：这是本轮唯一带**行为变更**的旧行改写（−2）。INDEX 00（pregap）与 ≥02（cue point）原本就不许移动起点，语义未动；新守卫只拦「同一轨第二条可解析的 INDEX 01」。

## H7 `C:\path\to\fnAudio\src\app\server\metadata_local_lyrics_cache.py` L28 — 单一键名
```
+CONFIG_BYTES_KEY = "metadata_lyrics_cache_max_bytes"
```
审核：键名收在缓存模块内，调用方不再各自重抄「默认＋上下界」三个数，避免漂移。

## H8 `metadata_local_lyrics_cache.py` L43-57 — 唯一读取器
```
+def bytes_limit_from_config(config):
+    value = DEFAULT_MAX_BYTES
+    if isinstance(config, dict):
+        value = config.get(CONFIG_BYTES_KEY, DEFAULT_MAX_BYTES)
+    return _bounded_bytes(value)
```
审核：非 dict／缺键／非整数／`True` 一律退默认而不抛；越界值在此就地夹取，使 `snapshot()["bytes_limit"]` 报告的永远是缓存真正执行的值。V7（访问器忽略设置恒返默认）指向此处。

## H9 `C:\path\to\fnAudio\src\app\server\metadata_service.py` L48 / L618 / L1976 — 两条道接线
```
+from metadata_local_lyrics_cache import LocalLyricsCache, bytes_limit_from_config, combined_snapshot
+        self._local_lyrics_cache = LocalLyricsCache(
+            lambda path: read_local_lyrics(path, self.config),
+            max_bytes=bytes_limit_from_config(self.config),
+        )
```
审核：`MetadataProviders`（L618）与 `MetadataService`（L1976）是**两个独立构造点**，此前 `max_bytes` 从无实参——即设置项存在但整条链断开。V4（两处都不传）与 V5（只改一处）分别对应；`test_metadata_service.py` L72 对三条 lane 逐一断言，防「一处生效一处仍钉默认」。

## H10-H13 测试侧（+110，零删除）
`test_config.py` L355/L369/L398+L413、`test_cue_parser.py` L333/L344、`test_metadata_local_lyrics_cache.py` L191/L200、`test_metadata_service.py` L72/L90，共 8 枚，逐枚对应 V1-V8。要点：`test_a_missing_or_broken_setting...` 用 tuple 而非 dict 承载用例（`True` 哈希为 1，dict 字面量会静默丢掉一例）。

## H14 文档与清单
- `TODO.md` L2 主记录；9 条勾选关闭位 L48/L49/L113/L115/L122/L129/L160/L804/L1889；L99 追加 X12=A 数字重算（判据未动）；L1878 迁入设备段（X1=A，文本原样）；L2082 第五桶声明（X2=B）。
- `CHANGELOG_AI.md` L2/L3 = R138 两条记录。**接管修正**：两条最初被插成 `R138主 / R137主 / R138收口`，违反最新在前，已交换 L3/L4。
- `PROJECT_CONTEXT.md` L2 = 读写两侧各设一枚夹取断言。
- `SOURCE_MANIFEST.sha256`：707 条、sha `61e6ddd0…`（大写十六进制）。

## 证据
变异 V1-V8 全 KILLED（仓库外副本）；prefix 门禁与终跑同值 `Ran 2491 / OK (skipped=2) / exit 0 / passed 73`。
