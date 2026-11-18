# Audio Station 的设备输出与系统集成：逆向分析 + 与 fnAudio 的差异

> 结论先行：**这块 AS 的「模型」比我们完整，「消费」比我们少。** 它把每个输出目标建模成「类型 + 分组 + 密码 + `supportSeek` / `supportSetVolume`」，但 `supportSeek` / `supportSetVolume` 在 624 个类里**只有声明和赋值两处，没有任何读取点**——采集了不用。真正值得搬的只有一条，而且不是抄它：**把我们自己已经声明的能力位接到 UI 上**。查这条时发现了一个真 bug：远端目标（USB DAC / DLNA）下，网页的音量滑块只改**本机 `<audio>` 元素**，对 DAC 没有任何作用，而 MPD 适配器其实**早就实现了 `volume` 动作**。其余大部分我们已经有了（设备集轮询、Wi-Fi 锁、拔出暂停、锁屏通知），有一处还比它稳（切换用 revision token，它用全局布尔）。

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `Android-DSaudio.3.16.0-547.cn.apk` | 已反编译，`com.synology.p000dsaudio` 624 个类，含 `mediasession/` 整个包 | **可逐行验证**（A 档：类名 + 行号） |
| `AudioStation-x86_64-7.0.3-5401.spk` | 加密容器（前几轮已复核打不开） | 服务端如何枚举 USB/蓝牙设备只能推断（B 档） |
| fnAudio 源码 | 本仓库 | 可逐行核对 |

本轮不重复 `ANALYSIS_AUDIO_ENGINE_VS_DS_AUDIO.md`（解码、边下边播、缓存）与 `PLAYBACK_OUTPUT_POLICY.md`（适配器职责、Mixer 策略、DSD）。这里只谈**输出目标怎么被发现、怎么被选择、怎么和系统打交道**。

---

## 1. 输出目标的模型

### 1.1 AS：七种类型，两个发现源

`playing/Player.java:70-78` 是客户端真正用的枚举：

```java
public enum PlayerType { LOCAL, USB, BLUETOOTH, UPNP, AIRPLAY, CHROMECAST, UNKNONWN }
```

（`UNKNONWN` 是原文拼写，反编译保留原样。）

而服务端下发的 VO 只有五种（`vos/base/BaseRemotePlayerResponseVo.java:14-19`）：

```java
public enum BaseRemotePlayerType { usb, bluetooth, upnp, airplay, unknown }
```

**差的那两种说明了架构**：`LOCAL` 是手机自己，`CHROMECAST` 由手机上的 Cast SDK 本地发现——**AS 的设备列表是「NAS 能驱动的输出」与「这台手机能投送的接收器」两个发现源的并集**。服务端只负责前者。

每个目标的完整字段（同一个 VO）：

```java
String getId(); String getName(); int getPlayerIndex();
BaseRemotePlayerType getPlayerType();
List<? extends BaseRemotePlayerVo> getSubPlayerList();   // 分组播放器的子设备
boolean isGroupPlayer(); boolean isPasswordProtected(); boolean isUsbSpeaker();
boolean supportSeek(); boolean supportSetVolume();
```

十个字段里，有三个是 fnAudio 完全没有的概念：**分组**、**密码保护**、**能力位**。

### 1.2 能力位：采集了，但没人用

这是本轮最值得记的一条。全文搜索 `supportseek` / `supportsetvolume`（大小写不敏感，含 VO 定义）：

```
item/RendererItem.java:15          private boolean mSupportSeek;              ← 声明
item/RendererItem.java:28          rendererItem.mSupportSeek = ...supportSeek();  ← 赋值
vos/api/ApiRemotePlayerResponseVo.java:116   public boolean supportSeek() { ... }
vos/base/BaseRemotePlayerResponseVo.java:35  public abstract boolean supportSeek();
vos/cgi/CgiRemotePlayerResponseVo.java:74    public boolean supportSeek() { ... }
```

**客户端里没有任何一处读它。** `RendererItem` 上这两个字段是死的。所以 AS 的投送界面**照常显示进度条和音量**，不管对端支不支持——服务端会不会拒绝另说，客户端是不知道的。

这条的价值不在「AS 做得对」，而在**它指对了字段该在哪一层**：能力属于**目标**，不属于界面。

### 1.3 fnAudio：三类目标 + 适配器能力

`app/ui/playback_target_policy.js` 用带前缀的字符串做目标 id（`local` / `mpd:<stable id>` / DLNA 推送），`/api/playback/targets` 每行带 `kind`、`online`、`selected`、`caps`、`message`。

