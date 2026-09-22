# fnAudio R156 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮由接管棒在 R155 基线之上完成。下表行号一律为**编辑后**盘上实测 1-based，取数方式写在每节末尾。
凡与历史快照不一致处，只登记不覆盖（见第九节）。

## 文件净增（`git diff --numstat 70604de HEAD`；`70604de` = R155 对照提交 ＝ 本轮基线）

| 文件 | 增 | 删 | 说明 |
| --- | ---: | ---: | --- |
| `src/app/ui/app.js` | 36 | 7 | 入站投送传输行的变更备忘（三 hunk） |
| `src/tests/test_ui_renderer_row_memo.js` | 204 | 0 | 新判别套件，10,946 B，8 组 37 枚断言 |
| `SOURCE_MANIFEST.sha256` | 2 | 1 | 两条摘要改写 ＋ 新增一行（713 → 714 条） |
| `TODO.md` | 3 | 2 | 顶部 R156 记录 1 行 ＋ 两条既有条目的行尾补记 |
| `CHANGELOG_AI.md` | 2 | 0 | R156 修复条 ＋ R156 取证/门禁条 |
| `PROJECT_CONTEXT.md` | 1 | 0 | R156 一条经验 |

取数：`git diff --numstat 70604de HEAD`、`python`（`os.path.getsize`／`sha256`／`split('\n')`）。

## 一、接管取证（磁盘实测，不采信交接快照）

| 项 | 实测值 | 取证方式 |
| --- | --- | --- |
| 工作目录／分支 | `E:/fnAudio` · `main` · 无 remote | `git rev-parse --abbrev-ref HEAD`、`git remote -v` 空 |
| 接管时 HEAD | `040fdf1 docs(round-R156)`（其下 `3220210`、`aa6118b`） | `git log --oneline -6` |
| 未完成态 | `MERGE_HEAD`／`rebase-merge`／`rebase-apply`／`CHERRY_PICK_HEAD` 全部 `False`；`git stash list` 空 | `Test-Path` ＋ `git stash list` |
| 工作树（跟踪文件） | 干净（`git status --porcelain -uno` 无输出）；未跟踪 740 条，本轮一律不动、不提交 | `git status --porcelain -uno` |
| `src/app/ui/app.js` | 412,085 B · 8,454 行 · CR 0 · 无 BOM · 有尾换行 · sha256 `31a9d81291bc…` | Python 字节级 |
| 基线 blob（`70604de`） | 410,254 B · 8,425 行 | `git cat-file blob` |
| 新套件 | 10,946 B · 204 行 · sha256 `b2ba77505914…` · `assert.*` 37 枚 | Python 字节级 ＋ 正则 |
| `SOURCE_MANIFEST.sha256` | 77,421 B · **714 条** · 0 缺文件 · 0 重复路径 · 本体 CRLF · 无 BOM | Python 解析（先剥 `\r`） |
| 逐文件抽查 | `src/app/ui/app.js`、`src/tests/test_ui_renderer_row_memo.js` 均 **MATCH** | 磁盘 sha256 对表 |
| 清单口径 | 只含 `android-client/`（80）＋ `src/`（634）＝ 714；三份根文档与 R155/R156 对照 md 均在口径外 | 解析一级目录计数 |
| 控制组 | `src/tests/test_ui_*.js` 盘上 78 枚，round245 日志内 78 条套件标记全绿 | 见第七节 |
| Python 守卫 | 7 模块 `Ran 66 tests` · `OK` · EXIT 0 | 复跑 |

## 二、缺陷与修法（逐 hunk）

### 2.1 取证：同类缺陷的第二条路径，R99 的口径恰好照不到它

`TODO.md:61` 要求「传输行不得无条件重写」。R99 当年用来结证的取证口径是**数 `textContent =` 直写**。本轮盘上复核该口径仍然成立，也正因此它照不到真正的漏点：

