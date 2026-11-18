# Audio Station 的标签、封面、歌词与 CUE：逆向分析 + 与 fnAudio 的差异

> 结论先行：**四块里 fnAudio 领先两块半（封面缓存、CUE 解析、歌词精度），落后半块（标签模型），另有一处真缺陷（编码判定）。** 标签上 AS 是「九字段 + 只读」，fnAudio 是「六字段 + 可写回」——写回能力是我们的优势，但六字段里 `album_artist` 被折叠进了 `artist`，合辑与原声带的专辑艺术家因此丢失；CUE 与 LRC 的编码回退链在 `gb18030` 之后放 `big5` 是无效的（`gb18030` 几乎不会抛错，实测 Big5 的「晴天」解成「锤ぱ」）；专辑封面取 `MIN(id)` 而不是「第一首真有封面的」，会让部分专辑整张没封面。歌词面板缺一条 AS 有的交互：用户手动滚动后暂停自动跟随。反过来，AS 的封面缓存键、投送时间补偿、永久负缓存三处**不值得借鉴**。

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `Android-DSaudio.3.16.0-547.cn.apk` | 已反编译，10554 个 `.java`，`com.synology.p000dsaudio` 624 个类 | **可逐行验证**（A 档：类名 + 行号） |
| `AudioStation-x86_64-7.0.3-5401.spk` | 加密容器（头 `42 AD BE EF` + `c0 20 00 00` 长度域，内嵌三处 `1f 8b 08` 全部 `zlib.error`，无 `ustar`/`PK`/`hsqs` 签名） | 服务端标签/封面/歌词/CUE 实现**取不出**，只能由契约反推（B 档） |
| fnAudio 源码 | 本仓库 | 可逐行核对 |

因此下文分两档：**A 档**给类名/行号；**B 档**逐条标注「推断」。凡涉及「服务端怎么读标签、怎么合成封面、怎么展开 CUE」的地方，一律不给确定结论。

本文只覆盖四块：**标签、封面、歌词、CUE**。库模型、播放队列、音频引擎分别在 `ANALYSIS_LIBRARY_INDEX_VS_DS_AUDIO.md`、`ANALYSIS_PLAYER_QUEUE_VS_DS_AUDIO.md`、`ANALYSIS_AUDIO_ENGINE_VS_DS_AUDIO.md`。

---

## 1. 标签

### 1.1 AS 的标签模型：九字段，分三段附加

曲目记录里 `title` 在顶层，其余标签按 `additional=song_tag,song_audio,song_rating` 分三段下发（`item/SongItem.java:24-46`）：

```json
{ "title":"...",
  "additional": {
    "song_tag":   { "artist","album","composer","genre","album_artist","comment","disc","track","year" },
    "song_audio": { "duration","frequency","channel","bitrate","codec","container","filesize" },
    "song_rating":{ "rating" }
  } }
```

客户端把这九项全部落进本地 SQLite（`item/SongItem.java:402` 的建表语句）：

```
id, dsid, songid, title, artist, album, composer, genre, album_artist,
path, duration, filesize, bitrate, channel, frequency, cache_path,
timestamp, hit_count, cover_path, lyric_path, disc, track, year, comment,
cache_bitrate, rating, download_type
```

**`cover_path` 与 `lyric_path` 是两列独立字段**——这说明「封面」和「歌词」在 AS 里都是**可落盘的一等对象**，不是每次现取。`timestamp` 是加入时间（服务端排序键，与库分析里那条「加入时间不下发」一致），`hit_count` 是播放次数。

`bit_depth` 仍然缺席（只有 `frequency`/`bitrate`/`channel`），与库分析结论一致——客户端判「高解析」只能靠频率阈值。

### 1.2 移动端**只读**：整个 APK 里没有任何写标签的 API

把客户端用到的 AS 命名空间全部列出来：

| 命名空间 | 次数 | 命名空间 | 次数 |
|---|---|---|---|
| `Playlist` | 41 | `Radio` | 10 |
| `Song` | 23 | `Album` | 8 |
| `Pin` | 17 | `Stream` | 7 |
| `RemotePlayer` | 14 | `RemotePlayerStatus` | 5 |
| `Proxy` | 13 | `Folder` | 5 |
| `Info` | 13 | `LyricsSearch` | 4 |
| `Cover` | 13 | `Lyrics` | 4 |
| `Genre` / `Artist` / `Composer` | 3 / 3 / 2 | | |

**没有 `Tag`、没有 `Metadata`、没有 `set_song_tag`。** `SYNO.AudioStation.Song` 只用到五个方法：`list`、`search`、`getinfo`、`setrating`、`setsharing`。

