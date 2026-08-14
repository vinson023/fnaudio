# fnAudio AI 修改记录

## 0.2.3 (2026-08-14)

- 从 `app.js` 抽取顶部标题/副标题的纯展示规则至 `view_presentation.js`，减少视图渲染函数的职责并建立前端模块边界。
- 发布缓存构建标识现在同时涵盖 CSS、主 UI 脚本与视图展示模块。
- 验证通过：282 项 Python 测试、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 检查。FPK：`artifacts/0.2.3/fnaudio-0.2.3-fnpack.fpk`，SHA-256 `C9D4B744ED56C8FD6CAEAF530EB6BA055C32DFCBA997DE1017C1B98FC48BBF8E`；Android Debug APK：`artifacts/0.2.3/fnaudio-android-0.2.3-debug.apk`，SHA-256 `307E4DCF5E5B6BAB67636F14F5AE6890039344A1EDFE7E240345593F9B04540E`。

## 0.2.2 (2026-08-14)

- 发布阶段静态资源改为由 CSS/JS 内容派生的构建标识，fnpack 暂存副本会自动写入缓存键，消除同版本修复残留旧脚本的风险。
- 新增受认证保护的 `/api/diagnostics` 脱敏快照，集中导出版本、播放、MPD、扫描、元数据、转码、DLNA 与计数器状态，不包含路径、密码、Token、Cookie 或歌曲信息。
- Android Release 构建必须提供完整 keystore 参数并验证文件存在；无签名凭据时明确失败，Debug 构建不受影响。
- 新增默认关闭的 Chromaprint/AcoustID 可选候选源：仅在配置 fpcalc、启用开关并设置环境变量 Key 时运行，失败不会影响现有元数据队列。
- 完整离线验证通过：282 项 Python 测试、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 包内检查。FPK：`artifacts/0.2.2/fnaudio-0.2.2-fnpack.fpk`，SHA-256 `8D2BFBA65DA52CC9B2AA1685D24654C8BCF486DAE2A28F2179CB0093F3ED9727`；Android Debug APK：`artifacts/0.2.2/fnaudio-android-0.2.2-debug.apk`，SHA-256 `A2F6009AEEF2EF57046BBDC9B5B278F8F4B48A99729B5B3BB22C48F82C228737`。

## 0.2.1 (2026-08-14)

- 修复顶部简介只在首屏短暂显示“飞牛私人音乐库”、随后被前端默认视图文案覆盖的问题。桌面与移动端音乐库默认副标题现保持为“飞牛私人音乐库”。
- 更新 Web 静态资源版本参数与 Android 安装序号，确保覆盖升级后不会继续命中 0.2.0 的缓存脚本。
- 验证通过：版本联动回归、JavaScript 语法检查、Android Debug 构建与原生 fnpack 包内检查。FPK：`artifacts/0.2.1/fnaudio-0.2.1-fnpack.fpk`，SHA-256 `F59FF020D739CAD35A94F6A44EEC0B6D9B86EB77C046937C1797FE3CAF6FC755`；Android Debug APK：`artifacts/0.2.1/fnaudio-android-0.2.1-debug.apk`，SHA-256 `5042A8C62CAC832EEB55F85327B45A07515D30E73AE39F32D0D64FC17043BCDE`。

## 0.2.0 (2026-08-14)

- 应用顶部简介统一为“飞牛私人音乐库”。
- 应用中心介绍更新为本地音乐播放、高解析音乐库、歌词封面补全、USB DAC、DLNA 推送和 Android 锁屏控制的完整能力说明。
- 发布版本升级至 0.2.0；Android `versionCode` 递增至 271，发布校验不再错误地从三段版本号末段推导安装序号。
- 验证通过：279 项 Python 回归、Node/UI 回归、2 项 Playwright E2E、Android Debug 构建与原生 fnpack 包内检查。
- 发布产物：`artifacts/0.2.0/fnaudio-0.2.0-fnpack.fpk`，SHA-256 `7441A3446CD239A3F8561894736068F904885464AD47D4799A84F4B508CDE7EE`；Android Debug APK 为 `artifacts/0.2.0/fnaudio-android-0.2.0-debug.apk`，SHA-256 `38E61CE3D0533EB34B00AB2DFC44DB58F169E6CAAA9808A12A41CC3C64024983`。

## 0.1.270 (2026-08-14)

- Metadata review now presents all persisted candidates and can confirm any selected candidate. The API accepts only a non-negative candidate index, validates it against that track's stored candidates, and never accepts client-supplied metadata fields.
- Added a Windows GitHub Actions verification workflow that reuses the offline Python/Node/Playwright tests, Android Debug build and native fnpack package inspection.
- Consolidated library root merge and configuration writes in `library.py`, so scan, SQLite and the settings API share canonical path identity.
- Reconciled the stale P1-P3 backlog against current code and documented real external blockers: Chromaprint runtime plus AcoustID key/quota, a remote CI repository, physical protocol/device acceptance, signing and historic backup recovery.

## 0.1.269 (2026-08-14)

- Cover thumbnail prewarming now uses the shared FFmpeg resource gate used by streaming and transcode work, so background artwork generation cannot bypass the configured concurrency budget.
- Library warmup is processed in 24-track pages with a short delay between pages. It attempts the FFmpeg slot only briefly, yielding to interactive cover, playback and transcode requests when the NAS is busy.
- Deferred library workers have a cancellable lifecycle. A rescan replaces stale work, shutdown cancels and joins workers, and cancellation is checked before every cache write to prevent cache-directory cleanup races.
- Added cover-cache regressions for shared FFmpeg gating and cancellation after a cover reader has started. Corrected the mobile CSS assertion to inspect only the player rule block.
- Built exclusively with fnpack and fast-deployed to the authorized LAN test host. The live 0.1.269 service on port 18083 passed its health check.

## 0.1.265 (2026-08-14)

- Android 长按歌曲菜单隐藏“打开包含的文件夹”和“分享外部链接”。
- PC 右键菜单保留这两项功能，避免移动端与飞牛文件管理能力不匹配。

## 0.1.264 (2026-08-14)

- 修正当前播放收藏按钮与异步服务端状态合并不同步的问题。
- 收藏 ID 比较统一为字符串形式；播放核心确认当前歌曲后立即刷新收藏状态。

## 0.1.263 (2026-08-14)

- 统一桌面播放器右侧工具按钮的尺寸与 SVG 描边，歌词按钮恢复为中文“词”。
- 播放设备图标改为扬声器输出设备图形；MP3 转码按钮改为纯 MP3 文字标识。
- 设置入口改为控制面板图形，替换历史复杂齿轮图标。

## 0.1.262 (2026-08-14)

- Raised the release version for formal fnOS App Center overwrite-upgrade validation.
- The FPK is built and inspected exclusively with the native `fnpack` tool; no post-build repackaging is permitted.
- This release records App Center upgrade, lifecycle/configuration retention, port/service health, and rollback evidence separately from fast deployment.

## 0.1.261 (2026-08-14)

- Added track-level metadata enrichment for files whose title/artist came from filenames or whose album is missing.
- Reused existing MusicBrainz, NetEase, QQ, Kugou, Migu, JOOX and Qianqian provider adapters to collect and score recording candidates.
- High-confidence, unambiguous matches automatically fill only blank or filename-derived fields; existing embedded tags are never overwritten by an online match.
- Ambiguous matches are persisted as review candidates and can be confirmed from the track action dialog before background writeback.
- Added metadata APIs for candidate inspection and confirmation, match status counters, and regression coverage for candidate ranking and safe apply behavior.
- Release artifacts remain fnpack-only, with no FPK repackaging.

## 0.1.238 (2026-08-13)

- Added persistent 160 px list thumbnails and 512 px playback artwork under the private cache directory. Cached URLs include the source modification version and use immutable HTTP caching.
- Limited cold thumbnail generation to two concurrent FFmpeg processes and deduplicated requests for the same cover, preventing first-page artwork from saturating the NAS.
- Added persistent negative results for tracks without artwork. Subsequent library responses omit their cover URL and render the unified music-note fallback without repeated 404 requests.
- Android notifications, MediaSession, now-playing and lyrics keep the 512 px artwork path; track and group lists use 160 px thumbnails.
- This cache is read-only with respect to music files: it does not write tags or replace embedded artwork.
- Fixed the no-cover image fallback so removing a failed image no longer dereferences its detached parent in Chromium/WebView.
- Installed on the LAN fnOS host and verified 3.03 MB artwork becomes a 4.8 KB 160 px thumbnail; cold generation was 241.57 ms and persistent-cache access was 0.17 ms. Live CGI rendering used 160 px list images, retained 512 px playback artwork, and produced no console warnings or errors.
- Android private cover requests now pass through the concurrent OkHttp resource proxy with the fnOS bearer token, trim-token header and authenticated cookies. Web-session profiles recover missing image cookies from CookieManager.
- Returning to Login now opens a blank address form instead of prefilling the active FN Connect ID. A manually entered endpoint no longer inherits an edited/active `FN Connect - ...` name or profile identity, so multiple direct addresses remain separate history records.
- Corrected the logout behavior: explicitly returning from MainActivity now prefills the last active address/FN ID, account and encrypted saved password without automatically logging in. First launch still resumes silently, while History > Add remains blank.

## 0.1.227 (2026-08-13)

- Removed FN Connect relay/Tpps mode by product decision. The Android APK no longer includes Tpps JNI, Go runtime support, Remote Config signing, `libgojni.so`, or `libsskit-native.so`.
- FN Connect resolves direct public endpoints only: public IPv6 is probed first and public IPv4 is the fallback. Historical localhost relay profiles are re-resolved from their FN ID.
- Updated the FN Connect preference screen to show the IPv6-first direct policy and relay disabled.
- Clean Android build passed. The debug APK installed on Xiaomi 15 Pro and displayed the new policy UI. Complete FN ID login, library, and playback remain a real-network acceptance task.

## 2026-08-12：连续目标 4，播放兼容 API 与模块边界

- 新增 `playback/http_contract.py`，从 2200 行级 `server.py` 抽出目标分类、目标规范化、队列输入、SSE 包络及旧播放 payload 转换等纯规则。
- 源码调用审计确认当前 Web 与 Android 不再使用 `/api/player/state`、`/api/upnp/{push,control}`、`/api/dac/{push,control}`。旧接口继续转发到权威 `/api/playback/*`，并返回标准 `Deprecation`、后继 `Link` 和诊断头。
- 保留 UPnP/DAC 的只读发现与诊断 API，以及 Renderer 必需的 `/upnp/media/*`。大型模块按风险分阶段拆分，完整边界和删除前置条件记录在 `docs/PLAYBACK_API_COMPATIBILITY.md`。
- 新增 6 个播放 HTTP 契约测试；专项播放回归共 17 项通过。

## 2026-08-12：连续目标 3，源码卫生清理

- 修复 `alsa_output.py` 与 `mpd_service.py` 中 10 处损坏的中文错误/状态提示，消除播放目标 payload 的重复 `name` 键。
- 删除没有调用方且会把 DSD 隐式转换成 PCM 的旧 `dac_ffmpeg_command()`；实际 ALSA 与 MPD 路径保持不变。
- 新增 `test_source_hygiene.py`，通过 AST 检查已知乱码、同作用域重复定义、字面量重复字典键及无条件终止语句后的不可达代码。
- 完整离线验证通过：205 个 Python 测试、JavaScript 语法、5 个 Node UI 回归和 `git diff --check`。

## 2026-08-11：连续目标 2，MPD 播放错误分类

- 新增纯函数模块 `playback/mpd_errors.py`，将 MPD 日志与命令异常稳定分类为媒体源损坏、seek、解码器不可用/失败、输出设备缺失/忙、输出格式不支持、输出 I/O、buffer underrun、队列陈旧、数据库未就绪和后端不可用。
- 每个错误携带 domain、severity、retryable 和建议 action；重复日志合并 occurrence，固定读取最新错误并限制最多 100 个唯一条目。启用 decoder 的普通日志不再误报“解码器不可用”。
- `MpdOutput` 的打开和控制失败返回结构化 `error`/`error_category`，保留原 message；MPD 状态新增 `playback_errors`，旧 `decoder_errors` 保留兼容。
- 日志监控只把真实 `buffer_underrun` 写入旧 underrun 计数。损坏 FLAC、seek 和 decoder 错误不再被当作 DAC 故障；设备缺失和格式不支持记录故障但不盲目重启，设备忙和输出 I/O 仍受 30 秒恢复节流保护。
- 本地 Volumio/moOde 对照确认其通用层同样依赖 MPD/ALSA 日志与输出插件边界，没有适合直接复用的跨版本错误分类器。完整离线验证通过：201 个 Python 测试、JavaScript 语法和 5 个 Node UI 回归。

## 2026-08-11：连续目标 1，统一资源边界

- 新增共享 FFmpeg 并发门。缓存转码与 HTTP 流式转码共用 `ffmpeg_max_concurrency`，并发饱和在发送响应头前返回 503；启动失败返回 502，超时和断连都会释放进程与槽位。
- 元数据和转码待办队列均有持久化上限。普通预热达到上限后拒绝入队，当前歌曲的歌词、封面或 Tag 工作可以淘汰最低优先级的非运行任务；运行中任务不会被删除。
- 元数据封面与转码缓存同时受最大字节数和最小磁盘保留水位控制。封面淘汰会清空实体引用并使其过期，以便后续重新抓取；正在运行或排队的转码目标不会被清理。
- 音乐库扫描新增最长运行时间和取消事件，CUE、目录、文件及快速签名循环均检查截止时间。取消/超时保留原有效索引，并提供受 `settings.write` scope 保护的 `POST /api/library/scan/cancel`。
- `/api/health` 增加扫描、元数据待办/丢弃/封面字节、转码队列与 FFmpeg active/peak/limit 指标。完整离线验证通过：192 个 Python 测试、JavaScript 语法和 5 个 Node UI 回归。

## 0.1.222 (2026-08-11)

- Completed the five-stage offline hardening sequence. DLNA ContentDirectory
  now honors metadata/direct-child browse modes, bounded paging, field filters,
  supported sort criteria and a library-derived SystemUpdateID; unknown objects
  and invalid sorts return UPnP 701/709 faults instead of silently listing the
  whole library.
- Centralized runtime version identity in `app/server/version.py` for HTTP,
  metadata requests, SSDP and device model descriptions. Consolidated the two
  media byte-range implementations and removed a duplicate library helper.
- Added native WAV and uncompressed DFF information readers plus generated
  fixtures covering duration, DSD properties, sidecar artwork, MIME and Range
  seek behavior. Added `tools/test_offline.ps1`; the consolidated run passed
  176 Python tests, JavaScript syntax and five Node UI regressions.
- Updated the release validator for the manifest-backed runtime version and
  built the inspected FPK at `artifacts/0.1.222/fnaudio-0.1.222-fnpack.fpk`;
  SHA-256: `F5B2254FA317F421BA53666C2AB3883EFF142D46751FA18BCA432ADCE917AD80`.
- Added revision-aware user-state changes for favorites and playlists. Stale
  browser windows now merge atomic additions, removals, playlist upserts and
  deletions instead of reviving deleted data through a set union. In-flight
  edits use a dirty retry, while old clients retain the explicit 409 contract.
- Added a reproducible 100,000-track SQLite pagination benchmark. The current
  host built a 56,598,528-byte index in 2.23 seconds; three 120-row pages took
  0.217 seconds in total with 221,516 bytes of peak traced Python allocations.
  Timing is recorded as evidence rather than a machine-independent CI limit.
- Added structured JSON Lines access logs with request IDs, recursive secret
  redaction and bounded rotation. `/api/health` now reports bounded MPD,
  library, metadata and DLNA status/metrics without exposing token state; GENA
  subscriptions are capped at 64 and notifications use four workers.