| 量化面 | 现盘实测 | 含义 |
| --- | ---: | --- |
| `app.js` 内 `.textContent =` 赋值 | 81 处 | 历史快照为 79 处（R99），本轮不改写历史数字 |
| 其中经 `setTextContentIfChanged(` 的调用 | 37 处 | 文本面普遍已走比较写入器 |
| 直接写 `$("nowTitle"/"nowArtist"/"nowTime"/"elapsed"/"duration").textContent` | **0 处** | :61 的文本部分确实已落实 |
| 直接写 `$("seek").value`（行 913 / 2158 / 2199 / **2235** / 4492 / 8376） | 6 处 | **`value` 不在这条口径的覆盖范围内** |
| 调 `updateMediaSessionPosition()`（行 2205 / **2244** / 2306 / 2326 / 4719 / 8380 / 8399） | 7 处 | **宿主调用同样不在这条口径的覆盖范围内** |

两条通道本就该对称，而盘上只有一条有备忘：

| 通道 | 函数（def 行号） | 备忘 | 比较点 | 本轮前状态 |
| --- | --- | --- | --- | --- |
| 出站（本机控制远端） | `updateRemoteUi` :2177-2206 | `state.remoteUiLast`（声明 :215、:297；读写 :2189、:2194） | :2192-2193，含 0.45 s 容差 | 自 R99 起有门 |
| 入站（远端推流到本机） | `updateIncomingRendererUi` :2207-2246 | **无** | **无** | 每拍裸写 |

节拍由 `src/app/ui/ui_sync_scheduler.js`（67 行）给出：:49 `every(1500, … refreshRendererSession)`、:52 `every(500, … updateRemoteUi)`，而 :52 的门是 `isRemoteTarget() || isIncomingRendererSession()` —— 入站投送也被这条 500 ms tick 驱动；`app.js` :2183 又把整行交给入站函数。叠加 :1989 的 1.5 s 渲染路径，被暂停／证据冻结的投送仍以**约每秒 2 次**重写 `$("seek").value` 并每拍调宿主 `setPositionState()`；`transportExtrapolation` 在非 PLAYING 时返回 0，所以每次写入的值完全相同。

结论：属 `TODO.md:61` 同一类缺陷的第二条路径，**并入既有条目，不另立新项**。该缺陷自 R99 起又活了 57 轮。

### 2.2 修法（`git diff 70604de HEAD -- src/app/ui/app.js` 原文）

