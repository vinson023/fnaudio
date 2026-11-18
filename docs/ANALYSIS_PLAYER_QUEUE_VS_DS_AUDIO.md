# Audio Station 的播放器与播放队列：逆向分析 + 与 fnAudio 的差异

> 结论先行：**AS 的队列是"客户端自持的一对数组"——源列表 `playItemQueue` 不动，播放序 `playIndexQueue` 是一个排列，随机播放就是打乱这个排列而不是随机取下一首。fnAudio 的队列是"服务端自持的 id 数组 + 下标"，随机播放是真的每次都随机挑一个。** 前者让"上一首"可逆、让一轮之内不重复、让关掉随机仍停在当前曲；后者做不到这三件事，而且同一个按钮在三种客户端上有三种语义。真正值得搬的只有四条，其余要么 ExoPlayer 已经做得更好，要么是 AS 自己的补丁。

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `references/AudioStation/Android-DSaudio.3.16.0-547.cn.apk` | 已反编译（`_analysis_dsaudio/`），`com.synology.p000dsaudio` 624 个类 | **A 档，可逐行验证**（队列、播放器、持久化、AIDL 契约） |
| `references/AudioStation/AudioStation-x86_64-7.0.3-5401.spk` | 加密容器，取不出代码 | 只用于解释"为什么 AS 要问服务端队列上限"（`playingQueueMax` 由 NAS 下发） |
| fnAudio 源码 | 本仓库 | **A 档**，服务端 `playback/`、`src/app/ui/app.js`、`android-client` |

下文凡给类名 + 行号的都是 A 档；凡写"推断"的，是我从字段名与调用形状反推的，不作结论使用。

本文只谈**播放器与队列**。音乐库/媒体索引那一层已在 `docs/ANALYSIS_LIBRARY_INDEX_VS_DS_AUDIO.md` 里逐项对过，不重复。

---

## 1. Audio Station 的播放器与队列

### 1.1 三层分工：目标、队列、解码器

AS 把"往哪儿放"和"放什么"彻底拆开：

| 层 | 类 | 职责 |
|---|---|---|
| 目标层 | `playing/PlayingStatusManager.java:56-72` | `PLAY_MODE{STREAMING, RENDERER, CHROMECAST}`，管"现在往哪放"、音量、睡眠定时器 |
| 队列层 | `model/data/PlayingQueueManager.java` | 队列内容、播放序、重复/随机、当前下标 |
| 解码层 | `mediasession/players/StreamingMediaPlayer.java` | 两个 `AudioMediaPlayer` 实例（当前 + 下一首）、缓冲、错误、位置刷新 |

切目标是一次"存盘 → 停 → 重载"（`PlaybackService.java:843-849`）：

```java
public void doBeforeSwitchIfNecessary(List<? extends SongItem> list) {
    savePauseStatus();      // 位置、下标、repeat、shuffle 写文件
    saveQueue(list);
    stop(false);
    this.mReloadCompleted = false;
}
```

`mReloadCompleted` 这个标志的存在本身就是证据：切目标期间到达的 `onPlay()` 不能被丢掉，得先记成 `mOnPlayCalledBeforeQueueReload`，等重载完成再执行（`PlaybackService.java:388-390`）。**这是 AS 自己的异步重载竞态补丁，不是设计。**

### 1.2 队列 = 源列表 + 播放序排列

```java
private final ArrayList<Integer> playIndexQueue = new ArrayList<>();
private final ArrayList<SongItem> playItemQueue = new ArrayList<>();
private final AtomicInteger mCurrentIdx = new AtomicInteger(0);   // 指向 playIndexQueue
```

- `playItemQueue`：歌曲本体，**只有增删，不因随机而变**；
- `playIndexQueue`：`playItemQueue` 的一个排列，随机播放就是打乱它；
- `mCurrentIdx`：排列里的游标；`getPlayIndex()` 把它翻译回源列表下标（`PlayingQueueManager.java:364-370`）。

于是三件事同时成立：

