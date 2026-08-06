# fnAudio 0.1.3 重构迁移说明

0.1.3 的目标是先把现有能力拆成清晰边界，再评估 MPD 或 upmpdcli 是否适合作为可选后端。

## 四层边界

1. 播放核心：`app/server/playback/core.py`
   - 负责队列、当前曲目、上一曲、下一曲、循环、随机、进度、播放状态和播放会话。
   - 通过输出插件接口获取能力和状态。

2. 输出插件：`app/server/playback/`
   - `browser_output.py`：浏览器播放目标。
   - `dlna_push_output.py`：外部 UPnP/DLNA 设备推送目标。
   - `alsa_output.py`：本机 USB DAC / 声卡输出目标。
   - 后续可继续增加 `airplay_output.py`、`snapcast_output.py`、`mpd_output.py` 等。

3. DLNA 子系统：`app/server/dlna/`
   - `control_point.py`：搜索和控制外部 DLNA 渲染器。
   - `media_server.py`：向 DLNA 设备暴露本地音乐资源和 DIDL-Lite 元数据。
   - `profiles.py`：按设备能力决定 MIME 和 protocolInfo。
   - `renderer.py`：预留 fnAudio 自己作为 DLNA Renderer 的入口。

4. 前端 UI：`app/ui/app.js`
   - 只选择播放目标、显示状态、同步队列、调用统一 API。
   - 不再直接知道 UPnP SOAP、ALSA 命令或浏览器以外目标的实现细节。

## 已完成的迁移

- 新增统一播放接口：
  - `GET /api/playback/targets`
  - `POST /api/playback/queue`
  - `POST /api/playback/load`
  - `POST /api/playback/control`
  - `GET /api/playback/status`
  - `GET /api/playback/core`
- 前端设备选择、推送播放、上一曲、下一曲、循环、随机、暂停、停止、进度拖动已经改为调用统一播放接口。
- `server.py` 中原来的 UPnP/DLNA 搜索、SOAP 控制、DIDL-Lite 资源生成已经迁移到 `app/server/dlna/`。
- `server.py` 中原来的 ALSA / USB DAC 播放实现已经迁移到 `app/server/playback/alsa_output.py`。
- 旧的 UPnP/DAC 推送和控制接口保留为兼容入口，但内部已转发到统一播放 API。

## 仍保留在入口服务中的内容

`server.py` 目前仍保留：

- HTTP 路由。
- 音乐库扫描和查询。
- 配置读取与保存。
- 转码缓存和媒体流接口。
- 对 DLNA/ALSA 模块的少量包装函数。

这些内容不是输出实现本身，后续如果继续细拆，可以再把音乐库、配置、转码服务单独抽为模块。

## 验证记录

本地验证：

- Python 服务端模块编译通过。
- 前端 `app.js` 语法检查通过。
- `playback` 和 `dlna` 包可以正常导入。

测试环境验证：

- 测试地址：`198.51.100.24`
- 应用中心重启后 `fnaudio` 状态为 running。
- `/api/health` 返回正常。
- `/api/library/status` 返回音乐库可读，当前测试库 226 首。
- `/api/playback/core` 返回三类输出插件：`browser`、`dlna_push`、`alsa`。
- `/api/playback/targets` 能返回本机播放和 DLNA 设备 `DESKTOP-EEIDGH9`。
- `/api/playback/queue`、`/api/playback/load`、`/api/playback/control` 本机目标基础流程正常。

## 后续评估方向

- MPD：适合承担本机 DAC / 声卡播放核心，尤其是队列、输出设备、gapless 和格式支持。
- upmpdcli：适合把 MPD 暴露成 UPnP/OpenHome Renderer。
- Volumio/moOde 的参考价值：输出后端和播放状态机分离、DLNA 控制点/渲染器/媒体库分离，而不是前端直接管理协议细节。
