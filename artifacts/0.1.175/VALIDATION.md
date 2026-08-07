# fnAudio 0.1.175 构建与测试记录

## 本地验证

- 63 个 Python 单元测试通过。
- 3 个 Node 回归脚本通过。
- Android `lintDebug` 与 `assembleDebug` 通过。
- FPK 外层 21 项、app.tgz 内层 110 项；正式包不含 `.pyc` 或 `__pycache__`。
- DSD 回归测试确认 DSF URL/MIME/资源大小来自源文件，并确认推送路径不会调用转码回调。

## NAS 真机验证（198.51.100.24）

- 已部署运行 manifest `0.1.175`，实际配置端口 `18081`。
- `/api/health` 和音乐库状态通过：228 首歌曲、5 首 DSD。
- 请求 `/upnp/media/<dsd-id>/Downtown.dsf?transcode=dsd_wav` 仍返回源文件：HTTP 206、`audio/x-dsf`、DSD 文件头 `DSD `，总大小 `145081232` 字节；未返回 WAV 头，也未改变采样格式。
- 当前仅 1 个 fnAudio server、1 个 MPD，未发现 zombie；旧版本回滚备份仍保留在 NAS。
- 测试机没有可发现的 USB DAC 或 UPnP Renderer，因此尚未完成真实硬件播放验收。

## 发布物哈希

见同目录 `SHA256SUMS`。
