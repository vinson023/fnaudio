# fnAudio R166 修改审查对照

## 一、本轮一句话结论

读完 `src/app/ui/app.js`「歌词面板高亮投影／歌词状态词汇」面 15 枚命名函数、其中首次点名 8 枚（深读分子 171 → 179）；在同一轮内抓到并修掉这一面的三处缺陷——**A** 高亮投影没有自身输出的记忆、**B** 扫描器缺「还没有行」这个状态、**C** 元数据预取通道私造第六个状态词并附带一处可见性判断。判别测试为新建的 12 用例套件，外加改写 `test_ui_lyrics_priority.js` 里那枚**把缺陷 C 钉成契约**的旧断言。本轮净关闭代码待办 0 条、新立 0 条（口径＝Q2=A／X3=A＋C：以生产码缺陷关闭与欠读面下降记账）。

## 二、缺陷定位（本轮要修的真东西）

| # | 缺陷 | 盘上证据（HEAD＝修改前母本 `b5adecc`；现盘＝工作树） |
|---|---|---|
| A | `updateLyricHighlight` 有 5 枚调用点，其中 3 枚是轮询面（宿主状态回调、投送界面刷新、audio `timeupdate` 约每秒 4 次），而当前歌词行每几秒才移动一次。投影**不记得自己上一次画了哪一行**，于是每个 tick 重扫全部 `[data-lyric]` 节点、每 tick 重发一次 `scrollTo({behavior:"smooth"})`：动画永不收敛，面板反复把读者拽回当前行 | HEAD `:917`／`:2237`／`:4791`／`:8420` 四处入口；现盘 5 枚调用点 `:923`／`:2243`／`:4800`／`:5358`／`:8455`。与 R99 关闭的 `:58`「投送残留数字」、`:61`「无条件重写」同族——都是轮询面缺比较 |
| B | 扫描起算值是 `let active = 0`，把「还没有到期行」和「第 1 行正在唱」合并成同一个值。`parseLyrics` 委托 `src/app/ui/lyrics_parse_policy.js`（672 B）给无时间戳行返回 `time: -1` 且升序排序 ⇒ **纯文本歌词的第 1 行永远坐 0 号位被宣告正在唱**；有 LRC 时前奏段同样被硬指派第 1 行 | HEAD `:5340`；现盘 `:5367` 起算 −1、`:5379` 无到期 cue 早退（连节点都不向文档索取） |
| C | 预取通道写 `state.lyricsStatus = "ready"`，而复用闸只认 `loading/loaded/pending`，全文件合法词汇为 `idle/loading/pending/error/loaded` 五词 ⇒ 缓存判定**恒为未命中**：每次重开抹掉已渲染面板、越过 10,000 ms 超时向 provider 重发同一请求。紧邻的 `if (!$("lyricsView")?.hidden) renderLyrics(...)` 是同一根因的另一半：隐藏时 `state.lyrics` 成为 DOM 从未收到的正文，复用判定连可信前提都没有 | HEAD `:5091`（第六词）＋ HEAD `:5092`（可见性判断）；现盘 `:5111-:5112` 折回唯一重绘通道；`:4907`（可见加载器的既有不变量）与 `:5111` 现在成对。第六词赋值现盘归零 |

当轮证伪并登记为不改动（避免下一轮重复劳动）：`closeLyrics`（HEAD `:8197`／现盘 `:8232`）不触碰歌词节点，关闭面板期间「节点 class 与记忆失真」只在行号变化时发生，而那时记忆值本身已变，故「重开时不写失效」与不写**等价**——这是本轮不设第 9 格变异的裁定依据。

## 三、逐 hunk 改动

### Hunk 1 · `src/app/ui/app.js`（`git diff --numstat` 实测 `39 4`＝净增 35 行：说明注释 30＋代码净 5；8 个 hunk）

```
 state.lyricsPollAttempts = 0;
+state.lyricsActiveLine = null;                    // A：投影对自身输出的记忆（现盘 :123，含 5 行注释 :118-:123）

 function renderLyrics(lines) {                    // 现盘 :4792
   state.lyrics = lines;
+  state.lyricsActiveLine = null;                  //   节点整体重建 ⇒ 记忆随之作废（:4796）
 function showLyricsMessage(message) {             // 现盘 :4802
   state.lyrics = [];
+  state.lyricsActiveLine = null;                  //   同上（:4806）

           if (lyrics) {
-            state.lyrics = parseLyrics(lyrics);
-            state.lyricsStatus = "ready";                              // C 第六词
-            if (!$('lyricsView')?.hidden) renderLyrics(state.lyrics);   // C 可见性判断
+            state.lyricsStatus = "loaded";                              // 现盘 :5111
+            renderLyrics(parseLyrics(lyrics));                           // 现盘 :5112

 async function openLyrics() {                     // 现盘 :5346
   await loadLyricsForCurrentTrack(item, retry, state.lyricsStatus === "error");
+  updateLyricHighlight();                          // 复用命中路径唯一的投影（:5358）

 function updateLyricHighlight() {                  // 现盘 :5360
-  let active = 0;
+  let active = -1;                                 // B：「还没有行」成为可表达的状态（:5367）
   state.lyrics.forEach(...);
+  if (active === state.lyricsActiveLine) return;   // A：比较后落笔（:5376-:5377）
+  state.lyricsActiveLine = active;
   document.querySelectorAll("[data-lyric]")...
+  if (active < 0) return;                          // B：无到期 cue 时连 activeNode 都不查（:5379）
```

