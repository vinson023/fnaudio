# Audio Station 的音乐库与媒体索引：逆向分析 + 与 fnAudio 的差异

> 结论先行：**Audio Station 的库是"服务端索引 + 客户端薄壳"——全库只存在于 NAS，客户端按 1024 一页取、页缓存无 TTL 无失效、离线库只是"已下载子集"。fnAudio 的库是"本地 SQLite 索引 + 事件驱动刷新"——全库在 NAS 本地、按签名增量重扫、keyset 分页、FTS 检索。两者不是同一类系统：前者靠服务端聚合能力取胜，后者靠索引自持与可观测性取胜。**

## 0. 方法与边界（先声明可信度）

| 材料 | 状态 | 可用程度 |
|---|---|---|
| `Android-DSaudio.3.16.0-547.cn.apk` | 已反编译，10554 个 `.java`，`com.synology.p000dsaudio` 624 个类 | **可逐行验证**（API 契约、客户端缓存、离线 DB） |
| `AudioStation-x86_64-7.0.3-5401.spk` | 加密容器（魔数 `42 AD BE EF`，无 zip/tar 签名） | 服务端索引**取不出**，只能由请求/响应形状反推 |
| fnAudio 源码 | 本仓库 | 可逐行核对，含 10 万曲基准 |

因此下文分两档：**A 档**有类名/行号；**B 档**是契约推断，逐条标注"推断"。凡涉及"服务端表结构、索引实现、分词器"的地方，一律不给确定结论。

---

## 1. Audio Station 的库模型

### 1.1 对象模型：一条记录，三段附加

服务端返回的每一项都带 `type`，客户端据此分流（`item/SongItem.java:100-180`）：

| `type` | 含义 | 客户端落地类型 |
|---|---|---|
| `file` | 一首真实曲目 | `FILE_MODE` |
| `folder` | 目录节点 | `DIRECTORY_MODE`（`is_personal` 追加 " (home)"） |
| `container` | 虚拟聚合（专辑/歌手/类型…） | `CONTAINER_MODE` |
| `station` | 网络电台 | `RADIO_MODE` |
| `remote` | 远端曲目 | `RADIO_MODE` |

曲目的字段不是平铺的，而是**按需附加**的三段（`additional=song_tag,song_audio,song_rating`）：

```json
{ "type":"file", "id":"...", "title":"...", "path":"/music/...",
  "additional": {
    "song_tag":   { "artist","album","composer","genre","album_artist","comment","disc","track","year" },
    "song_audio": { "duration","frequency","channel","bitrate","codec","container","filesize" },
    "song_rating":{ "rating" }
  } }
```

**字段缺什么，比有什么更能说明设计**：

- 没有 `bit_depth`（只有 `frequency`/`bitrate`/`channel`）→ 客户端判断"高解析"只能靠频率阈值，DSD 也只能靠 `format` 字符串；
- 没有"加入时间"字段，但服务端支持 `sort_by=time`（`ApiEnumerator.java:331-333`）→ **加入时间是服务端排序键，不下发**，客户端无法自行按加入时间排；
- `rating` 单独一段、且只有 `Song` API ≥ v2 才有（`WebAPI.java:124-125`）→ 评分是**后加的可选能力**，不是库的固有属性。

### 1.2 虚拟容器矩阵：14 种视图，4 个端点

客户端不自己分组，而是把"要看什么"翻译成 `container` 参数交给服务端（`ApiEnumerator.java:320-436`）：

| 容器 | 端点 | 关键参数 |
|---|---|---|
| 专辑 / 最新专辑 | `Album.list` | `sort_by=time&sort_direction=desc&limit=50`（最新 50 张） |
| 歌手 / 作曲者 / 类型 | `Artist.list` / `Composer.list` / `Genre.list` | `filter=<关键字>` |
| 首页默认类型 | `Genre.list_default_genre` | — |
| 某歌手的专辑 / 某类型的专辑 / 类型下歌手 | `Album.list` / `Artist.list` | `artist=` / `genre=` / `genre&genre_filter` |
| 类型→歌手→专辑 | `Album.list` | `genre&artist&genre_filter` |
| 评分视图 | `Song.list` | `song_rating_meq&song_rating_leq&sort_by=song_rating` |
| 随机 100 | `Song.list` | `sort_by=random&limit=100` |
| 文件夹 | `Folder.list` | `id&recursive`（API ≥ v3） |

