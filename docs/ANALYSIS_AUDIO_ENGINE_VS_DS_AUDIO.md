# Audio Station 音频引擎与播放稳定性：逆向分析 + 与 fnAudio 的差异

> 结论先行：**Audio Station 的稳定不是靠"解码器更强"，而是靠四件事——双播放器无缝衔接、边下边播+本地曲库缓存、按错误类型分流、把 CPU 钉醒。** fnAudio 有一半（转码、队列、后台服务），缺另一半（首播等待、无缝、断网、错误分流）。

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `AudioStation-x86_64-7.0.3-5401.spk` | **加密容器**：魔数 `42 AD BE EF`，全文件无 zip/tar/gzip 签名 | 服务端二进制**取不出**，只能从 API 契约反推 |
| `Android-DSaudio.3.16.0-547.cn.apk` | 已反编译，10554 个 `.java`，含 kotlin 元数据 | **可逐行验证** |
| fnAudio 源码 | 本仓库 | 可逐行核对 |

所以下文关于 Audio Station 的判断分两档：**客户端行为有类名/行号**，**服务端能力只有 URL 参数证据**。没有证据的地方我会写明"推测"。

---

## 1. Audio Station 的引擎分层

客户端不是 ExoPlayer，是 **`android.media.MediaPlayer` 外面包了一层**：`AudioMediaPlayer`（421 行）+ `StreamingMediaPlayer`（905 行）+ `PlaybackService`。没有 media3，也没有自研解码。

### 1.1 双播放器 + 平台级无缝

```java
// StreamingMediaPlayer.java:594  mpSetNextData()
this.nextStatus = NEXT_PLAYER_STATUS.Preparing;
AudioMediaPlayer next = new AudioMediaPlayer();
next.setWakeMode(mainContext, 1);          // PARTIAL_WAKE_LOCK
setDataSource(this.nextSong, next);
next.prepareAsync();
...
// AudioMediaPlayer.java:370  准备完成后交给系统做无缝
setNextMediaPlayer(audioMediaPlayer);
```

三点值得注意：

1. **下一首提前 `prepareAsync`**，不是等当前曲 `onCompletion` 才开始拉——首帧和缓冲都在你听上一首时就做完了。
2. **不和当前曲抢带宽**：`mpSetNextData()` 里先判断 `mediaPlayer.isDownloading()`，是则 `NEXT_PLAYER_STATUS.Waiting`，等下载完再准备。
3. **`setNextMediaPlayer` 是平台原语**，在 MediaPlayer 层做无缝交接，跨过 Java 层。

### 1.2 边下边播 + 本地缓存（真正的杀手锏）

`StreamingMediaPlayer.java:461`：

```java
if (缓存配额 == 0 || 是电台) {
    audioMediaPlayer.setStreaming(true);
    playUrl = ConnectionManager.getPlayUrl(songItem);   // 直接流
} else {
    PreDownloader pre = new PreDownloader(...);         // 后台整曲下载
    StreamProxy proxy = new StreamProxy();              // 本地 HTTP 代理
    proxy.init(pre); proxy.start();
    audioMediaPlayer.setProxy(proxy);                   // MediaPlayer 读 localhost
    playUrl = proxy.getUrl() + ext;
}
```

- **首播不用等下完**：MediaPlayer 读本地代理，代理边写边喂。
- **放过的曲就是缓存**：命中缓存时走 `getPlayUri()` → `SynoFile.getUri(true)`，**本地文件，零网络**。
- 断网/弱网时，已缓存的曲照放。

### 1.3 服务端契约：转码是"每曲一问"，不是全局开关

`ApiEnumerator.java:1037` 拼出来的 URL 只有三种：

