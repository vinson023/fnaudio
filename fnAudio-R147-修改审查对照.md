# fnAudio R147 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

> 本文件为 R148 补齐的欠账：Q5=B 要求每轮一份仓根对照文档，R147 当日未产出（盘上最新只到 R146）。内容一律由 `CHANGELOG_AI.md` 的 R147 两条记录（现 L5／L6）＋三笔提交的 `git show` 复损，未凭记忆补写任何数字。

本轮为设备段处置 R7：第五节剩余 8 条观感与外部性条目（L1860、L1866、L1867、L1868、L1869、L1870、L1871、L1874）分三档处置——1 条按实测结案（L1866）、5 条按本机无载体结案（L1868–L1871、L1874）、2 条实测否证判定线后保持开放（L1860、L1867）。同轮另落地负责人裁定的 C9（清单作用域排除段成对）与 C6（根级 `.gradle-user` 归位）。

## 文件净增（`git diff --numstat`，HEAD = `863d6bf` R146）

| # | 文件 | 净增 | 落笔提交 | 性质 |
| --- | --- | --- | --- | --- |
| 1 | docs/external-acceptance.md | +60 −7 | `81c8577` | 8 条条目三档处置：6 处勾选改状态位、1 处节说明改写、1 处卡形态规则新增、7 组四行注记（含 L1866 多出的性质标注）、文末 18 行 R7 结案记录段 |
| 2 | src/tests/test_ledger_evidence_cards.py | +300 −6 | `e2bb44e` | 18→25 枚用例、12 组新常量、4 处既有断言扩口径；28,178→44,239 B／550→844 LF |
| 3 | SOURCE_MANIFEST.sha256 | +2 −2 | `e2bb44e` | 710 条不变，两条守卫哈希刷新 |
| 4 | CHANGELOG_AI.md | +2 −0 | `e2bb44e` | L2 处置轮主记录、L3 判别/变异/清单/门禁记录（现 L5/L6），最新在前 |
| 5 | PROJECT_CONTEXT.md | +2 −0 | `e2bb44e` | 同轮两条经验，最新在前 |
| 6 | src/tests/test_source_manifest.py | +1 −1 | `dea989c` | C9：`EXCLUDED_SEGMENTS` 成对加入 `Python`（7,531→7,541 B） |
| 7 | tools/update_source_manifest.ps1 | +1 −1 | `dea989c` | C9：`$excludedSegments` 同上（2,070→2,080 B） |

未改：`TODO.md`（当日实测 2,168 LF／647,941 B／CR 0／sha16 6f4810d9652a5c49，一字未动；现盘 2,169 LF／650,903 B 属 R148 自身编辑所致）、`.gitignore`、`.gitattributes`。C6 是 untracked 整目录移动，不产生任何提交。

## 一、开工取证（磁盘实测，不采信交接快照）

分支 `main`、HEAD `863d6bf`（R146）、被跟踪 5 modified、暂存空、无 MERGE/CHERRY-PICK/REVERT/BISECT/rebase/sequencer 态、无 stash、无 remote。`TODO.md` 实测开放 15 条 = L99 + L150 + 长期观察 13。台账 59,624→71,531 B／712→765 LF／CR 0／sha16 4a433951462304d3→3fc26829abe288ef。

## 二、H1 `docs/external-acceptance.md` — 17 个 hunk（`git show --unified=0 81c8577`）

