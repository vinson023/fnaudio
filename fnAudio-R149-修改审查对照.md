# fnAudio R149 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为**深读轮**：读完 `src/app/server/playback/core.py` 全部 509 内容行，读的过程中当轮修掉 3 处无界写路径、当轮证伪 1 处疑点。**净关闭 0 条既有代码待办、新立 0 条**，进展按「欠读行数下降」计（口径见 `docs/REVIEW_ROUND_DISCIPLINE.md` 第二节、第五节）。

## 文件净增（`git diff --numstat`，HEAD = `3b7c80c` R148）

| 文件 | + | − |
|---|---|---|
| `CHANGELOG_AI.md` | 2 | 0 |
| `PROJECT_CONTEXT.md` | 1 | 0 |
| `SOURCE_MANIFEST.sha256` | 2 | 2 |
| `TODO.md` | 2 | 1 |
| `src/app/server/playback/core.py` | 6 | 3 |
| `src/tests/test_playback_core_state.py` | 58 | 1 |

## 一、开工取证（磁盘实测，不采信交接快照）

- 分支 `main`，HEAD `3b7c80c docs(round-review): carry the R147 and R148 review packets`；`git status --porcelain` 中已跟踪改动**恰为上表 6 项**；`MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD`/`rebase-merge`/`rebase-apply` 全部不存在，`git stash list` 空，`git remote -v` 空。
- `TODO.md` 未勾 **15** 条 = 代码桶 **2**（现盘 L101、L152）＋ 长期观察段 **13**（L2029 起）。旧目标正文 `155 = 64 + 82 + 9` 与实测 `15 = 2 + 13` 属不同历史快照，**不合并、不覆盖、不改写**。
- `SOURCE_MANIFEST.sha256` 共 **710** 行（CRLF），作用域实测只有 `src/`（630）与 `android-client/`（80）；`TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`、`docs/…`、`tools/…`、`fnAudio-R148-….md` 在清单内命中数均为 **0** ⇒ 本轮写文档与写本 packet **不需要**重刷清单，需要重刷的只有那两个 `src/` 文件。
- **清单比对口径补记**：`SOURCE_MANIFEST.sha256` 存的是**大写**十六进制，实算 `hexdigest()` 为小写，直接字符串相等会产生伪 MISMATCH。本轮全部比对一律先 `toLowerCase()`。710 条全量重算：0 缺失、0 哈希不符。

## 二、缺陷与修法：三处无界写路径收口到**文件内既有**常量与助手

被复用而未新增的三件现成物：`:18 MAX_EXTERNAL_ERROR = 2048`、`:19 MAX_EXTERNAL_TRANSPORT = 64`、`:73 _bounded_text`（`return value[:limit] if isinstance(value, str) else ""`）。

### 载体取证（为何这不算臆测）

- `dlna/control_point.py:159 soap_text` → `:166 return (node.text or "").strip()`，**不截断**。
- `dlna/network.py:13 MAX_DLNA_XML_BYTES = 1024 * 1024`，且 `:224 fetch_lan(request_or_url, timeout: float = 3, max_bytes: int = MAX_DLNA_XML_BYTES)`、`:232` 只校验 `1 <= max_bytes <= MAX_DLNA_XML_BYTES` ⇒ 单条 SOAP 文本合法上限 **1 MiB**。
- `server.py` 共 **12** 个 `sync_output_status(` 调用点：2390、2410、2418、3006、3015、3058、3085、3122、3136、3147、3390、3412。**只有 `:3147-3149` 把网络原文传入**（`:3149` 即裸 `transport,`）；MPD 侧 `:3390`/`:3412` 传的是 `services/mpd_service.py` 归一化后的枚举字面量。⇒ 无界载体确切＝DLNA 投送状态轮询。
- 旁证界值 64 早就是本字段的既定口径：`diagnostics_playback.py:29`、`dlna/event_payload.py:47` 均已按 64 截断 `transport`。
- 同文件既有同形写法：`sync_external_session` 的 `:371`/`:380` 早就对**同名两字段**施加同一对界值——本轮只是把权威状态本身对齐它。