- Added scoped non-DLNA API authorization. Only authenticated loopback proxy
  requests are accepted for protected routes; library, playback, state,
  settings and file operations use distinct scopes, while direct LAN, missing
  token and missing-scope requests are rejected.
- Hardened path operations with real-path containment, symlink-escape rejection,
  configured-root-only shared-folder deletion and a 2 MiB API request limit.
  Verification passed with 162 Python tests and all Node UI regressions.
- Added a shared DLNA outbound network boundary for SSDP `LOCATION`, SOAP/SCPD,
  GENA `CALLBACK` and Renderer media URIs. It rejects non-HTTP(S) schemes,
  credentials, public/multicast/unspecified addresses, redirects and responses
  above the configured bound while preserving empty NextURI clearing.
- Added focused network-boundary coverage. Verification passed: 157 Python
  tests, JavaScript syntax validation and all four Node UI regressions.
- Reorganized `TODO.md` into a single current backlog. It now separates
  immediately actionable offline engineering from deployment dependencies,
  physical-device acceptance and project-owner decisions; duplicate historical
  release records were removed from the active task list.
- Added `tools/build_release.ps1` as the only supported FPK release command.
  It stages only the authoritative `src/` tree in a temporary directory,
  excludes tests and Python bytecode, validates versions across fnOS, Web and
  Android, then verifies the outer FPK and inner payload before emitting
  `SHA256SUMS`.
- Added `src/tests/test_build_release_script.py`. Offline verification passed:
  151 Python tests, JavaScript syntax validation, four Node UI regressions and
  a complete FPK build/package inspection. The reproducible rebuild SHA-256 is
  `9804F776935DA64D74FFA43C8FC31B75132C3B0D8B661A6F41D762C7DA89BE92`.
- Reworked the repeat control to match Volumio's Media3 convention: neutral
  repeat when disabled, accent repeat for queue repeat, and an integrated `1`
  glyph for repeat-one. Removed the crossed-out repeat icon.
- The initial manually built 0.1.222 package installed on the NAS had SHA-256
  `906BE60546ADCCE1DCCCF72368251BD76C5845F738EEDC1456E5FB06E5FF4825`.
  The later reproducible offline rebuild is recorded above with its own hash.
- Installed the FPK through App Center on the DAC NAS. App Center and the
  running server both verified `0.1.222`.
- Ran the 20-track TEAC UD-301 queue acceptance: all positions appeared,
  `queue_traversal_verified=1`, `restore_verified=1`, 19 natural transitions,
  and zero underruns. Full evidence is in
  `docs/REAL_DEVICE_DAC_QUEUE_0.1.222.md`.
- Added and hardware-validated `tools/real_device_mpd_restart_run.sh`. A
  controlled MPD termination recovered playback through the supervisor, then
  restored the initial USB-DAC stopped session with `restore_verified=1`.
- Discovery recorded no available external Renderer, AirPlay receiver or
  Android/ADB device; no unsupported hardware case was claimed as complete.

## 0.1.204（MPD 重启状态同步与 P0 真机目标继续推进）

- 新增 `normalized_transport()`，恢复路径和 idle listener 统一从规范化 transport/MPD 原始状态推导 `PLAYING/PAUSED/STOPPED`。
- MPD 重启恢复完成后主动同步 idle/fault 状态并通知状态监听器，避免 WebView、PlaybackCore、Android MediaSession 误报 STOPPED。
- 本地 Python unittest 共 117 项通过；FPK SHA-256：`89F2F27701A5699180A80D9DD4C01586061004D7CC8099CA1A6BFE44E637BEFC`。
- FPK 已复制至真机 `/vol1/1000/fnaudio-0.1.204.fpk`，仍需通过 App Center UI“从 NAS 添加”完成安装后再做真机回归。
- 当前 P0 目标 1–7 保持未完成/进行中状态；小时级播放、息屏、物理热插拔、外部 DLNA Renderer、Android 多机和正式签名继续要求真实证据。

## 0.1.205（USB DAC 热插拔去抖）

- USB DAC 监控由单次探测切换为连续样本确认，降低 USB 重枚举期间误停 MPD 的概率。
- 新增 `mpd_device_presence_samples` 配置（1–5，默认 2），断开和恢复均需要达到阈值。
- 新增热插拔状态机和配置边界回归测试；本地 Python unittest 共 121 项通过。
- 修复安装回调端口保留顺序后，新增生命周期顺序回归；本地 Python unittest 共 122 项通过。
- 0.1.205 FPK SHA-256：`994712233E0707B85BE9759211EE71C80BA31A4BEDED9D3C41913768375FB1DE`。
- Android Debug APK SHA-256：`2B3F24FDF8488698F8679A4E6DFDD55D371C56313860AB29F7D71D5628CE2089`；Release 仍为 unsigned，不能作为正式发布包。
- 物理热插拔和真机安装验证尚未完成，目标 1–7 继续保持进行中。
- 0.1.205 已通过 App Center UI 覆盖安装；真实播放中终止 root MPD 后 supervisor 自动恢复，20 首队列、当前歌曲、进度和 `PLAYING` 状态恢复，`underrun=0`。详见 `docs/MPD_RESTART_RECOVERY_0.1.205.md`。
- 追加 TEAC UD-301 API 驱动复验：44.1 kHz PCM 播放至 105.60 秒，队列 20 首、`fault.state=PLAYING`、`underrun=0`；DSF 与 DFF 分别确认 `dsd64:2` Native DSD 源码输出，无 PCM fallback。测试后已恢复原 20 首队列、原当前曲和 STOP/IDLE 状态；详见 `docs/REAL_DEVICE_DAC_RECHECK_0.1.205.md`。
- 补充真机 PCM 控制闭环：pause/resume、seek、next/previous 均经 `playback/control` API 驱动验证，状态回传、原生队列和 underrun 指标正常。
- 启动真机 90 分钟 DAC 长测 runner（每 30 秒采样，结束自动恢复原队列/STOP）；启动阶段已确认 `PLAYING`、20 首队列和 `underrun=0`，最终结果待长测结束后回收日志。
- 长测运行约 5 分 26 秒已确认首个自动跨曲：第 1 首切换至第 2 首，MPD `nextsong=2`，队列 20 首且无 underrun；runner 继续运行中。
- 长测阶段性回收：19 个 30 秒样本已覆盖第 0/1/2 首，状态全部 `PLAYING`，20 首队列、最大 underrun 0；最终长测仍进行中。
- 长测约 12 分钟阶段覆盖第 0–3 首（24 个样本），状态仍为 `PLAYING`，队列 20 首、最大 underrun 0。
- 长测日志增加真机持久副本 `/vol1/1000/fnaudio-long-play-0.1.205.log`，避免会话删除后丢失验收材料。
- 新增 `tools/real_device_short_queue_after_long.sh`：等待长测结束后自动执行 20 首短曲跨曲验证，记录 queue-index 变化，并恢复原队列与 STOP 状态。
- 新增 `docs/REAL_DEVICE_AUTOMATION_0.1.205.md`，记录真机 runner、持久日志和会话删除后的恢复方法。
- 新增 `tools/analyze_real_device_playback_log.py`，可解析 base64 长测日志或 raw JSON 短队列日志，输出采样数、跨曲数、队列长度、fault 和 underrun 摘要。
- 校正短队列验收窗口：实测所选 20 首总长约 36 分 28 秒，因此验证器上限改为 50 分钟，并在 20 个 queue item 全部出现后提前结束；避免 15 分钟窗口造成“只验证部分曲目”的假完成。
- 新增真实 USB 热插拔采集脚本与操作规程；脚本已在 NAS 上通过 `sh -n`，只读记录 ALSA/MPD 状态，不采用 sysfs unbind/bind 模拟。
- 加强短队列自动验收：恢复原队列和 STOP 请求后追加 MPD 状态采样，记录最终队列长度、当前曲目、transport 与 fault。
- 长测阶段性回收更新至 2026-08-10 11:20：125 个有效样本覆盖 5 个队列项、4 次自动跨曲，队列始终 20 首，fault 始终 `PLAYING`，最大 underrun 为 0；90 分钟最终回滚仍待完成。
- 修复 `src/cmd/install_callback` 的配置端口保留顺序：先采用已有端口再探测可用回退端口，避免默认端口被占用时误改用户端口。新增回归测试，并在 NAS 临时夹具中验证 install/config/upgrade/uninstall keep/purge 全流程通过（`lifecycle-callbacks=pass`）。
- 90 分钟 TEAC UD-301 长测已完成：181 个样本、12 个 songid、11 次自然跨曲，测试队列始终 20 首、最大 underrun 为 0。第 146–148 个样本有 API timeout 造成临时 `fault.state=SUSPECT`，但 MPD 始终 `play` 并自动恢复为 `PLAYING`；详见 `docs/REAL_DEVICE_LONG_RUN_0.1.205.md`。历史恢复清单后续被发现有无效 ID，因此原生恢复长度需重新核验。
- 长测退出后，短队列完成 20 个不同项目的自然自动下一曲；全程为 PLAYING、测试队列 20、underrun 0。旧脚本恢复后 MPD 原生队列为 16 首，首次独立恢复为 19 首，均不能视作恢复通过。
- 已根据当前音乐库查询修正 4 个恢复歌曲 ID，新增独立恢复工具和静态一致性回归测试；Python unittest 增至 123 项。最终的正确恢复命令因 SSH 会话中断未提交，真机恢复测试已按用户要求暂停，待恢复连接后先恢复并核验 20 首原生队列、STOP 和 fault。

## 0.1.202（DSD 探测状态同步与生命周期修复）

- ALSA 忙状态探测增加强制刷新和有限重试，避免 MPD 刚停止时残留的 `EBUSY` 缓存误阻止 DSD。
- DSD 播放继续严格要求 Native DSD/DoP 验证，未验证时仍拒绝转 PCM。
- App Center 生命周期脚本兼容实际扁平 UI 安装布局，修复 `service_port.json` 写入错误路径。
- 真机 TEAC UD-301 验证 DSF 与 DFF 均以 `dsd64:2` 源码播放，未发生 PCM fallback。
- 本地 Python 测试 113 项通过；Android `lintDebug`、`assembleDebug` 通过。
- 构建物与验收记录见 `artifacts/0.1.202/`、`docs/APPCENTER_LIFECYCLE_0.1.202.md`。
- 真机短周期回归：20 首 PCM 队列自动推进、`underrun.count=0`；App Center restart 后 MPD 队列长度/当前索引/STOP 状态恢复，显式 play 后可继续播放。详见 `docs/REAL_DEVICE_REGRESSION_0.1.202.md`。
- TEAC UD-301 播放矩阵短测：PCM 44.1/48/96/176.4/192 kHz、DSF、DFF 通过；384 kHz 明确拒绝且不隐式重采样；控制冒烟和队列恢复后状态回滚通过。详见 `docs/PLAYBACK_MATRIX_0.1.202.md`。
- 新增 45 秒 96 kHz FLAC 连续播放监测，进度连续增长且无 underrun，测试后恢复原队列和停止状态。
- 记录真机日志中的 FLAC lost-sync、seek 和 wildmidi 缺失提示，暂不把它们误判为已修复，新增专项调查待办。
- 对两首 GAYLE FLAC 做独立 ffmpeg 校验，确认源文件本身损坏；后续考虑在库扫描或播放错误提示中显式区分源文件损坏与输出链路故障。
- Android `assembleRelease` 与 lintVital 通过；无发布 keystore 时产物保持 unsigned，`apksigner verify` 失败，未把它当作正式发布包。
- 真机配置边界回归：非法端口/不存在音乐目录返回 400，同端口保存不触发重启，队列和音乐库数据保持不变。

## 0.1.201（队列恢复与真机覆盖升级）

- 修复前端恢复超大播放队列时把 536 首 ID 拼成单个超长 URL 的问题；改为 100 首一批，并在临时请求失败时保留缓存行。
- 新增前端回归断言，覆盖分批恢复和失败批次保护逻辑。
- 根版本、FPK manifest、服务端版本、Web 缓存键和 Android versionCode/versionName 统一为 `0.1.201`。
- 本地 Python 112 项、3 个 Node 回归脚本、Android lint/Debug 构建全部通过。
- 真机 App Center UI 覆盖升级成功；版本 `0.1.201` 运行中，fnAudio 重开后当前队列恢复为 536 首。该证据不等同于完成 1–7 全部硬件矩阵。

## 0.1.198（继续推进目标 1–7）

- Android 远程播放 MediaSession 修改重复/随机模式时携带明确目标值，避免手机缓存与服务端状态不一致导致反向切换。
- 服务端播放控制接受 `repeat=off|one|all` 与布尔 `shuffle` 的显式值；未提供目标值时保留旧 toggle 兼容行为。
- 新增 PlaybackCore 回归测试；本地 Python 109 项、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 真机 `vinson023.eu.org:5666/:3100` 仍不可达，本轮未宣称硬件、后台、息屏或多机验证完成。
- 修复 `src/cmd/install_callback` 覆盖安装时覆盖整个 `config.json` 的问题，改为保留既有 MPD、输出、DLNA 和用户配置，只更新安装向导字段；新增生命周期脚本回归测试。
- 重建 FPK：`artifacts/0.1.198/fnaudio-0.1.198-rebuild.fpk`，SHA-256 为 `17C5EE318C110EDF4D5097A1E83A5F57D7319F4EF5D23924A371BADDCBB816D8`。
- 备用机只读检查确认当前运行 `0.1.178`；CLI 安装 dry-run 被 App Center 自定义向导/UI-only 依赖拦截，未启动覆盖安装。
- 新增 `docs/APPCENTER_LIFECYCLE_0.1.198.md`，记录备用机的当前证据、UI 升级步骤和会话删除后的恢复路径。

## 0.1.199（真机目标 1–7 继续）

- 统一 FPK、Web UI 缓存版本、服务端 `Server` 头和 Android `versionCode/versionName` 到 `0.1.199`，用于强制触发 fnOS 覆盖升级。
- 通过 App Center UI 完成 FPK 覆盖更新，已安装列表可见 fnAudio，点击“打开”后界面可加载。
- 本地 Python 111 项、Android lint/Debug 构建通过；USB DAC 长时、热插拔、DSD 全矩阵、DLNA Renderer、Android 多机和完整生命周期仍按 TODO 保持未完成。

## 0.1.198

- 修复 `/api/playback/control` 未持久化 stop/pause/next/previous/play/seek 等控制结果的问题，避免 App Center 重启后恢复旧的播放状态。
- 控制接口返回播放会话 `revision`，便于前端和恢复流程确认状态已写入。
- 修正 `server.py` 的 `Server` 头和 `index.html` 静态资源缓存参数仍硬编码为 `0.1.197` 的版本漂移问题，统一到 `0.1.198`。
- 增加 Android release keystore 参数化配置；密钥只从 Gradle properties/环境变量读取，不进入仓库，Debug 构建行为不变。
- 已验证 `assembleRelease` 在无密钥时产出明确的 `app-release-unsigned.apk`；`apksigner verify` 拒绝该包，正式发布仍必须注入 release keystore。
- 新增回归测试覆盖停止状态持久化和发布版本一致性；Python 测试总数 107 项通过。
- 重新构建 `artifacts/0.1.198/` FPK 与 Android Debug APK。
- 0.1.198 已上传并通过 App Center UI 启动真机覆盖升级，但设备随后暂时失联，运行时版本尚待确认。

## 0.1.197