容器列表统一带 `additional=avg_rating`，曲目列表带三段附加。**聚合值（`total`、`avg_rating`）由服务端算好下发**，客户端不做任何统计。

### 1.3 分页：固定 1024，`-1` 表示"全要"

```java
// ApiEnumerator.java:225-234
private int getLimit(int page)  { return -1 == page ? -1 : 1024; }
private int getOffset(int page) { return -1 == page ? 0 : (page - 1) * 1024; }
```

- 页大小**硬编码 1024**，与用户设置无关；
- `page = -1` → `offset=0&limit=-1`，服务端一次返回**全部**。这正是"全部播放 / 全部加入队列 / 全部下载"的取数方式（`ContainerFragment.java:365`、`PlaylistFragment.java:336`、`HomePagePinsFragment.java:135`）；
- 每页都回 `total`，客户端据此算页数（`CacheManager.java:700-786`）。

代价很直接：五万首的"全部播放"是一次**几 MB 的单响应**，且必须等它到齐才能起播——和 fnAudio 曾经"上传整条队列"是同一类错误的另一头。

### 1.4 搜索：字段级参数，无分页，上限 1024

```java
// ApiEnumerator.java:859-897
if (category == ALL) { params += title/album/artist/genre/composer = 关键字; }
else                 { params += category.name().toLowerCase() = 关键字; }
// getBasicParams(1) → offset=0&limit=1024，无翻页
```

三个要点：

1. **匹配在服务端**，客户端不持有可检索的全文；
2. `ALL` 是把同一关键字**分别塞进 5 个字段**，字段间是 OR 还是 AND 由服务端决定（**推断**：OR，否则 `ALL` 几乎不可能命中）；
3. 结果**封顶 1024 条**且不能翻页——搜索"周杰伦"这种大结果集，客户端只拿到前 1024 条，且顺序由服务端定。

### 1.5 封面：服务端合成，客户端按 `MD5(bundle)` 落盘

| 场景 | 方法 | 参数 |
|---|---|---|
| 专辑/歌手/类型/作曲者 | `Cover.getcover` | `album_name`、`artist_name`、`genre_name`、`composer_name`、`album_artist_name`、`default_genre_name&is_hr` |
| 文件夹 | `Cover.getfoldercover` | `id` |
| 单曲 | `Cover.getsongcover` | `id` |
| 直链（列表缩略图） | `getCoverUrl()` | `method=getsongcover&version=1&id=music_<数字>` |

客户端缓存文件名 = `getCoverFolder() + MD5(bundle.toString())`（`ApiEnumerator.java:729`）——**以"查询条件"为键**，不是以曲目 id 为键。好处是整张专辑共用一份；坏处是标签一改，旧文件永远不会被复用也不会被清（只能靠 `clearBrowsableCache` 扫 `:browsable:` 前缀）。

封面解码、嵌入图提取、文件夹 `cover.jpg` 查找**全在服务端**，客户端只存字节。

### 1.6 评分、智能歌单、首页 Pin：三种"保存下来的查询"

- **评分**：0–5 星，`song_rating_meq/leq` 过滤、`avg_rating` 聚合；离线改分先进内存 `mRatingMap`，列表回填时覆盖服务端值（`CacheManager.java:806-819`），联网后再落库。
- **智能歌单**：`PERSONAL_SMART_PLAYLIST` / `SHARED_SMART_PLAYLIST` 容器（`Common.java:230-231`）——条件存服务端，客户端只按 id 取曲目。
- **首页 Pin**：`Pin.pin` 提交 `{type, criteria:{...}, name}` JSON（`ApiEnumerator.java:1144-1179`），`Pin.list` 取回、`Pin.reorder` 排序。

这三者本质是同一件事：**把查询条件持久化在服务端，客户端只存展示顺序**。fnAudio 目前没有对应物（见 §3）。

### 1.7 客户端页缓存：无 TTL、无失效事件

```
<cacheDir>/<online>_<CONTAINER>[_<MD5(bundle)>]_<library>/<page>.cache
```

