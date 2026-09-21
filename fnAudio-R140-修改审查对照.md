# fnAudio R140 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮 3 个源/测试文件改动：`src/app/ui/index.html` **+5 −5**（5 行上补 8 个属性，行数不变），新增 `src/tests/test_ui_control_names.js` 142 行，`src/tests/test_library_sqlite.py` **+11 −3（净 +8）**（修一处既有搜索用例的夹具偶发红，**未碰任何产品码**）；另 1 份清单（707 → 708 条）与 2 份根文档的追加记录。`TODO.md` 只更新 L99 台账与本轮记录，**净关闭 0 条、新立 0 条**。对照 md 按裁定 Q5=B 以独立 pathspec 入库。

| # | 文件 | 净增 | 性质 |
|---|---|---|---|
| 1 | src/app/ui/index.html | +5 −5 | 5 个控件补可访问名（2 个 `aria-label` + 3 组 `aria-labelledby`/`id`） |
| 2 | src/tests/test_ui_control_names.js | +142 −0 | 判别测试：79 控件全有名 + 5 处逐字钉死 + 3 枚形状守卫 |
| 3 | src/tests/test_library_sqlite.py | +11 −3（净 +8） | 修既有搜索用例的夹具卫生：ASCII 短词撞随机临时目录名 ⇒ 约 1/200 偶发红 |
| 4 | SOURCE_MANIFEST.sha256 | 708 条 | 新增 1 个测试文件，逐文件 sha 已抽查 |
| 5 | TODO.md | L99 台账 + 本轮记录 | `index.html` 184 行转「已读出局」；数字漂移按现树重算 |
| 6 | CHANGELOG_AI.md / PROJECT_CONTEXT.md | 各 L2 插行 | 最新在前，尾部空行未动 |

---

## H1 `C:\path\to\fnAudio\src\app\ui\index.html` L70 — 进度条没有任何可访问名
```
- <input id="seek" type="range" min="0" max="100" value="0">
+ <input id="seek" type="range" min="0" max="100" value="0" aria-label="播放进度">
```
同处一行内已有 `#elapsed`、`#transportStateUnknown`、`#duration` 三个 `<span>`，但没有一个与 `#seek` 建立命名关系（全文 `label for` = 0、`aria-labelledby` 引用 = 0）。读屏软件落到这个滑块上只会念出「滑块 0 到 100」，说不出它在控制什么。

## H2 `C:\path\to\fnAudio\src\app\ui\index.html` L71 — 音量滑条同样裸奔
```
- <input id="volume" class="volume-slider" type="range" min="0" max="1" step="0.01" value="0.85">
+ <input id="volume" class="volume-slider" type="range" min="0" max="1" step="0.01" value="0.85" aria-label="音量">
```
注意 L71 上另有一个 `#volumeBtn`，它本来就带 `aria-label="音量"`；本轮**只**给 `#volume` 补名，替换用整枚 `<input>` 全文 needle（`assert count==1`）而非 `aria-label="音量"` 子串，后者全文出现 2 次，误用会连带改到 `#volumeBtn`。

## H3/H4/H5 `C:\path\to\fnAudio\src\app\ui\index.html` L94 / L96 / L98 — 三枚分享开关
```
- <div><strong>到期时间</strong><span id="shareExpirySummary">链接永久有效</span></div><label class="switch-control"><input id="shareExpiryEnabled" type="checkbox"><span></span></label>
+ <div><strong id="shareExpiryLabel">到期时间</strong><span id="shareExpirySummary">链接永久有效</span></div><label class="switch-control"><input id="shareExpiryEnabled" type="checkbox" aria-labelledby="shareExpiryLabel"><span></span></label>
```
（`密码`/`sharePasswordLabel`、`可访问次数`/`shareAccessLabel` 两行同形，不再重复贴。）