- DAC profile 增加 `track_settle_ms` 和 `keepalive_mode` 校验字段。
- 切换直连 ALSA 播放时先停止旧的 FFmpeg/aplay，再按 profile 等待，避免两个音频进程重叠导致 ALSA busy 和首帧卡顿。
- 增加可选的 MPD/FFmpeg `nice` 调度配置，默认保持 0，不改变既有设备行为。
- PCM keepalive 目前仅作为显式策略声明，默认关闭，Native DSD/DoP 不会被全局 keepalive 影响。
- 通过 fnOS App Center UI 将 `0.1.197` 覆盖升级到带 TEAC UD-301 的真机，应用状态确认 `running`，现有配置保留。
- 真机冒烟确认 PCM 播放/停止控制、TEAC UD-301 能力探测和 Native DSD64（DSF）源码播放；MPD 报告 `audio: dsd64:2`，未发生 PCM fallback。
- 真机长时间播放、物理热插拔、息屏后台、真实 DLNA Renderer 和 Android 多机型仍列为 P0 硬件验收目标，未提前标记为完成。

## 0.1.196

- 借鉴 Volumio 4 Stream Watchdog 的分层确认思路，为 MPD 增加 `IDLE/PLAYING/PAUSED/SUSPECT/RECOVERING/DEGRADED` 故障状态。
- 用户主动停止和歌曲自然结束不会触发故障升级；异常停止需要连续两次确认。
- 增加 MPD 状态平均耗时、故障次数、恢复次数和最近错误诊断字段。
- 新增 MPD 故障状态回归测试；Python 测试总数 103 项通过。

## 0.1.195

- 针对 USB DAC 播放时进度条、播放按钮和状态操作卡顿，拆分高频 MPD 播放状态与低频 ALSA 能力探测。
- `MpdService.output_capabilities()` 增加 4 秒缓存、过期后台刷新和设备切换失效机制；MPD 版本探测改为缓存。
- `/api/playback/status` 使用轻量 MPD 状态路径；前端增加远程状态请求防并发，并降低重复 UI 重绘。
- 本地 Python 100 项、Node UI 回归和 Android `assembleDebug` 通过；产物见 `artifacts/0.1.195/`。

## 0.1.194

- 修复 MPD 原生队列与逻辑队列在停止状态下不同步的问题；队列编辑同步支持 `play=false`，不会意外开始播放。
- 真机 TEAC UD-301 实测 DFF Native DSD，MPD 报告 `audio=dsd64:2`；384 kHz PCM 被明确拒绝且不隐式重采样。
- 同一真机补测 DSF Native DSD，MPD 同样报告 `audio=dsd64:2`，播放后队列可恢复。
- 使用 root 权限对 TEAC USB 节点 `1-4` 完成一次 unbind/bind 模拟拔插，MPD 自动停止并恢复当前歌曲、队列和 DAC 能力。
- 使用短测试曲验证 MPD 原生队列自然切歌，未执行前端 stop/clear/add 重建。
- 已通过 fnOS App Center 覆盖安装 0.1.194；停止状态同步后 MPD `playlistlength=2` 且保持 `STOP`，升级后队列和 DAC 标识均保留。

## 0.1.193（2026-08-09）

- 对照 Volumio 4 `mpdoutput` 的输出生命周期思路，修正 ALSA 能力探测在 MPD 持有设备时的状态抖动：如果此前已经成功完成 `hw_params`，后续 `-16 busy` 刷新会保留已验证的 PCM/Native DSD 格式，同时公开当前 busy 状态；从未验证过的设备不会被提升为已验证。
- MPD 输出能力增加 `dsd_advertised` 字段，用于表示 USB 驱动描述符声明的 DSD 能力；`native_dsd_verified` 继续只表示实际 ALSA 参数协商成功，避免把驱动广告误报为真实原生输出。
- 验证：Python unittest 99 项通过；新增 busy 探测保留/不提升回归测试。0.1.192 真机升级后队列保留、TEAC UD-301 可播放且 `underrun.count=0`；本修复以 0.1.193 重新部署。物理热插拔、Native DSD/DFF 矩阵、DLNA Renderer、AirPlay、Android 多机型仍待硬件验证。

## 2026-08-08：`0.1.189` 启动恢复与真实 transport 校验

- MPD 队列恢复加入 2/5/12 秒有界重试，覆盖 MPD 数据库启动竞态。
- 恢复播放后读取 MPD 实际 transport；DAC 不支持源格式导致 STOP 时，逻辑层回滚为 STOPPED 并保存状态。
- 真机 TEAC UD-301：44.1/192 kHz PCM、Native DSD64、384 kHz 拒播保护、stop/play/next 和 7 首队列恢复通过。
- Python 回归新增恢复重试和假 PLAYING 防护测试。

## 2026-08-08：`0.1.186` 发布收尾与版本一致性

- 修正 `src/app/ui/index.html` 的 CSS/JS 缓存参数和 `src/app/server/server.py` 的 `Server` 版本，避免升级后仍命中旧前端资源或报告旧版本。
- 重新生成 `SOURCE_MANIFEST.sha256`，重新构建 FPK，并核对 FPK 内层源码实际版本。
- Python 93 项、Node UI 3 项、Android lint/assemble 全部通过。
- FPK SHA-256：`45B10A74B51A111A4B78CCFAAC03B07AEC78DC00C7B4C531AB0DB6F4047CA46C`。
- App Center 列表虽显示 0.1.186，但运行进程仍报告 0.1.181；已记录为 fnOS 覆盖升级 payload 未替换问题，待进一步检查升级任务日志。

## 2026-08-08：`0.1.184` 播放能力边界与 underrun 可观测性

- DLNA 推送在 Renderer 明确声明不支持 DSD 时直接返回“设备不支持源码 DSD”，不再静默转码为 PCM。
- MPD underrun、broken pipe、ALSA error 和 audio output error 现在记录计数、最近错误、最近自动重启时间及被抑制次数，并通过 MPD idle 状态暴露。
- 参考 Volumio 的能力协商和播放守护思路；未知 Renderer 能力仍保持兼容尝试，避免误伤旧设备。

## 2026-08-08：`0.1.183` bit-perfect 采样率保护

- MPD ALSA 输出关闭自动重采样、自动格式转换和自动声道转换。
- 播放前依据真实 DAC 能力拒绝不支持的 PCM 采样率，避免 384 kHz 被静默降为 352.8 kHz。
- 真机 TEAC UD-301 验证：44.1 kHz PCM、DFF Native DSD（`dsd64:2`）正常；384 kHz 明确失败。
- 新增配置和不支持采样率回归测试，Python 测试总数 88 项。

## 2026-08-07：`0.1.175` DSD 源码直推

- DLNA DSD 资源不再强制转码为 96 kHz/24 bit WAV。
- DSF/DFF URL、MIME、扩展名、资源大小均来自原始文件；MediaServer 和 Renderer Push 强制 `original` 媒体模式。
- 浏览器播放仍保留显式 `dsd_wav` 转码能力，避免影响手机/浏览器兼容播放。
- 新增回归测试，确认 DSD 推送不会调用转码回调。

## 2026-08-07：`0.1.174` 服务生命周期与真机验收

- 修复 `src/cmd/main`：启动前清理旧版本遗留的 fnAudio `server.py`，停止时清理当前及遗留 MPD，防止旧 18080 与新 18081 双实例并存。
- 版本统一为 `0.1.174`，同步 FPK manifest、前端缓存键和 Android versionCode/versionName。
- 本地验证：62 个 Python 测试、3 个 Node 回归脚本、shell 语法、Android Lint/Debug 构建通过；正式 FPK 内层无 `.pyc`。
- 真机验证：单 server/单 MPD/无 zombie；健康、音乐库、浏览器控制、跨重启队列恢复、DSD WAV 96 kHz/24 bit 通过。
- 未完成：真实 USB DAC、DLNA Renderer 和多机 Android 安装矩阵仍需硬件/设备验收。

## 2026-08-07：`0.1.173` USB DAC、远程队列、DSD 与 Android 会话恢复

