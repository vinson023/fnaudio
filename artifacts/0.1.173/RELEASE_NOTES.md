# fnAudio 0.1.173 发布说明

本版集中改进 USB DAC、远程播放队列、DSD 推送和 Android 登录恢复。

- USB DAC/MPD 自然播放结束改由服务端事件推进队列，降低手机息屏或页面进入后台后无法播放下一曲的问题。
- 修复输出失败仍显示“正在播放”、播放按钮闪烁、进度回跳，以及直接 ALSA 启动缺少成功返回值的问题。
- 远程歌曲短时间重复加载会被去重；浏览器切换到 Android 或重新登录时先恢复 NAS 上的队列和播放状态，不会立即重新推送当前歌曲。
- DSD 推送统一转换为 96kHz/24bit WAV PCM，修正 URL、MIME、扩展名、协议描述和实际内容不一致导致的拒播。
- 对支持 `SetNextAVTransportURI` 的 DLNA Renderer 预装下一曲，提高后台连续播放成功率。
- Android 启动时自动验证并刷新 token，失败后尝试 longToken 和已保存密码，减少“无效的 token”页面。
- Android 最低版本由 8.0 扩展到 6.0，改善旧手机安装兼容性。

仍需真机确认：USB DAC 首帧、停止后不续播、长队列息屏连续播放、外部 DLNA 不支持 NextURI 时的后台推进，以及 Android 选择 USB DAC 后的通知栏/锁屏媒体卡片。本包为 Debug 签名 APK，不是正式商店签名版本。
