# fnAudio R159 修改审查对照（逐处 · 行号为「三份根文档写入后」盘上真实 1-based）

基线 HEAD：`483f1a4`（R158 第 5 笔）。本文件所有行号均以现盘 `splitlines()` 复核，改动原文以 `git diff -U2 HEAD` 为证，非草稿值。

## 文件净增（`git diff --numstat`，对 HEAD `483f1a4`）

| 文件 | + | - | 现盘规模 |
|---|---|---|---|
| `src/app/ui/app.js` | 19 | 6 | 8,469 行 / 412,955 B / LF / 无 BOM（净 +13 行 / +614 B） |
| `src/tests/test_ui_library_sort_shuffle.js`（新增，第 2 笔入库） | — | — | 159 行 / 9,549 B |
| `TODO.md` | 4 | 3 | 2,180 行（`split("\n")` 口径）/ 713,415 B |
| `CHANGELOG_AI.md` | 2 | 0 | 6,789 行 / 1,316,733 B |
| `PROJECT_CONTEXT.md` | 1 | 0 | 6,200 行 / 822,000 B |
| `SOURCE_MANIFEST.sha256` | 2 | 1 | 716 → 717 条（纯 CRLF／无 BOM，范围仅 `src/`＋`android-client/`） |

## 一、接管取证（磁盘实测，不采信交接快照）

- 分支 `main`、HEAD `483f1a4`、无 remote、无 stash。
- 未完成态逐个 `Test-Path`：`.git/MERGE_HEAD`、`.git/rebase-merge`、`.git/rebase-apply`、`.git/CHERRY_PICK_HEAD`、`.git/BISECT_LOG`、`.git/MERGE_MSG` 全部 False。
- 工作树＝4 改 1 新（`app.js`／三份根文档／新守卫）＋清单。`artifacts/`、`_external/`、`references/`、`tools/android-sdk*` 等巨量未跟踪物不属项目文件，故全程禁用 `git add -A`。
- `TODO.md`：开放 `- [ ]` = **4**（L111 欠读量化门、L162 app.js 深读面、L2046、L2068 为长期观察）；严格行首 `- [x]` = **1,502**。子串口径会因散文内引用虚高到 1,511／1,507，本仓统一取列 0 严格行首。
- `app.js`：`node --check` 通过；行首锚定 `^(?:async )?function 名称(` 实测 463 → **462**／unique 462，差的一枚即本轮删除的 `compareName`。

## 二、本轮读毕的面与分子变化

- 面：`app.js` :1568-:1830「曲库视图／播放列表／列选择／排序／分页判定／转码与访问档」连续切片 263 行／44 枚命名函数。
- 写入前三份根文档**反引号与裸文本双口径均 0 命中**者 42 枚，其中 41 枚在本轮改动后仍存活于盘上，`compareName` 读毕即删——它被读过、被删掉，不静默计入分子。
- 深读分子 **81 → 122**；登记分母 381 不改写（`docs/REVIEW_ROUND_DISCIPLINE.md` 第五节：历史数字禁改）。
- 未点名命名函数三档实测：HEAD 码 × HEAD 文档 = **277**；现盘码 × HEAD 文档 = **276**；现盘码 × 现盘文档 = **235**（276 − 41 枚存活首次点名，严格相符）。

## 三、修复 A：`shuffleItems` 兼容入口重写（`app.js` :1575-:1593）

改前一行（HEAD :1576）：`return window.fnAudioShufflePolicy?.shuffle?.(list) || [];`
三处缺陷：① 把调用者的原数组直接交给策略模块，允许被就地改动；② `|| []` 使模块缺席／返回假值时**整条队列换成空数组**；③ 完全不认识模块的 `MAX_ITEMS` 预算语义。
改后逐段（现盘行号）：

