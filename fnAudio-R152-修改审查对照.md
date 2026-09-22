# fnAudio R152 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮为**深读＋当轮修复轮**：读完 `src/app/ui/app.css` 全表（机器全扫 61 个分区、1,472 条「选择器→属性名」摘要，R151 遗留的 74,405 字符未读面读到 0），在这个出局的面里读到 16 处选不中任何元素的死样式并当轮清掉。**净关闭 0 条既有代码待办、新立 0 条**；进展记在欠读面：`app.css` 按登记值 1,528 内容行整面出局，欠读总量 20,992 → **19,464**。

## 文件净增（`git diff --numstat 98c4a27..ef8b990`，`98c4a27` = R151 闭合，`ef8b990` = 本轮收尾）

| 文件 | + | − |
|---|---|---|
| `src/app/ui/app.css` | 9 | 18 |
| `src/tests/test_ui_unreachable_css_selectors.js` | 155 | 0（本轮新增文件；含第五笔 `2902232` 的注释更正） |
| `src/tests/dom.txt` | 0 | 113（本轮删除文件） |
| `SOURCE_MANIFEST.sha256` | 2 | 2 |
| `TODO.md` | 2 | 1 |
| `CHANGELOG_AI.md` | 2 | 0 |
| `PROJECT_CONTEXT.md` | 2 | 0 |

六笔提交：`f365d19` 样式表死规则清理 → `1a3b5fd` 清单重刷 → `68d958d` 三份根记录 → `2902232` 判别测试注释里的腐坏计数更正 → `ced70c8` 清单重刷 → `ef8b990` 三份根记录的提交后复审补记。全部用显式 pathspec 提交，未 `git add -A`、未 push、未碰 `.gitignore`／`.gitattributes`。

## 一、接管取证（磁盘实测，不采信交接快照）

- 分支 `main`、无 remote、开工 HEAD `98c4a27 docs(round-R151): record the owner's four adjudications`。
- 未完成态哨兵逐个实测**均不存在**：`MERGE_HEAD`／`rebase-merge`／`rebase-apply`／`CHERRY_PICK_HEAD`／`BISECT_LOG`／`REVERT_HEAD`；`git ls-files -u` 空（无冲突条目）。
- 现盘 vs `98c4a27`（bytes／LF／CR／sha256 前 16 位大写）：

| 文件 | 盘态（截至 `68d958d`） | 基线 `98c4a27` |
|---|---|---|
| `TODO.md` | 669,300／2,173／CR 0／`DE16E16A2778A028` | 664,711／2,172／CR 0／`2500B001E8416CB4` |
| `CHANGELOG_AI.md` | 1,272,452／6,774／CR 0／`D88EB8CC6CF8A896` | 1,269,861／6,772／CR 0／`1194C77C82B3AD81` |
| `PROJECT_CONTEXT.md` | 811,849／6,192／CR 0／`21CD9C5788E7B3EE` | 810,112／6,190／CR 0／`FEF1B05E95845BE9` |
| `SOURCE_MANIFEST.sha256` | 77,094／711／CR 711／`8DE6D87A16866965` | 76,354／711／CR 0／`D813FA720D8C23B5` |
| `src/app/ui/app.css` | 167,148／1,519／CR 0／`2C3556F9F80EA91D` | 168,902／1,528／CR 0／`37073C138C64ABFF` |
| `src/tests/test_ui_unreachable_css_selectors.js` | 6,331／151／CR 0／`E1303F54D64413F6`（前三笔提交后） | 不在基线（本轮新增） |
| `src/tests/dom.txt` | 盘上不存在 | 16,951／113／CR 0／`E1FEDE6F19014346` |

**第五、六笔提交后的收尾盘态**（更正后重测，与上表同口径）：

| 文件 | 收尾盘态 |
|---|---|
| `TODO.md` | 671,246／2,173／CR 0／`7743BC76C6E9D9AF` |
| `CHANGELOG_AI.md` | 1,273,492／6,774／CR 0／`F3C4E261C2C95347` |
| `PROJECT_CONTEXT.md` | 812,472／6,192／CR 0／`245BF7E4FF38AFF8` |
| `SOURCE_MANIFEST.sha256` | 77,094／711／CR 711／`59F3DDFD90790A8B` |
| `src/app/ui/app.css` | 167,148／1,519／CR 0／`2C3556F9F80EA91D`（与上表一致，第五、六笔未碰） |
| `src/tests/test_ui_unreachable_css_selectors.js` | 6,522／154／CR 0／`D1364F23085984CE`（注释更正后） |