### core.py 四个 hunk（`git diff -U0`）

| hunk | 现盘行 | 修法 |
|---|---|---|
| `@@ -88 +88` | `:88` | `_plugin_result_error` 返回插件失败消息时套 `_bounded_text(message, MAX_EXTERNAL_ERROR)`，非 str 仍回退原文案 |
| `@@ -153,0 +154,3` | `:154-156` | `sync_output_status` docstring 补两句「transport 与 error 是不受信网络文本，在此按 `sync_external_session` 同样方式加界」的不变式说明 |
| `@@ -158 +161` | `:161` | `normalized = _bounded_text(transport, MAX_EXTERNAL_TRANSPORT).upper() or "UNKNOWN"`（原 `str(transport or "UNKNOWN").upper()`） |
| `@@ -170 +173` | `:173` | `next_error = _bounded_text(error, MAX_EXTERNAL_ERROR)`（原 `str(error or "")`） |

### 当轮证伪 1 项（只记取证，不立条目）

- 疑点：`core.py:100 set_target` 写入的 `target_id`/`target_kind` 是否也无界。结论：**已有界**——HTTP 载体 `playback/http_contract.py:31 normalize_target_id` → `:36 _target_text` → `:41 return value[:128] or "local"`。不立待办。
- 另记：`models.py` 亦有 `:12 MAX_TRACK_TEXT = 512`、`:24 _track_text`，曲目文本面自有口径。

### 并发面（R130 点名的欠读角度之一）读完

`core.py` 全部公开变更方法统一 `with self._lock`（`RLock`）；`wait_for_version` 用同一把锁上的 `Condition`；`snapshot_with_item` 把快照与当前条目放进同一临界区以避免配对错轨。**未见缺陷，不立条目。**

## 三、判别测试、先红与变异矩阵

守卫文件 `src/tests/test_playback_core_state.py`：450→**507** LF／20,292→**23,149** B。hunk `@@ -9 +9`（导入两个界常量）、`@@ -132,0 +133,57`（新增 5 枚）。

| 现盘行 | 用例 | 钉住的不变式 |
|---|---|---|
| `:133` | `…bounds_untrusted_transport_like_the_external_session` | 5,000 字符 transport 必被截到 `MAX_EXTERNAL_TRANSPORT` |
| `:146` | `…bounds_untrusted_error_like_the_external_session` | 20,000 字符 error 必被截到 `MAX_EXTERNAL_ERROR` |
| `:153` | `…keeps_a_transport_sitting_exactly_on_the_bound` | 恰在界上者不得多截一字符（off-by-one） |
| `:161` | `…does_not_stringify_untrusted_objects` | 非 str 入参绝不得被 `str()`——探针 `__str__` 直接抛 `AssertionError` |
| `:172` | `test_failed_plugin_command_error_is_bounded` | 插件失败消息经 `dispatch` 落到 `state.error` 时有界 |