```diff
diff --git a/src/app/ui/app.js b/src/app/ui/app.js
index f0e3270..dd0b36b 100644
--- a/src/app/ui/app.js
+++ b/src/app/ui/app.js
@@ -293,6 +293,10 @@ state.deviceSwitchInFlight = false;
 state.deviceTargetRevision = 0;
 state.rendererSession = null;
 state.rendererSnapshotAt = 0;
+// The last render evidence this browser painted into the transport row.
+// The outbound channel has `remoteUiLast` for the same job; the inbound one
+// had none, and that asymmetry is what this memo closes (R156).
+state.rendererUiLast = null;
 // The uri of a cast this browser stopped with a local play intent (TODO.md:72
 // ruling D-2). The status poll would otherwise hand the row straight back to it.
 state.rendererPreemptedUri = "";
@@ -1998,9 +2002,11 @@ function resetTransportRow() {
   if (rail) rail.value = 0;
   updateSeekRail(0);
   setPlayButton(false);
-  // The memo that keeps `updateRemoteUi` from repainting describes the session that just ended,
-  // so it has to go with the row it was guarding.
+  // The memos that keep `updateRemoteUi` and `updateIncomingRendererUi` from
+  // repainting describe the session that just ended, so they have to go with the
+  // row they were guarding.
   state.remoteUiLast = null;
+  state.rendererUiLast = null;
 }
 function restoreLibraryNowPlaying() {
   const item = currentItem();
@@ -2199,20 +2205,43 @@ function updateRemoteUi() {
   updateMediaSessionPosition();
 }
 function updateIncomingRendererUi() {
-  if (!isIncomingRendererSession()) return false;
+  if (!isIncomingRendererSession()) {
+    // Self-healing: this memo describes the cast that just ended, so it must not
+    // survive to suppress the first paint of the next one.
+    state.rendererUiLast = null;
+    return false;
+  }
   const session = state.rendererSession;
+  const transport = String(session.transport || "").toUpperCase();
   const duration = seekDuration();
+  const seconds = duration > 0 && !state.seeking ? currentSeconds() : -1;
+  const previous = state.rendererUiLast || {};
+  // Exact equality on purpose. `updateRemoteUi` can afford a 0.45s tolerance because it
+  // only ticks while this app owns the target; this channel is repainted every 500ms
+  // (`ui_sync_scheduler.js`) and re-extrapolates its position between polls, so any
+  // tolerance would freeze a rail that is legitimately advancing. Equal values therefore
+  // mean the status poll brought no new evidence -- the one case in which neither the
+  // slider nor the host media session has anything to learn. While the caster is paused
+  // `transportExtrapolation` returns 0, so before this gate a frozen cast was rewritten
+  // about twice a second forever (TODO.md:61 class, R156).
+  const unchanged = previous.uri === session.uri && previous.transport === transport
+    && previous.duration === duration && previous.seconds === seconds;
+  if (!unchanged) state.rendererUiLast = { uri: session.uri, transport, duration, seconds };
   if (duration > 0) {
     setTextContentIfChanged($("duration"), clock(duration));
     if (!state.seeking) {
-      const seconds = currentSeconds();
       setTextContentIfChanged($("elapsed"), clock(seconds));
-      $("seek").value = Math.max(0, Math.min(100, seconds / duration * 100));
+      if (!unchanged) {
+        $("seek").value = Math.max(0, Math.min(100, seconds / duration * 100));
+      }
     }
   }
-  setPlayButton(String(session.transport || "").toUpperCase() === "PLAYING");
+  // Deliberately not gated: `syncPlayerProgress` owns `updateTransportStateUnknown`,
+  // which flips on wall-clock staleness while every value above stays identical. The
+  // compare-first writers below are already free when nothing changed.
+  setPlayButton(transport === "PLAYING");
   syncPlayerProgress();
-  updateMediaSessionPosition();
+  if (!unchanged) updateMediaSessionPosition();
   return true;
 }
 async function controlIncomingRenderer(action, position = null) {
```

### 2.3 两处刻意的设计取舍（不是漏改）

- **精确相等，不用容差**（:2227-2228）：出站只在「本机拥有该目标」时推进，可承受 0.45 s 容差；入站每 500 ms 重画且两次轮询之间会重新外推位置，任何容差都会把合法推进的进度条冻住。M6 用 1.5 s 容差做变异，被组 2 的断言当场打死。四个比较量取自 :2215-2217（`uri`／`transport`／`duration`／`seconds`），备忘只在变化时落盘（:2229）。
- **`setPlayButton` 与 `syncPlayerProgress` 不加门**（:2239-2243）：`updateTransportStateUnknown()` 挂在 `syncPlayerProgress` 一侧，按墙钟陈旧度翻转，而上面四个值可以长时间全等 —— 给它们加门会把「状态未知」灯打死。M3 正是这条反证。且 `setPlayButton` 自带 `dataset.playing` 比较、`setTextContentIfChanged` 自带比较，无变化时本就不写 DOM，省下的写入是 0。
- **早退分支先清备忘**（:2208-2212）：备忘描述的是刚结束那次投送，留着它会吞掉下一次投送的第一帧。M4 删掉这行自愈即红。
- **`resetTransportRow` 一并清空两条备忘**（:2008-2009）：复位传输行时把两条通道的备忘随行一起丢弃。M5 只清旧备忘即红。

## 三、判别测试（`src/tests/test_ui_renderer_row_memo.js`，8 组 37 枚断言）

