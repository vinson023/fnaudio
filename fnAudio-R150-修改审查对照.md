# fnAudio R150 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为**设备段处置轮**：把取证单 `docs/external-acceptance.md` 固定编号 L1860 在真机实测到的「`fetch_lan(..., timeout=3)` 被一次地址解析拖成 15～20 秒、投送 worker 整段被占住」变成**代码里的可证伪上界**。**净关闭 0 条既有代码待办、新立 0 条**（0 ≤ 0），收益记在终止条件 (2)（设备/外部项移出逐轮任务）。

## 文件净增（`git diff --numstat`，HEAD = `59371b7` R149 packet）

| 文件 | + | − |
|---|---|---|
| `CHANGELOG_AI.md` | 2 | 0 |
| `PROJECT_CONTEXT.md` | 1 | 0 |
| `SOURCE_MANIFEST.sha256` | 3 | 3 |
| `TODO.md` | 1 | 0 |
| `src/app/server/dlna/network.py` | 67 | 3 |
| `src/tests/test_dlna_network.py` | 151 | 1 |
| `src/tests/test_dlna_protocol.py` | 17 | 4 |

## 一、开工取证（磁盘实测，不采信交接快照）

- 分支 `main`，HEAD `59371b7 docs(round-review): carry the R149 review packet`。已跟踪改动**恰为上表 7 项**；`MERGE_HEAD`／`rebase-merge`／`rebase-apply`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG` 六探针全部不存在；`git ls-files -u` 0 行；暂存区 0 文件；`git stash list` 空；`git remote -v` 空。
- 本轮**改动文件全量实测**（bytes／LF／CR／sha256 前 16 位大写）：

| 文件 | 现盘 | HEAD |
|---|---|---|
| `TODO.md` | 660,720／2,171／CR 0／`202C17CF82CFBC8F` | 656,229／2,170／`AB2FA0E75E5415E5` |
| `CHANGELOG_AI.md` | 1,265,954／6,770／CR 0／`8CF506F2B4E172CA` | 1,262,592／6,768／`86F4397728A27BAC` |
| `PROJECT_CONTEXT.md` | 808,650／6,189／CR 0／`99A2707CF62A4C22` | 807,038／6,188／`166A88C3389D5697` |
| `SOURCE_MANIFEST.sha256` | 76,954／710／CR 710／`8E6AC28455CC9637` | 76,244／710／`31C892B28128BE23` |
| `src/app/server/dlna/network.py` | 16,195／339／CR 0／`96B83B6C8C2D998D` | 12,561／275／`FBBECCE69E7AC786` |
| `src/tests/test_dlna_network.py` | 62,102／1,195／CR 0／`822B09660FD7ED37` | 54,361／1,044／`3D317177BBB4F906` |
| `src/tests/test_dlna_protocol.py` | 96,797／2,015／CR 0／`70F87D123B88FF2D` | 95,917／2,002／`E35E974B18E23996` |

- 清单作用域实测：`SOURCE_MANIFEST.sha256` 共 **710** 行，`src/` **630** ＋ `android-client/` **80**，其他 **0**；`TODO.md`、`CHANGELOG_AI.md`、`PROJECT_CONTEXT.md`、`docs/`、`tools/`、上一轮 packet 在清单内的命中数**均为 0** ⇒ 写根文档与本 packet **不需要**重刷清单，需要刷的只有那 3 个 `src/` 文件。全量 710 条逐文件重算：**0 缺失、0 哈希不符**；本轮 3 个 `src/` 文件逐条 **MATCH**（清单存**大写**十六进制，实算须先 `upper()`，否则产生伪 MISMATCH）。
- 桶计数（现盘）：`TODO.md` 未勾 **15** 条 = 代码桶 **2**（L102「R59 量化欠读清单」、L153「`src/app/ui/app.js` 剩余约 92% 符号仍是浅读面（381 个符号里深读过 31 个）」）＋ 长期观察段 **13**（L2030…L2112）。`docs/external-acceptance.md`（766 行）未勾 **28**／已勾 **17**。`docs/REVIEW_ROUND_DISCIPLINE.md`（73 行）`:25` 锚点 `observation-open-count = 13` **本轮未动**。三份根文档的行号**随 prepend 漂移**，本表只作当轮定位用，不作后续引用依据。
- 已裁定项**逐条复核未回退**：`tools/blutter` 已跟踪行 0 且目录不存在（D7／C 项）；`artifacts/0.1.174` 目录不存在且已跟踪行 **0**（该删除已入库）；`_external` 已跟踪行 **0**、含 5 个子目录（`.gradle-user`／`apk-analysis`／`pymanager-python-20260921`／`runtime`／`systemdrive-pollution-20260922`）；样本曲 `music/伍佰 - 泪桥.flac` 在盘且**未跟踪**；跟踪文件总数 **1010**；`git ls-files fnAudio-R*` = 23 份已跟踪对照文档（其中 R131–R149 的「修改审查对照」18 份）。
- **凭据扫描**：`git diff -U0` 的 **242** 条新增行按字节复扫，口令、测试机 IP、`:5666`、`SSH`／`ssh -p`、`password`、`admin` 命中**全部为 0**；唯一含 `21` 的新增行是清单里的一条十六进制摘要。既有行里的真机记录与 fixture 不属本轮引入，本轮不扩大。

## 二、缺陷与修法

缺陷（不是推测，是取证单 L1860 的实测记录）：黑洞 resolver 下 `socket.getaddrinfo` 单次耗时 **15,014 ms**，而它跑在 `fetch_lan(..., timeout=3)` 发出请求**之前**，`timeout` 管不到它；投送 worker 被整段占住，其他 peer 在此期间拿不到该 worker。

`src/app/server/dlna/network.py` 六个 hunk（`git diff -U0`）：

| hunk | 现盘行 | 修法 |
|---|---|---|
| `@@ -11,0 +12 @@` | `:12` | `from resource_limits import ConcurrencyGate` —— 复用仓内现成闸门，不新造计数器 |
| `@@ -28,0 +30,17 @@` | `:30-46` | `:30-37` 把 NAS 实测依据写进注释（`:32` 点名 `docs/external-acceptance.md, entry L1860`）并新增 `RESOLVER_WAIT_SECONDS = 1.0`；`:38-46` 写明「槽必须留在真正在跑的那件事上」并新增 `RESOLVER_IN_FLIGHT_LIMIT = 4`、`_RESOLVER_GATE` |
| `@@ -71 +89 @@`／`@@ -81 +99,3 @@` | `:89`、`:99-101` | `_cached_lan_addresses` 的两处 docstring 改写：把「释放锁」与「给等待加界」分开，指向新助手 |
| `@@ -91 +111 @@` | `:111` | 改道：缓存未命中时走 `_lan_addresses_within_budget(...)`，不再裸调 `_lan_addresses` |
| `@@ -164,0 +185,44 @@` | `:185-226` | 新增 `_lan_addresses_within_budget`：`:202-203` 饱和即拒；`:204-218` worker 内记结果，`finally` 先 `answered.set()` 后 `release()`；`:220` daemon 线程；`:221-222` 超时放弃；`:223-226` 原样中继异常或返回结果 |

六个必须写清的取舍：

1. **界值不是新发明的数**：`RESOLVER_WAIT_SECONDS = 1.0`（`:37`）严格小于调用方给的 `timeout=3`；`RESOLVER_IN_FLIGHT_LIMIT = 4`（`:45`）小于 `32 // 2`，与 GENA 接受路径早先定下的「同一四分之一 worker 池」理由是同一个，两处界值都由 §三 第一枚用例钉住。
2. **`_lan_addresses` 本体（`:168-172`）刻意不改**：它仍是仓内唯一真正做解析的函数，界加在调用方，语义才只落在投送路径上。
3. **`lan_http_url`（`:146`，其 `:149` 仍直调 `_lan_addresses`）刻意不改道**：那是入站地址校验路径，不占投送 worker；本轮不把界加到不在缺陷里的那条路上。
4. **迟到答案不入缓存**（`:196-200`）：缓存写入仍只在 `_cached_lan_addresses` 里，写的是包装函数的返回值；调用方已放弃时那条结果永不返回，于是也就永不被记住。
5. **失败口径保持单一**：新增的两条 `ValueError`（`:203` busy、`:222` in time）与既有那条（`:172`）同型，投送侧对「这个 endpoint 现在不能投」仍只有一个异常形状。
6. **刻意不做**：`server.py` 的受控停止入口属设备段 L1867（§十 第 2 项），本轮不碰；台账注记也不改写（§五）。