适配器的能力声明已经存在（`app/server/playback/plugins.py`）：

| 适配器 | 能力字典 |
|---|---|
| `BrowserOutput` | `seek: true, pause: true, volume: true, native_dsd: false, server_transcode: true` |
| `DlnaPushOutput` | `seek: true, pause: true, stop: true, next_previous: true, native_dsd: true, server_transcode: false`（**没有 `volume` 键**） |
| `AlsaOutput` | `seek: true, pause: true, stop: true, **volume: false**, native_dsd: false, server_transcode: true` |
| `MpdOutput` | `volume: flag(volume_control.available)` ← **动态取自 ALSA mixer 探测**，另有 `bitperfect` / `dop` / `dsd_mode` |

`build_targets()`（`playback_targets_presentation.py:64`）把 `browser` / `mpd` / `dlna_push` 三份 capabilities 分别挂到对应目标行上。

### 1.4 差异

| 概念 | AS | fnAudio |
|---|---|---|
| 类型枚举 | 7 种（含 chromecast / airplay 发送端） | 3 种（浏览器 / DAC / UPnP 推送） |
| 发现源 | 服务端 + 手机本地（Chromecast） | 仅服务端 |
| 分组（多房间） | ✅ `isGroupPlayer` + 子设备 | ❌ 单目标模型 |
| 密码保护 | ✅ `isPasswordProtected` | ❌ 无凭据模型 |
| 能力位 | ✅ 下发，**客户端不读** | ✅ 下发，**界面不读** |
| 能力位粒度 | 服务端给死的两个布尔 | 适配器按实际探测（`volume` 来自 mixer、`bitperfect` 来自 DSD 探测） |

**最后一行值得注意**：fnAudio 的能力位比 AS 的更细也更准（是探测出来的，不是写死的），但**两边都没把它接到界面上**。

---

## 2. 一个真 bug：音量滑块指向了错误的接收端

顺着「能力位没人读」往下查，发现的问题比「没门控」严重。

`app/ui/app.js:12580`：

```js
$("volume").oninput = e => {
  const value = Number(e.target.value);
  audio.volume = value;                                  // 只改本机 <audio>
  if (nativePlaybackAvailable()) nativePlaybackCall("setVolume", value);
  updateVolumeRail(value);
};
```

而服务端**早就实现了远端音量**（`playback/mpd_client.py:808`）：

```python
elif action == "volume":
    mpd.command("setvol", max(0, min(100, int(safe_float(position)))))
```

`PlaybackCommand` 是通用的 `action + position + track + context`，`volume` 动作对 MPD 已经能用。

**于是现在的行为是**：目标选到 USB DAC 时，拖动音量滑块——本机 `<audio>` 的音量变了（没在播，听不到），DAC 的音量没变，界面上的滑块和填充条却都跟着动了。**一个静默无效的控件。**

而且 `/api/playback/control` 的 `volume` 动作**整条链都修好了**（`server.py:3693-3696`）：

```python
def renderer_control(action, position=None):
    if action == "volume" and MPD_SERVICE:
        mixer = MPD_SERVICE.mixer_policy()
        if not mixer.get("available"):
            return {"ok": False, "message": mixer.get("message") or "renderer volume control is unavailable"}
    ...
    return service_control(action, position)
```

`PLAYBACK_OUTPUT_POLICY.md` 里那句「固定音量目标会明确拒绝音量写入，不伪装成功」——服务端**做到了，连给用户看的话都写好了**；问题全在界面：它根本没走到那条路径上去。

这条是本轮最值得记的一处：**能力位、mixer 策略、拒绝文案、`setvol` 实现，四样都在，缺的是把滑块接上去的那几行。**

---

## 3. 设备集的生命周期

### 3.1 AS：订阅式

`PlayerChooserActivity.java:78-99`，`PlayingStatusManager.PlayerSetObserver`：

```java
public void onPlayerChange(Player player) {
    mSelectedPlayer = player;
    selectPlayer();                       // 当前目标变了 → 重选
}
public void onPlayerSetChanged() {
    runOnUiThread(() -> {
        mPlayerAdapter.notifyDataSetChanged();   // 设备集变了 → 就地重绘
        selectPlayer();
    });
}
```

设备插拔/上线不需要重开对话框。`switchToGroupPlayerEditor` / `switchToSinglePlayerChooser` 是同一界面的两个模式。

### 3.2 fnAudio：轮询，但只在对话框开着时

`app.js:8476` 的 `scheduleDeviceRefresh()` 会在 `deviceDialog.open` 为真时自我续期（`8518` / `8527`）。所以「对话框开着时新设备出现」这一条**已经满足**——只是实现方式是轮询而不是订阅。

