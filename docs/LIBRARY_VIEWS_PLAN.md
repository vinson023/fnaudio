# 库浏览体验：可持续的 P1–P3 计划

> 来源：`docs/ANALYSIS_LIBRARY_INDEX_VS_DS_AUDIO.md` 第 5 节「值得借鉴」的三条。
> 与 `docs/PERF_STABILITY_PLAN.md` 同构：**每条都要有指标、有会失败的守卫、有复核方式**，缺一条就不算「可持续」。

## 怎么读这张表

1. **指标**：一句话说清量什么、单位是什么；
2. **守卫**：一条会失败的自动化断言（测试或脚本），改坏了就红；
3. **复核**：谁在什么时候跑，结果写在哪。

## 现状总表

| 编号 | 借鉴点 | 指标 | 守卫 | 状态 |
|---|---|---|---|---|
| P1 | 保存的查询（saved views） | 保存/应用/删除往返是否一致；同名是否覆盖而非新增；上限是否 24 | `src/tests/test_library_saved_views.py`（20 例）+ `src/tests/test_ui_library_saved_views.js` + e2e `a saved view restores its filter after a reload and can be removed` | **已实现**（R585） |
| P2-1 | 搜索字段限定（`artist:` 等） | 限定字段是否只命中该列；多子句是否 AND；短词是否降级 LIKE | `src/tests/test_library_search_query_policy.py`（19 例，含 4 条真实 trigram 集成） | **已实现**（R585） |
| P2-2 | 能力协商式功能开关 | `capabilities` 缺失时是否**退回老行为**而不是报错 | `test_ui_library_saved_views.js`（缺失/降级断言）+ `test_library_saved_views.py` | **已实现**（R585） |
| P3 | 封面按「同一张图」做键 | 一张专辑 N 首的**渲染次数** | `src/tests/test_cover_artwork_reuse.py`（13 例）+ `tools/measure_cover_key_strategy.py` | **已实现**（R585，比原建议更省） |

三条里两条是「补能力」（P1、P2-1），一条是「换做法」（P3）——P3 原建议（按 `album/artist/album_artist` 组合做键）**没有照做**，理由在下面 P3 一节，是量出来的。

---

## P1 保存的查询（已固化）

- **指标**：一次「保存 → 出现在列表 → 点它回到同一筛选 → 删除 → 列表少一条」的往返是否闭合；同名保存是否**替换**而不是堆两条；条数上限是否 24。
- **实现**：分三层，纯逻辑与落盘分开，才能只测逻辑。
  - `src/app/server/library_saved_view_policy.py`：纯校验。`VIEW_NAMES`（11 个）、`SORT_KEYS`（6 个）、`MAX_VIEWS=24`、`MAX_NAME_CHARS=48`；`normalize_criteria` 遇未知 view 抛 `ValueError`、未知 sort 回落 `title`、dir 只认 `desc`；`view_identity(name)` 按**名称** casefold 哈希（不是按条件）——同名即同一个位子。
  - `src/app/server/library_saved_views.py`：落盘，走 `state_db_connect`，与收藏/歌单同在 `state.sqlite3` 的 `saved_views(id, name, criteria, created_at, updated_at)`。
  - `src/app/ui/library_saved_view_policy.js`：浏览器侧纯函数（`capture`/`toQueryParams`/`validateName`/`summary`/`merge`/`remove`），`app.js` 只做接线。
- **为什么 id 跟名称走**：按「名称 + 条件」哈希会让「同一个名字换个筛选」变成两条，用户看到的是一排同名项。改完之后同名保存是 `upsert`，`created_at` 保留、`updated_at` 刷新。
- **守卫**：
  - `test_library_saved_views.py`：13 例策略（未知 view 抛错、未知 sort 回落、dir 归一、同名覆盖、上限截断、排序按 `updated_at` 倒序、`created_at` 保留）+ 5 例落盘往返（`tempfile.TemporaryDirectory` 真建库）+ 3 例能力块。
  - `test_ui_library_saved_views.js`：**跨语言守卫**——从 Python 文件里正则读出 `VIEW_NAMES`/`SORT_KEYS`/`MAX_VIEWS`，与 JS 侧常量比对。两侧各写一份常量是必要的（一个跑在服务端、一个跑在浏览器），但**不一致必须红**。
- **复核**：并入日常 Python + JS 门禁。

## P2-1 搜索字段限定（已固化）