```java
// CacheManager.java:222-241
if (force) clearFolder(prefix);              // 只有显式刷新才清
File f = new File(prefix + "/" + page + ".cache");
if (!f.exists()) ConnectionManager.doEnumContainer(...);   // 不存在才请求
JSONObject o = read(f);
if (!online) f.delete();                     // 离线读完即删
```

四个后果：

1. **没有 TTL**：一次取到的页会一直用到用户下拉刷新或切库；
2. **没有变更事件**：`Common.gLibraryChanged` 只在"个人库/共享库"偏好被改时置位（`SettingsFragment.java:466-475`），库内容变化**不会**通知客户端；`PagerFragment.java:565-576` 的 `onResume` 也只在这个标志为真时清缓存。全仓 grep 不到 `library_version` / `LibraryChange` / `onLibraryChanged` 一类入口，说明客户端**没有**轮询或推送来感知索引变化；
3. 缓存键含 `online` 与 `library`，所以"在线/离线""个人/共享"天然隔离；
4. 离线分支"读完即删"说明它**不是**离线数据源——离线数据源是本地 DB（下一节）。

### 1.8 离线库 = 已下载子集

本地库是 `DSaudio_LocalCache_DB`（v6，`provider/DatabaseAccesser.java:30-31`），三张表：

```sql
song_table(id, dsid, songid, title, artist, album, composer, genre, album_artist,
           path, duration, filesize, bitrate, channel, frequency, cache_path,
           timestamp, hit_count, cover_path, lyric_path, disc, track, year,
           comment, cache_bitrate, rating, download_type)
localPlaylistInfo(...)
local_playlist_song_relation(_relation_id, playlist_dsid, playlist_id, song_dsid, song_path, song_id)
```

离线时 `LocalEnumerator` 全部查这张表（`LocalEnumerator.java:87-134`、`208-214`）：分组按 `album/artist/genre/composer` 列做 `GROUP BY`，搜索用 `LIKE`，播放取 `songItem.getCachePath()`（`LocalEnumerator.java:237-240`）。

**关键结论**：`song_table` 只装**下载过的**曲目（`getConditionForDownloaded()` 以 `cache_path` 非空为准，`DatabaseAccesser.java:387-389`）。所以 Audio Station 的"离线音乐库"不是"完整索引的本地副本"，而是"我下载了什么"。这也解释了为什么它不需要本地索引引擎——本地根本没有全库。

### 1.9 能力协商：按 API 版本降级，不按 NAS 型号

`WebAPI.resolveCapability()`（`WebAPI.java:120-142`）先查 `SYNO.API.Info`，再按各 API 的 `maxVersion` 开功能：

| 能力 | 判据 |
|---|---|
| 评分 | `SYNO.AudioStation.Song` ≥ 2 |
| 歌单分享 | `Playlist` ≥ 2 |
| 文件夹递归 | `Folder` ≥ 3 |
| 类型→歌手 | `Artist` ≥ 3 |
| 首页 Pin | `Pin` ≥ 1 |
| 加入下一首 | `RemotePlayer` ≥ 3 |

这套做法值得借鉴：**新功能不靠"版本号大于 X"，而靠"这个端点支持到第几版"**，旧 NAS 自动少几个按钮而不是报错。

### 1.10 服务端索引（推断，标 B 档）

SPK 加密，无法验证实现。以下只能由契约反推，**不作为事实**：

- `total` 每页返回 → 每个过滤组合都要能快速计数，说明存在**按 (album/artist/genre/composer/rating) 的物化聚合**，而不是每次 `COUNT(*)` 扫全表；
- `avg_rating` 随容器下发 → 评分与容器聚合是**写时维护**的；
- `sort_by=time` 可用 → 有"加入时间"列且已建索引；
- 封面按 `album_name+artist_name` 查询即可返回 → 封面与曲目解耦，**按标签组合索引**，不按文件；
- `id` 为不透明串，纯数字时封面 URL 加 `music_` 前缀（`ApiEnumerator.java:1023-1028`）→ 服务端主键是自增整数，对外做了前缀隔离；
- `Info.getinfo` 下发 `playingQueueMax`、`transcodeCapability`、`privilege{tagEdit,sharing,upnpBrowse}` → 库的**写入能力（改标签）与队列上限由服务端声明**，客户端只做开关。

---

## 2. fnAudio 的库与索引

