# fnAudio 文档索引

## 当前权威文档

| 文档 | 作用 |
| --- | --- |
| `../README.md` | 项目入口、目录和验证命令 |
| `../PROJECT_CONTEXT.md` | 当前实现、功能、风险、测试和建议 |
| `../ARCHITECTURE.md` | 架构层次、模块、数据流和边界 |
| `../DECISIONS.md` | 已确认技术决策及其影响 |
| `../TODO.md` | 当前唯一有效待办列表 |
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