### 3.3 切换的竞态：我们比 AS 稳

`doChangePlayer`（`PlayerChooserActivity.java:457`）：

```java
mPlayerStatusManager.setPlayer(player);
mMediaBrowserHelper.getTransportControls().sendCustomAction("...switch_player", null);
Common.gModeSwitchMode = true;      // ← 全局布尔
Common.gDeviceChanged = false;
bindService();
```

切换期间用一个**全局静态布尔**表示「正在切模式」，界面各处去读它。

fnAudio 用的是**版本号 + 令牌**（`app.js:8535`）：

```js
if (token !== state.deviceLoadRequestToken || state.deviceLoadController !== controller
    || targetRevision !== state.deviceTargetRevision || state.deviceSwitchInFlight) return;
```

切换过程中到达的旧响应会被**丢弃**，而不是靠一个全局标志让所有读者自己判断。这一条**不借**，我们更好。

---

## 4. 音频焦点：AS 最精细的一块

`AudioFocusManager.java`（468 行）是自研的，三态机 + 三条回调：

```java
private enum AudioFocus { NoFocusNoDuck, NoFocusCanDuck, Focused }
```

**`onLostAudioFocus()`（永久丢失，如来电）**：

```java
if (playbackProxy.isPlaying()) {
    giveUpAudioFocus();
    if (playbackProxy.isRemotePlayer()) return;        // ← 投送中：直接返回，不暂停
    playbackProxy.pause();
    mResumeAfterInterrupt = playbackProxy.hasAudioToPlay();   // ← 只有真有内容才记「待恢复」
}
```

三条判断各自都有理由：

1. **投送中不暂停**。音频不在本机放，本机丢焦点与远端音箱无关。这是最容易写错的一处——照抄「丢焦点就暂停」会让投送被一通电话打断。
2. **`hasAudioToPlay()` 而不是无条件 `true`**。队列空了/已经播完时不该在来电结束后「恢复播放」一个空队列。
3. 先 `giveUpAudioFocus()` 再暂停，而不是留着焦点占位。

**`onLostAudioFocusCanDuck()`（短暂丢失，如通知音）**：

```java
if (playbackProxy.isPlaying()) {        // ← 只在真的在播时才 duck
    playbackProxy.toDuckVolume();
    ifDuck = true;
}
```

**`onGainedAudioFocus()`**：`ifDuck` 则恢复音量；`mResumeAfterInterrupt` 则 `play()`。

另外 `AudioFocusManager` 里还挂了一个 `SharedPreferences.OnSharedPreferenceChangeListener`——**duck 行为是用户可配的偏好项**，不是写死的。

### 4.1 fnAudio 的现状

Android 客户端把焦点交给 ExoPlayer（`PlaybackService.java:203-205`）：

```java
player.setAudioAttributes(AudioAttributes.DEFAULT, true);   // handleAudioFocus = true
player.setHandleAudioBecomingNoisy(true);                   // 拔耳机自动暂停
player.setWakeMode(C.WAKE_MODE_LOCAL);
```

**没有自研焦点管理器**，用的是 Media3 的默认策略。

于是 AS 那三条判断在我们这里逐条对照：

| AS 的判断 | fnAudio |
|---|---|
| 投送中不因本机丢焦点而暂停 | **天然成立**：投送时本机 `remotePlayer.isRemoteActive()`，ExoPlayer 不持有播放 |
| 只在真的在播时才 duck | Media3 内部同样只在播放中处理 |
| 恢复播放要看中断前有没有内容 | Media3 默认行为；无「恢复空队列」路径 |
| duck vs pause 用户可配 | ❌ 没有这个设置 |

所以这一块**只有最后一行是可补的**，而且是 Android 客户端专属。

---

## 5. 系统集成面

`mediasession/` 这个包是 AS 系统集成的全部：

| 类 | 作用 |
|---|---|
| `service/PlaybackService` | 前台播放服务 |
| `service/AbstractMediaBrowserService` | `MediaBrowserServiceCompat` 基类 |
| `service/AndroidAutoService` | **Android Auto**：`onGetRoot` / `onLoadChildren` / `onSkipToQueueItem` / `searchSongsAndPlay` / `VoiceSearchParams` / `loginForCar`（车机内登录）/ `provideWifiLock` |
| `service/ChromeCastService` + `AbstractChromeCastService` | Cast 会话 |
| `service/RemoteControllerService` | 反向：被别的客户端遥控 |
| `notifications/MediaNotificationManager` | `MediaStyle` + `setShowActionsInCompactView(0,1,2)` + `setVisibility(1)`（锁屏可见）+ `setOngoing(isPlaying)` |
| `MediaButtonReceiver` | 耳机线控 |
| `appwidget/AudioWidget` | **桌面小部件**（`AppWidgetProvider` + `RemoteViews`） |

