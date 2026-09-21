# fnAudio · R123 修改审核对照（接管取证 + 逐 hunk）

生成时间：2026-09-20（Asia/Shanghai）。仓库 `C:\path\to\fnAudio`，分支 `main`。
本文件是**给人逐 hunk 审核的交付物**，不是文件清单；每个 hunk 都带磁盘证据、具名杀手测试与变异编号。
本文件本身不入库（与 `artifacts/`、`music/`、`_external/` 同批未跟踪件）。

---

## 0 接管取证（当场实测，不引用任何历史快照）

| 项 | 磁盘读数 |
| --- | --- |
| 起始 HEAD（接管时） | `20158f1` docs: add the R122 closing addendum (round188 is the final gate) |
| 未完成 Git 状态 | 无 merge / rebase / cherry-pick（`.git/MERGE_HEAD` 等 0 命中） |
| 接管时已跟踪改动 | 11 个（`README.md`、`SOURCE_MANIFEST.sha256`、`src/app/ui/{app.css,app.js,index.html}`、`src/tests/`4 个） |
| 待入库未跟踪件 | 6 个（`LICENSE`、`NOTICE`、`AUTHORS`、`src/tests/{test_license_files.py,test_ui_dead_queue_entry_points.js,test_ui_transport_state_unknown.js}`） |
| 本轮终跑门禁 | `artifacts/offline-20260920-round189.log` ⇒ `GATE_EXIT=0`；Python `Ran 2437 tests in 108.161s` + `OK (skipped=2)`；JS 检查 **72 项全绿**（含本轮新增 `Transport state-unknown lamp regression checks passed.` 与 `Dead queue entry point regression checks passed.`） |
| 清单 | `SOURCE_MANIFEST.sha256` **703 条**；`takeover_forensics` ⇒ `drift 0 / stale 0 / unlisted 0` |
| `git diff --check` | 空（无行尾空白、无冲突标记） |
| 半截文件 | `.new` / `.orig` / `.rej` 递归 0 命中（排除 `artifacts/`、`_external/`） |
| 提交后 | `git status --porcelain -uno` **空** |

本轮落地的三笔提交（逐文件显式 pathspec，未用 `git add -A`，未碰 `.gitignore`）：

1. `f41d362` feat: license the project under GPL-3.0-or-later ⇒ `LICENSE` `NOTICE` `AUTHORS` `README.md` `src/tests/test_license_files.py`（+812 / -1）
2. `cb59dbe` fix(ui): mark extrapolated transport state as unknown and drop dead queue entry points ⇒ `src/app/ui/{index.html,app.css,app.js}` + 5 个测试文件（+371 / -63）
3. `701c817` chore: record R123 closure ⇒ `TODO.md` `CHANGELOG_AI.md` `PROJECT_CONTEXT.md` `SOURCE_MANIFEST.sha256`

### 0.1 四桶复算（按行首勾选标记 + 节标题文本锚定；行号只是当轮线索）

`TODO.md` 盘上 2212 行（按 `\n` 分割，含末尾空行），`- [ ] ` 行首前缀 **77** 条，`- [x] ` **1461** 条。77 条的真实归属：

| 桶 | 条数 | 锚定方式（节标题 + 当轮行号） |
| --- | --- | --- |
| 可离线代码项 | **18** | 主表 16（L37、L38、L71、L88、L100、L102、L104、L111、L115、L118、L139、L149、L152、L153、L157、L174）+ L545（持续审查未完成范围）+ L1836（按可测试边界继续拆分） |
| 设备/外部验收项 | **44** | L793 + 宿主 MediaSession 段 10（L810..L842）+ Android 等价 MediaSession 段 6（L973..L1173）+ P2 外部验收 3（L1825..L1827）+ P0 外部验收段 24（L1841..L1865） |
| 需项目负责人决策 | **2** | L1877（`allow_disk=False` 不生效的取舍）、L1881（D9 池开关是否上设置页） |
| 台账/历史叙述项 | **13** | L1883「完成定义」之后各「持续推进」段（L2070..L2152） |

