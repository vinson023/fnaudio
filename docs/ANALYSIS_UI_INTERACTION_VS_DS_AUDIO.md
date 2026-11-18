# Audio Station 的界面与交互：逆向分析 + 与 fnAudio 的差异

> 结论先行：**AS 的界面是一套「按设备与方向分桶的资源系统」，fnAudio 是一套「按宽度断点的 CSS」。同一件事两种成本：AS 用 8 份播放条 XML 换来的能力，我们用 3 条媒体查询就拿到了，所以「分桶」本身不值得抄。真正值得抄的是三个**交互细节**：进度条松手后 200 ms 内不跟随播放位置（否则滑块会先弹回再跳过去）、进度条的命中区是视觉轨道的 13 倍、专辑有详情页而 fnAudio 点专辑只是把列表过滤掉。另外 AS 自己把「长按拖拽」和「滑动删除」都关掉了，这与我们 R589 的裁定一致——不是我们保守，是这条路连原生实现都放弃了。

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `Android-DSaudio.3.16.0-547.cn.apk` | 已反编译：`res/layout*` 7 个布局桶共 345 个 XML、`values/dimens.xml` 972 行、`com.synology.p000dsaudio` 624 个类 | **可逐字验证**（A 档：文件名 + 行号） |
| `AudioStation-x86_64-7.0.3-5401.spk` | 加密容器（前几轮已复核：头 `42 AD BE EF`，无 tar/zip/squashfs 签名） | 服务端与 UI 无关，本轮不涉及 |
| fnAudio 源码 | 本仓库 | 可逐行核对 |

界面这块的取证比前几轮**更硬**：布局 XML 是声明式的，能直接读出尺寸、可见性、层级；`dimens` 能读出确切数值；`@integer/xxx_visibility` 能读出"什么条件下显示"。凡是「AS 在某个断点下怎么做」的结论都有资源文件支撑。只有「为什么这么做」属于推断，会逐条标注。

---

## 1. 壳层：抽屉 + 标签页 + 横屏详情栏

### 1.1 三个容器，三种宽度策略

`main_drawer.xml` + `fragment_drawer_menu.xml` + `content_fragment.xml` 拼出主壳：

| 部件 | 关键尺寸 | 出处 |
|---|---|---|
| 抽屉宽度 | `280dp` | `values/dimens.xml` |
| 抽屉项最小高 | `56dp` | 同上 |
| 标签页标题 | `13sp` | 同上 |
| 横屏详情栏 | `286dp` 固定宽 | `content_fragment.xml:7-12` |
| 分页容器 | `ViewPager2` | `fragment_pager.xml:3-7` |

### 1.2 详情栏只在「大平板横屏」出现

这是本轮最容易被误读的一处。`content_fragment.xml` 左侧那个 286dp 的详情栏，可见性写的是 `@integer/main_container_detail_land_visibility`：

```xml
<FrameLayout
    android:visibility="@integer/main_container_detail_land_visibility"
    android:layout_width="wrap_content" ...>
    <include android:layout_width="286dp" layout="@layout/container_details_land"/>
</FrameLayout>
```

而 `values/integers.xml:49-50` 是：

```xml
<integer name="main_container_detail_land_visibility">@integer/gone</integer>
<integer name="main_container_detail_land_visibility_tablet">@integer/visible</integer>
```

只有 `values-sw720dp/integers.xml:3` 把它改成 `_tablet`。也就是说：**手机横屏没有详情栏，只有 ≥720dp 的大平板横屏才有**。同一份 `content_fragment` 在竖屏/手机上走的是 `container_details_port`（作为可滚动的头部块）。

这个「一份布局 + 一个 visibility 整数」的写法本身值得记：它把"某个部件在某类设备上不存在"表达成资源覆盖，而不是 `if (isTablet())` 散在代码里。

### 1.3 fnAudio 的壳层

