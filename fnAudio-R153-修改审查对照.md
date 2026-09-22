# fnAudio R153 修改审查对照（逐 hunk · 行号为编辑后盘上真实 1-based）

本轮改动面：服务端封面缓存读路径 1 个文件 2 个 hunk ＋ 判别用例 1 个文件 5 枚 ＋ 三份根文档 ＋ 清单重刷。
下面每一节都可按行号与命令自行复算；未经磁盘确认的数字一律不写。

## 文件净增（`git diff --numstat c311535..HEAD`，`c311535` = R152 收尾；本轮前三笔为 `c5563e1`／`8ed746f`／`b80463c`）

| 文件 | 插入 | 删除 | 落笔提交 | 说明 |
| --- | --- | --- | --- | --- |
| `src/app/server/cover_cache.py` | 13 | 2 | `c5563e1` fix(cover-cache) | 两个 hunk，文件 1,364 → 1,375 行 |
| `src/tests/test_cover_cache.py` | 94 | 1 | `c5563e1` fix(cover-cache) | 新增 4 枚＋加强 1 枚，1,718 → 1,811 行、`def test_` 90 → 94 |
| `SOURCE_MANIFEST.sha256` | 2 | 2 | `8ed746f` chore(manifest) | 恰 2 条摘要变更（上述两文件），全表 711 条 |
| `TODO.md` | 2 | 1 | `b80463c` docs(round-R153) | 顶部新增 1 条深读记录；R59 条目追加第 9 枚折入 |
| `CHANGELOG_AI.md` | 2 | 0 | `b80463c` docs(round-R153) | 修复条目＋取证/变异/门禁条目 |
| `PROJECT_CONTEXT.md` | 1 | 0 | `b80463c` docs(round-R153) | 同一身份版本必须一次算清、处处传用 |
| `fnAudio-R153-修改审查对照.md` | 本文件 | — | 第四笔 docs(round-review) | 审查对照包（惯例：随轮入库） |

提交范围严格按 pathspec 逐笔 `git add`，未用 `-A`、未 push、未碰 `.gitignore`／`.gitattributes`。
`artifacts/offline-20260922-round234.log` 不入库：`git ls-files artifacts` 现盘 85 条全是 `artifacts/0.1.x/` 发包三件套，历史 `offline-*.log` 入库数为 **0**。

## 一、接管取证（磁盘实测，不采信交接快照）

| 项 | 实测值 | 取证方式 |
| --- | --- | --- |
| 工作目录／分支 | `E:/fnAudio`／`main` | `Get-Location`、`git rev-parse --abbrev-ref HEAD` |
| 接管时 HEAD | `c311535`（R152 packet 提交） | `git rev-parse --short HEAD` |
| 未完成合并态 | `MERGE_HEAD`、`rebase-merge`、`rebase-apply`、`CHERRY_PICK_HEAD`、`BISECT_LOG`、`index.lock` 六哨兵全不存在 | `os.path.exists` 逐一 |
| stash | 0 条 | `git stash list` |
| 接管时未提交面 | 6 文件全部 ` M`，均**未** staged | `git status --porcelain -- <pathspec>`（不带 pathspec 会输出百万级 token） |
| `cover_cache.py` | 1,375 行／60,085 B；numstat 13／2；两 hunk | 现盘 ＋ `git diff --numstat` |
| `test_cover_cache.py` | 1,811 行／100,485 B／`def test_` 94 | 现盘复算 |
| `SOURCE_MANIFEST.sha256` | 711 条／77,094 B／CRLF；全表逐文件复算 missing 0／mismatch 0 | 重算比对 |
| `TODO.md` | 2,174 行；`- [ ]` 15 ＝ 代码桶 2 ＋ 长期观察 13；`- [x]` 1,496；决策段开放 0 | 正则复算 |
| 设备段台账 | `docs/external-acceptance.md` 开放 28／收口 17 | 复算 |
| 欠读面 | `app.js` 8,405、已跟踪 Android `.java` 43 文件 9,695，均与登记值逐字相符；合计 **18,100** | 现盘复算 |
| focused 三套（真树） | `Ran 115 tests`／`OK` | `test_cover_cache`＋`test_library_presentation`＋`test_cover_item_cache` |
| 四守卫 | `Ran 44 tests`／`OK` | `test_change_record`、`test_source_manifest`、`test_device_todos_migrated`、`test_ledger_evidence_cards` |

### 门禁数字复核（本棒接手时唯一未决项）