结论（A 档）：**AS 移动端对标签是完全只读的**。标签编辑只存在于 DSM 网页端。这一条是 fnAudio 的**结构性优势**——`metadata_service.py` + `metadata_candidate_*` 那一整套「候选 → 确认 → 写回」在 AS 的移动端没有对应物。

### 1.3 缺省值：桌面给「未知」，手机给空

`playing/PlayingSongDetailHelper.java:100-125`：

```java
if (songItem.getArtist().length() == 0) {
    setTextIfNeeded(mArtistText, isMobileLayout() ? "" : this.unknownArtist);
} else {
    String artist = songItem.getArtist();
    if (this.mIsForPhone) {                       // 手机把 artist / composer 合并成一行
        String composer = songItem.getComposer();
        if (TextUtils.isEmpty(artist)) artist = composer;
        else if (!TextUtils.isEmpty(composer)) artist = artist + " / " + composer;
    }
    setTextIfNeeded(mArtistText, artist);
}
if (songItem.getAlbum().length() == 0) {
    setTextIfNeeded(mAlbumText, isMobileLayout() ? "" : this.unknownAlbum);
}
```

两个细节值得记：

1. **同一份数据在手机与桌面用两套缺省策略**——手机上「未知艺术家」占掉整整一行却没有信息量，所以直接给空；桌面上给占位符。
2. **手机上 artist 行塞两个字段**（`artist / composer`，artist 为空时退成 composer）。这是空间紧张时的信息密度技巧，与播放条那类「一列只放一件事」的约束正好互补。

### 1.4 fnAudio 的现状：六字段，`album_artist` 被折叠掉

`app/server/metadata_text.py:84-116` 的归一化表只有六个字段：

```python
aliases = {
    "title":     ("title", "tit2", "©nam"),
    "artist":    ("artist", "artists", "album_artist", "albumartist",
                  "performer", "performers", "author", "tpe1", "©art"),
    "album":     ("album", "talb", "©alb"),
    "composer":  ("composer", "composers", "tcom", "©wrt"),
    "genre":     ("genre", "genres", "tcon", "©gen"),
    "track_no":  ("track", "tracknumber", "track_number", "trck", "trkn",
                  "©trk", "tracknum", "disktrack"),
}
```

**`album_artist` / `albumartist` 被放进了 `artist` 的别名表。** 于是：

- 一首曲目若同时有 `ARTIST=周杰伦` 与 `ALBUMARTIST=群星`，取到哪个**取决于字典遍历顺序**（别名表里 `artist` 先于 `album_artist`，所以有 `artist` 就用 `artist`；只有 `album_artist` 时才回落）；
- **永远不会产出 `album_artist` 这个键**。

而 `tracks` 表里**确实有 `album_artist` 列**（`app/server/library.py:2684`），专辑分组也确实按它优先（`library.py:1875`）：

```sql
COALESCE(NULLIF(MIN(NULLIF(s.album_artist, '')), ''),
         NULLIF(MIN(NULLIF(s.artist, '')), ''), ?)   -- 专辑艺术家
```

但非 CUE 路径上这一列**永远是空字符串**——全仓只有 `cue_parser.py:151` 会产出 `album_artist`。所以上面的 `COALESCE` 对所有普通音频文件都退化成 `MIN(s.artist)`。

**这就是一个可观测的缺陷**：一张十位不同歌手的合辑，专辑列表里的艺术家会是这十个人里字典序最小的那一个，而不是 `ALBUMARTIST=群星`。原声带、合集、`Various Artists` 全都命中。

### 1.5 字段对齐与差异

| 字段 | AS | fnAudio | 说明 |
|---|---|---|---|
| `title` | 顶层 | ✅ `title` | |
| `artist` | `song_tag.artist` | ✅ `artist` | fnAudio 把 `album_artist` 也塞进这里 |
| `album` | ✅ | ✅ | |
| `composer` | ✅ | ✅ | |
| `genre` | ✅ | ✅ | |
| `track` | ✅ `track` | ✅ `track_no` | |
| **`album_artist`** | ✅ 独立字段 | ⚠️ 有列、无值 | **缺陷**：合辑/原声带的专辑艺术家丢失 |
| **`disc`** | ✅ | ❌ 无列 | 多碟专辑排序会错：第 2 碟第 1 首排在第 1 碟第 2 首前面 |
| **`year`** | ✅ | ❌ 无列 | 无法显示/按年代排序 |
| `comment` | ✅ | ❌ | 价值低 |
| `bit_depth` | ❌ | ✅ `bit_depth` | fnAudio 更好 |
| 写回/补全 | ❌ 移动端只读 | ✅ 候选 + 确认 + 写回 | fnAudio 更好 |

