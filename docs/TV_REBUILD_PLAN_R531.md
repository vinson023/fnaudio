# fnAudio TV 端重构方案（R531）

> 状态：第 1–3 期已实施；第 4 期电视端已实施并端到端验证，手机端（扫码发送）待拍板
> 依据：`references/TVapp/` 内两份 APK 反编译实测（网易云音乐 TV 1.1.80、QQ 音乐 TV 9.0.0.39）+ fnAudio 现有 TV 端代码审计
> 作者：AI
> 日期：2026-11-10（v5：第 4 期电视端落地，偏离记在 §12.1–§12.3）

---

## 0. 一句话结论

现在的电视版把手机端的「左侧竖排导航 + 内容卡片 + 覆盖式播放页」直接搬到了大屏，它的问题不是配色或圆角，而是**信息架构错位**：用 136dp 宽的侧栏吃掉 14% 屏宽、字号按桌面视距给（16sp）、播放页没有内容（只有封面和队列）、登录要在遥控器上敲 IP 和密码。

两家国内标杆（网易云 TV、QQ 音乐 TV）**都用顶部横向 Tab、都没有侧栏**，播放页都是「封面 ↔ 歌词」双形态，歌词区都固定占右侧 40–43% 宽。这是行业收敛的结果，不是审美偏好。

本方案按这套模型重做，并把你要求的「登录复用手机端功能」落到具体的类拆分上。全文给到可直接开工的页面规格（dp/sp/时长）与分四期的实施清单。

---

## 1. 输入材料与研究方法

### 1.1 实际提供的文件

| 文件 | 大小 | 包名 | 判定 |
|---|---|---|---|
| `NeteaseCloudMusic_MusicTV_official_1.1.80…apk` | 48.9 MB | `com.netease.cloudmusic.tv` | 网易云音乐 TV 版，资源名被 AndResGuard 混淆 |
| `10007068_self_32_kg_9.0.0.39…apk` | 72.2 MB | `com.tencent.qqmusictv` | QQ 音乐 TV 9.0.0.39，**资源名未混淆**，可读性最好 |

（上一版目录里那份 222 MB 的 `NeteaseCloudMusic_Music_h5_9.6.22` 是网易云手机版，已无用，不参与本节结论。）

关于 QQ 音乐这个包的构成，需要先说清楚，否则会误读：

- 包名与桌面 label 都是 QQ 音乐，`uses-feature` 为 `type.television` + `software.leanback`，是**标准电视应用**；
- 但 7 个 dex、22424 个类里同时存在 `com.tencent.karaoketv`（全民 K 歌 TV）与 `com.tencent.qqmusiccar`（车载引擎）。**主界面是 K 歌的 `HomeTabsFragment`，音乐播放页复用 `qqmusiccar` 的 player 布局**——腾讯把「K 歌 TV + 音乐 TV + 车机」做成了一个工程；
- 因此读它的布局要分两类：`kgtv_*` = 电视界面，`activity_player*` / `layout_player_*` = 音乐播放（从车机复用，字号偏小，下面会对齐换算）。

**局限**：两份 APK 都只有 ARM ABI，本机是 x86_64，无 ARM 转译镜像，**无法真机运行截图**；所有结论来自布局与代码，不是看图。

### 1.2 方法

1. `aapt2 dump badging` 取清单与入口，`aapt2 dump xmltree` 取 Activity 列表；
2. `jadx 1.5.6` 导出资源与全量 Java；
3. 从 `AndroidManifest` 还原页面树，按 `R.layout.*` 引用把页面与布局对齐；
4. 统计设计常量分布（间距/字号/色值/动效时长）；
5. 逐页读关键布局 XML（登录、播放、歌词、主界面、列表）与对应代码。

三份 APK 的规模：

| 指标 | 网易云 TV | QQ 音乐 TV |
|---|---|---|
| 布局文件 | 709（解析出 564） | 965（全部明文） |
| 颜色定义 | 769 条 / 398 唯一值 | 823 条 / 516 唯一值 |
| 尺寸定义 | 1240 条 | 4054 条（含多分辨率覆盖） |
| 类数量 | 8095（86 个反编译失败） | 22424（18769 个失败，混淆+壳） |
| 能读到的业务类 | 完整 | 主界面/播放/焦点容器类完整，业务逻辑大部分被混淆 |

QQ 音乐的类失败率高，但**布局、尺寸、颜色、字符串全部可读**，加上 `karaoketv/ui` 下的焦点容器类完好，结论不受影响。

---

## 2. 反编译结果概览（网易云 TV）

| 项目 | 结果 |
|---|---|
| 技术栈 | 纯原生 Android（Kotlin + Java 混合），无 Flutter/RN |
| 原生库 | 53 个 per ABI：自研音视频（`libnecmMediaPlayer`/`libffmpeg`/`libneaudioeffects`）、`libmmkv`、`libkoom`（OOM 监控）、`libxcrash` |
| 布局 | 709 个（564 个解析为明文），最大仅 432 行 → **UI 大量由代码与自定义 View 组装**，不是 XML 堆出来的 |
| 自定义控件 | `MusicTVTabLayout`、`TvFocusFrameLayout`（焦点搜索框定）、`TVLeanbackViewPager`、`PlayerDiscViewFlipper`、`RotationConstraintLayout`（唱片旋转）、`IotTvLyricView`、`OneLineLyricView`、`FadingEdgeLayout`、`TVMarqueeTextView`、`IotPlayerSeekBar` |
| 页面数 | 103 个 Activity（业务约 35 个），播放形态拆成 8 个 Fragment |
| 主题色 | 深底 `#080812`，强调红 `#FF3A3A`，主文字链为**白色 + 透明度阶梯** |

QQ 音乐 TV 的结构差异在 3.9 节单列（它是 K 歌 + 车载 + 音乐三合一工程，混淆程度高，但布局未混淆）。

---

## 3. 网易云 TV 的设计体系（实测）

### 3.1 导航模型：顶部居中文字 Tab，不是侧栏

主界面布局 `af.xml`（97 行）：

```
ConstraintLayout
├── TvFocusFrameLayout          searchFocusUp = @id/t6（内容区按上 → 焦点搜回 Tab）
│   ├── TVLeanbackViewPager     全屏
│   └── include mr.xml          loading / 空态 / 错误 三态容器
├── View ai5                    76dp 顶部遮罩（gone，滚动时渐显）
├── MusicTVTabLayout  id=t6     h=37dp  top=19dp  start=230dp end=200dp
│                               tabMode=2（可滚动）  tabMinWidth=24dp
│                               tabPaddingStart/End=16dp  文字 18sp
├── FrameLayout ai8             h=39dp  与 Tab 同基线（焦点指示条）
├── ImageView vn                20dp  右上角图标  top=28dp end=40dp
└── ImageView vm + TextView     55×10dp + 5dp 字号（VIP 角标）
```

要点：

- Tab 只有 **37dp 高**，距顶 **19dp**，横向居中（左右各预留 230/200dp，给右上角图标和滚动留白）；
- Tab 文字 **18sp**，`tabMode=2` 表示 Tab 多了可以横向滚动；
- 内容区是全屏 `ViewPager`，**没有侧栏**，所以首页卡片是从屏幕左边缘 48dp 开始的满宽；
- Tab 列表**由服务端下发**（`MainTabResponse` / `tabCode`，如 `TAB_ATMOSPHERE`），客户端只渲染；
- 内容区任意位置按「上」→ `searchFocusUp` 把焦点送回 Tab 条；从 Tab 按「下」回到上次停留的卡片。

### 3.2 视觉规范（数值全部来自反编译）

**色板**：颜色定义 769 条、398 个唯一值，其中 60% 以上是白色透明度阶梯：

| 用途 | 值 |
|---|---|
| 页面底 | `#080812` |
| 主文字 | `#FFFFFF` |
| 次文字 | `#99FFFFFF` / `#B3FFFFFF` |
| 三级文字/说明 | `#66FFFFFF` / `#4DFFFFFF` |
| 分割线/描边 | `#1AFFFFFF` / `#33FFFFFF` |
| 卡片底 | `#29FFFFFF`（16% 白） |
| 强调 | `#FF3A3A`（红） |
| 遮罩 | `#99000000` / `#33000000` |

**间距**（1240 条 dimens 的分布，前 8 名）：

```
8dp ×68   16dp ×59   4dp ×50   10dp ×44
24dp ×44   6dp ×36   2dp ×36   20dp ×36
```

→ **4dp 栅格，8dp 为主节奏**，16dp 用于区块内，48dp 用于屏幕左右边距。

**字号**（styles 里 textSize 的分布 + 关键页实测）：

```
14sp ×20   18sp ×12   13sp ×10   12sp ×9   16sp ×9
```

页面级关键值：Tab 18sp、歌名 21sp、歌词正文 21sp / 高亮 28sp、单行歌词 18sp、登录大标题 66px（px，按 1080p 设计稿）。

**圆角**：卡片 15dp，二维码卡片 25dp，封面圆形（`roundAsCircle`），Tab 指示条跟随文字宽度。

**动效**（代码中 `setDuration` 的分布）：

```
400ms ×17   300ms ×6   680ms ×5   500ms ×4   320ms ×1   150ms ×1
```

→ 页面/形态转场 300–400ms，唱片旋转与歌词入场更长（500–680ms），即时反馈 150ms。

### 3.3 首页结构

首页 Fragment（`TVHomePageFragment`）只有 197 行，**内容是服务端下发的 shelf 列表**，客户端按 `tabCode` 渲染。这也是为什么它的布局文件只有 564 个且都不大：所有行都是同一套「卡片行」组件按数据重复。

对我们直接可用的结论：**首页不是一个固定布局，而是「若干条 shelf」的纵向堆叠**，每条 shelf = 标题 + 一行横向卡片。

### 3.4 播放页：黑胶转盘 + 单行歌词（`dq.xml`，131 行）

这是全项目信息密度最高的一屏，逐项拆开：

