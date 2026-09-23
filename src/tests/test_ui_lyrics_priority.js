const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const source = fs.readFileSync(
  path.join(__dirname, "..", "app", "ui", "app.js"),
  "utf8"
);
const index = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "index.html"), "utf8");
assert.ok(index.indexOf('src="metadata_response_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Metadata response policy must load before app.js");
const start = source.indexOf("function syncLyricsForCurrentTrack");
const end = source.indexOf("async function openLyrics", start);
assert.ok(start >= 0 && end > start, "Unable to locate lyric synchronization code");
const sync = source.slice(start, end);

assert.match(sync, /loadLyricsForCurrentTrack\(item\)/, "Track changes must preload lyrics");
assert.doesNotMatch(sync, /lyricsView"\)\.hidden\) return/, "Closed lyrics view must not disable lyric preload");
assert.match(source, /function scheduleLyricsPoll\(trackId\)/, "Pending lyrics must be refreshed automatically");
assert.match(source, /function closeLyrics\(\) \{[\s\S]*?cancelLyricsPoll\(\);[\s\S]*?cancelLyricsRequest\(\);[\s\S]*?lyricsRequestToken \+= 1/, "Closing lyrics must cancel its poll and in-flight request");
assert.match(source, /function prefetchCurrentTrackMetadata\(item = currentItem\(\)\)/, "Playback should trigger track metadata prefetch");
assert.match(source, /function prefetchCurrentTrackMetadata\(item = currentItem\(\)\)[\s\S]*?fetchMetadataRequest\(`api\/metadata\/track\?track_id=/, "Track metadata prefetch must use the shared no-store metadata request path");
assert.match(source, /state\.metadataPrefetchTrackId === trackId/, "Metadata prefetch must deduplicate the current track");
assert.match(source, /state\.metadataPrefetchLyricsAttempts < 12/, "Playback lyric prefetch must retry pending responses within a bound");
assert.match(source, /state\.metadataPrefetchLyricsTimer = setTimeout/, "Playback lyric prefetch must schedule pending retries");
assert.match(source, /let scheduleLyricsRetry = null;/, "Lyric retries must share one bounded scheduler");
assert.match(source, /scheduleLyricsRetry = \(retryFailed = false\) => \{[\s\S]*?requestLyrics\(retryFailed\)\.catch\(\(\) => scheduleLyricsRetry\(false\)\);/, "A failed timed lyric retry must continue through the existing bounded scheduler");
assert.match(source, /state\.metadataPrefetchLyricsController = lyricsController;/, "Lyric retries must retain cancellation ownership");
assert.match(source, /state\.metadataPrefetchLyricsController === lyricsController[\s\S]*?!state\.metadataPrefetchLyricsTimer[\s\S]*?state\.metadataPrefetchLyricsController = null;/, "Settled lyric lookups must release their controller");
assert.match(source, /state\.metadataPrefetchLyricsTrackId = "";/, "Empty settled lyric projections must remain eligible for later recovery");
assert.match(source, /requestLyrics = \(retryFailed = false\)/, "Playback lyric prefetch must support explicit terminal recovery");
assert.match(source, /function unwrapMetadataResponsePayload\(value\)/, "Metadata responses must have one shared envelope normalizer");
assert.match(source, /const lyricPayload = unwrapMetadataResponsePayload\(data\)/, "Playback lyric prefetch must accept direct and bridge-wrapped lyric payloads");
assert.match(source, /data = unwrapMetadataResponsePayload\(data\)/, "Track metadata prefetch must accept direct and bridge-wrapped payloads");
assert.match(source, /if \(response\.ok\) data = unwrapMetadataResponsePayload\(result\.data\)/, "Visible metadata prefetch must normalize bridge-wrapped responses");
assert.match(source, /const data = unwrapMetadataResponsePayload\(await readResponseJsonBounded\(response\)\);[\s\S]*?const candidates = Array\.isArray\(data\.candidates\)/, "Metadata candidate dialog must normalize bridge-wrapped responses");
assert.match(source, /async function loadLyricsForCurrentTrack[\s\S]*?data = unwrapMetadataResponsePayload\(await readResponseJsonBounded\(response\)/, "Lyrics requests must normalize bridge-wrapped responses");
assert.match(source, /async function loadMetadataStatus\(\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?unwrapMetadataResponsePayload\(result\.data/, "Metadata status must use the bounded loader and normalize bridge-wrapped responses");
assert.match(source, /async function saveMetadataSettings[\s\S]*?unwrapMetadataResponsePayload\(await readResponseJsonBounded\(response\)\)/, "Metadata settings save must normalize bridge-wrapped responses");
assert.match(source, /async function retryFailedTagWrites[\s\S]*?unwrapMetadataResponsePayload\(await readResponseJsonBounded\(response\)\)/, "Tag-write retry status must normalize bridge-wrapped responses");
assert.match(source, /fnAudioMetadataResponsePolicy\?\.unwrap\(value, 4\)/, "Metadata envelope unwrapping must remain bounded and support four host envelopes");
assert.match(source, /terminal = \["failed", "no_match"\]\.includes\(status\)/, "Terminal lyric misses must remain bounded-retryable");
assert.match(source, /scheduleLyricsRetry\?\.\(!requestedRetry && \(terminal \|\| data\.ok !== true\)\)/, "Terminal lyric retry must request server-side recovery once");
assert.match(source, /const lyricArtwork = usableCoverSource\(lyricPayload\?\.image_url\)/, "Playback lyric prefetch should apply resolved artwork");
// R166 rewrote this assertion.  It used to pin the prefetch lane to
// "render only when the panel is visible, and stash state.lyrics either way", which is
// the divergence that made the lane's private sixth status word fatal.  The replacement
// is strictly stronger: the parsed body must reach the one painting path, and both
// abolished shapes are now forbidden from returning.
assert.match(source, /state\.lyricsStatus = "loaded";\n\s*renderLyrics\(parseLyrics\(lyrics\)\);/, "Live lyric prefetch must hand the parsed lyric array to the one path that paints it");
assert.doesNotMatch(source, /if \(!\$\('lyricsView'\)\?\.hidden\) renderLyrics\(/, "A hidden panel may not be left holding a lyric body its DOM never received");
assert.doesNotMatch(source, /state\.lyricsStatus = "ready"/, "The lyric status vocabulary must stay closed to the words the reuse gate knows");
assert.match(source, /const needsPriorityLyricsLane = !String\(item\.lyrics \|\| ""\)\.trim\(\)/, "Embedded lyrics must not suppress artwork recovery");
assert.match(source, /const METADATA_PREFETCH_MAX_ATTEMPTS = 12;/, "Metadata prefetch must use an explicit bounded budget");
assert.match(source, /state\.metadataPrefetchAttempts < METADATA_PREFETCH_MAX_ATTEMPTS/, "Metadata prefetch polling must remain bounded");
assert.match(source, /selectDisplayCandidate\([\s\S]*?data\.candidates/, "Usable non-best metadata candidates should still be shown");
assert.match(source, /state\.metadataPrefetchTimer = setTimeout/, "Pending metadata must retry without blocking playback");
assert.match(source, /fnAudioMetadataResponsePolicy\?\.isTransientHttpStatus\?\.\(response\.status\)/, "Transient metadata service errors must remain bounded-retryable");
assert.match(source, /data\.pending === true \|\| String\(data\.status \|\| \"\"\)\.toLowerCase\(\) === \"pending\"/, "Queued metadata status must remain retryable across response shapes");
assert.match(source, /String\(data\.status \|\| \"\"\)\.toLowerCase\(\) === \"unavailable\"/, "Metadata dialog must distinguish an unavailable worker from no match");
assert.match(source, /const scheduleRetry = \(\) => \{/, "Network metadata failures must use a bounded retry scheduler");
assert.match(source, /state\.metadataPrefetchAttempts >= METADATA_PREFETCH_MAX_ATTEMPTS\)[\s\S]*?scheduleRearm\(\)/, "Exhausted metadata retries must enter the bounded cooldown re-arm path");
assert.match(source, /state\.metadataPrefetchRearms >= 2/, "Same-track metadata re-arm must have a hard cap");
assert.match(source, /}, 30000\);/, "Same-track metadata recovery must wait through a cooldown");
assert.match(source, /state\.metadataPrefetchUnavailable = true;[\s\S]*?scheduleRetry\(\);/, "Unavailable metadata worker must remain retryable");
assert.match(source, /request\(\)\.catch\(\(\) => scheduleRetry\(\)\)/, "Metadata prefetch network failures must be retried");
assert.match(source, /request\(retryFailed\)\.catch\(\(\) => scheduleRetry\(\)\)/, "Pending metadata polls must not force-retry an active provider job");
assert.match(source, /retryFailed = !requestedRetry && \(responseStatus === "failed" \|\| responseStatus === "no_match"\);/, "Only terminal provider projections may arm explicit recovery for the current track");
assert.match(source, /status === "no_match" \|\| status === "review" \|\| status === "auto"/, "An empty legacy review/auto projection must remain recoverable for the current track");
assert.match(source, /state\.lyricsPollAttempts >= 15/, "Automatic lyric polling needs a bounded retry limit");
assert.match(source, /const retry = retryFailed\s*\? "&retry=1"\s*:\s*"";/, "Only an explicit retry may request server-side recovery");
assert.match(source, /loadLyricsForCurrentTrack\(item, retry, state\.lyricsStatus === "error"\)/, "Reopening lyrics after a terminal failure must request a deliberate retry");
assert.match(source, /showLyricsMessage\("正在获取歌词\.\.\."\)/, "Pending lyrics should show an active retrieval state");
assert.ok(source.includes('const detail = String(error?.message || "").replace(/[\\r\\n]+/g, " ").trim().slice(0, 180);'), "Structured lyric-service errors should remain visible with a bounded message");
assert.match(source, /error\.metadataUnavailable = unavailable/, "Unavailable metadata service must be classified separately");
assert.match(source, /if \(!error\?\.metadataUnavailable\) scheduleLyricsPoll\(trackId\)/, "Unavailable metadata service must not trigger an endless lyric poll loop");
assert.match(source, /歌词加载失败：\$\{detail\}/, "The lyrics view should distinguish service failures from an ordinary empty lyric");
assert.match(source, /const lyricArtwork = usableCoverSource\(data\.image_url\);[\s\S]*?lyricArtwork && !item\.cover_url && !item\.cover_thumbnail_url/, "Resolved lyric artwork should validate and fill only missing local artwork");
assert.match(source, /const lyricArtwork = usableCoverSource\(data\.image_url\);[\s\S]*?if \(data\.pending === true\)/, "Cached artwork returned with pending lyrics must be applied before the pending branch");
assert.match(source, /if \(\$\("metadataEnabledInput"\) && !\$\("metadataEnabledInput"\)\.checked\) \{[\s\S]*?\$\("metadataEnabledInput"\)\.checked = true;/, "Manual metadata refresh must release the disabled-worker gate");
assert.match(source, /已开启后台元数据补全并加入队列/, "Manual metadata refresh should report that fetching is enabled");
assert.match(source, /prefetchCurrentTrackMetadata\(currentItem\(\)\)/, "Restored sessions must re-enter the current-track metadata lane");

console.log("Lyrics priority UI regression checks passed.");