## 三、判别测试、先红与变异证明

新守卫类 `src/tests/test_dlna_network.py:1047 DlnaResolverBudgetTests`（hunk `@@ -1045 +1045,151 @@`；夹具 `:1058 URL`、`:1060 _Resolver`、`:1072 setUp`、`:1076 _gate_is_quiet`）：

| 用例 | 钉住什么 |
|---|---|
| `:1085` 界值钉子 | `RESOLVER_WAIT_SECONDS ≤ 2.0` 且 `≥ 0.1`；`RESOLVER_IN_FLIGHT_LIMIT < 32 // 2` 且 `≥ 1`——**数被悄悄改大，本文件仍绿而行为回退**，这一枚专门拦这件事 |
| `:1097` 直通与错误形状 | 正常解析与真失败都经包装原样通过，返回值与异常文案不变 |
| `:1109` 卡住必放弃 | 超时后必须抛 `in time`；**迟到答案不得进缓存**；在飞解析结束前槽不得提前归还 |
| `:1144` 饱和即拒 | 4 个槽全占时立刻拒：`waited < 0.2`、零次解析、零次请求 |
| `:1168` 槽随查询归还 | 放弃的调用方不返还槽：`active == 1`、`waiting == 0`，槽只随真实查询结束而回 |

变异证明（仓库外克隆 `%TEMP%/fnaudio-r150-clone`，驱动 `%TEMP%/fnaudio-r150/r150_matrix2.py`，`finally` 还原 FIXED）：

