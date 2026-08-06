# fnAudio 0.1.4 更新说明

0.1.4 是 MPD / upmpdcli 可选后端测试版，不替换现有浏览器播放、UPnP/DLNA 推送和 ALSA 输出。

## 播放核心

- 新增 `mpd_output` 输出插件。
- MPD 通过统一播放核心接入，支持加载歌曲、播放、暂停、停止、上一曲、下一曲、seek 和音量控制。
- 前端仍只选择播放目标并发送统一控制命令，不直接处理 MPD 协议。

## 可选后端探测

- 新增 MPD 探测接口：`GET /api/mpd/status`。
- 新增 upmpdcli 探测接口：`GET /api/upmpdcli/status`。
- `GET /api/playback/targets` 会返回 MPD 可选目标和 upmpdcli 探测状态。
- 如果系统没有安装 MPD 或 upmpdcli，应用仍可正常使用现有播放方式。

## DLNA / OpenHome 后续准备

- 新增 upmpdcli renderer 探测模块，为后续让 fnAudio 作为 UPnP/OpenHome Renderer 做准备。
- 现阶段 upmpdcli 只做能力探测，不自动启动，也不强制依赖系统安装。

## 应用信息

- 版本号更新为 `0.1.4`。
- 应用中心开发者、发布者、维护者统一改为 `fnaudio`。