四处落笔的**先后顺序**本身即被钉住的语义：`if (active < 0) return;` 若在 class 切换之前，纯文本歌词的旧标记会残留在屏上；若在记忆赋值之前，一次「无行」就不会被记住，早退也就省不掉那趟重扫。

### Hunk 2 · 新守卫 `src/tests/test_ui_lyrics_highlight_projection.js`（320 内容行／15,861 B／CR 0／尾 LF✓／sha256 前缀 `05e89635f65041ee`／标记 `Lyric highlight projection regression checks passed.`）

在 `vm.runInNewContext` 里跑**真实**的 `updateLyricHighlight`、`renderLyrics`、`showLyricsMessage`、`openLyrics`、`parseLyrics`、`closeLyrics` 与预取通道回写分支，夹具为假节点并逐次统计其写入次数——因此「没写」与「写了同一个值」可判别，「最终像素相同」不构成通过理由。

| 用例 | 断言 | 钉住 |
|---|---|---|
| 1 | 前奏 5 s 而首个 cue 在 12 s 时，不得标记任何行 | B |
| 2 | 无时间戳歌词在任何时刻都没有当前行 | B（纯文本） |
| 3 | 到期 cue 恰好投影一次 | 修复未过矫 |
| 4 | 三个轮询入口在行号未变时零重扫 | A |
| 5 | 真实前进时旧行取消标记、新行标记 | A 不吞真变化 |
| 6 | 重建节点即作废记忆（以写入次数判别，非以字段空值判别） | A 的安全性前提 |
| 7 | 消息路径同样作废记忆 | A（`:4806`） |
| 8 | 关闭的面板从不投影，记忆不得成为唤起的理由 | A 与可见性解耦 |
| 9 | 重开已持有本曲歌词的面板必须复用 | C |
| 10 | 取消隐藏是唯一记忆看不见的转变，须由重开投影补上 | C（`:5358`） |
| 11 | 控制用例：复用闸按词汇判定——这正是第六词致命的原因 | C 的因果 |
| 12 | 源码级契约：状态词表闭合、每处 `loaded` 声明与一次重绘成对、投影入口恰 5 枚 | A/B/C 不回归 |

用例 12 末段（现盘 `:311-:314`）的 `updateLyricHighlight();` 计数断言写作「恰 5 枚」，与 Hunk 1 新增的第 5 枚入口互为锁扣：将来任何一方增减入口都会同时打挂这份账。

**改写** `src/tests/test_ui_lyrics_priority.js` 第 44 行（`git diff --numstat` 实测 `8 1`；套件 11,028 B／前缀 `6f2d842340202e34`）：旧断言 `if (!$("lyricsView")?.hidden) renderLyrics(state.lyrics)` 把缺陷 C 的形状钉成契约。新三条＝解析结果必须交给唯一重绘通道 ＋ 两种旧形状 `doesNotMatch` 禁止回归。

### Hunk 3 · 三份根文档（最新在前；桶计数一律未改动）

| 文档 | 写入前内容行 | 写入后 | 落点 |
|---|---|---|---|
| `TODO.md` | 2,187 | **2,188** | L2 本轮记录；`:118` 欠读总量重测追加（不勾销）；`:169` 本标读毕登记（分子 171→179、0 点名 183→175） |
| `CHANGELOG_AI.md` | 6,804 | **6,807** | 顶部 prepend 3 条：变异矩阵／判别套件与断言修正／红证·生产码修复·绿证 |
| `PROJECT_CONTEXT.md` | 6,209 | **6,212** | 顶部 prepend 3 条判据（状态词汇表须闭合、轮询投影须有自身记忆、行号与码点须锚现盘复算） |

写入用脚本内置硬断言前置：写入前 0 点名 `== 183`、`todo[1]`／`chg[1]` 均以 `R165` 开头、三文档 `0x0C`／NUL／CR 均为 0 且尾 LF；勾选项 `- [ ] ` 写入后仍恰 4 枚（`:118`／`:169`／`:2055`／`:2077`）。

