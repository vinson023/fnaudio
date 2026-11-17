# 播放稳定性与性能：可持续的 P0–P2 计划

> 来源：`docs/ANALYSIS_AUDIO_ENGINE_VS_DS_AUDIO.md` 第 5 节的建议清单。
> 这份文件不是待办列表，而是**每条建议的度量口径、守卫位置与复核方式**——让"优化过没有"变成可复查的事实，而不是印象。

## 怎么读这张表

每条建议必须落成三样东西，缺一就不算"可持续"：

1. **指标**：一句话说清量什么、单位是什么；
2. **守卫**：一条会失败的自动化断言（测试或脚本），改坏了就红；
3. **复核**：谁在什么时候跑，结果写在哪。

## 现状总表

| 编号 | 建议 | 指标 | 守卫 | 状态 |
|---|---|---|---|---|
| P0-1 | 播放错误分流（非 DSD 自动下一首，连续 3 次停） | 行为：错误后是否前进 / 是否停 | `src/tests/test_ui_media_error_policy.js` | **已实现**（R574） |
| P0-2 | 放不了的曲目不要反复重试 | 同一首被重试的次数 | `test_ui_media_error_policy.js`（名单 + 跳过） | **已实现（客户端自愈）** |
| P1-1 | ffmpeg 探测窗口收紧 | 转码到首字节毫秒数（中位数） | `tools/measure_first_byte.py` + `docs/perf/baseline_first_byte.json` | **已测无收益并撤回** |
| P1-2 | 浏览器预热下一首 URL | 同一 URL 的装载耗时（中位数） | `test_ui_media_error_policy.js`（禁止回归） | **已测无收益并撤回**（冷 603/726ms vs 预热 638/617ms） |
| P2-1 | 安卓 ExoPlayer 队列原生衔接 | 曲间空档毫秒数 | `test_ui_android_bridge.js`（禁止关掉衔接） | **已确认**（`setMediaItems` 整队列，未设 `setPauseAtEndOfMediaItems(true)`） |
| P2-2 | 原文件本地缓存（断网可放） | 断网后能连续播放的曲数 | 待定（实现时补） | **设计完成**（`docs/DESIGN_ORIGINAL_AUDIO_CACHE.md`，安卓先做） |

## P0-1 播放错误分流（已固化）

- **指标**：非 DSD 错误发生时，是否自动切到下一首；连续第 4 次失败是否停下。
- **实现**：`src/app/ui/media_error_policy.js`（纯函数，`decide()` 返回 `dsd-unsupported | stop | next`），`app.js` 的 `audio.onerror` 只做接线，`localErrorStreak` 在 `audio.onplaying` 归零。
- **守卫**：`test_ui_media_error_policy.js` 覆盖 DSD 优先、队尾无下一首、streak 0–2 前进、streak ≥3 停止、脏输入，以及"策略脚本必须先于 `app.js` 加载"。
- **复核**：并入日常 JS 门禁，每次改动都跑。

## P1-1 探测窗口：量过，没收益（结论要留着）

原设想来自"ffmpeg 默认探测 5 秒才定参数"，但那是**流式输入**的保守值，本地文件解析完头部就够：

| 版本 | 首字节中位数（5 次，测试机 192.168.5.141） |
|---|---|
| 带 `-probesize 262144 -analyzeduration 1000000` | **23 ms** |
| 不带（产品现状） | **22 ms** |

差值在噪声内，且缩短探测窗口对 APE/DSD 这类头部复杂的格式有误判风险，因此**撤回参数**，只在 `transcode_command` 里留注释说明为什么不要加。基线 `23 ms` 保留，用于发现"以后变慢了"。

> 这条写在这里是为了防止下次有人（包括我）再提一次同样的"优化"。

## 日常复核（自动化）

一条定时任务每天跑一次，只做**检查与报告**，不改代码：

1. JS 守卫：`test_ui_media_error_policy.js`、`test_ui_queue_navigation.js`、`test_ui_queue_stream.js`
2. Java 守卫：`gradlew testDebugUnitTest`（`NavigationDecisionTest` 覆盖队尾语义）
3. 首帧度量：`tools/measure_first_byte.py` 与基线比较

任一项失败即报告"哪条建议退化了"，并给出重现命令；全部通过则只报一行状态。

## P0-2 放不了的曲目（已实现，客户端自愈）

服务端已经能区分两类失败：并发槽满 → `503`、ffmpeg 起不来 → `502`。但"文件本身解不开"目前仍表现为 `200` + 空响应，改它要把响应头从"先发后读"改成"先读后发"，会影响 7 条现有转码流用例，暂不动（记为后续）。

客户端这一侧先把伤害止住：

- `media_error_policy.markUnplayable()/isUnplayable()/forgetUnplayable()`：名单上限 200，最近失败排最前；
- 播放失败即记名单，**放出来就除名**（文件被替换能自愈）；
- 自动续播时用 `nextPlayableIndex()` 跳过名单里的曲目，`循环=全部` 才回绕，全坏则停下。

## P1-2 预热下一首：量过，没收益（结论要留着）

实现过一版：换曲后用隐藏的 `audio[data-preheat]`（`preload=metadata`）打开下一首的流地址。R578 在测试机上量同一 URL 的装载耗时：

| 方式 | 装载耗时（各 2 首，ms） |
|---|---|
| 冷启动 | 603、726 |
| 先预热再装载 | 638、617 |

差值在噪声内。原因不难理解：局域网里握手本来就便宜，真正的等待在**服务端 ffmpeg 出第一帧**，客户端预热碰不到那一层。更糟的是预热会开一条转码流，和真正要播的请求**抢 ffmpeg 槽**（默认并发只有 2），极端情况下会让首播更慢。

因此撤掉实现，只留注释说明原因，并在 `test_ui_media_error_policy.js` 里加一条"不许再加回来"的断言。**曲间空档的度量保留**（R577 的 `fnAudioGapReport()`），它是 P2-1 的验收口径。

## P2-1 安卓衔接（已确认，未测）

整条队列由 `NativePlaybackBridge.setQueue` 一次性交给 `controller.setMediaItems(...)`，`PlaybackService` 没有调用 `setPauseAtEndOfMediaItems(true)`——media3 默认允许队列项之间直接衔接，同编码连续播放时不会有额外空档。守卫固定在 `test_ui_android_bridge.js`：谁把它设成 `true` 就会红。

**仍未量的**：不同容器（flac→mp3 转码流）之间的空档，需要设备侧 `ended → playing` 计时，与 P1-2 共用一个指标。

## 曲间空档怎么读（R577）

客户端已经埋好点：`audio.onended` 记时刻、`audio.onplaying` 算差，样本进 `state.gapSamples`（上限 50）。

- 浏览器控制台或 WebView 调试：`fnAudioGapReport()` → `{count, median, p95, max}`；
- 单位毫秒，`median` 是 P1-2 / P2-1 的对外口径；
- 采样满 5 条再看，单条会被首帧抖动带偏。

## 做下一件事的判据

按这个顺序取第一条**未做**的先做，做完补上"指标 + 守卫"再进表：

1. P0-2 转码错误分类（影响：坏文件会不会被反复重试）
2. P1-2 预热下一首 URL（影响：`ended → playing` 空档）
3. P2-1 安卓衔接确认（影响：曲间空档）
4. P2-2 原文件缓存（影响：断网可用性）

没写进这条链的改动，不进本计划。