| 操作 | 实现 | 效果 |
|---|---|---|
| 打开随机 | `shuffle()` 把其余元素 Fisher-Yates，**把当前曲放回原槽位**（`580-624`） | 当前这首不中断 |
| 关闭随机 | `unShuffle()` 先 `mCurrentIdx = playIndexQueue[mCurrentIdx]`，再恢复恒等排列（`626-668`） | 仍停在当前这首，只是"下一首"变回列表顺序 |
| 下一首 | `next(false, true)` 在排列里 +1（`400-419`） | 一轮之内不重复；"上一首"能退回真正来过的那首 |

`addSongsToNext`（`195-250`）插在当前曲之后时，会把排列里所有大于 `playIndex` 的值整体 `+size`，再给新元素补 `playIndex+1 … playIndex+size` 的槽位——**插入不影响已有播放序**。

一个反例，说明它也不是全对：`next()` 第 406-408 行在"单曲循环 + 已在队尾"时直接 `return null`（因为先判 `repeat != ALL && i+1 >= size` 就退出了），这个边界 AS 自己也是漏的。fnAudio 的 `nextIndex()` 反而写对了（`repeat === "one"` 直接返回当前索引）。**所以是"照它的模型，不照它的实现"。**

### 1.3 入队：五种动作，三条分支

动作枚举 `Common.PlaybackAction{PLAY_NOW, ADD_ONLY, ADD_PLAY, BY_SITUACTION, ADD_NEXT}`（`Common.java:354-359`），到服务层收成三条分支（`PlaybackService.java:893-918`）：

| 动作 | 行为 | 附带 |
|---|---|---|
| `play_now` | 清空 + 立刻播 | `queueSize` 置 0 触发自动开播 |
| `add_next` | 插到当前曲之后 | 正在放/暂停时不抢播放，否则开播 |
| 其余（`add_only`/`add_play`/`by_situation`） | 追加到队尾 | **若随机开着，追加后重新 `shuffle()`** |

最后一行是细节：追加进队列的新歌也得进随机序，否则"随机播放"里永远听不到刚加的歌。

### 1.4 容量是目标的能力，不是常量

```java
private static final int CHROMECAST_MAX_SONG_CAPACITY = 1000;
public  static final int DEFAULT_REMOTE_MAX_SONG_CAPACITY = 4096;
private static final int MAX_SONG_CAPACITY = Integer.MAX_VALUE;   // 本机
```

`QueueMaxCount.getQueueMaxByPlayer(mode)`（`mediasession/QueueMaxCount.java:42-54`）：本机无限、Chromecast 1000、DLNA 渲染器用 `remoteQueueMax`——而这个值来自登录响应：`LoginViewModel.java:329` 的 `QueueMaxCount.INSTANCE.setRemoteQueueMax(apiAudioInfoVo.getPlayingQueueMax())`。**NAS 知道那台渲染器能吃多少，客户端不猜。**

用的时候是"先问余量、再截断、并告知"（`activity/BaseActivity.java:92-96, 146-150`、`fragment/ContentFragment.java:861`）：

```java
int free = action != PLAY_NOW ? max - currentSize : max;      // 余量
if (checkSize(action, list)) { /* 全收 */ }
else { list = list.subList(0, free); /* 收得下的部分 */ }
// 提示文案里的 [__SONGLIMITATION__] 被替换成上限数字
```

### 1.5 持久化：队列一份、状态一份，每秒一次

| 文件 | 格式 | 内容 |
|---|---|---|
| `nowplayinglist-<dsId>.bin` | FlatBuffer（`NowPlayingManager.java:195-212`） | 整个队列 |
| `nowplayingstatus-<dsId>` | JSON（`43-63`） | `isPlaying`、`playPos`、`preSeekTime`、`repeatmode`、`shufflemode` |

`playPos` 与 `preSeekTime` 分开是有意的：`playPos` 是队列下标，`preSeekTime` 是"下次打开要跳到的秒数"。`doReloadAll` 恢复时把两者一起塞进延迟 100 ms 的打开消息（`PlaybackService.java:852-881`）。