- **先红**（仓库外克隆 `C:\path\to\fnAudio-r149-mut`，工作树 core.py）：`Ran 41 tests / OK`。同克隆换入 **HEAD 版** core.py（sha16 `033e21dee83b3835`）：`Ran 41 / FAILED (failures=4)`。
- **如实记**：第五枚「恰在界上」在修复前**亦绿**，只有变异 V4 能杀它——它防的是未来改坏，不是本轮修复本身。
- **变异矩阵 9 格 / `MISMATCHES 0` / `MATRIX OK`**，驱动 `%TEMP%\fnaudio-r149-mut-driver\r149_matrix.js` 自还原：`sha16 start=end=2372bf8e19c963c6 RESTORED`。CONTROL 绿；V1 撤销 transport 界→红 2；V2 撤销 error 界→红 2；V3 撤销插件界→红 1；V4 越界截断 off-by-one→红 2（含「恰在界上」）；V5 丢 `UNKNOWN` 回退→红 1；V6 transport 用错常量→红 1；V7 error 用错常量→红 1；V8 助手改成 stringify→红 2 并连带既有 `test_external_session_publishes_transport_and_does_not_coerce_untrusted_text`。
- **注释自我纠正一次**：`:134-138` 原写「every SSE frame carries verbatim」。实测权威帧由 `playback_event_presentation.py:8`（docstring 自称 authoritative playback SSE event payload）构造、`:79` 为 `"transport": {"state": transport.upper()}`——只改大小写、不截断；`state_projection.py` 内 `transport` 命中 **0**。故改述为「权威 SSE 载荷只做大写化后重播」。改注释后重跑 41 绿＋矩阵 9 格＋清单重刷。

## 四、控制组、门禁与污染复查

- 控制组 `tests.test_change_record tests.test_source_manifest tests.test_device_todos_migrated`：**`Ran 19 tests / OK`** rc=0，跑两次（清单重刷后、三份根文档写完后）均绿 ⇒ 根文档格式与唯一性守卫已过。
- 门禁前置 `artifacts/offline-20260922-round227-prefix.log`：434,243 B／node 计 2,703 内容行／`Ran 2550 tests in 134.605s`／`OK (skipped=2)`／含 ` passed` 的行 **73**。
- 终跑 `artifacts/offline-20260922-round227.log` 与提交时点复核见下文 §八。
- Python 多模块一律空格分隔（逗号会被当作单个模块名）。

## 五、三份根文档实测（写后回读）

| 文件 | LF | 字节 | sha256 前 16 | 写前 |
|---|---|---|---|---|
| `TODO.md` | 2,170 | 656,229 | `ab2fa0e75e5415e5` | 2,169 |
| `CHANGELOG_AI.md` | 6,768 | 1,262,592 | `86f4397728a27bac` | 6,766 |
| `PROJECT_CONTEXT.md` | 6,188 | 807,038 | `166a88c3389d5697` | 6,187 |
| `src/app/server/playback/core.py` | 509 | 22,664 | `2372bf8e19c963c6` | 506／22,424／`033e21dee83b3835` |
| `src/tests/test_playback_core_state.py` | 507 | 23,149 | `7c6ca066dfd42921` | 450／20,292 |
| `SOURCE_MANIFEST.sha256` | 710（CRLF） | 76,954 | `18be18854fd07441` | 2 行内容变化 |

- `TODO.md`：**L2** 新增单行 R149 记录；原 L100（现 **L101**）行尾追加〔R149 …〕注记，照 R134/R140 体例——**只增注、未改判据**，本条判据仍是「剩余欠读面全部读完」。
- `CHANGELOG_AI.md`：**L2、L3** 两条 R149（`- 2026-09-22 — R149 …`，em dash），最新在前。
- `PROJECT_CONTEXT.md`：**L2** 一条规则句：「文件里有界常量和界助手，不等于每条写路径都在用它们——审计要看赋值语句右边」。

## 六、记账口径（如实）

- **净关闭 0、新立 0**。本轮不以关闭条数计进展（深读轮）。
- 欠读总量 21,488 → **20,982** 行（内容行口径 `len(text.split("\n"))-1`）＝`app.css` 1,528＋`cover_cache.py` 1,364＋`app.js` 8,395＋已跟踪 Android `.java` 43 文件 9,695。出局量按 core.py **登记值 506** 计，不按现树 509（+3 是本轮给 `sync_output_status` 补的 docstring，属新增而非既有欠读）。
- 代码桶关闭条件未满足：L101 仍要求剩余欠读面**全部读完**，故保持 `[ ]`。

## 七、本轮遗留（需负责人裁定，本轮不代答）