- 控制组先绿：`CONTROL rc=0 Ran 63 tests in 3.597s|OK`。
- **V1 即本轮先红证据**：把 `:111` 的改道撤回（＝HEAD 的调用形状）→ `rc=1 FAILED (errors=2)`，杀掉它的正是 `:1109`、`:1144` 两枚；该格耗时 **32.579 s**（其余绿格约 3.5 s），无界等待在时长上也留了痕。
- V2 `RESOLVER_WAIT_SECONDS=15.0` → 1 红（界值钉子）；V3 迟到答案写进缓存 → 2 红；V4 超时改抛 `TimeoutError` → 1F+2E；V5 门永不拒（`try_acquire` 短路）→ 12F+10E；V6 槽归还给放弃的调用方 → 2 红；V7 吞掉 worker 异常 → 3E；V8 中继处 `return None` → 1F+2E；V9 `LIMIT = 0` → 1F+1E。
- 末行：`CELLS 10 CONTROL_GREEN True MISMATCHES 0 MATRIX OK`。九格语义与驱动源码逐格对应，`killed_by` 全部具名。

GENA 侧配套矩阵（驱动 `r150_gena_matrix.py`，输出 `gena_matrix_out.txt`）：`CONTROL want=green got=green Ran 99 tests in 1.752s|OK`；`M1_bound_removed red`（`GENA_VALIDATION_LIMIT 4→32`）、`M2_waiters_removed red`（`GENA_VALIDATION_WAITERS 4→3`）、`M3a_stagger_kept_hardened green`、`M3b_stagger_unguarded_wait red`（等待条件换回旧写法）；末行 `GENA-HARDEN CELLS 5 MISMATCHES 0 OK`。

## 四、收紧既有守门用例（同轮改掉，不另立条目）

`src/tests/test_dlna_protocol.py` 的三个 hunk：`@@ -1518 +1518,9 @@`、`@@ -1520,3 +1528,4 @@`、`@@ -1525,0 +1535,4 @@`（净增 13 行）。改动只落在 `test_a_host_that_never_resolves_cannot_take_the_http_pool_with_it` 的等待条件上：`:1518-1523` 写归因注释，`:1524-1532` 改为「直到 16 枚洪水线程全部在界处留痕（`active + waiting + refusals >= flood`）」，`:1535-1538` 在放行前断言 `accounted == flood`，`:1544-1554` 保留反惰化与上限断言。