| 元素 | 规格 |
|---|---|
| 可视化频谱 | 全屏 `CloudMusicVisualizerView`，高度 114.8%，默认 `gone` |
| 唱片底图 | 1:1，**高度占屏 51.9%**，垂直 bias 0.3615 |
| 唱片容器 | `FadingEdgeLayout`，**左右各 45dp 渐隐**（表示唱片可左右滑动切歌） |
| 唱臂 | 594:939，高度 28.8%，水平 bias 0.68，垂直 bias 0.046（压在唱片右上） |
| 歌名 | **21sp**，`sans-serif-medium`，跑马灯，maxWidth 500dp，垂直 bias 0.8217 |
| 单行歌词 | `OneLineLyricView`，宽 **700dp**，字号 **18sp**，`lyricTransScale=0.7`（非当前行缩到 70%） |
| 活动位 | Lottie 340×340（会员促销，我们不需要） |

唱片内部（`fu.xml`）：

```
PlayerDiscViewFlipper（双缓冲，切歌时一张在转一张待用）
├── RotationConstraintLayout   id=o9
│   ├── ImageView  aek   宽 41%（唱片纹理 y8）
│   └── AnimableDrawerImageView aei  高 62.2%，1:1，roundAsCircle（封面）
└── RotationConstraintLayout   id=o_  （同上，另一张）
```

**播放页没有控制按钮条**——网易云 TV 的控制是「按确认键呼出」的浮层（`MoreMenuSlideSheet`、`TvSelectQualityDialog` 等），默认画面上只有唱片、歌名、当前一句歌词。这一点很关键：大屏播放页应当**先给人看，再给人操作**。

### 3.5 全屏歌词页（`mu.xml`）

```
歌词视图 IotTvLyricView
  宽 40%，高 50%
  水平 bias 0.6384（偏右），垂直 bias 0.65（偏下）
  字号：正文 21sp，高亮 28sp
  lineModel=2  alignModel=1  lineType=2（多行滚动居中）
歌名   21sp bold，maxWidth 283dp，跑马灯无限循环，marginTop 74.5dp
副标题 18sp，marginTop 8dp，单行截断
```

要点：**歌词只占屏幕 40% 宽、50% 高，且刻意偏右下**，左上留白给封面/背景氛围——不是全屏铺满。当前行 28sp、其余 21sp，用字号差而不是颜色差做层次。

### 3.6 登录页：扫码（`mt.xml`）

```
ConstraintLayout（根）
├── 全屏登录层 z5  背景 #080812
│   ├── TextView 标题   66px bold（按 1080p 设计稿的 px）
│   ├── TextView 副标题 18sp，marginTop 8dp
│   ├── SimpleDraweeView 主视觉  430×330dp，start=92.3dp，bottom=59.5dp
│   ├── RoundedFrameLayout 二维码卡片 280×330dp，圆角 25dp，end=90dp，bottom=60dp
│   ├── ImageView 二维码 225×225dp，marginTop 27.8dp
│   ├── ImageView 中心 logo 52dp
│   └── TextView 操作文字 18.72sp，225×50dp，marginTop 12.6dp
└── 居中弹窗层 z6（include ms.xml = 40dp 转圈 + 15sp 提示）
```

文案实测：「使用 网易云音乐APP 扫码登录」「其他登录方式」「上次登录」「一键登录」「不是我的账号」。

**这是电视端唯一合理的默认登录方式**：遥控器不该用来敲 IP、端口、用户名、密码。

### 3.7 页面树（35 个业务 Activity）

```
MainActivity（Tab + ViewPager + 内嵌 PlayerFragment 播放条）
├── 播放
│   ├── PlayerActivityV2 / ProgramPlayerActivityV2
│   └── 形态 Fragment：Disc / Lyric / LyricVideo / Video / Portrait
│                     / ImmersiveDisc / ImmersiveVideo / FallScreenCover
├── 内容
│   ├── PlaylistActivity / MyPlayListActivity / PlayListSquareActivity
│   ├── RankingListActivity / DailyRecommendActivity / RecentPlayActivity
│   ├── AlbumPlayListActivity / ArtistCategoryActivity / ArtistDetailActivity
│   ├── VideoSquareActivity / TvVideoActivity / PodcastDetailActivity
│   └── MyCollectActivity / CollectPodcastPlayActivity / CommentCalenderActivity
├── 工具
│   ├── TVSearchActivity / TVSettingActivity
│   ├── TvH5Activity（H5 容器）
│   └── AtmosphereContentActivity（氛围听）
└── 登录 / 会员 / 购买
    TvLoginActivity / MemberRightActivity / HistoryOrderActivity / HisenseInitActivity
```

**播放页是独立 Activity**，从任何页面都能唤起；主界面里嵌的是播放条（`PlayerFragment` 的 mini 形态）。我们的现状是「播放页 = 覆盖在 MainActivity 上的 View」，这个差异导致返回栈和焦点恢复很难做对。

### 3.8 焦点与按键

- `TvFocusFrameLayout` 用 `searchFocusUp/Left/Right` **显式框定焦点搜索范围**，避免系统 `FocusFinder` 在复杂卡片网格里乱跳；
- 焦点态 = 白色 3px 描边 + 轻微放大（代码里出现 `1.05f`），`setPivotX` 调整缩放中心；
- 全局 `OnGlobalFocusChangeListener` 挂在 Activity 上，用于：焦点离开内容区时收起顶部遮罩、焦点进入卡片行时联动 Tab 高亮、控制播放条显隐；
- `fastKeyDownHelper` 处理长按方向键的加速滚动。

### 3.9 QQ 音乐 TV 9.0.0.39 的对照

#### 视觉基准

- 设计稿 **1920×1080 px**：`values-1920x1080/dimens.xml` 里 `tv_screen_height = 540dp` → 与我们的 960×540dp 视口一致；
- 尺寸命名 `kgtv_qmusic_dp_N` = **N/2 dp**（设计稿 px ÷ 2），例如 `kgtv_qmusic_dp_120 = 60dp`；
- 品牌绿 **`#31C27C`**，且 `lyric_hilight_text_color` 就是这个绿 → **歌词高亮用品牌色**；
- 自带三款字体：`DIN-Alternate-Bold`（数字）、`VisbyCF-Bold`（英文/logo）、`方正兰亭中`（中文）。

#### 主界面（`fragment_home_tabs.xml`，128 行）

```
FocusRelativeLayout
├── 全屏背景图（centerCrop，kgtv_page_common_bg）
├── CompatViewPager  全屏，nextFocusUp = tab_layout
├── HomeTitleLayout  高 250dp（可随滚动收缩为 mini 状态）
│   ├── HomeTabsTopView   高 60dp，左右 margin 22dp，内 padding 15dp
│   └── HorizontalTablayout  高 64dp，左右 padding 22dp
└── 标题容器  高 64dp（右侧 logo）
```

- 顶部区总高 **250dp**，Tab 条 **60–64dp**，左右 22dp，**左对齐**（网易云是居中）；
- 内容 `RecyclerView` 的 `paddingBottom = 60dp`——正好是底部播放条的高度；
- 有 `EmptyFocusView`（1px 透明可聚焦占位），用于「焦点在 Tab 时内容区不移动」。

#### 播放页：双形态镜像（最大差异点）

**封面模式**（`activity_player.xml`，144 行）的 Guideline：

| Guideline | 位置 |
|---|---|
| start | **7.29%** |
| middle_start | **55%** |
| middle_end | **60.7%** |
| end | **92.7%** |

- 封面：`1:1`，高 **56.2% 屏高**，右贴 `end_guideline`，`marginBottom 50dp`
- 歌曲信息区：`start` → `middle_start`，与封面同 top
- 底部控制区：高 **21.6%** 屏高（min 48dp），`marginBottom 10dp`，`Flow` 排 5 个按钮（播放模式/上一首/播放/下一首/列表）
- 底部彩色频谱：高 **8%** 屏高

**歌词模式**（`activity_player_style_lyric.xml`，161 行）的 Guideline：

| Guideline | 位置 |
|---|---|
| start | **7.81%** |
| middle_start | **45.31%** |
| middle_end | **49.47%** |
| end | **92.18%** |
| play_list_end | **95.62%** |

- 封面缩到高 **29.6%** 屏高，移到左边（`start` → `middle_start`），下方接歌曲信息
- 歌词区：`middle_end` → `end`，高 **56.2%** → 实际 **42.7% 宽 × 56.2% 高**
- 同屏可展开播放列表：宽 46.15%，高 68.1%

**两者是左右互换的镜像**：默认「左信息 + 右大封面」，切歌词后「左小封面 + 右大歌词」。视觉重心从 55% 移到 49.5%，屏幕既不空也不挤。这个做法比网易云的「黑胶居中 + 歌词另开一页」更省一次跳转，也更适合本地曲库（我们不需要黑胶的仪式感，需要快速看到歌词）。

#### 播放器皮肤

4 种可切换（`layout_player_{album,lyric,colorful,dynamic_lyric}_mode.xml`），其中 `dynamic_lyric` 用 `KineticLyricView` 做逐字动效；入口在设置里（`fragment_settings_player_style` + `layout_player_style_select`）。

#### 歌词引擎

`com.lyricengine.ui.LineFeedAnimationLyricView`：

- 高亮 **12sp bold** / 普通 **10sp**（车载基准，换算到电视偏小，取我们的 21/28sp）
- `lyric_refresh_interval = 50ms` → **逐字着色**（卡拉 OK 式进度）
- 行间距 3dp、句间距 6dp、水平居中、垂直顶部对齐

#### 列表与卡片

- 行高 **50dp**（网易云 56dp），副内容列宽 100dp，行右侧固定 3 个操作图标
- 字号体系：t1 **24dp** / t2 **18sp** / t3 **16dp** / t4 **14dp** / t5 **12dp**
- 文字色：#CCCCCC 主 / #808080 次 / #FFFFFF 强调 / #F04F43 红（K 歌业务）
- 卡片：DSL 两列（`kgtv_item_dsl_card`，weight 各 1，间距 7dp）