`.shell` 是 `220px + 1fr` 的网格（`app.css:176`），窄屏塌成单列（`app.css:249`）；侧栏在手机上变成横向滚动的 nav（`app.css:91`）。

**差异**：AS 的「列表 + 详情」是**并列**的（详情栏常驻左侧），fnAudio 是**替换**的（点专辑 → 列表被过滤）。见 §2.4。

---

## 2. 列表与行

### 2.1 AS 的行：60dp，一套布局承载三种模式

`song_item_fresco.xml` 的行是固定 `60dp`，里面同时预置了三套只在特定模式下可见的槽位：

| 槽位 | 尺寸 | 平时 | 多选模式 | 排序模式 |
|---|---|---|---|---|
| `drag_handle` | — | 隐藏 | 隐藏 | **显示** |
| `SongItemCheckBox` | — | 隐藏 | **显示** | 隐藏 |
| `SongItemCover` | `50dp` | 显示 | 显示 | 显示 |
| `SongItemTitle` / `SubTitle` | `14sp` | 显示 | 显示 | 显示 |
| `SongItemTime` | — | 显示 | 显示 | 显示 |
| `SongItemShortCut` | `48dp` | 显示 | 显示 | 显示 |

**一份 XML，三种模式切可见性**，而不是三套布局或三套 adapter。行高固定 60dp 也意味着切模式时列表不会跳。

### 2.2 网格/列表双形态

`FileSongListAdapter.java:276-281` 用 `isListMode()` 选两套 view type：

```java
return isListMode() ? 0 : 3;   // 0/1/2 = 列表三种行，3/4/5 = 网格三种格
```

也就是说 AS 的**文件夹/歌曲列表可以在列表与网格之间切换**，而且两种形态各有自己的行模板（`container_grid_item.xml` / `container_list_item.xml`）。

### 2.3 快速滚动条：只在手柄上接收触摸

`fast_scroller.xml` 是一个覆盖整个列表高度的 `SynoFastScroller`，参数写得很清楚：

```xml
app:fastScrollerAutoHideEnabled="true"
app:fastScrollerAutoHideDelayInMillis="1000"
app:fastScrollerBubbleEnabled="false"
app:fastScrollerIgnoreTouchesOutsideHandle="true"
```

三条设计决定：

1. **1 秒后自动隐藏**——不占视觉，但滑一下就在；
2. **没有气泡**——移动中不显示"B"之类的字母气泡（很多实现有，它没有）；
3. **手柄外的触摸一律忽略**——这一条是关键：一个满高的浮层如果吃掉所有触摸，列表就没法滚了。`ignoreTouchesOutsideHandle` 让它只在手柄那一窄条上接管。

### 2.4 fnAudio 的列表

- 行是 `display:grid` 的多列布局（`app.css:10`），列可配置（`app.js:1863` 的 `column-drag-handle` + 上移/下移）；
- **没有网格视图**（全仓只有 `.shell` 与 `.player` 两处 `grid-template-columns`）；
- **点专辑进专辑详情页**（`renderAlbumDetail()`，`app.js:3686`）：512 封面侧栏 + 专辑名 / 艺人 / 发行日期，右侧面包屑 + 曲目表；歌手侧另有 `renderCreatorAllTracks()` 的「所有歌曲」页。**本文初稿说「点专辑只是过滤列表」是错的**，见 §7；
- 选择态按 **row key 重放**（`app.js:3822`：渲染后 `setTrackSelection([...state.selectedTrackRowKeys])`），刷新不会丢选择。

### 2.5 差异

| 能力 | AS | fnAudio |
|---|---|---|
| 行高 | 固定 60dp | 内容驱动（封面 42px） |
| 模式槽位 | 一套布局切可见性 | `.is-selected` + 独立手柄 |
| 网格视图 | ✅ 双 view type | ❌ 只有列表 |
| 快速定位 | ✅ 字母条 | ❌ 只有搜索 |
| 专辑详情 | ✅ 独立详情栏/页 | ✅ 独立详情页（侧栏 512 封面 + 元数据） |
| 选择在刷新后 | 冻结刷新（`PlayingQueueFragment:611`） | 按 key 重放（更宽容） |

