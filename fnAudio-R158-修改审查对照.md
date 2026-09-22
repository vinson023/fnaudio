# fnAudio R158 修改审查对照（逐处 · 行号为「三份根文档写入后」盘上真实 1-based）

基线 HEAD：`1f110b7`（R157 第 5 笔）。本文件所有行号均以现盘 `splitlines()` 复核，非草稿值。

## 文件净增（`git diff --numstat`，对 HEAD `1f110b7`）

| 文件 | + | - | 现盘规模 |
|---|---|---|---|
| `src/app/ui/app.js` | 5 | 3 | 8,456 行 / 412,341 B / LF / 无 BOM |
| `src/tests/test_ui_android_bridge.js` | 2 | 1 | 815 行 |
| `src/tests/test_ui_native_bridge_queue.js`（新增，未跟踪→第 2 笔入库） | — | — | 416 行 / 21,584 B / 71 处 `assert` |
| `TODO.md` | 2 | 1 | 顶部新条 + 深读条追加 |
| `CHANGELOG_AI.md` | 2 | 0 | 修复条 + 取证/门禁条 |
| `PROJECT_CONTEXT.md` | 1 | 0 | 一条可迁移经验 |
| `SOURCE_MANIFEST.sha256` | 3 | 2 | 715 → 716 条 |

## 一、接管取证（磁盘实测，不采信交接快照）

- 分支 `main`、HEAD `1f110b7`、无 remote、无 stash。
- 未完成态逐个 `Test-Path`：`.git/MERGE_HEAD`、`.git/rebase-apply`、`.git/rebase-merge`、`.git/CHERRY_PICK_HEAD`、`.git/BISECT_LOG`、`.git/sequencer` 全部 False。
- 工作树：2 改 1 新（+ 清单）。`artifacts/`、`_external/`、`references/`、`tools/android-sdk*` 等巨量未跟踪物不属项目文件，故全程禁用 `git add -A`。
- `TODO.md` 开放 `- [ ]` = 4：L110（欠读量化门）、L161（app.js 深读面）、L2045、L2067（后两条为长期观察）。
- `app.js`：`node --check` 通过；行首锚定 `^(?:async )?function 名称(` 实测命名函数 463 枚／unique 463。

## 二、本轮读毕的面与分子变化

- 面：`app.js` :494-:883「Android 原生桥与宿主播放命令面」，连续切片 390 行／25 枚命名函数。
- 上一轮（R157）候选清单只列了其中 13 枚；本轮按切片整面读完，另 12 枚为复读。
- 写入前三份根文档**反引号与裸文本双口径均 0 命中**者 3 枚 ⇒ 首次点名：`nativeAbortError` :528-:535、`isFnAudioApiUrl` :563、`isApeTrack` :794。
- 深读分子 **78 → 81**；登记分母 381 不改写（`docs/REVIEW_ROUND_DISCIPLINE.md` 第五节：历史数字禁改）。
- 未点名命名函数：写入前实测 **280** 枚 ⇒ 本文件所属根文档写入后 **277** 枚（减 3 与首次点名数严格相符）。

## 三、修复 A：`nativeLoadQueue` 的死存储（`app.js` :857-:871）

取证链：`state.nativeQueueSignature` 现盘命中 **0**；该键从未在 `state` 字面量声明；全文无读取点；:863 的「队列是否同一份」判定用的是 `remoteIds`/`localIds` 逐位比较，不消费签名。
删除两行 ⇒ 每次载入本机队列少做一整遍 `JSON.stringify(rows.map(...))`。
`nativeQueueSignature` 此后仅存 :851（定义）与 :816（`nativeRemoteEnter` 活通道调用）。

## 四、修复 B：分表上界的裸字面量（`app.js` :611，注释 :521-:524）

- 改前：`if (nativeHttpResponseChunks.size >= 32) return;`
- 改后：`if (nativeHttpResponseChunks.size >= MAX_NATIVE_HTTP_REQUESTS) return;`
- 理由：32 这个数字同时是 `MAX_NATIVE_HTTP_REQUESTS`（:519）与 Android `MainActivity.java` :111 `MAX_NATIVE_HTTP_CALLS` 的值；分表寿命依附于在飞请求预算，各写一份字面量 ⇒ 改一侧即静默漂移。
- 合同常量本轮一并对齐复核：JS `MAX_NATIVE_HTTP_CHUNKS` 256 ＝ Android :107；`MAX_NATIVE_HTTP_RESPONSE_CHARS` 4 MiB ＝ Android :106。

## 五、守卫同步（`test_ui_android_bridge.js` :318-:319）——本轮第三处改动

原守卫：`requireText("nativeHttpResponseChunks.size >= 32", "Native HTTP transfer bookkeeping needs a bounded entry count")`
它把 B 要删的**缺陷写法逐字钉死**，控制组首跑 81 枚 JS 中正是它判红。
现改为钉 `nativeHttpResponseChunks.size >= MAX_NATIVE_HTTP_REQUESTS` ＋ 措辞「must stay bounded by the named in-flight request budget」（折行两行）。
定性：修复必然连带的口径同步，不新立待办。

## 六、证伪与观察（不当缺陷修、不立条）

- **C 证伪**：`MainActivity.java` :789-:793 的 `onResponse` 在投递前先 `if (!nativeHttpCalls.remove(safeRequestId, call)) return;` ⇒ :828-:833 `cancelRequestJson` 对**已送达**请求取不到 call，是无操作，不构成「取消后仍能收到数据」缺陷。已钉为新测试块 8。
- **D 观察**：`nativeBridgeCall` :840 与 `nativePlaybackCall` :505 函数体近乎相同，差别仅在可用性门。按反增长约束并入本文件与本条记录，不另立条目。