保存时机是一个 1 秒的 `TimerTask`（`460-473`）：

```java
public void run() {
    if (getReloadSuccessful()) saveStatus();        // 每秒写一次状态文件
    if (DeviceCustomization.supportForceNext()) checkMissingOnComplete();
}
```

**每秒一次 JSON 落盘**——这是本文唯一明确建议"别学"的性能细节（见 §5）。

### 1.6 播放器：双实例中继 + 预载 + 看门狗

`StreamingMediaPlayer` 同时持有两个 `AudioMediaPlayer`（当前 / 下一首），完成时做"接力"而不是"重开"（`79-109`）：

```
onCompletion(current) → hasNextPlayer() ?
    current.release(); mediaPlayer = nextPlayer;   // 已经 prepare 好，原生无缝
    currentSong = nextSong; nextPlayer = null; 重新挂监听 → 通知
  : 发停止消息
```

`AudioMediaPlayer.setNextPlayer` 里走的是平台能力（`362-377`）：`setNextMediaPlayer()`（API 16+ 的 gapless），失败则降级为"在 `onCompletion` 里手动 `nextPlayer.start()`"（`257-266`）。

预载有一个反向判断，值得记一笔（`591-604`）：

```java
if (current.isDownloading()) { nextStatus = Waiting; return; }   // 当前曲还在下载就不预载下一首
```

**别和正在播的那首抢带宽。**

三个故障处理，都是"具体判据"而不是"重试三次"：

| 机制 | 位置 | 判据 |
|---|---|---|
| 打开超时 | `PlaybackService.java:706-725` | 未初始化就计一次失败，失败次数 ≥ 队列长度则清零，否则 100 ms 后跳下一首 |
| 完成看门狗 | `634-640` | `position() - duration() <= 2000` 才算正常完成；否则认为"提前结束"→ 跳下一首 |
| 电台重连 | `AudioMediaPlayer.java:268-305` | `duration == 0` 视为电台；最多重连 5 次，每次隔 10 s，`reset() + setDataSource + prepareAsync` |

看门狗被 `DeviceCustomization.supportForceNext()` 门控——AS 自己把它当**特定机型的补丁**，不是通用机制。这条我在 §4 里按"借判据、不借机制"处理。

其余：位置 500 ms 刷新一次（`StreamingMediaPlayer.java:539-549`）、缓冲百分比上报、`Equalizer` 绑音频会话、SDK 28+ 用 `OnMediaTimeDiscontinuityListener` 读倍速、睡眠定时器就是一个 `CountDownTimer`（`widget/SleepTimer.java`，到点 `pause()`）。

---

## 2. fnAudio 的播放器与队列

### 2.1 真相源在服务端

`playback/core.py` 的 `PlaybackState` 是唯一真相：`queue`（`TrackRef` 列表）、`current_track_id`、`current_index`、`position`、`duration`、`repeat`、`shuffle`、`playing`、`target_kind`。客户端（Web / Android / DLNA 渲染器）都是镜像。

落盘走 `state.sqlite3`（`state_store.py:463-483`），队列 id 上限 **50000**（`playback_session_projection.py:8`），字段包含 `position`。

### 2.2 队列 = id 数组 + 下标

```js
state = { queue: [], index: -1, repeat: "off", shuffle: false, ... }   // app.js:1
```

没有"播放序"这一层。`nextIndex()` / `previousIndex()` 是纯函数（`app.js:5339-5357`）：

```js
function nextIndex() {
  if (state.repeat === "one" && state.index >= 0) return state.index;
  if (state.shuffle && state.queue.length > 1) {
    let next = state.index;
    while (next === state.index) next = Math.floor(Math.random() * state.queue.length);
    return next;
  }
  if (state.index < state.queue.length - 1) return state.index + 1;
  return state.repeat === "all" ? 0 : -1;
}
```

服务端 `next_track()`（`playback/core.py:472-487`）是同一套逻辑的 Python 版：`random.choice([i for i in range(n) if i != current])`。

