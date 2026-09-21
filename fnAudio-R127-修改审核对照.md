# fnAudio R127 修改审核对照（本文件不入库）

接管基线：HEAD `972f733 chore: record R126 closure`（本会话前）
本轮提交：`fb4bc68 test(library): pin the folder page count guard and the cache that hides it` → `0b6be71 chore: record R127 closure`
终跑门禁：`artifacts/offline-20260921-round193.log`（exit 0）

## 一、本轮关闭的条目

`TODO.md` 原 L103（关闭后落在 L104）：「50k 顶层目录时剩余 5.91 ms 的主成本是 `SELECT COUNT(*) FROM folders WHERE root=? AND parent=?` 的覆盖索引遍历（约 5 ms）。若还要继续压首屏，需要把『每个目录的子项数』变成持久列或按目录缓存计数……当前不做，因为 12.13 到 1.21 ms 的量级已经不再受目录宽度支配。」

磁盘重测（走真函数 `query_library_folders`，50k 目录挂同一父目录）：

| 形状 | 实测 |
| --- | --- |
| 未命中首页 | 9.2~11.5 ms（其中该 count 4.39 ms） |
| 深 offset 页 | 16.9 ms |
| 同参热重复 | 0.26 ms，0 条语句 |
| 删 `idx_folders_root_parent` 后同一 count | 5.38 ms（20k）/ 14.23 ms（50k） |

结论：**判定不改生产代码仍然成立，但原文那句理由只在缓存命中路径成立**；另取证到新事实 —— folders 面没有 saved-count 摊销协议（`_save_library_meta_count` 只服务 groups，`library.py:1593-1610`）。因此本轮关掉的是「前提」：把那层查询缓存的行为钉成守卫。

## 二、逐 hunk 审核

### hunk 1 — `src/tests/test_library_sqlite.py` L2686-2702（扩展既有测 `test_unfiltered_folder_page_reads_an_indexed_page_plus_count`）

- 取证方式：`set_trace_callback` 抓到真实生产 SQL，分成页面语句与计数语句两组，本 hunk 只管计数那组（页面那组的计划断言在既有 `:2681` 已存在，未放宽）。
- 新断言三件事：计数语句的计划必须是 `COVERING INDEX`；索引名必须是 `idx_folders_root_parent`；detail 里不得出现 `nocase`（否则会静默改用更宽的排序索引）；并禁 `TEMP B-TREE`。
- 判别性：变异 V1（删 `library.py:2389` 的建索引）当场被 `:2696` 杀死，证明断言不是恒真。
- 注释里写的是数字，但断言里没有计时，符合「计时阈值不当守卫」的仓库既有结论（L120）。

### hunk 2 — `src/tests/test_library_sqlite.py` L2704-2768（新增测 `test_repeated_folder_page_is_served_without_rereading_the_directory`）

- 夹具刻意只用 3 个目录（A/B/c），因为要断言的是「发不发语句」，与规模无关；NOCASE 序里 `c` 排在 `d` 前，正好让 offset=2 的深页返回唯一一行 `["c"]`，防止 key 少带一个维度时两页互相命中。
- 四条关键断言：`:2750` 同参热读必须 0 条语句（这条一挂，条目留下的理由就作废）；`:2753` 换 offset 必须重读；`:2754` 深页确实发了语句（反向兜住「空 trace 也算过」）；`:2766` 写库后 count 必须变 4 且 `:2767` 必须重发语句。
- 冷读侧 `:2747` 先断言「计数语句真的出现过」，否则热读 0 语句可能只是因为整条通路根本没跑到。
- 变异：V2 `cached = None` → KILLED `:2750`；V3 `cache_values` 去掉 `page.offset` → KILLED `:2753`；V4 `return result` 永不写缓存 → KILLED `:2750`；V8 双旋钮 → KILLED `:2766`。

### hunk 3 — `SOURCE_MANIFEST.sha256`

- 只有一行变动：`src/tests/test_library_sqlite.py` 的 sha。刷新后仍 706 条、0 重复路径、**全量 706 条逐文件 sha 复算 0 不一致**。本轮无新增文件（三份根文档不在清单内，属既有口径）。

### hunk 4-6 — 三份根文档（最新在前，纯插入 ＋ 一条状态翻转）

