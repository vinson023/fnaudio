# fnAudio R144 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮＝设备段处置 R4：把 9 条「本机永不可能产出取证材料」的设备项按各自卡面口径收口，并给每一枚勾选绑定一份可读回、可核对、可判红的取证缺口注记。接管方不采信交接快照，全部从磁盘复算后再落记录：台账 45 枚冻结块摘要 45/45 全等、守卫 15 用例、清单 710 条 0 冲突 0 缺盘、12 条随机抽样 sha 全配，全部复核通过。交接快照声称已经跑过的变异矩阵在临时目录里没有留下任何输出文件，因此本轮从影子树**亲自复跑**控制组与全部 11 格后才引用其数字。

## 文件净增（`git diff --numstat HEAD`，HEAD = `9b45a98` R143）

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | docs/external-acceptance.md | +68 −9 | 9 条勾选改状态位（−9/+9）＋每条 4 行结案注记（36 行）＋文末 23 行 R4 结案记录（含环境快照） |
| 2 | src/tests/test_ledger_evidence_cards.py | +156 −9 | 1 枚「一条都不许勾」用例删除，新增 2 助手 + 4 用例与 14 个常量／正则：12 用例 → 15 用例 |
| 3 | SOURCE_MANIFEST.sha256 | +1 −1 | 710 条不变，仅守卫哈希行刷新 |
| 4 | CHANGELOG_AI.md | +2 −0 | L2 主记录、L3 判别/变异/清单/门禁记录，最新在前 |
| 5 | PROJECT_CONTEXT.md | +2 −0 | L2/L3 两条跨轮经验，最新在前 |
| 6 | fnAudio-R144-修改审查对照.md | 新增 | 本文件 |

台账 47,543 B／633 LF／sha16 `427b43e7c9667efa` → **55,247 B／692 LF／CR 0／无 BOM／sha16 `fb1ecdf8802fd392`**；守卫 14,710 B／301 LF／sha16 `149844a2fa6281a3` → **22,334 B／448 LF／CR 0／无 BOM／尾 1 LF／sha16 `6e9b8d1a3b8e9931`**；`TODO.md` 本轮一字未动：**647,941 B／2,168 LF／CR 0／sha16 `6f4810d9652a5c49`**。

## 一、开工取证（全部本轮磁盘／真机实测，与快照不符处以磁盘为准）

- Git：分支 `main`、HEAD `9b45a98`（R143）、被跟踪文件在本轮开工前干净；`MERGE_HEAD`／`CHERRY_PICK_HEAD`／`REVERT_HEAD`／`BISECT_LOG`／`MERGE_MSG` 全部不存在，`rebase-apply`／`rebase-merge`／`sequencer` 目录全部不存在；`git stash list` 空；无 remote。
- 台账实测：开放 `- [ ]` 36 条、收口 `- [x]` 9 条（改前 45／0）；692 行。
- `TODO.md` 实测：开放 15 条＝`TODO.md:99`、`TODO.md:150` 加长期观察段 13 条（L2027、L2035、L2054、L2057、L2062、L2063、L2068、L2082、L2083、L2095、L2100、L2101、L2109），已勾 1,490 条。
- 真机只读复测（`plink -ssh -batch -P 22 -l root 198.51.100.24`，全程未写、未重启、未部署）：`Linux FNOS 6.18.18.c1032-trim #1032 SMP x86_64`／Debian 12／`uname -m`=x86_64；`/proc/asound/cards` 仅 `1 [pcsp] PC-Speaker`；`/proc/asound/pcm` 仅 `01-00: pcspeaker : pcsp : playback 1`；`find /proc/asound -name stream*` **零命中**；`/proc/asound/card1/pcm0p` 只有 `info`＋`sub0` 且 `pcm0p/info` 无速率与格式行；`/sys/module/snd_usb_audio` 不存在；`lsusb` 仅 `1d6b:0002/0001` 两个 root hub 与 `0e0f:0002` Virtual USB Hub、`0e0f:0003` Virtual Mouse（VMware 虚机，无可直通 USB 音频总线）；`command -v aplay`／`shairport-sync`／`nqptp` 全空；`/var/log/apps/fnaudio.log` 内 dac／stream0／dsd 零命中；服务端 pid 237556 监听 `0.0.0.0:53199`、mpd 子进程 pid 237571；本机 `tools/android-sdk/platform-tools/adb.exe devices -l` 空表。
- 结论：这 9 条要求的材料（三款第三方控制点、USB DAC 热插拔、DoP-only DAC、原生 DSD Renderer、AirPlay 环境、两台以上 Android 真机、ARM64 真机、真机 `stream*` 原文、可实测位深回退的设备）在本机**不可能产出**，不是「还没做」。

