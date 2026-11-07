## 主要更新

- **五类分组都能「播放」整组，手机上是长按**。文件夹、专辑、歌手、作曲者、类型的行菜单第一项是「播放」，点下去把该组下的歌整批塞进队列并从第一首开始放；桌面右键、手机长按两条入口走同一套 `runGroupAction`。手机端这条以前是死的：分组行的 `contextmenu` 在 760px 以下直接 return，而分组行又没有歌曲行那种长按计时器，所以两个 App 里按住一行没有任何反应。现在补了 550ms 计时器，位移超过 10px 取消，抬手后的那次 click 一律吃掉（不会顺带打开详情页），菜单打开时用行盒模型兜底坐标——否则按住位置在行内的偏移会让菜单跑到屏幕外。
- **平铺列表补「播放全部」**。全部、DSD、最近添加、随机 100 四个平铺视图顶上多了一条工具条，按钮带这一屏的曲目数；专辑详情与类型详情页的面包屑也有同一个按钮。工具条放在 `#listToolbar` 而不是塞进 `#trackList`：列表是键控复用的，混进一个非行节点会让整张表退化成整块 `innerHTML` 替换，滚动位置和过渡全部丢失。
- **手机端菜单砍掉三项文件动作**。手机上长按一首歌只剩播放、加入队列、收藏、加入歌单、详情、元数据候选六项——「打开包含的文件夹」「分享外部链接」「删除歌曲」在手机上直接隐藏，桌面一切照旧。过滤写在共用的按钮构造器末尾，所以右键菜单和「歌曲操作」对话框不会各说一套。为什么砍：这三项在安卓上没有宿主可调，在手机浏览器里调起来也都要绕一大圈，留着只会在点了之后失败。
- **分享外部链接换了一条通路**。这条请求从上线起就发错了：飞牛的 `appcgi.sharesvr.share.link.create` 要求参数放在 `data` 里，fnAudio 一直平铺发送，服务端回 `errno 3000001 Invalid Params`——字段名全对，所以每次读起来都像权限问题。桌面没暴露是因为桌面先走飞牛原生文件管理器面板，手机只能落内置面板，内部那条坏请求因此第一次被人看见。修好之后手机也能生成外链。
- **USB DAC 切队列不再跳到下一首**。遥控端把队列整批替换时，MPD 的第一条命令是 `clear`，正在播的歌进入 `STOPPED`，而空闲循环把「没有命令解释的 `PLAYING → STOPPED`」当成自然播完并派发 `next`；此刻逻辑队列已经换新、`current_index` 归零，于是这首歌被跳过。现在替换队列的那次 `clear` 会被显式标注，不再被误判成播完。
- **播放目标别名归一化**。同一个 USB DAC 在服务端有两个名字（输出注册表叫 `mpd`，`/api/playback/targets` 发布成 `mpd:usb:0644:…:dev0`），界面用字面相等比较，找不到行就判「设备离线」，于是每 3 秒把刚暂停的 DAC 写回本机输出、设备面板也跟着每 3 秒重排。现在比较前先归一化。
- **安卓客户端与飞牛端对齐**。安卓 App 不是第二套界面，它把 `src/app/ui/index.html` 里的 62 个脚本逐条内联进 WebView，所以上面这些改动只要资产同步就自带。排查中发现内联清单漏了 `native_share_bridge.js`——页面声明了、清单没有，WebView 会留一条 `<script src>` 去网络上取（旧 NAS 取不到、新 NAS 取到另一个版本）；已补齐，并把两个排错位的 loader 挪回页面声明顺序。新增三枚守卫：页面声明的每个脚本都必须有内联路径、清单必须与页面同序且无冗余、以及真用 `javac` 跑一遍内联逻辑并断言输出里没有一条 `<script src>` 残留。
- **构建脚本的缓存戳修好了**。资源戳声称是「内容派生」，实际取的是拼接串的前 12 位——也就是第一个资产（`access_profile_loader.js`）摘要的前缀，于是 0.2.130 到 0.2.137 每个版本的戳都是 `58a38563247b`，`app.css`／`app.js` 改了它也不动，同版本重构建根本击不穿浏览器缓存。现在改成对全部 65 个资产的摘要再算一次 SHA-256；本版的戳是 `0.2.138-eb303a6c9068`，与上一版不同了。

## 下载

- `fnaudio-0.2.138-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.138-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.138-fnpack.fpk` | 5,445,208 字节 | `69B52267C0C42361E608ED9805610F5BE4AF9068D19D5549F3CDAD399BB17401` |
| `fnaudio-0.2.138-debug.apk` | 15,517,882 字节 | `96FC6A9B7DA9E3532BF0E91F05740BDCDCC4AE44BF8B3CC18FF7EF66C270A26B` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，344 个文件、资源戳 `0.2.138-eb303a6c9068`，包结构、manifest 身份（`version = 0.2.138`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。解包后逐项确认包里是这一版：`ui/index.html` 的 65 个引用全部带新戳、`ui/app.js` 内含分组长按与手机端过滤、`ui/app.css` 含 `.list-toolbar`。
- APK 内置的 **73 个 assets 条目与 `src/app/ui` 逐字节一致**（按 `assets/` 之后的相对路径比对，零差异；上一版是 72 条，多出来的就是 `native_share_bridge.js`）；`versionName 0.2.138`／`versionCode 396`。
- 安卓端在模拟器（AVD `fnaudio-api35-atd`，320×640，`app-emulator.apk`，CDP 直连 WebView）实测 20/20：平铺「播放全部」在、歌曲长按只剩 6 项、菜单与对话框同源、五类分组长按首项都是「播放」且点下去队列长度与首曲逐例全等（文件夹 `NEW` 531 首）；类型详情「播放全部」与目录选择器兜底 3/3。
- 门禁：前端 JS 单元测试 **126 个文件全部通过**；浏览器端 e2e **104 项全部通过**；离线 Python `Ran 3226 tests` / `OK (skipped=8)`。`SOURCE_MANIFEST.sha256` 811 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.138` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。这一条在本轮之前是坏的——旁证正则只认 `fnaudio-android-<版本>-release.apk`，而实际发布的是 `fnaudio-<版本>-debug.apk`，于是 0.2.125 起每个归档跑自己的证据校验都会报 `invalid checksum record`；已改成两种命名都接受，`artifacts/0.2.137` 一并复验通过。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 396、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过，零漏项。

## 已知限制

- 安卓上没有飞牛宿主，设置页「选择音乐目录」会落到 `hostUnavailable` 分支，改用服务器目录浏览——这是设计，不是缺陷。
- 手机端隐藏的三项文件动作在安卓上本来就没有等价能力；桌面端行为不变。
