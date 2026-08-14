# fnAudio 0.1.190 播放栈改进

## 本版改动

- 新增 AirPlay Receiver 生命周期服务：检测 `shairport-sync`/`nqptp`，使用进程 supervisor 管理启动、退出和有限重启。
- AirPlay 启停与 MPD/DAC 共用音频输出租约，避免两个服务同时抢占 ALSA 设备。
- 新增 `/api/airplay/control`，支持 `start`、`stop`、`restart`；`/api/airplay/status` 现在同时返回依赖、进程和输出租约状态。
- 保持 DSD 源码推送策略：DLNA/UPnP 不支持 DSD 时明确拒绝，不隐式转 PCM。
- 保持 USB DAC 稳定身份、ALSA `hw_params` 验证、热插拔恢复、MPD watchdog 与队列恢复逻辑。

## 验证

- Python 单元测试：97 项通过。
- UI 队列、移动端布局、Android bridge 静态测试继续通过。
- AirPlay 无二进制时会报告不可用，不会伪装成已启动；有其他输出租约时会拒绝启动。

## 已知限制

- 真机没有安装 `shairport-sync`/`nqptp` 时，AirPlay Receiver 仍不可用；安装后可通过 API 启动并观察状态。
- Native DSD、USB 热插拔和 DLNA Renderer 兼容矩阵仍需更多真实设备覆盖。