---

## 3. 播放器

### 3.1 八份播放条

AS 的播放条按「方向 × 设备」分桶：

| 文件 | 用途 |
|---|---|
| `layout-port/main_control.xml` | 手机竖屏播放条 |
| `layout-land/main_control.xml` | 手机横屏播放条 |
| `layout-port/tablet_main_control.xml` | 平板竖屏 |
| `layout-land/tablet_main_control.xml` | 平板横屏 |
| `layout-port/player_control.xml` 等四份 | 对应的全屏播放页 |

手机竖屏与横屏的差别**只有一处**：那 52dp 的进度带，竖屏 `alignParentBottom`、横屏 `alignParentTop`。其余完全一样。

**这 8 份 XML 是 Android 没有媒体查询的代价**，不是设计复杂度。我们用 3 条断点做到同一件事，这一点上不需要向 AS 学。

### 3.2 播放条是「信息行 + 52dp 进度带」

`layout-port/main_control.xml` 的结构：

```xml
<RelativeLayout android:layout_height="@dimen/mini_player_total_height">   <!-- 96dp -->
    <LinearLayout android:layout_height="@dimen/mini_player_visual_height"  <!-- 70dp -->
                  android:layout_alignParentBottom="true">
        <include layout="@layout/playing_control_panel_song_info"/>          <!-- 封面+标题 -->
        <include layout="@layout/player_quick_controls_medium"/>             <!-- 上一首+播放 -->
    </LinearLayout>
    <include android:layout_height="52dp"
             layout="@layout/player_playbar_only_seekbar"/>                  <!-- 52dp 进度带 -->
</RelativeLayout>
```

`values-port/dimens.xml:7-10`：

```xml
<dimen name="mini_player_total_height">96dp</dimen>
<dimen name="mini_player_visual_height">70dp</dimen>
```

**总高 96dp > 可视 70dp**：多出来的那 26dp 是给进度带留的。进度带自己又是一个 52dp 高的容器（`player_playbar_only_seekbar.xml:1-11`），里面只有一个 `MediaSeekBar`，而 seekbar 的**视觉轨道只有 4dp**（`android:maxHeight="4dp"`、`android:minHeight="4dp"`、`progressDrawable` 画的就是 4dp）。

于是命中区与视觉的比例是 **52 : 4 = 13 : 1**。

### 3.3 三档控件密度

`player_quick_controls_{narrow,medium,wide}.xml` 是同一组按钮的三种子集，靠 `visibility` 控制：

| 档位 | 可见按钮 | 总数 |
|---|---|---|
| `narrow` | 只有**播放** | 1 |
| `medium` | 上一首 + 播放 | 2 |
| `wide` | 上一首 + 播放 + 下一首 + 停止 | 4 |

注意 `narrow` 是**只剩播放键**——不是"把按钮缩小"，是"把上一首/下一首/停止整个去掉"。这是最激进的降级，见 §7「不借鉴」。

### 3.4 进度条的三态守卫（本轮最重要的一条）

`widget/MediaSeekBar.java` 是 AS 自己写的 seekbar。它的 `setProgress` 只有四行（`:276-282`）：

```java
@Override
public void setProgress(int progress) {
    if (this.mIsTracking || getMIsWaitingForSeekCompleted()) {
        return;
    }
    super.setProgress(progress);
}
```

两个守卫：

```java
// :210-219
private final boolean getMIsWaitingForSeekCompleted() {
    if (this.mLatestSeekTimeStamp == -1) return false;
    if (System.currentTimeMillis() - this.mLatestSeekTimeStamp <= 200) return true;
    this.mLatestSeekTimeStamp = -1L;
    return false;
}
```

