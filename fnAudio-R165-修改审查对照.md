# fnAudio R165 修改审查对照

> 口径说明：本轮全部坐标按**现盘**文本锚点定位；行号只用于指位，判据一律是文本。历史轮次记录中的数字一律不改写。

## 一、本轮一句话结论

读完 `src/app/ui/app.js`「投送停止投影／目标绑定」面 42 枚符号，当轮修掉同面**两处**真缺陷（旧设备 stop 回包覆写新设备权威快照；停止后进度条与 `#elapsed` 冻在投送位置），配一套 4 用例判别套件与 6/6 全灭变异证明；本轮**净关闭 0 条既有代码待办、新立 0 条**。

## 二、缺陷定位（本轮要修的真东西）

| # | 缺陷 | 盘上证据 |
|---|---|---|
| A | `stopPlayback` 远端分支不绑定目标：发起前不取 `remoteDeviceId()`、`await remoteControl("stop")` 回来后不复检 ⇒ 用户切走之后，旧设备的 stop 回包把新设备刚声明的权威快照覆写成 `STOPPED` 并丢掉 `target_id` | 现盘 `src/app/ui/app.js:2162-2180`；同一不变量在 `remoteControl`（`:2678`）与 `refreshRemoteStatus`（`:2520`）里早已实现，本处是第三次漏写 |
| B | 同一分支只在乐观快照里写 `position.rel_seconds = 0`，而 `currentSeconds`（`:4579`）优先读 `state.remoteBaseSeconds` ⇒ 那句零是**死数据**：按停止后图标变暂停、进度条与 `#elapsed` 仍冻在投送位置 | 载入路径 `pushToDevice`（`:8003`）一直是「快照＋基线归零」成对写，停止路径只抄了一半；与 R99 记的「投送残留数字」同族 |

当轮证伪并登记为不改动（避免下一轮重复劳动）：`selectPlaybackTarget` 不清 `state.remoteUiLast`（不可观测）、`isDacTarget()` 无参调用合法（形参有默认值）、`maybeAdvanceRemoteQueue` 首行 `return;` 与 legacy 注释块系滚动升级刻意保留、`stopPlayback` 本地分支 `$("seek").value = 0`（`:2191`）属用户动作而非轮询面。

## 三、逐 hunk 改动

### Hunk 1 · `src/app/ui/app.js` 远端停止分支（`git diff` 净增 14 行＝代码 3＋注释 11）

```
   if (isRemoteTarget()) {
+    const targetId = remoteDeviceId();          // 绑定在请求之前
     await remoteControl("stop");
+    if (targetId !== remoteDeviceId()) return;  // 复检在投影之前
+    state.remoteBaseSeconds = 0;                // 基线归零在复检之后
     state.remoteStatus = { transport: { state: "STOPPED" }, ... };
     updateRemoteUi();
```

三行的**先后顺序**本身就是被钉住的语义：基线归零若在目标闸之前，一次被设备切换作废的 stop 仍会把新设备已经声明的位置清零。

### Hunk 2 · 新守卫 `src/tests/test_ui_stop_target_bind.js`（250 内容行／11,799 B／CR 0／尾 LF✓／sha256 前缀 `0bdd6f79a9a8de37`）

在 `vm.runInNewContext` 里跑**真实**的 `stopPlayback`、`updateRemoteUi`、`setPlayButton`、`currentSeconds`、`seekDuration`、`remoteDeviceId` 等 20 余枚，只有门控 Promise 的 `remoteControl` 与叶子辅助为桩；假节点逐次记录每一笔写入，因此「没写」与「写了同样的值」可判别。

| 用例 | 断言 |
|---|---|
| ① 沙龙房→书房切换 | 新设备快照对象恒等、`remoteBaseSeconds` 不被旧回包归零、整行写入序列为空 |
| ② 控制组（未切换） | 仍生效：`STOPPED`、`duration_seconds=200`、`remoteBaseSeconds===0`、`#elapsed` 逐字写入 `0:00`、`seek.value` 写入 `0` |
| ③ 切回本机 | `remoteStatus` 为 null、本机基线 120 不变、行零写（不得凭空造一份远端快照） |
| ④ 接线断言 | 绑定在请求前、复检在请求后投影前、基线归零在复检之后；并钉住两邻居仍含 `targetId !== remoteDeviceId()`，三处算同一条规则 |

**红证原文**（修复前）＝`AssertionError: a stop reply for the renderer the user left must not overwrite the snapshot the new device declared`。
**首版假红教训**：夹具把 `#elapsed` 预置成 `2:00` 而停止后期望值同为 `2:00`，比较式写入器合法静默被误读成缺陷 ⇒ 改测试期望（预置值与期望值必须不同），不改生产码。

### Hunk 3 · 三份根文档记录（最新在前）

* `TODO.md` L2 本轮记录（内容行 2,186→2,187）；`:117` 欠读账按现盘重测 18,176→**18,190**；`:168` 本面读毕登记（分子 168→**171**、分母 381 不动、0 点名者 187→**183**）。
* `CHANGELOG_AI.md` L2/L3/L4 三条（接管取证／红证与修复／副本、控制组与变异矩阵），内容行 6,800→6,803。
* `PROJECT_CONTEXT.md` L2/L3 两条判据（乐观投影的读取优先级；比较式写入器的夹具预置值），内容行 6,206→6,208。
* 本棒复核新发现：`TODO.md` L2 里的克隆目录名被上一棒写成 `E:`＋`0x0C`＋`nAudio-mut-r165`（Python 非 raw 字符串里的 `\f`），与 R164 定案的静默损坏同类；已按字节复原为 `C:\path\to\fnAudio-mut-r165`，复验全文 `0x0C=0`、CR 0、尾 LF✓。

