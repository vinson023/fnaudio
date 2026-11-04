## 主要更新

- **文件夹视图只列出这个文件夹自己的歌**。此前打开一个文件夹，页面上既有子文件夹的行，又把子文件夹里的歌一并折进歌曲列表，同一首歌因此在两处出现。现在打开文件夹看到的是「子文件夹行 + 直接放在这个文件夹里的曲目」，点进子文件夹才看到下一层。文件夹行上的「N 首」不用改：列表本来读 `folders` 表、计数是整棵子树的累计，所以子文件夹之和加上直属曲目恰好等于容器总数——这条不变量现在有测试钉住。
- **勾选文件夹仍然覆盖整棵子树**。页面收窄成一层之后，勾选文件夹行加入队列或播放依旧要把下面所有层的歌都取回来，因此单开了一条 `subtree=1` 的请求通道，只在批量取歌时带上；「播放全部」不带，维持「页面上看到什么就播什么」。
- **远程挂载出现在音乐目录选择器里**。局域网里挂到本机的 SMB／NFS／WebDAV／rclone 目录此前在选择器里完全看不到。根因不是前缀表少一项，而是**挂载点位置不可猜**：fnOS 自带的远程挂载放在系统目录下，手工写 `fstab` 的可以落在任何地方。实测三种位置三种失败形态——被 `/mnt` 覆盖的能看见、`/vol1/@mountmgr` 下的通过了路径校验却走不到、`/srv` 下的直接被拒。改为读 `/proc/mounts` 判定远程文件系统，放行挂载点内的路径，并把不在已有根目录之下的挂载点提升为浏览根；两个挂载点同名时用父目录名区分。
- **修掉一个只在真实音乐库上才暴露的缓存 bug**。`query_library_page` 自己手写了一份页缓存键，没带 `subtree`，于是「打开文件夹」和「把这个文件夹加入队列」拿到同一个键：先到的那次把答案写进缓存，后到的直接复用，表现为勾选文件夹加入队列只拿到页面里那几首。单元测试每个用例都新建临时库、两次请求撞不上同一个缓存，所以是拿测试机的真实库跑出来的。同时删掉 `LibraryPageQuery.cache_values` 这个从没被读过的属性——它长得像「键就在这里」，改缓存键时最容易改错地方。

## 下载

- `fnaudio-0.2.136-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.136-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.136-fnpack.fpk` | 5,410,149 字节 | `A9A1283C93678D2897BBA0E62F5EE2D0AE1CCD92733AF513306F9F9C34C671B5` |
| `fnaudio-0.2.136-debug.apk` | 15,479,976 字节 | `193F4A1DEC1B572A86CD44E632D30259D46991DE7BD0FFF61CE45B3032DCB884` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，343 个文件、资源戳 `0.2.136-58a38563247b`，构建器自带的包结构、manifest 身份、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。
- APK 内置的四个 assets（`index.html`／`app.js`／`app.css`／`fnos-theme.css`）与 `src/app/ui` 逐字节一致；`versionName 0.2.136`／`versionCode 394`。
- 离线门禁 `Ran 3212 tests` / `OK (skipped=8)`；浏览器端 e2e **86 项全部通过**；前端 JS 单元测试 **115 项全部通过**；`SOURCE_MANIFEST.sha256` 798 条新鲜。
- 文件夹语义在测试机真实库上复验（117 首的根目录）：`folder = ''` 直属 **0** 首、`subtree=1` **117** 首；两个子文件夹 `Billboard Hot 100`（直属 100／子树 100／行 100）与 `hires`（直属 17／子树 17／行 17），`100 + 17 = 117`，「子文件夹之和 + 直属 = 容器」成立。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`/`versionCode` 394、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过，零漏项；八个文件行尾全为 LF。
- 测试机 `192.168.5.141` 走应用中心「手动安装」升级成功：登记 `{"appName":"fnaudio","version":"0.2.136","status":"running"}`，首页资源戳 `app.js?v=0.2.136-58a38563247b`，下发的 `app.css`（133,673 字节）、`fnos-theme.css`（82,255 字节）、`app.js`（516,149 字节）与本地源逐字节一致，`/api/health` 200 且 mpd running、library 无错误。
- 一个需要说明的地方：应用中心对**已安装的同版本号** FPK 走的是「更新」流程但不替换磁盘文件（实测装完 `server/library.py` 仍是旧 md5），所以上面那条缓存键修复在测试机上是把 `library.py` 与 `library_query_spec.py` 直接传到服务端目录后用新进程验证的。正式一致性以 FPK 为准，本轮 FPK 已包含该修复。
