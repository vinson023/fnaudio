# fnAudio 文档索引

- `OFFLINE_ENGINEERING_0.1.222.md`：九项连续离线加固的完成范围、验证入口与硬件边界。
- `RESOURCE_LIMITS_20260811.md`：扫描、元数据、缓存和 FFmpeg 的资源预算、取消语义与恢复验证。
- `PLAYBACK_ERROR_TAXONOMY.md`：MPD/FLAC/seek/decoder/ALSA 错误类别、兼容字段与恢复策略。
- `PLAYBACK_API_COMPATIBILITY.md`：权威播放接口、旧 player/UPnP/DAC 入口的弃用策略与大模块拆分顺序。
- `LARGE_LIBRARY_BENCHMARK.md`：10 万曲 SQLite 分页与内存基准方法。
- `LIBRARY_CONNECTION_POOL.md`：曲库索引空闲连接复用开关的默认值、严格布尔取值口径、关闭即排空空闲句柄的保证与观测面。
- `LIBRARY_CURSOR_NULL_GROUPS.md`：浏览器游标续页面对 SQL NULL 标签组的可寻址边界、前瞻行锚点、降序末块残差与写路径归一/一次性迁移的分工。
- `LIBRARY_CHANGE_DETECTION.md`：inotify、generation、溢出回退与符号链接边界。
- `PLAYBACK_OUTPUT_POLICY.md`：输出适配器、upmpdcli 角色、硬件 Mixer 与 DSD 策略。
- `ANDROID_HTTPS_PINNING.md`：Android 自签名 HTTPS 的按连接 TOFU 指纹固定。
- `ANDROID_EMULATOR_TESTING.md`：Android API 35 模拟器的连接记录、TLS 固定与 Media3 自动化入口及验收边界。
- `FNOS_MUSIC_MEDIASESSION_RESEARCH_20260831.md`：trim.music 与飞牛 APP 的跨平台播放会话、MediaSession、后台保活和宿主桥接研究。
- `ANDROID_RELEASE.md`：正式 Android 签名构建、产物校验和密钥保管边界。
- `RELEASE_EVIDENCE_0.2.33.md`：0.2.33 历史 FPK 的校验和状态、源码 provenance 缺口和恢复规则。
- `FILE_PERMISSIONS_AND_PATH_BOUNDARIES.md`：私有/公开 mode、原子写、删除白名单与降权边界。
- `REAL_DEVICE_COVER_BACKFILL_0.1.225.md`：缓存封面写入 Tag 的根因、一次性回填迁移与内网机前后证据。
- `history/releases/UPDATE_0.1.172_TO_0.2.1.md`：0.1.172 至 0.2.1 的面向用户发布摘要。
- `external-acceptance.md`：设备与外部材料侧待办的唯一台账，含 45 条原文冻结块、固定编号与逐条处置计划。
- `REVIEW_ROUND_DISCIPLINE.md`：逐轮记账口径的唯一成文处——第五桶不计入终止分母、0-close 轮的记法、真机取证分档白名单、终局收口形式与 c1～c8 裁定落点；由 `src/tests/test_device_todos_migrated.py` 与 `TODO.md` 双向核对。
- `REAL_DEVICE_GOALS.md`：负责人常设指令（2026-09-22）下从逐轮目标移出的真机验收事项——固定编号 G01～G11、逐条真机口径、开工前置、与终止条件的关系和建议顺序；与 `external-acceptance.md` 共同构成「以后的目标」，由 `src/tests/test_real_device_goals_moved_out.py` 守护原文冻结。
- `FUTURE_GOALS.md`：负责人裁定（2026-09-23）下从本次逐轮目标移出的 Android 客户端审计面——迁出范围（43 个文件／9,695 行中点名的 4 枚已审计面）、移出后留下的账、与 `external-acceptance.md`／`REAL_DEVICE_GOALS.md` 的分工、启动专项审计的前置与记录规则；由 `src/tests/test_android_audit_scope_moved_out.py` 守护「移出≠删除≠关闭」。

## 当前权威文档

| 文档 | 作用 |
| --- | --- |
| `../README.md` | 项目入口、目录和验证命令 |
| `../PROJECT_CONTEXT.md` | 当前实现、功能、风险、测试和建议 |
| `../ARCHITECTURE.md` | 架构层次、模块、数据流和边界 |
| `../DECISIONS.md` | 已确认技术决策及其影响 |
| `../TODO.md` | 可离线推进的待办列表（设备／外部项已另册于 `external-acceptance.md`，需真机的长期观察项已另册于 `REAL_DEVICE_GOALS.md`） |
| `../CHANGELOG_AI.md` | AI 修改和验证记录 |
| `../RECOVERY.md` | 会话丢失后的恢复流程 |
| `../SOURCE_MANIFEST.sha256` | 当前源码文件哈希清单 |
| `SOURCE_INVENTORY.md` | 源码范围、归档范围和明确排除项 |

## 历史文档

`history/` 中的文件从 `E:\Codex\fnaudio-0.1.7` 原样复制，用于追溯实现过程：

- `MIGRATION_0.1.3.md`：播放架构迁移说明。
- `README_0.1.3_DEV.md`：早期开发说明和旧环境验证。
- `PHASE_1_2_TODO.md`：本机播放、格式和安装阶段记录。
- `PHASE_3_TODO.md`：DLNA 服务与 Renderer 阶段记录。
- `PHASE_4_TODO.md`：服务器端状态阶段记录。
- `PROJECT_CONTEXT_SOURCE_ANALYSIS_2026-08-06.md`：整理前对整个 `E:\Codex` 的完整分析快照。
- `components/PLAYBACK_ARCHITECTURE_0.1.4.md`：播放组件早期边界说明。
- `releases/UPDATE_*.md`：历史版本片段，当前收录源目录中存在的 `0.1.2`、`0.1.4` 至 `0.1.7`、`0.1.20` 至 `0.1.57`、`0.1.127` 至 `0.1.148`。

历史编号并不连续，表示原始目录本身缺少部分更新文档，不代表文件复制遗漏。

## 使用规则

- 当前状态以根目录文档为准。
- 历史文件不做内容修订，避免丢失当时语境。
- 新的发布说明应写入根 `CHANGELOG_AI.md` 或未来正式 `CHANGELOG.md`，不要继续创建大量零散 `UPDATE_*.md`。
- 每一轮改动（包括只改测试、脚本或文档）都必须在根 `CHANGELOG_AI.md` 与 `TODO.md` 标题后的扁平区顶部各留一条同日条目；只记一处视为未记录，`test_change_record.py` 会拒绝格式漂移和两份记录最新日期不一致。
- 记录条目保持单行、按日期倒序插入；不要重写 `## ` 之后的历史语境，也不要为补记录而改动既有结论。