| 行 | 作用 |
|---|---|
| :1576 | `Array.isArray(list) ? list.slice() : []`——非数组入参得空队列，数组入参一律先复制 |
| :1577 | 空表短路，不进策略 |
| :1578-:1581 | 四行注释写明「预算是**可乱序额度**，不是**可播放条数上限**」，越界项必须原序留在尾部 |
| :1582-:1583 | 读 `MAX_ITEMS`，仅当正整数生效；`limit = Math.min(budget, items.length)`，非正／缺失时 `limit = items.length`（预算失配不得缩小队列） |
| :1584-:1585 | `head` / `tail` 切分 |
| :1587-:1591 | `try/catch` 包住策略调用：异常随机源不得打断播放 |
| :1592 | `Array.isArray(shuffled) && shuffled.length === head.length ? shuffled.concat(tail) : items`——非数组或长度不符一律回落**原序全量**，绝不返回空表 |

## 四、修复 B：两条建队路径接线（`app.js` :4343 / :4385）

- `playGroup`（def :4332）:4343：`state.shuffle ? [...group].sort(() => Math.random() - 0.5) : group` → `state.shuffle ? shuffleItems(group) : group`
- `playAll`（def :4360）:4385：同形改动（`tracks`）
- 定性依据：比较器驱动的 `sort` 不是均匀洗牌（结果分布取决于引擎的比较次序），且完全绕过模块的预算与异常随机源守卫。
- 修复后盘上实测：`.sort(() => Math.random()` 命中 **0**；`shuffleItems(` 命中 **3**（定义 1 ＋ 调用 2）；`fnAudioShufflePolicy` 在 `app.js` 仅 :1582 与 :1588 两处，均在 `shuffleItems` 体内。

## 五、修复 C：删除 0 引用死码 `compareName`（HEAD :1770-:1772）

三行函数体把「当前排序方向」折进 `localeCompare(..., "zh-CN", {numeric:true, sensitivity:"base"})` 的返回值里，与活排序道 `sortTracks` 各持一套口径，且盘上零调用点。删除后 `src/app/ui` 目录内全部 `.js`／`.html` 对 `compareName` 命中 **0**（守卫块 9 逐文件钉死）。

## 六、判别测试：`src/tests/test_ui_library_sort_shuffle.js`（新增 159 行）

`vm.runInNewContext` 真实执行，切片锚＝`function isPlaylistView(` → `function scanProgressText() {`；跨 realm 值一律经 `JSON` 归一（沙箱内字面量不是宿主 realm 的 `Array`）。10 个判别块：

| 块 | 行 | 判别 |
|---|---|---|
| 1 | :48-:57 | 面锚点未漂移＋5 枚锚文本全文唯一 |
| 2 | :58-:61 | `index.html` 必须继续声明 `shuffle_policy.js`（变异 M10 命中点） |
| 3 | :62-:82 | 载入真模块与包装体；`MAX_ITEMS === 50000` |
| 4 | :84-:92 | 同元素／同长度／不返回调用者原数组／不改写调用者数组 |
| 5 | :94-:98 | 反向假策略（`reverse`）证明「确实把活交给模块」 |
| 6 | :99-:109 | 预算只限乱序额度：`MAX_ITEMS:3` 输入 5 项 ⇒ `[3,2,1,4,5]`；50,001 项末位仍在位；`MAX_ITEMS:0` 视作全量 |
| 7 | :111-:124 | 降级矩阵：模块缺席／非数组入参／空表／返回字符串／返回短数组／抛异常 |
| 8 | :126-:130 | 源码级接线：两条建队字面量各唯一、`.sort(() => Math.random()` = 0、`shuffleItems(` ≥ 3 |
| 9 | :132-:137 | `compareName` 在整个 UI 目录 0 命中 |
| 10 | :139-:157 | 已登记孤儿白名单 `pendingOrphans = ["effectiveProfile"]`；第二枚孤儿即判红；`state.accessProfile` 非赋值读取全文 = 1 |