#### 登录（`activity_comm_login_layout.xml`，299 行）

- 登录卡片固定宽 **426dp**，背景整图
- 二维码白底 **240×240dp** + 二维码 **220×220dp** + 选中框 **250×250dp**
- 标题 20dp：「请用全民K歌/微信/QQ扫码登录」
- **四个状态遮罩**（`#CD000000` + 20dp 文字）：
  1. 请先阅读并勾选下方协议
  2. 二维码过期，刷新中
  3. 登录失败，请重新扫描二维码
  4. 登录成功（41×51dp 图标 + 16dp 文字）

这四种状态是扫码登录必须画的，缺一个就会让用户停在黑屏上不知所措。

#### 焦点

- `FocusLayout` / `CustomFocusLayout`：默认 **scale = 1.1f**，`AnimUtils` 做缩放过渡（时长 100–500ms，300ms 为主）
- `FocusBorderView`：**焦点框是一条独立的白框 View，在容器里「飞」到目标位置**（`flyWhiteBorder`），而不是每个 item 自绘边框；
- `BounceFocusRootRelativeLayout`：重写 `focusSearch`，到边界时触发 bounce 并回调 listener。

飞行焦点框的取舍见 7.2。

#### 两家共性 = 行业共识

1. **顶部横向 Tab，都没有侧栏**；
2. 播放页「封面 ↔ 歌词」双形态，左右镜像；
3. 歌词区固定占右侧 **40–43% 宽、50–56% 高**；
4. 底部常驻播放条 **60dp**；
5. 焦点放大 **1.05–1.1** + 白色描边（或飞行框）；
6. 深底 + 白色透明度层级；
7. 扫码登录 + 多态遮罩。

#### 差异与我们的选择

| 维度 | 网易云 TV | QQ 音乐 TV | 我们的选择 |
|---|---|---|---|
| 主色 | 红 `#FF3A3A` | 绿 `#31C27C` | **蓝 `#3B82F6`**（与手机端、应用图标一致） |
| 导航 | 居中 Tab，37dp / 18sp | 左对齐 Tab，60dp / 左右 22dp | 居中 Tab，**56dp**（比网易云留更多焦点余量） |
| 主播放页 | 居中黑胶 52% + 单行歌词 | 右封面 56.2% + 左信息 | **QQ 模式**：方形封面适配我们的专辑图，且不需要建模黑胶纹理 |
| 歌词页 | 40% × 50% | 42.7% × 56.2% | **42% × 55%**（取中位） |
| 控制条 | 默认隐藏，按 OK 呼出 | 常显，占 21.6% | **常显但降透明度**（本地播放器要频繁选歌），焦点进入时才提亮 |
| 列表行高 | 56dp | 50dp | **52dp** |
| 焦点缩放 | 1.05 | 1.1 | **1.08** |
| 字体 | 系统 | 自带 3 款 | 系统字体 + 数字等宽（不引 ttf，省 3–5 MB） |
| 播放器皮肤 | 唱片 / 歌词 | 4 种可切 | **2 种**（封面 / 歌词），不做皮肤商店 |

---

## 4. fnAudio TV 现状诊断

对照两家的实测值（左为现状，右为两家收敛后的目标区间）：

| # | 维度 | 现状 | 目标 | 影响 |
|---|---|---|---|---|
| 1 | 导航 | 左侧竖排 10 项，宽 **136dp**（占 960dp 的 14%） | 顶部文字 Tab，56dp 高，不占横向空间 | 内容区被压缩，卡片只能放 3 张 |
| 2 | 字号 | 卡片标题 16sp / 副标题 13sp / 行标题 17sp | 卡片标题 18sp / 行标题 20sp / 歌名 21sp | 3 米外看不清，这是"不好看"的第一来源 |
| 3 | 首页结构 | hero（196dp）+ 最多 3 行固定卡片 | 多 shelf 纵向堆叠，服务端/规则驱动 | 内容承载量只有目标的三分之一 |
| 4 | 播放页 | 封面 196dp + 传输按钮 + 右侧队列 | 右封面 56% + 左信息 + 底部控制区（QQ 模式） | 没有"正在播什么"的画面感 |
| 5 | 歌词 | 全屏滚动列表（我上一轮做的） | 歌词模式：右侧 42%×55% 大字歌词；封面模式保留单行歌词 | 全屏铺满不符合观看距离 |
| 6 | 焦点 | 3dp 白描边 + 1.08 缩放 | 1.08 + 显式焦点搜索 + 到边界回调 | 遥控走位不可预测 |
| 7 | 页面 | 全部塞在 1 个 Activity + 4 个覆盖层 | 独立播放页 + 独立详情页 | 返回栈混乱（上一轮已踩坑） |
| 8 | 「我的」 | 收藏/播放列表/设置平铺在侧栏 | 独立 Tab：头像 + 账号 + 收藏/歌单/历史 + 设置入口 | 信息层级扁平 |
| 9 | 登录 | 原生表单：地址 + 端口 + 用户名 + 密码 | 扫码 / 局域网发现 / 历史档案优先 | 遥控器输入 32 位地址不可接受 |
| 10 | 状态 | 无骨架屏、无空态插画、无错误重试 | loading/空/错误三态（`mr.xml` 模式） | 首屏等待时是纯黑，像卡死 |

结论支持你的判断：**不是"再调一调"能解决的，需要重做**。但下面的方案**保留**已经写好的 API、播放器、图片加载、焦点导航器等资产，不是从零再来一遍。

---

## 5. 新信息架构

### 5.1 一级 Tab（5 个，顶部居中）

| Tab | 内容 | 数据来源 |
|---|---|---|
| **推荐** | 多 shelf：继续播放 / 最近添加 / 我的收藏 / 常听艺术家 / 专辑精选 / 随机 100 | 现有 `api/library`、`api/state/user` |
| **资料库** | 二级 Tab：专辑 / 艺术家 / 曲目 / 文件夹（后续） | `api/library/groups` |
| **我的** | 账号卡 + 收藏 + 播放列表 + 最近播放 + 设置入口 | `api/state/user` |
| **搜索** | 输入 + 历史 + 结果（歌曲/专辑/艺术家三组） | `api/library?search=` |
| **设置** | 服务器 / 播放 / 关于 / 退出 | 本地 |

理由：电视上「找到一首歌」的最短路径是「推荐点一下」或「搜索」，而「专辑/歌手/曲目」是同一件事的三个切面，放二级 Tab 比三个一级 Tab 更省空间（网易云的「歌手」页就是这种两层 Tab，`cv.xml` 实测：两层 TabLayout 各 36dp，间距 10dp）。

设置虽然只有 5 项，但独立成 Tab 比藏在「我的」第五层更容易被找到；如果你更希望减少 Tab 数量，可以把它并进「我的」最后一行（方案里预留开关）。

### 5.2 二级页

- 专辑详情 / 艺术家详情 / 播放列表详情：头图 + 简介 + 曲目列表
- 播放页（独立 Activity）
- 全屏歌词页（从播放页左右切）
- 队列浮层（播放页内按「上」）
- 搜索输入页（从搜索 Tab 进入，走系统输入法）

---

## 6. 页面规格（可直接照做）

> 视口基准：1920×1080 @320dpi = **960×540dp**。所有数值是 dp / sp，与网易云 TV 的 px 稿换算后一致（它 66px 标题 ≈ 33sp）。

### 6.0 全局

| 项 | 值 |
|---|---|
| 屏幕边距 | 左右 **48dp**，内容起于 48dp |
| 顶部安全区 | **80dp**（Tab 占 56dp + 24dp 呼吸） |
| 底部安全区 | **72dp**（播放条 64dp + 8dp） |
| 区块间距 | 32dp（shelf 之间） |
| 卡片间距 | 24dp（横向） |
| 圆角 | 卡片 15dp，封面 12dp，弹层 24dp，Tab 胶囊 18dp |
| 焦点描边 | **3dp 纯白**，圆角跟随元素 |
| 焦点放大 | **1.08 倍**（卡片；两家实测 1.05 / 1.1，取中），列表行不缩放只提亮 |
| 焦点动效 | **140ms** `decelerate`（必须跟手；网易云的 400ms 是转场不是焦点） |
| 页面转场 | **320ms** 淡入 + 轻微上移 8dp |
| 长按加速 | 方向键按下 400ms 后滚动速度 ×3 |

### 6.1 主壳（Shell）

```
┌────────────────────────────────────────────────────────────┐
│                    推荐   资料库   我的   搜索   设置        │  ← Tab 区 56dp
│                                                            │
│  继续播放                                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  │ 封面    │ │        │ │        │ │        │              │  ← shelf 行
│  └────────┘ └────────┘ └────────┘ └────────┘              │
│  最近添加                                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐              │
│  ...                                                       │
├────────────────────────────────────────────────────────────┤
│ ▶ 歌名 - 歌手            ──────●────── 1:12/3:45  ⏭  ⏯   │  ← 播放条 64dp
└────────────────────────────────────────────────────────────┘
```

- Tab 条：高 **56dp**，文字 **18sp**，Tab 之间间距 32dp，选中项下方 3dp 蓝色指示条（跟随文字宽度）；焦点在 Tab 上时整条高亮 + 放大 1.08。
- Tab 条上方 24dp 呼吸，内容区从 y=80dp 开始。
- 右上角：连接状态小圆点 + 服务器名（14sp，`#66FFFFFF`），替代网易云的 VIP 角标位置。
- 播放条：高 **64dp**，左侧 40dp 圆形封面缩略，歌名 16sp / 歌手 14sp，中间进度条，右侧「下一首」「播放/暂停」；未播放时整条隐藏（内容区下移 72dp）。
- 焦点在播放条按「上」→ 回内容区最后一行；内容区按「下」到底 → 进播放条。

### 6.2 推荐页

Shelf 定义（每条 = 标题行 + 卡片行）：

