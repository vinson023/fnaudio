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

## 分析文档

- `FNAUDIO_REFERENCE_ANALYSIS.md`：Volumio/moOde/MPD/upmpdcli 对 fnAudio 的详细改进方案。
- `FNOS_API_EVALUATION.md`：第三方 FNOS-API 与官方开放能力的边界、风险、可用场景和缓存提交号。