三份根文档的第六笔改动都是在各自 L2 的 R152 条目尾部追加 `〔…〕`／`（…）` 补记，**未新增行**，故行计数与上表相同、仅字节数与哈希变化。

- 自洽校验：`app.css` 现盘 1,519 ＝ 基线 1,528 − 9 枚整行删除；清单行数 711 → 711（删 `dom.txt` 一行、增新测试一行）。
- 运行时：`node v24.19.0`；门禁用的是 PATH 上的 `python` ＝ **3.14.6**（`C:\Users\example\AppData\Local\Python\pythoncore-3.14-64`）。3.14.7 只属于取证脚本调用的 `_external\pymanager-python-20260921\...\python.exe`，两者不是同一个解释器，不得混写（本节初稿就混写过，见 §九）。

### 桶计数：三口径并存，不得合并

| 口径 | 数字 | 来源 |
|---|---|---|
| 历史目标正文快照 | 155 ＝ 64 代码 ＋ 82 设备 ＋ 9 决策 | 旧目标原文，**已过期** |
| R99 汇报实测 | 115 ＝ 51 ＋ 43 ＋ 8 ＋ 13 | R99 当时的盘态 |
| **本轮磁盘实测** | **15 ＝ 代码 2 ＋ 长期观察 13** | 现盘 `TODO.md` 行首 `- [ ]` 逐条清点 |

磁盘实测的 15 条：代码桶 2 条（`TODO.md:104` 欠读范围清单、`:155` `app.js` 浅读面）＋ 长期观察 13 条（`:2032`–`:2114` 段）。设备段已外迁至 `docs/external-acceptance.md`，实测 **28 开放／17 收口**；决策段开放 **0**。三份根文档 `splitlines()` 与 LF 计数逐一相等，确认无控制字符污染。

## 二、缺陷与修法（逐 hunk）

定性证据：`git grep -c -e mobileMoreBtn -e mobileMoreDialog <修订> -- src/app/ui/index.html` 在 `e3b934b`（2026-08-06）得 2、在 `208d550`（2026-08-14「chore: establish 0.2.2 offline delivery baseline」）得 0；`src/app/ui/app.js` 现盘 0 命中。**DOM 与脚本都不再产生这两个 id，样式表却继续供养它们到今日**——属死样式清理，不是功能回归。计数：基线 `#mobileMoreBtn` 10／`#mobileMoreDialog` 5／`.mobile-more-button` 1 ＝ 16，现盘全部 0。

### A 组 · 整行删除 9 枚（无残留，只列位置）

| # | 基线行位 | 现盘落点 | 被删规则 |
|---|---|---|---|
| 02 | 244 | L243 之后 | `.mobile-more-button{display:none!important}` |
| 03 | 251 | L249 之后 | `.player-actions #mobileMoreBtn{display:inline-grid…}`（760px 档） |
| 05 | 265 | L262 之后 | 同上 390px 档 |
| 08 | 369 | L365 之后 | 同上（首屏对齐段） |
| 09 | 374 | L369 之后 | `.player-actions #mobileMoreBtn{width:36px…}` |
| 10 | 384 | L378 之后 | `.player-actions #mobileMoreBtn{display:grid…}` |
| 11 | 393 | L386 之后 | `.player-actions #mobileMoreBtn{width:36px…}` |
| 12 | 401 | L393 之后 | `.player-actions #mobileMoreBtn{display:grid…}` |
| 13 | 405 | L396 之后 | `.player-actions #mobileMoreBtn{width:36px…}` |

### B 组 · 原行改写 9 枚

**注释跟实体一致（hunk 01／04）** — 注释里点名的菜单已不存在，留着会误导下一个读表的人：

```css
- /* Current favorite controls and mobile player menu */
+ /* Current favorite controls */            /* 现盘 L242 */

- /* Hide audio quality in lists and place mobile more beside controls */
+ /* Hide audio quality in lists */          /* 现盘 L257 */
```

