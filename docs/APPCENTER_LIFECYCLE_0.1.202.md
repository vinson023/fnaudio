# fnAudio 0.1.202 真机验收记录

## 构建产物

- FPK：`artifacts/0.1.202/fnaudio-0.1.202-fnpack.fpk`
- APK：`artifacts/0.1.202/fnaudio-android-0.1.202-debug.apk`
- FPK SHA-256：`BA7A84C62AE1FC59F8781CEC2A5C0549AFB3C4D6080AE250930FAA8FBC1268DA`
- APK SHA-256：`1C26EE2C4D19C0731319A5C9DF808E97B5BB94F199C9DCEDE8517FC9A0BFB153`

## App Center

- 目标：`vinson023.eu.org:5666`
- 安装方式：App Center「手动安装」上传 FPK，并确认未经验证应用提示。
- 结果：应用中心显示 `fnaudio` 版本 `0.1.202`，状态 `running`。
- 运行服务响应头：`Server: fnAudio/0.1.202 Python/3.12.4`。

## DSD 源码播放

- 设备：TEAC UD-301，稳定标识 `usb:0644:804a:00160000386ca1d14e45282720120016:dev0`。
- DSF：`NEW/Lynyrd Skynyrd - Simple Man.dsf`，API 返回 `ok: true`，MPD `audio: dsd64:2`。
- DFF：`test/01 分手說愛你.dff`，API 返回 `ok: true`，MPD `audio: dsd64:2`。
- `/proc/asound/card3/stream0` 显示 `S32_LE DSD_U32_BE` 接口 Running。
- `native_dsd_verified: true`、`server_transcode: false`、`underrun.count: 0`。
- 本轮没有启用 PCM fallback；DSF/DFF 均为源码 DSD 推送。

## 生命周期脚本

`install_callback`、`upgrade_callback`、`config_callback` 已兼容扁平安装布局 `/vol1/@appcenter/fnaudio/ui`，不再强制写入不存在的 `target/ui/service_port.json`。历史日志中的旧版本报错属于升级前记录，新版本需继续观察后续安装日志。

## 停止/启动闭环

- CLI 停止：`app stop fnaudio --yes` 返回 `Stopped app fnaudio`。
- CLI 启动被 fnOS 依赖保护拒绝，返回 `dependency app changes that require App Center UI`；这不是应用启动失败，而是平台要求通过 UI 执行依赖变更。
- 通过 App Center「已安装」页面点击「启用」完成启动，随后 CLI 查询状态为 `running`、版本为 `0.1.202`。
- CGI 页面返回 HTTP 200，说明应用中心代理入口已恢复；未把代理层的 `Server: nginx` 误当作 fnAudio Python 服务头。

## 尚未完成

1. DAC 长时间播放、连续 20 首的长周期版本、热插拔恢复和息屏后台仍需完整硬件矩阵。
2. DLNA Renderer、Android 多机型后台通知和正式签名发布包仍需真机验收。

## 配置边界回归

- `/api/config/library` 对端口 `1000`、`65536` 和不存在目录返回 HTTP 400。
- 使用现有音乐目录和端口 `18080` 保存返回 `restart_required=false`。
- 回归后端口仍为 `18080`，音乐库仍为 536 首，现有 20 首队列未改变。