| 落点 | 新行号 | 锚点 | 内容 |
| --- | --- | --- | --- |
| 1 | 15 | 卡片形态规则段 | 新增一条：四字段之后可紧跟四行注记，`> **结案（轮次·日期）**`（须同时勾选并复述本卡判据短语）与 `> **取证记录（轮次·日期）**`（已实测但判定线未过，勾选保持未勾）两种形态不得混用 |
| 2 | 334 | 第五节 `> 源节：` | 「R7 处理戊类观感 8 条」→「R7 结案 L1866（按实测结案，测量否证了不可取证预设）＋L1868/L1869/L1870/L1871/L1874＋L1860/L1867 实测后保持开放」 |
| 3 | 467-470 | L1860 卡（勾选未改） | 新增取证记录 4 行：实测（黑洞 resolver 下 `getaddrinfo` 15,014 ms、`urlopen(timeout=3)` 15,013 ms；无隔离 `.local` 5,129 ms、`timeout=3` 走满 5,004 ms；对照 `www.baidu.com` 4 ms 与数字 IP 0 ms）、缺口（`dlna/network.py:150` 的 `socket.getaddrinfo` 不受 `timeout` 约束，最坏 15～20 秒整段占住投送 worker）、后续动作（加可证伪上界属代码动作，是否进代码桶见 N2，本轮不改投送路径） |
| 4 | 535 | L1866 `- [ ]` → `- [x]` | 勾选改状态位，冻结块正文一字未改 |
| 5 | 543-548 | L1866 卡下 | 结案头＋`实测：`（`/proc/237556/status` 的 `SigCgt=0000000100000000` 不含 15 号位、`SigIgn=0000000001001007`、`SigBlk=0`；`trim_app_center.service` 为 `KillMode=process`／`KillSignal=15`／`TimeoutStopUSec=1min 30s`／`Restart=always 5s`；停止脚本 `/var/apps/fnaudio/cmd/main` 43 行 `stop_pid()`、69/173 行只给主进程 10 秒、185 行给 mpd 5 秒；部署副本 `server.py` 108,927 B 内 `shutdown_runtime` 与 `signal.signal(` 命中均为 0）＋`缺料：`（无——要的是结论，计数器读数已给出）＋`重开条件：`（若装上受控停止入口，判据转为「清理确实跑完且耗时可测」）＋空行＋性质标注（与 L1867 同源，R7 结的是「路径已取证清楚」这一半，勾选不表示宿主宽限与 drain 上限已对齐） |
| 6 | 561-564 | L1867 卡（勾选未改） | 取证记录 4 行：代码侧 drain 上限 `MAX_JOB_BUDGET_SECONDS + 1` = 31 秒落在 10 秒宿主宽限之外且清理入口不可达；后续动作收窄为「补受控停止入口」更有价值 |
| 7-14 | 569/577-580、585/593-596、601/609-612、617/625-628 | L1868、L1869、L1870、L1871 各 2 组 | 四条各改 1 处勾选并新增四行结案注记，统一按「本机不可取证 → 观感无设备证据」口径：`实测：`记 2026-09-21 22:47 本机 `adb devices -l` 空表等载体普查，`缺料：`写明所缺低端 WebView 载体与前后对比记录，`重开条件：`写明取得记录后按卡面判定线重判 |
| 15-16 | 665、674-677 | L1874 | 勾选改状态位＋四行结案注记：`lsblk` 只有 `sda 0 disk 110G`（ROTA=0 虚拟盘）与 `sr0`，网络共享曲库计数 0，静默窗口两个常量继续按经验值标注、不得写成已实测 |
| 17 | 748-765 | 文末 | 新增 `## R7 结案记录（2026-09-21）` 18 行：三类结果的分别定性（证据已到／本机无载体／实测否证）＋6 条结案 ID 列表＋取证环境快照（主机 `Linux FNOS`、`plink -batch -P 22 -l root 198.51.100.24`、hostkey 已核对、两次运行 22:38 与 22:47 CST）＋DNS 黑洞配方＋一条被本轮否证的旧推断＋读数浮动说明＋零污染复验 |

## 三、真机只读取证与否证（本轮证据主体）

- 通道：`plink -batch -P 22 -l root 198.51.100.24`，hostkey 事先核对；全程只读，未改设备配置、未重启服务、未部署新构建。设备侧唯一写入是 `/tmp` 下四个自建探针脚本且用后即删。
- L1860 最坏等待：黑洞 resolver（`unshare -rnm` ＋私有 `/run/resolvconf` 指向收包不回包的 `127.0.0.1:53`）下 `getaddrinfo` 15,014 ms、`urlopen(timeout=3)` 15,013 ms，3 秒预算被拖成 5.0 倍。
- 否证一条旧推断：127.0.0.1 无监听不等于解析黑洞——无监听立刻回 ICMP port unreachable，glibc 约 3 秒快速失败；必须让 socket 真收报文而不回应。读数随重试轮数在 15～20 秒浮动（本轮 15,014/15,013、上一趟 15,015、更早 20,020/20,022），只改变量不改变结论。
- 零污染复验：`/etc/resolv.conf` md5 `b7d645fea803f0afba7ee357f6c0762b` 探测前后一致；`^nameserver` 计数 1；`:53` 监听计数 0；`/run/resolvconf` 挂载计数 0；设备 `/tmp` 下 `r147*` 残留计数 0。

## 四、H2 `src/tests/test_ledger_evidence_cards.py` — 12 组改动

