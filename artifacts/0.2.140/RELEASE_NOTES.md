## 主要更新

- **不剩任何「播放全部」按钮**。上一版按「列表里面的」划界，留下了专辑详情面包屑、类型详情面包屑和艺术家／类型分类头这三处；本版按「一个都不留」把它们一起撤掉。至此全部 30 个视图组合（11 个顶层视图 × 两档屏宽，加专辑详情、艺术家详情、艺术家下钻专辑、类型详情、文件夹下钻、播放列表）里这枚按钮的命中数都是 0。
- **`playAll()` 整段删除**。它唯一的调用者就是那两条绑定，按钮撤掉后函数没有任何入口，留着只会让后来的人以为还能播整页。同时删掉 `data-play-all` 与 `data-play-artist-album` 两条绑定——后者本来就没有渲染点，是 R501 遗留的死选择器。
- **分类详情头只留「返回分类」**。艺术家／类型根下钻后的那颗按钮撤掉，右侧动作区现在只剩返回。
- **`.breadcrumb-play-all` 样式整块删除**，含 760px 断点。它原本要在 `.album-detail-breadcrumb button` 的重置之上把按钮撑成钮形，没有使用者之后留着只是误导。
- **播整张的入口没变**：列表任意一行右键（手机长按）→「播放」，分组长按／右键菜单里的「播放」都还在，R499 起就是这条路。
- **本版是 0.2.139 的减法**。0.2.139 的说明写着「在专辑页仍然是点一下播整张」，这句话本版不再成立；其余改动（平铺列表撤工具条、计数条保留、队列空态文案）原样在内。

## 下载

- `fnaudio-0.2.140-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.140-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.140-fnpack.fpk` | 5,443,681 字节 | `92991F4A93BD2AFA2247861AC9A731881DE340E95C6A7C2C1860C6E5680558CB` |
| `fnaudio-0.2.140-debug.apk` | 15,516,452 字节 | `8E167B9AD1B95E1DBC2087FB0B7810C6033FF77F3E780379F6465EC0D4AD0087` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，344 个文件、资源戳 `0.2.140-fe59d400aa0a`，包结构、manifest 身份（`version = 0.2.140`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。
- 解包后逐项确认包里是这一版：`ui/index.html` 的 65 个引用全部带同一枚新戳、`listToolbar` 0 命中；`ui/app.js` 里 `data-play-all`／`playAll` 0 命中、只剩 4 处说明性注释；`ui/app.css` 里 `breadcrumb-play-all` 与 `.list-toolbar` 均 0 命中。`ui` 73 个文件、`server` 196 个文件。
- APK 内置的 **73 个 assets 条目与 `src/app/ui` 逐字节一致**（按 `assets/` 之后的相对路径比对，零缺失、零多余、零差异）；`versionName 0.2.140`／`versionCode 398`。
- 界面实测（复用 e2e fixture，390×844 与 1440×900 各一轮，脚本 `artifacts/r511/inventory.js`）：15 个视图组合逐枚按钮文本清点，全部为零命中；同脚本改前能稳定复现那三处。
- 守卫翻成反向断言：`src/tests/test_ui_detail_play_all.js` 经 `git mv` 改名 `test_ui_play_all_retired.js`，断言两处详情页与分类头都不再渲染、`playAll` 与两条绑定都不存在（`playlistTrackIds` 那节保留）；`test_ui_group_long_press.js` 第 3 节改成「四类位置全无」；`test_ui_library_sort_shuffle.js` 第 8 节 `shuffleItems(tracks)` 期望 1→0；e2e 用例换成 `no view renders a 播放全部 button`。
- 门禁：前端 JS 单元测试 **126 个文件全部通过**；浏览器端 e2e **104 项全部通过**；离线 Python `Ran 3226 tests` / `OK (skipped=8)`。`SOURCE_MANIFEST.sha256` 811 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.140` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 398、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过（2/2），零漏项。

## 已知限制

- 专辑页与类型页现在没有一键播整张的按钮。要在专辑里播整张，从任意一行右键／长按选「播放」；这是本次要求的直接结果。
- 安卓上没有飞牛宿主，设置页「选择音乐目录」会落到 `hostUnavailable` 分支，改用服务器目录浏览——这是设计，不是缺陷。
- 仓库里发的仍是调试签名 APK，正式签名缺 keystore（`build_android_release.ps1` 会拒绝运行）。
