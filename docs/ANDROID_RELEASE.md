# Android 正式发布

## 目标

`tools/build_android_release.ps1` 是唯一的正式 APK 构建入口。它不创建、不导出、也不保存签名密钥；构建前要求调用方提供已有的发布 keystore，构建后验证 APK 签名、版本与 SHA-256，再归档到 `artifacts/<VERSION>/`。

## 签名材料

keystore 已经生成并落在本机：

| 项 | 值 |
| --- | --- |
| keystore | `.secrets/fnaudio-release.jks`（PKCS12、RSA 4096、有效期 30 年） |
| alias | `fnaudio` |
| 证书 DN | `CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN` |
| 证书 SHA-256 | `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59` |
| 密码 | `.secrets/release-signing.env` 的 `FNAUDIO_RELEASE_STORE_PASSWORD`／`_KEY_PASSWORD` |

`.secrets/` 已在 `.gitignore` 中排除，既不进 Git 也不进 `SOURCE_MANIFEST.sha256`（清单只扫 `src/` 与 `android-client/`）。以下四项只以环境变量形式传到 Gradle：

- `FNAUDIO_RELEASE_STORE_FILE`
- `FNAUDIO_RELEASE_STORE_PASSWORD`
- `FNAUDIO_RELEASE_KEY_ALIAS`
- `FNAUDIO_RELEASE_KEY_PASSWORD`

**必须离线加密备份 keystore 与密码。** Android 安装器用签名证书判断升级身份：换成另一把密钥后，新 APK 无法覆盖已安装的正式版，用户只能卸载重装，本地数据（曲库缓存、设置）全部丢失。

## 首次生成（只做一次）

```powershell
python tools/gen_release_keystore.py
```

脚本生成 keystore 与 `.secrets/release-signing.env`，并打印证书指纹。**已有 keystore 时它拒绝运行**；`--force` 会作废旧身份（旧文件改名为 `.jks.retired` 留存），只有在确认要让所有已装用户卸载重装时才可用。

## 本地构建

```powershell
Set-Location D:\fnAudio
.\tools\load_signing_env.ps1 -ThenBuild -AndroidSdkRoot D:\fnAudio\tools\android-sdk
```

`load_signing_env.ps1` 把 `.secrets/release-signing.env` 的四项读进当前进程，再在同进程里调用 `build_android_release.ps1`——分开两次调用的话，环境变量不会跨进程传递。只想临时设置而不构建，去掉 `-ThenBuild` 即可。

脚本执行 `:app:assembleRelease`，用 Build Tools 的 `apksigner verify --verbose --print-certs` 验签，用 `aapt dump badging` 比对 `VERSION` 与 APK 的 `versionName`，成功后产出：

```text
artifacts/<VERSION>/fnaudio-android-<VERSION>-release.apk
artifacts/<VERSION>/ANDROID_SHA256SUMS
```

## 归档约定

- `SHA256SUMS` 只记 FPK，`ANDROID_SHA256SUMS` 只记一个 APK，且**必须恰好一行**——`verify_release_evidence.ps1` 会按这一条校验，多行会以「invalid checksum record」失败。
- 因此同一版本目录里若同时放调试包与正式包，`ANDROID_SHA256SUMS` 指向正式包，调试包的哈希写进 `RELEASE_NOTES.md` 的表格即可。
- 目录里已有 `ANDROID_SHA256SUMS` 时脚本会拒绝重建（防同版本 APK 被静默覆盖）；要重出正式包，先手工移走该文件。

## 升级身份

- 正式包之间互相可覆盖升级（同一把密钥）。
- 调试包（`com.fnaudio.client` + debug 签名）与正式包签名不同，**不能互相覆盖**。从调试版切到正式版要先卸载，反之亦然。
- `emulator`／`mediaSession` 两个变体有独立 `applicationId` 后缀，可与正式版并存，不受此限。

## CI

CI 默认只构建 Debug APK，避免把签名材料暴露给普通 Pull Request。受保护发布工作流需要在仓库 Secret 里配置同名的四项变量并提供 keystore；本地仓库目前把密钥留在 `.secrets/`，未做云端分发。