### 2.3 三种客户端，三种随机

| 出口 | 随机是怎么算的 | 证据 |
|---|---|---|
| Web（`<audio>`） | 每次"下一首"重新随机一个不等于当前的 | `app.js:5339-5357` |
| 服务端（远端目标） | `random.choice` 同上 | `playback/core.py:477-479` |
| Android 本机（ExoPlayer） | **ExoPlayer 自己的 shuffle 排列** | `NativePlaybackBridge.java:205` `setShuffleModeEnabled`，`step()` 走 `seekToNextMediaItem()` |

也就是说：同一个"随机播放"按钮，在浏览器上是"每次重掷骰子"，在手机上是"一轮不重复"。用户换个设备就换了一种随机。

### 2.4 Android：整条队列交给 ExoPlayer

`setQueue(json, index, position, autoPlay, repeat, shuffle)` 直接 `controller.setMediaItems(items, index, position)` + `prepare()`（`NativePlaybackBridge.java:191-213`）。**无缝播放、下一首预缓冲都是 ExoPlayer 播放列表自带的能力**，不需要自己造中继。

导航另有 `NavigationDecision`（纯函数、可离线单测），因为 ExoPlayer 的 `seekToNextMediaItem()` 在队尾是 no-op，会导致"最后一首播完了 UI 还显示在播"。

### 2.5 位置持久化：写了，但没人读

`save_playback_session` 把 `position` 写进了 `state.sqlite3`，但恢复路径（`app.js:1675-1745`）只读 `queue` / `current_id` / `repeat` / `shuffle` / `target_id`，**全仓没有任何地方读 `playback.position`**（`grep "playback\.position"` 零命中）。Web 端暂停是纯本地的 `audio.pause()`，不上报服务端。

结果：刷新页面 → 队列和当前曲回来了，位置回到 0；服务端那个 `position` 字段除了给 SSE/状态查询看，没有消费者。Android 的**远端**会话倒是读了（`PlaybackService.java:677` 把 `position_ms` 塞进 `EXTRA_POSITION_MS`），只有浏览器本机这一条链断了。

### 2.6 错误处理与队列延长

- 不可播名单：`media_error_policy.markUnplayable()`（上限 200），自动续播时 `nextPlayableIndex()` 跳过，放出来即除名（`app.js` `loadCurrent()` 的 `autoAdvancing` 分支）。
- 队列自动延长：`queueStream` + `QUEUE_LOOKAHEAD = 5`，剩 5 首时追加下一页（`app.js:5199-5266`）——这是 AS 没有的（AS 用显式的"按情境播放"动作）。

---

## 3. 差异总表