## 二、H1 `src/tests/test_ledger_evidence_cards.py` — 4 个 hunk

| hunk | 新行号 | 锚点 | 内容 |
|---|---|---|---|
| 1 | 9-19 | 模块 docstring 第三段 | 原「守卫是纯形状检查、设备项一律未勾」改写为：守卫仍不判定任何条目，但 R4 收口了 9 条材料不可能产出项，每枚勾选绑定一条复读本卡口径的注记，因此这里的勾选永远读不出「判据已通过」 |
| 2 | 45-69 | `CLOSING_WORDS` 之后、`DEVICE_TOKENS` 注释之前 | 新增 R4 记账常量块（14 项）：`R4_CLOSED_IDS` 九条固定号、`R4_CLOSURE_DATE`、注记头正则 `CLOSURE_HEAD`、三个子字段标签 `CLOSURE_FIELDS`、`CLOSURE_SUB`、记录节标题与终止前缀、`R4_RECORD_ID`、勾选态正则 `TICKED_STATE`、口径短语抽取 `VERDICT_PHRASE`、`VERDICT_FIELD`、取证锚点 `EVIDENCE_ANCHOR`、以及 `NOT_PASSED_PROMISE`「不表示判据已通过」 |
| 3 | 136-142（净删 6 行） | 原 `test_ledger_checkboxes_are_untouched_by_the_cards` | **删除**旧用例「开放必须 45、收口必须 0」。它保护的是「本轮不许勾」，与 R4 的处置直接冲突；不能改成放宽阈值，否则等于让守卫给结案让路 |
| 4 | 320-446 | 类尾、`if __name__` 之前 | 新增 2 枚助手 `_ticked_ids()`／`_closure_notes()` 加 `_verdict_phrase()`，与 4 枚新用例（见下表逐条拆解） |

新增 4 枚用例逐条：

| 用例 | 新行号 | 钉住什么 | 缺了会怎样 |
|---|---|---|---|
| `test_r4_ticks_and_their_notes_are_the_same_set` | 367-379 | 勾选集合必须恰为 `R4_CLOSED_IDS`；注记集合与勾选集合全等；`- [x]` 必须 9、`- [ ]` 必须 36 | 多勾一条、或勾了不打注记、或注记孤悬，全都读不出来 |
| `test_closure_note_quotes_the_verdict_of_its_own_card` | 380-397 | 注记首行必须逐字复读**所属卡**「不可取证时结案口径」里的短语；九条短语两两互异；他条短语不得出现在本条注记 | 注记可以互相抄袭或写成一句通用套话，「按卡面口径收口」变成空话 |
| `test_closure_notes_carry_measurement_gap_and_reopening` | 398-424 | 注记必须恰为 1 头＋3 子字段，依次以「实测：」「缺料：」「重开条件：」起头且非空；实测行必须含真实运行能打印的锚点；注记必须紧跟卡的四个字段之后；禁 6 个结案禁词、禁出现 `- [` | 注记退化成三行免责声明，或把「材料不可能产出」写成「已闭环」，或在注记里偷改勾选 |
| `test_r4_record_section_matches_the_ticked_set` | 425-446 | 文末 `## R4 结案记录` 全文件必须恰好一处；其 `- Lnnn` 列表与勾选集合全等、无重复；节内必须出现「不表示判据已通过」 | 记录段与勾选各说各话，或结案记录被读成功能已验证 |

三处刻意设计：

