# fnAudio 0.1.174 构建与测试记录

## 构建

- 工作树：`C:\path\to\fnAudio`
- Git 分支：`main`
- FPK：`tools\fnpack.exe build --directory C:\path\to\fnAudio\src`
- Android：`android-client\gradlew.bat :app:lintDebug :app:assembleDebug`
- 版本：根 `VERSION`、FPK manifest、前端缓存键、Android `versionName` 均为 `0.1.174`；Android `versionCode=174`、`minSdk=23`、`targetSdk=36`。

## 本地验证

- 62 个 Python 单元测试通过。
- 3 个 Node 回归脚本通过：队列/专辑序号、移动端布局、Android bridge/CGI 认证。
- `src/cmd/main` 通过 `/bin/bash -n` 语法检查。
- Android Lint 与 Debug APK 构建通过。
- FPK 外层 21 项、app.tgz 内层 110 项；正式包不含 `.pyc` 或 `__pycache__`。

## NAS 真机验证（198.51.100.24）

- 已备份旧安装：`/vol1/1000/fnaudio-backup-0.1.172-before-0.1.174-20260807.tgz`。
- 运行 manifest 为 `0.1.174`，实际配置端口 `18081`。
- 旧 18080 服务与 MPD 已清理；当前仅 1 个 fnAudio server、1 个 MPD、无 zombie，只有 18081 监听。
- 假设存在一个遗留 `server.py` 进程时，启动脚本记录并清理该 PID 后再启动新服务，验证通过。
- `/api/health`、音乐库状态（228 首、5 首 DSD）、浏览器 load/pause、队列跨 stop/start 持久化通过。
- DSD 媒体 HEAD/Range 返回 `audio/wav`；WAV fmt 头确认 2 声道、96000 Hz、24 bit，缓存状态为 ready。
- 当前设备未发现 USB DAC 或 UPnP Renderer，真实硬件连续播放仍待验收。

## 发布物哈希

见同目录 `SHA256SUMS`。