- 后端以 MPD 状态事件处理 USB DAC 自然结束和自动下一曲，显式停止/换曲加入事件抑制，避免误推进。
- Playback Core 不再在输出失败时乐观发布播放状态；直接 ALSA 启动补齐成功返回值。
- 前端远程 load 去重；恢复跨浏览器/Android 播放会话时读取服务端状态而不重复开播；MPD 自动下一曲不再依赖前端计时器。
- DSD DLNA 推送改为一致的 96kHz/24bit WAV PCM 资源声明，并尝试预装下一曲。
- Android 启动前验证并刷新 token，支持 longToken/保存密码回退；最低系统调整为 Android 6.0，兼容实现通过 Lint。
- 本地验证通过：62 个 Python 测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug`。未进行 fnOS、USB DAC、DLNA Renderer 或 Android 真机验收。

## 2026-08-07：`0.1.172` PC 右键菜单与文件夹定位语义修复

- 目标：PC 端右键菜单取消“播放”和“插播所选项目”，同时不影响移动端四项长按菜单和歌曲操作对话框。
- 修改文件：`src/app/ui/app.js`、`src/tests/test_ui_queue_columns.js`、版本与发布上下文文档。
- 菜单行为：新增 `desktopTrackContextActionButtons()`，桌面歌曲右键从完整歌曲操作中过滤 `play`/`insert`；文件夹/专辑等分组右键同步移除“播放”和“插播所选项目”；`trackContextActionButtons()` 继续只提供移动端四项快捷操作；`openTrackActionDialog()` 仍使用完整 `trackActionButtons()`。
- 文件定位：`openContainingFolder()` 继续读取 `api/library/location`，但只调用 `sdk.openFileManager(folder)`。fnOS 宿主的 `openFileManager` 接口接收目录路径；传入 `/vol1/.../歌曲.mp3` 这类完整文件路径会被解释为打开文件。当前未确认公开接口支持“打开父目录并自动选中文件”的额外参数，因此不伪造选中行为。
- 验证：`node --check app/ui/app.js`、`node tests/test_ui_queue_columns.js` 通过；真机 fnOS 文件管理视觉定位和 Android 安装尚未验证。
- 版本：统一到 `0.1.172`，后续产物记录在 `artifacts/0.1.172/`。

## 2026-08-07：`0.1.171` PC/移动菜单分离、文件定位、封面 fallback 与 Android 通知封面

- PC 端右键恢复完整歌曲操作菜单；移动端长按继续使用四项快捷菜单。
- “打开包含的文件夹”将完整歌曲路径传递给 fnOS 文件管理入口，便于直接定位文件。
- 歌曲行有真实封面时隐藏音乐符号；无封面统一显示 `♫`，DSD 不再使用单独符号，并在封面加载失败时恢复 fallback。
- Android Media3 新增 `AuthenticatedBitmapLoader`，同源封面请求附加 fnOS token Header/Cookie，结果写入应用私有缓存后交给通知栏 BitmapLoader；无封面继续使用白色占位图。
- 验证：59 个 Python 测试、JavaScript 语法、3 个 Node 回归脚本、Android Debug 编译通过；未连接 Android 真机。

## 2026-08-07：`0.1.170` Android 媒体卡片白色占位图标

- 目标：按截图把 Android 桌面/锁屏媒体卡片左侧的黑色默认播放图标改成白色，同时不覆盖真实歌曲封面。
- 通知图标：`PlaybackService` 显式配置 `DefaultMediaNotificationProvider`，将小图标设置为新增的白色描边播放圆环 `R.drawable.ic_notification`。
- 无封面占位：`NativePlaybackBridge` 在应用私有目录生成一次透明底、白色播放圆环的 512×512 PNG；无真实 `artwork` 时用文件 URI 写入 Media3 元数据，真实封面 URL 仍优先。
- 大队列保护：没有把 PNG 字节直接写进每一个 `MediaItem`，避免数千首队列重复携带位图并触发内存放大或 Binder 事务过大。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。APK 资源表包含 `drawable/ic_notification`，manifest 为 `0.1.170 / versionCode 170`，v2 Debug 签名有效；FPK 外层/内层为 21/110 项且无 Python 字节码。
- 产物：FPK `4,885,020` 字节，SHA-256 `3996D1E8E4E693EF889B46845F3ED59D677C5BD2B2A3295345485DDDD4FA7493`；APK `10,085,880` 字节，SHA-256 `1D4CE15B07B46289DC277A4EB26CCB7FFCA29488A6A1E29D41EC812C171A41BF`。
- 待验证：本轮没有连接 Android 真机；需分别播放无封面和有封面歌曲，确认媒体卡片/通知白色图标、真实封面优先、切歌更新以及后台/息屏行为。

## 2026-08-07：`0.1.169` 歌曲右键/长按四项菜单

- 目标：歌曲列表在桌面右键和移动端长按时，只显示“从当前开始播放所有歌曲、加入当前队列、收藏歌曲、加入播放列表”四项，并保持指定顺序。
- 交互：桌面继续使用 `contextmenu`；移动端新增 550ms Pointer Events 长按。手指移动超过 10px、触点取消或列表滚动会取消长按，触发成功后拦截随后生成的点击，避免松手时误播放。
- 菜单边界：新增独立 `trackContextActionButtons()`，不再把播放、插播、歌曲信息、打开文件夹、分享或页面移除操作混入右键/长按菜单；旧操作对话框保留原能力。
- 行为语义：“收藏歌曲”使用只添加的 `addSelectedFavorites()`，已收藏歌曲不会因菜单文字固定而被反向取消；“从当前开始播放所有歌曲”仍调用 `allTracksForCurrentContext()`，保持加载当前完整列表而非当前分页。
- 移动样式：菜单宽度限制在视口内，操作行提高到 44px，并关闭歌曲行文字选择和系统触摸呼出，降低 WebView 长按冲突。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 外层 21 项、内层 110 项且无 Python 字节码；APK manifest 为 `0.1.169 / versionCode 169`，v2 Debug 签名有效；包内 UI 文件哈希与源码一致。
- 产物：FPK `4,884,683` 字节，SHA-256 `E061CA3A761D7BA5E3F6C48604B700E340F938C372A3A90D02C8210C8E2EDD56`；APK `10,083,954` 字节，SHA-256 `EC2A690930E4560D003CBDF048857E3A75945101C57C1FA0BB559338EDBA7F02`。
- 待验证：本轮没有连接 fnOS/Android 真机；需在桌面浏览器和 Android WebView 验证右键/长按、滚动取消、松手不播放、完整列表入队、收藏只添加以及加入队列/歌单。

## 2026-08-07：`0.1.168` Android 多连接历史修复

- 目标：修复历史连接只能显示当前一条、登录第二个 NAS 会覆盖第一条的问题。
- 根因：登录页预填活动连接时保留其 UUID；用户修改服务器后，`ConnectionProfile.create()` 仍使用旧 UUID，`SecureProfileStore.upsert()` 因而删除旧行并写回新地址。
- 飞牛参考：本地 `FN_Media.apk` 的 Flutter 资源包含独立 `fn_connect` 连接模块和“手动添加”入口，说明选择已有设备与新增连接是两个明确动作。fnAudio 采用同样的交互原则，不复制其商业素材。
- 身份规则：规范化 host、端口、HTTP/HTTPS 和账号共同构成连接身份。普通表单改变身份会生成新 UUID；显示名、密码或证书选项变化更新匹配记录；完全相同身份复用已有记录，避免重复项。
- 历史页：新增“新增连接”按钮，返回空白表单；“编辑”显式保留所选 UUID，即使地址发生变化也只更新该记录。选择现有记录登录仍直接恢复对应连接。
- 验证：59 个 Python 测试、3 个 Node 回归脚本、JavaScript 语法、Android Java 编译、Lint 和 Debug APK 构建全部通过。FPK 为 21/110 个条目且无 Python 字节码；APK manifest 为 `0.1.168 / versionCode 168`，v2 Debug 签名有效。
- 产物：FPK `4,883,808` 字节，SHA-256 `F363B6C2E23CE7697ECF08E7C81CF7A296696199E3EECC732B8855FE83F30CD4`；APK `10,083,946` 字节，SHA-256 `A4736CE6F304084B87E9E95BF410051D9BC4E14CB9F649F732D650AD7CD35748`。
- 待验证：没有连接 Android 真机；需实际保存至少两个 NAS、编辑其中一个、重新登录相同连接并删除其中一条，确认记录互不覆盖。

## 2026-08-07：`0.1.167` Android 原生认证 API 与双击返回登录页

- 目标：修复 Android 播放仍提示“播放队列保存失败（HTTP 200）”，并把根页面返回改为第一次提示、第二次进入登录页。
- 真实根因：在测试 fnOS 上复现到 CGI 外层 nginx 返回 `HTTP 200 text/plain`，正文为 `invalid token`，请求没有进入 `cgi_proxy.py`。WebView 的 `shouldInterceptRequest()` 能代理 GET，但拿不到 POST body，因此队列、状态和控制 POST 绕过了已认证的 OkHttp 路径。
- 官方 App 对比：缓存的飞牛媒体 App 使用 Flutter/原生网络、WebSocket 和原生媒体服务持有认证及播放生命周期。fnAudio 沿用“WebView 界面 + 原生认证请求 + Media3 播放”的轻量架构，不复制官方商业素材或私有实现。
- 原生认证桥：`NativePlaybackBridge` 新增 `requestJson()`；`MainActivity` 只允许当前 NAS 的 fnAudio `/api/` 以及 POST/PUT/PATCH/DELETE，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和 token Cookie，通过 OkHttp 异步请求，再把状态、响应头和正文回传给网页。
- 网页 API：新增 `apiFetch()`、请求 ID/Promise 管理和 `fnAudioNativeOnHttpResponse()`。Android 环境的队列、用户状态、播放控制、转码预热、配置、共享目录同步和播放设备切换均走原生认证；普通浏览器继续使用标准 Fetch。
- 返回键：网页内部层级处理保持不变。根页面第一次返回显示“APP 即将退出，再按一次返回登录界面”，2.2 秒内第二次打开登录页并结束主页面；`EXTRA_SKIP_AUTO_RESUME` 阻止登录页立即自动重连。删除原有 `moveTaskToBack(true)` 根页面逻辑。
- 测试：59 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 与 `assembleDebug` 全部通过。FPK 外层 21 项、`app.tgz` 110 项且无 Python 字节码；APK manifest 为 `com.fnaudio.client / 0.1.167 / versionCode 167 / minSdk 26 / targetSdk 36`，v2 Debug 签名通过。
- 版本与产物：`fnaudio-0.1.167.fpk` 为 `4,884,107` 字节，SHA-256 `A5F5CF912C2477F1597D288201B5386552206B97870C49D1992D72D9741700DD`；`fnaudio-android-0.1.167-debug.apk` 为 `10,111,653` 字节，SHA-256 `5723CDAE06C7D94FCCD1B5D3E705D33AFC3165157996FFB23FE1C7DFB020FC34`。
- 待验证：本轮没有连接 Android 设备，不能宣称手机端播放和返回键已完成真机验证。需配套安装 `0.1.167` FPK/APK，至少播放两首歌曲，并确认第二次返回后登录页不会自动重连。

## 2026-08-07：`0.1.166` CGI 队列路由与 Android 返回修复

- 目标：修复播放时出现“播放队列保存失败（HTTP 200）”，以及 Android 系统返回键进入登录页的问题。
- CGI 路由：`cgi_proxy.py` 新增统一路径恢复，按显式 `X-FnAudio-Path`、`REQUEST_URI`、`PATH_INFO` 的顺序提取 `/index.cgi` 后的真实 API 后缀。播放队列 POST 主动携带 `/api/playback/queue` 路由 Header，即使 fnOS 只提供脚本级 `PATH_INFO`，也不会误代理到 HTML 首页。
- 前端诊断：队列响应先读取文本再解析 JSON；如果 CGI 回退返回 HTML，会显示“播放队列请求返回了错误页面”，不再把 HTTP 200 伪装成普通接口失败。
- Android 返回：登录成功启动 `MainActivity` 后立即结束 `LoginActivity`。系统返回键先调用网页 `fnAudioHandleAndroidBack()`，依次关闭对话框、上下文菜单、移动侧栏、歌词和嵌套分类；根页面只把应用任务移到后台，不调用可能进入 fnOS 登录/系统入口的 `WebView.goBack()`。
- 测试：新增 CGI `REQUEST_URI` 和显式路由 Header 回归；Android bridge 脚本同时检查网页返回入口、`MainActivity` 后台化逻辑与登录 Activity 出栈。59 个 Python 单元测试、3 个 Node 回归脚本、`node --check`、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一为 `0.1.166`。`artifacts/0.1.166/fnaudio-0.1.166.fpk` 为 `4,883,638` 字节，SHA-256 `03993A17CA0E87BA063BFBE6764847B0650A0743BA6D5B5827C9913DA95FBD53`；`fnaudio-android-0.1.166-debug.apk` 为 `10,105,834` 字节，SHA-256 `84A476C8F62A68955A52A385A37D4E4DF71103A8FED514452753CF042F8B3909`。
- 包验证：FPK manifest 为 `fnaudio / 0.1.166 / x86`，外层 21 个条目、`app.tgz` 110 个条目且无 Python 字节码缓存；APK 为 `com.fnaudio.client / 0.1.166 / minSdk 26 / targetSdk 36`，Android Debug 证书的 v2 签名通过。
- 待验证：当前未连接 fnOS 或 Android 真机；必须在配套安装 FPK/APK 后确认真实 CGI POST 返回 JSON、队列播放成功、返回键顺序正确、重新打开应用仍保持 fnAudio 页面，以及后台/息屏跨曲不回归。

## 2026-08-07：`0.1.165` Android 刘海安全区、默认端口与大队列播放修复

- 目标：修复登录界面顶部空间不足、fnAudio 主页面与状态栏/前置摄像头区域重叠，以及大音乐库播放时弹出“播放队列保存失败”。
- Android 窗口：新增 `WindowInsetsHelper`，登录页、历史连接页和主 WebView 宿主根据系统状态栏、导航栏与 `displayCutout` 自动增加安全内边距；主页面使用浅色状态栏图标，登录/历史页保持深色状态栏。
- 登录页：端口输入框默认直接显示 `5666`，移除“HTTP 常用 5666、HTTPS 常用 5667”的提示；切换 HTTPS 时仅在当前端口仍为默认值时切换到 `5667`，避免覆盖用户手动输入。
- 播放队列：前端 `/api/playback/queue` 只发送歌曲 ID，不再发送完整歌曲对象；服务端同时兼容 ID 列表和历史对象格式。这样“从当前开始播放所有歌曲”在大曲库/CGI 网关下的请求体显著减小，失败提示也会显示 HTTP 状态或服务端返回消息。
- 测试：新增紧凑队列 ID 的服务端单元测试和 Android bridge 静态回归检查；57 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 全部通过。
- 版本与产物：统一升级为 `0.1.165`。`artifacts/0.1.165/fnaudio-0.1.165.fpk` 为 `4,880,353` 字节，SHA-256 `7D134D517321F6C8A247A1F75D5B2B1FCE2AB3BB897FA5E2AE6651281A6C2E97`；`fnaudio-android-0.1.165-debug.apk` 为 `10,079,754` 字节，SHA-256 `569B0A1F6D6FB21A186B5C477920EE01CE7D94FA0775DDC4B8BF5A6B4EBFBDE5`。
- 待验证：尚未安装到真实 Android/fnOS 设备；需重点确认不同刘海/挖孔机型的登录和主页面顶部位置，以及大队列播放、自动下一曲和后台息屏播放。

## 2026-08-07：`0.1.164` WebView 子资源鉴权与 FPK/Android 图标统一

- 目标：修复 Android 登录后页面只显示无样式 HTML、CSS/JS/封面和 GET API 资源无法携带 fnOS 会话的问题，并处理启动图标中间音符过大被裁剪、Android 图标与 FPK 不一致的问题。
- WebView 资源：`MainActivity` 对同源 GET 子资源通过 OkHttp 重新请求，统一附加 `Authorization`、`X-Fnaudio-Trim-Token` 和兼容 token Header；响应 `Set-Cookie` 同步回 WebView CookieManager；对 `/cgi/ThirdParty/fnaudio/app.css` 等缺少 `/index.cgi/` 的路径增加兜底重写。
- CGI 入口：`cgi_proxy.py` 在 HTML 入口服务端注入 `<base href="/cgi/ThirdParty/fnaudio/index.cgi/">`，防止不同 WebView 对内联脚本/CSP 的处理差异导致相对资源解析到错误目录。
- 登录与历史页：保留参考 `FN_Media.apk` 的卡片式深色布局、独立历史连接页面、保存密码和删除确认交互；参考 APK 只用于行为和字段设计，没有复制其商业素材。
- 图标：Android 普通图标和 adaptive icon 改为白色圆角底 + 蓝色音符，与 FPK `src/ICON_256.PNG` 保持一致；前景音符缩放到 `0.68`，留出自适应图标安全区域。
- 版本与产物：统一升级为 `0.1.164`。`artifacts/0.1.164/fnaudio-0.1.164.fpk` 为 `4,882,412` 字节，SHA-256 `C114A0F9360F9E6D12C3487D2543F751F958B3E1B8E42362E4273591F66D62F5`；`fnaudio-android-0.1.164-debug.apk` 为 `10,078,542` 字节，SHA-256 `81831D01106DADAB2A2C39DCDA305228F7F809BD7D44FFC7126D16F23500B089`。
- 验证：55 个 Python 单元测试、3 个 Node 回归脚本、Android `lintDebug` 与 `assembleDebug` 通过；FPK 外层 21 个条目、内层 `app.tgz` 110 个条目可读取；APK manifest 为 `com.fnaudio.client / 0.1.164 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过。
- 待验证：尚未安装到真实 fnOS/Android 设备；需重点确认启动器图标显示、登录后 CSS/脚本/封面加载、保存密码与历史切换，以及后台/息屏跨曲播放。

## 2026-08-07：`0.1.163` Android 登录、历史连接、启动图标与 WebView 资源修复

- 目标：按真机截图修复 Android 启动图标白色外框、登录后 fnAudio 只显示无样式 HTML 的问题；允许安全保存密码，并把历史连接从登录页移到独立选择页面。
- WebView 根因与修复：部分入口最终 URL 是不带结尾斜杠的 `/cgi/ThirdParty/fnaudio/index.cgi`，相对的 `app.css`、`app.js` 和 API 路径因此解析到了 CGI 同级目录。`index.html` 现在会在检测到 `/index.cgi` 时、首个样式请求前写入以 `/index.cgi/` 结尾的 `<base>`；直接访问本机 TCP Web 服务时保持原路径。
- Android 登录与存储：`ConnectionProfile` 新增密码字段，与连接地址、账号和 token/longToken 一起进入 Android Keystore AES-GCM 加密载荷；`android:allowBackup=false` 保持不变。令牌恢复失败后会自动使用已保存密码登录，日志和界面不会显示明文。
- 历史连接：登录页只保留“历史连接”按钮；新增独立 `ConnectionHistoryActivity`，可选择连接、进入编辑或删除本机加密资料。
- 图标：launcher 改用 Android adaptive icon，蓝色背景由系统蒙版裁切，白色音符作为前景，避免 legacy 图标被启动器再次套白色圆角底框。
- 版本与产物：统一升级为 `0.1.163`。`artifacts/0.1.163/fnaudio-0.1.163.fpk` 为 `4,882,182` 字节，SHA-256 `DA31F9DFF9974A416CBB088CD30C8530D00D1AAF25BD6AC4DCFC04D0933856C2`；`fnaudio-android-0.1.163-debug.apk` 为 `10,071,583` 字节，SHA-256 `7DD22857DE994B89E8877FE38890A5972733938CA2A989219B8F4E660C4ED053`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JavaScript 语法、Android `lintDebug` 和 `assembleDebug` 通过；APK manifest 为 `com.fnaudio.client / 0.1.163 / minSdk 26 / targetSdk 36`，v2 Debug 签名验证通过；FPK manifest 为 `fnaudio / 0.1.163 / x86`，外层 21 个条目、内层 `app.tgz` 110 个条目可读取。
- 待验证：尚未安装到真实 fnOS/Android 设备。需重点确认启动器图标显示、保存密码后的切换/删除、令牌失效自动登录、CSS/脚本正常加载，以及后台/息屏跨曲播放。

## 2026-08-06：`0.1.162` Android 混合客户端与原生后台播放

- 执行者：Codex
- 目标：开发轻量 Android 客户端，由 WebView 复用 fnAudio 界面，由 Android 原生服务负责队列和播放；支持输入地址、端口、HTTPS、账号密码以及多连接历史，登录后直接打开 fnAudio。
- Android 工程：新增 `android-client/`，使用 Java 17、AGP 9.3.1、Gradle 9.6.1、Media3 1.10.1、ExoPlayer 和 OkHttp。
- 登录与历史：通过 `ws(s)://<host>:<port>/websocket?type=main` 发送 `user.login`，兼容 `user`/`username`；历史恢复尝试 `user.authToken` 和 `user.tokenLogin`。Android Keystore 加密保存地址、账号和 token/longToken，不保存密码。
- WebView：登录后直接加载 `/cgi/ThirdParty/fnaudio/index.cgi/`，初始请求携带 Authorization/Header，并设置同源 token Cookie；异常跳转到桌面/系统入口时显示重新登录提示。
- 原生播放：新增 `PlaybackService` 和 `NativePlaybackBridge`。Web UI 在 Android 桥存在时把完整队列、当前项、播放/暂停、前后曲、seek、音量、循环和随机交给 MediaController；MediaSessionService 持有 ExoPlayer 队列、自动下一首、通知、媒体键、音频焦点、耳机拔出和唤醒锁。
- fnOS 配套：`app.js` 保留普通浏览器 HTML audio 路径，同时增加原生状态回传和恢复逻辑；`cgi_proxy.py` 增加同源 Cookie token fallback。版本同步更新为 `0.1.162`。
- 构建产物：`artifacts/0.1.162/fnaudio-0.1.162.fpk`，SHA-256 `7253729113AEA07F55B93372EDC78BFE4E04E4EB991D71B3EFADEABD8C17CB9A`；`fnaudio-android-0.1.162-debug.apk`，SHA-256 `17898F32B6824C152AF5AA7DE34CE7F8C160547E1BB82028164D785A619C6EF9`。
- 验证：53 个 Python 单元测试、3 个 Node 回归脚本、JS/Python 语法、Android `lintDebug`、`assembleDebug`、APK v2 签名、APK manifest、FPK 外层/内层结构和关键源文件哈希均通过。
- 未验证：当前无 ADB 设备连接，尚未安装 APK/FPK；fnOS 登录 token 到 CGI 的真机交接、2FA/HMAC 固件、自签名 HTTPS、后台/息屏跨曲、通知/锁屏/蓝牙控制、多连接切换和厂商省电限制均待验证。当前 APK 是 Debug 签名，不是正式发布包。

## 2026-08-06：`0.1.161` 虚拟键盘直接覆盖固定播放器