### 1.6 值得借鉴

**P1（真缺陷）**：`album_artist` 独立出来。改动面比看起来小——列已经在表里，专辑分组的 SQL 已经优先用它，缺的只是归一化表加一项、`scan` 的插入列表加一个字段。守卫可以直接钉「合辑的 `albums.artist` 等于 `ALBUMARTIST` 而不是某个 track artist」。

**P2**：`disc`。多碟专辑在古典与现场专辑里很常见，排序错位是肉眼可见的。需要加列 + 排序键里插在 `track_no` 之前 + 迁移。

**P3**：`year`。纯展示，成本最低。

---

## 2. 封面

### 2.1 AS：服务端合成，客户端按 `MD5(bundle)` 落盘

三个端点（`ApiEnumerator.java:725-790`）：

| 场景 | method | 参数 |
|---|---|---|
| 专辑 / 歌手 / 类型 / 作曲者 | `getcover` | `album_name`、`artist_name`、`genre_name`、`composer_name`、`album_artist_name` |
| 文件夹 | `getfoldercover` | `id` |
| 单曲 | `getsongcover` | `id` |

容器封面在客户端的落盘名是 **`MD5(bundle.toString())`**（`ApiEnumerator.java:729`）——以「查询条件」为键，所以整张专辑共用一份。单曲封面走 `SongItem.getUniqueKey()`。

**代价很直接**：标签一改，`MD5(bundle)` 不变，旧文件既不会被复用也不会被清（只能靠 `clearBrowsableCache` 扫前缀）。这是**没有失效机制的缓存**。

### 2.2 fnAudio：尺寸感知 + 内容版本键 + 负缓存

`app/server/cover_cache.py` 做得比 AS 细：

- `ALLOWED_SIZES = (160, 512)`，请求尺寸按最近档归一（`:203-212`）；
- 缓存键是 **`(item 身份, size, 内容版本)`** 三元组（`:275-294`），`cover_source_version()` 把媒体修改版本带进键里——**文件一改，键就变，旧条目自然不再命中**；
- 无封面时写 `<key>.none` 标记（`:294`），即**负缓存**，避免反复对同一张没封面的曲目跑 ffmpeg。

这三条都比 AS 强，不需要向 AS 学。

### 2.3 fnAudio 的缺口：专辑封面取 `MIN(id)`

`app/server/library.py:1877`：

```sql
SELECT s.group_name AS name, %s AS artist, COUNT(*) AS track_count,
       MIN(s.id) AS cover_track_id
```

`cover_track_id` 是**专辑里 id 字典序最小的那一首**，不是「第一首真有封面的」。而封面是「按那首曲目去读」的（`read_cover_for_item` → 内嵌 → 同名 sidecar）。所以：

- 若 `MIN(id)` 那首没有内嵌图、且目录里没有 `cover.jpg`，**整张专辑就没有封面**——即使同一张专辑的其它曲目有内嵌图；
- 同名 sidecar 的存在会掩盖这个问题（同目录都有 `cover.jpg`），所以它只在「封面逐曲内嵌、且不全」的专辑上发作——合辑与杂拼专辑正是这种。

AS 的 `getcover(album_name, artist_name)` 由服务端按专辑去找，**推断**（B 档）服务端会扫该专辑的曲目直到找到一张，所以不会有这个洞。

### 2.4 值得借鉴

**P2**：`cover_track_id` 从 `MIN(s.id)` 改成「专辑内第一首有封面的曲目」。难点是扫描期就要知道谁有封面——但扫描时 `read_cover_for_item` 本来就会跑（封面是懒取的，所以更准确的说法是：在**首次取专辑封面失败时**回落到同专辑其它曲目，并把命中的那首记回 `cover_track_id`）。这样不需要改扫描期成本。

---

## 3. 歌词

### 3.1 AS 客户端：三级瀑布 + 永久负缓存

`CacheManager.doEnumLyrics()`（`CacheManager.java:1000-1044`）是一条很清楚的瀑布：

```java
String lyricPath = songItem.getLyricPath();
File file = new File(lyricPath);
if (!TextUtils.isEmpty(lyricPath) && file.exists()) return getJsonObjectFromFile(file);   // ① 本地缓存

String str = Common.getLyricFolder() + songItem.getUniqueKey();
File file2 = new File(str);
netMgr.doEnumLyrics(str, songItem.getID());                                              // ② 服务端随曲歌词
JSONObject o = getJsonObjectFromFile(file2);
if (API 连接 && o.optJSONObject("data").optString("lyrics","").isEmpty())
    ((ApiEnumerator) netMgr).doSearchLyrics(str, songItem);                              // ③ 在线搜索
if (file2.exists()) DatabaseAccesser.addLyric(songItem, str);                            // ④ 路径写回 SQLite
```