### Hunk 4 · `SOURCE_MANIFEST.sha256`（`git diff --numstat` 实测 `3 2`，724 行／78,535 B）

工作树整份 CRLF 而 HEAD 为 LF，属 `core.autocrlf` 归一化，**不得改写**；门禁内建守卫 `test_root_manifest_matches_authoritative_source_tree`、`test_the_real_manifest_and_the_real_tree_agree_right_now` 本轮均 ok。根目录 `fnAudio-R1xx-修改审查对照.md` 系列不在清单覆盖面（清单内 `.md` 恰 3 条，均在子目录），故本文档的写入不影响清单账。

## 四、复算证据（终版，全部在本轮最后一次改动之后重取）

| 项 | 实测 |
|---|---|
| `src/app/ui/app.js` | 418,004 B／8,530 内容行（HEAD 8,495，＋35）／CR 0／FF 0／NUL 0／尾 LF✓／sha256 前缀 `c70277ca567c840b`／`node --check` rc=0 |
| 行首锚定命名函数 | 461 枚／unique 461（本轮不新增函数，只新增 1 枚状态字段与 2 处提前返回） |
| 投影入口 | 现盘恰 5 枚：`:923`、`:2243`、`:4800`、`:5358`、`:8455` |
| 歌词状态词赋值 | 现盘 10 处（`:112`、`:4835` idle／`:4853` loading／`:4896` pending／`:4902`、`:4914` error／`:4907`、`:5111` loaded），第六词 `ready` 赋值 0 处 |
| 0 点名符号账 | 写入前 183 → 写入后 **175**（−8＝本面首次点名 8 枚），翻转集合逐枚核对恰为 `cancelLyricsPoll`、`cancelLyricsRequest`、`closeLyrics`、`openLyrics`、`parseLyrics`、`showLyricsMessage`、`syncLyricsForCurrentTrack`、`updateLyricHighlight`，本轮记录未附带点名其它 0 命中符号 |
| 红证原文 | `AssertionError [ERR_ASSERTION]: no cue is due at 5 s of a lyric whose first cue is at 12 s, so nothing may be marked active` |
| 变异矩阵 | 仓库外副本 `C:\path\to\fnAudio-mut-r166`（基线 `b5adecc`，克隆后 `git remote remove origin`）：控制组两套先绿 rc=0；V1–V8 **8/8 全灭**，每格被不同断言抓住（V4、V5 同时打挂 priority 套件的禁止回归断言）；还原后控制组复绿 rc=0。矩阵按两项卫生修正后的最终字节复跑，修正前旧结果留档 `r166_mut_pre.txt`，两轮结论一致 |
| JS 侧 | `src/tests` 下 88 枚 `test_*.js` 逐个跑：ran=88／failed=0 |
| Python 守卫 | `test_change_record`＋`test_decision_bucket_ledger`＋`test_source_manifest` 合跑 Ran 18 tests OK |
| 本轮终跑门禁 | `artifacts/offline-20260923-round262.log`：`Ran 2575 tests in 129.687s`、`OK (skipped=2)`，无 `Traceback`、无 `FAILED`；JS 段 82 枚 `passed.` 标记（上一轮 81，＋1 即本轮新套件），新套件标记位于该 log 第 2,706 行 |
| 卫生修正 2 处 | 新套件头注释把入口写成 `app.js:8459`，按现盘订正为 `:8455`（「行号必须锚现盘」第三次复发）；`CHANGELOG_AI.md` 中上一棒 R165 收尾行的 「0 不」 之后一字 系静默损坏码点 U+7B21（应为 U+7B26），按码点复原为 `0 不符`，全文该码点计数 1→0 |

## 五、遗留与下一步

1. **代码桶仍为 4 条**，其中 `:2055`／`:2077` 两条为常设守卫项（判据达成前不勾销）；真正可关闭的欠读债仍只有 `:118`（欠读清单）与 `:169`（符号账）两条。
2. **符号账**：179／381，余 202 枚。近 8 轮每轮首次点名 3–9 枚 ⇒ 约 23–50 轮读完；`app.js` 按符号口径已读约 33%。行账 18,225＝`app.js` 8,530 ＋ 已跟踪 Android `.java` 43 文件 9,695（本棒复算逐字相符）；Android 面尚未进入点名口径。
3. **下一段候选**：「歌词轮询与重试预算面」——`scheduleLyricsPoll` 一族与运行期预算输入；其宿主与输入函数在基线三份根文档仍为 0 点名，登记时须按坐标定位、不得提前点名。
4. 真机验证项一律不在本轮账内，另册见 `docs/REAL_DEVICE_GOALS.md` 与 `docs/external-acceptance.md`。
