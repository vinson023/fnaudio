## 主要更新

- **列表顶部的「播放全部」全部撤掉**。全部音乐、DSD、最近添加、随机 100 首这四类平铺列表，以及播放列表、收藏、当前队列，顶部不再有这枚按钮。平铺列表连整条工具条一起消失——它当初只为放这枚按钮才存在，撤掉按钮后剩下的计数与左侧栏的曲目数重复，留着只是白占一行。
- **播放列表与队列的计数条保留**。这两条上面还挂着「删除播放列表」和「清空队列」，所以条本身留下，只把按钮摘掉；收藏那条没有别的动作，现在只剩「N 首收藏歌曲」一行计数。
- **专辑详情、类型详情、艺术家／类型分类头的按钮保留**。这次要求撤的是「列表里面的」工具条，详情页与分类头不属于列表工具条，所以没动——在专辑页仍然是点一下播整张。
- **队列空态的文案跟着改了**。原来写「播放歌曲或使用“播放全部”后，歌曲会出现在当前队列」，按钮撤掉后这句话指向一个不存在的入口，改成「从音乐库播放歌曲后，歌曲会出现在当前队列」。
- **实现上收敛成一个计数条构造器**。R504 引入的 `playAllBar` 改成 `countBar`：不再产按钮，只有带额外动作（删除播放列表／清空队列）时才渲染右侧容器，收藏条因此不会留一个空的 `div`。同时删掉 `FLAT_PLAY_ALL_VIEWS` 常量、`renderFlatListToolbar` 渲染器、`index.html` 里的 `#listToolbar`、`app.css` 里的 `.list-toolbar` 两条规则。
- **本版是 0.2.138 的减法**。0.2.138 说明里的「平铺列表补『播放全部』」在本版被撤回，五类分组长按／右键播放、手机端六项菜单、外链修复、USB DAC 换队列不跳曲等其余改动全部保留。

## 下载

- `fnaudio-0.2.139-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.139-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.139-fnpack.fpk` | 5,444,571 字节 | `2997260E1DFCA9182EEF3C4B6C1FDE1B18B7347DA5993E4B2B4FBB205A088745` |
| `fnaudio-0.2.139-debug.apk` | 15,517,045 字节 | `E3076EB5A2C22E84BB4B3ACB3AF59C4991855488BB0BB81953212A012F1BB249` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，344 个文件、资源戳 `0.2.139-cb96c60e7216`，包结构、manifest 身份（`version = 0.2.139`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。解包后逐项确认包里是这一版：`ui/index.html` 的 65 个引用全部带同一枚新戳且已不含 `listToolbar`、`ui/app.js` 不含 `FLAT_PLAY_ALL_VIEWS` 与 `renderFlatListToolbar` 而含 `countBar`、`ui/app.css` 已无 `.list-toolbar` 而保留 `.playlist-toolbar`。
- APK 内置的 **73 个 assets 条目与 `src/app/ui` 逐字节一致**（按 `assets/` 之后的相对路径比对，零缺失、零多余、零差异）；`versionName 0.2.139`／`versionCode 397`。
- 界面实测（复用 e2e fixture，390×844 与 1440×900 各一轮，脚本 `artifacts/r508/shots.js`）：六组读数里 `#listToolbar` 与 `.playlist-toolbar [data-play-all]` 全为 0，只有专辑详情页的 `detailPlayAll` 为 1；队列条仍有「清空队列」，收藏条仍有「首收藏歌曲」。
- 守卫改成反向断言：`src/tests/test_ui_group_long_press.js` 第 3／4 节断言三个标识符都不存在、`countBar` 与三个调用点都不含 `data-play-all`、详情页两处仍保留；e2e 用例 `phone hold opens the group menu and list toolbars drop 播放全部` 断言 all／random100 下两个选择器计数都为 0。
- 门禁：前端 JS 单元测试 **126 个文件全部通过**；浏览器端 e2e **104 项全部通过**；离线 Python `Ran 3226 tests` / `OK (skipped=8)`。`SOURCE_MANIFEST.sha256` 811 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.139` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 397、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过，零漏项。

## 已知限制

- 安卓上没有飞牛宿主，设置页「选择音乐目录」会落到 `hostUnavailable` 分支，改用服务器目录浏览——这是设计，不是缺陷。
- 平铺列表撤掉工具条后，整库「播全部」只能从左侧分类下钻或用分组长按／右键触发；这是本次要求的直接结果。