1. **同一事实读三遍并互相全等。** 勾选态（L292 等 9 行）、逐卡注记（L300 等 9 组 4 行）、文末记录（L672-L684）三者由 `R4_CLOSED_IDS` 单点锚定，任一边漏改或改歪即红；这不是冗余，是为了让「勾了但没交代」与「交代了但没勾」都各自可判红。
2. **注记只能复读自己卡的裁定短语，且短语必须互异。** 用例先断言每枚卡的「不可取证时结案口径」恰好给出一个「」短语，再断言九条短语两两不同，最后要求注记引用自己那条——抄袭在结构上不可行。
3. **收口与通过之间留一句硬话。** 注记与记录段都不得含 `CLOSURING_WORDS`（含「已闭环」），且 `NOT_PASSED_PROMISE`「不表示判据已通过」被用例强制写在记录段里；M6 变异（在重开条件后追加「，本条已闭环」）正是被这一点杀红的。

## 三、H2 `docs/external-acceptance.md` — 12 个 hunk

| hunk | 新行号 | 对象 | 内容 |
|---|---|---|---|
| 1 | 292 | L1838 | 勾选 `- [ ]` → `- [x]`（正文一字未改） |
| 2 | 300-303 | L1838 卡 | 四行结案注记，口径短语「第三方控制点未复测」 |
| 3 | 330 | L1852 | 勾选改状态位 |
| 4 | 338-341 | L1852 卡 | 注记，口径「USB DAC 热插拔与息屏长时控制本机永不可取证」 |
| 5 | 346 | L1853 | 勾选改状态位 |
| 6 | 354-357 | L1853 卡 | 注记，口径「无 DoP-only DAC 设备」 |
| 7 | 362 | L1854 | 勾选改状态位 |
| 8 | 370-373 | L1854 卡 | 注记，口径「无原生 DSD Renderer 设备」 |
| 9 | 378 | L1855 | 勾选改状态位 |
| 10 | 386-389 | L1855 卡 | 注记，口径「无 AirPlay 环境」 |
| 11 | 394 / 402-405 | L1856 | 勾选＋注记，口径「Android 多机型矩阵覆盖不足」 |
| 12 | 410 / 418-421 | L1857 | 勾选＋注记，口径「ARM64 真机缺位，中继项未验」；另 591-594／602-605＝L1872 勾选＋注记「真机 stream* 样本永不可得」；610／618-621＝L1873 勾选＋注记「位深回退仍属猜测」；667-692＝文末 `## R4 结案记录（2026-09-21）` |

代表卡原文照录（L1838，盘上 295-303 行；注记在第 5 个字段位）：

```text
> **取证单 L1838**
> - 设备／材料：UAPP、中子、BubbleUPnP 三款实体 DLNA 控制点
> - 抓取：每款各做一次 DMS Browse、分页翻页、封面显示、播放，并留日志或录屏
> - 判定线：三款各自给出通过或不通过的结论；协议自动化已覆盖的三项不能顶替真机结论
> - 不可取证时结案口径：结案为「第三方控制点未复测」，R4 拟按不可取证口径收口
> **结案（R4·2026-09-21）**：本机不可取证，按本条取证单口径收口为「第三方控制点未复测」。
> - 实测：2026-09-21 只读探测 `198.51.100.24`，服务端 pid 237556 在 `0.0.0.0:53199` 提供 DMS；本机 `adb devices -l` 返回空表，三款车型化控制点客户端一个都没有安装载体
> - 缺料：UAPP、中子、BubbleUPnP 三款实体 DLNA 控制点，以及能装上并运行它们的真实终端
> - 重开条件：取得任一控制点真机并完成一次 Browse 与播放，结论按卡面判定线逐项记「通过」或「不通过」
```

文末记录段（盘上 672-692 行）包含：一句总述（明确「收口只表示取证材料不可能产出，不表示判据已通过，也不表示对应功能可用」）、9 行 `- Lnnn`、以及 5 行 `> - ` 取证环境快照（主机／ALSA／USB／服务／缺位）。