- **指标**：`artist:pink floyd` 是否只命中 `artist` 列（同名词在 title 里不算命中）；`artist:x title:y` 是否 AND；少于 3 字符的词是否降级到 LIKE 而不是静默丢结果。
- **实现**：`src/app/server/library_search_query_policy.py` 是纯解析层——`SEARCH_FIELDS`（9 列）、`MAX_QUERY_CHARS=4096`、`MAX_CLAUSES=8`、`FTS_MIN_TERM_CHARS=3`；`_split_tokens` 让引号内空格不断词；`_unquote` **只剥整串引号**，内部引号留作字面量（`a"b` 是合法输入，不是错误）；`_clause` 遇到 `artist:` 这种「字段有值无」按放弃前缀处理（用户还在打字）。`library_search_policy.track_search_condition` 只做分发：能走 FTS 就走 `tracks_search MATCH`，否则回落 `LIKE`。
- **为什么必须有 LIKE 兜底**：trigram 索引对 <3 字符的词无效。早先的实现会在这条路径上**静默返回空**，用户看到的是「搜不到」而不是「词太短」。
- **守卫**：`test_library_search_query_policy.py` 19 例，其中 4 条是**真实 SQLite trigram 集成**用例（建表、`rebuild`、真查），不是对着字符串比对——解析层写错、索引层写错、SQL 拼错都能被这 4 条抓到。
- **复核**：并入日常 Python 门禁。

## P2-2 能力协商（已固化）

- **指标**：服务端 `capabilities` **缺失或畸形**时，客户端是否退回「老行为」（不显示保存按钮、不加搜索提示），而不是报错或显示一个点不动的按钮。
- **实现**：
  - 服务端 `src/app/server/library_capability_policy.py`，`CAPABILITY_VERSION=1`，随 `/api/library/status` 下发 `{version, saved_views, search, sort, views, formats}`；未知搜索模式降级为 `like`。
  - 客户端 `src/app/ui/library_capability_policy.js` 是**唯一读取点**。默认值刻意写成「不启用」：`features(null)` 返回 `savedViews.enabled=false`、`search.fieldSyntax=false`。这样「新客户端 + 老服务端」是安全的降级，不是崩。
- **为什么默认关**：默认开等于假设服务端一定支持，那么老服务端上会出现「按钮在、点了 404」。AS 的 `maxVersion` 也是同一逻辑：**能力由服务端声明，客户端只做适配**。
- **守卫**：`test_ui_library_saved_views.js` 断言 `features(null)`/`features({})` 全关、`searchPlaceholder` 在无字段语法时是原样文案；`test_library_saved_views.py` 断言服务端块字段齐全且 `search.mode` 合法。
- **复核**：并入日常 JS 门禁。

## P3 封面键：原建议没照做，因为已经更省了

原建议是「按 `album/artist/album_artist` 组合做键，让整张专辑共用一份缩略图」。查过现有实现后**没有照做**，原因是它想解决的问题已经解决了，而且是更强的方式：

- `cover_cache` 早就是**内容寻址**：渲染出的 JPEG 存在 `covers/assets/thumb-<size>/<sha256(原图字节)>.jpg`，每首曲子只留一个 64 字节的 `<key>.asset` 别名指向它（`cover_cache.py` 里 `asset_key = sha256(body)` 那一段）。同一张专辑的 N 首曲子，**磁盘上只有一份图**。
- 按专辑名做键反而**更弱**：两首曲子同专辑名但内嵌封面不同（换过封面的重制版、合辑里各曲自带图）会互相串图；内容寻址不可能串，因为键就是图本身。

**但量下来确实还有一处浪费**：每首曲子都要**自己渲染一次**。别名是按曲子的，第二首曲子的别名还没写，所以同一张图又走了一遍缩略图器。

R585 因此加了一层 **artwork 摘要记忆**（`_ARTWORK_ASSET_CACHE`，键是 `(缓存目录, 图字节摘要, 尺寸)`）：第二首及以后的曲子直接认领第一首的渲染结果，再补写自己的别名。键仍然是内容，所以永远不会指错图。

实测（`tools/measure_cover_key_strategy.py`，12 首共用一张图）：

| 策略 | 冷启动渲染次数 | 磁盘字节 | 文件数 |
|---|---|---|---|
| 每曲各渲染（R584 及以前） | **12** | 13,056 | 1 图 + 12 别名 |
| 摘要记忆（R585） | **1** | 13,056 | 1 图 + 12 别名 |
| 按专辑做键（原建议） | 1 | 12,288 | 1 图 + 0 别名 |

**结论**：省下的是 **11/12 的渲染（91.67%）**，磁盘字节**一个没变**——原建议那 768 字节的差距是 12 个 64 字节别名，用它换掉「同专辑不同封面会串图」的风险不划算。基线写进 `docs/perf/baseline_cover_key.json`，用于发现「以后又变成每曲一渲染」。