三个关键点：

1. **缓存键 `getUniqueKey() = MD5(dsId + id + path)`**（`item/SongItem.java:643-645`）。把 `path` 也放进去，意味着**文件被替换/移动后缓存自然失效**——比纯 id 键好。这一条**值得借鉴**（见 §3.5）。
2. **在线搜索只在「服务端返回的 `data.lyrics` 为空」且「连接类型是 API」时触发**，参数只有 `artist` + `title` + `limit=1` + `additional=full_lyrics`（`ApiEnumerator.java:899-915`）。
3. **负缓存是永久的**：`downloadStream` 把响应（哪怕是「没有歌词」）写进 `file2`，`file2.exists()` 为真就把路径写进 `lyric_path`。下次打开 → ① 直接命中 → **永远不会再问服务端**。用户在 NAS 上补了一个 `.lrc`，客户端仍然显示「无歌词」。这是 AS 的一处真实缺陷，**不值得借鉴**。

### 3.2 AS 的 LRC 解析器（`util/LyricUtils.java`）

`extractDynamicLyric()`（`:12-36`）+ `fromTimeString()`（`:45-63`）+ `getLyricItems()`（`:65-79`）+ `getOffset()`（`:81-89`）：

```java
// 一行多个时间戳 → 展开成多条
Matcher matcher = Pattern.compile("\\[.+?\\]", 2).matcher(str);
while (matcher.find()) {
    long t = fromTimeString(matcher.group());
    if (-1 != t) items.add(new LyricItem(t - offset, textWithoutTags));
}
// [mm:ss] 与 [mm:ss.xx] 都接受；没有小数点时毫秒记为 "0"
int dot = s.lastIndexOf(".");
fraction = (dot >= 0) ? s.substring(dot + 1) : "0";
// [offset:N] 只在该行不含时间戳时才被读入，并对后续所有行整体偏移
private static int getOffset(String line) {
    if (line.startsWith("[offset:")) return Integer.parseInt(line.substring(8, line.length() - 1));
    return 0;
}
```

设计上做对的地方：

- **`[mm:ss]` 无小数也接受**（毫秒记 0）——大量 LRC 就是这种形态；
- **一行多时间戳展开成多条**（`[00:12][01:30]同一句`）；
- **`[offset:]` 支持**，且偏移作用于其后所有行——卡拉 OK 场景常见；
- 解析失败返回 `-1` 由调用方跳过，**从不抛**。

一处明确的缺陷：

```java
strSubstring = s.substring(dot + 1);          // 毫秒位按整数读
```

**`[00:12.5]` 会被读成 5 毫秒，而不是 500 毫秒**——慢 495 ms。只有两位小数（`.50`）才是对的。`[00:12:30]`（老式「分:秒:帧」）会因为 `Integer.parseInt("12:30")` 抛 `NumberFormatException` → 返回 `-1` → **整行被丢弃**。

### 3.3 AS 的渲染（`widget/DynamicLyricListView.java`）

`setSelection(long time)`（`:135-170`）里有四条值得记的判断：

```java
private static final int TIME_SHIFT_REMOTE_MODE = 1000;   // 投送模式整体后移 1 秒
private static final long UNLOCK_SCROLL_DELAY = 3000;     // 手动滚动后 3 秒恢复自动跟随

long j2 = j + (Common.isPlayModeRenderer() ? 1000L : 0L);
while (mSelPos < size - 1 && mTimeList.get(mSelPos + 1) < j2) mSelPos++;   // 前进
while (mSelPos >= 0 && mTimeList.get(mSelPos) > j2) mSelPos--;             // 倒退
...
if (isLockScroll || !checkOutOfRange(mSelPos)) return;                     // 用户正在翻 → 不抢
smoothScrollToPositionFromTop(mSelPos + 1, getHeight() / 2);               // 下一行滚到屏幕中间
```

1. **增量游标而不是二分**：`mSelPos` 记住上一次位置，两个 `while` 分别处理前进与倒退。播放时时间单调递增，所以几乎总是 O(1)。
2. **`checkOutOfRange()`**（`:66-83`）：目标行已经在可视区上方 30% 以内就**不滚**（`f < 0.3` 返回 false）。避免每换一行都触发一次滚动动画。
3. **`isLockScroll`**：`onScrollStateChanged` 收到 `SCROLL_STATE_TOUCH_SCROLL` 就锁定，回到 `IDLE` 后**延时 3 秒**解锁。用户翻歌词时不会被自动滚动拽回去。
4. **投送模式 +1000 ms**：远端播放的位置回报有延迟，整体后移 1 秒对齐。

