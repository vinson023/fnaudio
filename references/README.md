# 音频播放器与平台参考源码

这些目录仅用于 fnAudio 架构研究，不会被打包进 fnAudio，也不会自动安装或运行参考项目。

## 已下载源码

| 目录 | 来源 | 用途 |
|---|---|---|
| `volumio3-backend` | `https://github.com/volumio/volumio3-backend` | Volumio 后端、插件管理、MPD、ALSA、upmpdcli、WebSocket/API |
| `volumio2-ui` | `https://github.com/volumio/Volumio2-UI` | Volumio 浏览、队列、播放器、设置、输出设备和响应式 UI |
| `volumio-plugins-sources` | `https://github.com/volumio/volumio-plugins-sources` | Volumio 插件实现和插件配置样例 |
| `volumio-plugins-sources-bookworm` | `https://github.com/volumio/volumio-plugins-sources-bookworm` | Volumio Debian 12/Bookworm 插件源 |
| `volumio3-os` | `https://github.com/volumio/volumio3-os` | Volumio 系统构建、服务和平台依赖 |
| `moode` | `https://github.com/moode-player/moode` | moOde 播放器、MPD/ALSA、音乐库、Renderer、后台守护进程 |
| `moode-docs` | `https://github.com/moode-player/docs` | moOde 音频基础设施和系统说明 |
| `mpd` | `https://github.com/MusicPlayerDaemon/MPD` | MPD 播放核心、输出插件、解码器、协议和配置 |
| `libmpdclient` | `https://github.com/MusicPlayerDaemon/libmpdclient` | MPD 客户端协议库 |
| `upmpdcli-source/upmpdcli-1.9.17` | `https://www.lesbonscomptes.com/upmpdcli/` | upmpdcli UPnP/OpenHome Renderer 源码 |
| `upmpdcli-source/libupnpp-1.0.3` | 官方 upmpdcli 下载页 | UPnP/OpenHome C++ 支持库 |
| `upmpdcli-source/libnpupnp-6.2.3` | 官方 upmpdcli 下载页 | UPnP 协议实现库 |
| `FNOS-API-upstream` | `https://github.com/heijiangangqin/FNOS-API` | 第三方 `trim-cli` REST 封装；仅作 fnOS 设备验收、日志和运维接口参考，不接入产品 |

Volumio、moOde、MPD 和 libmpdclient 使用浅克隆保存当前源码快照；upmpdcli 及其依赖使用官方源码压缩包保存。

本轮用于 0.1.173 审计的固定快照：

- `volumio3-backend`: `9938d7179e3b7c4e41f3e2d60c255985cff08fee`
- `volumio2-ui`: `557bb55c9918cce5571e57b99712b966cc4a42cb`
- `moode`: `f6db85f8db27f4189c481fdcc1e585e95212fb77`

缓存仓库由根 `.gitignore` 排除；提交中只保留固定提交号、分析结论和产品侧实现，不复制第三方源码。

## fnOS 真机侧工具与文档（trim-cli skill）

| 路径 | 入库 | 说明 |
|---|---|---|
| `tools/skill/` | 否 | 厂商工具投送，共 45 个文件：`bin/` 是六个平台的可执行体，约 49.8 MB；`scripts/` 是三个包装脚本。仓库不复制二进制，也没有为它改 `.gitignore`，只在本地保留 |
| `references/fnos-skill/` | 是 | 工具内 markdown 的字节级镜像，共 36 篇：`SKILL.md`、`manifest.json`、`entries/` 13 篇任务入口、`reference/` 15 篇模块文档、`reference/workflows/` 6 篇流程文档 |
| `tools/sync_fnos_skill_docs.py` | 是 | 镜像的同步与漂移校验：`--write` 刷新副本，`--check` 一旦发现缺失、改动或多余即以非零退出 |

镜像保留工具原本的层级结构，因为这些文档用 `./entries/...` 和 `../reference/...` 相对链接互指（当前 62 条），压平层级会让它们全部失效。

文档里的命令示例写作 `./scripts/trim-cli ...`，指的是未入库的包装脚本；在本机对应 `tools\skill\scripts\trim-cli.cmd` 或 `trim-cli.ps1`，二者只是转发到 `bin\trim-cli-windows-x64.exe`。

2026-09-25 起，上一代手抄文档 `references/SKILL.md` 与 `references/fnos-api/`（共 14 个文件）被移除。理由是它们与工具内文档同名却已经落后：`app-center.md` 手抄本 6.3 KB、工具内 19.1 KB，`media`、`network`、`photos`、`power` 四个模块整体缺失，`file-routing`、`device-validation`、`storage-dangerous-ops` 三篇在工具内已归入 `reference/workflows/`；而且仓库里已经没有任何文件引用这些手抄路径。此后由 `src/tests/test_fnos_skill_docs.py` 同时守住「镜像等于工具」和「手抄本不再回来」两件事。
## 分析文档

- `FNAUDIO_REFERENCE_ANALYSIS.md`：Volumio/moOde/MPD/upmpdcli 对 fnAudio 的详细改进方案。
- `FNOS_API_EVALUATION.md`：第三方 FNOS-API 与官方开放能力的边界、风险、可用场景和缓存提交号。
