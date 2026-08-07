# fnAudio 0.1.175

## 本版重点

- DSD 的 DLNA MediaServer 和 Renderer Push 改为原始 DSF/DFF 直推，不再强制转码为 96 kHz/24 bit WAV。
- DSD URL 使用源文件扩展名，MIME 使用 `audio/x-dsf` 或 `audio/x-dff`，资源大小使用源文件大小。
- 浏览器播放仍可显式请求 `dsd_wav` 转码；这只用于浏览器兼容，不影响 DLNA 源码推送。
- 继承 0.1.174 的旧服务实例清理、MPD 生命周期和播放状态恢复修复。

## 已知限制

- Renderer 必须支持原生 DSD；不支持的设备会拒绝源码 DSD，这是本版的明确行为，不再静默转码。
- 尚未在真实 USB DAC、DLNA Renderer 和多型号 Android 设备上完成硬件矩阵验收。
