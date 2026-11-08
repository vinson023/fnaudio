## 主要更新

- **应用中心图标换了样子：白底 + 蓝色音符，并沿圆角描了一圈边**。此前飞牛 App 的应用中心里 fnAudio 看着像没有图标——它其实一直在加载，只是原图是「白色圆角方块 + 蓝音符」，方块放在白色卡片上没有边界，只剩一个悬空的音符。这版把方块的白底保留、音符用品牌蓝渐变，另加一道极淡的浅蓝灰描边，让方块在白卡片上仍能看出轮廓。
- **补齐全套尺寸**。飞牛微应用按 `icon_{0}.png` 取图、桌面与列表分别用 16/24/48/64/72/96/128/256，此前库里只有 64 与 256 两档，小尺寸由浏览器硬缩会发糊。现在 8 档俱在，且 `ICON.PNG`／`ICON_256.PNG` 与界面内那套是同一张图，不会出现桌面一种配色、卡片另一种配色。
- **本版只带图标这一条**。0.2.141 的功能内容（手机上单击文件夹直接进入、长按菜单、以及 0.2.140 撤掉全部「播放全部」按钮）原样在内，代码一行未改。

## 下载

- `fnaudio-0.2.142-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-android-0.2.142-release.apk`：**正式签名包**，可直接覆盖安装此前的正式版（同一把密钥）。从调试包切过来必须先卸载一次——两者签名身份不同。
- `fnaudio-0.2.142-debug.apk`：调试签名测试包，仅供开发调试，**不能**作为正式升级包。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.142-fnpack.fpk` | 5,413,977 字节 | `0E50159F87E1E91A4264BE98D56E79499A4FAC3FD6880CFA814BBD310A53F81F` |
| `fnaudio-android-0.2.142-release.apk` | 12,899,031 字节 | `E33BACAA5A5F0FE6E604697E6BDFE5E88B62165B239F9A46B346A960E6329BE4` |
| `fnaudio-0.2.142-debug.apk` | 15,527,931 字节 | `EEC44D972E5818363C3FC6E3B7E3BDA0C6181F2B144AEC49F3BF5F818350C602` |

正式包签名证书：`CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN`，RSA 4096，证书 SHA-256 指纹 `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59`。`ANDROID_SHA256SUMS` 记录的是正式包这一行。

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，351 个文件、资源戳 `0.2.142-6a04789ae082`，包结构、manifest 身份（`version = 0.2.142`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。
- **包内图标逐个核对**：根层 `ICON.PNG` 3,040 B／`ICON_256.PNG` 15,315 B，`app.tgz` 内 `ui/images/` 九张（含字面量 `icon_{0}.png`）与工作区 `src/app/ui/images/` 的 md5 逐张相等；旧图的 2,354 B 白底版已不存在于包内。
- 三张图的判据是「形状未改、只改颜色」：音符蒙版按「蓝度（B−R）」从原图提取，音符轮廓一像素未动；描边在 1024 画布上腐蚀 8 px 取 alpha 差集生成，缩到 256 为 2 px、缩到 64 为 0.5 px。
- APK 内置的 80 个 assets 与 `src/app/ui` 逐字节一致（零缺失、零多余、零差异；另有 2 个 Gradle 生成的 dexopt baseline profile）；`versionName 0.2.142`／`versionCode 400`。
- **正式包签名已验**：`apksigner verify --verbose --print-certs` 报 `Verifies`，v1（JAR）与 v2 两种方案均为 true，签名者 1 人、证书 DN 与上表一致、RSA 4096，证书 SHA-256 与 keystore 里的那把逐字相同；`aapt dump badging` 读到 `package name='com.fnaudio.client' versionCode='400' versionName='0.2.142'`。
- **签名材料位置**：keystore 在 `.secrets/fnaudio-release.jks`（PKCS12、RSA 4096、有效期 30 年、alias `fnaudio`），四项环境变量在 `.secrets/release-signing.env`，`.secrets/` 已被 `.gitignore` 排除，不进仓库、不进 `SOURCE_MANIFEST`。构建入口 `tools/load_signing_env.ps1 -ThenBuild` 负责把变量读进进程再调 `build_android_release.ps1`；`tools/gen_release_keystore.py` 只在没有 keystore 时生成，默认拒绝覆盖——换掉密钥等于让所有已装正式版无法升级。
- 门禁：前端 JS 单元测试 **126 个文件全部通过**；离线 Python `Ran 3226 tests` / `OK (skipped=8)`；`SOURCE_MANIFEST.sha256` 818 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.142` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 400、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）改完当刻先跑 `test_release_version` 通过（2/2）。
- 测试机部署：`192.168.5.141` 升级后 `VERSION=0.2.142`、`ASSET_STAMP=v=0.2.142-6a04789ae082`、`/api/health` `ok:true`（mpd 与 dlna 均在跑），远端包 sha256 复算等于本地，旧树备份在 `upgrade-backups/20261108-114130`；曲库 117 首与升级前相同。

## 已知限制

- `192.168.5.20` 本次未升级：机器 ping 通，但 22 与 18080 端口都不通，连不上。它上面还停着 0.2.141 的旧图标，恢复后跑一次 `deploy_fpk.py` 或 `tools/push_icons.py` 即可。
- 飞牛 App 会缓存应用中心图标，升级后若仍显示旧图，杀掉 App 重开。
- 专辑页与类型页没有一键播整张的按钮，要整张播放从任意一行右键／长按选「播放」（0.2.140 的既定形态）。
- 正式签名 keystore 只存在于本机 `.secrets/`，**没有离线加密备份就不要再发正式版**：它一旦丢失，新包再也覆盖不上已安装的正式版，用户只能卸载重装（本地数据全丢）。备份时连同 `.secrets/release-signing.env` 里的密码一起存进密码管理器。