终跑日志 `artifacts/offline-20260922-round234.log`：436,196 B、无 BOM、2,718 行、`FAIL`／`ERROR`／`Traceback` 各 0 次，尾行仅 `git diff --check` 的 CRLF 警告；包装器 rc 文件 `EXIT=0`。

| 待核项 | 逐字读数 | 文档口径 | 结论 |
| --- | --- | --- | --- |
| Python 汇总 | `Ran 2559 tests in 122.269s`／`OK (skipped=2)` | 同 | 相符 |
| JS 文件数 | 现盘 `src/tests/test_*.js` 共 77 个 | 「77 个全退 0」 | 相符 |
| 含 `passed` 行数 | **75**（`"passed" in line` 与 `re.search(r"passed")` 两种判据同数） | 「75 行含 passed」 | 相符 |

上一棒的 76 是**计数口径假象**：那次用 `Select-String + Group-Object` 汇总，去重前把同名行多算一行。逐行打印 2,640..2,716 实得 75，与文档一致。
⇒ **结论：三份根文档与清单均无需改动，终跑无需重跑**；本棒只补做提交与本包。

## 二、缺陷 A 与修法（逐 hunk）

缺陷：`thumbnail_asset_id_for_item`（def `:414`）与 `cover_is_known_missing`（def `:540`）签名收 `allow_disk`，却把它交给 `_cache_paths(item, config, size)`（def `:281`）——不传 `version`，其内部 `_cache_key`（`:265`）在 `version is None` 时按**磁盘默认**重算身份。参数在、约束不在，两个后果：

1. `allow_disk=False` 快路径每行仍照付一次媒体文件 `os.stat`（`:245`），本要规避的成本一分没省；
2. 索引身份不完整（`:218-221`）时，页面序列化用的有界版本与缓存键用的磁盘版本分叉：`library_presentation.py:86-90` 以同一个 `allow_cover_disk_lookup` 出 `cover/<id>?v=<版本>`，端点写好的 `<key>.asset` 别名，页面按另一套键永远查不到。

### Hunk 1 · `:432-433`（`thumbnail_asset_id_for_item` 命中路径）

```diff
     size = normalized_cover_size(size)
     if not size:
         return ""
-    _root, target, _missing = _cache_paths(item, config, size)
+    # The alias key has to come from the source version this call is allowed to
+    # know about.  Letting ``_cache_paths`` recompute it silently uses the disk
+    # default, which puts one media ``stat`` behind every visible row of a
+    # latency-sensitive page projection -- the exact cost ``allow_disk=False``
+    # exists to avoid -- and keys the lookup by a version the page never
+    # advertises (``library_presentation`` serialises the bounded one).
+    version = cover_source_version(item, allow_disk=allow_disk)
+    _root, target, _missing = _cache_paths(item, config, size, version)
     return _alias_asset_key(target[:-4] + ".asset", config, size, allow_disk)
```

### Hunk 2 · `:553-554`（`cover_is_known_missing` 标记键）

```diff
     size = normalized_cover_size(size)
     if not size:
         return False
-    _root, _target, missing = _cache_paths(item, config, size)
+    # Same single-version rule as ``thumbnail_asset_id_for_item``: the marker is
+    # addressed by the version the caller may resolve, so the fast page and the
+    # cover URL it serialises cannot drift onto two different cache namespaces.
+    version = cover_source_version(item, allow_disk=allow_disk)
+    _root, _target, missing = _cache_paths(item, config, size, version)
```

两处共用同一条不变量：**同一次调用里，别名/标记键所依据的版本，必须就是调用方被允许知道的那个版本**，且只算一次、显式下传。默认路径（`allow_disk=True`）仍走权威磁盘身份，行为不变，仅改为显式传参。

## 三、判别测试（`src/tests/test_cover_cache.py`）

| 位置 | 用例 | 盯住的不变量 | 改前 | 改后 |
| --- | --- | --- | --- | --- |
| `:390`（既有，加强） | `..._do_not_probe_disk_for_unknown_entries` | 未知条目不得探盘 | 通过（旧 mock 只挡 `isfile`，挡不住 `os.stat`） | 通过 |
| `:415`（新增） | `..._do_not_stat_media_with_incomplete_identity` | 身份不完整时快路径不得 stat 媒体文件 | **RAISED** `AssertionError: page projection must not stat the media file` | 通过 |
| `:432`（新增） | `..._agree_with_the_version_the_page_url_carries` | 快路径必须解析到页面自己广告的那个版本 | **RAISED**（键落到磁盘版本，别名查不到） | 通过 |
| `:465`（新增） | `test_authoritative_cover_lookups_keep_the_filesystem_version` | 权威路径（默认 `allow_disk=True`）不得被降级为有界版本 | 通过（防过度修正的反向闸门） | 通过 |
| `:497`（新增） | `test_complete_indexed_identity_keys_the_same_under_both_lookup_modes` | 完整索引身份在两种查询模式下必须同键（修复不产生新命名空间） | 通过 | 通过 |