| Shelf | 卡片尺寸 | 内容 |
|---|---|---|
| 最近添加 | 210×210dp（**行首第一张是「继续播放」卡**，封面右下带 37% 进度条 + 「继续播放」角标） | 上次未播完 + 最近 40 首 |
| 我的收藏 | 210×210dp | 收藏曲目（取封面） |
| 常听艺术家 | 168dp 圆形 | 按播放次数聚合的 top 8 |
| 专辑精选 | 210×210dp | 随机 12 张专辑 |
| 随机 100 | 210×210dp | 快捷入口卡（一个"骰子"卡） |

> 「继续播放」**不单独占一行**。原型验证：960×540dp 下，Tab 60dp + 行标题 20dp + 210dp 卡片 = 290dp，一屏只剩 250dp，独立成行会把第二行挤到播放条下面只露 46px。改成行首第一张卡后，第一行完整可见、第二行露出约 79dp（158px@1080p），才是电视书架该有的"1.5 行"节奏。

- Shelf 标题：**20sp**，`#B3FFFFFF`，行高 40dp，与卡片间距 12dp。
- 卡片：封面 186×186dp（圆角 12dp）+ 标题 **18sp** 单行 + 副标题 **14sp** `#99FFFFFF`，整卡 210 宽。
- 卡片焦点：放大 1.06 + 3dp 白边 + 上浮 6dp 阴影；焦点卡标题变纯白。
- 行内横向滚动，边缘 48dp 渐隐（`FadingEdgeLayout` 同款），露出半张卡暗示可滚动。
- 行末尾追加「查看全部」方形卡（虚线边 + `+` 图标），焦点可及。

### 6.3 资料库页

- 二级 Tab（36dp 高，18sp，间距 24dp）：专辑 / 艺术家 / 曲目
- 内容：**4 列网格**，卡 **198×198dp** + 24dp 间距：48 + 4×198 + 3×24 + 48 = 960dp 正好满宽（用 210dp 的 4 列是 1008dp，会溢出 48dp，上一版方案这里算错了）
- 网格为两维焦点：左右在行内，上下跨行（用 `TvShelfNavigator` 的纵向行模型改造为真网格 `TvGridNavigator`）
- 曲目视图为列表：行高 **52dp**（网易云 56 / QQ 音乐 50 的折中），序号 14sp / 封面 44dp / 标题 18sp / 歌手 14sp / 时长 14sp / 格式角标
- 焦点行：底色 `#1AFFFFFF` + 左侧 3dp 蓝条（不用描边，列表里描边太吵）

### 6.4 我的页

```
┌──────────────────────────────────────────────┐
│  ┌────┐  用户名                    [设置]     │
│  │头像│  服务器 · 已连接 · 117 首              │
│  └────┘                                       │
│  收藏 32   播放列表 6   最近播放 50            │  ← 三个统计块
│                                               │
│  我的收藏            → 查看全部               │
│  ┌────┐┌────┐┌────┐┌────┐                    │
│  播放列表                                     │
│  ┌───────┐┌───────┐┌───────┐                 │  ← 288×96dp 横卡
└──────────────────────────────────────────────┘
```

- 头像 72dp 圆形，用户名 22sp bold，副信息 14sp `#99FFFFFF`
- 统计块：数字 24sp bold + 标签 14sp，三块等宽
- 播放列表横卡：288×96dp，圆角 15dp，底色 `#29FFFFFF`，标题 18sp

### 6.5 搜索页

- 顶部搜索框：高 56dp，圆角 28dp，`#1AFFFFFF` 底，占位「搜索歌曲、专辑、艺术家」18sp
- 未输入时：搜索历史（标签胶囊，14sp，高 36dp，间距 12dp）+ 热门（如果有）
- 结果分三组：「歌曲」「专辑」「艺术家」，组标题 20sp，每组最多 8 条 + 「查看全部」

### 6.6 播放页（核心）：封面 / 歌词 双形态

采用 QQ 音乐 TV 的镜像模型（`activity_player.xml` ↔ `activity_player_style_lyric.xml`）：方形封面直接吃我们的专辑图，不需要建模黑胶纹理；网易云的「20s 一圈的唱片旋转」作为可选动效保留，但不做转盘与唱臂。

#### 形态 A：封面模式（默认）

```
┌──────────────────────────────────────────────────────────────┐
│ ←                                                            │ 顶 7.3%
│                                                              │
│   歌名 21sp                     ╭──────────────────╮         │
│   歌手 · 专辑 16sp              │                  │         │ 封面高
│                                 │   方形封面        │         │ 56.2%
│   街角的风 从窗缝里经过 18sp     │   304×304dp      │         │ (304dp)
│                                 │                  │         │
│                                 ╰──────────────────╯         │
│                                                              │
│  ──────●───────────── 1:12 / 3:45   ♪ ⇄ ⏮ ⏯ ⏭ ☰          │ 底 21.6%
└──────────────────────────────────────────────────────────────┘
   ← 7.3%                                    55%          92.7% →
```

| 元素 | 值（960×540dp） |
|---|---|
| 左边距 | 屏宽 **7.3%**（70dp） |
| 左右分界 | **55%** |
| 大封面 | 高 **56.2%**（304dp），1:1，右贴 92.7%（距右 70dp），底部留 50dp |
| 歌名 | **21sp** 中黑，单行跑马灯（超 500dp 才滚） |
| 歌手·专辑 | 16sp，`#99FFFFFF` |
| 单行歌词 | **18sp**，maxWidth 640dp，切句 260ms 淡入 + 1.06→1.0 |
| 背景 | 封面放大 1.2 + 24px 模糊，叠 `#080812` 88% 遮罩 |
| 唱片动效 | 可选：封面以 20s/圈缓慢旋转（关闭后为静态方图），默认开启 |

#### 形态 B：歌词模式（按「歌词」按钮进入）

```
┌──────────────────────────────────────────────────────────────┐
│ ←                                                            │ 顶 7.8%
│  ┌──────────┐      街角的风 从窗缝里经过                      │
│  │ 小封面    │      像一段旧旋律 迟迟不肯停                    │ 宽 42.7%
│  │160×160dp │      你说过的话 我还记得                       │ × 高 56.2%
│  └──────────┘      隔着这么多年 依旧温热                      │
│  歌名 21sp          ————————                                  │
│  歌手 16sp                                                    │
│                                                              │
│  ──────●───────────── 1:12 / 3:45   ♪ ⇄ ⏮ ⏯ ⏭ ☰          │ 底 21.6%
└──────────────────────────────────────────────────────────────┘
   ← 7.8%      45.3%   49.5%                        92.2% →
```

| 元素 | 值 |
|---|---|
| 左边距 / 封面区右界 | **7.8%** / **45.3%** |
| 小封面 | 高 **29.6%**（160dp），1:1，靠左 |
| 歌曲信息 | 封面下方，`marginTop 14dp`，歌名 21sp / 歌手 16sp |
| 歌词区 | **49.5% → 92.2%**（宽 42.7%）、高 **56.2%**，垂直居中 |
| 歌词字号 | 正文 **21sp** / 当前行 **28sp** bold，行距 12dp |
| 无歌词 | 歌词区居中提示 18sp `#66FFFFFF`（三种文案见 6.7） |
| 播放列表 | 同屏右侧可展开（宽 46%、高 68%），默认收起 |

#### 形态切换与按键

| 按键 | 封面模式 | 歌词模式 |
|---|---|---|
| 左 / 右 | **上一首 / 下一首** | 上一句 / 下一句（微调歌词位置） |
| 上 | 队列浮层 | 队列浮层 |
| 下 | 进入控制条 | 进入控制条 |
| OK | 播放 / 暂停（控制条聚焦时执行按钮） | 同 |
| 返回 | 退出播放页 | **退回封面模式** |
| 「歌词」按钮 | 切到歌词模式 | 切回封面模式 |

「歌词」按钮放在底部控制条最右（`☰` 之前），遥控左右键可达。控制条**常显但整体 alpha 0.55**，焦点进入时提到 1.0。

> 网易云选择「默认隐藏控制条」，因为它的内容是流媒体推荐，用户多数时间只听不看。我们的场景是本地曲库，选歌、切歌、看歌词的频率高得多，所以取 QQ 音乐的做法（常显），用透明度区分主次。

### 6.7 歌词页

不再单独开 Activity，作为播放页的形态 B 存在。与两家对照：

| 指标 | 网易云 `mu.xml` | QQ 音乐 `style_lyric` | 我们 |
|---|---|---|---|
| 歌词区宽度 | 40% | 42.7% | **42%** |
| 歌词区高度 | 50% | 56.2% | **55%** |
| 正文 / 当前行 | 21sp / 28sp | 21sp / 28sp | **21sp / 28sp** |
| 位置 | 偏右（bias 0.638） | `49.5% → 92.2%` | 右区 |
| 同屏元素 | 歌名 21sp + 副标题 18sp | 左小封面 + 歌曲信息 | 同 QQ 音乐 |

三种状态文案（照抄 QQ 音乐登录四态的思路，歌词也必须给状态）：

1. 匹配中：「正在匹配歌词…」（18sp `#66FFFFFF`）
2. 无结果：「这首歌没有歌词」+ 小字「按返回键回到封面模式」
3. 失败：「歌词加载失败」+ 具体原因（元数据服务未就绪 / 网络）

关键在字阶与留白，不在新奇效果。上一轮做的「全屏居中滚动列表」弃用。

### 6.8 队列浮层

- 右侧滑入，宽 40%（384dp），高 100%，背景 `#F214161A`
- 标题「接下来播放」20sp，列表行 56dp
- 当前曲目左侧 3dp 蓝条 + 播放图标
- 焦点进入时行内可「OK 切换 / 长按菜单（下一首播放、移除）」

### 6.9 登录页

三选一的落地方式见第 10 节，UI 规格：