**共享选择器里摘掉死成员（hunk 06／07／14／15／15b／16／17）** — 这类不是整条删，而是从多选择器组里抽掉一项，活选择器的声明一字未动：

```css
- .transport{gap:10px!important;padding-right:42px!important}.player-actions #mobileMoreBtn{width:36px…}
+ .transport{gap:10px!important;padding-right:42px!important}                    /* 现盘 L266 */

- #trackActionDialog,#mobileMoreDialog,#playlistDialog{
+ #trackActionDialog,#playlistDialog{                                            /* 现盘 L1051 */

- #trackActionDialog::backdrop,#mobileMoreDialog::backdrop,#playlistDialog::backdrop{background:#17203352!important}
+ #trackActionDialog::backdrop,#playlistDialog::backdrop{background:#17203352!important}   /* 现盘 L1060 */

- #trackActionDialog .dialog-head,#mobileMoreDialog .dialog-head,#playlistDialog .dialog-head{
+ #trackActionDialog .dialog-head,#playlistDialog .dialog-head{                  /* 现盘 L1061 */

- #trackActionDialog .dialog-head h2,#mobileMoreDialog .dialog-head h2,#playlistDialog .dialog-head h2{
+ #trackActionDialog .dialog-head h2,#playlistDialog .dialog-head h2{            /* 现盘 L1066 */

- #trackActionDialog .dialog-head .icon-button,#mobileMoreDialog .dialog-head .icon-button,#playlistDialog .dialog-head .icon-button{
+ #trackActionDialog .dialog-head .icon-button,#playlistDialog .dialog-head .icon-button{  /* 现盘 L1073 */
```

hunk 07（现盘 L339）同属此类：`.player{…}` 长行内删除指向死菜单的子串，行的其余声明保持原值。

**为什么 `#trackActionDialog`／`#playlistDialog` 必须留下**：对证到行——`src/app/ui/index.html:87` 定义 `<dialog id="playlistDialog">`、`index.html:88` 定义 `<dialog id="trackActionDialog">`；`src/app/ui/app.js:6877`（playlistDialog）、`app.js:7183`、`app.js:7201`、`app.js:7544`（trackActionDialog）都有 `showModal()` 调用点。本轮只摘共犯的 id，不碰现役对话框。真正兜住这条约束的是「可达性取差」判据本身——这两个 id 在 DOM 里可达，所以不会进幻影集；新测试第 141 行的 5 枚断言只覆盖移动端在位 id，不承担这条约束（初稿把归属写错了，见 §九）。

## 三、判别测试

新增 `src/tests/test_ui_unreachable_css_selectors.js`（现盘 155 行，其中第五笔 `2902232` 更正了 L12–17 的注释）。判据：**样式表 id 选择器集合 ∖（`index.html` 的 id ∪ `src/app/ui` 脚本文本里的单词字面量）必须为空**。

不是空转的自证设计（三处关键）：
1. **注释不是选择器**：`stripComments()` 抹掉注释内容但保留每一个换行，所以报告的行号仍与盘上一一对应。
2. **声明值会伪装成 id**：本轮按可复算口径重测——抹注释后取全部 `#[0-9A-Za-z_-]+`，得 **908 个 token**，其中 **699 个**是 3/4/6/8 位十六进制颜色（`border:1px solid #dfe5ee` 之类）、**209 个**形似 id；朴素正则必然误报。该数字属「带日期的盘态快照」，所以测试注释里不写死计数、只写口径；扫描器只取真正的「选择器前导」，并排除 at-rule 条件（`@media(max-width:760px)`）与 `@keyframes` 进度标签（`from`／`0%`）。
3. **敌意夹具**：一段合成 CSS 同时塞进幻影 id、颜色、注释文本、at-rule、keyframe 标签，断言扫描器**只**报出幻影 id——没有这组夹具，一个「静默返回空」的提取器会让这道守卫永远绿。

另附结构性断言：`app.css` 花括号必须配平（否则扫描器无意义）；`.player-actions #mobileMoreBtn` 不得以任何形式复活；`dom.txt` 不得复活；≤760px 整行 `.player-actions` 隐藏规则不得半复原。

