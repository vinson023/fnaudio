# App Center 生命周期回归：0.1.203

日期：2026-08-10  
设备：`vinson023.eu.org:3100` / fnOS App Center `:5666`

## 覆盖升级结果

- 通过 fnOS App Center 手动安装流程提交 `artifacts/0.1.203/fnaudio-0.1.203-fnpack.fpk`。
- 未清除已有配置、音乐库、播放队列或 DAC 选择。
- 通过 SSH 只读确认服务进程来自 App Center payload，HTTP 响应头为：
  `Server: fnAudio/0.1.203 Python/3.12.4`。
- `/api/health` 返回 `ok=true`。

## 数据与播放状态

- 音乐库：`/vol1/1000/music`，536 首，其中 DSD 2 首。
- 服务端逻辑队列：20 首。
- MPD 原生队列：`playlistlength=20`，当前为 STOPPED，未被升级过程清空。
- 输出设备：TEAC UD-301，稳定 ID 为
  `usb:0644:804a:00160000386ca1d14e45282720120016:dev0`。
- ALSA：`hw:CARD=UD301,DEV=0`。
- Native DSD：`native_dsd_verified=true`，`dsd_mode=native`，`dop=false`。
- 当前 underrun：`count=0`。
- 新增 MPD 解码错误分类字段存在：`decoder_errors.count/items/last_category/last_message`，本次回归为 0。

## 本次确认的边界

本记录证明 0.1.203 已完成一次真实 App Center 覆盖安装并保留运行数据；它不替代小时级播放、息屏连续播放、物理热插拔、外部 DLNA Renderer、Android 多机型和正式签名包验证。上述项目继续保留在 `TODO.md` 的 P0 清单中。