- 为什么旧写法不对：旧条件只看「峰值是否到达 limit」，那测的是**调度**而不是**上限**——主线程放行时最慢的 arrivals 还卡在屏障与 `subscribe()` 之间，随后它们找到空槽，`subscriptions` 就会超出 `limit + waiters`。
- 实证（也是收紧动机）：收紧前在真仓跑出 `Ran 162 tests / FAILED (failures=1)`，`AssertionError: 16 not less than or equal to 8`，traceback 指向旧行号 **1539**；现盘同一条断言在 **1552**，差 **13**，恰等于该文件 numstat 净增（17−4）⇒ 同一条断言、同一次失败，只是收紧前后的两个行号。**该 log（`g_repo.txt`）是收紧前的红，不得当作收紧后的结果引用**。
- 收紧后的支撑：`hunt_proto.txt` `mods=tests.test_dlna_protocol repeat=14 bad_runs=0`、`hunt_pair.txt` `mods=tests.test_dlna_network,tests.test_dlna_protocol repeat=10 bad_runs=0`（驱动 `r150_hunt.py`，ROOT 为真仓），以及 §七 的两轮完整门禁。

## 五、设备台账：跳过注记的理由（不是遗漏）

守卫 `src/tests/test_ledger_evidence_cards.py:788 test_ledger_records_never_claim_a_pending_code_action`（常量 `:105 CLOSURE_SUB`、`:146 CODE_ACTION_WORDS`、`:149 NOT_CODE_ACTION`）四条硬规则：取证注记必须**恰 4 行**且第 4 行以 `CLOSURE_SUB + 后续动作：` 开头；第 4 行必须含「不改」；注记与后续动作一律禁止出现 `已补`／`已安装信号`／`已实现`／`已修复`／`已改写`／`已改投送`／`已压缩上限`。

- 因此 `docs/external-acceptance.md:469`（缺口）与 `:470`（后续动作）**原样不动**、`:459` 的 L1860 复选框**不翻勾**；代码侧落地证据改放 `network.py:30-37` 的注释里（那里反向点名 entry L1860，形成台账→代码的单向指认）。
- 顺带记一处**陈旧指针且不改写**：`:469` 写的是「`dlna/network.py:150` 用 `socket.getaddrinfo`」，现盘该调用在 `:170`。台账记的是取证当时的事实，仓内纪律同时要求「不写死文档行号」，本轮按记录时点原样保留，并在本 packet 说明差异，避免下一轮误以为代码行号被文档钉住。
- L1867 现盘位置：`:550-564`（`:553` 未勾；`:562` 实测宿主宽限 10 s／mpd 5 s／90 s 兜底；`:563` 缺口 31 s > 10 s；`:564` 后续动作倾向「补受控停止入口」）。它要不要进代码桶属产品/范围裁定，见 §十 第 2 项。

## 六、目标正文与真实计数的漂移（不改写任何一方）

- 目标正文仍是 `155 = 64 + 82 + 9`；现盘实测是 `TODO.md` 未勾 15 = 代码 2 ＋ 长期观察 13，设备台账另有未勾 28／已勾 17。两组数**属不同历史快照**，本 packet 只做并列陈列，不合并、不覆盖、不改写目标正文。
- 另一处必须记在案：R147 的旧记录曾写「(4) 由 R150 终局门禁承担」。本轮确实跑了门禁，但那是**本轮改动后的终验**，不是「四项终止条件全部成立之后」的终止前门禁——目标四项尚未成立（§九）。该旧表述**原文不改写**，由本节声明其适用范围，防止后续轮把它读成 (4) 已完成。

## 七、门禁与清单