- 目标：让移动端输入法直接覆盖底部歌曲信息和播放控制区域，避免隐藏恢复逻辑及播放器随键盘移动造成的掉帧。
- 修改：搜索期间播放器始终保持 `position:fixed` 和 `display:grid`；保留 viewport 的 `interactive-widget=overlays-content`，并在 WebView 支持时设置 `navigator.virtualKeyboard.overlaysContent = true`，不支持或拒绝写入时安全降级。
- 性能：搜索聚焦期间暂停歌曲信息跑马灯、阴影和过渡，并跳过跑马灯尺寸及移动分页位置测量；失焦后统一恢复一次，避免键盘动画中的同步布局读取。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.161/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.161`；`artifacts/0.1.161/fnaudio-0.1.161.fpk`，4,879,924 字节，SHA-256 `427CA1E87EB6030413B11453AF6D120D6B113C1B2835A54260F4F060342CB875`。
- 设备验证：按用户此前要求不代为安装，由用户自行安装测试；输入法覆盖模式、动画流畅度和不支持 Virtual Keyboard API 时的降级行为仍需真机确认。

## 2026-08-06：`0.1.160` 搜索期间保持移动播放器可用

- 目标：修复搜索时隐藏底部歌曲信息和播放控制区域后，部分移动 WebView 无法再次打开播放器的问题。
- 根因：`0.1.159` 通过输入框 `focus` 隐藏播放器，并依赖 `blur` 恢复；部分 WebView 在收起虚拟键盘后不会可靠触发 `blur`，播放器因此永久保持隐藏状态。
- 修改：播放器在搜索期间始终保持 `display:grid`，只切换为绝对定位；暂停歌曲信息跑马灯，关闭阴影和过渡以降低输入法动画期间的重绘；viewport 增加 `interactive-widget=overlays-content`。保留焦点状态类用于性能样式，不再用于播放器显隐。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.160/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过；包外层 18 个文件、运行时 97 个文件，未包含测试、数据库或 Python 缓存。
- 版本与产物：`0.1.160`；`artifacts/0.1.160/fnaudio-0.1.160.fpk`，4,880,027 字节，SHA-256 `E224641A09A05F5352BA0A24F02F098CB5E33CE967CA4619E855CE5D740F54CE`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度、键盘覆盖行为和播放器可操作性仍需真机确认。

## 2026-08-06：`0.1.159` 移动分页居中与输入法性能优化

- 目标：移动分页信息和按钮居中显示，并消除搜索输入法弹出时底部播放器上移造成的卡顿。
- 修改：移动分页容器和按钮组改为整行居中，页码摘要取消继承的 `flex:1`；搜索获得焦点时一次性隐藏播放器并扩展内容区，失焦后恢复，不监听键盘动画期间的连续 resize。
- 文件：`src/app/ui/app.css`、`src/app/ui/app.js`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.159/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.159`；`artifacts/0.1.159/fnaudio-0.1.159.fpk`，4,879,931 字节，SHA-256 `E20A98721E436D6497C19FD0AA15E3B27AD495E8BB180C9B225E8ED9A467CB43`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；输入法动画流畅度仍需真机确认。

## 2026-08-06：`0.1.158` 移动搜索返回主页面

- 目标：把移动搜索栏恢复到主页面顶部，并移除左上角更多菜单中的返回按钮。
- 修改：主内容列表上方新增独立 `type=search` 输入，提供搜索图标、圆角容器、聚焦高亮和原生清除；侧栏恢复为纯导航结构，删除 `mobileBackBtn`、相关样式和 `handleMobileBack()`。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/app/ui/app.js`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.158/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.158`；`artifacts/0.1.158/fnaudio-0.1.158.fpk`，4,879,685 字节，SHA-256 `973795FCA58069CA66CDFE66FDFA168DE8E4E0C63ADD59ACA2E2842DCA379EF2`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.157` 移动搜索与返回布局重构

- 目标：解决移动侧栏中搜索框被返回按钮挤压、输入空间不足的问题，同时明确返回按钮的位置和视觉。
- 修改：第一行使用 `32px + 1fr` 网格放置返回图标与“音乐库”标题；第二行搜索框横跨两列、占满侧栏宽度；返回按钮改为带边框的 SVG 箭头按钮。桌面端仍保持搜索框在导航标题之前。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.157/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.157`；`artifacts/0.1.157/fnaudio-0.1.157.fpk`，4,880,068 字节，SHA-256 `DE79ED0FD54E147B3EEA7CD746078496F012DBDC3A4F55B89BD55D79AB3B609C`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.156` 移动歌词页顶部布局压缩

- 目标：减少移动端歌词界面顶部空白，使返回、歌曲信息、收藏和歌词首屏布局更紧凑合理。
- 修改：移除歌词页对 `safe-area-inset-top` 的重复网格行高与 padding 计算；标题栏固定为 `48px`，三列宽度改为 `52px / 1fr / 52px`，按钮缩小为 `50x30px`；歌词面板顶部 padding 调整为 `8px`。
- 文件：`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.156/` 和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.156`；`artifacts/0.1.156/fnaudio-0.1.156.fpk`，4,879,848 字节，SHA-256 `978A582966255E14AF0694685697596FB67A2019EC72FA1DA481E2BFE06BD28F`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试。

## 2026-08-06：`0.1.155` 移动侧栏顶部压缩

- 目标：按移动端截图缩小侧栏及顶部返回、搜索、“音乐库”区域的占用。
- 修改：移动侧栏最大宽度由 `290px` 收窄到 `268px`；返回按钮和搜索框放入同一行；侧栏顶部改为固定紧凑留白，“音乐库”标题紧随工具行。
- 文件：`src/app/ui/index.html`、`src/app/ui/app.css`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.155/` 归档记录和项目恢复文档。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归、移动布局回归和 FPK 结构校验均通过。
- 版本与产物：`0.1.155`；`artifacts/0.1.155/fnaudio-0.1.155.fpk`，4,879,937 字节，SHA-256 `D8FA806C30C6B3CA0C80592CAF4C66CBB02A75230FEDBEAF961E059D626C6474`。
- 设备验证：按用户要求不代为安装，由用户自行安装测试；浏览器安全策略不允许直接渲染本地 `file://` 页面，因此未宣称完成截图级或真机视觉验收。

## 2026-08-06：`0.1.154` 移动端菜单与分页体验优化

- 目标：压缩移动侧栏返回和搜索占用；从右下角更多菜单移除歌词；歌曲列表分页仅在确有多页且滚动到底部时显示。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`，以及 `artifacts/0.1.154/` 归档记录。
- 实现：返回改为紧凑图标按钮，侧栏顶部和搜索框高度/间距缩小；移动更多动作不再生成歌词项；分页 `pages <= 1` 时完全不渲染，移动端分页栏默认隐藏，列表滚动到底部后显示。
- 版本与产物：`0.1.154`；`artifacts/0.1.154/fnaudio-0.1.154.fpk`，4,879,719 字节，SHA-256 `81562B56F54490F8C1E84E3D06B76606E2D44AF7B94649C365B364F4B464C2A9`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列回归和移动端布局回归均通过；包内 manifest、缓存键和 97 个运行时文件已校验。
- 设备验证：尚未完成。fnOS 应用中心手动安装需要自定义向导参数，官方 `trim-cli app install-fpk` 已连接设备但返回该安装限制，设备仍运行 `0.1.153`。

## 2026-08-06：`0.1.153` 移动端初始化修复与 fnOS 验收

- 目标：完成移动端布局修复后的可安装发布，避免移除移动搜索输入后阻断初始化，并记录真实设备结果。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/app/ui/index.html`、`src/tests/test_ui_mobile_layout.js`、`VERSION`、`src/manifest`、`SOURCE_MANIFEST.sha256`，以及当前恢复/发布文档和 `artifacts/0.1.153/` 验收记录。
- 实现：对可选的 `mobileSearchInput` 增加存在性守卫；移动端使用侧栏搜索和返回入口，移除顶部分类栏，固定分页区域并让歌曲列表独立滚动，歌词页顶部采用不重叠的三列控件布局。
- 版本与产物：`0.1.153`；`artifacts/0.1.153/fnaudio-0.1.153.fpk`，4,879,159 字节，SHA-256 `A2214FD1A07513634229EAF2A91A685EE60AD56FED25F2BF66CDB6AE62BDB3F0`。
- 本地验证：50 个 Python 单元测试、JavaScript 语法检查、队列/专辑列 Node 回归和移动端布局 Node 回归均通过；FPK manifest、缓存键、内容清单和哈希一致。
- 设备验证：已完成 fnOS 应用中心 `0.1.152 -> 0.1.153` 覆盖升级，状态为 `running`，`/api/health` 正常；移动视口烟雾确认菜单搜索/返回、分类移除、列表滚动容器、分页栏和歌词头部不重叠。
- 未验证：设备音乐库为 0 项，真实长列表手势、分页按钮操作、歌词实际播放状态及“从当前开始播放全部歌曲”全流程；全新安装、停止/启动、卸载、硬件和 DLNA 互操作也未覆盖。

## 2026-08-06：`0.1.152` 移动端布局验收包

- 生成 `artifacts/0.1.152/` 作为移动端布局的中间 FPK，保留其本地测试、结构检查和设备升级记录；当前开发基线随后推进到 `0.1.153`。

## 2026-08-06：`0.1.151` 队列当前曲目同步与设备验收

- 目标：让“正在播放”只显示在当前播放队列，并在切换歌曲后立即同步标识、分页和滚动位置。
- 修改文件：`src/app/ui/app.js`、`src/tests/test_ui_queue_columns.js`、`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.151/` 验收记录。
- 实现：当前项样式仅在 `state.view === "queue"` 时显示；新增队列展示同步入口，由播放核心快照、远端播放无当前项和本机 CUE 自动切歌共同调用。索引变化时会重新计算目标页、重渲染，并在下一帧滚动到当前行。
- 版本与产物：`0.1.151`；`artifacts/0.1.151/fnaudio-0.1.151.fpk`，4,878,955 字节，SHA-256 `05CC22B336A9AC821B0166A31D401B0383A425DA88679CA928604F8FCBB6A039`。
- 本地验证：50 个 Python 单元测试、`node --check app/ui/app.js` 和 `node tests/test_ui_queue_columns.js` 通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和静态资源缓存版本均为 `0.1.151`。
- 设备验证：已通过 fnOS 应用中心完成 `0.1.150 -> 0.1.151` 覆盖升级，设备状态为 `running`，保留 228 首音乐、队列和播放状态。打开当前队列显示一个当前曲目标识；点击下一曲后队列即时跳到新曲目所在页，标识随新曲目移动；非队列视图不显示该标识。
- 未验证：全新安装、端口变更、停止/启动、两种卸载、USB DAC、移动 WebView、DLNA 互操作和“从当前开始播放全部歌曲”完整设备端流程。

> 规则：按时间倒序追加。记录目标、实际文件、行为变化、验证和遗留问题。不要只写“已修改”。

## 2026-08-06：建立 Git `0.1.150` 基线

- 执行者：Codex
- 目标：把 `C:\path\to\fnAudio` 从无版本历史的目录转为可恢复、可审计的 Git 工作树。
- 修改文件：新增 `.git/` 元数据；更新 `.gitignore`、根恢复文档和技术决策。
- 版本控制范围：提交当前源码、文档、完整性清单和必要构建工具；排除 FPK、历史 staging、派生包检查目录、运行时缓存/数据库/凭据，以及嵌套第三方 Git 仓库。
- 结果：创建 `main` 分支的初始 `0.1.150` 基线提交，并标记 `v0.1.150`。
- 后续：本地仓库尚无远程备份；应在确认托管位置与访问控制后推送到私有远程仓库。

## 2026-08-06：构建 `0.1.150` FPK

- 执行者：Codex
- 目标：为已完成的队列定位和专辑序号列功能生成可安装 FPK，并将当前源码版本升级为 `0.1.150`。
- 修改文件：`VERSION`、`src/manifest`、`src/app/ui/index.html`、`SOURCE_MANIFEST.sha256`，以及根目录恢复文档和 `artifacts/0.1.150/` 归档记录。
- 版本行为：FPK manifest、根版本标识和 `app.css`/`app.js` 缓存键均为 `0.1.150`；没有修改播放、音乐库或协议行为。
- 产物：`artifacts/0.1.150/fnaudio-0.1.150.fpk`，4,878,790 字节，SHA-256 `B70EAEE3913AC9AEE8C5CE003C5CC409BC8CF535960B702C19398B593F1A8660`。
- 验证：50 个 Python 单元测试、Node 前端回归和 JavaScript 语法检查均通过；外层 FPK 与内层 `app.tgz` 可读取，manifest 和前端资源版本为 `0.1.150`，运行时负载包含 97 个文件且排除测试、缓存、数据库和 Python 字节码。
- 未验证：未安装到 fnOS 真机。`0.1.149` 设备验证不覆盖本包新增的当前队列定位和专辑详情序号列，需单独真机验收。

## 2026-08-06：当前队列定位与专辑序号列

- 执行者：Codex
- 目标：打开当前播放队列时直接定位正在播放的歌曲并提供清晰标识；在所有专辑详情的曲目列表默认首列显示“序号”。
- 修改文件：`src/app/ui/app.js`、`src/app/ui/app.css`、`src/tests/test_ui_queue_columns.js`、`SOURCE_MANIFEST.sha256`。
- 队列行为：底部播放器和导航中的当前队列入口都会清除列表筛选；根据当前排序计算当前项所在页，渲染后滚动至行中部。队列行携带原始队列位置，重复曲目只会在真实当前位置显示“正在播放”标签。
- 专辑行为：专辑、歌手专辑和作曲者专辑详情共用 `albums:tracks:*` 列作用域，新的默认列为“序号、标题、歌手、专辑、大小、格式”；保存的旧默认列会自动迁移，明确自定义的列配置不被覆盖。
- 验证：`python -B -m unittest discover -s tests -v` 通过（50 个测试）；`node --check app/ui/app.js` 通过；`node tests/test_ui_queue_columns.js` 通过，覆盖重复 ID 队列项的正确页定位及旧专辑列默认值迁移。
- 未验证：本轮未构建或安装新 FPK，fnOS WebView、实际长队列滚动和专辑详情的真机视觉效果需要在下一个更高测试版本中验收。

## 2026-08-06：评估并缓存第三方 `FNOS-API`

- 执行者：Codex
- 目标：对照 `heijiangangqin/FNOS-API` 与飞牛官方开发/API 文档，判断其是否能帮助 fnAudio 后续开发，并在有价值时保留可恢复本地快照。
- 应用源码修改：无。未修改 `src/`、未安装该第三方应用、未建立 NAS 会话、未写入任何凭据。
- 缓存：以浅克隆方式保存到 `references/FNOS-API-upstream`，固定提交 `33101767e01a7f413cac5e0ed016f6a9483df526`（`main`，2026-07-21），工作树干净。
- 结论：该项目是 Node.js/Express 对 `trim-cli` 的 REST 封装，适合外部验收、应用中心操作对照、日志导出和设备监控参考；它不提供 fnAudio 所需的媒体/播放能力，也不能取代官方 Scope、ACL、JS SDK 和本地 open-gateway 机制。
- 风险：服务监听 `0.0.0.0:9932`、启用全域 CORS、默认 Bearer token、未受 token 保护的登录路由、明文 NAS 凭据，以及大量自动确认的破坏性管理操作。因此明确禁止作为 fnAudio 依赖或内部 HTTP 服务。
- 文档：新增 `references/FNOS_API_EVALUATION.md`，并更新参考索引、项目上下文和技术决策。

## 2026-08-06：`0.1.149` 临时升级包真机验收