`:390` 的加强是本轮关键：给它补 mock `os.stat`。**这正是旧缺陷能躲过全部 90 枚既有用例的原因**——旧用例只观察 `isfile`，而真实盘查询发生在 `os.stat`。

## 四、缺陷 B：扫描截断可致资产回收误删（当轮并入既有条目，本轮不修）

同面读到：`_cover_cache_files`（def `:586`）在 `:609-610` 按 `COVER_CACHE_SWEEP_ENTRY_LIMIT`（`:571` = 20000）**先截断**；`os.walk` 配 `dirnames.sort()`（`:606-608`）使 `covers/assets` 恒先被枚举，触顶时**别名一枚都看不到**，于是 `prune_cover_cache`（def `:677`）的 tier-2（`:741-744`）可能删掉仍被引用的资产，或以截断清单低估 `total`（`:749`）。

按「新发现的问题当轮修掉、当轮证伪，或并入既有条目」口径，折入 R59 量化欠读条目（`TODO.md:156` 第 9 枚标记），**不另立新项**，本轮净关闭 0、新立 0。

推荐设计（待裁定是否单独占一轮）：
1. `_cover_cache_files` 返回 `(entries, alias_complete)`，触顶即 `alias_complete=False`；
2. `alias_complete=False` 时只跑 tier-1（悬空别名）＋ legacy thumb 清理，**禁用 tier-2/tier-3 资产回收**——宁可暂留字节，不可删仍在引用者；
3. 枚举顺序把 `covers/thumb-*` 排在 `covers/assets` 之前，使截断优先丢资产而非丢引用来源；
4. 须一并论证：超过 20,000 文件时，仅靠 tier-1＋legacy 通道仍能在有界删除预算（`:576`／`:720` = 200）内收敛到字节上限，否则本条不得关闭。

## 五、仓库外副本变异证明（9 格，本棒复跑并逐格记录被杀用例）

副本 `E:/fnAudio_r153_cp3`（`src`＋`docs`＋`tools`＋清单，用完即删；真树全程未注入任何变异）。控制组先绿：`BASE` `Ran 115 tests`／`OK`。每格独立子进程跑 focused 三套。

| 格 | 注入点 | 注入内容 | 结果 | 被杀用例 |
| --- | --- | --- | --- | --- |
| V1 | `:432-433` | 回退为不传 `version` | KILLED | `:432`、`:390`、`:415` 三枚 |
| V2 | `:553-554` | 回退为不传 `version` | KILLED | 同上 3 枚 |
| V3 | `:432` | `allow_disk=allow_disk` → 硬编码 `False` | KILLED | `:465`、`test_memory_entries_are_keyed_by_identity_so_a_sweep_cannot_reverse_them` 2 枚 |
| V4 | `:553` | 同上硬编码 `False` | KILLED | `:465` 1 枚 |
| V5 | `:434` | `_alias_asset_key(..., allow_disk)` → `True` | KILLED | `test_fast_page_cover_lookups_reuse_in_process_positive_entries` 1 枚 |
| V6 | `_write_alias` | 去掉「版本已由调用方给定」短路，无条件重算 | KILLED | 5 枚：`:465`、`:390`、`:415`、`test_mid_request_identity_change_cannot_split_the_cache_keys`、`test_one_cover_request_resolves_the_source_version_once` |
| V7 | `:433` | 显式传 `version` → 传 `None` | KILLED | `:432`、`:390`、`:415` 3 枚 |
| V8 | `:554` | 同上 | KILLED | 3 枚 |
| P1 | 测试 `:465` | 正控：把期望值换成假 asset key | **RED（符合预期）** | 该用例 1 枚 |

8 枚变异体全灭、正控判 RED，`killed 9/9`；两文件随后逐字节复原 pristine（`prod True / test True`），`AFTER-RESTORE` 复绿。
本棒复跑结果与已提交的 `CHANGELOG_AI.md` R153 第二条计数**逐格一致**，故未追加更正条目。