| # | 维度 | Audio Station | fnAudio | 谁更好 |
|---|---|---|---|---|
| 1 | 队列真相源 | 客户端进程内，落 FlatBuffer | 服务端内存 + `state.sqlite3` | **fnAudio**（跨设备、可换机继续） |
| 2 | 随机模型 | 排列（`playIndexQueue`） | 每次随机下一首 | **AS** |
| 3 | 关随机后位置 | 停在同一首 | 停在同一首（但下一次"下一首"跳到相邻，与刚才听过的那首无关） | 平（都停住，但 AS 的"上一首"可逆） |
| 4 | 一轮内重复 | 不重复，直到排列走完 | 会重复；100 首的队列约 460 次才听全（coupon collector） | **AS** |
| 5 | "上一首"语义 | 走排列回退，真的回到来过的那首 | 恒为 `index-1`，与随机无关 | **AS** |
| 6 | 跨端随机一致 | 单客户端，天然一致 | 浏览器随机 / 手机排列 / 远端随机，三种 | **AS** |
| 7 | 队列上限 | 按目标：本机 ∞ / Cast 1000 / DLNA 由 NAS 下发（默认 4096） | 服务端 50000；Android 远端快照静默截断到 500 | **AS**（且它截断会告知） |
| 8 | 超限行为 | 截断 + 提示"最多 N 首" | 静默截断 | **AS** |
| 9 | 入队语义 | 五种动作，`add_next` 不抢播放 | 整队列覆盖（`setQueue`），无"下一首插队" | **AS** |
| 10 | 追加后随机序 | 重新 `shuffle()`，新歌进随机序 | 随机无状态，无需处理（因为本来就随机） | 平 |
| 11 | 队列重排 | `reorder(start, limit, ids)` 自定义动作 | 只能"从队列移除"，不能拖动排序 | **AS** |
| 12 | 位置持久化 | 每秒写状态文件 | 字段有、Web 端不读 | **AS** |
| 13 | 无缝播放 | 双播放器中继 + `setNextMediaPlayer` | ExoPlayer 播放列表自带 | **fnAudio**（更省、更稳） |
| 14 | 下一首预载 | 自建 nextPlayer；当前曲在下载时跳过 | ExoPlayer 自动预缓冲；Web 端预热转码缓存（只对 MP3 转码路径） | **fnAudio** |
| 15 | 失败跳过 | 打开超时计数 + 完成看门狗（机型门控） | 不可播名单 200 条 + `nextPlayableIndex` | **fnAudio**（有记忆，不是盲跳） |
| 16 | 队列自动延长 | 无（用"按情境播放"显式动作） | `queueStream` + 预读 5 首 | **fnAudio** |
| 17 | 睡眠定时器 | 有（30/60/90 分钟，到点暂停） | 无 | **AS** |
| 18 | 均衡器 / 倍速 | 有（绑音频会话 / 读 clockRate） | 无 | AS（但属产品范围，非队列问题） |
| 19 | 状态写盘频率 | 每秒一次 JSON | 只在命令时写 | **fnAudio** |
| 20 | 队列容量协商 | 服务端下发 `playingQueueMax` | 无（硬编码） | **AS** |

---

## 4. 值得借鉴的四条

按"用户可感知的收益 ÷ 改动面"排序。

> **落地状态（2026-11-18 · R587，R590 收口）**：P1、P2、P3（容量协商）三条已实现，实现与守卫见
> `src/app/server/queue_order_policy.py`、`src/app/ui/queue_order_policy.js`、
> `src/app/server/playback_capability_policy.py`、`src/app/ui/playback_capability_policy.js`，
> 共用真值表 `src/tests/queue_order_table.json`。第四条已拆开收口：**睡眠定时器**由 R588 落地，
> **队列重排**由 R589 的「插播已有行」覆盖（拖拽重排经实测判定不做，与 AS 自己关掉长按拖拽同向），
> R590 关闭该条。**四条全部有结论，没有一条留在待办里。** 下面保留当时的分析与取舍理由，作为改动依据。

### P1 — 随机播放改成"排列"，不是"随机下一首"

**现象（可复现）**：100 首的队列开随机，连续按"下一首"会听到重复的歌，而且总有些歌一次都不出现；按"上一首"回到的不是刚才那首；关掉随机后"上一首"会跳到当前曲的前一首——与刚才的播放轨迹无关。

**证据**：`app.js:5339-5357`（客户端）与 `playback/core.py:477-479`（服务端）都是无状态的 `random.choice`；AS 是 `PlayingQueueManager.shuffle/unShuffle/next/previous`（`580-668`、`400-454`）。

**改法**：队列里加一层 `order`（源下标数组）与 `cursor`，与 AS 同构但不照抄实现：

- `next`：`order[cursor+1]`；`repeat=all` 且到底则回绕到 `order[0]`；`repeat=one` 返回 `order[cursor]`；
- `previous`：`order[cursor-1]`，`repeat=all` 回绕到末尾；
- 开随机：`order` 除当前项外打乱，当前项留在原槽位（AS 的 `shuffle()` 就这么做）；
- 关随机：`cursor = order[cursor]`，`order` 复原为恒等（AS 的 `unShuffle()` 就这么做）；
- 追加：新元素插到 `cursor+1` 之后，并把 `order` 里大于插入点的值整体平移（AS 的 `addSongsToNext`）。

