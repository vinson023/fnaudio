# fnAudio R141 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮＝第 43 轮＝「设备段处置」第 1 轮：把 `TODO.md` 里 45 条只能靠真机或外部材料推进的待办**逐字节**迁出，另册 `docs/external-acceptance.md`，并给迁移装上判别测试。跟踪文件的 `git diff --shortstat` 为 **7 files, 27 insertions(+), 74 deletions(-)**，另有 2 个新增未跟踪文件。本轮**不裁定、不关闭、不改写**任何一条待办：净关闭 0 条、新立 0 条，收益记在终止条件 (2)「设备/外部项移出逐轮任务」。

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | TODO.md | +10 −66 | 45 条设备项离开原节，五节各留 1 行迁移说明；设备区间开放项 45 → 0 |
| 2 | docs/external-acceptance.md | 新增 346 行／24,168 B | 外部验收台账：45 个 `BEGIN/END` 原文冻结块 + 记录规则 + 逐条处置计划 |
| 3 | src/tests/test_device_todos_migrated.py | 新增 273 行／13,996 B | 判别测试：45 枚冻结摘要 + 6 条不变量 |
| 4 | docs/INDEX.md | +2 −1 | 台账入索引；`TODO.md` 的定性由「唯一有效待办列表」改为「可离线推进的待办列表」 |
| 5 | src/app/server/playback/alsa_output.py | +3 −2 | 注释重锚：`TODO.md:1831` → 台账固定编号 L1872（含折行修复） |
| 6 | src/tests/test_alsa_output.py | +3 −3 | 同一处引用的测试侧镜像重锚（含折行修复） |
| 7 | SOURCE_MANIFEST.sha256 | +3 −2 | 709 条；两条摘要更新 + 新测试登记 |
| 8 | CHANGELOG_AI.md | +3 | L2/L3/L4 最新在前（含接管方复核记录） |
| 9 | PROJECT_CONTEXT.md | +3 | L2/L3/L4 最新在前（含跨文档重锚教训） |

---

## H1 `C:\path\to\fnAudio\TODO.md` — 五节迁出说明与设备区间清零

`git diff -U0` 共 12 个 hunk，删除 66 行、新增 10 行，构成完全对得上：**66 = 45 条目行 + 18 条缩进续行 + 3 空行**；**10 = 5 枚说明行 + 5 枚空行**。五枚说明落在 **L821（10 条）、L873（6 条）、L1802（3 条）、L1813（1 条）、L1821（25 条）**，合计 45。

设备区间口径：`## 宿主 MediaSession（…）` **L819** → `# 当前持续优化目标（…）` **L1842**。基线（`git cat-file blob HEAD:TODO.md`，662,748 B／2,224 个换行／sha256 前缀 `2f9d34b5ee8af63d`）该区间开放 **45**、已闭 616；现盘该区间开放 **0**、已闭 616 —— 历史闭项留在原地，没有被搬动。

- **说明行必须不是 checklist 项**：它们写成普通叙述段落。若带 `- [ ]`，区间清零这条不变量会被自己写的说明重新撑红；若带 `- [x]`，则等于「以迁移之名偷偷结案」。守卫 `test_each_source_section_keeps_one_pointer_note` 同时钉住「每节恰好 1 枚、且不以勾选符开头」。
- **为什么本轮不在 `TODO.md` 顶部插本轮记录**：`src/tests/test_ui_control_names.js:4` 与多份对照/变更记录都以「L99」「L150」为锚引用主表条目，顶部插一行会把两枚锚点整体下移，制造一批假漂移。本轮记录放在 `CHANGELOG_AI.md`。
- 现盘全文（2,168 个换行／647,941 B／CR 0／sha256 前缀 `6f4810d9652a5c49`）开放 **15** = `L99` + `L150` + 长期观察 13 条（L2027、L2035、L2054、L2057、L2062、L2063、L2068、L2082、L2083、L2095、L2100、L2101、L2109）；已勾选 **1,490**，与基线一致（迁移一条也没「顺手关掉」）。

## H2 `C:\path\to\fnAudio\docs\external-acceptance.md` — 台账结构与固定编号

结构：**L1** 标题（含「本文件是设备／外部待办的唯一存放处」）、**L8** 记录规则、**L16** 逐条处置计划（表 L18–L27，R1–R9）、L29 节次说明、**L31** 第一节（宿主 MediaSession，10 条）、**L106** 第二节（Android 等价目标，6 条）、**L153** 第三节（部署与外部系统，3 条）、**L177** 第四节（可维护性清理，1 条）、**L189** 第五节（P0 外部验收，25 条）。45 对 `<!-- BEGIN LNNN -->`／`<!-- END LNNN -->` 全部齐平（各 45 枚）。