- `mIsTracking`：手指按在滑块上时，播放器报上来的位置**一律不写**，滑块只跟手指走；
- `mLatestSeekTimeStamp`：松手后 **200 ms 内**，播放器报上来的位置**同样不写**。

第二条是这条设计的全部价值。松手那一刻 `seekTo()` 才发出去，播放器要过一会儿才把位置挪过去；这期间它上报的还是**旧位置**。没有这 200 ms 的窗口，滑块会先弹回旧位置、再跳到新位置——一次可感知的抖动。

另外两个细节：

- 拖动中的位置存在局部变量 `positionOverride` 里（`:79`），**松手时才 `seekTo`**（`:93-104`）。不是边拖边发请求；
- `setOnSeekBarChangeListener` 直接抛 `UnsupportedOperationException("Cannot add listeners to a MediaSeekBar")`（`:266-269`）——监听器是它自己独占的，外部不能再挂一个来打架。这条是"把不变量写进 API"的典型做法。

### 3.5 fnAudio 的播放器

- 单播放条 + 3 条断点（760 / 1100 / 1180）；
- 手机上的进度条：`app.css:235-239`

```css
.progress input{height:8px!important; ...}
.progress input::-webkit-slider-runnable-track{height:4px!important; ...}
.progress input::-webkit-slider-thumb{width:6px!important;height:6px!important; ...}
```

**视觉轨道 4px，命中区 8px，滑块 6px**。比例 2 : 1。手指要在 8px 高的条上命中，这是本轮最实的一处差距（Material 的最小触控目标是 48dp）。

- seek 的处理：`app.js:12669-12675`

```js
$("seek").oninput = e => { state.seeking = true; previewSeek(e.target.value); };
$("seek").onchange = e => commitSeek(e.target.value);
$("seek").onpointerup = e => commitSeek(e.target.value);
$("seek").ontouchend = e => commitSeek(e.target.value);
```

- 位置回写：`app.js:1078` `if (!state.seeking) $("seek").value = ...`

也就是说 fnAudio 有**第一态**（拖动中不写），但**没有第二态**。`commitSeek` 的第一行就是 `state.seeking = false`（`app.js:6123`），而 `seekTo` 之后的位置回报要等一个 `timeupdate`（约 250 ms）。所以松手后到位置真正更新之间，滑块会被旧位置重画一次。

---

## 4. 模式与手势：AS 自己关掉了两个「常识手势」

`adapters/SimpleItemTouchHelperCallback.java` 是播放队列的拖拽回调，三个方法值得连起来看：

```java
// :52-58
public int getMovementFlags(RecyclerView recyclerView, RecyclerView.ViewHolder viewHolder) {
    int i = this.mAdapter.isDragMode() ? 3 : 0;      // 只在 drag 模式下允许拖动
    this.dragFlags = i;
    this.swipeFlags = 0;
    return makeMovementFlags(i, 0);
}
// :60-62
public boolean isItemViewSwipeEnabled() { return false; }   // 没有滑动删除
// :64-66
public boolean isLongPressDragEnabled() { return false; }   // 长按不启动拖动
```

三条决定合起来是一句话：**拖拽必须先进「排序模式」，且必须抓手柄；长按和滑动都不触发任何破坏性动作。**

配套的是 `AbsAdapter.java:226-232` 的两个模式位（`isCheckMode` / `isDragMode`），以及 `PlayingQueueFragment.java:611-621` 的模式分支：

```java
if (this.adapter.isDragMode() || this.adapter.isCheckMode()) return;   // 下拉刷新停用
...
if (this.adapter.isDragMode() || this.adapter.isCheckMode()) return;   // 行点击（=播放）停用
```

**进模式后，所有平时会改变列表或跳转的默认手势一律停用。** 这是一个干净的规则：模式内只有一个手势是活的。

### 4.1 fnAudio 的同与不同