```
┌────────────────────────────────────────────────────────────┐
│                                                            │
│   连接你的 fnAudio 服务器                                    │  ← 34sp bold
│   在手机上打开 fnAudio，或在下方填写地址                     │  ← 18sp
│                                                            │
│   ┌──────────────────────┐   ┌──────────────┐              │
│   │  历史服务器列表        │   │   二维码      │              │
│   │  ○ 客厅 NAS  .141     │   │  （225×225）  │              │
│   │  ○ 书房 NAS  .20      │   │              │              │
│   │  + 添加新服务器        │   │ 手机扫码配对  │              │
│   └──────────────────────┘   └──────────────┘              │
│                                                            │
│   手动输入地址 ›                                            │
└────────────────────────────────────────────────────────────┘
```

- 标题 34sp bold，副标题 18sp `#99FFFFFF`
- 历史服务器卡片：420×96dp，圆角 15dp，底色 `#29FFFFFF`，行内 20sp 服务器名 + 14sp 地址
- 二维码卡片：**280×330dp，圆角 25dp**（照抄网易云与 QQ 音乐的实测值），内含白底 **240×240dp** + 二维码 **220×220dp** + 选中框 **250×250dp**
- 二维码下方：20sp「用手机 fnAudio 扫码」，再下行 14sp `#66FFFFFF` 显示 `192.168.5.141 : 42001`
- 二维码四态（照抄 QQ 音乐登录页的遮罩做法，`#CD000000` + 20sp 文字）：
  1. 待扫码：正常显示
  2. **已过期**：遮罩「二维码已过期」+「按 OK 刷新」
  3. **发送中**：遮罩「正在连接 客厅 NAS…」+ 40dp 转圈
  4. **失败**：遮罩「连不上该服务器」+ 具体原因
- 「手动输入地址」保留完整表单（复用手机端能力），作为兜底入口
- 按「菜单键」在「扫码」与「配对码」两种模式间切换（见 10.4.6）

---

## 7. 导航与焦点模型

### 7.1 按键映射

| 按键 | 推荐/资料库 | 播放页 | 歌词页 | 播放条 |
|---|---|---|---|---|
| 上 | 上一行 / 到 Tab 条 | 呼出队列 | 回到播放页 | 回内容区 |
| 下 | 下一行 / 到播放条 | 收起控制条 | — | — |
| 左 | 行内左移 | **上一首** | 上一句（微调） | seek −10s |
| 右 | 行内右移 | **下一首** | 下一句 | seek +10s |
| OK | 打开 | 呼出/收起控制条 | 切回唱片形态 | 打开播放页 |
| 返回 | 到 Tab 条 → 首页 → 退出确认 | 收起控制条 → 退出播放页 | 回播放页 | — |
| 菜单(长按 OK) | 加入队列/收藏 | 音质/模式 | — | — |
| 快进/快退键 | — | seek ±10s | seek ±10s | — |

### 7.2 焦点规则

1. **焦点永不丢失**：任何页面切换后焦点落到「上次同类型元素」，找不到就落到第一个可聚焦项。
2. **焦点回 Tab**：内容区按「上」越过第一行上边界 → Tab 条中当前 Tab 获得焦点（`searchFocusUp` 显式指定，不依赖几何搜索）。
3. **Tab 联动**：焦点在 Tab 条时左右切换 Tab 只高亮不换页，按 OK 才切换（避免误触刷新内容）；在内容区左右到底再按 → 切到相邻 Tab（可选，默认关闭）。
4. **隐藏元素不可聚焦**：播放条隐藏、弹层关闭时从焦点链中移除。
5. **大位移不跳格**：网格用行列模型（`TvGridNavigator`），不靠 `FocusFinder` 猜。
6. **到边界要有反馈**：内容区继续按方向键时，画面轻微回弹（4dp，120ms）而不是完全没反应——QQ 音乐用 `BounceFocusRootRelativeLayout` 重写 `focusSearch` 到边界时触发 bounce，这是我们缺的一环。

**关于「飞行焦点框」**：QQ 音乐用一条独立的白色描边 View 在容器里飞到目标位置（`FocusBorderView`），比每个 item 自绘边框更有连续感。代价是它要求焦点框能溢出父容器（`clipChildren=false`）、且要在滚动/翻页时同步位移，实现与调试成本约为自绘方案的 3 倍。

**本期采用「每项自绘描边 + 缩放」（现方案）**，理由是：我们的网格最多 4 列 × 3 行、单屏元素少，自绘已经够用；飞行框等到第 4 期打磨时再评估。这一条列进待拍板（第 14 节）。

---

## 8. 视觉规范（Design Token）

```java
// TvTheme.java —— 全部数值来自实测换算
static final int BG           = 0xFF080812;  // 页面底
static final int BG_ELEVATED  = 0xFF12141C;  // 卡片/浮层底
static final int CARD         = 0x29FFFFFF;  // 16% 白
static final int CARD_FOCUS   = 0x3DFFFFFF;  // 24% 白
static final int TEXT         = 0xFFFFFFFF;
static final int TEXT_2       = 0xB3FFFFFF;  // 70%
static final int TEXT_3       = 0x99FFFFFF;  // 60%
static final int TEXT_4       = 0x66FFFFFF;  // 40%
static final int DIVIDER      = 0x1AFFFFFF;  // 10%
static final int ACCENT       = 0xFF3B82F6;  // fnAudio 蓝（品牌一致，不跟网易云红）
static final int ACCENT_SOFT  = 0x333B82F6;
static final int DANGER       = 0xFFFF5A5A;

// 字阶（两家实测的并集，QQ 音乐的 t1–t5 = 24/18/16/14/12 与我们基本重合）
TAB 18 / SHELF 20 / CARD_TITLE 18 / CARD_SUB 14
LIST_TITLE 18 / LIST_SUB 14 / LIST_META 12
PLAYER_TITLE 21 / PLAYER_SUB 16 / LYRIC_LINE 18
LYRIC_FULL 21 / LYRIC_ACTIVE 28
HERO 34 (登录/空态大标题)
// 尺寸
TAB_BAR 56 / PLAYER_BAR 64 / LIST_ROW 52 / CARD 210 / COVER 186

// 间距
SCREEN_EDGE 48 / BLOCK_GAP 32 / CARD_GAP 24 / INNER 16 / TIGHT 8 / HAIR 4
// 圆角
R_CARD 15 / R_COVER 12 / R_SHEET 24 / R_PILL 18
// 动效
FOCUS 140 / TRANSITION 320 / LYRIC 220 / DISC_ROTATE 20000(一圈，可关)
```

字体：系统 `sans-serif`（中文走思源黑体），数字用 `sans-serif-medium`；**不使用自定义字体文件**。QQ 音乐为了质感打包了 3 款 ttf（DIN-Alternate-Bold 数字、VisbyCF-Bold 英文、方正兰亭中），代价是 3–5 MB 与首屏字体加载；我们只有 117 首曲库、数字量小，用系统字体 + 等宽数字即可，把体积留给封面缓存。

---

## 9. 与现状的取舍：保留 / 重写 / 删除

| 现有资产 | 处置 |
|---|---|
| `TvApi`（536 行，含搜索/收藏/歌单/分类/歌词） | **保留**，补 `mainShelves` 聚合 |
| `TvPlayer`（280 行，ExoPlayer 队列语义） | **保留**，补 `seek` 精度与播放位置持久化 |
| `TvArtworkLoader`（133 行） | **保留**，加内存 LRU 上限 |
| `TvShelfNavigator`（136 行） | **保留**，新增 `TvGridNavigator`（二维） |
| `TvCardView` / `TvShelfView` | **重写**（尺寸/字号/焦点态全部变更） |
| `TvLyricsView`（370 行，歌词页） | **重写**为播放页的歌词形态（右区 42%×55%），去掉全屏铺满 |
| `TvNowPlayingOverlay`（408 行） | **删除**，改为 `PlayerActivity` + 封面/歌词双形态 |
| `TvMainActivity`（1449 行，侧栏+hero+分页） | **删除**，改为 `ShellActivity`（Tab + ViewPager） |
| `TvUi`（107 行） | **替换**为 `TvTheme`（token 化） |
| `TvLoginActivity`（378 行，表单） | **重写**，复用 `AuthFlow`（见第 10 节） |

---

## 10. 登录：怎么"复用手机安卓 APP 的功能"

### 10.1 现状拆解

手机端 `ui/LoginActivity.java`（631 行）里真正有价值的是**非 UI 部分**：

| 能力 | 所在类 | 是否可共享 |
|---|---|---|
| 地址解析（含端口/协议/路径） | `LoginActivity.AddressParts`（私有） | 需抽出 |
| 账号密码认证 | `network/FnOsAuthClient` | ✅ 已在 main 源集 |
| FN Connect 远程解析 | `network/FnConnectResolver` + `TppsTunnel` | ✅ |
| 连接档案持久化（加密） | `data/SecureProfileStore` | ✅ |
| 档案自动恢复 | `LoginActivity.resumeProfile()` | 需抽出 |
| 错误分类（密码错/证书/网络/需要内网） | `authenticate()` 里的大段分支 | **需抽出（最有价值）** |

TV 端现在自己写了一遍表单与认证（`TvLoginActivity` 378 行），和手机端逻辑重复且不同步——这才是"登录要复用手机功能"的真实含义。

### 10.2 方案：抽 `AuthFlow`，两端共用

```
com.fnaudio.client.login/          （新增，main 源集，手机与 TV 共用）
  AuthFlow.java        // 有状态机：resolve → authenticate → persist → resume
  AuthResult.java      // sealed：Success(profile) / BadPassword(msg) / Unreachable(msg)
                       //         / CertUntrusted(msg) / NeedIntranet(msg) / Cancelled
  AddressSpec.java     // 从 LoginActivity.AddressParts 抽出（解析 192.168.5.141:5666）
  AuthFlowListener.java
```

- 手机端 `LoginActivity` 改为调用 `AuthFlow`，删除内部认证逻辑（约 260 行）；
- TV 端 `TvLoginActivity` 同样只调 `AuthFlow`，UI 换成电视样式（大字号、遥控焦点、历史档案卡片）；
- 两端共享同一套错误文案与重试策略，**改一次两端生效**。