- **固定编号 `LNNN`** 指迁移**前** `TODO.md` 的行号，此后不随台账行号变化而重编 —— 台账自身还会被 R2–R7 追加内容，若编号跟着本文件行号漂，五轮之后没人知道哪条是哪条。
- **勾选状态必须按「行首」口径统计**：本文件行首 `- [ ]` 恰 **45**、`- [x]` **0**；而全文子串 `- [ ]` 会出现 **46** 次，多出的那枚是 **L13**《记录规则》里举的格式示例。任何按子串写的断言都会假红。
- 每条结论、裁定、并账与结案说明一律写在标记**之外**，因此后续轮次追加不改冻结凭据；台账不在 `SOURCE_MANIFEST.sha256` 覆盖范围内（清单只遍历 `src/` 与 `android-client/`），其完整性由守卫里 45 枚 SHA-256 承担。

## H3 两处注释重锚 + 本轮修掉的折行缺陷

上一执行体把 `TODO.md:1831`（条目已迁走）换成台账引用，用的是**行内子串替换**，结果两行被撑破所在文件既有 92 列折行上限。本轮只重折、措辞一字不动：

| 文件 | 修复前（HEAD 行宽） | 修复后（现盘行宽） | 字节 | sha256 前缀 | 引用落点 |
|---|---|---|---|---|---|
| src/app/server/playback/alsa_output.py | 93 / 84 / 82 / 85（4 行） | 93 / 84 / 90 / 92 / 21（5 行） | 43,347 → 43,384 | `340ba668968420ce` → `f2d73ed257c116b8` | **L828** |
| src/tests/test_alsa_output.py | 71 / 90 / 92 / 92 / 24 | 71 / 90 / 62 / 91 / 82（仍 5 行） | 26,257 → 26,257 | `83b720e5871307a9` → `b090141c9de46488` | **L155** |

- 两处引用指向的都是**第五节 L1872**（未测 DAC 的取证项），语义未变：驱动没报采样率、只报了位宽，这一位事实值得保留。
- 守卫 `test_source_comments_stop_citing_moved_todo_lines` 钉住「源码注释里不再出现指向已迁移条目的 `TODO.md:` 行号」，M5（把字节还原成基线写法）实测 KILLED —— 这条断言不是装饰。

## H4 `C:\path\to\fnAudio\docs\INDEX.md`

**L20** 新增一行索引：台账＝设备／外部待办的唯一存放处，含 45 条原文冻结块、固定编号与逐条处置计划。**L30** 改写权威文档表里 `../TODO.md` 的定性：`当前唯一有效待办列表` → `可离线推进的待办列表（设备／外部项已另册于 external-acceptance.md）`。若不改这行，「唯一有效」会和台账互相矛盾，下一任执行体就无从判断哪份是权威。

## H5 `C:\path\to\fnAudio\src\tests\test_device_todos_migrated.py` — 6 条判别用例

常量 L37–L54（区间上下界、说明句前缀、`LEDGER_SECTIONS = 5`、4 枚正则），`FROZEN_ENTRY_DIGESTS` L59 是 **45 条以 int 固定编号为键**的 SHA-256；`CHECKBOX_STATE` L108、`unflexed_block_lines` L111、`digest` L128、`ledger_blocks` L133、`device_segment` L158、用例类 L166。

| 行 | 用例 | 钉什么 |
|---|---|---|
| L172 | test_every_frozen_entry_survives_the_move_verbatim | 45 块与基线条目（条目行 + 其后全部缩进续行）**逐字节相等**，0 不匹配；块体合计 63 行 = 45 + 18 |
| L186 | test_ledger_headings_agree_with_the_frozen_blocks | 五节标题数 = 5，且每节的固定编号集合与实测分布一致（一 821/827/830/834/835/838/841/843/845/853；二 984/986/988/990/992/1184；三 1836/1837/1838；四 1847；五 1852–1874 连续 + 1876 + 1878） |
| L193 | test_the_frozen_digest_pins_words_but_not_the_checkbox | 摘要先把状态位归一为未勾选再哈希 ⇒ 真机上勾掉一条**不该**让门禁红 |
| L216 | test_device_segment_of_the_todo_holds_no_open_item | 设备区间内行首 `- [ ]` = 0（终止条件 (2) 的磁盘可测形式） |
| L229 | test_each_source_section_keeps_one_pointer_note | 五枚说明各恰好 1，且都不是 checklist 项 |
| L248 | test_source_comments_stop_citing_moved_todo_lines | 源码不再引用被迁走条目的旧行号 |

- **为何不钉「全局开放/已勾选总数」**：docstring 明写。那两枚数会把别处正在推进的合法关闭也变成红，等于用一条守护测试阻止别的轮次干活；本轮只钉与迁移直接相关的不变量。
- 状态位归一这一步是本轮自纠的结果：M7（修复前算法）在「逐条勾选」场景下 45 条全红，M7b（修复后）勾选 45 条 **0 红**，未动时同样 0 红。

## H6 `C:\path\to\fnAudio\SOURCE_MANIFEST.sha256`