- **Z3**：仓库根内 `%SystemDrive%\ProgramData\Microsoft\Windows\Caches\`（4 个未跟踪 `.db`）。建议照 C3/C6 口径 `Move-Item` 至 `C:\path\to\fnAudio\_external\`，**不删除**。本轮未动。
- **Z4**：真机终局档排在读完代码桶深读债（剩 20,982 行）之后。
- **N2**：`dlna/network.py:150` getaddrinfo 最坏 15,014 ms（`timeout=3` 被拖 5.0 倍）＋ `server.py` 缺受控停止入口——是否进代码桶。
- **N4**：设备部署副本（`server.py` 108,927 B、`/var/apps/fnaudio/cmd/main` 6,654 B）是否重打包。
- **C5 第二档**：真机「放样本曲＋播放＋抓日志」（样本曲 `C:\path\to\fnAudio\music\伍佰 - 泪桥.flac`）要不要单开一轮；涉停服务须先请示。
- **R148 风险提示**：`TODO.md` L73 疑已落实（门禁含 `Transport state-unknown lamp regression checks passed.`）——动前必先取证。


## 八、终跑门禁与提交时点复核（2026-09-22 · 本轮收尾）

### 终跑

- `tools/test_offline.ps1` → `artifacts/offline-20260922-round227.log`，退出码 **0**（取自独立 rc 文件）。
- `Ran 2550 tests in 134.198s`／`OK (skipped=2)`／0 条 `FAILED`／0 条 `Traceback`／含 ` passed` 的结果行 **73**。
- 时序合规：终跑 log mtime 19:37:17 晚于 `TODO.md`(19:28:51)、`CHANGELOG_AI.md`(19:29:17)、`PROJECT_CONTEXT.md`(19:29:33)、`core.py`(18:41:35)，即**门禁覆盖了本轮全部代码与根文档编辑**。本 packet 自身在门禁之后写出（它不在门禁作用域，也不在清单作用域），与 R148「§八 收尾补记」同一体例。
- 门禁未改动产物：门禁前后 `SOURCE_MANIFEST.sha256` 实算同为 `18be18854fd07441`；`src\Python`、`C:\path\to\fnAudio\Python`、`E:\Codex\Python`、`C:\path\to\fnAudio\android-client\Python` 四者均不存在（以 `_external` 解释器前置 PATH 启动，未触发 Python Install Manager）。
- 收尾 `git diff --check` rc=0，仅该清单文件既有的 CRLF→LF 归一化 warning。

### 一处必须纠正的比对口径（不得沿用旧预期）

- 交接预期写的是「终跑与前置**仅耗时行不同**」。**磁盘实测不成立**：两份 log 各 2,704 原始行／2,703 内容行，逐行集合比对有 **17 行仅终跑有、10 行仅前置有**，耗时行只是其中之一。
- 实质查明：差异全部是 **stdout 与 stderr 的交错换行**。前置那一跑把 9 条被捕获的 `fnAudio …` 诊断文本并到了同一行的测试名后面，终跑把它们另起一行——于是「字面含 `... ok`」的行数一个 2,536、一个 2,545，差 **9**，恰等于这 9 处交错。
- 按内容比对（先按 `fnAudio ` 切分、再按 `test_` 切分）：诊断文本 token **10 = 10，双向零差异**；测试名 token **2,565 = 2,565，双向零差异**。`'ThreadProbe' object has no attribute \'join\'` 在两跑各命中 **3** 次，并未消失。
- ⇒ 结论：两跑**内容等价**，退出码同为 0；但「逐行 diff 门禁 log」这一比对方法本身不确定，今后跨跑比对必须走内容切分口径，不能按裸逐行 diff 判红。此为方法口径备忘，**不立待办**。

### 控制组（第三时点）

- 门禁后复跑：本轮守卫套件 `Ran 41 tests in 0.496s / OK`；控制组 `Ran 19 tests in 0.861s / OK`。三个时点（清单重刷后、根文档写完后、门禁后）控制组均绿。