### 2.1 数据模型：一张宽表 + 四张聚合表

`library.py:2639` 起，`library.sqlite3`：

```sql
tracks(id PK, path, root, folder, title, artist, album, track_no, album_artist,
       composer, genre, format, mime, is_dsd, duration, size, sample_rate,
       bit_depth, bitrate, added, added_ns, modified, modified_ns,
       cue_path, cue_track, cue_start, cue_end, metadata_version, item_json)
albums(name PK, artist, track_count, cover_track_id)
artists / composers / genres(name PK, track_count, cover_track_id)
folders(path PK, root, parent, name, track_count, cover_track_id)
covers(track_id PK, source, folder_path, updated_at)
cue_tracks(track_id PK, cue_path, audio_path, track_no, start, end)
library_meta(key PK, value)   -- signature / track_count / dsd_count / root_summary / search_index_version
```

与 Audio Station 的三处结构性差异：

1. **`bit_depth` 与 `sample_rate` 是独立列**，DSD 另有 `is_dsd` 布尔 → 高解析/DSD 是索引属性，不靠字符串猜；
2. **`added_ns` 是本地列**，可直接排序，不依赖服务端；
3. **`item_json` 是渲染快照**：列表页直接吐这段 JSON，避免"回表 + 拼装"；代价是标签改动要同步重写该列（写入路径用 `WHERE tracks.item_json <> excluded.item_json` 跳过无变化行）。

聚合表都带 `cover_track_id`（该组用哪首的封面）与 `track_count`（该组曲目数）——**封面选择与计数是索引的一部分**，不在请求时算。

### 2.2 身份：内容指纹，不是路径

```python
# track_identity.py
sha1("fnaudio-id1|" + size + "|" + head(16KiB) + middle(16KiB) + tail(16KiB))[:16]
```

- 移动/改名/换盘不换 id；收藏、歌单、队列不会指空（旧实现是 `sha1(path)`，换挂载点即全库失效）；
- 字节完全相同的两份文件**故意折叠成一个 id**；
- CUE 段没有自己的文件 → id = CUE 内容 id + 轨号。

对比 Audio Station：`id` 由服务端分配，客户端只当不透明串用——**换 NAS、重装、重建索引都可能换 id**，客户端侧只能靠 `path` 兜底（`SongItem` 里同时存 `path` 与 `songid`）。

### 2.3 扫描管线：事件 → 签名 → 复用 → 解析 → 发布

```
inotify(dirty/generation) ─┐
                           ├→ library_signature(每文件 size+mtime_ns+METADATA_VERSION)
定时/启动完整性 ────────────┘        │
                                     ├─ 相同 → 整轮跳过（空闲 O(1)，不再遍历全库）
                                     └─ 不同 → 逐文件：
                                          can_reuse_cached_item(size, mtime_ns, version)?
                                            ├ 是 → 直接复用旧 item（不读标签）
                                            └ 否 → content id → ffprobe → 标签/封面/CUE → build item
```

关键性质（`library.py:783-900`、`1232-1356`）：

- **CUE 先扫、音频后扫**，被 CUE 引用的整轨文件不重复入索引；
- **增量粒度是文件**：只有 `size/mtime_ns/METADATA_VERSION` 变了的文件才解析标签；`METADATA_VERSION` 一升，全库强制重解析；
- **超时/取消/异常保留上一个有效索引**，并把已扫到的部分发布为"部分索引"（`publish_partial_library_index`），不会出现"扫到一半库空了"；
- **写盘失败有重试队列**（`library_persist_retry_status`），不是丢结果；
- **符号链接不越界**：扫描、签名、CUE 引用都用真实路径判包含关系。

对比 Audio Station：库变更对客户端**不可见**（§1.7），只能人工刷新；fnAudio 是"事件驱动 + 签名复核"，两者在"库变了多久能看到"上是数量级差异。

### 2.4 写入：先算差集，只重建受影响的分组

`save_items_to_sqlite`（`library.py:3012-3166`）在一个事务里：