真仓内直跑：`node tests\test_ui_library_sort_shuffle.js` ⇒ `Library sort/shuffle policy regression checks passed.` rc 0。

## 七、红证（现盘守卫 × HEAD 母本）

`git cat-file blob HEAD:src/app/ui/app.js`（412,341 B）＋ 现盘守卫落入仓库外 `<TEMP>\r159red2`，跑守卫：退出码 **1**，首枚判红在 `test_ui_library_sort_shuffle.js:101`「beyond-budget items keep their original order at the tail instead of vanishing」，实得 `[5,4,3,2,1]`、应为 `[3,2,1,4,5]`。全程未用 `git checkout --`。

## 八、控制组（仓库外副本，先绿）

`git archive HEAD` 落 `<TEMP>\r159ctl` ＋ 覆盖本轮两文件 ＋ `git init`（`test_license_files.test_repository_is_still_unhosted` 要读 `.git/config`）＋ 副本内刷新清单 717 条：Python `Ran 2567 tests in 130.045s — OK (skipped=3)` rc 0，JS 82 套件发现式全跑 0 失败。两套先绿后才允许进入变异与门禁。

## 九、变异矩阵（本轮收尾时原地重跑一次，结果一致）

`python -X utf8 <TEMP>\r159mut.py` 十格，逐格独立子进程：

| 格 | 变异 | 结果 |
|---|---|---|
| M1 | 原样（对照） | rc=0 绿 |
| M2 | 入口退回 HEAD 朴素写法 | rc=1 灭 |
| M3 | `playGroup` 退回比较器洗牌 | rc=1 灭 |
| M4 | `playAll` 退回比较器洗牌 | rc=1 灭 |
| M5 | 去掉 `try/catch` | rc=1 灭（判红原因单独复证为 `Error: hostile rng` 穿出 `shuffleItems`） |
| M6 | 去掉 `.concat(tail)` | rc=1 灭 |
| M7 | 回落换成空数组 | rc=1 灭 |
| M8 | 无视预算（全量交给策略） | rc=1 灭 |
| M9 | 复活 `compareName` | rc=1 灭 |
| M10 | 摘掉 `index.html` 的策略声明 | rc=1 灭（`index.html must keep declaring shuffle_policy.js`） |

⇒ **9/9 全灭**，且每一格灭因均指向本轮的具体改动，非「文件读不出来」型假绿。

## 十、清单与门禁

- `tools/update_source_manifest.ps1:29` 的取证范围只有 `src/` 与 `android-client/`，**三份根文档不入清单**。刷新结果 716 → **717**：新增 1（新守卫）／改哈希 1（`app.js`）／删除 0；逐条唯一、Ordinal 行序、纯 CRLF、无 BOM。逐文件抽查 MATCH：`app.js de37cb5a…`、新守卫 `cf4eed5a…`、`shuffle_policy.js c5ae651c…`。
- 门禁终跑 `artifacts/offline-20260923-round251.log`（＋同名 `.err`），退出码 **0**：Python `Ran 2567 tests in 132.049s — OK (skipped=2)`；JS 盘上 82 个 `test_*.js` 全部成功（80 枚 `... passed.` ＋ 2 枚异体成功行），本轮新守卫的成功行在门禁输出内实到；`git diff --check` 仅吐出 `SOURCE_MANIFEST.sha256` 的 CRLF 提示。
- 日志名口径：沿用门禁自身的**自增计数器**（R158 为 round249，本轮两次真实运行落在 250／251），**不跟轮号**；round250 那次未能捕获退出码，其日志对已删除，不留悬空引用。
- skipped 真仓 2 与副本 3 的差因取证：`src/tests/test_offline_verification_script.py:232-236` 在 `artifacts/release-evidence-index-latest.json` 缺席时 `skipTest`；该文件未跟踪（`git ls-files --error-unmatch` rc 1），故 `git archive` 副本没有它。真仓该模块单跑 `Ran 15 tests OK` skipped=0，副本 skipped=1；真仓余下 2 枚是 `test_process_output.py` 的两枚 POSIX 进程组用例。
- 收尾复跑根文档守卫：`python -B -X utf8 -m unittest tests.test_change_record tests.test_device_todos_migrated` ⇒ `Ran 12 tests` OK。