- `artifacts/offline-20260922-round228.log`（435,195 B／2,708 个 LF 行）：`Ran 2555 tests in 127.737s`、`OK (skipped=2)`、行首 `FAIL|FAILED` 命中 **0**、`Traceback` **0**、含 `checks passed` 的行 **70**、含 `passed` 的行 **73**（另 3 行是不带 `checks` 字样的套件收口行）、`gate228_rc.txt = 0`。用例数谱系：round226 `2545` → round227-prefix/round227 `2550` → round228 `2555`，**+5 恰为本轮 5 枚新用例**。
- **文档定稿后复跑**：`artifacts/offline-20260922-round229.log`（435,195 B／2,708 个 LF 行）同口径 `Ran 2555 tests in 134.766s`、`OK (skipped=2)`、0／0／70／73、rc 0。与 round228 逐行集合比对：仅前者独有 **1** 行、仅后者独有 **1** 行，且两行都是那条 `Ran ...` 耗时行 ⇒ 两跑内容等价。这一点让「代码＋清单＋三份根文档」在同一次门禁里被覆盖，不依赖 R149 那种跨跑差异解释。
- 时序如实：两份根文档的记录追加与 §八 的两处精度纠正发生在 round228 **之后**；round229 在文档定稿后跑，覆盖它们；**本 packet 写在 round229 之后**，而清单作用域（§一）不含 packet、仓内也无任何用例引用 packet 文件名，故 packet 自身只能由本节说明承担，不谎称被门禁覆盖。
- 收尾检查：`git diff --check` rc=0 且无输出；`git status --porcelain` 中已跟踪改动仍恰为 7 项、untracked 仍为既有历史目录；门禁与全部复跑均用 `_external` 内的外置解释器并把其目录前置进 `PATH`，未触发 Python Install Manager 向仓库落运行时；跟踪文件中 `.new`／`.orig`／`.rej` 命中 **0**。
- **工作物清理披露**：本节与 §三／§四引用的 `%TEMP%` 工作物——变异驱动 `fnaudio-r150\r150_matrix2.py`、`fnaudio-r150\r150_gena_matrix.py`、饱载复跑驱动 `fnaudio-r150\r150_hunt.py`、收紧前的真仓红日志 `fnaudio-r150\g_repo.txt`、整个仓库外克隆 `fnaudio-r150-clone`，以及散置的 `fnaudio-r150-forensic.py`——在本 packet 把数字抄录完成之后按收尾纪律删除（删除时记录的规模：`fnaudio-r150` 116 项、`fnaudio-r150-clone` 45 项）。packet 定稿时复点 `%TEMP%`，发现仍有两份本轮 scratch 输出未清：`r150_files.txt`（跟踪文件清单 1,011 行，可由 `git ls-files` 复算）与 `r150_tops.txt`（三份根文档表头快照，内容均已在盘上），随后一并删除；清完后 `%TEMP%` 内与本轮相关的工作物只剩 `fnaudio-offline-pycache-3d914ca76d7748d3948cc85cc7e9d49e`（门禁用的外置字节码缓存，不属本轮产物）。含义如实说明：删除只丢掉原始日志文件，矩逐逐格数字、`g_repo.txt` 的收紧前红读数与饱载轮数同时留存于 §三／§四／本节与 `CHANGELOG_AI.md` 最新记录；引用者应把这些数字视为本轮一次性观测，它们已不可二次复查。另就本节两处门禁日志的「行」做口径对齐：现场复点两份日志均为 435,195 B、行尾 CRLF、**按 LF 计 2,708 个行**（以 LF 分割得 2,709 段，末段为空），故本节从「2,709 原始行」改为与 `CHANGELOG_AI.md` 最新记录一致的 2,708；同理，`docs/external-acceptance.md` 实测 71,531 B／765 个 LF，§一所写「766 行」是分割段数。

## 八、三份根文档：本棒的两处精度纠正