**行号取证的一个坑（已写进 `PROJECT_CONTEXT.md`）**：扫描器用 `pending === ""` 判 token 边界时，累积的空白会让 `pendingLine` 停在更早的 token 上，把 251 报成 250。所有行号未经 `git grep` 原值对证前不得写进任何记录——本轮全部行号已逐一对证。

## 四、仓库外副本变异证明

副本 `C:\path\to\fnAudio_r152_cp`，控制组**先绿**，随后 V1～V9 全部 KILLED，还原后再绿，末行 `mutants killed 9/9`，脚本退出码 0；副本末态 pristine（`app.css 2c3556f9…`／测试 `e1303f54…`／`dom.txt` 不存在）。九个变异体分别攻击：删掉可达性取差、把注释当选择器、把颜色当 id、放过 at-rule、放过 keyframe、放宽 `.player-actions` 隐藏断言、摘掉 id 在位断言、去掉敌意夹具、放行 `dom.txt` 复活。

**第六轮复跑（提交后独立复核）**：用同一份 `%TEMP%\r152_mutate.py`（4,041 B）在副本上重跑一遍——控制组 exit 0 先绿 → V1～V9 **全部 KILLED** → 还原后再绿 → 末行 `mutants killed 9/9`，脚本退出码 **0**。复跑时副本上还是更正前的测试文件 `E1303F54D64413F6`，副本 git HEAD 仍是基线 `98c4a27`，末态哈希见 §一「收尾盘态」表。

**如实登记一处 SURVIVED 候选**：把可达集收窄成「只认 `index.html` 的 id」不会被判红，说明 `scriptIdTokens()` 那半边当前冗余。不立项（它不构成缺陷，只是守卫的冗余分支）。

## 五、当轮证伪 5 组（不得记作发现）

1. `--fnaudio-track-columns`／`--marquee-distance`／`--seek-fill` 并非死变量，由 `app.js` 运行时注入。
2. `--fn-accent` 定义后零消费——属设计令牌冗项，非缺陷，不立项。
3. 样式表 `url()` 外部引用实测 0 处，无失效资源路径问题。
4. **类选择器**死码扫描不可靠：同口径跑出 96 条误报（类名经 `classList`／模板字符串拼接，静态不可判定），故本轮只对 **id 选择器**下结论。
5. ≤760px 无音量入口是既有产品形态，不是缺失。

## 六、记账与门禁

- `TODO.md` 行首 `- [x]` 1,494 → **1,495**；未勾 `- [ ]` **15 不变**；`TODO.md:104` 欠读清单条追加 `〔R152 本面出局…〕`（该条第 8 枚续注，与 R129／R130／R134／R140／R149／R151 同一行文风）。
- 四份记账守卫合并跑 `test_change_record`＋`test_source_manifest`＋`test_device_todos_migrated`＋`test_ledger_evidence_cards`：**Ran 44 OK**。
- 清单 `SOURCE_MANIFEST.sha256` 711 条逐文件复算：missing 0／hash_mismatch 0／重复路径 0。
- 正式门禁三道（`tools/test_offline.ps1`，退出码由 `%TEMP%\*.cmd` 包装显式捕获）：

| 日志 | 覆盖的树态 | 结果 | sha256 前 16 |
|---|---|---|---|
| `artifacts/offline-20260922-round231.log` | 代码修复前原态 | `Ran 2555 tests in 125.766s` → `OK (skipped=2)`／含 `passed` 的行 75／`RC=0` | `fafabad04f11f6b4` |
| `artifacts/offline-20260922-round232.log` | 样式表清理＋清单态 | `Ran 2555 tests in 123.228s` → `OK (skipped=2)`／75 行／`RC=0` | `27bde234d4ab140d` |
| `artifacts/offline-20260922-round233.log` | **收尾门禁**（含第五、六笔补记的全树） | `Ran 2555 tests in 122.970s` → `OK (skipped=2)`／75 行／`RC=0` | `659ecf4ecf973909` |

  三份日志均无 `CategoryInfo`／`Traceback`／`FAILED` 签名；JS 侧 77 套件全部退出码 0；`git diff --check`、发布包校验、PowerShell 语法门全部通过。