以 `tools/update_source_manifest.ps1` 刷新为 **709 条**（`android-client/` 80 + `src/` 629；盘上 76,847 B、709 个 CRLF）。差异恰 3 处：**L214** `alsa_output.py` 摘要 `CDBCCE27…` → `F2D73ED2…`、**L421** `test_alsa_output.py` `0007F0B7…` → `B090141C…`、**L447** 新增 `0EE1DA8B…  src/tests/test_device_todos_migrated.py`。三条与盘上字节逐字 MATCH；另抽查 12 枚随机条目（seed 20260921）0 不匹配、709 条路径唯一、0 缺盘。清单含 3 条 `.md`（`android-client/README.md`、`src/app/server/playback/README.md`、`src/tests/unwired/README.md`），**不含任何 `docs/`** ⇒ 台账不入清单是口径正确，不是漏登记。

## 无损性复算与已证伪，未改

- 45 个块体由接管方**自行重算**（不引用交接快照）：与基线逐字节相等、0 不匹配；45 个固定编号在基线全部命中 `- [ ]` 行。
- 45 条**一条也没结案**，也没有被改写成「已完成」；迁出 ≠ 关闭。
- 仓库里的 `artifacts/`、`_external/`、`.gradle-user/`、`tools/android-sdk*`、`tools/platform-tools*`、`tools/skill/`、`music/`、`references/`、根级 `*.log`、`full-test-output.txt` 等未跟踪垃圾**一律不入库**，本轮也未碰 `.gitignore`。
- 盘上无 `.new`/`.orig`/`.rej`（实测 0）。
- 一次**误判已撤销**：本会话曾据 `git diff` 左侧的 `CDBCCE27…` 判清单陈旧 —— 左侧是 HEAD 版本而不是编辑前的工作树，结论不成立；刷新只是登记重折后的新字节。

## 先红后绿（影子树）

基线材料（TODO 662,748 B + 两源文件 43,347／26,230 B）放进影子树：`PRISTINE` ⇒ `Ran 6 tests`、`FAILED (failures=6)`、rc 1；`PATCHED` ⇒ rc 0、`OK`。守卫不是「天然对现盘为真」，它确实会红。

## 变异证明（仓库外克隆，控制组先绿）

克隆 `%TEMP%` 下副本（HEAD `5a8fbd6`、remote 置空），7 个跟踪文件手工复制（新增文件 `git clone` 不带）。

| 格 | 注入 | 期望 | 实跑 |
|---|---|---|---|
| C0 | 无（控制组） | PASS | **PASS** |
| M1 | L821 块内加 1 个字符 | FAIL | **KILLED** |
| M2 | 把一条设备项写回 `TODO.md` 区间 | FAIL | **KILLED** |
| M3 | 删掉 L1184 整个冻结块 | FAIL | **KILLED** |
| M4 | 把某枚说明改写成勾选项 | FAIL | **KILLED** |
| M5 | 基线字节复原旧 `TODO.md:1831` 引用 | FAIL | **KILLED** |
| M6 | 勾掉 L1847（真机取证之后会做的事） | PASS | **PASS**（按预期不红） |
| M8 | 裁掉一条缩进续行 | FAIL | **KILLED** |
| M7／M7b | 逐条勾选 45 条（修复前／修复后算法） | 45 红／0 红 | **45 红／0 红** |

`CELLS 8 / MISMATCHES 0`；变异结束后还原复跑 rc 0。六模块合跑（含 `test_change_record`、`test_takeover_forensics`、`test_source_hygiene`、`test_source_manifest`）：`Ran 58 tests OK`。

## 门禁

前置门禁 `artifacts/offline-20260921-round214-prefix.log`（428,158 B）：`Ran 2516 tests`、`OK (skipped=2)`、`^FAILED` 0、`^ERROR:` 0、`Traceback` 0。终跑 `artifacts/offline-20260921-round214.log`（428,144 B、2,666 行）逐字回读：**L2588** `Ran 2516 tests`、**L2590** `OK (skipped=2)`、无 `FAILED`、无 `ERROR:`、无 `Traceback`、门禁退出码 **0**。JS 段含 `passed` 的输出行 **73**，盘上 `src/tests/test_*.js` 实为 **75** —— 两枚口径不同，禁止混用。读取判定行必须加 `-CaseSensitive`，否则逐条的 `... ok` 会被当成 `OK` 命中。按纪律，本 md 与各轮记录均不写具体用时。

## 计数与目标进度

- 开放 **60 → 15** = 代码 **2**（`TODO.md:99`、`TODO.md:150`）+ 设备/外部 **0**（45 条另册）+ 需决策 **0** + 长期观察 **13**；已勾选 1,490 未变。
- 本轮**净关闭 0 条**（反增长约束的下限由终止条件 (2) 买到，不靠虚报关闭数凑）。
- 终止条件：(1) 代码桶清零 ✗（剩 2）、(2) 设备/外部移出 ✓（本轮）、(3) 需决策汇总征询 ✓、(4) 终局完整门禁 ✗ ⇒ 目标继续。
