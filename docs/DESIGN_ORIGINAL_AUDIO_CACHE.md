# P2-2 设计：原文件本地缓存（断网可放）

> 结论先说：**这个能力只能落在客户端**。NAS 断网时服务端根本够不着，服务端缓存再多也救不了"断网还能放"。Audio Station 也是这么做的（`PreDownloader` + `StreamProxy` 把整曲下到手机本地）。

## 1. 要解决的问题

| 场景 | 现在 | 目标 |
|---|---|---|
| 局域网抖动 / WiFi 切换 | 播到一半就断，恢复要重连 | 已缓存曲目不受影响 |
| 完全断网 | 全部不能放 | 已缓存的仍可连续播放 |
| 重复播放同一首 | 每次都重新拉流 / 重新转码 | 命中缓存直接本地读 |

## 2. 为什么不在服务端做

服务端缓存（现在的 `transcode` 缓存）解决的是**解码成本**，不是**可达性**。断网时：

- 手机连不上 NAS → 服务端缓存命中与否都取不到；
- 所以"断网可放"必须由客户端持有音频字节。

服务端这一层不改，只是在响应头里补 `Cache-Control` / `ETag`，让客户端缓存有据可依。

## 3. 安卓端（先做这条）

media3 自带这套能力，不需要自研下载器：

```
OkHttpDataSource.Factory（现有）
  └── CacheDataSource.Factory
        ├── cache  = SimpleCache(cacheDir/media, LeastRecentlyUsedCacheEvictor(maxBytes))
        ├── upstream = 上面的 OkHttp
        └── cacheWriteDataSinkFactory = CacheDataSink.Factory
```

要点：

1. **单例**：`SimpleCache` 全进程只能开一个（否则 media3 会抛 "another SimpleCache instance"）。挂在 `PlaybackService` 的单例里，进程退出时 `release()`。
2. **只缓存整段**：请求带 `?start=` 的（中间续播、CUE 段）不写缓存，避免同一首产生大量碎片。判断方式：URL 里 `start` 缺失或为 0。
3. **配额与淘汰**：`LeastRecentlyUsedCacheEvictor`，默认 **1024 MB**，可在设置里改（256 / 512 / 1024 / 2048 / 关闭）。上限同时受"磁盘剩余 < 512MB 时不写"约束，与 `cache_min_free_bytes` 对齐。
4. **命中即离线可放**：`CacheDataSource` 命中时完全不碰网络；上游失败且命中缓存时继续播（`FLAG_IGNORE_CACHE_ON_ERROR` 不开——那个 flag 是"错就忽略缓存"，方向相反）。
5. **不缓存转码流之外的东西**：封面、歌词走各自的 LRU，不进这个 cache。

验收指标（写进计划表）：

- 断网后能连续播放的曲数 ≥ 缓存里完整的曲数；
- 二次播放同一首的网络请求字节数 ≈ 0（用 OkHttp 的 EventListener 计数）；
- 磁盘占用不超过配额（`SimpleCache` 目录 size 检查）。

## 4. 浏览器端（后做，风险高）

浏览器要"断网可放"只有两条路，都不轻：

| 方案 | 代价 |
|---|---|
| Service Worker 缓存 `?transcode=` 响应 | 需要处理 Range 请求、缓存键含 start、页面刷新后 SW 生命周期，容易变成"缓存了但放不出来" |
| 播放前整段 `fetch` 进 Cache Storage，播放走 blob URL | 大文件占内存、切歌延迟变大 |

判断：**先不做**。桌面端断网播放的价值低于安卓（安卓是移动场景，WiFi/4G 切换频繁）。若要做，只做"整首下完才入缓存"这一条，宁可慢也不出半截音频。

## 5. 与服务端转码缓存的关系

两者不重复：

| 缓存 | 内容 | 解决 |
|---|---|---|
| 服务端 `transcode` | mp3/wav/flac 转码产物 | 解码 CPU、首帧 |
| 客户端 `SimpleCache` | 实际下载到的字节（多为转码流） | 可达性、重复流量 |

副作用要接受：同一首歌在 NAS 上留一份转码产物、手机上留一份字节，空间各算各的。设置页要把两处的用量分别显示，别让用户以为"清了一次就都清了"。

## 6. 落地顺序

1. （已完成）`CacheDataSource` 接线 + 单例 + 配额设置项；
2. 断网验证：先在模拟器上用 `adb shell svc wifi disable` 跑；
3. 指标接入 `docs/PERF_STABILITY_PLAN.md` 的 P2-2 行；
4. 浏览器端另开一轮，先做设计评审再动手。

## 7. 不做的事（明确边界）

- 不做"整库离线下载"（那是另一个产品功能，需要任务队列、进度、空间预估）；
- 不做缓存加密（音频本来就在 NAS 上明文，加密只增加 CPU）；
- 不跨设备共享缓存（断网场景下没有共享的意义）。
