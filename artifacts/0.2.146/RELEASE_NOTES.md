## 主要更新

- **修好了应用中心列表里不显示图标的问题**。之前只有点进详情页才看得到音符，列表里一直是灰底占位图。原因是应用入口配置里把图标写成了模板 `images/icon_{0}.png`，而飞牛应用中心**不做占位符替换**——它把这个字符串原样拼进图片地址，列表侧拿不到确切文件名就退回默认占位图。现在改成具体文件名 `images/icon_256.png`（飞牛自家应用也是这么写的），列表与详情页都能正常显示。
- **图标重画**。旧图标是临时脚本画的，符头压扁、横梁拉平，缩到列表里像一个方框加两个点。这一版以 0.2.144 的原版为准逐像素量出几何重画：正圆符头、16 宽符干（右缘与符头最右点相切）、下倾 12.2° 的横梁带垂直切口与圆角。画完又按飞牛自家图标的观感把主体占比从 52%×68% 放大到 **60%×78%**，在一排系统应用里不再显小。
- **服务端代码零改动**。这一版只动了 `app/ui/config` 里的一个图标路径和图标本体，其余与服务端相关的实现完全没变；FPK 必须跟着升一次版本号，是为了让应用中心重新读配置。

## 下载

- `fnaudio-android-0.2.146-release.apk`：**正式签名包**，可直接覆盖安装此前的正式版（同一把密钥）。从调试包切过来必须先卸载一次——两者签名身份不同。
- `fnaudio-0.2.146-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级。**想在列表里看到图标必须装这个**：图标路径写在包里，只升 APK 不会改应用中心的登记。
- `fnaudio-android-0.2.146-debug.apk`：调试签名测试包，仅供开发调试，**不能**作为正式升级包。

装完 FPK 后如果列表里还是灰图标，把飞牛 App 杀掉重开——它会缓存应用中心的图标。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.146-fnpack.fpk` | 5,399,439 字节 | `968D4C192E96990664E1E361F546A202C665CD5BF1D3873C0E905B29140B483B` |
| `fnaudio-android-0.2.146-release.apk` | 12,926,347 字节 | `B82CA1A0841F4D66D1E07F6D0621D654576E9258FE5D1B31F8332B433D57DE28` |
| `fnaudio-android-0.2.146-debug.apk` | 15,574,746 字节 | `E31A26194118400EF29A59850D54CCF65DDA0753840C25AE88FA4AED15F8C2A0` |

正式包签名证书：`CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN`，RSA 4096，证书 SHA-256 指纹 `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59`。`ANDROID_SHA256SUMS` 记录的是正式包这一行，调试包哈希见上表。

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，351 个文件、资源戳 `0.2.146-2934596bde7a`，包结构、manifest 身份（`version = 0.2.146`）、图标与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_commit 5221a8b`，`git_tracked_edits: 0`，`git_untracked_inputs: 0`）。
- 包内逐项核对过：`app/ui/config` 的 `icon` 是 `images/icon_256.png`，根层 `ICON.PNG` 2,222 B／`ICON_256.PNG` 8,897 B／`app/ui/images/icon_256.png` 8,897 B／`icon_64.png` 2,222 B，与源码逐字节相同。
- 正式包签名已验：`apksigner verify --verbose --print-certs` 报 `Verifies`，v1（JAR）与 v2 均为 true，签名者 1 人、证书 DN 与上表一致、RSA 4096；`aapt dump badging` 读到 `versionCode='404' versionName='0.2.146'`（调试包同）。
- **测试机 `192.168.5.141` 已升级**：`VERSION=0.2.146`、`ASSET_STAMP=v=0.2.146-2934596bde7a`、`/api/health` `ok:true`（mpd 与 dlna 均在跑）、远端包 sha256 复算等于本地，旧树备份在 `upgrade-backups/20261109-201053`；曲库 117 首不变。远端 `target/ui/config` 已随包变成 `images/icon_256.png`，两个图标文件 md5 与本地一致；飞牛 App 随后请求 `/app-center-static/serviceicon/fnaudio/ui/images/icon_256.png` 返回 200，列表图标正常显示。
- 门禁：前端 JS 单元测试 **127 个文件全部通过**；离线 Python `Ran 3227 tests` / `OK (skipped=7)`；浏览器 e2e **107 条全绿**；`SOURCE_MANIFEST.sha256` 834 条新鲜。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode 404`、`README.md`、`ARCHITECTURE.md`、`RECOVERY.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`）按「功能提交 → 版本号 + 清单提交 → 打包」的顺序出包，provenance 因此是干净的。

## 已知限制

- **图标有尺寸规范**：包根层 `ICON.PNG` 必须是 64×64、`ICON_256.PNG` 必须是 256×256，PNG、sRGB、≤1024 KB、正方形、圆角矩形风格。系统其实不校验（有的应用塞 512 顶替也能装），但这一版按规范来，没有用大图占位——256 已经是按 256 展示位 1:1 出的，再大只会被缩回去。
- **`192.168.5.20` 仍未升级**：ping 100% 丢包、22 与 18080 都连不上，它上面还停在 0.2.141。恢复后跑一次 `tools/deploy_fpk.py --host 192.168.5.20 --user admin --sudo --fpk artifacts/0.2.146/fnaudio-0.2.146-fnpack.fpk` 即可补齐。
- 飞牛 App 会缓存应用中心图标，升级后若仍显示旧图，杀掉 App 重开。
- 正式签名 keystore 只存在于本机 `.secrets/`，**没有离线加密备份就不要再发正式版**：它一旦丢失，新包再也覆盖不上已安装的正式版，用户只能卸载重装（本地数据全丢）。备份时连同 `.secrets/release-signing.env` 里的密码一起存进密码管理器。
