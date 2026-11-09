## 主要更新

- **加了安卓电视端**。电视（或电视盒子）上会多出一个独立的 fnAudio 入口，遥控器四个方向键 + OK 就能走完全程。手机端的界面一行没动，两者装在同一个 APK 里。
- **不用重新登录**。电视端和手机端共用同一份连接档案与凭据存储，手机上登录过的 NAS 会出现在电视的启动页里，按一次 OK 就连上了；没登录过的话可以当场填地址、端口、用户名、密码。
- **界面是「左侧固定栏 + 推荐位 + 三排横滑」**：首页、专辑、艺术家、曲目、队列五页，底部常驻一条正在播放（标题、艺术家、进度），OK 进全屏播放页（左封面 + 播放控制，右「接下来」队列）。随机与循环开关在控制行里。
- **播放完全在本地**。电视端不复用手机的后台播放服务——电视永远在前台，没有后台续播的需求，音频解码直接由页面持有，切页、返回都不中断。
- **服务端与 0.2.144 相同**：这一版没有改服务端代码，FPK 只随版本号重新出包。改动全部在 Android 客户端，升级 APK 即可看到；FPK 是否升级只影响版本号登记。

## 下载

- `fnaudio-android-0.2.145-release.apk`：**正式签名包**，可直接覆盖安装此前的正式版（同一把密钥），手机上装或电视上装都是它。从调试包切过来必须先卸载一次——两者签名身份不同。
- `fnaudio-0.2.145-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.145-debug.apk`：调试签名测试包，仅供开发调试，**不能**作为正式升级包。

电视安装提示：部分电视／盒子的应用列表只显示「推荐」里的应用，装完后如果桌面上找不到，去「应用 → 全部应用」或「媒体播放器」分类里翻；banner 图是深蓝底白音符的 `fnAudio / TV client`。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.145-fnpack.fpk` | 5,419,835 字节 | `2CF9F89E55472BE0BB5AE286FFFC0F54C7E3EAC4851D4B1E99916B9FFD1FC611` |
| `fnaudio-android-0.2.145-release.apk` | 12,945,522 字节 | `AF65E131F63995693BB998B63C83384869664C024E7CE146DC07CD9B2382406A` |
| `fnaudio-0.2.145-debug.apk` | 15,593,917 字节 | `1B764E0EA1E6B490FB94693D728EC67EA909C42FA951FB85B818EDF70CB65C35` |

正式包签名证书：`CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN`，RSA 4096，证书 SHA-256 指纹 `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59`。`ANDROID_SHA256SUMS` 记录的是正式包这一行，调试包哈希见上表。

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，351 个文件、资源戳 `0.2.145-2934596bde7a`，包结构、manifest 身份（`version = 0.2.145`）、图标与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`、`EvidenceComplete: True`，`git_provenance_status: clean`，`git_commit 8580fd8`，`git_tracked_edits: 0`，`git_untracked_inputs: 0`）。包内根层 `ICON.PNG` 3,040 B／`ICON_256.PNG` 15,315 B，与 0.2.144 逐字节相同（这一版没动图标）。
- 正式包签名已验：`apksigner verify --verbose --print-certs` 报 `Verifies`，v1（JAR）与 v2 均为 true，签名者 1 人、证书 DN 与上表一致、RSA 4096；`aapt dump badging` 读到 `versionCode='403' versionName='0.2.145'`。
- **电视端在 1080p／320dpi 的 TV 模拟器上逐页走查**（即 960×540dp 的真实电视视口）：首页（推荐位 + 最近添加／专辑／艺术家三排）、专辑网格、专辑详情、全部曲目、队列、全屏播放页、空队列态，遥控器上下左右与 OK／返回全部实测。焦点全部显式接线而不是依赖系统默认的焦点搜索——默认搜索在电视上会把右方向键送到推荐位按钮而不是卡片、把上方向键送到不相干的行。
- **数据链路用本地 fnOS 网关替身验证**（`tools/tv-mock/server.py`，开发件，不随产品发布）：模拟 WebSocket 登录 + `library`／`groups`／`cover`／`media` 四个只读接口，24 首／6 专辑／4 艺术家，封面是程序生成的渐变图，音频是 8 秒静音 WAV。连接档案只能由 `TvMockSeedTest` 在应用进程内落盘，因为凭据用 AndroidKeyStore 加密，`adb push`／`run-as` 写不进去。
- 门禁：前端 JS 单元测试 **127 个文件全部通过**；离线 Python `Ran 3227 tests` / `OK (skipped=8)`；浏览器 e2e **107 条全绿**；`SOURCE_MANIFEST.sha256` 834 条新鲜。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode 403`、`README.md`、`ARCHITECTURE.md`、`RECOVERY.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`）按「功能提交 → 版本号 + 清单提交 → 打包」的顺序出包，provenance 因此是干净的。
- 测试机部署：`192.168.5.141` 升级后 `VERSION=0.2.145`、`ASSET_STAMP=v=0.2.145-2934596bde7a`、`/api/health` `ok:true`（mpd 与 dlna 均在跑）、远端包 sha256 复算等于本地，旧树备份在 `upgrade-backups/20261109-154156`；曲库 117 首／80 专辑／86 歌手与升级前相同。

## 已知限制

- **电视端只在模拟器上验过，没上过真电视／盒子**。真机的解码能力、遥控器按键码（个别厂商会给方向键发非标准 keyCode）、以及 4K 电视上的缩放都还没实测。如果装上去有焦点跳错或黑屏，请把电视型号和系统版本告诉我。
- 电视端没有歌词页，也不能选输出设备（本机／DLNA 推送）——播放固定走电视本机出声。想要这两项的电视用户暂时得用手机端推。
- 电视端只读曲库：不能扫描、不能改元数据、不能编辑歌单。这些仍然只能在手机端或网页端做。
- `192.168.5.20` 仍未升级：ping 100% 丢包、22 与 18080 都连不上，它上面还停在 0.2.141。恢复后跑一次 `tools/deploy_fpk.py --host 192.168.5.20 --user admin --sudo --fpk artifacts/0.2.145/fnaudio-0.2.145-fnpack.fpk` 即可补齐。
- 飞牛 App 会缓存应用中心图标，升级后若仍显示旧图，杀掉 App 重开。
- 正式签名 keystore 只存在于本机 `.secrets/`，**没有离线加密备份就不要再发正式版**：它一旦丢失，新包再也覆盖不上已安装的正式版，用户只能卸载重装（本地数据全丢）。备份时连同 `.secrets/release-signing.env` 里的密码一起存进密码管理器。