### 10.3 遥控输入问题的三层解法

| 层 | 做法 | 工作量 | 建议 |
|---|---|---|---|
| L1 默认 | 历史档案卡片（一次输入，之后开机直达）+ 大字号表单 + 系统输入法 | 小 | **本期必做** |
| L2 推荐 | 局域网自动发现：TV 在启动扫描器并发探测 192.168.x.0/24 的 fnOS 特征端口（`api/health`），列出「发现 2 台服务器」直接选中 | 中 | 第二期做 |
| L3 最佳 | **扫码配对**：TV 显示二维码 → 手机 fnAudio 扫码 → 局域网直推连接档案 → TV 免输入登录 | 中大 | **第 4 期做，详见 10.4** |

L1 + L3 是互补的：L1 解决「已有档案的复访」，L3 解决「第一次在新电视上登录」。L2 的价值被 L3 吃掉大半（扫码时手机上的档案已经带地址），所以 L2 降级为可选。

> 注意：L2/L3 都依赖「TV 与 NAS 同网段」。如果用户靠 FN Connect 远程使用，L2 无效，仍需 L1 表单或 L3 推送。方案默认按「绝大多数是家庭局域网」做，FN Connect 保留在表单里。

---

### 10.4 扫码配对登录（本期新增）

#### 10.4.1 目标与边界

**做什么**：电视登录页显示二维码 → 手机 fnAudio 扫一下 → 手机上选一个已保存的连接档案并确认 → 电视自动填好服务器地址、端口、证书指纹和登录态，直接进首页。遥控器一次都不用打字。

**不做什么**：不做「电视反控手机」，不做多设备批量推送，不传用户密码。

#### 10.4.2 传什么：白名单字段

`ConnectionProfile.toJson()` 会把 `password` 一起序列化，**不能直接拿来传**。配对只传下面这组（新增 `PairingTransfer.toJson()`）：

| 字段 | 传 | 原因 |
|---|---|---|
| `name` / `host` / `port` / `https` | ✅ | 电视连服务器必需 |
| `trustSelfSigned` / `certificatePinSha256` | ✅ | 否则电视会被自签证书卡住（我们大量用户是内网自签） |
| `username` | ✅ | 显示用，也用于 token 失效时的提示 |
| **`longToken`** | ✅ | 长期票据，电视用 `user.tokenLogin` 换短 token |
| `webSession` / `fnConnectRelay` / `fnConnectMode` / `accessCode` | ✅ | 影响走直连还是 FN Connect 隧道 |
| **`password`** | ❌ | 密码永不出手机 |
| `token`（短票） | ❌ | 短票换不了新票，传了也没用，反而扩大暴露面 |
| `id` / `updatedAt` | ❌ | 电视本地重新生成 |

> 依据：`FnOsAuthClient` 已支持三条恢复路径——短票（`AUTH_TOKEN`）、`user.tokenLogin`（长票换新票）、密码。传 `longToken` 就够电视长期维持登录，密码完全不参与。

#### 10.4.3 通道：局域网直推，不动服务端

```
 电视 (TvLoginActivity)                      手机 (fnAudio)
 │                                               │
 │ 1. 起临时 HTTP 服务 0.0.0.0:42001              │
 │ 2. 生成 6 位码 482913（60s 有效）               │
 │ 3. 渲染二维码                                   │
 │    fnaudio://pair?v=1&h=192.168.5.141          │
 │                   &p=42001&c=482913            │
 │ ───────── 屏幕上显示 ─────────────────────────▶ │ 4. 扫码解析
 │                                               │ 5. 选档案 + 确认
 │ ◀──── POST http://192.168.5.141:42001/pair ──── │
 │ 6. 校验码/来源/时效                             │
 │ 7. 用 longToken 试连 /api/health + 鉴权         │
 │ 8. 成功 → 保存档案 + 关服务 + 进首页            │
 │                                               │
```

**为什么不做服务端中转**（这是最容易想到的方案，但有死结）：电视必须先知道服务器地址才能去服务器轮询配对码，而「不知道服务器地址」正是要解决的问题本身。所以中转方案只能解决「免密」不能解决「免输地址」，还要改 fnOS 应用加接口。局域网直推零后端改动，且一次性把地址+凭据都送到位。

**代价**：要求手机与电视在同一局域网。不同网段（路由器开了 AP 隔离、访客网络）时回退到表单或 6 位码模式（10.4.6）。

#### 10.4.4 接口与状态码

只有一个端点：

```
POST /pair          Content-Type: application/json      body ≤ 8 KB
{
  "v": 1,
  "code": "482913",
  "profile": {
    "name": "客厅 NAS", "host": "192.168.5.141", "port": 5666,
    "https": false, "trustSelfSigned": true, "certificatePinSha256": "",
    "username": "admin", "longToken": "...", "webSession": false,
    "fnConnectRelay": false, "fnConnectMode": "", "accessCode": ""
  }
}

200 {"ok": true,  "tv": "fnAudio TV", "app": "0.2.146"}           // 已保存
401 {"ok": false, "error": "code_mismatch"}                       // 码不对
410 {"ok": false, "error": "code_expired"}                        // 过期（>60s）
403 {"ok": false, "error": "not_lan"}                             // 非私网来源
413 {"ok": false, "error": "too_large"}                           // body 超限
502 {"ok": false, "error": "unreachable", "detail": "连接超时"}    // 电视连不上该服务器
```

电视侧行为：收到 200 后**立即关闭服务**；收到 401 累计 3 次也关闭（防猜码）；60s 内没有任何请求同样关闭并在屏幕上把二维码置灰，点击「刷新」重新生成。

#### 10.4.5 安全设计

| 措施 | 做法 |
|---|---|
| 二维码不含凭据 | 内容只有 TV 的 IP、端口、一次性码 |
| 一次性 | 码用过即失效，服务随即关闭 |
| 时效 | 60s 过期，屏幕置灰提示「二维码已过期，按 OK 刷新」 |
| 来源限制 | 只接受 `isSiteLocalAddress()` / `isLinkLocalAddress()` / `isLoopbackAddress()`，公网直接 403 |
| 防猜码 | 6 位数字（10⁶），60s 窗口内最多 3 次尝试 |
| 人工确认 | 手机上必须点「发送到电视」，不做扫码即发 |
| 报文加密（可选） | 用 6 位码经 PBKDF2 派生 AES-128-GCM 密钥，payload 加密后再传。约 40 行，默认开启；关掉也不影响功能 |

不做的：TLS（临时自签证书在电视上没有意义，用户还得点信任）。

#### 10.4.6 兜底：6 位码模式

当相机不可用、权限被拒、或两台设备不同网段时，登录页可切到「配对码模式」：

```
┌────────────────────────────────────────┐
│  在手机的 fnAudio 里打开「发送到电视」   │
│                                        │
│  电视地址   192.168.5.141 : 42001       │  ← 36sp 等宽
│  配对码     4 8 2 9 1 3                 │  ← 60sp 等宽，字间距 12dp
│                                        │
│  二维码 60 秒后过期，按 OK 刷新          │
└────────────────────────────────────────┘
```

手机端对应页面：两个输入框（地址可省略——如果手机档案里已有该 IP 可自动匹配）+「发送」。这条路径复用同一套 `POST /pair`，服务端代码零改动。

#### 10.4.7 二维码怎么画：三条实现路径

这是本功能唯一需要新增依赖的地方，必须选型：

| 路径 | 代码量 | 依赖 | 风险 |
|---|---|---|---|
| **A. 手写 QR 编码器**（固定 version 5、EC M、byte mode、固定掩码） | ~300 行 | 零 | RS 纠错/掩码写错就是「图能画、扫不出来」，排查成本高 |
| **B. WebView + 自带 JS 实现** | ~300 行 JS + 30 行 Java | 零（系统 WebView） | 同上，还多一层 WebView 生命周期；电视上 WebView 内存 20 MB+ |
| **C. 引入 `com.google.zxing:core:3.5.3`** | ~20 行 | 1 个 jar，约 560 KB | 需**一次联网** gradle 同步把它缓存进 `tools/gradle-home-jdk17`，之后 `--offline` 可构建 |

**推荐 C**。理由：

1. QR 编码是容错性极差的算法，自写后唯一的验证手段是「拿手机扫」——一旦扫不出来，是掩码错、纠错错还是静区不够，很难定位；
2. zxing 自带 `QRCodeWriter` 与 `MultiFormatReader`，**可以在 JVM 单元测试里写完再读回来自校验**，不依赖外部工具；
3. 560 KB 对当前 12.9 MB 的 TV 包是 4%，可接受。

如果不同意新增依赖，则退到 B（WebView + JS），功能不变；A 不推荐。

#### 10.4.8 手机端扫码

需要新增：

- 依赖 `com.journeyapps:zxing-android-embedded:4.3.0`（约 200 KB，自带扫描界面；同样需要一次联网同步）；
- 权限 `android.permission.CAMERA`（运行时申请，拒绝后引导去设置）；
- `ui/ScanPairingActivity.java`：`ScanContract` 拉起扫描，拿到 `fnaudio://pair?...` 解析；
- `ui/PairingConfirmActivity.java`：显示「发送到 fnAudio TV（192.168.5.141）」+ 本机档案单选列表 + 「发送」按钮；
- 发送用现有 OkHttp client，5s 超时。

**注意**：手机端这一步会动 `android-client` 的 Manifest 与依赖，属于跨端改动，需要单独一轮回归（现有 107 条 e2e 与手机端 UI 不受影响，但权限弹窗路径要测）。

#### 10.4.9 失败矩阵