## 六、当轮证伪 5 组（不得记作发现）

| 疑点 | 证伪依据 |
| --- | --- |
| 单元回收会先删资产留悬空别名 | 已保证别名先于资产，且预算不足时整单元跳过（`:763-780`） |
| `_forget_advertising_asset` 会误清可服务别名 | `:437-451` 只在资产请求已失败之后清内存别名 |
| 两个 prewarm worker 的 `stop_when_drained` 有清旗/出队竞态 | 清旗与出队放在同一次持锁内（`:901-914`／`:1085-1095`） |
| `_atomic_bytes` 缺 fsync 会让读者看到半截内容 | 按「读者能否把半截字节当有效内容」分级 fsync（`:1195-1202`），别名与标记走 `durable=False` |
| `cached_thumbnail_for_item` 路径中途版本漂移 | 全路径共用一个 `version`（`:1270-1276`） |

## 七、记账与门禁

- 反增长四条逐条核：净关闭既有代码待办 **0**（本轮为深读＋缺陷修复轮，未关闭任何条目）；新立可离线代码项 **0**；本轮发现全部当轮修掉、证伪或并入既有条目；每条代码待办均有判别测试。
- 勾选项 1,495 → **1,496**；开放 `- [ ]` 15 条 ＝ 代码桶 2（`TODO.md:105`、`:156`）＋ 长期观察 13；决策段开放 **0**；设备段台账开放 28／收口 17。
- 欠读总量 19,464 → **18,100**（`cover_cache.py` 整面出局）。
- 清单重刷至 711 条，本轮 diff 恰 2 行，全表逐文件复算 missing 0／mismatch 0。
- 真树终跑 `artifacts/offline-20260922-round234.log`：Python `Ran 2559 tests`／`OK (skipped=2)`、JS 77 个文件全退 0 且 75 行含 `passed`、`exit 0`。
- 探针与副本已全部清理：`E:/fnAudio` 根下 `r153*`／`r154*`／`r155*` 7 个日志与 `E:/fnAudio_r153_cp`、本轮 `E:/fnAudio_r153_cp3`、`%TEMP%` 脚本按轮末清除。
- `.new`／`.orig`／`.rej`：`src`、`tools`、仓库根为 0；全仓唯一命中在 `_external/runtime/gomodcache/**/surface.new`（第三方缓存，非本轮残留）。

## 八、终止条件进度（成立 1/4，不得自称完成）

| 条件 | 状态 | 依据 |
| --- | --- | --- |
| (1) 可离线代码项清空 | ✗ 剩 2 条 | `:105` 判据为「剩余欠读面全部读完」，仍欠 18,100 行；`:156` 判据 381 个登记符号面，深读分子 48 |
| (2) 设备/外部项移出逐轮任务 | ✗ 台账开放 28 条 | N1=C：代码桶优先、设备段并行推进 |
| (3) 需产品决策项汇总征询 | ✓ 决策段开放 0 | 全部裁定已入库 |
| (4) 终止前跑完整离线门禁 | ✗ 待用户发令 | N3=A：终局门禁只在显发终止令时跑，不得自行判定终止 |

三口径历史数字并存不合并：旧目标正文 `155 = 64 + 82 + 9`（过期快照）／R99 实测 `115 = 51 + 43 + 8 + 13`／现盘 `15 = 2 + 13`。
已完成轮次远超 36，`maxGoalRounds = 72` 既不构成终止理由，也不得据此改动终止条件。

## 九、提交后复审与更正清单（本棒自查，逐条「原表述 → 现盘实测 → 处置」）

1. 「文档改完必须再刷清单」→ 实测 `SOURCE_MANIFEST.sha256` 只覆盖 `src/`（631）＋ `android-client/`（80），三份根文档与 `docs/` **不在清单内** → 本包第一节按此更正；本轮文档改动不影响清单，无需二次重刷。
2. 「终跑 JS 侧 76 行含 passed」→ 逐行实数 75，76 系 `Group-Object` 去重前多算 → 文档口径本就是 75，无需改文档；差异记录在本包第一节。
3. 变异矩阵逐格被杀用例名此前只存计数 → 本棒在副本复跑补齐九格明细（第五节），计数与已提交记录一致。
4. 未提交面 6 文件 → 已按三个 pathspec 组逐笔入库（`c5563e1`／`8ed746f`／`b80463c`），工作树此后只剩未跟踪噪声。