套件用 `vm.runInNewContext` 真跑函数源码，假节点除 text／html／style 外**额外统计 `value` 的写次数**，并统计宿主 `setPositionState` 的调用次数 —— 这正是 R99 口径漏掉的两类写入。

| 组 | 起始行 | 断言 | 判别点 |
| --- | ---: | ---: | --- |
| 1 | :91 | 4 | 缺陷本身：冻结的投送连续 6 拍后，传输行一次都不许再被碰 |
| 2 | :103 | 3 | 控制组：证据在推进时必须每拍重画，防止「靠不写来通过」 |
| 3 | :112 | 3 | 传输态变了但位置没变 → 必须重画（备忘不能只看时间） |
| 4 | :127 | 6 | 自愈：投送结束后备忘不得活到下一次投送 |
| 5 | :142 | 2 | 用户拖动（`state.seeking`）期间不盖章，松手后恢复 |
| 6 | :156 | 4 | 被抑制的那一拍里，陈旧灯仍须点亮（防 M3 式回归） |
| 7 | :174 | 3 | `resetTransportRow` 同时丢弃两条备忘 |
| 8 | :185 | 10 | 源码级接线断言：门与备忘必须留在被验证的那两处，不得被搬走 |

组 1 的判别性是本轮的「先红」依据：基线 blob ＋ 本套件 ⇒ `12 !== 6`（六拍 × 每次 2 类写入）。

## 四、并入既有条目的缺陷（不另立新项）

| 归属 | 条目 | 本轮关系 |
| --- | --- | --- |
| 并入 | `TODO.md:61`（传输行不得无条件重写） | 本轮补上它照不到的 `value` 写入与宿主调用两面，属同一条目的第二条路径 |
| 相邻 | `TODO.md:58`（投送残留数字） | R99 的 `resetTransportRow` 是本轮组 7 的前提，未重复改动 |
| 未动 | `TODO.md:108`、`TODO.md:159` | 两条取证门，本轮只推进量化面（见第八节），不构成关闭条件 |

本轮**净关闭 0 条**：盘上仅剩的两枚代码待办（:108 欠读 18,149 行、:159 深读 78/381）都属于「读完才可关闭」的取证门，不存在可提前关闭的缺陷。收益记在量化面上：:159 的深读面本轮新增 `updateIncomingRendererUi` 一条通道（含 `transportExtrapolation`、`seekDuration`、`currentSeconds`、`updateMediaSessionPosition` 四个相邻符号），:108 的 `src/app/ui` 面按盘上行数复核后仍为 18,149 行。新立 0 条。

## 五、仓库外副本变异证明（7 格，控制组先绿）

克隆：`git clone` 到 `E:/temp/r156/clone`，HEAD 钉 `70604de`（＝ 本轮基线），工作树内 `src/app/ui/app.js` 替换为本轮补丁态。
**关键坑（已复现）**：变异脚本的 `BASE` 必须写死 `70604de:src/app/ui/app.js`；写 `HEAD` 在提交之后会把「回退到基线」这一格误判成幸存。

| 格 | 变异 | 首条失败断言 | 结果 |
| --- | --- | --- | --- |
| 控制组 | 未变异（补丁态） | — | RC 0 · `Incoming render transport-row memo checks passed.` |
| M1 | :2229 备忘永不落盘 | 组 1「六拍冻结不得触碰传输行」 | KILLED（RC 1） |
| M2 | :2227 `unchanged` 恒为 `false` | 组 1 同上 | KILLED（RC 1） |
| M3 | 连 `syncPlayerProgress()` 一起加门 | 组 6「证据耗尽时灯仍亮」 | KILLED（RC 1） |
| M4 | 删 :2211 早退自愈 | 组 4「投送结束后备忘被清除」 | KILLED（RC 1） |
| M5 | :2009 不清新备忘 | 组 7「备忘随行复位一同丢弃」 | KILLED（RC 1） |
| M6 | 改用 1.5 s 容差比较 | 组 2「合法推进必须每拍重画」 | KILLED（RC 1） |
| M7 | `app.js` 整体回退基线 | 组 1 同上 | KILLED（RC 1） |