### 3.4 fnAudio 的现状

解析器 `app/ui/lyrics_parse_policy.js:3-15`：

```js
const matches = [...line.matchAll(/\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g)];
const content = line.replace(/\[[^\]]+\]/g, "").trim();
if (!content) return;
if (!matches.length) { rows.push({ time: -1, text: content }); return; }
matches.forEach(m => rows.push({
  time: Number(m[1]) * 60 + Number(m[2]) + Number(`0.${m[3] || 0}`), text: content }));
```

- **小数精度是对的**：`0.${digits}` 让 `.5` = 0.5 s、`.50` = 0.5 s、`.500` = 0.5 s，**比 AS 的一位小数读法正确**；
- 一行多时间戳展开 ✅；
- 删掉所有 `[...]` 取正文 ✅；
- **没有 `[offset:]`** ❌；
- 无时间戳的行保留为 `time: -1`（AS 的动态视图会丢掉它们，纯文本视图保留）。

歌词来源 `app/server/metadata_service.py:2228-2247`：**内嵌（ffprobe）→ 同名 `.lrc` → 同目录 `lyrics.lrc`**，编码 `utf-8-sig` → `utf-16` → `gb18030`。

高亮投影 `app/ui/app.js:6737-6763`：

```js
let active = -1;
state.lyrics.forEach((line, i) => { if (line.time >= 0 && line.time <= now + 0.25) active = i; });
if (active === state.lyricsActiveLine) return;              // 每个 tick 都重算，但只有换行才重绘
...
lyricBox.scrollTo({ top: activeNode.offsetTop - h/2 + lineH/2, behavior: "smooth" });
```

- 有 **+0.25 s 前瞻**（字幕略早于人声）；
- 有「换行才重绘」的门，避免每 tick 重启滚动动画；
- **每次换行都居中滚动**，没有「目标行已在可视区就不滚」；
- **没有「用户手动滚动后暂停跟随」**。

### 3.5 差异与值得借鉴

| 能力 | AS | fnAudio |
|---|---|---|
| 小数精度 | ⚠️ 一位小数当毫秒 | ✅ 1–3 位都对 |
| `[mm:ss]` 无小数 | ✅ | ✅ |
| 一行多时间戳 | ✅ | ✅ |
| `[offset:]` | ✅ | ❌ |
| `[mm:ss:ff]` | ❌ 丢行 | ❌ 丢行 |
| 内嵌歌词 | B 档（服务端） | ✅ ffprobe，键覆盖 `USLT`/`©lyr`/`lyrics_*` |
| 同名 `.lrc` | B 档（服务端） | ✅ |
| 在线搜索 | ✅ `artist+title, limit=1` | ✅ 元数据 provider 体系 |
| 负缓存 | ❌ 永久（错） | ✅ 15 次后停 + 手动 `retry=1` |
| 手动滚动锁 | ✅ 3 秒 | ❌ |
| 投送时间补偿 | ⚠️ 硬编码 +1000 ms | ✅ 外推（`transportExtrapolation`） |

**值得借鉴（按性价比）**

**P1 `[offset:]`**。改 `lyrics_parse_policy.js` 一处：扫到 `[offset:N]` 时记下偏移，后续行的 `time` 统一减 `N/1000`。守卫直接钉「`[offset:500]` 之后的行整体前移 0.5 s」与「offset 只影响其后」。这是卡拉 OK 场景里最常见的元数据，而我们目前把它当正文删掉了。

**P2 手动滚动后暂停自动跟随**。`updateLyricHighlight` 里加一个 `state.lyricsUserScrollAt`：`lyricsLines` 的 `scroll` 事件若不是本函数触发的（用一个标志位区分），就记时间戳；3 秒内不自动滚。这条比 AS 的原版更容易做——网页的 `scroll` 事件是同步的，不需要 `OnScrollListener` 那套状态机。

**P3 目标行已在可视区就不滚**。省掉「行高相近时每次只挪一点点、动画不断重启」的抖动。

**不借鉴**

- **`+1000 ms` 投送补偿**：fnAudio 的 `currentSeconds()`（`app.js:5960-5979`）已经用 `transportExtrapolation` 按快照时间外推，比硬编码 1 秒准得多；
- **永久负缓存**：见 §3.1；
- **一位小数当毫秒**：AS 的解析缺陷。

---

## 4. CUE

### 4.1 AS：客户端零 CUE 概念