| 场景 | 电视侧 | 手机侧 |
|---|---|---|
| 扫不出二维码 | 二维码 220dp、静区 8dp、白底，屏上还有 6 位码备用 | 提示「对准二维码，保持 15cm 距离」 |
| 相机权限被拒 | — | 引导去设置；同时提示可用 6 位码 |
| 不同网段 | 收不到请求，60s 后置灰 | 发送超时，提示「电视与手机不在同一网络」 |
| 电视 IP 变了 | 二维码每次打开时实时取 IP，不会过期 | — |
| 端口被占 | 42001 起试 10 个端口，都失败则只显示 6 位码模式 | — |
| 电视连不上该服务器 | 502 + detail，屏幕上显示「连不上 192.168.5.141」 | Toast 显示同一原因 |
| 长票已失效 | 试连返回鉴权失败，提示「手机上的登录已过期，请重新登录后再发送」 | 引导重登 |

#### 10.4.10 工程量

| 部分 | 文件 | 行数 |
|---|---|---|
| TV 配对服务 | `login/TvPairingServer.java` | ~180 |
| TV 协议编解码 | `login/PairingTransfer.java` + `PairingPayload.java` | ~150 |
| TV 二维码 | `login/TvQrCodeView.java` | ~50 |
| TV 登录页改造 | `login/TvLoginActivity.java` | +120 |
| 手机扫码 | `ui/ScanPairingActivity.java` | ~120 |
| 手机确认页 | `ui/PairingConfirmActivity.java` | ~150 |
| 测试 | `TvPairingServerTest`（回环）+ `PairingPayloadTest` + 二维码自校验 | ~220 |
| **合计** | | **~990 行** |

---

## 11. 技术架构

```
android-client/app/src/main/java/com/fnaudio/client/
├── login/                       ← 新增，手机+TV 共用
│   ├── AuthFlow.java
│   ├── AddressSpec.java
│   └── AuthResult.java
├── ui/                          ← 手机端（仅改 LoginActivity 调用点）
└── tv/                          ← 重写后
    ├── ui/
    │   ├── TvTheme.java              token
    │   ├── TvFocusCard.java          通用焦点卡（放大/描边/阴影）
    │   ├── TvFocusRow.java           横向焦点行（RecyclerView + 边缘渐隐）
    │   ├── TvGridNavigator.java      二维网格导航
    │   ├── TvTabBar.java             顶部 18sp Tab
    │   ├── TvPlayerBar.java          64dp 播放条
    │   ├── TvEmptyState.java
    │   └── TvSkeleton.java           骨架屏
    ├── shell/
    │   └── ShellActivity.java        Tab + ViewPager + 播放条
    ├── home/
    │   ├── HomeFragment.java
    │   └── HomeShelfBuilder.java     规则拼装 shelf（本地算，不依赖服务端）
    ├── library/
    │   ├── LibraryFragment.java      二级 Tab
    │   ├── AlbumGridFragment.java
    │   ├── ArtistGridFragment.java
    │   └── TrackListFragment.java
    ├── detail/
    │   ├── AlbumDetailActivity.java
    │   ├── ArtistDetailActivity.java
    │   └── PlaylistDetailActivity.java
    ├── mine/
    │   └── MineFragment.java
    ├── search/
    │   ├── SearchFragment.java
    │   └── SearchInputActivity.java
    ├── settings/
    │   └── SettingsFragment.java
    ├── player/
    │   ├── PlayerActivity.java       宿主：双形态切换 + 返回栈
    │   ├── PlayerCoverMode.java      形态 A：左信息 + 右封面 56.2%
    │   ├── PlayerLyricMode.java      形态 B：左小封面 + 右歌词（42.7%×56.2%）
    │   ├── PlayerSingleLineLyric.java  封面模式的单行歌词（260ms 切句）
    │   ├── LyricScrollView.java      歌词模式的多行滚动（21/28sp）
    │   ├── PlayerControlBar.java     底部控制条（常显，alpha 0.55→1.0）
    │   └── QueueSheet.java           队列浮层
    ├── login/
    │   ├── TvLoginActivity.java      复用 AuthFlow + 扫码区
    │   ├── TvPairingServer.java      临时 HTTP 服务（ServerSocket，~180 行）
    │   ├── PairingTransfer.java      白名单序列化（不含 password）
    │   ├── PairingPayload.java       二维码内容编解码 + 校验
    │   └── TvQrCodeView.java         zxing 生成二维码 Bitmap
    ├── data/  ← 现有 TvApi / TvPlayer / TvArtworkLoader / ConnectionProfile
    └── compat/ ← TvShelfNavigator 等现有导航器
```

### 数据侧需要补的两个接口

1. **首页 shelf 聚合**：`HomeShelfBuilder` 在本地用现有接口组装（继续播放取本地、最近添加 `?view=recent`、收藏取 `api/state/user`、常听艺术家按播放计数），**不新增服务端接口**——这是与网易云最大的区别（它服务端下发，我们本地算），好处是零后端改动，代价是首页规则写死在客户端。
2. **最近播放持久化**：TV 本地存最近 50 条（`SharedPreferences` JSON），用于「继续播放」与「最近播放」页。

---

## 12. 实施计划（四期）

### 第 1 期：骨架与首页（可视验收）

- `TvTheme` / `TvFocusCard` / `TvFocusRow` / `TvTabBar` / `TvPlayerBar` / `TvSkeleton`
- `ShellActivity`（Tab + ViewPager + 播放条），删 `TvMainActivity` 侧栏与 hero
- `HomeFragment` + `HomeShelfBuilder`（4 条 shelf：继续播放、最近添加、我的收藏、常听艺术家）
- 焦点模型：内容区↑回 Tab，↓进播放条
- 产出：能与现在并排对比的首页

### 第 2 期：播放页双形态（已完成）

- `TvPlayerScreen`（主壳内的覆盖层，替代 `PlayerActivity`，见 §12.1）
- 形态 A：封面模式（左信息 + 右方形封面 56.2%）
- 形态 B：歌词模式（左小封面 29.6% + 右歌词区 42.7%×56.2%）
- `TvLyricLine`（封面模式的单行歌词，260ms 切句）
- `TvLyricColumn`（歌词模式的多行滚动，21/28sp）
- `TvLyricSource`（加载 / 轮询 / 三态文案，无视图的控制器）
- `TvSeekStrip`（可聚焦进度条，左右键 ±10s）
- `TvQueueSheet`（右侧 46%×68% 队列浮层）
- 形态切换（「歌词」按钮 / 返回键）
- 删旧前端 8 枚类，清单里 TV 入口收敛到 2 个 Activity

**§12.1 第 2 期的实施偏离（记录，不是待办）**

| 方案写的 | 实际做的 | 原因 |
|---|---|---|
| 独立 `PlayerActivity` | 主壳内覆盖层 `TvPlayerScreen` | 播放器实例只有一个；跨 Activity 共享它要么做进程级单例、要么把 `TvPlayer` 搬进 Service，两者都比覆盖层重。覆盖层里返回栈只有一级，用 `handleKey` 显式管理反而更清楚 |
| 左上「返回」+ 底部控制条都隐藏 | 控制条常显（`#12141C`）、返回常显 | 本地曲库的观看频率与操作频率都高，隐藏式控制条在遥控上每次都要先按一下 |
| 左右键 = 上一首 / 下一首 | 左右键在按钮间移焦点；seek 只在进度条聚焦时生效 | 旧播放页把左右键绑给 seek，导致控制条第六个按钮遥控不可达。这条是本轮唯一修掉的硬伤，见 §7.2 第 6 条 |
| 控制条高 21.6% 屏高 | 固定 117dp | 比例值要在 `onSizeChanged` 回写，会多拖一轮布局，首帧 `requestFocus` 时按钮高度还是 0（实测 `focus=false`） |
| 封面 20s 转一圈 | 未做 | 见第 14 节待拍板第 3 条，本期先不做旋转 |

### 第 3 期：资料库 / 我的 / 搜索 / 详情（已完成）

- `TvLibraryPage`（二级 Tab + 歌曲列表 / 专辑网格 / 艺术家网格）
- `TvMinePage`（收藏 / 播放列表）
- `TvSearchPage`（文本域 + 结果列表）
- `TvDetailPage`（专辑 / 艺术家 / 播放列表三合一）
- 通用件：`TvTrackList`（52dp 行）、`TvCardGrid`（198dp 四列 + 显式焦点图）、`TvChipTabs`（40dp 二级 Tab）
- `TvGridNavigator` 不做：网格是静态的，行主序 `nextFocus*` 已经足够确定
- 设置页留到第 4 期

**§12.2 第 3 期的实施偏离**

| 方案写的 | 实际做的 | 原因 |
|---|---|---|
| 三个详情页各写一个 | 一个 `TvDetailPage`，按卡片 id 前缀（`album:` / `artist:` / `playlist:`）决定取数 | 三页的差别只在「怎么拿到 track 列表」，头部、播放全部、返回、空态完全一样 |
| `SearchFragment` + `SearchInputActivity` 两级 | 一个 `TvSearchPage`：输入框 + 结果同屏 | 电视上没有「键盘页」这一层，弹出输入法本身就要占满半屏；分两级反而多一次返回 |
| 自带字母键盘 | 交给系统输入法 | 后端搜索是字面 `LIKE`，没有拼音索引，自造 A–Z 键盘只能打拉丁字符，对中文曲库等于不可用 |
| `TvGridNavigator` | 行主序 `nextFocus*` | 网格 4 列固定、卡片等宽，几何搜索会挑对角线邻居；显式 id 更便宜也更确定 |
| Fragment | 普通 View，主壳按 Tab 缓存 | 同第 1 期：没有分页、没有嵌套导航、没有进程死亡恢复 |

### 第 4 期：登录复用 + 扫码配对 + 打磨（电视端已完成，手机端待定）

- `TvLoginActivity` 重写：左侧扫码卡（280×330，二维码 220dp + 六位码）× 右侧连接列表与手动表单
- `TvPairingServer`：临时 HTTP 服务，一次性六位码、60 秒、私网来源、三次错码即关
- `TvPairingCard`：二维码渲染 + 四态遮罩（待扫 / 过期 / 正在连接 / 失败）
- `PairingPayload` + `PairingTransfer`：`fnaudio://pair?...` 编解码；传输白名单，**不含密码**
- `TvQrCode`：自写二维码编码器（版本 1–6、纠错 M、字节模式），与参考实现逐模块一致

