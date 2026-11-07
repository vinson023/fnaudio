## 主要更新

- **手机上单击文件夹直接进入**。此前文件夹行在触屏上点一下什么也不发生：点击处理里这一支只做了 `preventDefault`，选中是桌面才有的行为，进入只能靠长按菜单里的「打开」或者双击——而触屏基本不产生 `dblclick`。现在按屏宽分流：≤760px 单击就进入，桌面保持「单击选中、双击进入」的资源管理器语义。
- **长按菜单照旧**。按住超过阈值那一刻已经记下一次点击抑制，抬手产生的那次 click 会被拦下，菜单弹出时不会顺带钻进文件夹，也不会出现「进了一层又弹菜单」。
- **列表刷新闸门不用改**。文件夹行本来就被认作导航目标，「列表正在被替换」的闸门对它一直豁免，所以单击进入不会被吞掉。
- **本版只带这一条**。0.2.140 的内容（撤掉全部「播放全部」按钮、`playAll()` 删除、面包屑样式清理）原样在内。

## 下载

- `fnaudio-0.2.141-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.141-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.141-fnpack.fpk` | 5,444,684 字节 | `9BD33A224AC5C5205A0BB7786C388DB82F5677D2BC005B240863C78350FBB4C1` |
| `fnaudio-0.2.141-debug.apk` | 15,516,935 字节 | `768722B596A3ABF235625E79EB11515E17B36E148B4BAB92CFF92F99CA9D08A5` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，344 个文件、资源戳 `0.2.141-6a04789ae082`，包结构、manifest 身份（`version = 0.2.141`）、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。
- 解包后确认包里是这一版：`ui/index.html` 的 65 个引用全部带同一枚新戳；`ui/app.js` 的 group-row 点击分支里 `matchMedia("(max-width: 760px)")` 为真时调用 `openGroupRow(row)`（:4261），桌面分支仍是 `setGroupSelection`；`ui` 73 个文件、`server` 196 个文件。
- APK 内置的 **73 个 assets 条目与 `src/app/ui` 逐字节一致**（零缺失、零多余、零差异）；`versionName 0.2.141`／`versionCode 399`。
- 界面实测：e2e 用例 `a phone tap opens a folder row while a desktop click only selects it` 在 390×844 下点文件夹行直接进到 `Live`（面包屑出现且当前项为 `Live`），在 1440×900 下单击只让行变 `is-selected`、不出现当前层面包屑（根目录本就没有），双击才进入。
- 守卫：`src/tests/test_ui_folder_navigation.js` 原先只断言「folder 分支以 return 收尾」，现在要求「手机那一支的 `openGroupRow` 先于桌面那一支的 `setGroupSelection`」，两句顺序调换即红。
- 门禁：前端 JS 单元测试 **126 个文件全部通过**；浏览器端 e2e **105 项全部通过**；离线 Python `Ran 3226 tests` / `OK (skipped=8)`。`SOURCE_MANIFEST.sha256` 811 条新鲜。
- 归档自带校验可用：`tools/verify_release_evidence.ps1 -ArtifactDirectory artifacts/0.2.141` 返回 `Validated: True`、`AndroidValidated: True`、`EvidenceComplete: True`。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 399、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过（2/2），零漏项。

## 已知限制

- 专辑页与类型页没有一键播整张的按钮，要整张播放从任意一行右键／长按选「播放」（0.2.140 的既定形态）。
- 安卓上没有飞牛宿主，设置页「选择音乐目录」会落到 `hostUnavailable` 分支，改用服务器目录浏览——这是设计，不是缺陷。
- 仓库里发的仍是调试签名 APK，正式签名缺 keystore（`build_android_release.ps1` 会拒绝运行）。