## 十一、口径与「还剩多少」

- 三口径并存、**不合并**：旧目标正文快照 `155 = 64 + 82 + 9`；R99 实测 `115 = 51 + 43 + 8 + 13`；现盘逐轮口径 **开放 4 = 代码 2 ＋ 长期观察 2**；另真机迁出 11 条（`docs/REAL_DEVICE_GOALS.md` G01-G11）＋ 外部验收台账 45 张卡（`docs/external-acceptance.md`）属「以后的目标」。
- 终止四条件：(3) 决策桶已清空 ⇒ 成立；(2) 自 R157 起结构性成立；(1) **未成立**——唯一实质剩余是深读债：现盘未点名 **235** 枚（app.js）＋ 已跟踪 Android `.java` 43 文件／9,695 行，欠读总量 **18,164** 行；(4) 仅在终止那一轮跑门禁才成立。⇒ 报「1/4 成立 ＋ 1/4 结构性成立」，**禁止自称完成**。
- 本轮**净关闭 0 条代码待办、新立 0 条**：两枚在开代码项是累计型深读门，面未读毕结构上不可能关闭，如实报 0，不用「修复了几个缺陷」抵充关闭数。
- 粗估剩余：app.js 235 枚未点名按 40-42 枚／轮 ⇒ 6-7 轮；Android 面 15-22 轮。合计 ≈22-29 轮（不含真机段与台账）。

## 十二、记入未修：`effectiveProfile` 孤儿链（按反增长约束并入记录，不另立条目）

`effectiveProfile`（现盘 :1825-:1828）0 引用，是 `state.accessProfile` 唯一的非赋值读取者、`isPrivateHost`（:1807）唯一调用者，而后者是 `ui/host_privacy_policy.js`（`index.html:167` 声明，Android 资产包内嵌）唯一消费者。`app.js:6077` 注释声称访问档驱动模式徽标，但 `updateModeButton`（:1829-:1843）只读 `state.mp3Transcode`，所以每次冷加载仍发 `api/access` 并在回调里调用一枚无消费者的函数。本轮不盲删：其真机取证与退役决策列入「以后的目标」，离线侧由守卫块 10 以白名单钉住「不得长出第二枚孤儿」。

## 十三、复审更正清单（相对接手草稿；均已按现盘改到文档里）

1. **门禁日志名**：草稿写 `offline-20260923-round159.log`——该文件不存在。门禁日志是**自增计数器**（续 R158 的 round249），本轮实跑为 round250／251，已改写为 round251 并删除 250 那对未捕获退出码的日志。
2. **清单范围**：草稿称刷新已覆盖三份根文档——不成立，`update_source_manifest.ps1:29` 只覆盖 `src/` 与 `android-client/`。已按真实口径改写。
3. **红证行号**：草稿写守卫 `:100`（当时副本文件 9,454 B），现盘 9,549 B 原地复跑得真实判红行 **101**，已复跑复证并改写。
4. **判别块数**：草稿写 11 枚，盘上实为 **10** 枚（`// --- N.` 计数），两处根文档均已订正。
5. **未点名余量**：草稿写 231，按「行首锚定 462 ＋ 三份根文档反引号与裸文本双口径 0 命中」复算为 **235**，与 276 − 41 严格相符。
6. **`- [x]` 计数**：草稿写 1,501（子串口径），本仓严格行首口径实测 **1,502**，已订正。
7. **skipped 差因**：草稿只写「副本 3 / 真仓 2 有差异」，本轮补做取证定位到未跟踪的发布证据索引，不再以「环境差异」搪塞。