1. 临时表 `current_track_ids` / `current_track_meta` 装新扫描结果；
2. 用 `LEFT JOIN` 算出**受影响的 (root, folder) 子树**与**标签变化集**；
3. 先 `_refresh_group_tables_for_changes(conn)` 捕获旧标签，再 upsert `tracks`（`item_json` 未变则不写）；
4. 删掉不在新集合里的 `tracks` / `covers` / `cue_tracks`（孤儿清理）；
5. 只重建受影响的分组表与 `folders` 子树，不做全表重建；
6. 重建 FTS（外部内容表 `rebuild`）、刷新各组 `track_count`、`root_summary`、`signature`；
7. 失效查询缓存 epoch。

Audio Station 侧没有对应证据（服务端加密），但**从"客户端只读"这一点可以确定：标签修正必须回到服务端索引器，客户端改不了库**。

### 2.5 查询：keyset 游标 + 六种排序 × 双向

`/api/library` 参数（`library_query_spec.py:232-248`）：

```
view=all|recent|dsd|random100   group=albums|artists|composers|genres
album / folder / root / search / subtree
sort=title|artist|album|format|added|track_no    dir=asc|desc
limit(1..500) / offset(≤100000) / cursor(≤768 字符)
```

- **游标是 keyset 位置**，一页两次索引 seek；`cursor` 与 `offset` 同时给时**忽略 offset**（否则会重复跳过）；
- 每种排序都有 `(键 NOCASE, title NOCASE, id)` 的**双向复合索引**，`track_no<=0` 用 `CASE` 归到末尾，避免"无轨号"排在最前；
- 分组表另有 `name COLLATE NOCASE` 双向索引，注释里写明"没有它每页都要全表排序"；
- `random100` 不用 `ORDER BY RANDOM()`（会扫全表），而是**按 rowid 采样 + 缺口重试**，再按展示键排序；
- 页面缓存按 `(view, group, album, folder, root, search, sort, dir, limit, offset, cursor, subtree)` 做键，扫描后 epoch 自增整体失效。

对比 Audio Station：1024 固定页 + offset，深度翻页是 `OFFSET n` 线性代价；排序只有 3 个服务端键。

### 2.6 搜索：FTS5 trigram，可降级

```sql
CREATE VIRTUAL TABLE tracks_search USING fts5(
  title,artist,album,album_artist,composer,genre,folder,path,format,
  content='tracks', content_rowid='rowid', tokenize='trigram')
```

- 外部内容表，不复制正文；`rebuild` 在索引写入尾部统一做；
- 老 fnOS 的 SQLite 没有 FTS5/trigram → 捕获 `OperationalError` 后**自动降级 LIKE**，并把模式记进 `library_search_index_status`；
- 搜索词只做"整串"匹配，**没有字段限定**（`title:` / `artist:` 之类）。

对比 Audio Station：字段级参数（`title/album/artist/genre/composer`）但**无分页、上限 1024**；fnAudio 可翻页但**不能限定字段**。两者各缺一半。

### 2.7 元数据与封面：本地解析 + 在线增强 + 可写回

| 环节 | fnAudio | Audio Station |
|---|---|---|
| 标签解析 | ID3v1/v2、Vorbis、APE、MP4、WAV、DSD、CUE（`id3_parser.py`、`vorbis_reader.py`、`ape_tag_parser.py`、`cue_parser.py`） | 服务端索引器（不可见） |
| 音频参数 | ffprobe（`probe_runner.py`），采样率/位深/码率/声道 | 服务端 `song_audio` |
| 封面 | 嵌入图 / 侧车图 / 文件夹图 / ffmpeg 抽取（`cover_readers.py`、`ffmpeg_cover.py`），**按尺寸归一化 + 预热缩略图**（`cover_cache.py`） | 服务端 `Cover` 端点合成 |
| 在线增强 | 网易云 / QQ / 酷狗 / MusicBrainz（`metadata_service.py`），候选打分、字段级合并 | **无**（只有 `LyricsSearch` 在线找歌词） |
| 写回标签 | 支持（`metadata/apply`、`retry-tag-writes`） | 仅服务端声明 `tagEdit` 权限，客户端未实现 |

这是 fnAudio 明显更强的一块：**索引不只记录标签，还能修正标签并回写文件**。Audio Station 的标签一旦错，只能在 DSM 网页端改，客户端没有入口。

### 2.8 可观测性