## 四、先红后绿与变异矩阵（本轮亲自复跑，输出落盘）

- 先红：台账未改而守卫已扩时跑 `test_ledger_evidence_cards` → `Ran 15`／`FAILED (failures=4)`，红的恰是新增 4 枚，旧 11 枚全绿。
- 后绿：`Ran 21 tests OK`（守卫 15 ＋ 迁移守卫 6），45 枚冻结块摘要 45/45 全等。
- 影子树：`git clone --no-hardlinks` 后 `git remote remove origin`，两个改动文件手工复制进去，保持 `shadow/src/tests` 层级（守卫靠 `parents[2]` 推仓库根）。控制组 `Ran 15 OK`。

| 格 | 敌意变异／正控 | 期望 | 实测 | 杀死它的用例 |
|---|---|---|---|---|
| M1 | 多勾 L1874 但不打注记 | RED | RED | ticks_and_their_notes |
| M2 | 删 L1853 的 4 行注记、保留勾选 | RED | RED | quotes／measurement／ticks（3 枚） |
| M3 | L1855 注记改抄 L1854 的口径短语 | RED | RED | quotes_the_verdict |
| M4 | L1856 注记挪到卡头之上 | RED | RED | quotes／measurement／ticks（3 枚） |
| M5 | L1872 实测行改成无锚点空话 | RED | RED | carry_measurement_gap |
| M6 | L1873 重开条件追加「，本条已闭环」 | RED | RED | carry_measurement_gap（禁词） |
| M7 | 记录段删掉 `- L1857` | RED | RED | record_section_matches |
| M8 | 记录段插入 `- L1874` | RED | RED | record_section_matches |
| C1 | 文末追加一行无实质变更的 `> 备注：` | GREEN | GREEN | - |
| C2 | 注记后追加 `> 性质标注：` 行 | GREEN | GREEN | - |
| C3 | 空操作 | GREEN | GREEN | - |

`MATRIX OK`；每格前 `restore()` 且逐字节断言还原，跑完影子树两文件与真盘**字节一致**。

## 五、清单与门禁

- `SOURCE_MANIFEST.sha256`：710 条／76,954 B／CRLF 710／裸 LF 0；独立复算 0 缺盘、0 重复路径、12 条随机抽样 sha 全配；守卫在列，`docs/` 与三份根文档不在列（符合清单自身口径）。
- 门禁终跑 `artifacts/offline-20260921-round219.log`：Python `Ran 2531 tests`／`OK (skipped=2)`，JS 侧 73 行 `... passed` 加 1 行 `regression ok`（含 `Transport state-unknown lamp regression checks passed.`），退出码 0，取码方式为 `Start-Process cmd.exe -Wait -PassThru -WindowStyle Hidden`。对照上一轮 `round218`：`Ran 2528` → `Ran 2531`，增量恰为本轮净增的 3 枚用例（−1 ＋4）。
- 无 `.new`／`.orig`／`.rej`／临时后缀残留。

## 六、记账口径（如实）

- 本轮关闭的 9 条全部在**设备／外部段**，代码待办桶**净关闭 0 条、新立 0 条**。反增长约束里「每轮净关闭至少 1 条既有代码待办」在设备处置轮如实记 0，并写明原因：设备处置轮由负责人 R1-R10 授权单独开道、一轮只处理一条，其收益记在终止条件 (2)。
- 磁盘实测四桶：可离线代码项 2 条（`TODO.md:99`、`TODO.md:150`）、长期观察 13 条、设备／外部段 36 开＋9 收口、需负责人决策桶本轮无新增。历史计数快照（155＝64＋82＋9、115＝51＋43＋8＋13、JS 68）并存不合并，一律以上述磁盘实测为准。
- 终止条件：(1) 代码桶未清零、(3) 决策桶尚有未裁定项、(4) 终局门禁未跑 ⇒ 目标保持未完成，续开 R145（＝处置 R5：`L1836` 与「开源、暂不托管」的口径冲突）。
- 未 push、未使用 `git add -A`、未改 `.gitignore`／`.gitattributes`、门禁日志与临时产物不入库。
