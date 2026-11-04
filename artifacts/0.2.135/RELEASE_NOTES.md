## 主要更新

- **样式表减负：去掉 806 条冗余 `!important`**。这两个样式表里的 `!important` 已经多到「改一行要猜三处」，但它们大部分并不在扛事——真正决定最终样式的是层叠顺序，而这一点过去只能靠眼睛判断。本版先把「每条属性最终胜者」的层叠图算出来（96 个界面状态 × 每个元素 × 每个长写属性，再把胜者降级成普通声明重算一遍，两轮都还是它才算可摘），再按图的结论改。`app.css` 2,614 → 2,130 条、`fnos-theme.css` 1,495 → 1,173 条，合计 **4,109 → 3,303（−19.6%）**。
- **样式表减负：合并 119 组重复选择器**。同一个选择器在同一个媒体条件下出现两三次、彼此覆盖，是这份样式表最难读的地方。合并前后重复组 **195 → 76**、重复块 **444 → 190**，规则数 1,187 → 1,071 与 570 → 551。
- **这两个改动都不改变任何可见效果**。两个文件合计少了 11,790 字节（`app.css` 141,156 → 133,673、`fnos-theme.css` 86,562 → 82,255），96 个界面状态的计算样式快照逐条比对**零差异**，对比度探针在浅色与深色下各 **0 处**不达 WCAG AA。

## 下载

- `fnaudio-0.2.135-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.135-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.135-fnpack.fpk` | 5,407,824 字节 | `AA8516EC7A7574A9EDE0C9F3AFFCF627CC51228B960937DD45C496C6A48F0618` |
| `fnaudio-0.2.135-debug.apk` | 15,479,870 字节 | `539E42F7C64EE9C8E9056AFB5094DBB3DE580C04E1C2F6A6F6C7174CDF91C671` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，343 个文件、资源戳 `0.2.135-58a38563247b`，构建器自带的包结构、manifest 身份、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`）。
- APK 内置的四个 assets（`index.html`／`app.js`／`app.css`／`fnos-theme.css`）与 `src/app/ui` 逐字节一致。
- 96 个界面状态的计算样式快照：原始样式表与改后样式表**跨会话**比对 `records removed/added/changed = 0/0/0`。同一次会话里的第 2 次采集会带预热伪影（`w1024-dark/settings-playback` 的 `margin:auto` 会被算成 `0px`），所以判定用的是「另一次会话采的原始基线」对「本次会话采的改后结果」。
- 离线门禁 `Ran 3191 tests` / `OK (skipped=6)`，**全绿**；浏览器端 e2e **86 项全部通过**；前端 JS 单元测试 **115 项全部通过**。
- 对比度探针 `probe_contrast_sweep.js`：浅色 **0 处**、深色 **0 处**不达 AA。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`/`versionCode` 393、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过，零漏项。
- 测试机 `192.168.5.141` 走应用中心「手动安装」升级成功：登记 `{"appName":"fnaudio","version":"0.2.135","status":"running"}`，首页资源戳 `app.js?v=0.2.135-58a38563247b`，下发的 `app.css`（133,673 字节）、`fnos-theme.css`（82,255 字节）、`app.js`（515,953 字节）与本地源逐字节一致，`/api/health` 200 且 mpd running、library 无错误。