- 复测发现 round228 之后的记录里「73 行 checks passed」属**口径混用**：73 是「含 `passed`」的行数，「含 `checks passed`」是 70（实测 70／3／73）。为避免记录虚高，各改一处内文、不新增行、不动桶计数：`TODO.md` L2 改为「含 `checks passed` 的行 70 行、含 `passed` 的行 73 行」；`CHANGELOG_AI.md` L3 改为「70 行 checks passed（含 `passed` 的行 73 行）」。改后 `TODO.md` L2 由 2,658→2,674 字符、文件 660,696→660,720 B（＋24）；`CHANGELOG_AI.md` L3 由 1,128→1,146 字符、文件 1,265,924→1,265,954 B（＋30）；两处均以字节安全方式改写（断言无 CR、无 BOM、尾 LF、锚点在该行内唯一命中且旧串已不存在），表内 §一 的现盘值即纠正后真值。
- 纠正后复跑（控制组）：`tests.test_change_record`＋`tests.test_source_manifest`＋`tests.test_device_todos_migrated` = `Ran 19 tests in 0.789s / OK`；`tests.test_ledger_evidence_cards` = `Ran 25 tests in 0.023s / OK`；记录校验器给出 `TODO run=139 malformed=0`、`CHANGELOG run=917`、`PROJECT_CONTEXT run=496`、三份最新记录同为 2026-09-22；随后由 round229 全量门禁再覆盖一次。
- 校验器还查出一处需要如实说明的形态：`CHANGELOG_AI.md` 的 R150 关键字命中行是 `[2, 3, 10]`——**L10 是 R147 旧记录原文里就含「R150」字样**（见 §六 第二条），不是本轮重复登记；本轮记录确实只有 L2、L3 两行。

## 九、记账口径

- 关闭既有代码待办 **0**；新立可离线代码项 **0**（0 ≤ 0，满足反增长约束）。本轮新发现一律当轮处置：GENA 守门用例竞态**当轮收紧并证伪**、台账陈旧指针**当轮记为取证时点事实**、文档计数口径混用**当轮纠正**，均**未另立条目**。
- L1860 **保持未勾**：代码上界已落地并有判别测试，但取证单判定线还含「多路投送并发时该占用对 SSE 与其他 peer 的影响」未测，卡的两半不同进度，不合并结案。
- 目标剩余量：(1) 代码桶 **2** 条；(2) 设备台账未勾 **28**（已勾 17）＋长期观察 **13**；(3) **已完成**（9 条产品决策项已一次性裁定）；(4) 终止前门禁**尚未到达**——四项未全成立。⇒ 继续开轮，既不因「已完成 36 轮」也不因 `maxGoalRounds = 72` 而终止，亦不改写终止条件。

## 十、待裁定（本 packet 不代答）

1. **L1860 结案口径**：代码上界已落地、真机并发挤兑未测——是保持未勾（本 packet 建议：保持未勾），还是承认「代码面已尽」后按代码面结案并把测量部分另计数。
2. **L1867 是否进代码桶**：`server.py` 补受控停止入口属代码动作，但其判定线依赖宿主宽限测量；建议下一轮先只补「可测性」而不改停止语义。
3. **是否批准第一档真机取证**：需澄清三点记录事实——SSH 端口是 **22**（21 上是 FTP）；取证若需停服务必须先请示；凭据严禁入任何已跟踪文件（本轮 §一 复扫 0 命中），样本曲 `music/伍佰 - 泪桥.flac` 保持未跟踪。
4. **R151 先做哪条代码待办**：`app.js` 浅读面条（381 符号深读 31）vs R59 量化欠读清单条。建议先做 `app.js`——它自带可判别的读面收敛口径，能量化欠读行数下降。
5. **是否放宽「不给 `_lan_addresses` 本体加界」**：现状把界加在投送侧调用方，校验路径 `lan_http_url:149` 仍无界。建议维持现状，除非真机证明校验路径也会被占。
6. **是否允许补 `test_dlna_network.py:1046` 的第二个空行**：新类前只有一枚空行（PEP8 E302 期望两枚）。仓内**无**任何 pycodestyle/flake8 守卫，既有同形位置见 `:726`→`:727`（HEAD 既有），故不构成缺陷。若裁定要补，须刷清单并重跑，本 packet 倾向**不改**。
7. **终局门禁与 D1 形式留点是否另行授权**：D1 已裁定 GPL-3.0+、开源暂不托管、`NOTICE`／`AUTHORS` 署名 `vinson023`；落地形式（新增三份文件的具体内容与是否本轮做）请单独给一句话。