⇒ **77 = 18 + 44 + 2 + 13**。

历史快照**并存、不合并、不覆盖**：`155=64+82+9`、`115=51+43+8+13`、`88=24+43+8+13`、`82=22+44+3+13`、`80=20+44+3+13`、`77=18+44+2+13`（本轮）。
上一轮交接笔记里的「77 = 16 + 44 + 2 + 13」把 L545 与 L1836 漏在代码桶外（求和也只有 75），本轮按节标题重算已纠正，并以此为准。

---

## T1 许可证三件套（`f41d362`）—— 关闭 TODO 决策段 D1（R121 记为 L1872）

### T1.1 新增 `LICENSE`（未跟踪 → 入库，674 行 / 35149 字节，裸 LF）

内容 = GNU GPL-3.0 **逐字正文**，未作任何修改。磁盘取证（首两行）：

```
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007
```

- 判别测试：`src/tests/test_license_files.py`（5 项）——逐文件 sha256、GPL 正文段落锚点、`AUTHORS` 禁邮箱与域名、`git remote -v` 为空即「暂不托管」未被动过。
- 变异证明 **V7**：删掉 `LICENSE` 里的 `Version 3, 29 June 2007` 一行 ⇒ `test_license_files.py` 立即红（正文段落锚点杀手）。

### T1.2 新增 `AUTHORS`（16 行 / 815 字节）

```
版权持有人与维护者（全部权利保留；授权条款见 `LICENSE` 与 `NOTICE`）：

    vinson023    项目发起人、版权持有人、维护者
```

按负责人裁定，署名对象只有 `vinson023`，**不写邮箱**（GPL 正文里的 `fsf.org` 是自由软件基金会自身版权行，属逐字正文不可改）；同时登记「自动化编码代理的改动并入上述版权持有人署名，不单独列出代理身份」与「不登记未经确认的第三方署名」。

- 变异证明 **V8**：在 `AUTHORS` 里插一个邮箱地址 ⇒ 被「禁邮箱与域名」项击杀。

### T1.3 新增 `NOTICE`（45 行 / 2135 字节）

登记三件事：版权归属（`Copyright (C) 2026 vinson023`）、版本选择（**GPL-3.0-or-later**，以 `LICENSE` 为唯一正文来源）、以及「暂不托管」现状下的**再分发义务**——对外分发 FPK 或 APK 必须按 `NOTICE` 随包提供对应源码。

### T1.4 `README.md` L97（1/1）

改前：

```
项目许可证尚未明确，不应自行假设开源授权。
```

改后：

```
项目许可证为 GPL-3.0-or-later（第 3 版或其后任一版本，由使用者选择），完整逐字正文见 LICENSE，版权持有人与维护者见 AUTHORS，再分发义务与托管现状见 NOTICE。2026-09-20 负责人裁定开源、暂不托管，git remote -v 实测为空，因此在建立公开源码地址之前，对外分发 FPK 或 APK 必须按 NOTICE 随包提供对应源码。
```

审核要点：这句话是**唯一**对外口径来源，且它把「方向已定」与「许可证已定」区分开了——D1 之所以在 R121 不能关闭，正是因为 `README.md:97` 还写着「尚未明确」；本轮补齐三件套后才具备关闭条件。

---

## T2 队列死码删除（`cb59dbe`）—— 实施 L71（负责人裁定 A：证伪 + 删死码，残余语义并入投送条）

取证（本轮重跑）：`git grep -E "addQueueAndPlay|playFolder|queue-play|addQueue" -- src android-client` 在**提交后的树上**只剩 8 处命中，全部位于 `src/tests/test_ui_dead_queue_entry_points.js` 的判别文本里；生产代码 **0 命中**。

### T2.1 `src/app/ui/app.js` hunk `@@ -4004,38 +4032,6 @@`（删 32 行）