`AndroidAutoService` 的方法表能看出它做了多少：浏览树（播放列表/歌曲/评分）、语音搜索、队列同步（`updateSessionQueue` / `saveQueue` / `queueValid`）、车载内登录、Wi-Fi 锁。这不是「顺手支持一下」，是一套完整实现。

### 5.1 fnAudio 的现状

| 能力 | AS | fnAudio |
|---|---|---|
| 锁屏/通知三键 | ✅ | ✅ 自定义 `Notification.MediaStyle` + `VISIBILITY_PUBLIC`（`PlaybackService.java:631-634`） |
| 耳机线控 | ✅ `MediaButtonReceiver` | Media3 默认 |
| 拔耳机暂停 | 未查到显式处理 | ✅ `setHandleAudioBecomingNoisy(true)` |
| Wi-Fi 锁 | ✅ `provideWifiLock`（车载侧） | ✅ `WIFI_MODE_FULL_HIGH_PERF`（`PlaybackService.java:233`） |
| Android Auto | ✅ 完整 | ❌ |
| 桌面小部件 | ✅ | ❌ |
| Chromecast | ✅ | ❌ |

前三行是「同级」，后三行是「没有」。后三行见 §8。

---

## 6. 音量与路由

三条路径，AS 和我们是两种组织方式：

| | AS | fnAudio |
|---|---|---|
| 本机音量 | `AudioManager` 流音量（`getStreamVolume(3)` = STREAM_MUSIC） | `<audio>.volume` / native `setVolume` |
| 投送时本机音量 | `RemoteClientVolumeDetector`：记录 `mOriginMediaVolume`，投送开始/结束各恢复一次 | 无（投送时本机不播，无需处理） |
| 目标音量 | 服务端管；客户端只有 `supportSetVolume` 标记（未读） | MPD `setvol` 已实现；DLNA 未声明 `volume`；界面不发送 |

`RemoteClientVolumeDetector` 那个「记录原始音量、结束后恢复」的小动作，只有在「投送时本机仍在出声」的架构里才有意义——AS 的 Chromecast 投送确实可能让手机继续出声。我们没有这个场景，**不借**。

---

## 7. 值得借鉴的清单

只有三条，而且第一条是「补我们自己的半成品」，不是抄 AS。

| 优先级 | 项 | 状态 | 落点 |
|---|---|---|---|
| **P1** | 音量控件按目标路由 + 按能力门控 | ✅ 已落地（R596） | `activeTargetCapabilities()` / `targetVolumeIsFixed()` / `applyVolumeToTarget()` / `syncVolumeAvailability()`（`app.js`）；守卫 `tests/test_ui_volume_target_routing.js` |
| **P2** | 目标行显示「能调 / 不能调音量」 | ✅ 已落地（R596） | `targetVolumeNote()` 接进 `deviceTargetDetail()`；守卫扩展了 `tests/test_ui_device_target_rows.js` |
| **P3** | duck-vs-pause 做成偏好 | ❌ 关闭：做不了验证 | 见 §10 第 3 条 |

### 7.1 P1 的具体口径

三种目标，三种正确行为：

1. **`local`（浏览器/本机）**：保持现状——改 `audio.volume` 或 native `setVolume`。
2. **`mpd:`（USB DAC）**：走 `/api/playback/control` 的 `volume` 动作（`server.py:3693` → `mpd_client.py:808` 的 `setvol`）；`capabilities.volume === false` 时（mixer 固定）**禁用**滑块并直接显示服务端那句 `mixer.message`——那句话已经写好了，不必另造一句。
3. **`dlna_push`**：能力字典里**没有 `volume` 键**——但**不能因此判为不支持**。顺着 `renderer_control` 读下去会发现，DLNA 推送的音量走的也是 `MPD_SERVICE.mixer_policy()`（upmpdcli 就是 MPD），所以它其实能调。**口径因此改成「只有显式 `volume: false` 才禁用，缺键表示未知」**：未知就保持可用，服务端拒绝时把它的 `message` 显示出来（`remoteControl` 已经会 `alert` 那句 `renderer volume control is unavailable`）。

禁用而不是隐藏：隐藏会让播放条宽度跳动，而用户需要知道「这里本来有个音量，但这个输出不归我管」。

---

