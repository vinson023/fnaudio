## 主要更新

- **登录中按钮变成「取消登录」**。以前点了登录，按钮就被禁用，地址填错、密码填错或者设备根本没响应时，页面上没有任何退路，最长要干等三十秒超时才回来一次。现在按钮在登录过程中显示「取消登录」（文字降到石板灰，避免读成第二个提交按钮），点一下立刻中断在途的认证握手和 FN Connect 解析，回到可输入状态，并提示「已取消登录」。
- **取消后能马上再试**。中断走的是「作废本次请求」而不是「关掉会话」——解析器只把当前这一轮的序号加一，后续回调被自动丢弃，连接器和解析器本身仍然可用。所以取消一次之后，接着重新填地址、重新点登录，一切照旧，不需要重启 App。
- **不在登录中时行为完全不变**：按钮回「登录」、品牌蓝配色、点击发起登录。
- 这一版的**服务端与 0.2.143 相同**（FPK 只随版本号重新出包，功能差异为零）。改动全部集中在 Android 客户端，升级 APK 即可看到；FPK 是否升级只影响版本号登记。

## 下载

- `fnaudio-android-0.2.144-release.apk`：**正式签名包**，可直接覆盖安装此前的正式版（同一把密钥）。从调试包切过来必须先卸载一次——两者签名身份不同。
- `fnaudio-0.2.144-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.144-debug.apk`：调试签名测试包，仅供开发调试，**不能**作为正式升级包。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.144-fnpack.fpk` | 5,419,038 字节 | `27A45A28D088FC3D48E5202DA788B61DC7DE5749D255239DB98931B443F28DD7` |
| `fnaudio-android-0.2.144-release.apk` | 12,902,528 字节 | `C30E197C2D8CE8E12F1C36306051E4B479ED76295151EA5D6CE1081504AF3A82` |
| `fnaudio-0.2.144-debug.apk` | 15,531,867 字节 | `C4A4053E1FF68B4AF2764EF606F1531FBF32D1B71F39064B9834DFAF4532A1E6` |

正式包签名证书：`CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN`，RSA 4096，证书 SHA-256 指纹 `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59`。`ANDROID_SHA256SUMS` 记录的是正式包这一行，调试包哈希见上表。

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，351 个文件、资源戳 `0.2.144-7f1aa29d96f9`，包结构、manifest 身份（`version = 0.2.144`）、data share 与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_commit 474f488`，`git_tracked_edits: 0`，`git_untracked_inputs: 0`）。
- **包内图标复核**：根层 `ICON.PNG` 3,040 B（md5 `3131f54a…`）／`ICON_256.PNG` 15,315 B（`70b0acfa…`），与 0.2.143 的白底蓝音符 + 浅蓝灰描边版逐字节相同；`app.tgz` 内 `ui/images/` 九张与工作区一致。
- APK 内置的 80 个 assets 与 `src/app/ui` 逐字节一致（零缺失、零多余、零差异；另有 2 个 Gradle 生成的 dexopt baseline profile）；`versionName 0.2.144`／`versionCode 402`（`aapt dump badging` 读到 `package name='com.fnaudio.client' versionCode='402' versionName='0.2.144'`）。
- **正式包签名已验**：`apksigner verify --verbose --print-certs` 报 `Verifies`，v1（JAR）与 v2 两种方案均为 true，签名者 1 人、证书 DN 与上表一致、RSA 4096，证书 SHA-256 与 keystore 里的那把逐字相同。
- 登录取消的契约由 `src/tests/test_android_login_cancel_contract.py` 钉住：文案切换、点击先判忙态、两条在途链路都被 `cancel()`、**不得出现 `.close()`**、取消后忙态复位，另加一条「按钮在任何状态都不得被禁用」。
- 模拟器实测（x86_64 ATD，用 `emulator` 变体装包）：初始「登录」→ 点击后「取消登录」+「正在登录 fnOS…」且输入框禁用 → 点取消回「登录」、字段恢复 → **再点一次又能进忙态**（这条专门证明取消用的是作废而非关闭）。无头模拟器 `screencap` 返回纯黑，视觉验证改走 `uiautomator dump` 读视图层级。
- 门禁：前端 JS 单元测试 **127 个文件全部通过**；离线 Python `Ran 3227 tests` / `OK (skipped=8)`；浏览器 e2e **107 条全绿**；`SOURCE_MANIFEST.sha256` 820 条新鲜。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 402、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）按「功能提交 → 版本号 + 清单提交 → 打包」的顺序出包，provenance 因此是干净的。
- 测试机部署：`192.168.5.141` 升级后 `VERSION=0.2.144`、`ASSET_STAMP=v=0.2.144-7f1aa29d96f9`、`/api/health` `ok:true`（mpd 与 dlna 均在跑）、远端 `manifest` 里 `version = 0.2.144`，远端包 sha256 复算等于本地，旧树备份在 `upgrade-backups/20261109-102906`；曲库 117 首／80 专辑／86 歌手与升级前相同；根层两个图标 md5 与包内一致。

## 已知限制

- `192.168.5.20` 本次未升级：ping 通，但 22 与 18080 端口都 connect 超时，连不上。它上面还停在 0.2.141，恢复后跑一次 `tools/deploy_fpk.py --host 192.168.5.20 --user admin --sudo --fpk artifacts/0.2.144/fnaudio-0.2.144-fnpack.fpk` 即可补齐。
- 「飞牛访问码」输入框在登录过程中仍然可以编辑（`setBusy` 从来没管过它）。这不影响本次的取消能力，但严格说忙态下应该一并锁住，留作后续收尾。
- 取消登录只会中断这一次尝试，不会登出已经建立的会话；如果证书或地址本身有问题，重新点登录仍会以同样的方式失败，需要改配置。
- 飞牛 App 会缓存应用中心图标，升级后若仍显示旧图，杀掉 App 重开。
- 正式签名 keystore 只存在于本机 `.secrets/`，**没有离线加密备份就不要再发正式版**：它一旦丢失，新包再也覆盖不上已安装的正式版，用户只能卸载重装（本地数据全丢）。备份时连同 `.secrets/release-signing.env` 里的密码一起存进密码管理器。