| 组 | 新行号 | 内容 | 缺了会怎样 |
| --- | --- | --- | --- |
| 常量 | 19-26 | 模块 docstring 补 R7 三句，仍声明本文件 shape-only、不判定任何条目 | 记录与守卫各说各话 |
| 常量 | 67-76 | `R7_UNEVIDENCED_CLOSED_IDS`／`R7_EVIDENCED_CLOSED_IDS`／`R7_CLOSED_IDS`／`R7_OPEN_WITH_EVIDENCE_IDS` | 按轮循环的用例在 R7 当天假绿 |
| 常量 | 78-90 | `CLOSURE_FIELDS` 之外新增 `EVIDENCE_HEAD`／`EVIDENCE_FIELDS`，`CLOSURES_BY_ROUND`／`CLOSED_IDS` 并入 R7 | 取证记录四行与结案注记无法分别校验 |
| 常量 | 97-104 | `R7_MEASUREMENT_TOKENS`（只锚本轮 15014 ms／15013 ms／5129 ms／timeout=3）与 `R7_VERDICT_FALSIFIED` | 注记里的读数被下一轮悄悄改掉也无人报警 |
| 常量 | 121-151 | `R7_SECTION_ENTRY`、`READ_ONLY_PROMISE`、`READ_ONLY_HOSTKEY`、`WRITE_PATTERNS`、`CODE_ACTION_WORDS` | 只读承诺与「不得把代码动作写成已完成」失去可执行边界 |
| 用例 | 444-462 | ① `test_r7_closes_the_view_items_whose_carrier_this_host_cannot_hold`：五条无载体项勾选集合与卡面口径逐条全等 | 无载体结案回退成未勾 |
| 用例 | 477-481、488-499、507、512-524 | 4 处既有断言扩口径（含硬数与两处消息） | 老用例继续只认 R4/R5/R6 |
| 用例 | 654-741 | ② ③ `test_r7_closes_L1866_on_the_measured_stop_path`（结案头须同时含 R7、实测读数与「不表示已按它改过代码」）与 `test_r7_measured_L1860_and_L1867_without_closing_them`（「取证记录」三子字段齐备、勾选保持未勾、实测 token 命中本轮读数） | 「实测但未过线」与「结案」两种形态可被互相冒充 |
| 用例 | 751-842 | ④⑤⑥⑦ `test_r7_section_note_reports_the_split_outcome`、`test_the_read_only_promise_survives_in_the_record_section`、`test_ledger_records_never_claim_a_pending_code_action`、`test_a_stopping_path_entry_cannot_claim_the_grace_gap_is_closed` | 节说明回退成单一结论、只读承诺丢失、记录段把代码动作写成已完成、L1866/L1867 声称宽限与上限已对齐 |

## 五、先红后绿、控制组与变异矩阵

- 先红（影子树 = HEAD 台账 blob ＋ 新守卫）：`Ran 25 tests`／`FAILED (failures=9, errors=1)`，输出先落盘再引用；后绿（真盘）：`Ran 25 tests OK`。
- 控制组先跑在矩阵之前：`test_source_manifest`(6) ＋ `test_device_todos_migrated`(6) ＋ `test_change_record`(3) = `Ran 15 tests OK`。
- 仓库外变异矩阵 M01–M15 全 KILLED（每格 ran=25），末行 `CELLS 15 / MISMATCHES 0 / MATRIX OK`。

## 六、C9 清单作用域对（`dea989c`，负责人裁定项）

两处同一行：`EXCLUDED_SEGMENTS`／`$excludedSegments` 成对加入 `Python`。仓库外三向影子实跑证明双向可杀——control OK／mut_a（ps1 缺该段）FAILED／mut_b（守卫缺该段）FAILED；直接跑 ps1 得清单条数 3／4／3，敌意夹具只在 mut_a 泄漏。安全性复算：`git ls-files` 下 `Python/` 段 0 条、`C:\path\to\fnAudio\src\Python` 与 `E:\Codex\Python` 现盘不存在、清单作用域仍只有 `src` 与 `android-client`；清单重跑后 710 条（改前同为 710），diff 仅两行且与盘上实算 sha256 逐字符相符。

## 七、C6 目录归位

根级 `.gradle-user`（717 文件／0.15 GB／untracked／全仓无构建脚本引用）整目录移入 `_external\.gradle-user`，不产生任何提交。

## 八、门禁与记账

- 门禁：先跑前置复现 `artifacts/offline-20260921-round225-prefix.log`，再以同一条令产出终跑 `artifacts/offline-20260921-round225.log`（432,526 B），退出码 0、`Ran 2541 tests`／`OK (skipped=2)`／0 条 FAILED／0 条 Traceback／JS 侧含 ` passed` 的结果行 73；终跑 log mtime 晚于本轮全部文档编辑；门禁前后 `SOURCE_MANIFEST.sha256` 实算 sha256 前 16 位同为 `49067e6e912649c4`；`git diff --check` 通过；未 push（本仓无 remote）、未碰 `.gitignore`/`.gitattributes`；`%TEMP%` 脚本与影子树用完即删。
- 记账：净关闭 0 条代码待办、新立 0 条；台账开放 34→28、收口 11→17；代码桶仍 2（`TODO.md` L99、L150 两条深读债）、需决策桶 0、长期观察 13；终止条件 (1) 剩 2 条，(4) 由终局门禁承担。
- 提交三笔：台账一笔（`81c8577`）、守卫＋两份根文档＋清单一笔（`e2bb44e`）、C9 作用域对一笔（`dea989c`），`git add` 只列台账、守卫、根文档、清单与 C9 两文件，无 `git add -A`。

## 九、R147 遗留到 R148

1. 未产出本轮对照文档（本文件即补齐）。2. N2（解析无界 15,014 ms ＋ `server.py` 缺受控停止入口）是否进代码桶待裁定。3. N4（设备部署副本 `server.py` 108,927 B／停止脚本 6,654 B）是否重打包升级待裁定。4. C5 第二档真机「放样本曲＋播放＋抓日志」未开轮。