| 模式 | URL | 用途 |
|---|---|---|
| 原文件 | `SYNO.AudioStation.Stream?method=stream&id=…&_sid=…` | 客户端能解的格式 |
| 转码 | `…?method=transcode&id=…&format=mp3&bitrate=…&ext=.mp3` | 需要降码率/格式 |
| 转 WAV | `…&format=wav&ext=.wav` | `supportMP3()` 为假时的兜底 |
| 电台 | `SYNO.AudioStation.Proxy?method=stream&format=raw|mp3` | 外部流代理 |

选项只有两个：`TranscodeFormat { MP3, WAV }`，且 `TranscodeDownloadQuality` 还带码率档。**注意默认是 WAV**——宁可带宽大，也不要解码失败，这是"稳定优先"的取向。

### 1.4 错误按类型分流

`StreamingMediaPlayer.java:112`：

```java
if (extra == -1007 || extra == -1010) {   // 格式错/不支持
    弹提示("无法播放…"); 停止;
} else {                                   // 其它（网络、解码抖动）
    自动下一首;
}
```

`nextPlayer` 自己出错时只 `releaseNextPlayer()`，**不影响当前正在放的曲**。

---

## 2. fnAudio 的引擎结构

| 环节 | 实现 |
|---|---|
| NAS 本机出声 | MPD（`playback/mpd_client.py`、`mpd_output.py`）；USB DAC 走 ALSA（`alsa_output.py`） |
| 投到音箱/电视 | DLNA push（`dlna_push_output.py`），解码在接收端 |
| 浏览器出声 | `<audio preload="metadata">`（`index.html:141`），每首换 `src` |
| 安卓出声 | media3 ExoPlayer + `setMediaItems(整个队列)`（`NativePlaybackBridge.java:202`）+ 前台服务 `mediaPlayback` + WAKE_LOCK + WifiLock |
| 转码 | ffmpeg 四模式（mp3 / dsd_wav / ape_flac / cue_flac），命中缓存发文件、未命中 `pipe` 流式（`transcode.py:539`、`server.py:2432`） |
| 并发 | `ffmpeg_max_concurrency` 默认 **2**（`transcode.py:630`） |
| 预取 | R567 起播放开始时预热**下一首的转码缓存**（`warmUpcomingTrackCache`） |

---

## 3. 逐项对比

| 维度 | Audio Station | fnAudio | 判断 |
|---|---|---|---|
| 解码在哪 | 客户端 MediaPlayer；服务端只做转码 | 同（浏览器/ExoPlayer/MPD 本地解） | 持平 |
| 格式策略 | 每曲一问，`MP3`/`WAV` 二选一，默认 WAV | 按扩展名自动判（`BROWSER_NATIVE_EXTENSIONS`），WMA 等转 mp3 | 我们更聪明，但**默认更省带宽 = 更容易撞解码边界** |
| 首播延迟 | 边下边播 + 命中缓存走本地文件 | ffmpeg 起进程 → 管道首帧；缓存命中才快 | **我们慢** |
| 下一首准备 | 提前 `prepareAsync` + `setNextMediaPlayer` | 只预热转码缓存；浏览器没有 URL 预热 | **我们弱** |
| 曲间无缝 | 平台级无缝（同格式可做到零 gap） | 浏览器每首换 `src`；ExoPlayer 队列接近但跨格式必有 gap | **我们弱** |
| 本地缓存 | 整曲落盘，断网可放 | 只有转码缓存，原文件不复用；断网即停 | **我们弱** |
| 错误分流 | 格式错提示、其它自动下一首 | `audio.onerror` **只处理 DSD**，其它静默 | **我们弱**（最该补） |
| 熄屏/后台 | `setWakeMode(PARTIAL)` + 前台服务 | ExoPlayer 前台服务 + WifiLock；浏览器靠页面保活 | 持平（安卓侧） |
| 转码并发 | 未知（服务端加密） | 2 路，超时 5s 抢槽 | 我们可控 |
| 队列模型 | 内存全量 + flatbuffer 落盘 | 内存 + 服务端 SQLite + 按页追加（R571） | 我们更省内存 |

