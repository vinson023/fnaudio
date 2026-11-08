## 主要更新

- **补全日志现在会说清是哪首歌**。以前元数据面板只给一行「失败 2 · 未匹配 155」这样的计数——数字后面是什么歌、哪类任务、为什么失败，全看不到，等于给了一个没法处理的数字。这版日志弹窗顶部加了「失败与未匹配明细」，每行写明 `失败/未匹配｜歌名 · 歌手｜任务类型｜原因`。
- **计数按任务类型拆开**。摘要行从「未匹配 155」变成 `未匹配 8（歌词 6、封面 2）` 这样的形态，先知道是哪一类任务在积压，再决定要不要处理。
- **明细里的歌可以直接点开**。当前曲库能解析到的行是按钮，点一下关掉日志、直接打开这首歌的补全候选，可以手动搜一个结果写进去；解析不到的行保持纯文本，不假装可点。
- **面板上的计数本身就是入口**。设置页那个红色的失败／未匹配计数现在可以点击，直接打开日志弹窗，不必先绕去日志按钮。
- **复制日志会连明细一起导出**，粘贴到别处仍然看得出是哪几首。
- 日志弹窗顺带修了一个显示缺陷：关闭后内容仍留在页面上（`display:flex` 盖掉了浏览器对关闭 dialog 的 `display:none`）。
- 功能内容与 0.2.142 相同的不再重复列出；移动端单击文件夹进入、撤掉「播放全部」等既有形态原样在内。

## 下载

- `fnaudio-0.2.143-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-android-0.2.143-release.apk`：**正式签名包**，可直接覆盖安装此前的正式版（同一把密钥）。从调试包切过来必须先卸载一次——两者签名身份不同。
- `fnaudio-0.2.143-debug.apk`：调试签名测试包，仅供开发调试，**不能**作为正式升级包。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.143-fnpack.fpk` | 5,419,428 字节 | `852D64D1DC9D60C24262892D9142EC07E942176362D874E28D2A9B19D27BB8AB` |
| `fnaudio-android-0.2.143-release.apk` | 12,901,901 字节 | `62B1E3F47E88023AF82D7071F127EFA67E17A9F36C545347BDC785A604D6400C` |
| `fnaudio-0.2.143-debug.apk` | 15,531,646 字节 | `033E596A7BBE6794B89EFB3B1BAF57E75E9A7D04014A73A644A254B0D2A15478` |

正式包签名证书：`CN=fnAudio, OU=fnAudio, O=fnAudio, L=Shenzhen, ST=Guangdong, C=CN`，RSA 4096，证书 SHA-256 指纹 `DF:88:31:F8:FD:09:11:8F:26:A1:16:BE:CD:7D:DA:44:FA:C6:2C:B2:B0:4F:0D:CB:FB:BB:FF:CB:39:32:76:59`。`ANDROID_SHA256SUMS` 记录的是正式包这一行，调试包哈希见上表。

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，351 个文件、资源戳 `0.2.143-7f1aa29d96f9`，包结构、manifest 身份（`version = 0.2.143`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`，`git_untracked_inputs: 0`）。
- **包内图标复核**：根层 `ICON.PNG` 3,040 B（md5 `3131f54a…`）／`ICON_256.PNG` 15,315 B（`70b0acfa…`），与 0.2.142 的白底蓝音符 + 浅蓝灰描边版逐字节相同；`app.tgz` 内 `ui/images/` 九张与工作区一致。
- APK 内置的 80 个 assets 与 `src/app/ui` 逐字节一致（零缺失、零多余、零差异；另有 2 个 Gradle 生成的 dexopt baseline profile）；`versionName 0.2.143`／`versionCode 401`。
- **正式包签名已验**：`apksigner verify --verbose --print-certs` 报 `Verifies`，v1（JAR）与 v2 两种方案均为 true，签名者 1 人、证书 DN 与上表一致、RSA 4096，证书 SHA-256 与 keystore 里的那把逐字相同；`aapt dump badging` 读到 `package name='com.fnaudio.client' versionCode='401' versionName='0.2.143'`。
- 门禁：前端 JS 单元测试 **127 个文件全部通过**；离线 Python `Ran 3227 tests` / `OK (skipped=8)`；浏览器 e2e **107 条全绿**（本轮新增 2 条：日志明细内容、390px 下弹窗不超屏）；`SOURCE_MANIFEST.sha256` 819 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.143` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 401、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）改完当刻先跑 `test_release_version` 通过（2/2），按「功能提交 → 版本号 + 清单提交 → 打包」的顺序出包，provenance 因此是干净的。
- 测试机部署：`192.168.5.141` 升级后 `VERSION=0.2.143`、`ASSET_STAMP=v=0.2.143-7f1aa29d96f9`、`/api/health` `ok:true`（mpd 与 dlna 均在跑）、`manifest` 里 `version = 0.2.143`，远端包 sha256 复算等于本地，旧树备份在 `upgrade-backups/20261108-153454`；曲库 117 首与升级前相同；四个图标文件 md5 与包内一致。

## 已知限制

- `192.168.5.20` 本次未升级：ping 通，但 22 与 18080 端口都 connect 超时，连不上。它上面还停在 0.2.141，恢复后跑一次 `tools/deploy_fpk.py --host 192.168.5.20 --user admin --sudo --fpk artifacts/0.2.143/fnaudio-0.2.143-fnpack.fpk` 即可补上两轮的改动。
- **明细是有界的**：失败取最新 8 条、未匹配取最新 12 条，超出部分会写明「另有 N 条未展开」。要看全部仍得看服务端日志。
- 飞牛 App 会缓存应用中心图标，升级后若仍显示旧图，杀掉 App 重开。
- 专辑页与类型页没有一键播整张的按钮，要整张播放从任意一行右键／长按选「播放」（0.2.140 的既定形态）。
- 正式签名 keystore 只存在于本机 `.secrets/`，**没有离线加密备份就不要再发正式版**：它一旦丢失，新包再也覆盖不上已安装的正式版，用户只能卸载重装（本地数据全丢）。备份时连同 `.secrets/release-signing.env` 里的密码一起存进密码管理器。