全树搜索 `.cue` / `CueSheet` / `cue_file` / `cuesplit`，**`com.synology.p000dsaudio` 下 0 处引用**；`values*/strings.xml` 里也没有任何 CUE 相关字符串（英文与 `zh-rCN`/`zh-rHK`/`zh-rTW` 全查过）。

所以只有两种可能：**要么服务端把 CUE 展开成普通曲目下发，要么 AS 根本不支持 CUE。** 加密容器打不开，无法判定（B 档）。

有一条间接证据偏向「服务端展开」：`getUniqueKey() = MD5(dsId + id + path)`（§3.1）。如果 CUE 分轨是「同一个 `path`、不同 `id`」下发，那么**缓存键必须同时含 `id` 和 `path` 才不会让同一文件的多轨撞键**——这个键的形状正好是这个需求的解。反过来说，若 AS 不分轨，`id` 已经唯一，`path` 是冗余的。

**推断（B 档）**：AS 服务端把 CUE 展开成「同 path、不同 id、不同 duration」的曲目，客户端无感知。

### 4.2 fnAudio 的 CUE：成熟度高于 AS 能验证到的程度

`app/server/cue_parser.py` + `cue_reader.py` + `library.py:708-762`：

- **`INDEX 01` 才是起点**，`INDEX 00`（pregap）与更大的索引号都不移动起点；
- **重复的 `INDEX 01` 以第一次为准**（`index01_seen` 标志，`:104`/`:145`）——制版留下的重复索引不会把起点改掉；
- **轨道结束三态**（`:19-80`）：正数＝同一文件上后一首的起点；`0.0`＝没有后一首，用文件时长；`None`＝有后一首但起点不更靠后（并列或乱序），边界未知。把第三态折进第二态曾经让 `cue_end` 变成整文件时长；
- **单遍单调栈**算轨道结束，不是嵌套扫描——`MAX_CUE_LINES = 20000` 与 4096 字符行上限挡住了「一个恶意 CUE 让索引卡几秒」；
- **整轨文件被隐藏**：`library.py:843` 的 `if os.path.abspath(full) in cue_audio_paths: continue`——不会同时出现 `album.ape` 与它拆出的 12 首；
- **多文件 CUE** 按 `FILE` 分组，每首各自算结束；
- **CUE 曲目继承源文件标签**（`:744-747`），CUE 里的 `TITLE`/`PERFORMER` 覆盖之，`metadata_source` 标成 `cue`。

这些在 AS 侧**一条都无法验证**（服务端加密）。就离线可验证的部分而言，fnAudio 的 CUE 处理是完整的。

### 4.3 真缺陷：编码回退链在 `gb18030` 之后放 `big5` 是无效的

`app/server/cue_reader.py:19`：

```python
for encoding in ("utf-8-sig", "gb18030", "big5", "latin1"):
    try:
        return payload.decode(encoding).splitlines()
    except UnicodeError:
        continue
```

**`gb18030` 几乎不会抛 `UnicodeError`**——它覆盖 1/2/4 字节，绝大多数字节对都能解出某个码位。于是 `big5` 这一档**永远不会被执行到**，`latin1` 更是恒成功（所以这个函数实际上从不返回 `[]`）。

实测：

```
big5       utf-8-sig  fail
big5       gb18030    OK  'TITLE "锤ぱ"'        ← 原文是「晴天」
shift_jis  utf-8-sig  fail
shift_jis  gb18030    OK  'TITLE "栭偵嬱偗傞"'  ← 原文是「夜に駆ける」
```

一个 Big5 的 CUE（港台用户的常见形态）会被静默解成乱码，而且**没有任何错误信号**——用户看到的是曲名变成「锤ぱ」，而不是「编码不支持」。

歌词侧更窄：`metadata_service.py:2241` 只有 `utf-8-sig` / `utf-16` / `gb18030`，**连 `big5` 都没有**，繁体中文的 `.lrc` 一样会变成乱码。

### 4.4 其他缺口

- **`PREGAP` / `POSTGAP` 未处理**：带 `PREGAP 00:02:00` 的轨道起点应当早 2 秒。实际少见，且「pregap 归前一首」也是主流约定，可以不改。
- **无 `INDEX 01` 的 CUE**（只有 `TRACK` + `TITLE`）：所有 `start` 都是 `0.0`，`_attach_track_ends` 判成并列 → `end = None` → 每轨 `duration = 0`。结果是 N 首零长度曲目。建议：这种 sheet 直接**不展开**（退回把整轨当一个文件），比给出 N 个 0 秒条目更好。
- **`FLAGS` / `CATALOG` / `ISRC` / `REM`** 未读。对播放无影响；`REM DISCID` 若将来接 MusicBrainz 会有用。

### 4.5 值得借鉴