## 8. 不借鉴：写下来防止回流（已裁定）

> **2026-11-18 负责人裁定：这六条不再借鉴、不再排期、不再复核。** 记在这里是为了下次别再提——不是待办，也不是「以后有空再说」。
> 口径与 `docs/LIBRARY_VIEWS_PLAN.md`、另两份 AS 分析文档的同类小节一致。

| AS 的做法 | 为什么不借鉴 |
|---|---|
| **分组播放器（多房间）** | `PlaybackCore` 是单 target 模型，分组要求服务端同时驱动多路输出并保持同步，改动面等于重写输出层。AS 的 group 也是「服务端合成一个虚拟 player」，不是客户端拼的 |
| **密码保护的 renderer** | 我们的 DLNA 目标是局域网发现出来的，没有凭据模型；引入等于在设备列表里加一套认证状态机 |
| **自研 AudioFocusManager** | Media3 已经接管焦点，再挂一个自研的会和 ExoPlayer 抢 `requestAudioFocus` |
| **`RemoteClientVolumeDetector`** | 只在「投送时本机仍出声」的架构里才有意义，我们没有那个场景 |
| **Android Auto / 桌面小部件 / Chromecast** | 前两个是 Android 客户端专属，第三个需要接收端应用（Cast SDK + 注册的 receiver），都不属于网页端能做的事。要不要做是客户端立项问题，不是「抄 AS」 |
| **全局 `gModeSwitchMode` 布尔** | 我们用 revision token + request token，切换期的旧响应会被丢弃，比全局标志稳 |

六条一律**不做**，也不再进入任何计划。

---

## 9. 一句话对比

| 维度 | AS | fnAudio |
|---|---|---|
| 目标模型 | 7 类型 + 分组 + 密码 + 2 个能力位（不读） | 3 类型 + 适配器能力（更细，也不读） |
| 发现 | 服务端 ∪ 手机本地（Chromecast） | 仅服务端，对话框开着时轮询 |
| 切换 | 全局布尔标志 | revision token（更稳） |
| 焦点 | 自研三态机，投送时不暂停，duck 可配 | Media3 默认；投送场景天然正确；无 duck 偏好 |
| 系统面 | 通知 + 线控 + 车载 + 小部件 + Cast | 通知 + 线控 + Wi-Fi 锁 |
| 音量 | 服务端管，客户端不发送 | 服务端已实现 `setvol`，**界面没接** |

**如果只做一件事**：把音量滑块接到目标上（P1）。这是唯一一条「用户能直接感知、服务端已经准备好、只差界面二十行」的改动。做完之后 §1.4 那张表最后一行「两边都不读能力位」就只剩 AS 一家了。

---

## 10. 落地记录（R596）

两条落地，一条关闭。

**1. 音量按目标路由（P1）**。`applyVolumeToTarget(fraction)`：本地目标写 `audio.volume` + native `setVolume`（原行为不变）；远端目标发 `/api/playback/control` 的 `volume` 动作，单位从控件的 0–1 换成服务端要的 0–100。拖动只做预览（`updateVolumeRail`），**松手才提交**——和进度条同一套 preview/commit 分工，一次拖动一个 POST 而不是一像素一个。

**2. 能力门控（P1 后半 + P2）**。`targetVolumeIsFixed()` 只认显式 `volume: false`；`syncVolumeAvailability()` 把滑块 `disabled`、把原因写进 `title` 和按钮的 `aria-label`，并挂在 `renderDeviceTargets()` 的**早退之前**（目标会变、列表不一定变）。禁用而不是隐藏，播放条宽度不动。目标行副标题由 `targetVolumeNote()` 补一句「固定音量」。

**3. P3 关闭：duck-vs-pause 不做。** 不是优先级问题，是**验证不了**：要让「短暂打断时压低还是暂停」可配，必须把焦点所有权从 Media3 手里拿回来——`setAudioAttributes(attrs, true)` 换成 `false`，自己 `requestAudioFocus` / 处理 `LOSS_TRANSIENT` / `LOSS_TRANSIENT_CAN_DUCK` / `GAIN` / 自己 `setVolume` 做 duck。AS 那套是 468 行、踩过多轮的实现。失败模式是「来电时音乐继续放」或「打断后不恢复」，而这两条**只能在真机上用一通电话验证**，本地没有任何门禁能覆盖。写一个测不到的焦点子系统，风险大于收益。

真要做，它应该是一个**带真机验收口径的独立条目**（参照 `PLAYBACK_OUTPUT_POLICY.md` 的「仍需设备验收」一节），而不是夹在这一轮里顺手改掉。