- **为什么不能往 `<label>` 里塞文字**：`app.css` 的 `.switch-control input{position:absolute;opacity:0;pointer-events:none}` 把真实控件整个隐形，开关外观完全由 `.switch-control span`（`position:absolute;inset:0`）加 `span::after` 画的滑块呈现。往那个空 `<span>` 填文案，视觉上会盖住开关，等于用一个可访问性问题换一个渲染故障。
- **为什么用 `aria-labelledby` 而不是 `aria-label`**：这一行的可见标题 `<strong>` 就是 sighted 用户读到的名字。用 `labelledby` 指过去，文案只有一个主人；用 `aria-label` 复制一份字符串，两处就会各自漂移（三行 detail 里 `#shareExpiryInput`、`#sharePasswordInput`、`#shareAccessInput` 已经各自带 `aria-label`，与本轮 3 枚开关不冲突，未动）。

## 已证伪，未改
- `#nowPlayingSummary`（L68）键盘可达性：`app.js` L8165-8169 已在 `onkeydown` 里处理 Enter/Space 并 `preventDefault`，且它是全文唯一 `tabindex="0"`。记「证伪」，不记「发现」。
- `lyrics-meta-artist`（L79 那枚 `<span id="lyricsMetaArtist">`）是死样式钩子：`app.css` 中作为选择器命中 **0**，而同族 `.lyrics-meta` 有 23 条、兄弟 `.lyrics-meta-album` 有 2 条 —— 同一行三格里只有歌手这格从来没被样式覆盖过；ui 目录下 60 个 .js 里也全部 0 命中，既不渲染也不被脚本读写。属死钩子而非缺陷，**不为清库存改动 UI**。
- `single`（L87 `class="path-entry single"`）同样：`app.css` 中 `.single` 选择器命中 **0**，全文仅有的 2 处 "single" 字样都落在注释里（L272、L576）；ui .js 中仅 `lru_cache.js` L54 一处注释。登记，不改。

## H6 `C:\path\to\fnAudio\src\tests\test_library_sqlite.py` L3234–L3261 — 一处既有搜索用例的偶发红

```
-                self._item("hit", os.path.join(music_root, "Ab", "Cd", "hit.flac"), "hi there", 1),
+        search = "唱"
             music_root = os.path.join(root, "music")
+            self.assertNotIn(search.lower(), music_root.lower())
+                self._item("hit", os.path.join(music_root, "Ab", "Cd", "hit.flac"), "hi there " + search, 1),
-            page = query_library_folders(config, "", music_root, "asc", 20, 0, "hi")
+            page = query_library_folders(config, "", music_root, "asc", 20, 0, search)
```

- **现象**：正式门禁日志 `artifacts/offline-20260921-round213.log` 的修复前版本红在这里，逐字 `AssertionError: Lists differ: ['Ab', 'Zz'] != ['Ab']`，`FAILED (failures=1, skipped=2)`，JS 段没跑到；而同一段代码在修复前的一次取数跑里全绿（该取数跑未归档，不作后续复核依据）。
- **根因**：`library_search_policy.SEARCH_COLUMNS` = `title/artist/album/album_artist/composer/genre/folder/path/format`，`path` 在列，`track_search_condition` 对每一列各绑一份 `%词%`。用例搜索词是 2 个 ASCII 字母的 `hi`，而 `tempfile.TemporaryDirectory()` 只给 8 个随机字符（外层 TEMP 还会缩成 `ADMINI~1`）—— 随机名里出现 `hi` 时，夹具根自身命中路径列，`Zz/Cd` 一起被判为匹配。实测 200,000 个随机名里 984 个含 `hi`（约 1/203；理论 7/37^2 约 1/196）。
- **为什么不是产品缺陷**：`query_library_folders` 的行为完全正确 —— 它确实按「任一可搜索列含该词」返回；错在用例挑了一个能被临时目录名拼出来的词。取证用手工敌意夹具一次性复现：`needle_in_fixture_path=True` ⇒ `folders=['Ab', 'Zz'] count=2`；`=False` ⇒ `folders=['Ab'] count=1`。
- **为什么选单个非 ASCII 字符**：必须同时满足两件事 —— ① 仍低于 trigram 最小 3 字符，否则用例就从「LIKE 回退分支」漂到「fts5-trigram 分支」，守卫的对象被换掉；② 任何 ASCII 随机名都拼不出它。单个汉字正好同时满足，命中行标题再带上同一个词，`assertEqual(..., ["Ab"])` 的语义不变。
- **守卫**：`assertNotIn(search.lower(), music_root.lower())` 把坑钉死 —— 将来若有人再把搜索词换回 ASCII 短词，报错会直接指名是路径污染，而不是让人去猜为什么多了一行。

