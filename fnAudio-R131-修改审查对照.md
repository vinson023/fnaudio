# fnAudio R131 修改审查对照（不入库）

轮次：R131（第 38 轮）｜基线 HEAD `7595cbb` ｜本轮两笔提交：`a770dc3`（代码＋测试）、`e6bca79`（三份根文档＋清单）
净结果：关闭既有代码待办 1 条（原 TODO L122「热页拷贝成本」），新立 0 条。

## 改了哪些文件

| 文件 | 变化 | 作用 |
|---|---|---|
| `src/app/server/metadata_service.py` | +31 / -8 | 把「每次命中重做」的三件事挪到冷读 |
| `src/tests/test_metadata_service.py` | +97 / -0 | 三条判别性用例＋一个共享 fixture |
| `TODO.md` / `CHANGELOG_AI.md` / `PROJECT_CONTEXT.md` | L2 插入、勾掉原 L122 | 记录与账本 |
| `SOURCE_MANIFEST.sha256` | 2 行 | 上述两个源文件的新摘要 |

## 逐 hunk 审核（源码）

### H1 `metadata_service.py:1895-1903`（新增 `_overlay_artwork_id`）
- 前：折叠 artwork id 的写法 `_provider_text(value, 128).strip().lower()` 只存在于合并循环里，每次命中每行重跑。
- 后：定义一次（同一边界、同一折叠顺序），冷读调用它，热路径变成查表。
- 审核要点：语义与旧表达式逐字等价，只是搬到冷读；返回必为 `str`，所以缓存里存的是成品。

### H2 `metadata_service.py:4347-4352`（行身份归一化改成一趟）
- 前：`ids = list(dict.fromkeys(track_id for track_id in (_page_track_id(item) for item in items) if track_id))`
- 后：`track_ids = [_page_track_id(item) for item in items]` ＋ 由它派生 `ids`。
- 审核要点：`_page_track_id` 的返回值、空值过滤、去重顺序全部未变；变的是只算一遍。

### H3 `metadata_service.py:4358`（`item_by_id` 复用同一趟）
- 前：`{track_id: item for item in items if (track_id := _page_track_id(item))}`（第二次归一化）
- 后：`{track_id: item for track_id, item in zip(track_ids, items) if track_id}`
- 审核要点：`zip` 同序、键值配对与旧推导式一致；重复 id 的后写覆盖语义不变。

### H4 `metadata_service.py:4403-4411`（冷读就把投影做完）
- 前：`overlay = {"artwork_id": row["artwork_id"] or "", "fields_json": row["fields_json"] or ""}`
- 后：`overlay = {"artwork_id": _overlay_artwork_id(...), "projected": project_match_fields(row["fields_json"] or "")}`
- 审核要点：这是本轮真正的收益点，也是唯一的形状变更 —— 缓存条目不再有 `fields_json`。缓存读写的双向 `copy.deepcopy`（`:2020`、`:2037`）保持不动，所以「缓存里存成品」不等于「缓存里的东西可被写坏」。

### H5 `metadata_service.py:4421-4427`（命中路径退化为查表）
- 前：`projected = project_match_fields(row.get("fields_json"))`；`for item in items: track_id = _page_track_id(item)`
- 后：`projected = row.get("projected")`；`for index, item in enumerate(items): track_id = track_ids[index]`
- 审核要点：若某行 `projected` 为空则跳过，与旧的「解码结果为空则跳过」同口径。

### H6 `metadata_service.py:4438-4440`（合并循环不再重算折叠）
- 前：`row_artwork_id = _provider_text(row.get("artwork_id") if row else "", 128).strip().lower()`
- 后：`row_artwork_id = row.get("artwork_id") if row else ""`
- 审核要点：`valid_artwork_id` 的守卫原样保留在下一行；因为存进来的已经是折叠成品，输出不变。等价性已用同一曲库逐字节对拍（68,706 B、sha256 相同）。

## 逐 hunk 审核（测试）

- `test_metadata_service.py:2271` `_seed_page_overlay_fixture`：造 2 行，各带一条 `auto` 匹配与一个大小写混杂的 `artwork_id`（`"AB"*32`），故意让折叠可见。
- `:2308` 计数用例：用 `side_effect` 记录 `project_match_fields` 的调用次数 —— 冷读必须恰等于行数，两次热页必须零新增；同时断言三次服务结果全等、字段值与折叠后的 artwork id 正确。
- `:2341` 键集合用例：断言缓存条目恰为 `["artwork_id", "projected"]`、不含 `fields_json`、值已是折叠成品。
- `:2353` 身份用例：断言每页 `normalize_track_id` 调用次数恰等于行数。
- 判别性来自「计数」而不是「输出」：只把改动回退成任意一种旧写法，用例立刻红。

## 变异矩阵（仓库外副本 `%TEMP%\r131c2`，跑完已删）

控制组先绿（rc=0、ran=3、零失败），随后 6 个变异体 6/6 KILLED，收尾 `restored=True`：
M1 回退成缓存存 `fields_json` → 计数 6≠2 ＋ 键集合双杀；M2 恢复 `item_by_id` 现算 → 6≠2（仅身份用例捕获）；
M3 存了投影仍每次重解 → 4≠2（仅计数用例捕获）；M4 完全不折叠／M5 折叠但不 casefold → 大小写串不等；M6 同时保留 `fields_json` → 键集合失败。

## 门禁与取证

- `artifacts/offline-20260921-round203.log`（mtime 05:48:22，晚于本轮全部文档编辑）：`Ran 2483 tests in 111.595s`、`OK (skipped=2)`、0 条 FAILED、含 passed 的 JS 结果行 73、三条新用例位于 L1786/L1790/L1794、外层捕获 `GATE_EXIT=0`。
- `SOURCE_MANIFEST.sha256`：WinPS 5.1 幂等复跑字节不变，逐文件复算 707/707 MATCH、0 missing、0 重复。
- 设备段 L816..L1874 与 HEAD 逐字一致（53,981 字符），本轮未触碰；未改 `.gitignore`；未 push。
- 收口后开放 69 ＝ 代码 11 ＋ 设备/外部 44 ＋ 需决策 1 ＋ 台账 13；距终止条件差 12 条（代码 11 ＋ 决策 1）。