跑完还原：补丁态字节 sha 与跑前一致（`restored True`）。控制组另跑 `test_ui_transport_state_unknown.js`、`test_ui_android_bridge.js` 均 RC 0。

## 六、当轮证伪（不得记作发现）

| 怀疑 | 证伪方式 | 结论 |
| --- | --- | --- |
| 「:61 早已关好，本轮是重复劳动」 | 盘上数 `$("seek").value` 与 `updateMediaSessionPosition()` 两类写入点（6／7 处），而 `textContent` 直写为 0 | 不成立：:61 的口径本身有盲区，本轮是同一条目的另一半 |
| 「给 `setPlayButton` 也加门更省」 | 读 :2242 上游 `syncPlayerProgress` → `updateTransportStateUnknown` 依赖墙钟；M3 实证 | 不成立：加了会把陈旧灯打死，且省下 0 次写入 |
| 「入站也该用出站的 0.45 s 容差保持一致」 | M6 实证 | 不成立：入站每拍重新外推，任何容差都会冻住合法推进 |
| 「注释里写的 1.5 s／:2043／:4375 说明代码有错」 | 读 `ui_sync_scheduler.js` :49/:52 与 `app.js` :1989/:2183 实测节拍；查 :2043、:4375 现盘内容 | 代码行为正确，**是注释漂移**，纯注释问题，本轮只登记未改（见第九节） |

## 七、记账与门禁

| 笔次 | 短哈希 | 内容 |
| --- | --- | --- |
| 1 | `aa6118b` | `fix(ui): 投送传输行变更备忘（R156）` —— `app.js` ＋ 新套件 |
| 2 | `3220210` | `chore(manifest): R156 刷新 SOURCE_MANIFEST.sha256`（714 条） |
| 3 | `040fdf1` | `docs(round-R156)` —— TODO／CHANGELOG／CONTEXT（曾订正插入位置后 amend，见第九节） |
| 4 | 本笔 | `docs(round-review): R156 逐 hunk 审查对照与变异矩阵`（即本文件） |

离线门禁 `tools/test_offline.ps1` 本轮跑了四次：

| 轮次 | 日志字节 | 行数 | Python | JS 套件标记 | 退出码 |
| --- | ---: | ---: | --- | ---: | --- |
| round242 | 436,324 | 2,720 | `Ran 2559 in 123.630s` · `OK (skipped=2)` | 78 | ⚠ 捕获失效（0 字节） |
| round243 | 436,324 | 2,720 | `Ran 2559 in 121.461s` · `OK (skipped=2)` | 78 | ⚠ 捕获失效（0 字节） |
| round244 | 436,209 | 2,719 | `Ran 2559 in 121.065s` · `OK (skipped=2)` | 78 | ⚠ 捕获失效（0 字节） |
| **round245** | 436,209 | 2,719 | `Ran 2559 in 120.217s` · `OK (skipped=2)` | **78** | **`EXITCODE=0`（Python 驱动捕获）** |

**退出码捕获失效（本轮新发现，必须如实登记）**：旧驱动 `r156_gateNNN.cmd` 末行 `echo %ERRORLEVEL%> "file"` 在本机 cmd 下写出 0 字节文件 —— 已在 `E:/temp/r156_echo_test/t_a.cmd` 用 `powershell -Command "exit 3"` 复现（结果文件 0 字节、控制台漏出 `EXIT=`）。因此 round242/243/244 的退出码**没有可靠出处，不得引用**；本轮改用确定性 Python 驱动（`subprocess.run` 起门禁，退出后立即写码），round245 取得 `EXITCODE=0`。

