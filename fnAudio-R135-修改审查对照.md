# fnAudio R135 修改审查对照（本轮）

> 提交：`0ab3ced` docs: register the R135 state_store and dlna renderer deep-read round
> 上一提交：`4a4ee61`（R134）。本轮为**文档-only 登记轮**：净关闭 0、新立 0、零源改动、未刷 SOURCE_MANIFEST、未做变异证明（无对象）。

## 变更总览
| 文件 | 变更 | 说明 |
|---|---|---|
| `CHANGELOG_AI.md` | L2 插入 2 行（R135 记录 + 收口记录） | 内容行 6737→6739，尾 9LF、0CR 不变 |
| `PROJECT_CONTEXT.md` | L2 插入 1 行（R135 方法论） | 内容行 6164→6165，尾 8LF、0CR 不变 |
| `TODO.md` | **未动** | 沿用 R132/R134 先例：0-close 登记轮只在 CHANGELOG/CONTEXT 插行，TODO 保持 2221 行/开放 68（代码 10＋设备 44＋决策 1＋台账 13）|
| 生产代码 / SOURCE_MANIFEST | **未动** | manifest 仍 707 条、sha `22b81b17…df3f` 逐字节原样 |

## Hunk 1 — CHANGELOG_AI.md（在 L1 标题与旧 L2「R134」之间，新增 L2、L3）
```diff
   # fnAudio 变更日志（AI）              ← L1（上下文，未改）
+ - 2026-09-21 — R135 深读登记轮 ……（本轮取证 + 逐条判定 + state_store/renderer 两面深读，见下全文）   ← 新 L2
+ - 2026-09-21 — R135 收口／终跑／清单 ……（round208 门禁、格式校验、git add 范围、三问未回话，见下全文） ← 新 L3
  - 2026-09-21 — R134 深读登记轮 ……      ← 旧 L2，下移为 L4（未改）
  - 2026-09-21 — R134 收口／终跑／清单 …… ← 旧 L3，下移为 L5（未改）
```

新 L2 全文：
> - 2026-09-21 — R135 深读登记轮（净关闭 0 条、新立 0 条、零源改动）：接管后先复算磁盘而非引用旧正文 —— HEAD `4a4ee61`（R134）、分支 `main`、无 remote、暂存空、被跟踪 0 modified ✓ `.git` 下 MERGE_HEAD/CHERRY_PICK_HEAD/REVERT_HEAD/BISECT_LOG/rebase-merge/rebase-apply/sequencer 全部不存在 ✓ `TODO.md` 内容行 2,221／尾 4 LF／0 CR、开放 68；四桶按节边界独立复扫（L803 落在 L791「持续目标推进（无需真机）」节内、属代码桶但为设备性质；L2080「飞牛 APP 原生同等能力」落在 L1896「当前持续优化目标」块、非可离线代码项）得 **代码 10（L47/48/98/112/114/121/128/149/159/803）＋ 设备/外部 44（L818–L1876）＋ 需决策 1（L1887）＋ 台账 13 ＝ 68**，四桶数学通过 ✓ 逐条读完 10 项代码待办，判定本轮无一可凭盘上自证关闭、且不硬凑：L47/L48/L112/L114/L121/L128/L159 各被其自设取证门挡住，R129 已实测该测试机无 SMB、曲库仅 6 行、`metadata_enabled=false`、全盘 `*.cue` 为 0，答不了这些门 ✓ L803 桶归属存争议，移设备段须负责人裁定（先例 R121），**不得自移** ✓ 剩 L98/L149 为纯深读债（关闭条件是「剩余欠读面全部读完」，跨多轮）✓ 本轮按 L98 关路口径做真实离线深读两面：`state_store.py`（本轮接管前执行方读完，判定无缺陷 —— `_STATE_WRITE_LOCK` RLock + `BEGIN IMMEDIATE` + `busy_timeout=15000` 三件套自洽、`_revision` CAS 有界、`_trim_*` 有界、L453-456 无单字段阈但有 2 MiB 总阈 raise 兜底属刻意设计）与 `src/app/server/dlna/renderer.py` 442 内容行全模块读完 —— `_safe_position` 对 NaN/inf/负/超长字符串均有兜底、`bounded_next_queue` 溢出计数封顶 1e9、`snapshot()` 以 `status_generation != _load_generation` 防陈旧快照外泄、`_backend_active_observed` 在 STOPPED 分支复位为 False 对重复 STOPPED 幂等、`set_volume` 拒绝 bool/非整/越界、`command("next")` 于锁外 `set_uri`+`play` 避免持锁触发监听器、`_schedule_backend`/`take_latest` 的 latest-wins 合并与线程创建失败时释放 `_backend_worker_active` 闩锁均自洽，判定无缺陷，未改源、未刷清单（`SOURCE_MANIFEST.sha256` 保持 707 条、sha `22b81b17b050673889bdf036f9b115e9154c6b3642651fa349d11deefcb8df3f` 逐字节原样）✓ 本轮文档-only：**不做变异证明，也不声称做过** —— 零源改动没有可变异的对象。

