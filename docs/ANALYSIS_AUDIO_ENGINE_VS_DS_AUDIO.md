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
| 预取 | R567 起播放开始时预热**下一首的转码缓存**（`warmUpcomingTrackCache`）；浏览器侧不预取 URL，R600 判死（媒体响应不可复用） |

---

## 3. 逐项对比

| 维度 | Audio Station | fnAudio | 判断 |
|---|---|---|---|
| 解码在哪 | 客户端 MediaPlayer；服务端只做转码 | 同（浏览器/ExoPlayer/MPD 本地解） | 持平 |
| 格式策略 | 每曲一问，`MP3`/`WAV` 二选一，默认 WAV | 按扩展名自动判（`BROWSER_NATIVE_EXTENSIONS`），WMA 等转 mp3 | 我们更聪明，但**默认更省带宽 = 更容易撞解码边界** |
| 首播延迟 | 边下边播 + 命中缓存走本地文件 | ffmpeg 起进程 → 管道首帧；缓存命中才快 | **我们慢** |
| 下一首准备 | 提前 `prepareAsync` + `setNextMediaPlayer` | 只预热转码缓存；浏览器侧不预取 URL（R600 判死：媒体响应不可复用） | **我们弱**，但补不了 |
| 曲间无缝 | 平台级无缝（同格式可做到零 gap） | 浏览器每首换 `src`；ExoPlayer 队列接近但跨格式必有 gap | **我们弱** |
| 本地缓存 | 整曲落盘，断网可放 | 只有转码缓存，原文件不复用；断网即停 | **我们弱** |
| 错误分流 | 格式错提示、其它自动下一首 | `audio.onerror` **只处理 DSD**，其它静默 | **我们弱**（最该补） |
| 熄屏/后台 | `setWakeMode(PARTIAL)` + 前台服务 | ExoPlayer 前台服务 + WifiLock；浏览器靠页面保活 | 持平（安卓侧） |
| 转码并发 | 未知（服务端加密） | 2 路，超时 5s 抢槽 | 我们可控 |
| 队列模型 | 内存全量 + flatbuffer 落盘 | 内存 + 服务端 SQLite + 按页追加（R571） | 我们更省内存 |

---

## 4. 稳定性差距，按风险排序

> **状态（2026-11-18 复核）**：① 已修（`media_error_policy.js` + 守卫 `test_ui_media_error_policy.js`）；
> ② 已实测撤回；③④⑤ **仍是缺口，不是缺陷**——没有一条会让用户看到"坏了"，只是不如 AS 顺。
> §5 的表里有四行到现在没有状态标记，本轮补齐：两项未做（都是优化），一项待真机确认，一项是大工程。
> 其中「转码错误码分类」由 R598 落地、R599 把「缺解码器」从永久判定里拆出来；剩三项仍见 §5 的状态列。

**① 播放出错等于卡死（P0）**
`app.js` 里 `audio.onerror` 只认 DSD：

```js
audio.onerror = () => {
  if (currentItem()?.is_dsd === true) { alert("DSD 兼容流不可用…"); stopLocalAudio(); }
};
```

其余错误（转码失败、404、连接断）**没有任何处理**：播放器停住、进度条不动、用户以为"卡了"。Audio Station 在这个位置是"格式错提示、其它自动下一首"。

**② 首播要等 ffmpeg 起灶（P1）——已测，实测无收益**
曾判断 `transcode_command` 缺 `-probesize/-analyzeduration` 会让 ffmpeg 白等 5 秒。**R574 在测试机上量过了**：带参数 23ms、不带 22ms（各 5 次中位数），没有收益——本地文件解析完头部即可开工，"探测 5 秒"只对真正的流式输入成立。参数已撤回，度量脚本与基线保留在 `tools/measure_first_byte.py`、`docs/perf/baseline_first_byte.json`，结论记在 `docs/PERF_STABILITY_PLAN.md`。

**③ 曲间有空档（P1）**
浏览器换 `src` 是硬切；ExoPlayer 虽然 `setMediaItems` 有队列能力，但我们把**每一首都转成 mp3**（开了转码时），转码流之间没有 gapless 元数据，仍然会断。Audio Station 靠 `setNextMediaPlayer` 绕开这个问题。

R601 去掉了空档里浏览器侧唯一能省的两段：自动续播不再等 `/api/playback/control` 回话才装载（本地 `nextIndex()` 先接上，服务端回话只用来对齐账本），转码曲目也不再为"缓存好了没"多发一次 `/api/transcode/warm`（复用上一首播放时预热拿到的 `ready` 答案）。剩下的空档是服务端首字节与浏览器解码，属平台差异，见 `docs/PERF_STABILITY_PLAN.md` §P1-2。