## 七、判别测试：`src/tests/test_ui_native_bridge_queue.js`（新增 416 行）

切片锚：`function nativePlaybackAvailable() {` → `window.fnAudioNativeOnState =`；`vm.createContext` 注入 `URL`、`URLSearchParams`、`setTimeout/clearTimeout`、计数版 `JSON`、`state`、`currentItem`、`isRemoteTarget` 等。
11 个判别块：1-2 序列化次数与 `setQueue` 实参；3 签名可区分性（含本轮补的分隔符歧义直接断言）；4 时长钳位；**4b** 负时长行（本轮补）；5-6 分表上界与命名常量；7 `isFnAudioApiUrl`；8 Android 侧取消语义证伪；9 `isApeTrack`；10 异步收口（async IIFE + `.catch` 设 `process.exitCode`，不可改回顶层 await：CJS 报 `ERR_AMBIGUOUS_MODULE_SYNTAX`）。

## 八、红证 / 控制组 / 变异矩阵

- **红证**：`git show HEAD:src/app/ui/app.js` 母本（8,455 split-nl；签名命中 [812,847,857,866]；裸 `>= 32` 在 :607）在三个 `%TEMP%` 变体跑新测试，分别判红于 :159 / :173 / :297，三趟 exit 均 1、通过标记均 False。全程未用 `git checkout --`。
- **控制组**（仓库外 `git clone --no-hardlinks` + `git remote remove origin`）：JS 81 套件 failed 0；Python `Ran 2567 tests`，仅 2 条 FAIL 且同为「清单落后守卫」，副本内重跑刷新工具（同样 716 条）后定向复跑 7 OK ＋ 10 OK。
- **变异矩阵** 11 格（逐格独立子进程）：首跑 9 killed／2 survivors ⇒ M9（去 `durationMs` 钳位）、M11（签名退化为 `join(",")`）判为**测试自身缺口**，当场补块 4b 与块 3 直接断言；重跑 **11/11 killed，survivors []**。

## 九、清单与门禁

- `SOURCE_MANIFEST.sha256` 715 → **716**；逐条唯一、Ordinal 行序、纯 CRLF、无 BOM、缺盘 0、口径仅 `src/`＋`android-client/`；逐文件抽查 MATCH：app.js `5C2EE6BA…`、android_bridge 测试 `A661A757…`、新测试 `6D78C029…`。
- 门禁终跑 `artifacts/offline-20260922-round249.log`（437,983 B／2,730 行；跑前 `Test-Path` False）：Python `Ran 2567 tests in 131.382s` → `OK (skipped=2)`；FAILED 0、Traceback 0；清单双守卫 ok；`index.html control names: 79 controls, 0 nameless, 3 labelledby rows, 1 keyboard role kept`；JS 按发现式口径＝盘上 81 个 `test_*.js` 全部退出 0（`tools/test_offline.ps1` :57-:61 任一非零即 throw）；exit 0。
- 时序说明：门禁日志晚于全部 `src/` 与 `android-client/` 改动；CHANGELOG 取证条在门禁后写入以实补数字，其后 `test_change_record.py`（3 OK）等根文档守卫复跑仍绿，且清单覆盖文件零改动（逐文件 sha 已复核）。

## 十、口径与进度

- 三口径并存、**不合并**：旧目标正文快照 `155 = 64 + 82 + 9`；R99 实测 `115 = 51 + 43 + 8 + 13`；现盘逐轮口径 **开放 4 = 代码 2 ＋ 长期观察 2**；另真机迁出 11 条（`docs/REAL_DEVICE_GOALS.md` G01-G11）＋ 设备台账 45 条（开放 28）属「以后的目标」。
- 终止条件：(3) 决策桶 0 ⇒ 成立；(2) 自 R157 起结构性成立；(1) 未成立——唯一实质剩余是 app.js 深读债（分子 81/登记分母 381，盘上未点名 277 枚）；(4) 仅在终止那一轮跑门禁才成立。⇒ **1/4 成立 ＋ 1/4 结构性成立，禁止自称完成**。
- R159 候选面（本棒实测，接手时须重测）：`app.js` :1568-:1816「曲库视图、播放列表、排序与转码判定面」，44 枚命名函数、42 枚未点名。

## 十一、复审更正清单（相对接手草稿）

1. **分子**：草稿写「78 → 80」，现盘双口径实测首次点名为 **3** 枚 ⇒ 正确值 **78 → 81**。
2. **改动面**：草稿只列 2 文件，实际 **3** 文件——`test_ui_android_bridge.js` :318 的陈旧文本 pin 必须同步（见第五节）。
3. **净增行数**：草稿写 app.js +4/-2，`git diff --numstat` 实为 **+5/-3**（8,454 → 8,456 splitlines）。
4. **未点名余量**：草稿写 311，本棒以「行首锚定 463 ＋ 三份根文档反引号与裸文本双口径 0 命中」复算为 **280**（根文档写入后 277）。草稿口径未排除根文档其它位置的裸文本提及，不可复算，弃用。
5. **欠读总量**：按现树复算 18,149 → **18,151**（app.js 8,456 ＋ 已跟踪 Android `.java` 43 文件 9,695），本轮修复净增 2 行 ⇒ 如实登记为**不降反升**，收益另记在深读面出局。