新 L3 全文：
> - 2026-09-21 — R135 收口／终跑／清单（一笔文档-only 提交）：本轮零源改动，门禁数值应当与 R133/R134 相同，故先跑前置复现 `artifacts/offline-20260921-round208-prefix.log` 实测 `Ran 2483 tests`／`OK (skipped=2)`／0 条 `FAILED`／JS 侧含 `passed` 的结果行 73 ✓ 再落两份根文档（CHANGELOG 两条 R135、CONTEXT 一条，均插在 L2、最新在前）✓ 最后以同一条令产出本轮终跑 `artifacts/offline-20260921-round208.log`，退出码须为 0 且逐项复现上述四值，任何偏离即本轮不算收口 ✓ 终跑 log mtime 晚于本轮全部文档编辑 ✓ 门禁未改 `SOURCE_MANIFEST.sha256`（前后 sha 相同、707 条）✓ `git diff --check` 通过（本轮仅文档插入、无尾随空白）✓ 格式校验器实测 TODO 内容行 2,221 不变（本轮未动 TODO）、CHANGELOG 内容行 6,739（6,737＋2）、CONTEXT 内容行 6,165（6,164＋1），尾 LF 4／9／8、0 CR，本轮 R135 记录位于两文件最前、编号不与任何既有轮次重复，四桶 68＝10＋44＋1＋13 复算通过 ✓ 校验器与全部 %TEMP% 脚本用完即删 ✓ 未跟踪项（artifacts、music、_external、references、tools、根级 offline-*.log、审查对照.md、.gradle-user）一律不入库，本次 `git add` 只列 CHANGELOG 与 CONTEXT 两份文档 ✓ 提交后代码桶仍 10、需决策仍 1，距四项终止条件合计剩 11 条 ✓ 连续第三轮 0-close（R132/R134/R135）如实暴露：结构性卡点是负责人三项未回话 —— (一) L1887 封面磁盘缓存 `allow_disk=False` 口径、(二) L803 是否移设备段、(三) 是否正式豁免「每轮净关闭 ≥ 1」铁律；这三问不得代答，在拿到回话前继续以深读登记轮维持「不造浅关闭」。

## Hunk 2 — PROJECT_CONTEXT.md（在 L1 与旧 L2「R134 并发写角度」之间，新增 L2）
```diff
   # fnAudio 项目上下文（AI）            ← L1（上下文，未改）
+ - 2026-09-21： 纯读取的深读登记轮一旦连续……（R135 方法论，见下全文）  ← 新 L2
  - 2026-09-21： 登记「并发写」「常驻循环」……（R134）                    ← 旧 L2，下移为 L3（未改）
```

新 L2 全文：
> - 2026-09-21： **纯读取的深读登记轮一旦连续，就要把它当成结构性信号上报，而不是当成可无限复制的常规轮次**（R135 实据：R132/R134/R135 三轮都是 0-close 文档轮，本轮读完 `state_store.py`＋`renderer.py` 两个大面仍拿不下一条可盘上自证关闭的代码待办 —— 因为剩下 10 条里 7 条卡在负责人自己设的取证门（真机/样本/产品判断）、1 条是桶归属争议（L803）、2 条是跨多轮的深读债（L98/L149）。深读轮的产出是「证明某面无缺陷＋把欠读面集合缩小」，它天然满足反增长里的「新立 ≤ 关闭＝0」和「不硬凑」，却违反「每轮净关闭 ≥ 1」，这不是执行失败，是终止条件与该铁律在盘上无更多可离线关闭项时彼此打架。可迁移做法：连续 0-close 时把张力点名交给负责人三问（是否授权多轮纯深读债、是否豁免 ≥1、L803/L1887 怎么定），既不偷换成浅关闭，也不因「反正关闭不了」而停手不读。）。

## 逐项取证依据（为何本轮 0-close）
- 磁盘复算：main/HEAD 提交前 `4a4ee61`、无 remote、无 merge/rebase/cherry-pick/sequencer 残留、暂存空、被跟踪 0 modified。
- TODO 2221 行/尾4LF/0CR、开放 68；四桶按节边界独立复扫 = 代码 10 / 设备 44 / 需决策 1(L1887) / 台账 13。
- 10 条代码待办无一可盘上自证关闭：7 条卡自设真机/样本/产品门（R129 实测测试机无 SMB、曲库 6 行、metadata_enabled=false、全盘 cue=0）；L803 桶归属待裁；L98/L149 跨多轮深读债。
- 本轮真实深读两面：`state_store.py`（接管前执行方读完，无缺陷）＋ `dlna/renderer.py` 442 行全读完（`_safe_position` 兜底、`bounded_next_queue` 封顶、`snapshot` generation 防陈旧、`_backend_active_observed` STOPPED 幂等、`set_volume`/`set_mute` 边界、`command(next)` 锁外派发、`_schedule_backend` latest-wins + 线程失败释放闩锁，均自洽，无缺陷）。
- 门禁 round208：exit 0 / `Ran 2483 tests` / `OK (skipped=2)` / 0 FAILED / JS passed 73；前置 round208-prefix 同值；终跑 mtime(08:04:52) 晚于文档编辑(08:00:10)。
- 格式校验器 PASS；全部 r135_ 临时脚本自删，TEMP 净；无 .new/.orig/.rej（排除 _external/.git）；未跟踪项一律未入库。

## 连续 0-close 张力（须负责人定夺，不得代答）
R132 / R134 / R135 连续第三轮 0-close。盘上已无「可离线自证关闭」的代码待办，「每轮净关闭≥1」铁律与终止条件在当下互斥。三问未回话：(一) L1887 封面磁盘缓存 allow_disk=False 口径；(二) L803 是否移设备段；(三) 是否正式豁免 ≥1 或授权若干轮专攻纯深读债。