### Hunk 4 · `SOURCE_MANIFEST.sha256`（`git diff --numstat` 实测 `2 1`）

722→**723** 条（＋1＝本轮新 JS 套件入册）；改动两行为 `src/app/ui/app.js` 新前缀 `816c1da093fb33cc` 与新增 `src/tests/test_ui_stop_target_bind.js` 前缀 `0bdd6f79a9a8de37`。逐条对盘复算：**723 条 0 不符、0 缺失、0 重复路径**。清单尾字节疑点定案：工作树 78,314 B／CR=722 对 HEAD blob 77,592 B／CR=0，差值恰 722 行，`core.autocrlf=true` 且 `git diff` 判该文件无改动 ⇒ 检出期换行归一化而非真实漂移，按禁令不改写其换行、不碰 `.gitattributes`。

## 四、复算证据（终版，全部在本轮最后一次改动之后重取）

| 项 | 结果 |
|---|---|
| `node --check` | `src/app/ui/app.js` rc=0 |
| JS 全量 | `cd src` 后 `src/tests` 下 **87** 个 `test_*.js` 逐个 rc=0（含本轮新套件，末行标记逐字 `Stop command target binding regression checks passed.`） |
| 仓库外副本 | `git clone --no-hardlinks` 至 `C:\path\to\fnAudio-mut-r165`，基线 `3989c86`，克隆后 `git remote remove origin`；母本与副本同名文件 sha256 前缀逐一对齐 |
| 控制组 | 副本内本轮套件＋`test_ui_target_switch_teardown.js`＋`test_ui_transport_staleness.js`＋`test_ui_renderer_ownership.js` 全绿 |
| 变异矩阵 | **6/6 全灭**：V1 删闸→①、V2 绑定挪到 await 后→①、V3 改比 `state.playTargetName`→②、V4 基线归零挪到闸前→③、V5 投影挪到闸前→①、V6 删基线归零→②；逐字节还原后复绿 |
| 门禁 | `artifacts/offline-20260923-round260.log`：441,037 B／2,764 内容行／`Ran 2575 tests in 130.970s`／`OK (skipped=2)`／`Ran 2575`@L2654、`OK`@L2656、本轮标记@L2728、无 `Traceback`、无 `FAILED`；同会话双探针 `LASTEXITCODE=0`、`$?=True` |
| 根文档体检 | TODO 内容行 2,187／CHANGELOG 6,803／PROJECT_CONTEXT 6,208；三文件 `0x0C=0`、`NUL=0`、CR=0、尾 LF✓；`R165` 命中行分别为 L2/L117/L168、L2/L3/L4、L2/L3，逐行各 1 枚、新 L2 记录全文件唯一 |
| 符号与母本账 | `app.js` 8,495 内容行；行首锚定 `^(?:async )?function X(` **461** 枚／unique 461（与 HEAD 母本同为 461 ⇒ 本轮修复不新增函数）；Android 已跟踪 `.java` 43 文件／9,695 行 |

## 五、遗留与下一步

盘上 `- [ ]` 现存 **4** 条 @ `:117`、`:168`、`:2054`、`:2076`：前两条是**可排期的深读账**（`:168` 尚余 381−171＝**210** 枚未点名；`:117` 欠读 **18,190** 行＝`app.js` 8,495＋Android `.java` 9,695），后两条属 `## 2026-09-01 持续目标（无需真机）` 段，是**常设口径**（不可勾销）。真机与设备项已全部另册（`docs/REAL_DEVICE_GOALS.md`、`docs/external-acceptance.md`、`docs/REVIEW_ROUND_DISCIPLINE.md`），不计入当前目标。全树 `SPDX-License-Identifier` 头 0 命中一事只登记、不当轮处理。

## 六、同轮收尾（提交与提交后端门禁）

| 项 | 结果 |
|---|---|
| 提交（逐 pathspec，共六笔） | `83716f3` test(guard) → `9c933d2` fix(ui) → `42a024f` docs(round-R165) → `0bd8925` docs(round-review) → `7b0a9dd` chore(manifest) → 本收尾段与 CHANGELOG 收尾行随第六笔；无 `git add -A`、无 push、无 tag；`.gitignore`、`.gitattributes` 未触碰；`artifacts/`、`_external/`、`music/` 未入库 |
| 提交后工作树 | `git status --porcelain -uno` 空；未跟踪面仍是变异副本与构建产物 |
| 提交后端门禁 | `artifacts/offline-20260923-round261.log`：440,921 B、2,762 内容行、`Ran 2575 tests`、`OK (skipped=2)`、无 `Traceback`、无 `FAILED`；同会话双探针 `LASTEXITCODE=0`、`$?=True` |
| 清理 | TEMP 内 r165x_ 与 r165y_ 取证脚本与中间产物、根目录 8 枚取证文件、仓库外变异副本 `C:\path\to\fnAudio-mut-r165`，逐个断言 realpath 后删除，复验 left=0 |
| 收尾后再算 | TODO 内容行 2,187（收尾只在 L2 记录尾追句、不新增行）、CHANGELOG 6,803→6,804、PROJECT_CONTEXT 6,208→6,209；四份文件 0x0C=0、NUL=0、CR=0、尾 LF✓；根目录 .md 不在清单范围内，无需重刷清单 |