**代价**：`order` 要跟着队列一起持久化（多一个 `state.sqlite3` 字段），`setQueue` 时若随机开着要重建 `order`；`reorder`/`remove` 要同步维护它。

**收益**：一次改掉 #2 #4 #5 #6 四行差异，而且让三个出口的随机语义合一（Web / Android 本机 / 远端）。Android 端可以继续用 ExoPlayer 的 `setShuffleModeEnabled(false)`，由服务端的 `order` 决定下一首——避免"UI 一套顺序、解码器另一套顺序"。

**守卫**：纯函数 `queue_order_policy`（JS + Python 各一份，跨语言常量比对，照 R585 的 `test_ui_library_saved_views.js` 写法）：
`next` 走完一轮不重复；`unShuffle` 后当前曲不变；`addSongsToNext` 后已有播放序的相对顺序不变；空队列/单曲队列不抛。

### P2 — 位置持久化闭环：把已经写下的 `position` 读回来

**现象**：刷新页面（或换设备打开），队列与当前曲都回来了，位置回到 0。

**证据**：`state_store.py:463-483` 写 `position`；`app.js:1675-1745` 恢复时不读；`grep "playback\.position"` 零命中。AS 的 `preSeekTime` 在 `doReloadAll` 里被用于 seek（`PlaybackService.java:852-881`）。

**改法**（比 AS 更省）：不要 1 秒写一次盘。只在三个时刻把位置推给服务端——`pause`、`visibilitychange`（hidden）、`pagehide`，外加播放中每 30 s 一次节流；恢复时 `state.pendingSeekTime = playback.position`，`loadCurrent()` 里已经有 `pendingSeekTime` 这条通路（`app.js:5535`、`5719`）。

**代价**：三个事件监听 + 一次节流上报；服务端已有的 `/api/playback/control`（`seek`）可直接复用，不用新接口。

**守卫**：`state_store` 往返测试（已有 `test_state_store*` 的样板）；JS 侧断言"恢复路径读 `playback.position` 且只在 `> 0` 时设 `pendingSeekTime`"；一条 e2e：播放 → 拖到 30 s → 刷新 → `currentTime ≈ 30`。

### P3 — 队列容量按目标协商，超限要告知

**现象**：Android 远端把队列截到 500 条（`PlaybackService.java:108, 1273`），**用户看不到任何提示**，第 501 首起静默消失。

**证据**：AS 的 `QueueMaxCount` + `getQueueFreeSize` + `[__SONGLIMITATION__]` 文案（`BaseActivity.java:92-96,130-133,146-150`）。

**改法**：容量进 `capabilities`（R585 刚建的那个块），由目标类型决定：

```json
"queue": { "max_items": 50000, "remote_max_items": 500 }
```

超限时**截断 + 一次可见提示**（"队列最多 500 首，已加入前 500 首"）。数不必学 AS 按机型下发——DLNA 渲染器的真实上限拿不到，500 是保守值即可；**要学的是"截断必须说出来"**。

**代价**：小（一个 capability 字段 + 一处提示）。

**守卫**：能力块字段的跨语言比对；截断函数返回 `{items, dropped}`，`dropped > 0` 必触发提示。

### P3 — 队列重排、睡眠定时器（列出但不建议现在做）

- **重排**：AS 用 `reorder(start, limit, ids)` 一次替换一个切片（`PlaybackService.java:358-360, 816-841`）。fnAudio 只有"从队列移除"。要做就是拖拽 + 切片提交，成本主要在 UI 与触摸端手势冲突，收益是"我能把刚加的那首挪到前面"。**排在 P1 之后**，因为有了 `order` 层，重排才有干净的落点。
- **睡眠定时器**：`CountDownTimer` + 到点 `pause()`，半小时的活。纯产品功能，与队列架构无关，**不建议挂在这次改动里**。

---

## 5. 不值得借鉴

