# Android 正式发布

## 目标

`tools/build_android_release.ps1` 是唯一的正式 APK 构建入口。它不创建、不导出、也不保存签名密钥；构建前要求调用方提供已有的发布 keystore，构建后验证 APK 签名、版本与 SHA-256，再归档到 `artifacts/<VERSION>/`。

## 签名材料

以下四项只能放在受控构建机的环境变量或 CI Secret 中，禁止写入 Git、`local.properties`、文档示例的真实值或构建产物：

- `FNAUDIO_RELEASE_STORE_FILE`
- `FNAUDIO_RELEASE_STORE_PASSWORD`
- `FNAUDIO_RELEASE_KEY_ALIAS`
- `FNAUDIO_RELEASE_KEY_PASSWORD`

密钥文件必须有离线加密备份。Android 安装器使用签名证书决定升级身份，丢失原 keystore 将无法对已安装的正式版本进行覆盖升级。

## 本地构建

```powershell
Set-Location C:\path\to\fnAudio
$env:ANDROID_SDK_ROOT = 'E:\Codex\android-sdk'
$env:FNAUDIO_RELEASE_STORE_FILE = 'E:\secrets\fnaudio-release.jks'
$env:FNAUDIO_RELEASE_STORE_PASSWORD = '<store password>'
$env:FNAUDIO_RELEASE_KEY_ALIAS = 'fnaudio'
$env:FNAUDIO_RELEASE_KEY_PASSWORD = '<key password>'
.\tools\build_android_release.ps1
```

脚本会执行 `:app:assembleRelease`，使用 Android Build Tools 的 `apksigner verify --verbose --print-certs` 验签，并用 `aapt dump badging` 比对 `VERSION` 和 APK `versionName`。成功后生成：

```text
artifacts/<VERSION>/fnaudio-android-<VERSION>-release.apk
artifacts/<VERSION>/SHA256SUMS
```

Debug APK 与 Release APK 的签名身份不同，不能把 Debug APK 当作正式升级包。没有发布 keystore 时，脚本会在任何构建副作用之前失败，这是预期的安全保护。

## CI

CI 默认只构建 Debug APK，避免把签名材料暴露给普通 Pull Request。受保护发布工作流在配置远程仓库和 Secret 后才可以调用此脚本；当前本地仓库未配置 remote，不能宣称已经完成云端签名发布。