删除 `async function addQueue(id)`（原 L4007）与 `async function addQueueAndPlay(id)`（原 L4017）。`selectedItems()` 与 `addSelectedToQueue()` **保留**（它们有真实生产者：右键菜单「加入队列」）。

审核要点：两函数唯一「调用点」是彼此与已死的右键别名，属零调用面；`addQueueAndPlay` 内部还带一处 `isPlayingNow()` 分支，是 `isPlayingNow()` 的假性依赖，删掉之后该谓词的调用面更干净。

### T2.2 `src/app/ui/app.js` hunk `@@ -4237,28 +4233,6 @@`（删 22 行）

删除 `async function playFolder(root = state.folderRoot, path = state.folderPath)`（原 L4240）整函数。它自带一套「重置 `streamOffset` / `pendingSeekTime` / `transcodeCacheReady` / `playSourceKind` + 洗牌 + `commitQueue`」的第二份播放装载逻辑，与 `playGroup()`、`playSelectedTracks()` 三处并存，是口径漂移的高发形状——留着比删掉更危险。

### T2.3 `src/app/ui/app.js` hunk `@@ -7432,7 +7426,7 @@`

改前：

```javascript
  else if (action === "queue" || action === "queue-play") addSelectedToQueue(selected);
```

改后：

```javascript
  else if (action === "queue") addSelectedToQueue(selected);
```

审核要点：`queue-play` 是**有消费者、无生产者**的别名——全仓找不到任何地方产生这个 action，等价于把「播放并加入队列」的语义以死码形式挂在那里，也是本次删除的入口锚点。

### T2.4 判别测试 `src/tests/test_ui_dead_queue_entry_points.js`（新增 97 行）

首行具名报错：`addQueueAndPlay must stay deleted (app.js)`；对 `addQueue` / `addQueueAndPlay` / `playFolder` 三个名字逐个 `assert.doesNotMatch`，并断言 `"queue-play"` 字面量已消失、在 vm 里以 `queue-play` 触发 `runTrackAction` 之后**除菜单关闭外零路由**（`assert.deepEqual(calls.filter(...), [], "queue-play must no longer route anywhere")`）。文件尾另留一条反向不变量：被处理却没人生产的分支就是死码，被生产却没人处理的 action 同样算缺陷。

- 变异证明 **V1**：把 `addQueueAndPlay` 原样加回 `app.js` ⇒ 本杀手测试指名报错。

---

## T3 「状态未知」灯（`cb59dbe`）—— 实施 L74（负责人裁定 A：阈值 10 秒 / 文案「状态未知」/ 位置 `#elapsed` 之后 / 复用现有状态字段）

背景缺陷：传输行在状态通道断供时**继续走外推**，`transportExtrapolation()` 会把位置钳在预算上限并**冻在那里**；冻住的计数与真暂停无法区分，于是界面在说谎。本轮把「这块屏在吃外推而不是吃证据」显式告诉用户。

### T3.1 `src/app/ui/index.html` L70（1/1）

改前：

```html
    <div class="progress"><span id="elapsed">0:00</span><input id="seek" ...><span id="duration">0:00</span></div>
```

改后（`#elapsed` 之后插入，位置按裁定）：

```html
    <div class="progress"><span id="elapsed">0:00</span><span id="transportStateUnknown" role="status" title="状态通道未更新，位置可能不准">状态未知</span><input id="seek" ...><span id="duration">0:00</span></div>
```

审核要点：文案写在 HTML 里是**静态**的，JS 只切 `data-state`，因此「500ms 轮询什么都没变」仍然一次 DOM 写入都不发生——这是本轮写次数断言的前提。

### T3.2 `src/app/ui/app.css` hunk `@@ -762,6 +762,16 @@`（盘上 L765-L774，新增 10 行）