- 执行者：Codex
- 目标：在不卸载现有应用、不清除用户音乐库或播放状态的前提下，验证本次优化后的 `0.1.148` 源码能否在真实 fnOS 上完成覆盖升级并启动。
- 应用源码修改：无。`C:\path\to\fnAudio\src`、`src/manifest` 和 `SOURCE_MANIFEST.sha256` 均未改动，正式开发基线仍是 `0.1.148`。
- 构建方式：复制 `src/` 至 `artifacts/0.1.149/stage/`，仅将 `manifest` 中的版本号改为 `0.1.149`，使用 `fnpack 1.2.3` 构建 `fnaudio-0.1.149.fpk`。
- 产物：`artifacts/0.1.149/fnaudio-0.1.149.fpk`，4,876,087 字节，SHA-256 `B7FD239E26D69AC16CE8C1F4B788AE6528F47E2DBA479FCC33B1CD9B0B507AA0`。
- 安装结果：fnOS 应用中心成功把 `fnaudio` 升级为 `0.1.149`，应用状态为 `running`；服务端口维持 `18081`，原音乐库配置和播放队列保留。
- 完成验证：设备端 `app.js`、`index.html`、`server.py`、`transcode.py` 与 `src/` 哈希一致；CGI 页面正常显示全部音乐；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 冒烟通过，音乐库为 228 首（含 5 首 DSD），MPD `0.23.12` 运行中。
- 专项验证：当前 FLAC 曲目 `d412eb7fd07a94df` 初始转码缓存未就绪，调用 `POST /api/transcode/warm` 后约 6 秒变为就绪；歌词页不再有 `lyricsQueueBtn`，点击底部队列按钮会关闭歌词页并转到当前队列。
- 未完成：未执行会改变现有队列和播放状态的“从当前开始播放全部歌曲”完整 E2E。全新安装、端口变更、停止/启动、卸载、USB DAC、移动 WebView、FFmpeg 压力和 DLNA 互操作也未在本轮覆盖。
- 文档：新增 `artifacts/0.1.149/{SHA256SUMS,PACKAGE_CONTENTS.txt,VALIDATION.md}`，并同步根目录恢复、待办、架构决策和产物索引文档。

## 2026-08-06：fnOS 真机安装尝试与环境冒烟测试

- 执行者：Codex
- 目标：将 `artifacts/0.1.148/fnaudio-0.1.148.fpk` 安装到用户提供的 fnOS 测试设备并进行基础验收。
- 应用源码修改：无。
- 安装结果：应用中心接受 FPK 上传并完成包解析；确认标准未验证第三方应用提示后，因设备已安装相同或更高的 `fnAudio 0.1.148` 而拒绝覆盖。未卸载、未覆盖或重启现有应用，未改动配置或音乐数据。
- 已发现状态：设备运行的同版本 `fnaudio` 核心文件哈希与当前源码不同，属于优化前代码，不能作为本 FPK 的验收实例。
- 环境验证：现有实例服务端口可访问；`/api/health`、`/api/library/status`、`/api/playback/core`、`/api/playback/targets`、`/api/mpd/status` 均返回 `HTTP 200`；CGI 页面正常加载音乐库，MPD 正在运行。
- 未完成：需要用户明确选择“保留数据卸载后重装当前 `0.1.148` FPK”或“创建更高的独立测试版本”后，才能完成本包的真机安装、升级、端口、启动停止和卸载验收。

## 2026-08-06：重建并归档 `0.1.148` FPK

- 执行者：Codex
- 目标：基于 `C:\path\to\fnAudio\src` 的当前 `0.1.148` 源码构建可安装 FPK，并保留可恢复的包身份和验证记录。
- 应用源码修改：无。
- 构建命令：在 `C:\path\to\fnAudio\artifacts` 执行 `C:\path\to\fnAudio\tools\fnpack.exe build --directory C:\path\to\fnAudio\src`，使用 `fnpack 1.2.3`。
- 产物：`artifacts/0.1.148/fnaudio-0.1.148.fpk`，4,878,142 字节，SHA-256 `856088E19DD926F0ACE2F07C0BB0E76526BB129F6A3A807A27EB2E27686EB4E1`。
- 记录更新：`README.md`、`PROJECT_CONTEXT.md`、`RECOVERY.md`、`TODO.md`、`artifacts/README.md` 以及版本产物目录中的校验文件。
- 验证：50 个 Python 单元测试通过；`node --check app/ui/app.js` 通过；`fnpack` 构建成功；外层 FPK 和内层 `app.tgz` 可读取；包内 manifest 是 `fnaudio / 0.1.148 / x86`，运行时负载中包含 server、UI、CGI、MPD 和运行库，未包含测试、历史 builds、缓存或本地数据库。
- 未验证：尚未在真实 fnOS 设备执行全新安装、升级、改端口、进程生命周期和卸载验证。

## 2026-08-06：歌词导航、当前曲目缓存与全量队列修复

- 执行者：Codex
- 目标：修复歌词页队列返回、优先缓存当前播放曲目，以及“从当前开始播放”没有完整装载列表的问题。
- 修改文件：`src/app/ui/index.html`、`src/app/ui/app.js`、`src/app/server/transcode.py`、`src/app/server/server.py`、`src/tests/test_transcode_cache.py`。
- 歌词页：删除顶部重复的队列按钮；底部播放器的队列按钮在歌词页打开时先关闭歌词视图，再切换到当前队列。
- 当前曲目缓存：新增 `POST /api/transcode/warm`。前端在本地 MP3 转码曲目设置媒体 URL 前请求缓存；后端将当前曲目放入优先级 `0` 的单工作线程缓存队列，普通媒体预热使用优先级 `100`。
- 全量队列：从当前曲目开始播放时队列保留完整上下文，服务端通过 `current_id` 定位当前曲目；收藏和歌单场景会补齐未缓存的曲目 ID 后再创建队列。
- 兼容性：原格式播放、DSD/CUE 转码、远程 DLNA 目标及既有 `/api/transcode/status` 行为保持不变。
- 验证：`python -B -m unittest discover -s tests -v` 通过，50 个测试；新增缓存优先级回归测试。`node --check app/ui/app.js` 通过。
- 未验证：尚未在真实 fnOS WebView、真实大歌单和实际 FFmpeg 转码负载下完成端到端验证。

## 2026-08-06：建立 `0.1.148` 可恢复项目目录

- 执行者：Codex
- 目标：把当前项目、文档和恢复上下文整理到 `C:\path\to\fnAudio`，避免依赖历史 AI 会话。
- 源码基线：`E:\Codex\fnaudio-0.1.7`，`manifest` 版本 `0.1.148`。
- 新建根文档：`README.md`、`PROJECT_CONTEXT.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`TODO.md`、`CHANGELOG_AI.md`、`RECOVERY.md`。
- 新建索引和策略：`docs/INDEX.md`、`docs/history/README.md`、`artifacts/README.md`、`.gitignore`、`VERSION`。
- 复制源码：将当前可继续开发的代码、测试、MPD 二进制和动态库复制到 `src/`。
- 归档文档：旧迁移说明、阶段 TODO、发布片段和原始分析归档到 `docs/history/`。
- 排除内容：根 `builds/`、旧版本源码、FPK 解包目录、参考仓库、旧 FPK、`app.tgz`、陈旧 `transcode/library.json` 未作为当前源码引入。
- 生成内容：`SOURCE_MANIFEST.sha256` 和 `docs/SOURCE_INVENTORY.md` 记录恢复快照身份。
- 产品行为变化：无。没有修改 Python、JavaScript、CSS、fnOS 配置或生命周期脚本内容。
- 原工作区变化：保留不动；此前只在原当前源码中新增过一份 `PROJECT_CONTEXT.md`。
- 验证：在 `C:\path\to\fnAudio\src` 重新运行 49 个 Python 单元测试，全部通过，耗时约 0.9 秒。
- 语法验证：`node --check app/ui/app.js` 通过；39 个 Python 文件 AST 解析通过。
- 一致性验证：136 个源码文件均能在原 `0.1.148` 来源中找到，SHA-256 差异为 0。
- 恢复验证：根目录必需文档无缺失，`VERSION` 与 `src/manifest` 均为 `0.1.148`，源码清单为 136 条，Markdown 代码块完整。

## 记录模板

```markdown
## YYYY-MM-DD：标题