- `.new`／`.orig`／`.rej` 残留清点：`src/`、`tools/` 与仓库根目录**零残留**；全仓唯一命中在 `_external/runtime/gomodcache/**/surface.new`，那是第三方 Go 模块自带文件名，且 `_external` 不入库。按这个口径登记，不得写成「全仓 0」。
- 未动 `.gitignore`／`.gitattributes`，未 push，未放宽任何旧守卫，设备台账一行未改（`docs/external-acceptance.md` 实测 28 开放／17 收口，与本轮开工时一致）。

## 七、JS 成功口径纠正（历史数字不改写）

实测 `src/tests/test_*.js` **77 个文件全部退出码 0**，其中仅 **75** 个输出含字面 `passed`；`test_ui_control_names.js` 打印控件清单统计、`test_ui_library_metadata_merge_policy.js` 打印「regression ok」。所以历史「68/74 passed」是按行统计、且受措辞左右。自本轮起双口径登记：**文件数／失败数为真**，日志含 `passed` 的行数仅作对照。

## 八、下一步（待用户裁定见对话正文）

终止条件四项现状：**成立 1／4**。

| 条件 | 现状 |
|---|---|
| (1) 可离线验证代码侧待办清空 | ✗ 剩 2 条深读债，欠读 19,464 行 |
| (2) 设备／外部项移出逐轮任务 | ✗ 已外迁到台账，但 28 条开放尚未逐条裁定 |
| (3) 需产品决策项汇总征询 | ✓ 决策段开放 0（9/9 已 `[x]`） |
| (4) 终止前完整离线门禁 | ✗ 属终止动作，尚未到终止时点 |

可选下一步：**(A)** 继续啃代码桶（`cover_cache.py` 1,364 行 → `app.js` 8,405 行 → Android 43 文件 9,695 行）；**(B)** 转设备段 28 条逐条裁定（真机 198.51.100.24 已授权）；**(C)** 两条深读债按 Q2=A「欠读行数计进展」口径承认关闭。已用 36+ 轮，`maxGoalRounds = 72` 不作终止理由、不改终止条件。
## 九、提交后复审与更正清单（本轮自查，逐条「原表述 → 现盘实测 → 处置」）

| # | packet 初稿原表述 | 现盘实测 | 处置 |
|---|---|---|---|
| 1 | 「全表 117 个 `#词` token、其中 115 个是颜色」 | 抹注释后 `#[0-9A-Za-z_-]+` 复算＝**908 token／699 个十六进制颜色／209 形似 id**；117／115 是从已被删掉的测试注释 L14 抄来的陈旧值 | **证伪并已更正**（§三 item 2 换成可复算口径＋带日期快照声明） |
| 2 | 「门禁 Python 3.14.7」 | PATH 上的 `python` ＝ **3.14.6**；3.14.7 是取证脚本用的 `_external\pymanager-python-20260921\...\python.exe` | **版本号错误已更正**（§一运行时条）；`node v24.19.0` 复核无误 |
| 3 | 「对话框 id 不得删这条约束由新测试 L141 的 5 枚断言钉住」 | L141 只覆盖 5 枚**移动端在位 id**；真正兜底的是可达性取差判据本身；对话框 id 的在位证据是 `index.html:87`／`:88` ＋ `app.js:6877`／`:7183`／`:7201`／`:7544` | **归属误写已更正**（§二 B 组末段补齐对证到行的证据链） |
| 4 | §文件净增写「三笔提交」、测试文件 +152 | `git diff --numstat 98c4a27..ef8b990` 实为 **＋155**，提交共 **六笔**（第五笔 `2902232` 就是修这条注释腐坏） | **已更正**（提交链＋计数） |

一处自查结论值得单列：初稿写「无 `.new`／`.orig`／`.rej` 残留」时未限定作用域，实测全仓唯一命中在 `_external/runtime/gomodcache/`（第三方 Go 模块自带的 `surface.new`），已在 §六改成带作用域的口径。这类「口径写宽了」与「计数抄旧值」是本轮 packet 唯一的两类失真，都不影响 §二的 17 个 hunk 与 §四的变异证明结论。

**记账影响：本轮净关闭 0 条既有代码待办、新立 0 条**；`TODO.md` 行首 `- [x]` **1,495**、未勾 `- [ ]` **15** 与 §六登记值一致，packet 的更正不改任何桶计数。