```css
/* Transport staleness lamp (TODO.md:74).  `#elapsed` and `#duration` are hidden at every
   width, so the frozen extrapolated position this replaces had no visible tell at all.
   Its visibility is driven by the `data-state` attribute written from app.js, and its copy
   is static in index.html, so a poll that changes nothing still writes nothing.
   The ID is load-bearing, not decoration: `.progress>span` above and `.progress span` at
   :1146/:1274 hide every span in the row with !important, and (1,1,0) is the only shape
   that out-ranks (0,1,1) inside the important cascade regardless of source order. */
#transportStateUnknown{display:none}
#transportStateUnknown[data-state="unknown"]{display:inline-flex!important;align-items:center!important;color:#b45309!important;font-size:10px!important;...}
@media(min-width:761px){#transportStateUnknown[data-state="unknown"]{position:absolute!important;top:-17px!important;left:14px!important;height:15px!important;padding:0 7px!important;border-radius:8px!important;background:#fff7ed!important;box-shadow:0 1px 3px #17203322!important;font-size:11px!important}}
```

**这是本轮最容易看错的地方**：紧邻上一行 L764 就有 `.progress>span{display:none!important}`，而 `:1146` 与 `:1274` 还有 `.progress span{...}` 用 `!important` 吞掉行内所有 span。类选择器（0,1,1）在 important 层里压不过它，只有 ID（1,1,0）能压过——所以 ID 是功能件，不是命名偏好。
取证还包含一次真实计算样式核对：R122 之前该元素曾被 `!important` 层完全吞掉（写了值但看不见）。

- 变异证明 **V6**：把选择器从 `#transportStateUnknown` 换成 `.progress span` ⇒ 判别测试红（「shown state must out-rank the !important hides ... which needs an ID」）。
- 顺带修复：`app.css` 全文件行尾污染已清，盘上 **0 CRLF / 168902 字节**。

### T3.3 `src/app/ui/app.js` hunk `@@ -4443,6 +4417,16 @@`：新增谓词 `transportStateIsUnknown()`（盘上 L4427）

```javascript
function transportStateIsUnknown(snapshotAt, playing) {
  return playing === true && transportExtrapolation(snapshotAt, true) >= TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS;
}
```

审核要点：这里**故意不重新算一遍时间差**，而是把 `transportExtrapolation()` 的钳位结果读回来比较。理由是外推与判灯必须共用同一份预算（阈值常量 `TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS = 10`，盘上 L4409），两套算术迟早会在边界上分家。参数化（传 `snapshotAt`/`playing`）而不是伸手进 `state`，是为了让「问的是哪条通道」写在调用点上，同时保住 `test_ui_transport_staleness.js` 断言的单闸门形状。

- 变异证明 **V3**：阈值 10 改成 30 ⇒ 「the ruled budget is 10 seconds」红。
- 变异证明 **V5**：把 `playing === true` 取反 ⇒ 判灯语义杀手红。

### T3.4 `src/app/ui/app.js` hunk `@@ -1904,10 +1909,28 @@`：新增 `updateTransportStateUnknown()`（盘上 L1917）+ 本机进度轮末尾接线（L1912）

```javascript
function updateTransportStateUnknown() {
  let unknown = false;
  if (isIncomingRendererSession()) {
    unknown = transportStateIsUnknown(state.rendererSnapshotAt,
      String(state.rendererSession?.transport || "").toUpperCase() === "PLAYING");
  } else if (isRemoteTarget()) {
    unknown = transportStateIsUnknown(state.remoteSnapshotAt,
      String(state.remoteStatus?.transport?.state || "").toUpperCase() === "PLAYING");
  }
  setDatasetStateIfChanged($("transportStateUnknown"), unknown);
}
```

审核要点：两条状态通道**按 `currentSeconds()` 的解析顺序**分别问，先受控端投影、再远端设备；两者都不成立就是本机播放，本机权威是 `audio.ontimeupdate`，它不会「数字还在更新但通道已冻」，所以显式清灯（`else` 分支隐含 `unknown = false`）。复用的正是裁定要求的现成字段 `rendererSnapshotAt` / `remoteSnapshotAt`，没有新增时间戳。

### T3.5 `src/app/ui/app.js` hunk `@@ -2087,6 +2110,11 @@`：**灯接线在 `updateRemoteUi()` 两条 early return 之前**（盘上 L2117）

```javascript
function updateRemoteUi() {
+  updateTransportStateUnknown();          // 首条语句
   if (updateIncomingRendererUi()) return;
   if (!isRemoteTarget()) return;
```

**这是全轮最需要人看的一行位置**：`currentSeconds()` 会把外推位置钳在上限，通道一旦断供，下面那串 memo 就一直看到相同的数字并在 early return 处返回；灯若接在闸门**之后**，就只会在「已经不再变化的变化」上点亮——即永远不亮。

- 变异证明 **V2**：把这次调用挪到 `if (updateIncomingRendererUi()) return;` 之后 ⇒ 判别测试指名报错 `the lamp must be written before the early returns: currentSeconds clamps at the limit, so a frozen memo would hide it`。

### T3.6 `src/app/ui/app.js` hunk `@@ -1823,6 +1823,11 @@`：换设备也要清灯（`updateDeviceLabel()` 首行，盘上 L1830）

`render()` 换设备时只重画这一行的「归属」，不重画整行；不从这儿清灯，就会把上一台设备的「状态未知」留在新设备名下。本机分支不写 DOM，因此每次 render 多这一次调用成本为 0。

- 变异证明 **V9**：删掉这次接线 ⇒ 「a device switch repaints the row's owner but not the row, so it must clear the lamp too」红。

### T3.7 `src/app/ui/app.js` hunk `@@ -5357,6 +5341,16 @@`：新增 `setDatasetStateIfChanged()`（盘上 L5344）

```javascript
function setDatasetStateIfChanged(node, value) {
  if (!node || !node.dataset) return;
  const next = value === true ? "unknown" : "";
  if ((node.dataset.state || "") === next) return;
  node.dataset.state = next;
}
```

审核要点：与 `setTextContentIfChanged` / `setStyleVarIfChanged` 同族，遵守既有硬规矩——凡是定时器可达的写入都必须先比较。**清除写空串而不是 `delete`**，因为空串同样不匹配 `[data-state="unknown"]`，却能让第二次、第三次同值调用无事可做（幂等）。

- 变异证明 **V4**：删掉那行比较守卫 ⇒ 写入计数从 1 变 3，同值短路杀手红。

### T3.8 判别测试 `src/tests/test_ui_transport_state_unknown.js`（新增 184 行）

四条具名报错分别咬住：接线位置（V2 同源文案）、10 秒预算、ID 可见性、换设备清灯；并用假节点统计 `dataset.state` 写入次数，验证「同值轮询零新增写入」。门禁日志里对应 `Transport state-unknown lamp regression checks passed.`。

---

## T4 既有测量扩样（防「新增写入器把成本测量做瞎」）

`syncPlayerProgress()` 多出第三个写入者，所以两个既有成本/写入次数测试必须把灯**一起跑进 vm**，否则它们测的是不完整的真实轮询。

### T4.1 `src/tests/test_ui_library_loading.js`（11/2）

- `progressSource` 名单追加 4 个函数：`updateTransportStateUnknown`、`transportStateIsUnknown`、`transportExtrapolation`、`setDatasetStateIfChanged`；
- `progressContext` 补两个桩：`isIncomingRendererSession: () => false`、`isRemoteTarget: () => false`（让轮询走本机分支）；
- 新增 `progressLimit = app.match(/^const TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS = [^\n]+/m)` 与断言，并把该 `const` 前置注入 `vm.runInNewContext`——函数体引用了顶层常量，vm 里没有它就直接 `ReferenceError`。

原断言保持不变：一次真实进度变化 = 一次文本写 + 一次轨道写（`writes + styleWrites === 2`）。**扩样之后它仍然只有 2**，这正是「灯在同值轮询里零成本」的证据。

### T4.2 `src/tests/test_ui_renderer_transport.js`（17/4）

- 新增 `constSource(name)`（顶层 `const` 提取器，与既有 `functionSource` 同族）；
- 新增 `stalenessLampNames` 四个函数名；两处 vm 上下文（`sources`、`railSources`）改为 `.concat(stalenessLampNames).map(functionSource)` 并前置 `limitConst`；
- 一次提交里同时保住「`syncPlayerProgress();` 与 `updateNowMarquee();` 相邻模式恰 6 处」这类形状断言（因此新函数一律加在函数体外，不插在两行之间）。

### T4.3 顺手项 `src/tests/test_playback_event_presentation.py`（2/1）

把 `if __name__ == "__main__":` 前的单个空行改成两空行（PEP8 顶层定义后两空行）。无功能改动。

---

## 5 变异矩阵与控制组（仓库外副本 `C:\path\to\fnAudio_r123_verify2`，已删除）

| 编号 | 变异 | 指名杀手 | 结果 |
| --- | --- | --- | --- |
| V1 | 把 `addQueueAndPlay` 原样加回 `app.js` | `test_ui_dead_queue_entry_points.js` | 红（杀灭） |
| V2 | 灯的接线挪到 `updateRemoteUi()` 两条 early return **之后** | `test_ui_transport_state_unknown.js` | 红（杀灭） |
| V3 | 外推预算 10 秒改成 30 秒 | `test_ui_transport_state_unknown.js` | 红（杀灭） |
| V4 | 删 `setDatasetStateIfChanged` 的比较守卫 | 写入计数断言（1→3） | 红（杀灭） |
| V5 | `playing === true` 判据取反 | `test_ui_transport_state_unknown.js` | 红（杀灭） |
| V6 | CSS 选择器 `#transportStateUnknown` → `.progress span` | 计算样式/特异性断言 | 红（杀灭） |
| V7 | 删 `LICENSE` 的 `Version 3, 29 June 2007` 行 | `test_license_files.py` | 红（杀灭） |
| V8 | 在 `AUTHORS` 插入邮箱 | `test_license_files.py` | 红（杀灭） |
| V9 | 删 `updateDeviceLabel()` 里的清灯接线 | `test_ui_transport_state_unknown.js` | 红（杀灭） |
| V10 | （自造冗余用例）锚定不存在的字符串 | —— | SKIP，非缺陷，登记说明 |

控制组（改动前先跑，必须先绿）：Python `Ran 2437 / OK (skipped=3) / EXIT=0`；Node JS `files=72 failures=0`。
副本重建纪律：全量 `git ls-files` 复制 + 6 个未跟踪新文件 + `.git/config`（`test_repository_is_still_unhosted` 要读）；清单先刷新，否则 `test_source_manifest` / `test_takeover_forensics` 必红。

---

## 6 三份根文档与清单（`701c817`）

| 文件 | 本轮插入 | 盘上取证 |
| --- | --- | --- |
| `TODO.md` | R123 记录于 **L2**；三条收口 `L1872→[x]`、`L71→[x]`、`L74→[x]`（收口说明在**同一行末尾追加**，原条目均为单行，不新增行） | 2212 行（按 `\n`）；开放 77 / 已关闭 1461；CRLF 0；控制字符 0；扁平记录段 L2..L125 |
| `CHANGELOG_AI.md` | L2 插入 3 条（实现 / 测试+控制组+变异矩阵 / 收口+清单+门禁+提交） | 6706 行；记录段 L2..L852；records 852；CRLF 0 |
| `PROJECT_CONTEXT.md` | L2 插入 4 条教训：① 可见性落点必须用真实计算样式与作用域取证（V2/V6 为实据）；② `.gitattributes` 归一化会让行尾污染在 `git diff` 里隐形；③ 根文档计数一律按行首前缀，同前缀条目定位必须加长锚点；④ Windows 路径写进 python 非 raw 串时 `\f` 会变成 0x0C，而 `splitlines()` 把它当换行 | 6138 行；记录段 L2..L444；records 444；CRLF 0；控制字符 0 |
| `SOURCE_MANIFEST.sha256` | `tools/update_source_manifest.ps1` ⇒ `Wrote 703 entries`；复跑 `takeover_forensics --full` ⇒ `listed 703 / drift 0 / stale 0 / unlisted 0` | 逐文件抽查含本轮 6 个新文件 |

计数口径提醒（写在记录里，避免下轮重犯）：`count("- [x] ")` = 1459，但按**行首前缀**只有 1457——差 2 处是正文里的行内引用；根文档门禁以行首口径为准。
`test_change_record.py`（OK，3 项）与 `test_source_hygiene.py`（OK，7 项）在收口后连跑通过。

设备段核对：本轮 `TODO.md` 里 **L1839 之后 P0 段 24 条、宿主 MediaSession 段 10 条、Android 段 6 条、P2 段 3 条、L793 一条，正文一字未改**（只作为分类锚点读取）。

---

## 7 这个目标还剩多少没完成（按四项终止条件逐条回答）

目标正文四项（R123 之后，磁盘取证）：

1. **代码桶清零：未完成。** 仍开 **18** 条（主表 16 + L545 审查范围 + L1836 拆分）。本轮从 20 → 18（净关闭 2 条实现项 + 关闭 1 条决策项 D1）。已裁定、可直接排期的只有 2 条：L71（投送三段口径 D 裁定：投送即停本机 + 本机播放意图抢占投送 + 投送结束不自动续播）、L152（A+C：口径入 docs + 写路径 `None`→`""` 与旧库一次性收敛）。其余 14 条仍需逐轮取证立项/证伪，其中含 4 条明确标注「要先有真实分布数据才动」（L37、L38、L157、L174 一类）。
2. **设备/外部项移出逐轮任务：已达成，须保持。** 44 条全部留在设备段，36+ 轮无一条被盲改；本轮同样为 0 改动。
3. **需产品决策项全部落地：未完成。** 决策段仍开 **2** 条：L1881（**D9 曲库连接池开关是否上设置页**——裁定方向已给「要上」，尚未实施）与 L1877（`allow_disk=False` 不生效的取舍，仍待方向）。另有台账/历史段 13 条「持续推进」叙述项不计入代码桶，但也不能被勾选。
4. **终止前完整离线门禁全绿：本轮已达成一次**（round189：exit 0 / Python 2437 OK / JS 72 / 清单 703 / `diff --check` 空），但它只是**每轮动作**，不是终止条件本身——终止要求在第 1、3 项成立之后再跑一次。

⇒ 距离终止的最小工作量：**代码 18 条 + 决策 2 条 = 20 条**，按已裁定的推进节奏（每条 1～2 轮）粗估 **10～15 轮**；其中 4 条依赖真机/外部数据（D5 类，测试机已授权但不能用离线测试替代），这类要么真机取证、要么并入设备段，不得为凑数关闭。
`maxGoalRounds = 72`、已完成 36+ 轮 ⇒ 不据此终止，也不修改终止条件。

### 下一轮（R124）排期

D9 落地：`library_connection_pool` 开关上设置页。取证锚点（当轮行号，重跑为准）：`src/app/server/config.py:22` `DEFAULT_LIBRARY_CONNECTION_POOL = True`、`:29` 默认表、`:93-94` 与 `:153-154` 两处 `_strict_bool` 读取；`server.py:591 commit_config_update → :606 apply_library_connection_pool_config`；`library.py:1905/1917`。设置页需同时补「非法值回落默认」的判别测试与开关可见性取证。
R125 排期：L71（投送三段口径，`isIncomingRendererSession()` 缺位的 5 处）+ L152（A+C）。
