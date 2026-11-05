## 主要更新

- **设置页推倒重写**。旧结构的问题不是丑，是同一件事有三套说法：六个标签页散着七个保存按钮（文案各异，实测 top 分别 695／719／735），元数据里还嵌着第二层四个子标签，「播放与输出」写着「立即生效，不需要保存」却配一个只存 Renderer 名的按钮，DLNA 页只有一个开关却占满 680px，`#saveDlnaSettingsBtn` 还因缺 `.settings-save` 类是白底。现在弹窗内是一套 `.settings-shell` 三行网格（56px 头／内容／底部保存栏），内容区 208px 左导航 + 560px 可读行长，六个平级分组 `library/playback/metadata/network/appearance/advanced`；七个历史按钮全部降级成 `.settings-legacy-actions[hidden]` 里的隐藏触发器，**可见写入路径只剩底部一条**。脏追踪按端点分组而不是按标签页——`network-pool` 与 `advanced-cache` 共用一次 `POST /api/config/runtime`，所以是同一个 group 横跨两个标签，脏了就在这两个导航项上都挂圆点；逐组保存按固定顺序 await，只有该组自己的端点确认后才出队，任一失败不掩盖后续成功；带未保存改动时第一次点 × 或按 Esc 只提示，第二次才关。手机上同一套 DOM 切两级：列表页 6 行 ×60px，选中进详情页，返回箭头取代 ×，保存栏只在详情层出现。
- **进度条改成「缓冲双层」，位置一个字节没动**。轨道锚点仍是 `position:fixed; left/right:0; bottom:var(--ui-player-height)`，实测桌面 `bottom:88px`、手机 `142px`，这轮只改这条 4px 带子怎么画：一条 `linear-gradient` 三段硬停——已播 `--ui-accent` → 已缓冲 `--ui-selected`（品牌色 15%／25%，跟随主题）→ 未播 `--ui-line`。`--seek-buffer` 的缺省值回退到 `--seek-fill`，所以没有可用 TimeRanges 的音源（本机播放器接管、刚开播的曲目）中段宽度归零，观感与改之前完全一致，是渐进增强而不是替换。把手从 6px 实心圆点换成 10px 白心 + 2px 品牌色描边：已播段与已缓冲段同为蓝色，实心蓝点落上去会糊成一片，白心才读得出把手在哪。新增 `seekBufferedPercent()` 把 `audio.buffered` 末端折进轨道时基，用 `localPlaybackSeconds()` 与 `audio.currentTime` 的差值平移，让缓冲边和播放位置共用同一套映射；结果取一位小数，否则每帧都在变、compare-first 的写入永远省不掉。事件补 `audio.onprogress`（暂停时缓冲仍在长）与 `audio.onemptied`（停止播放后 ranges 消失）。
- **播放条重排：歌曲信息靠左，播放与上下曲居中**。桌面 `.player` 的列模板从 `max-content minmax(0,1fr) max-content` 换成 `minmax(0,1fr) max-content minmax(0,1fr)`——只有两侧是等分弹性列，传输组 `max-content` 落在正中；`.now-playing` 与 `.transport` 的 `grid-column` 对调，`.transport` 的 `justify-content` 从 `flex-start` 改为 `center`。实测 1440／1280／1000／860／800／761 六档，传输组中心与播放条中心的偏差**全部为 0px**。没有用 `position:absolute; left:50%`：那样也能精确居中，但窗口窄到 761 时歌曲信息会直接压到按钮底下；等分列让信息列先截断（`text-overflow: ellipsis` 实测生效），任何宽度都不会重叠。播放条高度、进度轨锚点、手机端三行网格都没动。
- **顺带修掉三处真问题**。① 旧移动端 `@media(max-width:760px)` 里还留着一条 `#folderDialog[open]{height:calc(100dvh - 24px)}`，与桌面框架规则同特异性但后加载，手机弹窗只有 796px 高、底部露出播放条——手机规则改用 `[open]` 提高特异性并删掉旧块；② `.metadata-provider-settings` 的 `grid-template-areas` 把新加的分组标题挤进 `heading` 格与说明文字重叠，「数据源」标题在手机上整块不可见——删掉这套过时网格；③ 手机端「数据源在前、测试输入在后」的顺序随网格一起丢了，改用 `order` 恢复。

## 下载

- `fnaudio-0.2.137-fnpack.fpk`：fnOS 安装包，在应用中心「手动安装 → 从电脑上传」升级，这是 fnOS 上唯一会刷新登记版本的路径。
- `fnaudio-0.2.137-debug.apk`：Android Debug 测试包，使用调试签名，仅供测试；与正式包签名身份不同，安装前需先卸载已装正式版。

## 校验

| 文件 | 大小 | SHA-256 |
| --- | --- | --- |
| `fnaudio-0.2.137-fnpack.fpk` | 5,416,536 字节 | `167DF12C62BEBD9467EF14E99484D8F415BE8AD804AE400A4375B8608138E942` |
| `fnaudio-0.2.137-debug.apk` | 15,487,186 字节 | `B3D2DC6A5322BBD2AB0BDBF79B1C44EAD96750B21876264792F7D12DA01F39AE` |

## 验证

- FPK 由 `tools/build_release.ps1` 从唯一的 `src/` 构建，343 个文件、资源戳 `0.2.137-58a38563247b`，构建器自带的包结构、manifest 身份、data share、lifecycle 脚本与 `SHA256SUMS`／`SOURCE_PROVENANCE.json` 互校全部通过（`Validated: True`，`git_provenance_status: clean`，`git_tracked_edits: 0`）。
- APK 内置的 **72 个 assets 条目与 `src/app/ui` 逐字节一致**（按相对路径比对，零差异）；`versionName 0.2.137`／`versionCode 395`。
- 离线门禁 `Ran 3212 tests` / `OK (skipped=8)`；浏览器端 e2e **87 项全部通过**；前端 JS 单元测试 **114 个文件全部通过**；`SOURCE_MANIFEST.sha256` 797 条新鲜。
- 版本坐标八处（`VERSION`、`src/manifest`、`build.gradle` 的 `versionName`／`versionCode` 395、`README.md`、`ARCHITECTURE.md`、`docs/SOURCE_INVENTORY.md`、`android-client/README.md`、`RECOVERY.md`）在改完当刻先跑 `test_release_version` 通过，零漏项；九个文件行尾全为 LF。
- 进度条位置有实测证据：八套设计稿（`artifacts/r484/gallery.html`）逐套量过 `railPos/railBottom/railHeight`，桌面 `bottom:88px`、手机 `142px` 全部一致，最终实现沿用同一组数值。
- 新增守卫：`test_ui_seek_buffer_rail.js` 钉住三段停顺序、把手尺寸与描边、桌面与手机两处锚点、手机 `overflow:visible`、映射四例（正常／越界／无 ranges／被接管）；`fnos-design.spec.js` 桌面那条改成「传输组中心偏差 ≤1px + 动作区贴右 ≤24px」，并新增一条 800px 窄窗用例用超长标题验证截断而不是推走控制区。
- 一个需要说明的地方：R483 当时没跑到 `test_ui_metadata_provider_settings.js`，留下三条红灯（`ensureMetadataProviderSaveAction` 已删但守卫仍要求存在、`saveMetadataProvidersBtn` 已变静态按钮但守卫仍要求「不得提前绑定」、提示文案已改但守卫仍查旧句子）。本轮已按新结构反向改写，三条全部转绿。