### 判别矩阵（仓库外克隆，每格一个子进程）

克隆 HEAD `1302a96`、`git remote remove origin` 后 remote 为空；驱动脚本 monkeypatch `tempfile.TemporaryDirectory` 注入敌意根（普通格为 `<base>/plain`）。旧用例体由新用例体文本替换构造，替换前先断言 `count("20, 0, search)")==2` 且非注释行不含 `search`。产品变异点：`library.py:1681` 的 `args = list(search_args) + list(args)` ⇄ `list(args) + list(search_args)`。

| 格 | 夹具根 | 被测写法 | 期望 | 实跑 | 判据 |
|---|---|---|---|---|---|
| E1 | 普通 | 修复后 | PASS | **PASS** | 控制组先绿 |
| E2 | 敌意（名含 `hi`） | 修复前 | FAIL | **FAIL** `['Ab', 'Zz'] != ['Ab']` | 复现原红，非本轮引入 |
| E3 | 敌意（名含 `hi`） | 修复后 | PASS | **PASS**（`NEEDLE-IN-PATH True`） | 新写法对敌意路径免疫 |
| E4 | 敌意 | 修复前 + 新守卫 | FAIL | **FAIL** `'hi' unexpectedly found in '…hi-ish\music'` | 守卫指名道姓 |
| E5 | 普通 | 修复后 + 产品变异 | FAIL | **FAIL** `[] != ['Ab']` | 没把测试改成常绿 |
| E6 | 普通 | 还原产品码 | PASS | **PASS** | 克隆未被污染 |

`MATRIX ALL-AS-EXPECTED [True, True, True, True, True, True]`；收尾 `RESTORED_TEST True`、`RESTORED_LIB True`，克隆内该模块 139 项复跑 `OK`。

## 变异证明（仓库外克隆，控制组先绿）

做法：在 `%TEMP%` 下 `git clone --no-hardlinks`（副本 HEAD `1302a96`，随即 `git remote remove origin`），把**已打补丁的** `index.html` 与测试文件写进副本再逐枚注入变异。本轮最后一次独立复跑在副本目录 `r140_vmut` 内完成。

> ⚠ 关键坑：`src/tests/test_ui_control_names.js` 是本轮新建的**未跟踪**文件，`git clone` 只会带入库内容，不复制它，副本里 `node` 直接 `Cannot find module` —— 控制组与 9 枚变异会一起「非零退出」，看起来像全灭，实际什么都没测。第一次做变异就踩了这条，那一次不作数；下表是测试文件复制进克隆之后的重跑结果。

| 变异 | 注入内容 | 结果 |
|---|---|---|
| V1 | 删 `#seek` 的 `aria-label` | KILLED（exit 1） |
| V2 | 删 `#volume` 的 `aria-label` | KILLED |
| V3 | 三枚开关全部去掉 `aria-labelledby` | KILLED |
| V4 | `aria-labelledby` 指向不存在的 id（typo） | KILLED |
| V5 | 改用 `aria-label` 复制可见文案 | KILLED |
| V6 | 往 `.switch-control` 的空 `<span>` 填文案 | KILLED |
| V7 | 删 `#nowPlayingSummary` 的 `tabindex` | KILLED |
| V8 | 造一个重复 id：把 `<strong id="shareExpiryLabel">` 改写为行内已存在的 `sharePasswordLabel` | KILLED |
| V9 | `aria-labelledby` 挂到包裹 `<label>` 而非 `<input>` | KILLED |

控制组：副本内（补丁已就位）新测试 exit 0；变异结束后还原复跑 exit 0。