`/api/library/status` 一次给出：`roots[]`（每个根目录的 exists/readable）、`count`、`dsd_count`、`scanning/queued/result/cancelled/timed_out/deadline`、`phase`、`scanned`、`found`、`errors[]`、`cache_failures`、`index_persist`（重试队列）、`change_detection`（inotify 监听数/dirty/overflow）、`search_index`（fts5-trigram 或 like）、`storage`。

Audio Station 侧对应物只有 `Info.getinfo` 的包版本与能力位——**没有索引进度、没有错误列表**。库出问题时用户只能"清缓存重进"。

---

## 3. 差异总表

| 维度 | Audio Station（3.16.0） | fnAudio | 判断 |
|---|---|---|---|
| 全库位置 | 仅 NAS 服务端 | NAS 本地 SQLite（`library.sqlite3`） | 持平（都本地于 NAS） |
| 客户端是否持有全库 | 否，按页取 | 否，按页取 | 持平 |
| 索引身份 | 服务端分配的不透明 id（数字加 `music_` 前缀） | 内容指纹 `sha1(size+头/中/尾)` | **fnAudio 强**（移动/换盘不丢引用） |
| 分页 | 固定 1024 + offset | 1–500 可调 + keyset 游标 + offset 兜底 | **fnAudio 强** |
| 深度翻页代价 | `OFFSET n` 线性 | 游标恒定（10 万曲实测 0.016 s，深度 5 万 0.021 s） | **fnAudio 强** |
| 排序 | 3 个服务端键（time / rating / random） | 6 键 × 双向，全有复合索引 | **fnAudio 强** |
| 全量播放取数 | 一次 `limit=-1` 拉全表 | 按页追加队列（R571） | **fnAudio 强** |
| 搜索 | 服务端字段级，无分页，上限 1024 | FTS5 trigram，可分页，不能限字段 | 各有优劣 |
| 搜索性能（10 万曲） | 不可测（服务端加密） | FTS 0.018 s vs LIKE 0.154 s（8.6×） | 仅记录 |
| 变更检测 | **无**（仅手动刷新/切库） | inotify + 签名 + generation，空闲 O(1) | **fnAudio 强** |
| 增量写入 | 不可见（推断为服务端全量重建） | 文件级复用 + 只重建受影响分组 | **fnAudio 强**（可验证） |
| 库状态/进度 | 无 | 完整 `/api/library/status` | **fnAudio 强** |
| 聚合能力 | `total`、`avg_rating`、智能歌单、首页 Pin | 分组 `track_count` + `root_summary`，无保存查询 | **AS 强** |
| 评分 | 0–5 星 + 区间过滤 + 平均分 | 无星级（只有收藏） | **AS 强** |
| 保存的查询 | 智能歌单 + Pin（criteria JSON） | 无（前端 localStorage 只存 UI 偏好） | **AS 强** |
| 个人/共享库 | `library=personal` 或 `shared`，按用户隔离 | 单一库 + 访问配置 | **AS 强** |
| 离线库 | 已下载子集（`song_table`），离线可浏览/搜索/播放 | 无离线浏览（R583 已按裁定撤除） | **AS 强** |
| 标签修正 | 客户端无入口 | 在线增强 + 写回文件 | **fnAudio 强** |
| 封面 | 服务端按标签组合合成，客户端按 `MD5(bundle)` 存 | 本地提取 + 尺寸归一化 + 预热缩略图 | 各有优劣 |
| 能力协商 | 按端点 `maxVersion` 降级 | 按自有版本整体升级 | **AS 更平滑** |
| 多根目录 | 无（单共享文件夹模型） | `library_paths` 多根 + 标签消歧 | **fnAudio 强** |
| CUE | 服务端虚拟曲目（`isVirtualSong`） | 索引内 `cue_tracks`，段有独立 id/时长 | **fnAudio 更完整** |
| 位深/DSD | 无 `bit_depth`，靠 `format`/`frequency` 猜 | `bit_depth`、`is_dsd` 独立列 | **fnAudio 强** |

---

## 4. 结论：两类系统的分界

**Audio Station 把复杂度放在服务端**：客户端只认 5 种 `type`、14 种容器、1024 一页，所有分组/聚合/搜索/封面都问 NAS。好处是客户端极薄、换端成本低、聚合能力天然一致；代价是**刷新语义落后**（库变了没人告诉它）、深度翻页线性、全量操作要拉全表。