- 栏目配置里已经是同一形态：`app.js:1863` 的 `column-drag-handle` + `上移`/`下移` 按钮，**显式手柄、不靠长按**；
- 但选择态用的是另一种解法：不冻结刷新，而是**按 row key 重放**（`app.js:3822`）。列表刷新后，仍在页上的行保持选中，已经不在页上的 key 自然不匹配。

两种解法都成立，取舍不同：

| | AS | fnAudio |
|---|---|---|
| 选择中列表变了 | 刷新被挡住 | 刷新照常，选择按 key 重放 |
| 风险 | 用户下拉时没反应（会以为卡了） | 选中项可能已不在当前页 |

fnAudio 的做法在"库正在被别的设备改动"时更宽容，所以**不借**。

### 4.2 与 R589 裁定的一致性

R589 判定「队列拖拽重排不做」，理由是 HTML5 `draggable` 在 Android WebView 触摸下不触发。本轮的证据补充了一条更有力的理由：**AS 自己把 `isLongPressDragEnabled` 和 `isItemViewSwipeEnabled` 都关成了 `false`**。也就是说在原生 Android 上，长按拖拽与滑动删除同样被认为是危险手势，它选了"显式模式 + 手柄"这条路。我们的结论与它一致，不是保守。

（这条不影响 R589 的落地形态——「插播已有行」已经覆盖了同一个诉求。此处只做证据补强，不重开该条。）

---

## 5. 状态：空、加载、对话框

### 5.1 空态：两边结构相同

`empty.xml`：`ImageView`（`bgicon_nodata`）+ `TextView`（`no_data_desc` = 14sp、`text_desc` 色、左右各 25dp、`lineSpacingExtra 3dp`），整体 `gravity=center`。

fnAudio `index.html:120`：`<div class="empty">` 里一个 SVG 图标 + `<h2>` + `<p>`，`app.css:15` 居中、`margin:80px auto`（手机 36px）。

**结构等价，不需要借。**

### 5.2 加载态：都只有进度文本

AS 用 `fragment_progress_grid.xml`（`progress_container` + `progress_text` + 一个空 `grid`），fnAudio 用 `正在加载音乐库：N 首`（`app.js:2153`）。两边都没有骨架屏。**同级，不构成差距。**

### 5.3 对话框：平板上固定宽度，手机上近全屏

`values-sw600dp/dimens.xml` 把一批对话框尺寸钉死：`model_view_dialog_width 420dp`、`lib__large_dialog_width 560dp`、`gdpr_large_dialog_width 420dp`。

fnAudio：`dialog{width:min(520px,calc(100vw - 30px))}`（`app.css:242`）——**一条 `min()` 同时表达了这两件事**，比 AS 的两套资源更省。同一思路，不需要借。

### 5.4 下拉刷新：不借

AS 在 `content` / `playingq` / `playlist` / `playlistsong` 四个页面都挂了 `SwipeRefreshLayout`。fnAudio 没有下拉刷新，因为它**知道库什么时候变**（inotify + 签名），另外有「立即扫描」按钮和扫描状态。

AS 需要下拉刷新，恰恰是因为它的页缓存没有失效机制（见库分析 §1.7）。我们补一个"手动兜底手势"只会让用户以为库经常在变。**不借。**

---

## 6. 触控与无障碍

| 项 | AS | fnAudio |
|---|---|---|
| 抽屉项高 | 56dp | `nav-item` 无固定高 |
| 行内快捷按钮 | 48dp | 无 |
| 进度条命中区 | 52dp | 38px（R594 前是 8px） |
| 进度条视觉 | 4dp | 4px |
| 图标 `contentDescription` | 布局里逐条写 | `aria-label`，由 `test_ui_control_names.js` 守卫（117 控件 / 0 无名） |

fnAudio 的无障碍是**被守卫钉住的**（那个测试会数控件并断言每个都有可访问名），这一点比 AS 的"靠开发者自觉写 contentDescription"更可靠。唯一的实质差距是进度条的命中区。