- `TODO.md`：L2 插入本轮记录 1 行；L104（原 L103）仅把 `- [ ] ` 翻成 `- [x] ` 并在行尾内联追加关闭说明，其余字节不动。净增 1 内容行（2214 → 2215），开放 73 → 72，已关闭 1468 → 1470。
- `CHANGELOG_AI.md`：插入 3 行（实现／测试与变异矩阵／收口清单与提交），6710 → 6713 内容行。
- `PROJECT_CONTEXT.md`：插入 3 行经验（性能条目钉前提不钉数字／条目自设的门不可硬关／冗余兜底造成的单旋钮存活必须原样上报），6140 → 6143 内容行。
- 设备/外部段 44 条与 `git show HEAD:TODO.md` 按节标题切片逐字比对 `identical=True`；决策段仍 1 条（L1880）。
- 校验器实跑（`%TEMP%`，跑完即删）：轮次号唯一且最新在前 `[127,126,125,124,…]`、三份文档前缀格式正确、0 个 CRLF、尾部空行序列与 HEAD 全等、源码区无 `.new/.orig/.rej/.tmp`。

## 三、门禁当场抓到并已修掉的一处真实缺陷

首跑 round193 失败：`test_change_record.test_every_flat_entry_is_dated_and_newest_first` 报「TODO.md line 3 is not a dated entry」。根因是我在 TODO 记录里写副本路径时，Python 源串把 `%TEMP%\fnaudio-...` 里的 `\f` 吃成 0x0C 换页符，`splitlines()` 会把该记录行劈成两行。修复＝把 0x0C 还原为字面反斜杠＋f，`splitlines()` 与内容行数重新相等（2215），复跑 `test_change_record` 3 项 OK，再整跑门禁 exit 0。其余两份文档扫描无控制字符。

## 四、变异矩阵（仓库外副本，已删除）

副本 `%TEMP%\fnaudio-r127-copy`（`git clone --no-hardlinks` ⇒ HEAD `972f733`、`git remote remove origin`、两文件与在盘逐文件 sha 全等；副本内先刷清单再跑，因 clone 以 autocrlf 签出使 src 内 38 个文件带 CRLF）。控制组 Python 全量 `Ran 2462 OK (skipped=3)`（多的 1 条 skip 是 `artifacts/` 缺失的环境差异）、Node 74 文件 0 失败。

| 变异 | 结果 | 杀手/原因 |
| --- | --- | --- |
| V1 删 `idx_folders_root_parent` 建索引 | KILLED | G1 `:2696`（正是新断言） |
| V2 `cached = None` 永不读 folder 缓存 | KILLED | G2 `:2750` |
| V3 `cache_values` 去掉 `page.offset` | KILLED | G2 `:2753`（`['A','B'] != ['c']`） |
| V4 `return result` 永不写缓存 | KILLED | G2 `:2750` |
| V5 计数条件去掉 `f.root = ?`（连带 args） | KILLED-OTHER | 杀手是既有断言 `:2681`，不宣称证明新断言 |
| V6 `invalidate_library_query_cache` 空转 | **SURVIVED** | 写路径改写库文件，身份指纹仍换 key |
| V7 `self.identity = None` | **SURVIVED** | 显式 invalidate 仍在写路径清该库 |
| V8 ＝ V6＋V7 双旋钮同摘 | KILLED | G2 `:2766`（`3 != 4`）——反证该断言是活的 |

另有 1 次三旋钮尝试（再去掉 `search_cache_token` 段）因锚点在文件内出现 2 次被 assert 拦下、未落盘（无坏锚点）。8 试 6 灭 2 存活按实上报，未挑能灭的报。基线与每次还原后 rc=0，写回后逐字节 sha 复验等于 pristine；副本与其 pycache 目录本轮已删除。

## 五、同轮放弃的一条（不为凑数硬关）

L114（过户标记复用 `MAX_SIGNATURE_CHARS = 2048`）：条目指定的修法「逐行比较、超长行单独判不等」在现有整页布尔 API 下与现状行为不存在可观测差集 ⇒ 判别性测试不存在，保持开放。经验已写入 `PROJECT_CONTEXT.md`。

## 六、剩余量（磁盘实测，历史快照并存不合并）

- 开放 72 ＝ 可离线代码 **14** ＋ 设备/外部 44 ＋ 需产品决策 **1**（L1880）＋ 台账 13。
- 距四项终止条件还差 **15 条**：代码 14（L41/L42/L92/L106/L108/L115/L119/L122/L143/L153/L157/L161/L549/L797）＋ 决策 1。设备 44 保持不动（条件 2 已达成并继续保持）。
- 代码桶中仅 L92（欠读清单刷新）、L143（app.js 深读）、L157（第 2 半）、L161（测量形状改造）有离线推进空间，其余被条目自身「需真机证据/需样本/条目自设门」挡住。
- R128 预定：L161 内部追加 —— `tools/benchmark_large_library.py:653-662` 先后两段式计时改配对交错 A/B，主判据换 `reuses`/`creations`（守卫 `:671-672`）；属既有条目内部推进，不另立新项、不关闭 L161。