**手机端（已完成）**：`PairingSendActivity`（扫码 / 手填地址与六位码、选档案、发送）+ `PairingClient`。
按你的决定引入 `com.journeyapps:zxing-android-embedded:4.3.0`（连带 `com.google.zxing:core:3.4.1`）
与 `CAMERA` 权限，**两者只落在手机 APK**；电视端仍然只用自写编码器画码，APK 不增加体积。
入口在「历史连接」页头部的「发到电视」。扫不了时同一页可手填地址与六位码，走同一个接口。

**本期无法在这台机器上跑手机 UI**：手机 APK 只带 arm 原生库，x86 模拟器报
`INSTALL_FAILED_NO_MATCHING_ABIS`，所以手机端是「构建 + 合并清单」验证（`CAMERA` 权限、
zxing 的 `CaptureActivity`、`PairingSendActivity` 都在合并后的清单里），协议则用与
`PairingClient` 完全同构的报文在宿主上 POST 到电视验证（200）。

**§12.3 第 4 期的实施偏离**

| 方案写的 | 实际做的 | 原因 |
|---|---|---|
| 引入 `com.google.zxing:core`（560 KB） | 自写 `TvQrCode`（~420 行，零依赖） | 电视端是 `--offline` 构建，加依赖等于每次换机器都要联网同步一次。自写的风险（「画得出但扫不动」）用两道验证抵掉：与 Python `qrcode` 参考实现在 8 种掩码 × 5 种长度上**逐模块 0 差异**；再把模拟器截图里的二维码反解回来，同样 **0/1089 失配** |
| 电视连不上服务器时回 502 | 先回 200「已收到」，连接结果由电视自己显示 | 认证是回调式的，在请求线程里等它要加超时与锁；手机上看到 200 后就能收起键盘，电视上的遮罩会说明结果 |
| 报文 AES-GCM 加密 | 未做 | 局域网 + 一次性码 + 60 秒窗口已经够用；加密留给以后，接口留了 `v=1` 版本位 |
| 手机端扫码 | 已做（zxing + CAMERA，仅手机 APK） | 负责人拍板「引 zxing，做完整扫码」 |

### 第 4 期（原计划内容，保留备查）

- `AuthFlow` 抽取（手机端同步改造）+ `TvLoginActivity` 重写
- **扫码配对**（10.4）：TV 端配对服务 + 二维码；手机端扫码 + 确认页；6 位码兜底
- 依赖同步一次：`com.google.zxing:core`（TV）、`com.journeyapps:zxing-android-embedded`（手机）
- 局域网发现（L2，可选，若你批准）
- 空态/错误态/重试/骨架屏覆盖
- 性能：图片内存上限、列表复用、首屏时间
- 双 ABI 打包、真机回归

### 每期都必须过

- JS 127 / Python 全量 / e2e 107 / 源码清单刷新
- Java 行数冻结常量同步（`test_android_audit_scope_moved_out.py`）
- 新增文件名进 `CHANGELOG_AI.md` / `PROJECT_CONTEXT.md` / `TODO.md` / `docs/AUDIT_LEDGER.md` 之一
- 模拟器（x86_64 + `tvEmulator` 变体）逐页截图验收

---

## 13. 验收标准（可测）

1. **首屏**：冷启动到首页可交互 ≤ 2.5s（现约 3.2s）。
2. **字号**：3 米外能读出卡片标题（1080p 下 18sp 实测通过）。
3. **焦点**：任何方向键连按 30 次，焦点不丢、不跳格、不落到隐藏元素。
4. **播放页**：从任何页面 OK 进入播放页 ≤ 300ms；唱片旋转不掉帧（≥55fps）。
5. **歌词**：切句延迟 ≤ 150ms；拖进度后 500ms 内对齐。
6. **登录**：已有档案时，开机到首页 ≤ 2 次按键。
7. **返回栈**：任意路径连按返回，最终回到首页再退出，不出现白屏或空 Activity。
8. **扫码登录**：新电视从开机到进首页 ≤ 3 次按键（开机 → 手机扫码 → 确认）；手机端到电视端总耗时 ≤ 5s（局域网千兆）。
9. **配对安全**：过期后的二维码扫了必须被拒（410）；同一码第二次使用必须被拒（401）；公网来源必须 403；成功后服务端口必须不可连接。
10. **对比验收**：与网易云 TV / QQ 音乐 TV 并排截图，导航/播放页/歌词页三屏的布局比例误差 ≤ 10%。

---

## 14. 风险与待你拍板

| # | 事项 | 我的建议 |
|---|---|---|
| 1 | 强调色：蓝（品牌）还是学网易云红 / QQ 音乐绿 | **用蓝 `#3B82F6`**，与手机端、应用图标一致；两家的红/绿都是各自品牌色，没有可借鉴的普适性 |
| 2 | 播放页形态：2 种（封面/歌词）还是 4 种（加动效歌词、氛围） | **2 种**。QQ 音乐的 4 种里 `colorful`/`dynamic_lyric` 依赖在线曲库的逐字歌词与视觉素材，本地库做不出来效果，反成负担 |
| 3 | 封面是否保留缓慢旋转（黑胶味） | 默认开启 20s/圈，设置里可关。只是 `RotationAnimator`，成本极低 |
| 4 | 顶部 Tab 5 个是否太多 | 可合并为 4 个（设置并入「我的」）；默认按 5 个做，改起来只是删一行 |
| 5 | 首页 shelf 由客户端规则拼装（无服务端推荐） | 接受。两家的首页都是服务端下发 DSL，我们没有后端推荐；本地规则（最近添加/收藏/常听）已够用 |
| 6 | 登录 L2（局域网发现）是否本期做 | 不做。L3 扫码配对已覆盖「地址+凭据」两件事，L2 只剩下「服务器不可达时的兜底」，价值不大 |
| 6b | 扫码配对要不要做（10.4） | **做**，第 4 期。~990 行，含 TV 端配对服务 + 手机端扫码 |
| 6c | 扫码配对要引入 zxing（TV 560 KB / 手机 200 KB），需要一次联网 gradle 同步 | 建议接受。这是本方案里唯一需要联网拉依赖的地方；拉不到就退到 WebView 方案（功能不变，代码更多） |
| 6d | 手机端要新增 CAMERA 权限与扫码页 | 必须，否则这个功能只能做到「6 位码手输」。会动 `android-client` 的 Manifest 与依赖 |
| 6e | 配对报文是否 AES-GCM 加密 | 建议开（6 位码派生密钥，约 40 行）。局域网 + 60s 窗口已经够安全，加密是纵深防御 |
| 7 | 焦点用「每项自绘描边」还是「飞行焦点框」 | 本期自绘（1.08 缩放 + 3dp 白边），飞行框留到第 4 期评估 |
| 8 | 是否引入自定义字体（DIN / 兰亭） | 不引入，省 3–5 MB |
| 9 | 工作量 | 四期合计约 4500–5500 行新 Java，替换现有 1900 行 TV 代码 |

---

## 附：关键实测数据出处

### 网易云 TV 1.1.80（`_external/tvapp-analysis/netease-tv/`）

| 结论 | 文件 |
|---|---|
| 顶部 Tab 规格 | `resources/res/layout/af.xml` |
| 播放页比例（唱片 52%） | `resources/res/layout/dq.xml` |
| 唱片双缓冲 | `resources/res/layout/fu.xml` |
| 歌词页 40%×50% | `resources/res/layout/mu.xml` |
| 登录扫码页 | `resources/res/layout/mt.xml` |
| 两层 Tab 页 | `resources/res/layout/cv.xml` |
| 色值/间距/字号分布 | `resources/res/values/{colors,dimens,styles}.xml` |
| 页面树（103 Activity） | `resources/AndroidManifest.xml` |
| 主界面逻辑 | `sources/com/netease/cloudmusic/tv/activity/MainActivity.java` |
| 登录逻辑 | `sources/com/netease/cloudmusic/app/dialog/LoginDialog.java` |

### QQ 音乐 TV 9.0.0.39（`_external/tvapp-analysis/qqmusic-tv/`）

| 结论 | 文件 |
|---|---|
| 主界面（Tab 250dp 区 + ViewPager） | `resources/res/layout/fragment_home_tabs.xml` |
| 封面模式栅格（7.29/55/60.7/92.7） | `resources/res/layout/activity_player.xml` |
| 歌词模式栅格（7.81/45.3/49.5/92.18） | `resources/res/layout/activity_player_style_lyric.xml` |
| 歌曲信息区（歌名+收藏+歌词容器） | `resources/res/layout/player_song_info_view.xml` |
| 控制条（seekbar 12dp + Flow 5 按钮） | `resources/res/layout/player_control_buttons_views.xml` |
| 顶部区（返回 + 4 图标） | `resources/res/layout/player_top_area_view.xml` |
| 歌词控件（逐字着色 50ms） | `resources/res/layout/view_player_center_lyric.xml` |
| 黑胶封面组件 | `resources/res/layout/player_album_cover_vinyl.xml` |
| 4 种播放器模式 | `resources/res/layout/layout_player_{album,lyric,colorful,dynamic_lyric}_mode.xml` |
| 登录扫码 + 四态遮罩 | `resources/res/layout/activity_comm_login_layout.xml` |
| 列表行（50dp） | `resources/res/layout/common_layout_single_item.xml` |
| TV 尺寸体系（`kgtv_qmusic_dp_N` = N/2 dp） | `resources/res/values/dimens.xml` |
| 分辨率基准（`tv_screen_height=540dp`） | `resources/res/values-1920x1080/dimens.xml` |
| 焦点缩放 1.1 | `sources/com/tencent/karaoketv/ui/view/FocusLayout.java` |
| 飞行焦点框 | `sources/com/tencent/karaoketv/ui/view/FocusBorderView.java` |
| 边界回弹 | `sources/com/tencent/karaoketv/ui/view/BounceFocusRootRelativeLayout.java` |