---

## 4. 稳定性差距，按风险排序

**① 播放出错等于卡死（P0）**
`app.js` 里 `audio.onerror` 只认 DSD：

```js
audio.onerror = () => {
  if (currentItem()?.is_dsd === true) { alert("DSD 兼容流不可用…"); stopLocalAudio(); }
};
```

其余错误（转码失败、404、连接断）**没有任何处理**：播放器停住、进度条不动、用户以为"卡了"。Audio Station 在这个位置是"格式错提示、其它自动下一首"。

**② 首播要等 ffmpeg 起灶（P1）**
`transcode_command` 没带 `-probesize/-analyzeduration`，ffmpeg 默认要探测约 5 秒的输入才确定编码参数。文件在 NAS 本地时这是纯浪费。加 `-probesize 32768 -analyzeduration 0` 通常能把首帧提前几百毫秒到一秒。

**③ 曲间有空档（P1）**
浏览器换 `src` 是硬切；ExoPlayer 虽然 `setMediaItems` 有队列能力，但我们把**每一首都转成 mp3**（开了转码时），转码流之间没有 gapless 元数据，仍然会断。Audio Station 靠 `setNextMediaPlayer` 绕开这个问题。

**④ 断网/弱网没有退路（P1）**
Audio Station 放过的曲就是本地文件。我们没有原文件缓存，网络一断就停在半句。

**⑤ 下一首的"预热"只暖了一半（P2）**
R567 预热的是**转码缓存**，但浏览器侧的 `<audio>` 没有预加载下一首 URL，切歌时仍要经过 建立连接 → 首字节。可以复用同一个 warm 结果，但要把 next 的 URL 也喂给一个 `new Audio()` 预热（或 `link rel=prefetch`）。

---

## 5. 建议的改法（按性价比排）

| 优先级 | 动作 | 落点 | 代价 |
|---|---|---|---|
| **P0** | 错误分流：非 DSD 错误 → 提示 + 自动跳下一首（连续失败 3 次才停） | `app.js` `audio.onerror` | 小 |
| **P0** | 转码失败要能区分"格式不支持"与"临时失败"，前者不再重试 | `transcode.py` 错误码 | 小 |
| **P1** | ffmpeg 加 `-probesize 32768 -analyzeduration 0`（仅本地文件；网络源保留探测） | `transcode_command` | 小，需实测首帧 |
| **P1** | 浏览器预热下一首 URL（与转码预热同步） | `warmUpcomingTrackCache` 旁加 `new Audio(url)` | 小 |
| **P2** | 安卓侧确认 `setPauseAtEndOfMediaItems(false)`，让 ExoPlayer 用队列原生衔接 | `PlaybackService` | 小 |
| **P2** | 原文件本地缓存（IndexedDB/OPFS 或安卓磁盘），断网可用 | 新模块 | 大 |

---

## 6. 怎么验证（不是拍脑袋）

- **首播延迟**：`curl -o /dev/null -w "%{time_starttransfer}"` 对 `?transcode=mp3` 的同一首曲，改前后各 10 次取中位数。
- **错误分流**：把一首曲的文件改名制造 404，看是否自动跳下一首而不是停住。
- **曲间空档**：连续播 20 首，用 `audio.ontimeupdate` 记录 `ended` → 下一首 `playing` 的间隔，取中位数。
- **断网**：播放中禁用网络，看已缓冲是否还能放完、是否给出可理解的提示。

## 7. 一句话总结

Audio Station 的稳定是**工程取舍**堆出来的：默认转 WAV 换解码确定性、边下边播换体感延迟、提前 prepare 换无缝、错误分流换"永远有下一首"。fnAudio 的解码与自动转码其实比它更聪明，缺的是这几层"兜底"——其中**错误分流**和 **ffmpeg 探测参数**两处改动最小、收益最直接。