**④ 断网/弱网没有退路（P1）**
Audio Station 放过的曲就是本地文件。我们没有原文件缓存，网络一断就停在半句。

**⑤ 下一首的"预热"只暖了一半（P2）——判死，不做（R600）**
R567 预热的是**转码缓存**，浏览器侧的 `<audio>` 没有预加载下一首 URL，切歌时仍要经过 建立连接 → 首字节。曾经的建议是"复用同一个 warm 结果，把 next 的 URL 喂给 `new Audio()` 或 `link rel=prefetch`"。

R578 在测试机上量过（冷启动 603/726 ms vs 预热后 638/617 ms，差值在噪声内）并撤掉了实现；**R600 补上了它为什么不可能有收益**：流式转码的响应是 `Cache-Control: no-store`，命中缓存走 `serve_file_range` 的响应则**没有 `ETag`／`Last-Modified`／`Cache-Control`**——两条路都让浏览器无权把预取的字节交给另一个元素，第二次请求必须重新传。预取唯一确定的后果是多开一条转码流，和真正要播的请求抢 ffmpeg 槽（默认并发 2）。机制上判死，不再量、不再排期。详见 `docs/PERF_STABILITY_PLAN.md` §P1-2 的 R600 小节。

---

## 5. 建议的改法（按性价比排）

| 优先级 | 动作 | 落点 | 代价 | 状态（2026-11-18 复核） |
|---|---|---|---|---|
| **P0** | 错误分流：非 DSD 错误 → 提示 + 自动跳下一首（连续失败 3 次才停） | 已实现：`media_error_policy.js` + `app.js` | 完成（守卫 `test_ui_media_error_policy.js`） | ✅ 已落地 |
| **P0** | 转码失败要能区分"格式不支持"与"临时失败"，前者不再重试 | `transcode.py` 错误码 | 小 | ✅ **已落地（R598，R599 收口）**：`transcode_error_policy.py` 十一个码；`unsupported_format` 是唯一的永久码（写 `<target>.failed` 标记、415、客户端记「放不了」），`decoder_unavailable` 在 R599 从它里面拆出来——缺解码器是 ffmpeg 构建的事，换构建就能解，不该记在文件头上 |
| ~~P1~~ | ~~ffmpeg 加探测参数~~ **实测无收益，已撤回**（23ms vs 22ms） | `transcode_command` | 已关闭 | ✅ 已撤回 |
| ~~P1~~ | ~~浏览器预热下一首 URL（与转码预热同步）~~ **机制上不成立，已关闭** | `warmUpcomingTrackCache` 旁加 `new Audio(url)` | 已关闭 | ✅ **关闭（R600）**：媒体响应不可复用——流式转码 `no-store`，缓存文件无 `ETag`／`Last-Modified`／`Cache-Control`，浏览器无权把预取字节交给播放元素，第二次请求照传。R578 的测量（差值在噪声内）是这个事实的表象，不是独立结论。守卫：`test_server_transcode_stream.py` 两条响应头用例 + `test_ui_media_error_policy.js` 三处禁加 |
| **P2** | 安卓侧确认 `setPauseAtEndOfMediaItems(false)`，让 ExoPlayer 用队列原生衔接 | `PlaybackService` | 小 | ⚠️ **未复核**：原生队列走 `NativePlaybackBridge.java:238` 的 `setMediaItems(...)`，全仓没有显式设过这个开关，行为依赖 Media3 默认值——要在真机上确认曲间是否自动衔接 |
| **P2** | 原文件本地缓存（IndexedDB/OPFS 或安卓磁盘），断网可用 | 新模块 | 大 | ❌ **未做**（大工程，未排期） |

---

## 6. 怎么验证（不是拍脑袋）

- **首播延迟**：`curl -o /dev/null -w "%{time_starttransfer}"` 对 `?transcode=mp3` 的同一首曲，改前后各 10 次取中位数。
- **错误分流**：把一首曲的文件改名制造 404，看是否自动跳下一首而不是停住。
- **曲间空档**：连续播 20 首，用 `audio.ontimeupdate` 记录 `ended` → 下一首 `playing` 的间隔，取中位数。
- **断网**：播放中禁用网络，看已缓冲是否还能放完、是否给出可理解的提示。

## 7. 一句话总结

Audio Station 的稳定是**工程取舍**堆出来的：默认转 WAV 换解码确定性、边下边播换体感延迟、提前 prepare 换无缝、错误分流换"永远有下一首"。fnAudio 的解码与自动转码其实比它更聪明，缺的是这几层"兜底"——其中**错误分流**和 **ffmpeg 探测参数**两处改动最小、收益最直接。