---

## 7. 值得借鉴的清单

| 优先级 | 项 | 状态 | 落点 |
|---|---|---|---|
| **P1** | 进度条松手后 200 ms 内不跟随播放位置 | ✅ 已落地 | `seekPositionIsSettled()`，六处回写统一走它（`app.js`）；守卫 `tests/test_ui_seek_settle.js` |
| **P1** | 进度条命中区 8px → 38px（视觉仍 4px） | ✅ 已落地 | 手机进度行 24px → 38px（三行加两个 2px gap 仍是 136px），输入框填满整行；`app.css` |
| **P2** | 专辑/歌手详情页 | ❌ **撤回：已经有了** | `renderAlbumDetail()`（`app.js:3686`）就是它——512 封面侧栏 + 专辑名/艺人/发行日期 + 面包屑 + 曲目表；歌手侧有 `renderCreatorAllTracks()`。本文 §2.4 那句「点专辑只是过滤列表」是**错的** |
| **P2** | 网格视图（专辑墙） | ✅ 已落地 | `setAlbumLayout()`／`albumLayoutBar()`／`renderAlbumTiles()`（`app.js`）+ `.album-grid`（`app.css`）；守卫 `tests/test_ui_album_layout.js` |
| **P3** | 长列表字母快速定位 | ❌ 关闭：做不对 | 见 §10 第 3 条 |
| **P3** | 行结构承载多模式 | ❌ **已满足** | `renderTrackRow()` 本来就是单模板：`is-current`/`is-selected` 类 + `playingIndicator`/`cover` 槽位 + 列由 `activeTrackColumns()` 驱动，没有第二套结构可收敛 |

> 六条里真正需要动的是四条；两条经复查发现 fnAudio 已经是那个形态，一条经评估做不对。**结论写在这里，不留在待办里。**

---

## 8. 不借鉴：写下来防止回流（已裁定）

> **2026-11-18 负责人裁定：这六条不再借鉴、不再排期、不再复核。** 记在这里是为了下次别再提——不是待办，也不是「以后有空再说」。
> 口径与 `docs/LIBRARY_VIEWS_PLAN.md`、`docs/ANALYSIS_TAGS_COVERS_LYRICS_CUE_VS_DS_AUDIO.md` §6 一致。

| AS 的做法 | 为什么不借鉴 |
|---|---|
| 播放条降级成"只剩播放键"（`player_quick_controls_narrow`） | fnAudio 的 e2e 钉住「上一首 / 播放 / 下一首 居中」（`fnos-design.spec.js`），那是负责人要求；去掉上一首/下一首不是空间问题的正解 |
| 长按拖拽、滑动删除 | AS 自己都关成了 `false`；与 R589 裁定一致 |
| 进模式冻结下拉刷新 | 我们用 row key 重放选择，刷新不必被挡；冻结会让用户以为卡了 |
| 下拉刷新 | 我们有 inotify + 扫描按钮，补一个手动兜底手势会误导用户 |
| 从封面取色做主题 | **AS 根本没有**：全仓 0 处 `Palette` 引用。别把它当成"AS 有而我们没有" |
| 8 份播放条 / 详情栏 visibility 整数 | 那是 Android 缺媒体查询的代价；我们的断点 + `min()` 更省，抄过来是给自己加维护面 |

六条一律**不做**，也不再进入任何计划。

---

## 9. 一句话对比

| 维度 | AS | fnAudio |
|---|---|---|
| 壳层 | 抽屉 280dp + 标签页 + 大平板横屏 286dp 详情栏 | 侧栏 220px / 手机横向 nav；无**并列**详情栏（详情是整页） |
| 列表 | 固定 60dp 行 + 模式槽位 + 网格/列表 + 字母条 | 多列可配置行 + 右键菜单 + 选择重放；无网格、无字母条 |
| 播放器 | 8 份 XML + 3 档控件 + 52dp 进度带 + 三态守卫 | 1 条 + 3 断点 + 8px 进度条 + 两态守卫 |
| 手势 | 显式模式，长按/滑动都关闭 | 显式手柄（栏目配置），无破坏性手势 |
| 状态 | empty / progress / 下拉刷新 | empty / 进度文本 / 扫描按钮 |
| 无障碍 | 手写 contentDescription | aria-label + 测试守卫（117/0） |