**边界**：这张记忆表只在同一进程内有效，重启后靠磁盘上的别名文件（第二首的别名已经在上一轮写好了），所以重启不会退回 12 次渲染——`test_a_restart_serves_the_second_track_without_rendering` 守的就是这条。

**守卫**：`src/tests/test_cover_artwork_reuse.py` 13 例——整张专辑只渲染一次、不同图仍分开渲染、不同尺寸不共用、不同缓存目录不共用、别名照写、重启后不重渲染、资产被清理后回落重渲染、别名写失败仍出图、`clear_memory_cache` 清掉记忆、上限有界、空值拒绝、状态可见。

---

## 不值得做：写下来防止回流

这三条都是 AS 里「看起来能抄」但**抄了会更差**的做法，记在这里，下次别再提。

1. **固定 1024 分页**。AS 把 `limit` 硬编码成 1024，靠 `page=-1 → limit=-1` 一次拉全表来实现「全部播放」。fnAudio 用 keyset 游标，10 万曲实测单页 0.016–0.024 s；换成 1024 一页会让首屏等一个 1024 行的响应，而「全部播放」本来就有 `random100`/整列表两条独立路径。**不做。**
2. **无 TTL、无失效的页缓存**。AS 的 `<online>_<CONTAINER>_<library>/<page>.cache` 没有 TTL，`gLibraryChanged` 只在切个人/共享库时置位——库变了客户端不知道，只能下拉刷新。fnAudio 的增量刷新是 inotify + 签名，**本来就知道库什么时候变**，抄一个「不知道库变了」的缓存是倒退。**不做。**
3. **离线库拆成两套表**。AS 的离线库是「已下载子集」（`song_table` + `cache_path IS NOT NULL`），与在线库两套 schema。fnAudio 的离线能力已由负责人裁定撤除（见 `docs/PERF_STABILITY_PLAN.md` P2-2 边界），再引入第二套表只会多一份要维护的真相。**不做。**

## 复核方式

**不额外设定时任务。** 本计划的四条守卫都已经在既有门禁里，再排一个定时任务只会是它的真子集：

- `.github/workflows/verify.yml`（`on: push / pull_request`）调 `tools/test_offline.ps1 -Browser`，跑的是**全量** `unittest discover` + 每个 `test_*.js` + playwright，外加清单新鲜度、Android debug 构建、fnpack 打包——严格覆盖本计划需要的全部断言。
- P3 那条不需要单独度量：`test_cover_artwork_reuse.py` 的 `test_a_whole_album_costs_one_render` 与 `test_a_restart_serves_the_second_track_without_rendering` 就是会失败的断言。`tools/measure_cover_key_strategy.py` 与 `docs/perf/baseline_cover_key.json` 只用于**改动前后对比**，不是常设哨兵。

本地想单跑一遍（工作目录 `src/`）：

```bash
PYTHONPATH=app/server python -m unittest tests.test_library_saved_views tests.test_library_search_query_policy \
  tests.test_library_search_policy tests.test_cover_artwork_reuse tests.test_library_sqlite \
  tests.test_android_bundled_scripts tests.test_source_manifest
node tests/test_ui_library_saved_views.js && node tests/test_ui_touch_hover_residue.js
```

> Python 门禁必须从 `src/` 跑：`src/tests/` 里有大量用例按相对路径读 `app/server/*.py`，从仓库根跑会成片 `FileNotFoundError`，那是调用方式错，不是代码红。

> 2026-11-18 记：曾建过一条每天 09:00 的「P1–P3 守卫复核」定时任务，一天后删除。原因有三：它跑的是 CI 的子集；只报告不拦截，没人看就只是噪音；最要紧的是**窄范围绿灯会骗人**——它全绿时清单可能已过期、Android 可能编译不过。护栏留在 CI，不另设。**唯一还值得单独立项的**是 `tools/benchmark_large_library.py` 的大库基准（CI 不跑它，因为要几分钟和 200MB+ 临时库），它能抓「单页 0.02 s 退到 0.2 s」这类单测抓不到的回归；那是独立计划，不挂在本文件下。

## 做下一件事的判据

本计划的四条已经全部落地，**没有排在队里的条目**。再往 AS 那边看，剩下的都是「不值得做」里列的三条。

真要继续，只有两个方向，且都不是抄 AS：

1. **保存的视图能不能跨设备**（现在存在 NAS 的 `state.sqlite3` 里，天然是跨设备的；缺的是「导入/导出」与「默认视图」）；
2. **字段语法的可见性**（现在只有 placeholder 提一句，用户不知道有哪 9 个字段）。

没写进这条链的改动，不进本计划。
