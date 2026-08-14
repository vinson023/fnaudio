# fnAudio 0.1.172 至 0.2.1 更新摘要

本阶段完成了播放链路、元数据、移动端与发布工程的系统性改进。

- 统一浏览器、Android、本机、USB DAC 与 DLNA/UPnP 的播放状态、队列、循环、随机与恢复逻辑。
- 优化 USB DAC 的能力识别、稳定身份、热插拔去抖、故障恢复和高频状态刷新；DSF/DFF 维持 Native DSD/DoP 优先策略。
- 增加 APE、CUE+APE、WAV、DSF/DFF 等格式支持与安全 Tag/封面写回；元数据补全优先服务当前播放歌曲。
- 支持 DLNA Renderer 自动下一曲、状态回传、设备能力识别与 DSD 原始资源推送。
- Android 使用 Media3 MediaSession 管理通知栏、锁屏、蓝牙媒体键和远程输出控制；改善连接历史、HTTPS、自签名证书及 WebView 封面缓存。
- 封面缩略图采用目录/专辑去重、持久缓存、内存缓存和低优先级可取消预热，避免影响播放与转码。
- 应用中心支持端口配置与冲突检测；所有 FPK 均通过原生 fnpack 构建和包内校验。
- 0.2.1 修复顶部简介被初始视图渲染覆盖的问题，并将默认简介统一为“飞牛私人音乐库”。

真实 USB DAC、DoP-only DSD、DLNA Renderer、AirPlay 与 Android 多机后台行为仍需按 `TODO.md` 的 P0 清单在物理设备上验收。