日志差异面：244/245 相对 242/243 少 1 行，是 `test_offline.ps1` 末段 `git diff --check` 打印的 `SOURCE_MANIFEST.sha256` CRLF 警告 —— manifest 提交后该行消失，恰好反证 244/245 是「全提交后终态」。四份日志内均无 `FAILED`、无 `Traceback`，新套件标记 `Incoming render transport-row memo checks passed.` 自 round242 起在场（round240/241 为 0 次，套件尚不存在）。
门禁产物（`artifacts/roundNNN*`、`*.exit*`）一律不入库；本文件亦不在清单口径内，故**无需**再刷 `SOURCE_MANIFEST.sha256`。

## 八、终止条件进度（成立 1/4，禁止自称完成）

| 条件 | 状态 | 盘上依据 |
| --- | --- | --- |
| (1) 可离线验证的代码侧待办清空 | ✗ | `TODO.md` 行首锚定 `- [ ]` 共 **15** 条 ＝ 代码桶 **2**（:108、:159，均为取证门）＋ 长期观察 **13** |
| (2) 设备／外部项移出逐轮任务 | ✗ | `docs/external-acceptance.md` 行首锚定开放 **28**、收口 **17**（宽松口径 29／18，多出的一处在 :13 的说明行里） |
| (3) 需产品决策项汇总征询 | ✓ | 决策段开放 **0** 条，已一次性摊开并获裁定 |
| (4) 终止前跑完整离线门禁 | ✗ | 依 N3=A，终局门禁只在负责人显发终止令时跑；round242–245 属轮内门禁 |

**三口径并存（禁止合并、禁止改写历史）**：旧目标正文 `155 = 64 + 82 + 9` · R99 实测 `115 = 51 + 43 + 8 + 13` · 现盘锚定口径 `15 = 2 + 13`。三者是不同时点、不同计数口径的产物，历史两处数字本轮原样保留。
`TODO.md` 宽松 `- [ ]` 18 处 = 锚定 15 处 + 行文内引用 3 处（:6 两处、:2035 一处），后者不计入待办；`- [x]` 锚定 1,499、宽松 1,500，差集唯一命中 :694 的缩进项。

## 九、提交前复审与更正清单（逐条「原表述 → 现盘实测 → 处置」）

1. **三份根文档插入位置** → 第 3 笔提交最初把 R156 记录插在 R155 之下，违反「最新在前」→ 现盘实测 TODO R156 在 L2、CHANGELOG R156 在 L2–L3、CONTEXT R156 在 L2（R155 依次后移）→ 已订正后复跑守卫（66 项 OK）再 `amend`。**教训：记录类提交前必须先定位既有同级条目的实际行号，不能按轮次顺序追加。**
2. **变异脚本的 `BASE`** → 最初写 `HEAD:src/app/ui/app.js` → 提交后 M7 会「假判幸存」→ 已钉死 `70604de`，本轮五、六节结论均出自钉死后的复跑。
3. **门禁退出码** → 旧说法「round243 EXITCODE=0」→ 现盘实测该文件不存在、round242/244 的退出码文件均为 0 字节 → 根因为 cmd `echo %ERRORLEVEL%>` 写法，已复现并改 Python 驱动，**以 round245 为准**。
4. **注释漂移（本轮登记未改）** → `app.js` :1986-1988 把 500 ms 通道写成「this 1.5s status poll」；:1997 引用的 `:2043`、`:4375` 在现盘分别是 `controlIncomingRenderer` 的 `apiFetch` 收尾与 `playAll` 的 `return`；真正的停止路径在 :2156-:2158、新载入路径在 :4490-:4492（均已下移约 113 行） → 纯注释问题，不影响行为，**建议单独一轮修注释并加一条源码级断言防回归**（待裁定）。
5. **环境事实（建议写入 `docs/REVIEW_ROUND_DISCIPLINE.md`）** → JS 套件 `cwd` 必须是 `E:/fnAudio/src`（在 `src/tests` 下跑会出 53 枚假 ENOENT）；`SOURCE_MANIFEST.sha256` 本体为 CRLF，解析须先剥 `\r`；门禁退出码必须用 Python 驱动捕获。