- 执行者：
- 目标：
- 修改文件：
- 行为变化：
- 数据或兼容性影响：
- 验证：
- 未验证：
- 后续事项：
```

## 2026-08-08：播放栈对比与服务端远程 Renderer 改造

- 执行者：Codex
- 目标：对比 Volumio/moOde 的播放控制、MPD、USB DAC、DLNA/UPnP、AirPlay 和 Renderer 生命周期，并修复后台续播依赖前端的问题。
- 修改文件：`src/app/server/playback/models.py`、`plugins.py`、`core.py`、`mpd_client.py`、`mpd_output.py`、`services/mpd_service.py`、`services/airplay_service.py`、`dlna/control_point.py`、`dlna/media_server.py`、`server.py`、`src/app/ui/app.js`，以及对应测试和 `docs/PLAYBACK_STACK_COMPARISON.md`。
- 行为变化：MPD idle 状态现在回写统一 PlaybackCore；外部 DLNA Renderer 由服务端监控 transport 并自动推进队列；DLNA 设备能力缓存到发现结果；MPD status 增加 PCM/DSD stream 信息；AirPlay 缺依赖时明确返回不可用。
- DSD 策略：DLNA MediaServer 继续原始 DSF/DFF 直出；MPD 配置默认 `mixer_type none`、`dop no`，优先 native DSD，但 `native_dsd_verified` 保持 `false`，直到真实 USB DAC 验证。
- 验证：Python 新增状态桥、MPD stream、DLNA protocolInfo、AirPlay probe、Renderer URI 回归测试；已通过。完整构建和真机部署待本轮结束后执行。
- 真机部署：已在 `198.51.100.24` 从 0.1.175 升级到 0.1.177，保留 228 首歌曲/5 首 DSD 与现有队列；单一 server、单一 MPD 运行于 18081/56660。
- Renderer 验证：`DESKTOP-EEIDGH9` 的 FLAC push/pause/resume、设备侧 NextURI 和服务端队列回写通过；DSF 最终进入 PLAYING，HTTP 资源保持 `audio/x-dsf`、原始长度和 `DSD ` 文件头。
- 遗留限制：NAS 无 USB DAC，无法验证本地 native DSD；AirPlay 依赖缺失；Android 通知/锁屏仍需手机真机验证。
## 0.1.181 - MPD 崩溃恢复防误进下一曲

- MPD watchdog 恢复期间新增 15 秒 STOPPED 抑制窗口，避免进程崩溃/重启被误判为自然结束而跳到下一曲。
- 保留原队列、当前歌曲和最后位置恢复逻辑，并增加真机异常重启验证记录。

## 0.1.180 - 播放队列一致性修复

- 修复从音乐库直接点击一首不在前端已同步队列中的歌曲时，PlaybackCore 仍保留旧队列、MPD 实际播放旧曲但接口返回新曲的问题。
- `load` 现在会先将缺失的选中歌曲加入权威队列，再交给 MPD 镜像队列；这也让不支持的采样率/格式错误能够准确返回，而不是静默沿用上一首。
- 新增回归测试覆盖该场景。

## 0.1.179 - USB DAC 真机验证与稳定身份持久化

- 在 TEAC UD-301 真机读取 ALSA 实时 `hw_params`：44.1 kHz WAV 输出为 `S16_LE / 44100 Hz`，DFF 输出为 `DSD_U32_BE`，MPD 同时报 `dsd64:2`，确认 Native DSD 未转 PCM。
- 验证 MPD 镜像队列可自然切换到下一首，fnAudio 当前歌曲状态随 MPD 自主推进同步更新。
- 修复自动选择或旧 ALSA 编号迁移后只更新内存、不写回 `config.json` 的问题；稳定 USB DAC ID 与当前运行时 ALSA ID 现在会持久化。
- 移除 MPD 0.23 已弃用的 `buffer_before_play` 配置，保留 `audio_buffer_size` 与 DAC 启动延迟 quirk。
- 参考 Volumio 4 `Systeminfo/fusion` 的 libasound `hw_params` 探测思路，确认 fnAudio 当前 ctypes 探测结果与内核实时输出一致。
- 本地回归：85 项 Python 测试、3 项 Node UI 回归和 JavaScript 语法检查通过。

## 0.1.178 - 播放与 USB DAC 可靠性改造

- 增加 MPD 原生队列镜像、预加载、自然切歌回写和恢复。
- 增加稳定 USB DAC 身份、真实 ALSA `hw_params` 探测和设备级能力报告。
- 增加 Native DSD/DoP 协商，无法验证时阻止 PCM 兜底转码。
- 增加 USB 热插拔恢复、underrun 监控、有限重启、事务化输出切换和音频设备租约。
- 增加 DAC quirk profile 配置与 82 项 Python 测试、前端回归测试。
- 构建 FPK/APK：见 `artifacts/0.1.178/`。
## 2026-08-08：`0.1.185` 播放失败事务修复

- 修复播放中选择 DAC 不支持采样率（例如 384 kHz）时，ALSA busy 探测触发 MPD 停止的问题。
- PCM 不支持采样率优先依据稳定 DAC 描述拒绝，不中断当前歌曲。
- DSD 在无法验证 Native DSD/DoP 时明确拒绝并保持已有播放。
- 播放核心在输出打开失败时回滚当前歌曲、队列、进度和 transport 状态。
- 验证：Python 91 项全部通过。
## 2026-08-08：`0.1.186` MPD 队列恢复闭环

- 修复应用重启后只恢复 fnAudio 逻辑队列、没有恢复 MPD 原生执行队列的问题。
- 恢复 MPD 目标时重新镜像队列、当前歌曲、循环/随机模式和播放位置。
- 已停止的历史会话会先恢复队列再保持停止；播放中的历史会话恢复为播放状态。
- 新增 MPD 会话恢复回归测试。
## 0.1.190

- 新增 AirPlay Receiver supervisor 与 `/api/airplay/control` 控制接口。
- AirPlay 使用音频输出租约，和 MPD/DAC 互斥，异常退出可有限重启。
- 保持 DLNA DSD 源码推送与 USB DAC 热插拔/恢复策略。
## 0.1.194

- 修复 MPD 原生队列与逻辑队列在停止状态下不同步的问题。
- 队列编辑同步 MPD 时支持 `play=false`，不会因编辑队列意外开始播放。
- 增加停止状态队列同步回归测试。
- 真机 TEAC UD-301 实测 DFF Native DSD 播放，MPD 报告 `dsd64:2`；384 kHz PCM 被明确拒绝且不隐式重采样。
# 0.1.203（2026-08-10）

- 新增 MPD 解码错误分类：`source_corrupt`、`seek_error`、`decoder_unavailable`，并通过 `/api/mpd/status` 暴露结构化 `decoder_errors` 字段。
- Python 测试从 113 项增至 115 项，全部通过；Node UI 回归和 Android lint/build 通过。
- 生成 FPK、Debug APK 和 unsigned Release APK；FPK 已通过 fnOS App Center UI 覆盖安装到真实设备。
- 真机确认版本头、健康检查、音乐库、20 首队列、TEAC UD-301 Native DSD 能力和 underrun 状态均保持正常。
- 未将缺少真实硬件证据的小时级播放、息屏、热插拔、外部 Renderer、Android 多机型和正式签名列为完成。

## 0.1.203 真机长测补充（2026-08-10）

- 在 TEAC UD-301 上对原有 20 首队列执行约 5 分 30 秒、12 点采样的真实连续播放。
- 观察到第 1 首自然切换到第 2 首；全部采样保持 `PLAY`、`underrun=0`、`decoder_errors=0`。
- 测试结束恢复原来的第 20 首和 STOP 状态；短暂 ALSA busy 随后自动清除。
- 该结果只扩大跨曲短时证据，不改变小时级、息屏和热插拔目标的未完成状态。

## 0.1.204（2026-08-10）

- 修复 MPD 重启恢复后 idle transport 可能残留 `STOPPED`、而原始 MPD 已经 `PLAY` 的状态同步问题。
- 新增 `normalized_transport()`，恢复完成后主动同步 idle、fault、PlaybackCore 和状态监听器。
- 在真实 TEAC UD-301 上验证了 0.1.203 的 MPD supervisor 自动重启、20 首队列和当前曲目恢复；0.1.204 的同一矩阵待 App Center UI 安装后复验。
- Python 测试 117 项通过；FPK/APK 构建完成；正式签名仍未提供。
## 2026-08-11: 0.1.213 metadata cache and safe tag write

- Current playback now promotes its lyrics job ahead of library-wide metadata work.
- Lyrics, album artwork, and release date are cached independently, then coalesced into one low-priority `tag_write` job per track.
- Tag writes are serialized with a two-second interval and use a temporary file plus atomic replacement. MP3, FLAC, M4A, and MP4 are supported; DSD and CUE tracks are deliberately skipped.
- Embedded lyrics are read before contacting external lyric providers. Missing song artwork continues to use the centered music-note fallback.
- Verification: 138 Python tests, JavaScript syntax validation, and Android bridge regression checks passed. Real media-file writes on fnOS remain to be validated with a disposable music file.
## 2026-08-11: go-music-dl provider live validation

- Ran the actual `go-music-dl` provider registry against live network endpoints, using returned song and album IDs for the dependent lyrics and album-detail calls.
- Registered scope: 12 online providers plus `local`; full JSONL evidence is stored in `artifacts/go-music-dl-provider-smoke-20260811.jsonl`.
- Confirmed complete search-to-lyrics flows for NetEase, QQ, Kugou, Migu, JOOX, and Qianqian. Confirmed complete album flows for NetEase, QQ, Kuwo, Jamendo, JOOX, Qianqian, and Soda.
- Apple is currently blocked by failed dynamic token extraction; Soda song search currently fails because its response can no longer be parsed. These results are not inferred from mocks.
- Added the reproducible source matrix and test contract to `docs/GO_MUSIC_DL_PROVIDER_VALIDATION.md`. No fnAudio runtime code, package version, FPK, or APK was changed by this validation-only task.

## 2026-08-11: metadata provider migration

- Removed Spotify runtime integration: OAuth token exchange, API search, configuration defaults and persistence, metadata status fields, settings controls, client-side save/clear actions, and API handling.
- Removed the Kuwo metadata adapter and all of its active fallback routes.
- Metadata now uses only MusicBrainz plus the live-validated go-music-dl-style adapters: NetEase, QQ, Kugou, Migu, JOOX, and Qianqian. Album and lyric requests search and score a source candidate before accepting its returned identifier.
- Added gzip response support required by Qianqian's current API response. Existing Spotify keys are discarded when legacy configuration is read, then omitted on the next configuration save.
- Verification: 141 Python tests, `node --check app/ui/app.js`, and `node tests/test_ui_android_bridge.js` passed. A live read-only `Hotel California / Eagles` probe confirmed lyric and cover paths for NetEase, QQ, Migu, and JOOX; Kugou cover worked but had no lyric for that returned track; Qianqian search worked but did not produce a scored match for that English sample.

## 2026-08-11: currently playing metadata priority

- Fixed current-track prioritization so it covers lyrics, album metadata/artwork, and the subsequent tag write rather than only lyrics.
- Priority order is now: current lyrics `0`, current album metadata/artwork `1`, current tag write `2`, library lyrics `100`, ordinary tag writes `200`.
- Reconcile no longer demotes an already promoted task. When playback changes, pending work for the former current track is returned to ordinary priority so repeated song changes cannot starve the library queue.
- Verification: 142 Python tests, UI syntax, and Android bridge regression checks passed, including a regression that runs reconcile between prioritization and verifies that the previous track is demoted after switching.

## 2026-08-11: stop and startup playback behavior

- Local browser and Android-WebView stop now also issue the authoritative backend `stop` command after clearing local media, so a paused session cannot be resumed by a later synchronization.
- Session restore mirrors the saved MPD queue with `play=False`, explicitly stops MPD, and persists the resulting stopped state. Startup restores the queue, current position, repeat/shuffle, and output target without starting audio.
- Verification: 142 Python tests, UI syntax, and Android bridge regression checks passed.

## 2026-08-11: 0.1.214 go-music-dl provider expansion

- Ported the metadata provider flow used by go-music-dl's `music-lib`: score a source-side song result against the local title and artist, then use its source identifier for lyrics and cover metadata.
- Added Kuwo album and standard-LRC lookup plus Kugou album artwork/date and LRC lookup. The provider order is local tags, NetEase, QQ, Kuwo, then Kugou for lyrics; Chinese album lookup now includes Kuwo and Kugou fallbacks.
- Cached `references/music-lib` at commit `3c4c32fd2aff2ffb9737856e52a45fd46b7ca12d` as the source-level implementation reference used by go-music-dl.
- Verification: 141 Python tests, JavaScript syntax validation, Android bridge regression checks, and a read-only live Kugou search probe passed. Kuwo currently returned no candidates from this network and safely falls through.

## 2026-08-11: 0.1.215 FPK release

- Released the stop and startup-state fixes together with the current-track metadata prioritization and provider migration work.
- Version identifiers were synchronized across root `VERSION`, FPK manifest, server User-Agent, web cache keys, and Android source release metadata. Android was not built or packaged for this FPK-only release.
- Verification before packaging: 142 Python tests, JavaScript syntax validation, and Android bridge regression checks passed.
- Built `artifacts/0.1.215/fnaudio-0.1.215-fnpack.fpk` with SHA-256 `204C5C78702CD21B3B192BA819428F2391D3502B118E194BBCCCAC1989DA7C79`; outer manifest, packaged server version, and UI cache keys were inspected.

## 2026-08-11: 0.1.216 embedded artwork preservation

- Fixed the ffmpeg mapping used for metadata tag writes. Lyrics-only updates map the full original input instead of `0:a:0`, preserving embedded cover artwork and other non-audio streams.
- When a verified replacement cover exists, only original image streams are removed before the replacement is attached; audio, data, subtitles, and original container metadata are retained.
- Added a regression assertion that a lyrics-only tag write never uses an audio-only stream map. Verification: metadata tests and the full 142-test Python suite passed, with UI syntax and Android bridge regressions also passing.
- Built `artifacts/0.1.216/fnaudio-0.1.216-fnpack.fpk`, SHA-256 `AA54BE69AB6CF6B96D0E354961A1909AB447E6861971F296846555A7185A07BC`; package inspection confirmed the fixed metadata writer is included.
- Ran the same lyrics-only ffmpeg remux on fnOS against a generated, embedded-artwork MP3 in an isolated temporary directory. The output retained `attached_pic=1`; extracted cover SHA-256 matched the original, and title plus new lyrics tags were verified.

## 2026-08-11: active TODO consolidation

- Replaced the accumulated release diary in `TODO.md` with a current-only backlog grouped by data integrity, real-device playback, Android, security, release reliability, scale, and protocol/test work.
- Removed duplicate DAC/DLNA/Android matrix statements, already implemented AirPlay supervisor and remote MediaSession tasks, obsolete 0.1.173/0.1.175/0.1.198 acceptance tasks, and Spotify validation after the provider migration.
- Added the user-impacting tag audit and recovery work as P0. Historical evidence remains in `PROJECT_CONTEXT.md` and `docs/`.

## 2026-08-11: read-only tag integrity audit

- Added `tools/audit_tag_integrity.py`, which correlates persisted scan provenance, current local Tag/cover contents, and completed tag-write jobs without opening the database for write access.
- High-confidence findings recommend snapshot or backup restoration. The tool intentionally has no media write mode; a separately reviewed recovery workflow is required before any backfill.
- Added `docs/TAG_INTEGRITY_AUDIT.md` and two regression tests. Full local validation: 144 Python tests, UI syntax check, and Android bridge regression passed.
- Ran the tool read-only against the current NAS database and 227-track library. It found 200 files without local artwork, but no prior Tag fields now missing and no completed tag-write history; therefore all 200 remain unproven review findings, not recovery candidates. Downloaded reports are stored in `artifacts/tag-audit-0.1.216/`; remote temporary files were removed.
- A follow-up read-only NAS storage search found no usable recovery source: `/vol1` is the only mounted data volume and has no snapshots, recycle directory, mounted backup disk, or older `library.sqlite3`. The retained `fnaudio.backup-codex-20260731-121550` directory contains application source only. No media was changed; recovery is pending a pre-0.1.213 library backup or snapshot.

## 2026-08-11: tag-write visibility and controlled retry

- Metadata status now includes the six most recent `tag_write` jobs. The UI shows the song label, state, and failure reason while keeping absolute media paths on the server.
- Added `POST /api/metadata/retry-tag-writes`. It requeues only jobs with `job_type='tag_write'` and terminal `failed` state; pending work and all other metadata job types are untouched.
- Added regression coverage for isolated retry behavior and path-free status output. Verification: 26 focused metadata-service tests and the frontend syntax check passed.

## 2026-08-11: 0.1.217 FPK release candidate

- Built `artifacts/0.1.217/fnaudio-0.1.217-fnpack.fpk` for the tag-write transparency update.
- SHA-256: `467ECC0D647854973E7E5F4B88A220210BBC4C515B2AEAD19FA3F48055631528`; outer FPK manifest was inspected and declares version `0.1.217`.
- Verification before packaging: 146 Python tests, frontend syntax validation, Android bridge regression. This artifact has not been installed on the NAS yet.

## 2026-08-11: 0.1.219 current-track lyric priority

- Removed the closed-lyrics-view guard that prevented an actively playing song from requesting lyrics.
- `/api/lyrics` now places the active song lyric job at priority `0`. A dedicated worker claims only these high-priority lyric jobs, so normal album/artwork enrichment cannot hold up the playing track. The browser retries a pending lyric response every 900 ms, with a 15-attempt bound, and updates an open lyrics page automatically when content arrives.
- Added `test_ui_lyrics_priority.js` and priority-worker coverage; full validation passed: 147 Python tests, UI syntax check, Android bridge regression, and lyrics-priority UI regression.
- Released and installed `artifacts/0.1.219/fnaudio-0.1.219-fnpack.fpk` through App Center. SHA-256: `6A3FFD0A0FFF166D99338F4E97C1471BD2B143457C65555AF893C53E4DE065BC`; deployed health check reported `fnAudio/0.1.219`.

## 2026-08-11: 0.1.220 repeat-state icons

- Replaced the repeat button's small text badge with three state-specific SVGs: disabled repeat with slash, list repeat, and single-repeat with an integrated `1`.
- Kept the existing state cycle and explicit backend control contract. Updated UI regression coverage to require separate icon markup for each state.
- Built and installed `artifacts/0.1.220/fnaudio-0.1.220-fnpack.fpk`; SHA-256: `78BD12CF9C139ACF02CA837F8C796AB8F47AF2345781DAB70EFAF54DFF56530A`. Browser acceptance verified every icon state and returned the control to off.

## 2026-08-11: P0 DAC queue-run recovery

- Added `tools/real_device_dac_queue_run.sh` for future physical DAC queue runs. It snapshots the active PlaybackCore session instead of restoring a historical hard-coded ID list, then verifies queue/current/repeat/shuffle/transport after cleanup.
- Added `docs/REAL_DEVICE_DAC_QUEUE_RUN.md` and regression coverage. The script requires an operator-provided valid queue and optional DAC target, so it cannot silently test or restore the wrong library.
- Verified POSIX shell syntax with the locally installed Git Bash and ran the script regression tests.
- This improves the evidence collection path only; USB hot-plug, DoP-only DSD, external Renderer, AirPlay and Android P0 requirements remain open until their dedicated hardware tests are performed.
- Device discovery on the current in-LAN test NAS found only browser playback, with no USB DAC or Renderer. It must not be used to close the hardware acceptance items.

## 0.1.254 CUE 封面写回与配置迁移修复（2026-08-14）

- CUE 虚拟曲目现在仅可更新共享音频封面，不再把跳过的写回记录成“已写入”，也不会污染共享文件的虚拟标题或歌词。
- APE/DSF 写回只覆盖实际传入字段，封面补全不会删除既有文字标签。
- 安装与升级回调迁移同卷旧配置中的音乐库与播放设置，保留新实例端口，避免应用扫描 UI 目录导致库和封面均为空。
- 51 项回归测试通过。内网实际 `/cover/` 返回 JPEG 缩略图的证据位于 `artifacts/0.1.254/real-device-cue-cover.json`。

## 0.1.252 封面读取与缓存失效修复（2026-08-14）

- APEv2 `Cover Art (Front)` 已进入本地封面读取链路，写回后的 APE 可由列表 `/cover/` 端点读取。
- CUE 行的封面缓存键与 URL 版本改用真实音频 mtime，Tag 写回会即时淘汰旧的无封面缓存标记。
- WAV 增加 FFmpeg 嵌入封面提取回退；容器不支持图片时保持统一音乐符号回退。
- 50 项封面、元数据与格式回归测试通过；内网隔离副本验证通过。FPK SHA-256：`75E783BEA8BAD9478F0371D0AA75EE4FF6503A1BE0EA7A64CF31CD78603AF531`。

## 0.1.250 Tag 真实设备验收（2026-08-14）

- 在内网 fnOS 使用隔离副本验证 APE、WAV、DSF 的实际 Tag 写回链路。
- 三种格式的标题、艺术家、专辑、歌词均可由 fnAudio 与 ffprobe 读回，且均可解码；DSF 原封面保持字节一致，APE 未管理 Tag 保持。
- 证据：`artifacts/0.1.250/real-device-format-tags.json`。

## 2026-08-11: Android version-code correction

- Fixed Android `versionCode` from `216` to `220` to match `versionName 0.1.220`; this prevents Android's monotonic upgrade gate from rejecting the package as older than an already-installed build.
- `lintDebug` and `assembleDebug` passed. Archived `artifacts/0.1.220/fnaudio-android-0.1.220-debug.apk` with SHA-256 `B25A39297A67F3B78098D800B0FF62038284E5ED43543052893CB7DF8F288A8B`.
- Real installation remains pending because no `adb` executable or attached Android device is present on this workstation.

## 2026-08-11: 0.1.217 App Center acceptance

- Installed `0.1.217` as an App Center overlay update on `198.51.100.24`. The manual UI was required because fnOS treated the Python dependency change as a UI-confirmed operation; existing library path, service port, and metadata setting were retained.
- Server health returned `fnAudio/0.1.217`. The deployed metadata status endpoint exposed `tag_jobs`; the retry endpoint returned successfully with zero candidates.
- Verified the completed real-library write for `艾薇 - 痴心无名氏.flac` read-only with `ffprobe`: embedded artwork (`attached_pic=1`), title, artist, and lyrics are intact. The web metadata settings page also rendered the completed write status.

## 2026-08-12: 0.1.222 continuous offline goals 1-9

- Completed bounded scan/metadata/transcode resources, MPD error taxonomy, source hygiene, playback compatibility-contract extraction, HTTP/auth/Range/media/FFmpeg/FPK/browser automation, inotify change detection, Renderer/Mixer policy, Android per-connection certificate pinning, and private file/path-boundary hardening.
- Linux music-library monitoring now skips the O(n) signature walk while clean, preserves generation changes during a scan, and falls back after overflow or monitor failure. CUE references, audio symlinks and sidecar-cover symlinks cannot escape a configured root.
- upmpdcli is compatibility-probe-only. MPD hardware volume requires an ALSA Playback Volume capability, fixed volume remains bit-perfect, and software volume is explicitly non-bit-perfect.
- Android self-signed HTTPS now performs credential-free TOFU, encrypts the full-DER SHA-256 with the connection profile, and enforces it for authentication, WebSocket, API/media/artwork requests and WebView SSL errors.
- Added `file_permissions.py`: private directories/files use 0700/0600, public UI uses 0755/0644, sensitive writes are atomic, SQLite sidecars are hardened, and Tag replacement restores owner/mode. Lifecycle scripts use umask 077 and uninstall rejects paths outside an explicit fnAudio allowlist.
- Kept the main fnOS process privileged because shared-folder ACL, ALSA/DAC, SSDP and Tag-write group contracts are not yet defined; the required migration evidence remains in `TODO.md` rather than claiming an unsafe privilege drop.
- Rewrote current TODO and recovery context, added dedicated inotify/output/TLS/permission documents, updated architecture and decisions, and added a reproducible source-manifest generator.
- Focused verification during implementation passed 46 permission/path/HTTP tests, four source-hygiene tests and POSIX shell syntax checks. Final unified verification passed 238 Python tests, JavaScript syntax validation, five Node UI regressions and two Chromium E2E scenarios.
- Android verification passed two JVM tests, `lintDebug` and `assembleDebug`; the Debug APK reports `versionCode=222`, `versionName=0.1.222`, `minSdk=23`, and verifies with v1/v2 signatures.
- Final artifacts: `artifacts/0.1.222/fnaudio-0.1.222-fnpack.fpk` SHA-256 `4F9C0A4FBB99959446EE80CBE17354C183822B5095230D2F83DC3E40741CCADF`; `artifacts/0.1.222/fnaudio-android-0.1.222-debug.apk` SHA-256 `415A320369EBE1F171F000BC6482F3CA1C984CB0D943CF882BBEFCA2C05209F5`.

## 2026-08-12: Android emulator automated regression

- Added a reproducible API 35 headless AOSP ATD test entry point at `tools/test_android_emulator.ps1`. `-InstallSdk` installs the Emulator/system image when absent; regular runs create or reuse the isolated AVD and execute `connectedDebugAndroidTest`.
- Added six Android instrumented tests for encrypted multi-profile storage and active selection, login/history rendering, matching and mismatched self-signed TLS pins against an in-process server, Mock fnOS WebSocket authentication followed by WebView loading/double-back navigation, and Media3 remote-mode queue/transport forwarding.
- The tests use only `instrument-*` connection IDs and restore the prior active selection. They do not clear arbitrary saved connection records.
- Emulator execution exposed two production defects: `RemotePlaybackPlayer` advertised `COMMAND_RELEASE` without handling it, and omitted `COMMAND_SEEK_TO_MEDIA_ITEM`. Both are now implemented and covered.
- Fixed `android-client/gradlew.bat` to return Gradle's actual exit code, so automation cannot report a failed Android test task as successful.
- After the test task, the runner installs the just-built Debug APK and verifies its emulator `versionCode` matches Gradle. API 35 emulator verification passed all six tests. The result is not evidence for real fnOS login, WebView against NAS, lock-screen, Bluetooth, USB DAC, background policy or other physical-device behavior; those remain explicit TODO items.

## 0.1.223 (2026-08-12)

- Released the Android emulator automation, Media3 remote-player lifecycle and indexed-seek fixes.
- Synchronized root version, fnOS manifest, Web cache keys and Android `versionCode=223` / `versionName=0.1.223`.
- Full offline release verification passed: 238 Python tests, JavaScript syntax, 5 Node UI regressions, 2 Chromium E2E scenarios, FPK outer/inner inspection, Android JVM tests, `lintDebug`, `assembleDebug`, and 6 API 35 emulator instrumented tests.
- `artifacts/0.1.223/fnaudio-0.1.223-fnpack.fpk` SHA-256: `6CBE385C472EC53099EFDE1CAC412208EF09C47FD028A51E0F12CFCFA13E574B`.
- `artifacts/0.1.223/fnaudio-android-0.1.223-debug.apk` SHA-256: `7CA0EBA584FFC937F939E195979E212F58DEE26AF0E79169C4A3333A72DDE40A`; it is Debug-signed with v1/v2 verification.
- Neither artifact was deployed to fnOS or a physical Android device during this release pass.

## 0.1.225 (2026-08-12)

- Fixed album artwork Tag writes when a track has no explicit `album_artist`: the writer now uses the canonical artist from the album index, matching the metadata-cache key.
- Fixed album artwork completion so every track in the indexed album receives a coalesced Tag-write job.
- Added one-time `tag_write_backfill_version=1` migration for tracks that already have valid cached album artwork. It preserves the cache, runs at the existing two-second Tag-write pace, and does not repeat after completion.
- Fixed installed fnOS runtime version detection by reading `/var/apps/fnaudio/manifest`; the HTTP header now reports `fnAudio/0.1.225` instead of `fnAudio/0.0.0`.
- Full offline verification passed 241 Python tests and all Node UI regressions. The FPK passed outer/inner package validation.
- Installed through fnOS App Center on `198.51.100.24`; App Center and HTTP both report 0.1.225 running.
- Real-library exact probing found 92 missing embedded covers among 99 tracks with matching cached artwork. Direct and background samples reduced that count to 90. The clean MP3 sample preserved all checked tags and permissions, decoded before and after the write, and produced an extracted cover byte-identical to the cached asset.
- FPK: `artifacts/0.1.225/fnaudio-0.1.225-fnpack.fpk`, SHA-256 `0E86B11F41519AD7D17FD49A815031EDDC0784EEA0BB5E58EC45D8C9A136C6AA`.
- Evidence: `docs/REAL_DEVICE_COVER_BACKFILL_0.1.225.md` and `artifacts/0.1.225/real-device/`.
## Unreleased

## 0.1.268 - 2026-08-14

- Fixed notification app return reloading the current fnAudio page. `MainActivity` now recognizes the notification-only action and restores the existing task without calling `recreate()`.
- API 35 Android-emulator regression tests passed. FPK SHA-256: `55991775E3551F032632E1FC2752679B3D437087DF5A306AC514937848556AFE`; Android debug APK SHA-256: `034FDAA0F2AA59C7252D958493F583691B0D2FF569C803D8533956269D327126`.

## 0.1.267 - 2026-08-14

- Tapping an Android remote-playback notification now brings the existing fnAudio activity and WebView session to the foreground instead of leaving the notification without an app destination.
- API 35 Android-emulator verification passed for the notification's `MediaSession` token and app-return `PendingIntent`. FPK SHA-256: `A4698E8615AB9DA67AB8747E287BA17FE549EA800DFE284A510A809C169E9A88`; Android debug APK SHA-256: `958BB2F150F3BE5CF5A29CB8393F59382CCDBC1B728F3486E91651B6015F8F09`.

## 0.1.266 - 2026-08-14

- Fixed Android remote-output media notifications. USB DAC, UPnP and DLNA targets now use a media-style foreground notification bound to the active `MediaSession`, instead of a separate plain foreground notification.
- Remote sessions publish their notification while playing, paused, or awaiting the first renderer status update, restoring notification shade, lock-screen and Bluetooth media controls without local audio decoding.
- Verified on the API 35 Android emulator with both `dac:*` and `upnp:*` targets. FPK SHA-256: `B3C85534A1C36F84FCF4D2D501300D1ED74E8EB4DA45C1E8562AA6B093388DD0`; Android debug APK SHA-256: `26D12A4084590E84F13F2D01C61C54F1DCE3EF80858671D789A39375478F0877`.

## 0.1.260 - 2026-08-14

- Packaging policy changed: all FPK releases are now emitted directly by `fnpack build`; no secondary archive creation or FPK byte rewriting is permitted. The build validator retains structural and gzip checks only.
- `0.1.260` is the first pure-fnpack replacement package. It was verified as a gzip FPK and fast-deployed successfully to `198.51.100.24`. SHA-256: `2303A1490452D0D05F9DBD60FEBF579F7A6BF84BA45E25E39D29BD670155DF69`.

## 0.1.259 - 2026-08-14

- Corrected the `0.1.258` packaging repair: fnOS requires the outer `.fpk` itself to remain gzip-compressed. The release flow now preserves that container while applying POSIX `0755` modes to lifecycle commands, producing a valid FPK for App Center installation.
- `0.1.259` was verified as gzip-compressed with executable `cmd/main`, `install_callback`, and `upgrade_callback`; it was deployed successfully to the authorized LAN host. FPK SHA-256: `7C4C1A7AAEC9065E73F0FF4D96889890EDEEB526602671CAF3DB1065EE081453`.

## 0.1.258 - 2026-08-14

- Fixed the FPK lifecycle-command permissions that caused fnOS App Center to mark fnAudio as abnormal after an update. Windows builds now repack the outer FPK with `cmd/*` at `755`, and the release validator rejects packages whose `cmd/main` is not executable.
- Hardened the LAN fast-deployment path with the same explicit lifecycle-command permission restoration before it swaps application control files.
- Verified on `198.51.100.24`: `cmd/main`, `install_callback`, and `upgrade_callback` are all mode `755`; direct `main status` and `/api/health` succeed after deployment. FPK SHA-256: `989AF478E9AC0EF563E665E94CDB9E7130FF390A578C49BC7C32D396E196B8FE`.

## 0.1.257 - 2026-08-14

- Restored the mobile MP3 transcoding control through the playback "More" menu. The option reflects its current state and applies the same reload behavior as the desktop control.
- Removed the list-cover flash at application startup: library status is now collected before the first list paint instead of causing an immediate second full-list render, and the music fallback remains visible until a thumbnail has loaded successfully.
- Verified with the UI JavaScript regressions, Android bridge regressions, 15 focused Python tests, FPK package validation and an Android Debug build. The FPK was fast-deployed to `198.51.100.24`; the service reports `0.1.257` on port `18083`.
- FPK SHA-256: `9CCAB111846542EAA8D02CDC3A921502D5923603D45FF5C8E790F1950E6A4749`. Android Debug APK SHA-256: `54D7C6CBD1880DCFCD7716286B9347B95F8746540C7DE0750FA5A1E2DD740693`.

## 0.1.256 - 2026-08-14

- Added WAV artwork writeback using RIFF `ID3 ` chunks with ID3v2.3 `APIC` frames. The audio payload is copied chunk-for-chunk rather than remuxed through FFmpeg.
- Added native RIFF-ID3 discovery for WAV metadata and cover extraction, with the existing FFmpeg extractor retained only as a compatibility fallback.
- Added WAV write/read regression coverage. Local verification passed 63 tests, JavaScript syntax validation, and FPK validation.
- Installed and tested on `198.51.100.24`. The `伍佰 - 泪桥.wav` library item renders its embedded cover after writeback. Backup: `/vol1/1000/fnaudio/wav-cover-0.1.256/伍佰 - 泪桥.before-wav-id3.wav`.
- FPK SHA-256: `1FB5DA03223BF334B3DAC2F785C602B47B6BEBF1D0EEB9D4B3C5C595805637B1`.
- Added and tested `tools/install_test_host_fast.ps1` for the authorized LAN test host. It performs a root-owned transactional FPK swap, normal upgrade callback, listener check, and automatic rollback; the first successful run completed in about nine seconds and retained the previous application at `/vol1/1000/fnaudio/fast-deploy-backups/20260814-105922`.

## 0.1.255 - 2026-08-14

- Fixed metadata completion for songs with `album = 未分类`: a successful lyric/tag task no longer masks a missing cover. The metadata service now requests exact per-track artwork from NetEase and QQ and caches it separately from album artwork.
- APE and DSF writes preserve unrelated tags. Cover-only refreshes no longer erase existing lyrics.
- Installed and validated on `198.51.100.24` through fnOS App Center. `周杰伦 - 威廉古堡.ape` returns a 59,960-byte embedded JPEG and a 5,354-byte 160px thumbnail; `艾薇 - 痴心无名氏.dsf` returns an 85,034-byte embedded JPEG and a 7,086-byte 160px thumbnail. Both thumbnail endpoints returned HTTP 200.
- FPK: `artifacts/0.1.255/fnaudio-0.1.255-fnpack.fpk`; SHA-256 `11F1376BB37A8EE8CB1B0EE789CC1109B1C1C0EE9E5D47E30BF18A5B76BA2B1C`.

- Rebuilt the Android login screen against the official fnOS login reference: extracted official FN login artwork, centered brand treatment, large rounded device/account/password fields, history icon, HTTPS control and bare-FN-ID resolver flow.
- Removed Android's per-resource OkHttp interception for authenticated WebView sessions. Album covers now load through WebView's parallel loader and cache instead of waiting behind synchronous proxy requests.
- Removed all fnOS shared-folder authorisation UI and API usage. Music-library roots are now manual entries only.
- Fixed manual library-root saves when fnOS does not expose an application token: CGI-to-local-service requests are explicitly marked as internal loopback calls, while direct network API requests remain authenticated.
- Rebuilt the Android login screen in the official fnOS visual structure: light surface, explicit text/input colors, FN Connect-first entry and manual-address fallback. This removes the theme-dependent white-on-white form rendering that caused the reported blank login area.
- Updated FN Connect handoff to begin with the official `https://fnos.net/<FN ID>/` resolver before following the selected direct or relay route in the same WebView session.
- Added Android FN Connect WebView login. The same WebView session now navigates from the FN Connect/fnOS login page directly to `/cgi/ThirdParty/fnaudio/index.cgi/`.
- Preserved manual host/port/account/password login and existing connection history.
- Added WebView-session profile routing so fnAudio requests retain Cookie authentication instead of requiring an fnOS token.
- Fixed FN Connect settings writes by attaching the authenticated WebView Cookie to native POST requests.
- Stopped intercepting FN Connect image and other GET resources with OkHttp, restoring WebView parallel loading and HTTP caching for album artwork.
# 0.1.226

- 引入官方 Tpps V2 本地隧道 JNI 封装和 Android 隧道管理器。
- FN Connect 不再回退到 `fnid.fnos.net:443` 网页地址；缺少动态中继配置时给出明确错误。
- 继续保留公网地址直连优先路径。
## 0.1.233 - 2026-08-13

- 恢复安装向导中的“服务端口”输入，默认值统一为 `53199`。
- 恢复应用中心应用设置中的“当前服务端口”，由 `config_init` 从实际 `config.json` 动态读取，不再固定显示旧端口。
- 保存设置时校验数字范围和端口占用；冲突时明确失败并保留原配置，不再静默改用相邻端口。
- 启动时严格监听已配置端口；端口被占用时停止启动并写入应用日志，用户可在应用设置中修改后重新启动。
- 真机隔离回调验证：当前端口 `54321` 正确显示；空闲端口 `54322` 正确保存；占用端口 `54323` 被拒绝且原配置保持 `54322`。
- FPK：`artifacts/0.1.233/fnaudio-0.1.233-fnpack.fpk`。
## 0.1.234 - 2026-08-13

- 修复 M4A/MP4 元数据写回失败：不再把源文件中的文本或二进制辅助流原样复制进 `ipod` 容器，只映射音频和有效封面流。
- 保持原子替换策略；临时文件写入失败时不会覆盖原歌曲。
- 设置页的端口标签由“播放”更正为“运行”，并更新端口冲突说明。
# 0.1.262（2026-08-14）

- 使用原生 `fnpack` 生成正式 FPK，并完成 fnOS App Center 覆盖升级验收。
- 验证生命周期命令可执行、服务端口与健康接口、配置和音乐库缓存保留。
- 新增 `docs/APPCENTER_LIFECYCLE_0.1.262.md` 和 `artifacts/0.1.262/verification.json`，记录可重复验收与回滚路径。