**P1 编码判定改成「打分」而不是「第一个不抛错」**。这是本轮最值得做的一条：

- 对每个候选编码解码，给结果打分：命中 CJK 统一表意区（`4E00–9FFF`）加分；出现半角片假名（`FF61–FF9F`）与中文混排、CJK 扩展区（`3400–4DBF`、`20000+`）罕见字、私用区（`E000–F8FF`）大幅减分；控制字符减分；
- 取分最高者；**都不像话就返回空**（让调用方退回整轨，而不是给出乱码曲名）；
- 加一个**按库的显式编码设置**作为最高优先（`utf-8` / `gb18030` / `big5` / `shift_jis` / 自动），默认「自动」。AS 服务端是否提供同类设置无法验证（B 档），但这是解决同一问题的标准做法。

守卫可以很硬：把 `晴天` 的 Big5 字节、`夜に駆ける` 的 Shift-JIS 字节、GBK 的 `晴天` 字节做成三组 fixture，断言解出的文本分别等于原字面——现在这三组里有两组是红的。

---

## 5. 汇总：值得借鉴的清单

| 优先级 | 项 | 位置 | 代价 | 收益 | 可钉的守卫 |
|---|---|---|---|---|---|
| **P1** | CUE/LRC 编码打分 + 可选显式编码 | `cue_reader.py:19`、`metadata_service.py:2241` | 中 | 港台/日文 CUE 与 LRC 不再乱码 | 三组字节 fixture 解出原字面 |
| **P1** | `album_artist` 独立成字段 | `metadata_text.py:86-93` | 小 | 合辑/原声带的专辑艺术家不再丢失 | 合辑的 `albums.artist` == `ALBUMARTIST` |
| **P2** | 歌词 `[offset:]` | `lyrics_parse_policy.js:3-15` | 小 | 卡拉 OK 歌词对齐 | `[offset:500]` 之后整体前移 0.5 s |
| **P2** | 专辑封面回落到同专辑其它曲目 | `library.py:1877` | 小 | 逐曲内嵌封面不全的专辑不再整张空白 | 首曲无封面、次曲有 → 专辑有封面 |
| **P2** | 歌词面板手动滚动锁 3 秒 | `app.js:6737-6763` | 小 | 翻歌词时不被拽回 | 模拟 scroll 后 3 s 内不自动滚 |
| **P2** | `disc` 字段 | `library.py:2675-2705` | 中 | 多碟专辑排序正确 | 碟 2 曲 1 排在碟 1 曲 2 之后 |
| **P3** | 目标行已在可视区就不滚 | `app.js:6759-6762` | 小 | 少抖动 | — |
| **P3** | `year` 字段 | 同上 | 小 | 可显示/排序 | — |
| **P3** | 无 `INDEX 01` 的 CUE 不展开 | `cue_parser.py` | 小 | 不再产出 N 首 0 秒曲目 | 该 sheet 展开结果为 0 条 |
| **P3** | `comment` 字段 | — | 小 | 价值低 | — |

## 6. 不借鉴：写下来防止回流（已裁定）

> **2026-11-18 负责人裁定：这六条不再借鉴、不再排期、不再复核。** 它们都是 AS 里「看起来能抄」但抄了会更差的
> 做法，记在这里是为了下次别再提——不是待办，也不是「以后有空再说」。R591 落地十条时已按此裁定跳过，`TODO.md`
> 的 R592 条目是本裁定的账本记录。

| AS 的做法 | 为什么不借鉴 |
|---|---|
| 封面缓存键 `MD5(bundle)` | 无失效机制：标签一改，旧文件既不复用也不清理。fnAudio 的 `(身份, size, 版本)` 三元组更好 |
| 歌词/封面**永久**负缓存 | 用户在 NAS 上补了 `.lrc` 后客户端永远显示「无歌词」。fnAudio 的「15 次后停 + 手动 retry」更稳 |
| 投送模式 `+1000 ms` 硬补偿 | fnAudio 已用 `transportExtrapolation` 按快照外推，比硬编码准 |
| 一位小数当毫秒 | 解析缺陷，`[00:12.5]` 会慢 495 ms |
| 移动端标签只读 | 这是 fnAudio 的结构性优势（候选 + 确认 + 写回），不是要补的洞 |
| 手机端「未知艺术家」给空串 | fnAudio 的 `library_metadata_presentation` 已按场景决定占位符；这一条只是提醒「同一份数据两套缺省策略」是合理设计，不必照搬 |

六条一律**不做**，且不再进入任何计划。真要继续往 AS 那边看，只有「换一个还没分析过的面」这一条路——同一块里剩下的做法都已经在上面这张表里了。