**fnAudio 把复杂度放在索引层**：SQLite 一张宽表 + 四张聚合表 + FTS，事件驱动刷新，keyset 分页，标签可写回。好处是"库是自己的"，刷新、增量、可观测都能自己控；代价是**缺少"保存的查询"这一层抽象**——没有评分、没有智能歌单、没有 Pin，用户想固定一个"最近添加的 DSD"视图只能每次手点。

一句话：**Audio Station 的库是"查询服务"，fnAudio 的库是"索引 + 查询服务"；前者赢在视图抽象，后者赢在索引自持。**

---

## 5. 值得借鉴 / 不值得借鉴

### 值得借鉴（按性价比）

| 优先级 | 动作 | 落点 | 代价 |
|---|---|---|---|
| P1 | **保存的查询（criteria JSON）**：把 `view+group+album+folder+search+sort+dir` 存成一条命名视图，服务端执行 | `state_store.py` 新增 `saved_views`，`/api/library` 接受 `view_id` | 中（不动索引） |
| P2 | **搜索字段限定**：`search=artist:周杰伦` 之类的前缀语法，映射到 FTS 的列过滤 | `library_search_policy.py` | 小 |
| P2 | **能力协商**：把 `/api/library/status` 里的 `search_index.mode`、`supported_formats` 变成前端的功能开关，而不是版本号判断 | `app.js` 启动时读一次 | 小 |
| P3 | **封面按查询条件做键**：专辑/歌手共用一份，避免同专辑 20 首各存一张 | `cover_cache.py` | 中 |

### 不值得借鉴

1. **1024 固定分页**：fnAudio 已经是 1–500 可调 + 游标，退回去只会更差；
2. **无 TTL、无失效的页缓存**：AS 的"库变了客户端不知道"正是 fnAudio 用 inotify + epoch 解决的问题；
3. **`limit=-1` 全量拉取**：五万首一次响应，正是 R571 在 fnAudio 里改掉的模型；
4. **离线库 = 下载子集**：产品目标不同（AS 是"离线听我下载的"，fnAudio 是"局域网内随时听全库"），照搬会把索引拆成两套。

---

## 6. 怎么验证（不是拍脑袋）

- **分页代价**：`tools/benchmark_large_library.py --tracks 100000 --page-size 120`，对比 `offset` 与 `cursor` 在第 0/1200/12000/50000 页的耗时；
- **搜索代价**：同一基准里的 `search.active` 与 `search.like_baseline`（本机 0.018 s vs 0.154 s）；
- **刷新语义**：在曲库目录里新建一个文件，看 `/api/library/status` 的 `change_detection.dirty` 与 `last_scan` 是否在一个轮询周期内变化；
- **AS 侧结论**：只能靠反编译证据复核（`ApiEnumerator.getLimit/getOffset`、`CacheManager.doEnumContainer` 的 `file.exists()` 短路、`DatabaseAccesser` 的 `song_table` 查询条件），服务端行为不可测。

### 本机基准（10 万曲合成索引，不含真实文件解析）

| 指标 | 数值 |
|---|---|
| 索引库大小 | 214,499,328 B（约 205 MB） |
| 建索引耗时 | 11.49 s |
| 单页查询（120 行） | 0.016–0.024 s |
| 游标 vs offset（深度 5 万） | 0.0164 s vs 0.0207 s（0.79×） |
| 搜索 FTS vs LIKE | 0.0180 s vs 0.1543 s（8.6×） |
| 页面缓存冷/热 | 13.8 ms / 1.9 ms（7.3×） |
| 连接池首屏 | 11.0 ms → 4.8 ms（2.3×） |

> 这些是**查询与索引写入**的数字，不含扫描/标签解析。真实库的首扫耗时取决于文件数与磁盘，`library.py` 的 `scan_timeout_seconds` 默认 3600 s。

---

## 7. 一句话总结

Audio Station 的音乐库是**服务端的物化视图**：客户端只拿 1024 一页和三个排序键，库变了也不知道；fnAudio 的音乐库是**自己的索引**：内容指纹、事件驱动、游标分页、FTS、标签可写回。要补的不是索引能力，而是 AS 那层"把查询存下来"的抽象——**保存的查询、字段级搜索、能力协商**这三件，是这套逆向里唯一值得搬的东西。