## 门禁
`tools/test_offline.ps1` 本轮登记四份运行。(a) 修复前的一次取数跑绿（未归档，收尾随 TEMP 清除，不作后续复核依据）；(b) 正式日志 `artifacts/offline-20260921-round213.log` 的修复前版本 **红**：`Ran 2510 tests` / `FAILED (failures=1, skipped=2)` / `AssertionError: Lists differ: ['Ab', 'Zz'] != ['Ab']`，`tools/test_offline.ps1:39` 抛 `Python tests failed`，**JS 段完全没跑到** —— 本 md 初稿写的「跑两次…判定值逐项一致…GATE_EXIT 0」是未回读盘上日志造成的假记录，已作废并在自我纠错第 4 条留痕。定位到根因是 H6 那处既有测试的夹具卫生缺陷（与产品码无关），修复后先做一次验证跑 (c) 绿（同样未归档），收尾终跑 (d) 覆盖同一份 round213 日志。判定值：Python `Ran 2510 tests`、`OK (skipped=2)`、`^FAILED` 0、`^ERROR:` 0、`Traceback` 0；；`Traceback` 0 / `^FAILED` 0 / `^ERROR:` 0，JS 段 75 个 `test_*.js` 逐文件 exit 0（其中 73 行输出含 "passed" 字样，2 行不含：新测试与 `ui library metadata merge policy regression ok`），GATE_EXIT 0。**「75 文件」与「73 个 passed」是两枚不同口径，不得混用。** 本 md 与各轮记录一律不写具体用时：一旦写进正文，为满足「终跑日志的 mtime 必须晚于本轮全部写入」而重跑门禁，就会把那个数字改掉；可复现的判据只有条数、skipped、退出码与 0 失败，用时不是。

## 计数
开放项 60 = 代码 2（L99、L150）＋ 设备/外部 45 ＋ 需决策 0 ＋ 长期观察/台账 13。本轮**净关闭 0、新立 0**；`index.html` 184 行按 Q2=A「欠读行数计进展」推进，L99 欠读 21,672 → 21,488。

## 本轮四处自我纠错（写档前自查命中 3 条，写档后回读盘上日志命中第 4 条）
1. 首轮用 `node "tests\$f"` 跑全量 JS 时 `$f` 是 FileInfo，插值取到**绝对路径**，拼出 `tests\E:\...\test_x.js`，75 个文件全部假红。改成 `node ("tests\" + $f.Name)` 后 75/75 绿。假红不是代码问题，但如果不复核就会污染门禁叙述。
2. 第一次写 `TODO.md` 的脚本里误留一行 `io.open(p,"w",...).read()`，`"w"` 模式在 open 时就把文件截断为 0 字节。已用 `git cat-file blob HEAD:TODO.md` 原样恢复并核对 sha（`892140C9…72AF`，与事故前实测值逐字相同），随后改成「内存构造 + 单次写入 + 写后回读校验」的写法。教训进 `PROJECT_CONTEXT.md`。
3. 第一次做仓库外变异时忘了新测试是未跟踪文件、`git clone` 不会带上，副本里没有 `test_ui_control_names.js`，控制组自己就报 `Cannot find module` —— 若当时只看「9 枚变异都非零退出」就会把一次完全没跑起来的实验写成「V1～V9 全灭」。本轮结论全部出自把测试文件复制进克隆之后的重跑（`r140_vmut`：CONTROL 0 / PRISTINE 1 / V1～V9 KILLED / SURVIVORS 0 / 还原复跑 0）。
4. **门禁结论没回读日志**。本 md 与 `CHANGELOG_AI.md` 的 R140 第二条初稿都写着「门禁跑两次、判定值逐项一致、GATE_EXIT 0」，而盘上那份正式日志 `artifacts/offline-20260921-round213.log` 的修复前版本逐字是 `FAILED (failures=1, skipped=2)`，失败用例 `test_folder_search_in_like_mode_binds_the_match_term_once`，JS 段一行没跑。原因是写档时引用了早前口算的结论。已按日志逐字改写两处，并把「宣布门禁结论前必须回读该日志的判定行」并入收尾流程；红因本身见 H6 一节，属既有测试的夹具卫生缺陷，当轮修掉、当轮用六格矩阵证明。