---

## 7. 一句话对比

| 维度 | AS | fnAudio |
|---|---|---|
| 标签 | 九字段、只读、缺省值分端 | 六字段、可写回、`album_artist` 丢失、无 `disc`/`year` |
| 封面 | 服务端合成、客户端 `MD5(bundle)` 缓存、无失效 | 内嵌→sidecar、尺寸感知、内容版本键、负缓存；专辑封面取 `MIN(id)` 有洞 |
| 歌词 | 三级瀑布、永久负缓存、`[offset:]`、手动滚动锁、一位小数有缺陷 | 内嵌→`.lrc`→`lyrics.lrc`、精度正确、无 `[offset:]`、无滚动锁 |
| CUE | 客户端零概念，服务端实现不可验证 | 完整解析、三态边界、隐藏整轨、编码回退链失效 |

**如果只做两件事**：修编码判定（P1），把 `album_artist` 独立出来（P1）。这两条都在「用户能直接看见」的层面，且守卫都能写得很硬。

---

## 8. 落地记录（R591）

十条「值得借鉴」已全部落地，另有两条在实现时按实际情况调整了口径。

| 项 | 状态 | 落点 |
|---|---|---|
| P1 编码判定打分 | ✅ | 新增 `src/app/server/text_encoding_policy.py`；`cue_reader.py`、`metadata_service.read_local_lyrics` 改走它；`/api/config/library` 接受 `text_encoding`，`library_status()` 回传；设置页「音乐目录」组一个下拉 |
| P1 `album_artist` 独立 | ✅ | `metadata_text.normalize_probe_tags`；`tracks` 表本来就有这一列，缺的是有人往里写 |
| P2 歌词 `[offset:]` | ✅ | `src/app/ui/lyrics_parse_policy.js` |
| P2 专辑封面回落 | ✅ | `library.album_cover_fallback_paths()` + `server.read_cover_with_album_fallback()` |
| P2 歌词滚动锁 | ✅ | `app.js` 的 `ensureLyricScrollIntentTracking()` + `LYRICS_SCROLL_LOCK_MS = 3000` |
| P2 `disc` | ✅ | `tracks.disc_no` + `library_write.track_sort_value()` + `TRACK_SORT_COLUMNS["track_no"]` |
| P3 中段不滚 | ✅ | `app.js` 的 `updateLyricHighlight` |
| P3 `year` | ✅ | `tracks.year`，由 `date` 投影（`metadata_text.parse_year`） |
| P3 无 `INDEX 01` 的 CUE 不展开 | ✅ | `cue_parser.parse_cue_structure` 回传 `has_index`，`library.parse_cue_tracks` 读它 |
| P3 `comment` | ✅ | `tracks.comment` |

**实现时改掉的两处口径**

1. **`[offset:]` 的符号与 AS 相反。** 本文 §3.2 记录 AS 是 `time - offset`；实现按 LRC 标签本身的约定（"`+` shifts time up"，即正数让该行更晚出现）取 `time + offset`，因为 `.lrc` 文件是照着这个约定写的。同一个文件在两边会差 `2*offset`，`tests/test_ui_lyrics_parse_policy.js` 把符号钉住了，改动必须是有意的。

2. **自动检测在 GBK 与 Big5 之间仍然不可靠，这一条没有被「修好」，而是被绕开了。** 没有统计模型时，两个字的样本在两种编码下都能解出「合法」文本（「晴天」的 Big5 字节按 GBK 解就是「锤ぱ」），这不是实现缺陷而是信息不足。所以真正的解法是显式设置：`text_encoding` 只要解出来还算像话就优先于启发式，解成胡话（半角假名、私用区、控制字符）才回落。打分能可靠处理的是**真实长度**的 CUE——`PERFORMER "周杰倫樂團"` 里的繁体专属字会把 Big5 一档顶上去，`TITLE "夜に駆ける"` 的假名会把 Shift-JIS 顶上去，`周杰伦乐队` 的简体字会把 GBK 顶上去；这三组都在 `tests/test_text_encoding_policy.py` 里。

**顺手修掉的一处漂移**

`tools/benchmark_large_library.py` 的 `EXPLAIN QUERY PLAN` 自己手写了一份 ORDER BY，和 `TRACK_SORT_COLUMNS` 是两处独立维护的字符串。R591 改了 `track_no` 的表达式之后，基准脚本仍拿旧表达式去问计划，于是把一条**实际仍走索引**的查询报成了 `SCAN tracks` + `TEMP B-TREE`——基准测的是它自己那份过期副本。现在它读 `parse_library_page_query(...).sql_order_by`，两边不可能再分开。