1. **双播放器中继做无缝**。AS 需要它是因为 `MediaPlayer` 一次只能播一个源；fnAudio 的 ExoPlayer 播放列表本身就预缓冲下一首并支持 gapless。自己再造一层中继只会把 ExoPlayer 的优势丢掉，还要自己处理"下一个源格式不同"的情况。
2. **每秒写一次状态文件**。AS 的 `UpdateStatusTimer` 每秒 `saveStatus()`。fnAudio 的状态在 SQLite 里，1 Hz 写盘 × 每个在线客户端是纯浪费。**借意图（位置要落盘），不借节奏（§4 P2 的 30 s 节流 + 事件触发）。**
3. **电台专用重连**（5 次 × 10 s）。fnAudio 没有电台；`media_error_policy` 的不可播名单已经覆盖了"这个源打不开"的通用情况，而且有记忆。
4. **`mOnPlayCalledBeforeQueueReload` / `queueInitiated()` 这类补丁**。它们是 AS 异步重载竞态的产物，不是可复用的设计。
5. **均衡器 / 倍速 / Chromecast**。属产品范围，不在"播放器与队列"这条线上；没有用户诉求就不做。

另外两条**只借判据、不借机制**：

- **完成看门狗**：判据是"`duration - position > 2 s` 却收到完成事件 → 当成提前结束"。fnAudio 可以加三行（`audio.onended` 里判一次），但**不要**学 AS 用 1 Hz 轮询去查——那是在没有事件的地方硬造事件。
- **打开超时计数**：fnAudio 已有更好的替代（不可播名单），不重复实现。

---

## 6. 顺带发现的自身缺陷

> **状态（2026-11-18 复核）：已修，R587。** 浏览器侧现在走 `queue_order_policy.js`（与 `queue_order_policy.py` 共用真值表
> `tests/queue_order_table.json`），`applyShuffleOrder()` / `queueOrderCursor()` 都读它；服务端在 `/api/playback/capabilities`
> 里声明 `shuffle.mode = "queue-order"`，客户端 `playback_capability_policy.js` 读这个字段。三个出口的随机语义已合一。

**同一个"随机播放"按钮，三种语义**（§2.3）。这不是"要不要学 AS"的问题，是内部不一致：

- 浏览器：每次重掷；
- Android 本机：ExoPlayer 排列；
- 远端：服务端重掷。

用户在手机和电脑之间切换时，会看到"随机"这件事本身变了。P1 落地后三种合一，这是它的附带收益，也是它优先级最高的理由。

---

## 7. 验证方式

P1（`order` 层）是纯函数，可以完全离线验证，不需要真机：

| 用例 | 断言 |
|---|---|
| 走完一轮 | 从任意起点按 `next` 直到回绕，命中的源下标集合 = 全集，且无重复 |
| 关随机 | `unShuffle` 前后当前曲 id 不变 |
| 插队 | `addSongsToNext` 后，原有元素的相对顺序不变 |
| 单曲/空队列 | 不抛、不死循环（现在的 `while (next === index)` 靠 `length > 1` 兜住，新实现不能退化成死循环） |
| 跨语言 | Python 与 JS 的 `next/previous/unShuffle` 对同一组随机种子给出同一顺序 |

P2 需要一条 e2e（播放 → seek → 刷新 → 位置一致），P3 需要一条"截断即提示"的断言。

真机口径：`android-client/gradlew.bat testDebugUnitTest` 跑 `NavigationDecision` 与新的 `queue_order` 单测；e2e 走 `tools/browser-e2e`（保存视图那条用例的写法可直接复用）。

---

## 8. 一句话总结

AS 在"队列"这件事上比 fnAudio 多想了一层——**把"播什么"和"按什么顺序播"分开存**，代价是一个排列数组，换来随机可逆、不重复、跨端一致；fnAudio 该搬的正是这一层，而不是它的双播放器中继、每秒落盘和一堆机型补丁。位置持久化则是"已经写进库、却没人读"的现成缺口，比 AS 的 1 Hz 写盘便宜得多就能补上。