**如果只做两件事**：补上进度条的第二态守卫（松手后 200 ms），把命中区从 8px 提到 ≥44px。两条都在同一个控件上，加起来不到二十行，但都是手指能直接感知的差别。

---

## 10. 落地记录（R594）

四条落地，两条经复查撤回，一条关闭。

**1. 进度条的 200 ms 稳定窗（P1）**。新增 `seekPositionIsSettled()`：手指不在滑块上、且距上次 `seekTo` 已过 200 ms 才认为播放器的位置可信。六处回写（原生快照、远端 tick 的 `seconds` 与写入、投送 tick 的 `seconds` 与写入、`timeupdate`）统一走它，替掉了四处各自拼的 `!state.seeking`。`commitSeek()` 在发出 seek 后记 `state.seekSettledAt`。

一处实现细节值得记：判定写成 `!(settledAt > 0) || Date.now() - settledAt > 200`，而不是直觉的 `Date.now() - state.seekSettledAt > 200`。后者在字段缺失时得到 `NaN`，而 `NaN > 200` 是 false —— 轨道会**永久冻结**。`tests/test_ui_seek_settle.js` 专门钉了这一条。

**2. 进度条命中区（P1）**。手机进度行从 24px 提到 38px，输入框填满整行，视觉轨道仍是 4px、滑块仍是 6px。三行 44+38+50 加两个 2px gap 仍然等于 136px，所以播放条总高没动，`test_ui_mobile_layout.js` 里那条「136px 三行」的断言改成**算术校验**（三行加间距必须等于总高），而不是钉死某一行的像素值。

没做到 44px 的原因写清楚：44+50+50 = 144 ≠ 136，要 44px 就得同时把播放条总高加 8px，那会动到手机播放器的整体几何与 e2e。38px 是「不动布局」的上限，是 8px 的 4.75 倍。

**3. 专辑网格（P2）**。`state.albumLayout` 存在本机（`fnaudio.albumLayout.v1`），只认 `"grid"` 这一个值，其余一律回落到列表。切换栏 `albumLayoutBar()` 给出张数与两个按钮，瓦片 `renderAlbumTiles()` 复用 `groupIcon()` 的 160 缩略图与懒加载调度器，并且**带同一套 `data-group-*` 契约**——所以点击、长按、分组菜单、多选全部走原有处理函数，没有第二套选择模型。切换时手动保住滚动位置（立即 + 一帧后各一次，因为行提交会重排）。

**4. 两条撤回**。专辑/歌手详情页**本来就有**（`renderAlbumDetail()` / `renderCreatorAllTracks()`），是本文初稿的事实错误，已在 §2.4、§2.5、§9 改正；行结构收敛**本来就已经是**那个形态（单模板 + 类 + 槽位），没有重复结构可收。

**5. 一条关闭：字母快速定位**。做不对，理由有三条：

- 列表是**服务端分页**（120/页），字母条要跳到 "S"，必须能按首字母**锚定**一个游标。服务端目前只有 `search`（子串匹配），没有前缀锚定参数；
- 用现成的游标去合成一个「首字母为 S」的锚点，得为每一种排序键分别构造（`title`/`artist`/`album` 是文本，`added`/`track_no` 是数值），而且游标 token 编错会直接破坏翻页——这是全仓最不该出错的一段；
- 收益边际：搜索已经覆盖了「找某一首/某一张」这个真实需求，字母条只在「按顺序翻」时更省事。

P3 的优先级加上这三条，结论是不做。**关闭，不留待办。**