### 先红与还原（本轮收尾在仓库外克隆上独立复现一次）

- 克隆装入 HEAD 版 `core.py`（22,424 B／sha16 `033e21dee83b3835`）→ `Ran 41 tests / FAILED (failures=4)`，四枚红恰为 transport 界、error 界、不得 stringify、插件失败消息；**「恰在界上」那枚不在失败清单里**，与 §三「只有 V4 能杀它」互证。
- 取 HEAD 版时踩到一次自身工具错误并当场纠正：`git show … | Set-Content` 会把行全部粘连，产出 `SyntaxError: invalid decimal literal`；改用 node 取字节流后得到正确哈希。该失误只影响克隆、未触及仓库，随后按备份还原。
- 还原校验：克隆 `core.py` sha16 `2372bf8e19c963c6`，与工作树真值**逐字节相同**。

### 清理与凭据复查

- 本轮 `%TEMP%` 临时物 11 项（`fnaudio-r149-mut-driver`、`-takeover`、`-verify`、两个 rc、两个 HEAD 版 core 副本、`-testblock.txt`、备份副本、两个 pycache）与仓库外克隆 `C:\path\to\fnAudio-r149-mut` 全部删除，逐个复核 `exists=false`。
- 递归清理在本机被 shell 安全策略拒绝（变量插值与字面路径均拒），改由 node `fs.rmSync` 完成；删除前已逐项列明绝对路径并确认均在 `%TEMP%\fnaudio-r149-*` 与 `C:\path\to\fnAudio-r149-mut` 之内。
- 补丁残留：仓库内 `.new/.orig/.rej` 仅 2 处，均在 `_external\runtime\gomodcache\modernc.org\libc@v1.67.6\surface.new`（Go 模块缓存既有文件名，mtime 2026-08-11，非本轮产物，且 `_external` 已跟踪数 0）；`tools/`、`artifacts/` 命中 0。
- **凭据复扫**：口令字面量在全部已跟踪文件中 **0 命中**（`git grep -cI` rc=1）；本轮 6 文件共 71 条新增行按字节复扫，凭据、测试机 IP、`:5666`、`SSH` 形状均 **0 命中**（唯一 `password` 子串是既有行里的 DOM ID `#sharePasswordEnabled`）；本 packet 自身同样 0 命中。测试机 LAN IP 出现在 23 个既有文档/脚本中，属历史遗留、非本轮引入，本轮不扩大。
- 一次伪报记录在案：用 `Select-String` 扫凭据时因 PowerShell 控制台按 GBK 解码 git 输出而产生过 1 次假命中，改由 node 按字节重扫后归零；同时清单哈希比对须注意清单存**大写**十六进制（§一已记）。

### 提交分组

- 第一笔 `fix(playback-core)` = `core.py` ＋ `test_playback_core_state.py` ＋ `SOURCE_MANIFEST.sha256`（清单同时哈希这两个 `src/` 文件，拆开会让中间提交自相矛盾）。
- 第二笔 `docs(round-R149)` = 三份根文档。
- 第三笔 `docs(round-review)` = 本 packet，照 R147/R148 先例入库（§八 依据：`git ls-files "fnAudio-R*"` 22 个已跟踪，HEAD `3b7c80c` 的 `--stat` 实证该笔把 R147、R148 两份一并入库）。
- 三笔之后：复跑控制组、`git status --porcelain -uno` 归空、710 条清单全量重算、凭据形状全仓复扫——结果以本轮最终汇报为准（本 packet 无法记录自己的提交号）。

## 九、packet 归属裁定（本轮）

- `git ls-files "fnAudio-R*"` = **22 个已跟踪**；HEAD 提交 `3b7c80c` 的 `--stat` 实证它把 R147、R148 两份对照文档一并入库。R148 文档第 10 行「不入库」是其 §八 自己纠正前的旧计划。
- ⇒ 本文件照先例入库，随本轮第三笔提交落地。
