# fnAudio 0.1.201 App Center 生命周期记录

## 构建

- FPK：`artifacts/0.1.201/fnaudio-0.1.201-fnpack.fpk`
- Android Debug APK：`artifacts/0.1.201/fnaudio-android-0.1.201-debug.apk`
- FPK SHA-256：`8C5F550FED94D62489B7FEC382BE0FDE4F8BEE13D5B045CFA69C74E67D41F7C1`
- APK SHA-256：`F67955278F3774F5C7A34DBE1A9E8CA0F162129E67DD8CE8B6CFE539389052D0`
- 构建工具：`tools/fnpack.exe 1.2.3`；Android `lintDebug assembleDebug`

## 真机覆盖升级

- 目标：`vinson023.eu.org:5666`
- App Center 通过 NAS 文件选择器安装 `fnaudio-0.1.201-fnpack.fpk`。
- App Center 安装确认和更新过程完成后，应用列表显示 `fnaudio` 版本 `0.1.201`、状态 `running`。
- CLI 复核：`app list` 返回版本 `0.1.201`；CLI 直接安装被 App Center 自定义向导安全策略拒绝，因此没有绕过 UI。

## 播放队列复测

- 覆盖升级前后保留原有配置和播放会话。
- fnAudio 重开后当前队列显示 `536` 首；当前播放歌曲显示“已恢复播放设备”，进度继续变化。
- 真机 SQLite 中保存的队列为 536 个 ID，和前端显示一致。
- 本次只证明大队列恢复和覆盖升级链路；USB DAC 长时、热插拔、DSD 全矩阵、DLNA Renderer、Android 多机仍按 `TODO.md` 保持未完成。

## 回滚与恢复

若后续会话丢失，优先读取 `PROJECT_CONTEXT.md`、本文件和 `RECOVERY.md`，再使用 `artifacts/0.1.201/` 中的包复现。不要删除 fnOS 配置目录或播放数据库；覆盖升级应继续保留用户配置、MPD 输出和队列。
