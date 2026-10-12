const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const loader = fs.readFileSync("app/ui/library_response_loader.js", "utf8");
const metadataRequestLoader = fs.readFileSync("app/ui/metadata_request_loader.js", "utf8");
const loadKey = fs.readFileSync("app/ui/library_load_key.js", "utf8");
const index = fs.readFileSync("app/ui/index.html", "utf8");
const itemLoader = fs.readFileSync("app/ui/library_item_request_loader.js", "utf8");
const hydrationRequest = fs.readFileSync("app/ui/item_hydration_request.js", "utf8");
const metadataProjection = fs.readFileSync("app/ui/metadata_projection_policy.js", "utf8");
const metadataMerge = fs.readFileSync("app/ui/library_metadata_merge_policy.js", "utf8");
const emptyResponsePolicy = fs.readFileSync("app/ui/library_empty_response_policy.js", "utf8");
const visibleMetadataPolicy = fs.readFileSync("app/ui/visible_metadata_prefetch_policy.js", "utf8");
const candidatePresentation = fs.readFileSync("app/ui/metadata_candidate_presentation_policy.js", "utf8");
const renderPolicy = fs.readFileSync("app/ui/library_render_policy.js", "utf8");
const snapshotReusePolicy = fs.readFileSync("app/ui/library_snapshot_reuse_policy.js", "utf8");
const rowSignaturePolicy = fs.readFileSync("app/ui/library_row_signature_policy.js", "utf8");
const pageSizePolicy = fs.readFileSync("app/ui/library_page_size_policy.js", "utf8");
const pageSnapshotPolicy = fs.readFileSync("app/ui/library_page_snapshot_policy.js", "utf8");
const statusRefreshPolicy = fs.readFileSync("app/ui/library_status_refresh_policy.js", "utf8");
const responseJsonLoader = fs.readFileSync("app/ui/response_json_loader.js", "utf8");
const pageCursorPolicy = fs.readFileSync("app/ui/library_page_cursor_policy.js", "utf8");

const pagePresentationSource = app.match(/function trackPagePresentationSignatures\(items = \[\]\) \{[\s\S]*?\n\}/);
assert.ok(pagePresentationSource, "Track-page presentation signatures must remain independently testable");
const pagePresentationContext = {
  JSON,
  String,
  Array,
  state: { view: "all" },
  activeTrackColumns: () => ["title"],
  trackColumnValues: () => ({}),
  trackRowMarkupSignature: () => "same-row",
  coverUrl: () => "",
};
vm.runInNewContext(`${pagePresentationSource[0]}; globalThis.signatures = trackPagePresentationSignatures;`, pagePresentationContext);
assert.notDeepEqual(
  pagePresentationContext.signatures([{ id: "a\\u001fsame-row" }]),
  pagePresentationContext.signatures([{ id: "a" }]),
  "opaque track IDs must not collide with presentation signatures during snapshot reuse",
);

assert.match(app, /fnAudioLibraryPageSizePolicy\?\.resolvePageSize\(localStorage, window\)/, "Page size must use the isolated viewport/storage policy");
assert.match(pageSizePolicy, /MOBILE_DEFAULT = 60/);
assert.match(pageSizePolicy, /DESKTOP_DEFAULT = 96/);
assert.match(pageSizePolicy, /MAX_PAGE_SIZE = 500/);
assert.ok(index.indexOf('src="library_page_size_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Page size policy must load before app.js");
assert.match(app, /state\.libraryAbortController = null;/);

const transcodeStatusStart = app.indexOf("async function refreshCurrentTranscodeStatus");
const transcodeStatusEnd = app.indexOf("function previewSeek", transcodeStatusStart);
assert.ok(transcodeStatusStart >= 0 && transcodeStatusEnd > transcodeStatusStart);
const transcodeStatusSource = app.slice(transcodeStatusStart, transcodeStatusEnd);
assert.doesNotMatch(transcodeStatusSource, /clearTimeout\(timer\)/,
  "Transcode status cleanup must not reference an undefined timer");
assert.match(transcodeStatusSource, /if \(!item \|\| isRemoteTarget\(\) \|\| nativePlaybackAvailable\(\)\) \{[\s\S]*?transcodeStatusRequestToken \+= 1;[\s\S]*?transcodeStatusController\?\.abort\(\)/,
  "Mode changes must invalidate an older transcode status request");
assert.match(app, /function libraryCount\(value, fallback = 0\)/, "Page totals need a shared bounded count projection");
assert.match(app, /state\.pageTotal = libraryCount\(data\.count\);/, "Authoritative page counts must reject malformed numeric payloads");
assert.match(app, /state\.folderTotal = libraryCount\(folderData\.count\);/, "Folder page counts must reject malformed numeric payloads");
assert.match(app, /state\.libraryInteractionBlocked = false;/, "Stale library rows need an explicit interaction guard during replacement loads");
assert.match(app, /state\.libraryInteractionBlocked = true;[\s\S]*?state\.libraryInteractionBlocked = false;/, "Replacement page loads must make the retained old projection inert until commit");
const clickListenerBlock = app.match(/list\.addEventListener\("click", event => \{[\s\S]*?\}, true\);/)?.[0] ?? "";
assert.ok(
  clickListenerBlock.includes(String.raw`if (!libraryInteractionBlockedFor(event.target, list)) return;`),
  "The retained list must release folder navigation while it keeps blocking stale rows",
);
assert.match(app, /if \(state\.libraryInteractionBlocked && event\.target\.closest\?\.\("#trackList"\)/, "Double-click playback must not bypass the stale-list interaction guard");
assert.match(app, /list\.addEventListener\("contextmenu", event => \{\s*if \(libraryInteractionBlockedFor\(event\.target, list\)\)[\s\S]*?event\.stopImmediatePropagation\(\);/, "Context menus must not operate on stale rows during replacement loads");
assert.match(app, /list\.addEventListener\("pointerdown", event => \{\s*if \(libraryInteractionBlockedFor\(event\.target, list\)\)[\s\S]*?cancelTrackLongPress\(\);[\s\S]*?event\.preventDefault\(\);/, "Long-press gestures must not operate on stale rows during replacement loads");
assert.match(app, /state\.libraryStatusPromise = null;/, "Library status polling needs explicit in-flight ownership");
assert.match(app, /state\.libraryStatusRefreshQueued = false;/, "Status polling needs a bounded trailing-refresh flag");
assert.match(app, /fnAudioLibraryStatusRefreshPolicy\?\.plan\(/, "Status refresh reuse must use the isolated policy");
assert.match(statusRefreshPolicy, /function plan\(inFlight, refresh\)/, "Status refresh arbitration must stay in a pure policy");
assert.ok(index.indexOf('src="library_status_refresh_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Status refresh policy must load before app.js");
assert.match(app, /token === state\.libraryStatusRequestToken[\s\S]*?state\.libraryStatusController === controller[\s\S]*?state\.libraryStatusPromise === request[\s\S]*?state\.libraryStatusPromise = null;/, "Status request ownership must be cleared only by the active request");
assert.match(app, /state\.itemHydrationGeneration = 0;/, "Item hydration needs generation ownership across cancelled pools");
assert.match(app, /state\.itemHydrationRequest = null;/, "Item hydration must retain an active request identity");
assert.match(app, /state\.itemHydrationInflight = new Map\(\);/, "Item hydration batches must share in-flight requests");
assert.match(app, /state\.referencedItemHydrationTimer = 0;/, "Post-paint referenced hydration needs explicit cancellation ownership");
assert.match(app, /state\.visibleMetadataPrefetchUsesIdle = false;/, "Visible metadata prefetch must distinguish a delay timer from an idle callback");
assert.match(app, /const priorityLaneActive = globalThis\.fnAudioVisibleMetadataPrefetchPolicy\?\.ownsCurrentTrackLane\?\.\(/, "Cold-start restored current tracks must be eligible for metadata recovery");
assert.match(app, /fnAudioVisibleMetadataPrefetchPolicy\?\.ownsCurrentTrackLane\?\.\(/, "Current-track exclusion must use the isolated live-lane ownership policy");
assert.match(app, /state\.metadataPrefetchController === controller[\s\S]*?!state\.metadataPrefetchTimer[\s\S]*?state\.metadataPrefetchController = null;/, "A settled priority lookup must release its controller when no retry remains");
assert.match(app, /const scheduleRetry = \(\) => \{[\s\S]*?state\.metadataPrefetchController = controller;[\s\S]*?state\.metadataPrefetchTimer = setTimeout/, "A queued priority retry must retain cancellation ownership after a rejected request");
assert.match(app, /const excludedCurrentTrackId = priorityLaneActive \? currentTrackId : "";/, "Current-track exclusion must only apply while its priority lane is active");
assert.match(app, /setTimeout\(queueIdleRun, 220\)/, "Optional visible-row metadata must yield briefly without looking unavailable after first paint");
assert.match(app, /requestIdleCallback\(\(\) => \{ run\(\)\.catch\(\(\) => \{\}\); \}, \{ timeout: 450 \}\)/, "Visible metadata should continue through a short bounded idle slot after first paint");
assert.match(app, /state\.visibleMetadataPrefetchUsesIdle && typeof cancelIdleCallback === "function"/, "Cancelling visible metadata must not pass timeout IDs to cancelIdleCallback");
assert.match(app, /function scheduleReferencedItemHydration\(requestSeq\)/, "Referenced queue/favorite hydration must yield until after first paint");
assert.match(app, /const seq = \+\+state\.libraryRequestSeq;\s*cancelReferencedItemHydrationSchedule\(\);/, "A new library request must cancel stale post-paint hydration before opening a new page request");
assert.match(app, /render\(\);[\s\S]*?scheduleReferencedItemHydration\(seq\);/, "First page rendering must precede referenced item hydration");
assert.match(app, /const restoredCurrent = currentItem\(\);[\s\S]*?fnAudioVisibleMetadataPrefetchPolicy\?\.needsMetadata\?\.\(restoredCurrent\)/, "Authoritative first page must use the shared metadata-missing policy for a restored current track");
assert.match(app, /if \(restoredNeedsMetadata\) \{\s*prefetchCurrentTrackMetadata\(restoredCurrent\);/, "Authoritative first page must re-arm metadata for a restored current track");
assert.match(app, /requestIdleCallback\(run, \{ timeout: 600 \}\)/, "Modern WebViews should yield hydration to an idle phase");
assert.match(app, /state\.referencedItemHydrationTimer = setTimeout\(run, 80\);/, "Older WebViews need a bounded post-paint fallback");
assert.match(app, /fnAudioLibraryItemRequestLoader\.loadBatch\(/, "Item hydration must use the shared request loader");
assert.match(itemLoader, /if \(inflight\.has\(key\)\) return inflight\.get\(key\);/);
assert.match(itemLoader, /if \(inflight\.size >= limit\)/, "Item hydration must reject at the concurrency limit instead of dispatching untracked requests");
assert.ok(index.indexOf('src="library_item_request_loader.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Item request loader must load before app.js");
assert.ok(index.indexOf('src="ui_metrics_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "UI metrics policy must load before app.js");
assert.ok(index.indexOf('src="metadata_candidate_presentation_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Metadata candidate presentation policy must load before app.js");
assert.match(candidatePresentation, /function selectDisplayCandidate\(best, candidates\)/, "Metadata display candidate selection must be isolated as a pure policy");
assert.match(app, /fnAudioMetadataCandidatePresentationPolicy\?\.selectDisplayCandidate\(/, "Current-track metadata rendering must choose the most complete candidate");
assert.match(app, /window\.__fnAudioUiMetricsSnapshot = \(\) =>/, "UI metrics should expose a safe snapshot helper");
assert.match(app, /state\.libraryLoadKey = "";/);
assert.match(app, /state\.libraryLoadPromise = null;/);
assert.match(app, /function invalidateLibraryLoad\(\)[\s\S]*?state\.libraryStatusRequestToken \+= 1;[\s\S]*?state\.libraryStatusController = null;[\s\S]*?state\.libraryStatusPromise = null;[\s\S]*?state\.libraryStatusRefreshQueued = false;/, "Switching views must invalidate stale library status polling");
assert.match(app, /function invalidateLibraryLoad\(\) \{[\s\S]*?state\.libraryRequestSeq \+= 1;[\s\S]*?state\.libraryAbortController\.abort\(\);[\s\S]*?cancelVisibleMetadataPrefetch\(\{ releaseKeys: true \}\);/, "Switching to a non-paged view must invalidate stale paged work and release cancelled metadata keys");
assert.match(app, /function setView\(view\) \{[\s\S]*?state\.view = nextView;\s*if \(!isPagedLibraryView\(\)\) invalidateLibraryLoad\(\);/, "Non-paged view switches must cancel the previous library request before rendering");
assert.match(app, /function deletePlaylist\(playlistId\) \{[\s\S]*?if \(state\.view === `playlist:\$\{playlistId\}`\) \{\s*setView\("all"\);\s*return;/, "Deleting the active playlist must reload the paged all-tracks view instead of rendering its stale rows");
assert.match(app, /state\.renderedTrackListHtml = null;/, "Initial row markup cache must have an explicit empty state");
assert.match(app, /state\.trackRowsMarkupCache = typeof WeakMap === "function" \? new WeakMap\(\) : null;/, "Stable page rows need a bounded identity cache");
assert.match(app, /const LIBRARY_PAGE_SNAPSHOT_TTL_MS = 15 \* 60 \* 1000;/, "First paint snapshot must have a bounded TTL");
assert.match(app, /const LIBRARY_PAGE_SNAPSHOT_MAX_BYTES = 384 \* 1024;/, "First paint snapshot must have a storage bound");
assert.match(app, /function restoreLibraryPageSnapshot\(page = 1\)/, "Startup should be able to restore a recent page snapshot");
assert.match(app, /function librarySnapshotKey\(page = 1\) \{[\s\S]*?return libraryLoadRequestKey\(page\);/, "Bootstrap snapshots must use the complete request identity, including nested filters");
assert.ok(index.indexOf('src="library_page_snapshot_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Snapshot policy must load before app.js");
assert.match(app, /fnAudioLibraryPageSnapshotPolicy\?\.restore\(raw, \{/, "Snapshot reads must delegate parsing and bounds to the isolated policy");
assert.match(pageSnapshotPolicy, /raw\.length > maxBytes/, "Oversized snapshots must be rejected before JSON parsing");
assert.match(pageSnapshotPolicy, /!Array\.isArray\(snapshot\.items\) \|\| !snapshot\.items\.length/, "Empty legacy snapshots must not trigger an empty first paint");
assert.match(app, /fnAudioLibraryPageSnapshotPolicy\?\.encode\(\{/, "Snapshot writes must delegate serialization bounds to the isolated policy");
assert.match(app, /function persistLibraryPageSnapshot\(page = 1\)/, "Successful pages should update the startup snapshot");
assert.match(app, /function scheduleLibraryPageSnapshot\(page = 1\)/, "Snapshot writes should yield to first-paint work");
assert.match(app, /requestIdleCallback\(persist, \{ timeout: 1200 \}\)/, "Snapshot serialization should prefer an idle slot");
assert.match(app, /scheduleLibraryPageSnapshot\(state\.page\);/, "Completed pages should schedule rather than synchronously persist snapshots");
assert.match(app, /if \(restoreLibraryPageSnapshot\(1\)\) render\(\);/, "Snapshot must be painted before the network load");
assert.match(app, /shouldRetainSnapshotForEmptyResponse\(data, refresh\)/, "Transient empty responses must not immediately replace a visible snapshot");
assert.match(app, /let retainedEmptySnapshot = false;/, "Empty-response retention must be scoped to one request");
assert.match(app, /if \(retainedEmptySnapshot\) \{\s*const retryKey = libraryLoadRequestKey\(state\.page\);\s*setTimeout\(/, "Retained snapshots must schedule one bounded follow-up request");
assert.match(app, /state\.libraryResponseCache\.delete\?\.\(`api\/library\?\$\{params\.toString\(\)\}`\)/, "Transient empty responses must be evicted before retry");
assert.match(app, /isPagedLibraryView\(\)\s*&&\s*libraryLoadRequestKey\(state\.page\) === retryKey/, "Delayed empty-response retry must not cross a view/query switch");
assert.match(app, /state\.librarySnapshotEmptyGuardUsed = false;\s*updateNavigationActiveState\(\);/, "Changing views must cancel the one-shot snapshot guard while refreshing navigation state");
assert.match(emptyResponsePolicy, /options\.guardUsed/, "Empty-response policy must be one-shot");
assert.match(app, /function hasVisibleLibraryPresentation\(\)/, "User-state hydration needs a first-page visibility guard");
assert.match(app, /function renderAfterUserStateHydration\(\{ visibleListChanged = false \} = \{\}\)/, "User-state hydration should use a compact pre-library presentation path");
assert.match(app, /if \(state\.libraryLoading && state\.librarySnapshot\?\.hit\) \{\s*refreshUserStateChrome\(\);/, "Snapshot first paint must not be repainted when user-state hydration wins the network race");
assert.match(app, /state\.libraryLoading = true;[\s\S]*?if \(!hasVisibleLibraryPresentation\(\)\) \{[\s\S]*?empty\.hidden = true;[\s\S]*?updateLibraryStatusDecorations\(\);[\s\S]*?\}/, "Cold start must hide only the static empty frame before page one arrives");
assert.match(app, /if \(hasVisibleLibraryPresentation\(\)\) \{[\s\S]*?if \(visibleListChanged\) render\(\);[\s\S]*?else refreshUserStateChrome\(\);/, "A late identical user state must update chrome without rebuilding the visible first page");
assert.match(app, /function visibleUserStatePresentationSignature\(\)/, "User-state hydration must compare the subset that can change visible rows");
assert.match(app, /visibleListChanged = await applyServerUserState\(serverState\);/, "Hydration must carry its visible-list decision to the renderer");
assert.match(app, /state\.libraryStatusRequestToken = 0;[\s\S]*?state\.libraryStatusController = null;/, "Library status refresh needs explicit request ownership");
assert.match(app, /const token = \+\+state\.libraryStatusRequestToken;[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?request: responsePromise,[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout:/, "Library status refresh must time out its response body instead of permanently occupying its dedupe slot");
assert.match(responseJsonLoader, /Promise\.race\(\[operation, timeout\]\)/, "Shared JSON loader must bound both response headers and body parsing");
assert.match(app, /token === state\.libraryStatusRequestToken[\s\S]*?state\.libraryStatusController === controller[\s\S]*?state\.libraryStatusPromise === request/, "Only the owning library status request may release the shared refresh slot");
assert.match(app, /function refreshUserStateChrome\(\) \{\s*renderPlaylistNav\(\);\s*updateFavoriteControls\(\);\s*updateRepeatShuffleButtons\(\);/, "Pre-library user-state presentation must still refresh player controls");
assert.match(app, /state\.userStateHydrated = true;\s*if \(!serverState\.initialized\) scheduleUserStateSave\(\);\s*renderAfterUserStateHydration\(\{ visibleListChanged \}\);/, "Initial user-state load must avoid an unconditional full render");
assert.match(app, /!state\.userStateHydrated && state\.libraryLoading && state\.libraryLoadPromise/, "Cold-start queue hydration must yield to the authoritative first library page even when a snapshot is already visible");
assert.match(app, /await state\.libraryLoadPromise/, "Initial queue hydration must wait for page-one completion before issuing item batches");
assert.match(app, /fetchJsonChecked\([\s\S]*?读取播放队列失败/, "Cold-start queue hydration must use the bounded JSON response loader");
assert.match(app, /async function loadMetadataStatus\(\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?api\/metadata\/status/, "Metadata settings status must bound response-body parsing");
assert.match(app, /async function loadDlnaDiagnostics\(\)[\s\S]*?fetch\("api\/dlna\/diagnostics"[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000/, "DLNA diagnostics must bound response-body parsing");
assert.match(css, /\.track,\.group-row\{content-visibility:auto;contain-intrinsic-size:68px 68px\}/, "Rows should expose a progressive rendering hint for large libraries");
assert.match(app, /function commitTrackListHtml\(listHtml\)/, "Library rows should support keyed incremental commits");
assert.match(app, /state\.uiMetrics = \{[\s\S]*?renders: 0,[\s\S]*?listCommits: 0,[\s\S]*?snapshotMarkupReuses: 0,[\s\S]*?listMarkupNoops: 0,[\s\S]*?coverHydrations: 0,[\s\S]*?firstListCommitMs: 0,[\s\S]*?firstCoverHydrationMs: 0/, "First-paint regressions should expose bounded session counters and timings");
assert.match(app, /state\.uiMetrics\.listCommits = Math\.min\(1000000/, "List commit evidence must remain bounded");
assert.match(app, /state\.uiMetrics\.snapshotMarkupReuses = Math\.min\(1000000/, "Warm snapshot markup reuse must remain observable and bounded");
assert.match(app, /state\.uiMetrics\.listMarkupNoops = Math\.min\(1000000/, "No-op list commits must remain observable and bounded");
assert.match(app, /state\.uiMetrics\.coverHydrations = Math\.min\(1000000/, "Cover hydration evidence must remain bounded");
assert.match(app, /metadataPrefetchRequests: 0/, "Metadata prefetch request metrics should be exposed");
assert.match(app, /metadataPrefetchSuccesses: 0/, "Metadata prefetch success metrics should be exposed");
assert.match(app, /metadataPrefetchFailures: 0/, "Metadata prefetch failure metrics should be exposed");
assert.match(app, /metadataPrefetchNoMatches: 0/, "Metadata prefetch no-match metrics should be exposed");
assert.match(app, /metadataPrefetchLastMs: 0/, "Metadata prefetch latency should be observable");
assert.match(app, /metadataPrefetchTotalMs = Math\.min\(3600000/, "Metadata prefetch latency accumulation must remain bounded");
assert.match(app, /state\.uiMetrics\.metadataPrefetchNoMatches = Math\.min\(1000000/, "Metadata no-match metrics must remain bounded");
assert.match(app, /terminalStatus === "no_match"\)[\s\S]*?metadataPrefetchNoMatches[\s\S]*?terminalStatus === "failed"\)[\s\S]*?metadataPrefetchFailures/, "Terminal no-match and provider failure diagnostics must remain distinct");
assert.match(app, /state\.uiMetrics\.metadataPrefetchRequests = Math\.min\(1000000/, "Metadata prefetch request metrics must remain bounded");
assert.match(app, /state\.uiMetrics\.metadataPrefetchFailures = Math\.min\(1000000, state\.uiMetrics\.metadataPrefetchFailures \+ 1\);/, "Non-cancelled metadata prefetch failures must be observable");
assert.match(app, /const metadataRequestStartedAt = Date\.now\(\);/, "Metadata latency must measure each provider request independently");
assert.match(app, /metadataPrefetchTotalMs = Math\.min\(3600000, state\.uiMetrics\.metadataPrefetchTotalMs \+ metadataRequestElapsedMs\)/, "Metadata latency total must not double-count poll windows");
assert.match(app, /if \(generation !== state\.visibleMetadataPrefetchSeq \|\| requestSeq !== state\.libraryRequestSeq\) return;\s*if \(!data\) \{/, "Cancelled visible metadata batches must not be counted as provider failures");
assert.match(app, /const noMatchJobs = Number\(jobs\.no_match \|\| 0\);/, "Metadata status must distinguish provider no-match jobs from failures");
assert.match(app, /暂未匹配（可稍后重试）/, "Metadata no-match status should remain visibly recoverable");
assert.match(app, /const missingProjection = !Object\.prototype\.hasOwnProperty\.call\(data, "status"\)/, "Generic HTTP 200 metadata envelopes must remain retryable");
assert.match(app, /firstListCommitMs = Math\.min\(3600000/, "First list commit timing must remain bounded");
assert.match(app, /firstCoverHydrationMs = Math\.min\(3600000/, "First cover timing must remain bounded");
assert.match(css, /\.track\{[^}]*content-visibility:auto;contain-intrinsic-size:68px/, "Large library rows should use progressive content-visibility optimization");
assert.match(app, /function renderTrackRows\(items = \[\]\)/, "Track lists should build one shared column configuration per page");
assert.match(app, /const columns = activeTrackColumns\(\);\s*const rows = Array\.isArray\(items\) \? items : \[\];/, "Page rows must reuse one scoped column array instead of recalculating it per song");
assert.match(app, /const cacheKey = state\.view === "queue" \? "" : `\$\{trackColumnScope\(\)\}\|\$\{columns\.join\("\|"\)\}`;/, "Non-queue pages should reuse markup only for the same visible column scope");
assert.match(app, /if \(cached\?\.key === cacheKey\) return cached\.html;/, "Stable page rows must bypass repeat HTML serialization");
assert.match(app, /function invalidateTrackRowsMarkup\(items = state\.pageItems\)/, "In-place page-row mutations need explicit cache invalidation");
assert.match(app, /invalidateTrackRowsMarkup\(state\.pageItems\);/, "Priority artwork completion must invalidate retained row markup");
assert.match(app, /function renderTrack\(item, index = 0, columns = activeTrackColumns\(\)\)/, "Single-row callers retain the existing safe column fallback");
assert.match(app, /const columnValues = trackColumnValues\(item, columns\.filter\(key => key !== "title"\)\);/, "Each song should format its visible non-title columns once");
assert.match(app, /columnValues\[key\] \|\| "—"/, "Rows should reuse their precomputed column values");
assert.match(app, /const currentByKey = new Map\(current\.map\(node => \[keyOf\(node\), node\]\)/, "Stable row keys should patch rows even when page length changes");
assert.match(app, /const nextKeySet = new Set\(nextKeys\.filter\(Boolean\)\)/, "Keyed reconciliation must validate row identities without quadratic duplicate scans");
assert.match(app, /nextKeySet\.size === next\.length/, "Only unique stable keys may enter keyed reconciliation");
assert.match(app, /const orderUnchanged = current\.length === next\.length/, "Stable renders must detect unchanged row order before moving nodes");
assert.match(app, /if \(fragment\) list\.appendChild\(fragment\)/, "Only reordered keyed rows may be moved through a fragment");
assert.match(app, /document\.createDocumentFragment\(\)/, "Keyed row reconciliation should move unchanged nodes without rebuilding the list");
assert.match(app, /current\.some\(\(node, index\) => node !== desiredNodes\[index\]\)/, "Keyed row reconciliation should detect reorders as DOM changes");
assert.match(app, /let domChanged = false;/, "Keyed commits must distinguish DOM writes from render-signature bookkeeping");
assert.match(app, /domChanged = true;/, "Only actual row replacements or a full fallback replacement may flag layout work");
assert.match(app, /return domChanged;/, "Comparable live rows must not restart covers/layout merely because the signature changed");
assert.match(app, /function trackRowComparableHtml\(node\)/, "Row commits must normalize cover-loader runtime mutations before comparing markup");
assert.match(app, /existingSignature !== nextSignature\s*&& trackRowComparableHtml\(existing\) !== trackRowComparableHtml\(node\)/, "Snapshot-to-authoritative signature drift must compare final presentation before replacing a row");
assert.match(app, /copy\.removeAttribute\?\.\("data-track-row-signature"\)/, "Final row comparison must ignore the non-visible reconciliation signature");
assert.match(app, /data-track-row-signature/, "Track rows should expose a stable markup signature for cheap keyed reconciliation");
assert.ok(index.indexOf('src="library_row_signature_policy.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Row signature policy must load before app.js");
assert.match(app, /function trackRowMarkupSignature\(item, index = 0, columns = activeTrackColumns\(\), columnValues = \{\}, localCover = ""\)/, "Row reconciliation must use rendered values and the normalized cover URL");
assert.match(app, /trackRowMarkupSignature\(item, index, columns, columnValues, localCover\)/, "Rows must pass their already formatted cells into the reconciliation signature");
assert.match(rowSignaturePolicy, /transport-only differences cannot replace decoded cover nodes/, "Snapshot and network rows must compare by presentation rather than raw JSON types");
assert.match(app, /existingSignature && nextSignature[\s\S]*?existingSignature !== nextSignature/, "Keyed row reconciliation should compare signatures before cloning live DOM nodes");
assert.match(app, /function preserveTrackCoverNode\(current, next\)/, "Changed rows should preserve an already decoded cover when the URL is unchanged");
assert.match(app, /api\/lyrics\?track_id=\$\{encodeURIComponent\(trackId\)\}/, "Playback should opportunistically prefetch lyrics for the current track");
assert.match(app, /state\.metadataPrefetchLyricsTrackId !== trackId/, "Lyrics prefetch must be coalesced per current track");
assert.match(app, /const METADATA_PREFETCH_MAX_ATTEMPTS = 12;/, "Current-track metadata retries must use an explicit bounded budget");
assert.match(app, /state\.metadataPrefetchAttempts >= METADATA_PREFETCH_MAX_ATTEMPTS/, "Current-track metadata retries must remain bounded");
assert.match(app, /let retryFailed = false;/, "Current-track metadata polling must distinguish pending from a terminal retry");
assert.match(app, /request\(retryFailed\)\.catch\(\(\) => scheduleRetry\(\)\);/, "Current-track pending polls must not always force retry=1");
assert.match(app, /retryFailed = !requestedRetry && \(responseStatus === "failed" \|\| responseStatus === "no_match"\);/, "Current-track terminal failures must arm the one explicit recovery request");
assert.match(app, /function scheduleVisibleMetadataPrefetch\(items = \[\], requestSeq = state\.libraryRequestSeq\)/, "Visible first-page metadata should use a dedicated bounded lane");
assert.match(visibleMetadataPolicy, /result\.length >= bounded/, "Visible metadata prefetch must stay small and bounded");
assert.match(visibleMetadataPolicy, /function selectCandidates\(items, limit = DEFAULT_LIMIT, excludedId = ""\)/, "Visible metadata prefetch should support excluding the current priority track");
assert.match(app, /selectCandidates\(items, 6, excludedCurrentTrackId\)/, "Current-track priority metadata must not be duplicated while its priority lane is active");
assert.match(app, /Promise\.all\(\[worker\(\), worker\(\)\]\)/, "Visible metadata prefetch should use at most two concurrent requests");
assert.match(app, /for \(let attempt = 0; attempt < 12; attempt \+= 1\)/, "Visible metadata prefetch should retry slow pending providers within a bounded budget");
assert.match(app, /shouldRetry\(data, attempt, 12\)/, "Visible metadata prefetch policy must receive the expanded retry budget");
assert.match(app, /let retryFailed = false;/, "Visible metadata polling must not force-retry every pending response");
assert.match(app, /retryFailed = !requestedRetry && \(status === "failed" \|\| status === "no_match"\)/, "Only terminal metadata failures may arm an explicit retry");
assert.match(app, /retryFailed = !requestedRetry && \(status === "failed" \|\| status === "no_match"\)/, "Visible terminal retries must be consumed after one explicit recovery request");
assert.match(app, /fnAudioMetadataResponsePolicy\?\.isTransientHttpStatus\?\.\(response\.status\)/, "Transient metadata gateway responses must remain retryable");
assert.match(app, /await new Promise\(resolve => setTimeout\(resolve, 700\)\)/, "Visible metadata retries should yield between provider polls");
assert.match(app, /state\.metadataRowRenderUsesFrame = false;/, "Metadata row render cancellation must distinguish timers from animation frames");
assert.match(app, /function cancelMetadataRowRender\(\) \{[\s\S]*?cancelAnimationFrame\(state\.metadataRowRenderTimer\)[\s\S]*?state\.metadataRowRenderTrackIds\.clear\(\);[\s\S]*?state\.metadataRowRenderFieldsByTrack\.clear\(\);/, "Cancelling a metadata row batch must release the correct scheduler and discard its payload");
assert.match(app, /setTimeout\(flushMetadataRows, 180\)/, "Visible metadata burst updates should coalesce before patching the list");
assert.match(app, /state\.metadataRowRenderTrackIds = new Set\(\)/, "Metadata row updates should collect a bounded batch of visible ids");
assert.match(app, /const fieldsByTrack = new Map\(\[\.\.\.state\.metadataRowRenderFieldsByTrack\]/, "Metadata row patch eligibility should remain per-track");
assert.match(app, /const changedFields = \[\];[\s\S]*?changedFields\.push\(field\);[\s\S]*?changedFields\.push\("cover_url"\);[\s\S]*?scheduleMetadataRowRender\(id, changedFields\);/, "Visible metadata enrichment should patch rows using only fields that actually changed");
assert.match(app, /const visibleItemsById = new Map\(state\.pageItems\.map\(\(item, index\) => \[String\(item\?\.id \|\| ""\), \{ item, index \}\]\)\);/, "Metadata bursts should build one bounded visible-row lookup");
assert.match(app, /visiblePendingIds\.reduce\(\(count, id\) => \{[\s\S]*?metadataRowPatchOnly\(id, location\?\.item, location\?\.index,/, "Visible metadata bursts should use keyed row patches with the batch lookup");
assert.match(app, /const rowsById = new Map\(\[\.\.\.\(\$\("trackList"\)\?\.querySelectorAll\?\.\("\[data-track-id\]"\)/, "Metadata bursts should build one live row lookup");
assert.match(app, /const columns = activeTrackColumns\(\);[\s\S]*?metadataRowPatchOnly\(id, location\?\.item, location\?\.index, \{ rowsById, columns, deferSelection: true \}\)/, "Metadata row patches should reuse columns and defer selection refresh to the batch");
assert.match(app, /if \(patched > 0\) \{[\s\S]*?setTrackSelection\(\[\.\.\.state\.selectedTrackRowKeys\], false\);/, "Metadata bursts should refresh row selection once after patching");
assert.match(app, /if \(patched > 0\) \{[\s\S]*?state\.renderedTrackListHtml = renderTrackRows\(state\.pageItems\);/, "Metadata bursts should restore declarative page markup once after keyed patches");
assert.match(app, /const patched = visiblePendingIds\.reduce\(\(count, id\) =>[\s\S]*?if \(patched > 0\) hydrateVisibleTrackCovers\(\);/, "Visible metadata bursts should hydrate covers once per batch");
assert.match(app, /const visiblePendingIds = pendingTrackIds\.filter\(id => visibleItemsById\.has\(id\)\);[\s\S]*?visiblePendingIds\.every\(id => policy\?\.canPatchRow/, "Off-page metadata completions must not force a full render for visible rows");
assert.match(app, /if \(!forceFull && !visiblePendingIds\.length\) return;/, "An all-off-page metadata batch must be a no-op instead of rendering the current list");
assert.match(app, /visiblePendingIds\.length && patched !== visiblePendingIds\.length\) render\(\);/, "A metadata burst must fall back when any visible keyed row is unavailable");
assert.match(app, /state\.metadataRowRenderExpectedRequestSeq = state\.libraryRequestSeq;[\s\S]*?state\.metadataRowRenderExpectedView = state\.view;[\s\S]*?state\.metadataRowRenderExpectedPage = state\.page;[\s\S]*?state\.metadataRowRenderExpectedPageItems = state\.pageItems;/, "Deferred metadata commits must capture the visible list identity");
assert.match(app, /function metadataRowRenderBatchMatchesCurrent\(\) \{[\s\S]*?fnAudioMetadataRowPatchPolicy[\s\S]*?sameListIdentity\(expected, current\)/, "Metadata row scheduling should delegate visible-list identity checks to the isolated policy");
assert.match(app, /if \(!metadataRowRenderBatchMatchesCurrent\(\)\) return;/, "Stale metadata commits must not repaint a switched page or view");
assert.match(app, /const batchIsStale = state\.metadataRowRenderTimer && !metadataRowRenderBatchMatchesCurrent\(\);[\s\S]*?if \(batchIsStale\) cancelMetadataRowRender\(\);/, "A new page's metadata update must replace an obsolete deferred batch instead of being discarded with it");
assert.match(app, /const seq = \+\+state\.libraryRequestSeq;[\s\S]*?cancelReferencedItemHydrationSchedule\(\);[\s\S]*?cancelMetadataRowRender\(\);[\s\S]*?cancelVisibleMetadataPrefetch\(\{ releaseKeys: true \}\);/, "A new library request must cancel pending metadata row commits before replacing the page");
assert.match(app, /scheduleMetadataRowRender\(""\);/, "Client-side pagination must not reference an undefined track callback variable");
assert.match(app, /function cancelVisibleMetadataPrefetch\(options = \{\}\)/, "Visible metadata prefetch must be cancellable on view changes");
assert.match(app, /state\.visibleMetadataPrefetchController = null;/, "Visible metadata prefetch should own an abort controller");
assert.match(app, /state\.visibleMetadataPrefetchController\?\.abort\(\)/, "Cancelling visible metadata should abort in-flight requests");
assert.match(
  app,
  /try \{\s*await Promise\.all\(\[worker\(\), worker\(\)\]\);\s*\} finally \{\s*\/\/[^\n]*\n[\s\S]*?if \(state\.visibleMetadataPrefetchController === controller\) \{/,
  "A throwing visible metadata worker must still release its lane identity",
)

assert.match(app, /state\.visibleMetadataPrefetchActiveKeys = new Map\(\);/, "Visible metadata should track in-flight dedupe claims separately");
assert.match(app, /state\.visibleMetadataPrefetchActiveKeys\?\.forEach\(\(owner, key\) => \{[\s\S]*?state\.visibleMetadataPrefetchActiveKeys\.delete\(key\);/, "Cancelling a same-page metadata lane must release its in-flight keys");
assert.match(app, /state\.visibleMetadataPrefetchActiveKeys\.set\(key, generation\);[\s\S]*?finally \{[\s\S]*?get\(key\) === generation[\s\S]*?delete\(key\);/, "Completed or cancelled metadata work must release only its own active-key ownership");
assert.match(app, /state\.visibleMetadataPrefetchRearmTimer = 0;/, "Pending visible metadata needs explicit quiet re-arm ownership");
assert.match(app, /state\.visibleMetadataPrefetchRearmSeq = 0;/, "Pending visible metadata re-arms need a separate generation owner");
assert.match(app, /const preserveRearm = !cancelRearms && Boolean\(state\.visibleMetadataPrefetchRearmTimer\);/, "Status refreshes must preserve only an active pending re-arm");
assert.match(app, /if \(preserveRearm\) state\.visibleMetadataPrefetchRearmSeq = state\.visibleMetadataPrefetchSeq;/, "Preserved re-arms must be rebound after cancelling the old worker generation");
assert.match(app, /state\.visibleMetadataPrefetchRearmSeq !== state\.visibleMetadataPrefetchSeq/, "Re-arm callbacks must validate their rebound generation");
assert.match(app, /function scheduleVisibleMetadataPrefetchRearm\(key, data, attempts, generation, requestSeq\)/, "Exhausted pending rows should have a page-scoped recovery path");
assert.match(app, /shouldRearmPending\?\.\(data, attempts, knownRearms, 12, 2\)/, "Pending re-arms must use the shared finite policy");
assert.match(app, /cancelVisibleMetadataPrefetch\(\{ cancelRearms: false \}\);/, "Ordinary metadata refreshes should preserve an already scheduled quiet re-arm");
assert.match(app, /signal: controller\.signal/, "Visible metadata requests should carry the shared cancellation signal");
assert.match(app, /function rememberVisibleMetadataPrefetchKey\(key, limit = 256\)/, "Visible metadata deduplication should use an explicit bounded FIFO policy");
assert.match(app, /state\.visibleMetadataPrefetchKeys\.values\(\)\.next\(\)\.value/, "Visible metadata deduplication should evict the oldest key instead of clearing all history");
assert.match(app, /cancelVisibleMetadataPrefetch\(\{ releaseKeys: true \}\)/, "Visibility cancellation must release claimed metadata keys for foreground recovery");
assert.match(app, /scheduleVisibleMetadataPrefetch\(state\.pageItems, state\.libraryRequestSeq\)/, "Returning to the foreground must resume visible metadata prefetch");
assert.match(app, /state\.libraryRequestSeq \+= 1;[\s\S]*?cancelVisibleMetadataPrefetch\(\{ releaseKeys: true \}\)/, "Leaving a library view must release cancelled metadata keys");
assert.match(app, /if \(!rememberVisibleMetadataPrefetchKey\(key, 256\)\) continue;/, "Visible metadata prefetch should use the FIFO deduplication policy");
  assert.match(app, /const terminalRelease = data\.retryable === true[\s\S]*?releaseCompletedKey\?\.\(key, data, scheduleVisibleMetadataPrefetchCooldown, decision\)[\s\S]*?state\.visibleMetadataPrefetchKeys\.delete\(key\);/, "A retryable or terminal visible projection may only release its page dedupe key through the cooldown verdict");
assert.match(app, /scheduleVisibleMetadataPrefetch\(state\.pageItems, seq\);/, "Authoritative first-page paint should seed visible metadata prefetch");
assert.match(app, /render\(\);\s*\/\/ Persist the enriched visible page during idle time\.[\s\S]*?scheduleLibraryPageSnapshot\(state\.page\);/, "Metadata row commits should refresh the bounded startup snapshot");
assert.match(app, /patchTrackRowNode\(existing, node\);/, "Keyed row patches must update the existing live row instead of replacing it");
assert.match(app, /if \(currentCover && nextCover && currentSource !== nextSource\) currentCover\.innerHTML = nextCover\.innerHTML;/, "A keyed row patch must retain its live cover tile unless artwork changes");
assert.match(app, /nextImage\.replaceWith\(currentImage\)/, "Cover preservation should move the live decoded image node instead of re-requesting it");
assert.match(app, /image\.removeAttribute\(\"src\"\);/, "A decoded cover src must not force an unrelated row replacement");
assert.match(app, /image\.removeAttribute\(\"data-cover-queued\"\);/, "Cover scheduler generation markers must not force an unrelated row replacement");
assert.match(app, /image\.dataset\?\.coverLoadedSrc/, "Comparable rows must prefer the scheduler's original relative cover source");
assert.match(app, /image\.removeAttribute\(\"data-cover-loaded-src\"\);/, "The scheduler source marker must not become persisted row markup");
assert.match(app, /image\.removeAttribute\(\"data-cover-observed\"\);/, "The observer ownership marker must not become persisted row markup");
assert.match(app, /fallback => fallback\.removeAttribute\(\"hidden\"\)/, "Loaded fallback visibility must not force an unrelated row replacement");
assert.match(app, /if \(!patched\) \{\s*list\.innerHTML = listHtml;\s*domChanged = true;/, "Unkeyed views must retain a safe full replacement fallback");
assert.match(app, /function needsVisibleTrackCoverHydration\(\)/, "Cover scheduling must distinguish new cover nodes from ordinary row patches");
assert.match(app, /if \(!image\.dataset\.coverQueued && !image\.dataset\.coverObserved\) return true;/, "A playing-state patch must not restart queued or observer-owned covers");
assert.match(app, /state\.coverLoadScheduler && !needsVisibleTrackCoverHydration\(\)/, "Existing cover observer should be reused when no new cover work exists");
assert.match(app, /head\.dataset\.fnaudioTableHeadSignature !== signature/, "Unchanged table headers must not be rebuilt on ordinary list renders");
assert.match(app, /const changed = head\.dataset\.fnaudioTableHeadSignature !== signature;/, "Header rendering must report whether it actually changed DOM");
assert.match(app, /head\.dataset\.fnaudioTableHeadBound === "1"/, "Unchanged table headers must not rebind event handlers");
assert.match(app, /head\.dataset\.fnaudioTableHeadBound = "1"/, "Changed table headers must mark their handlers as bound");
assert.match(app, /const signature = JSON\.stringify\(\[mode, template, markup\]\);/, "Header identity must include view mode, column template and markup");
assert.match(app, /Do not use a NUL separator here/, "Header signatures must remain stable through dataset DOMString normalization");
assert.match(app, /state\.metadataCandidatePollTimer = 0;/, "Metadata candidate polling must have explicit timer state");
assert.match(app, /const METADATA_CANDIDATE_MAX_POLLS = 12;/, "Metadata candidate polling must use an explicit bounded budget");
assert.match(app, /state\.metadataCandidatePollAttempts < METADATA_CANDIDATE_MAX_POLLS/, "Metadata candidate polling must remain bounded");
assert.match(app, /state\.metadataCandidateRequestToken = 0;/, "Metadata candidate requests must have ownership tokens");
assert.match(app, /state\.metadataCandidateController = null;/, "Metadata candidate requests need explicit cancellation ownership");
assert.match(app, /requestToken === state\.metadataCandidateRequestToken/, "Stale candidate responses must not overwrite the active dialog");
assert.match(app, /data-retry-track-metadata/, "Negative metadata matches must expose an explicit retry action");
assert.match(app, /retry=1/, "Only a deliberate metadata retry may replace a negative cache entry");
assert.match(app, /完成后将自动显示/, "Pending metadata candidates should update without requiring the user to reopen the dialog");
assert.match(app, /clearTimeout\(state\.metadataCandidatePollTimer\)/, "Closing the metadata dialog must cancel its poll");
assert.match(app, /state\.metadataCandidateController\?\.abort\(\)/, "Closing or replacing the metadata dialog must abort an in-flight lookup");
assert.match(app, /error\?\.name === "AbortError"/, "Cancelled metadata candidate lookups must not be rendered as failures");
assert.match(app, /const applyController = typeof AbortController === "function" \? new AbortController\(\) : null;[\s\S]*?state\.metadataCandidateController = applyController;/, "Metadata candidate confirmation must own a cancellable request");
assert.match(app, /api\/metadata\/track\/apply[\s\S]*?signal: applyController\.signal/, "Metadata candidate confirmation must propagate its cancellation signal");
assert.match(app, /if \(!isCurrentRequest\(\) \|\| state\.metadataCandidateController !== applyController\) return;[\s\S]*?已确认，后台将只补全空白 Tag 字段/, "A stale metadata confirmation must not overwrite a replaced dialog");
assert.match(app, /cooldown_seconds/, "Metadata status should expose provider cooldown observability");
assert.match(app, /冷却\$\{cooldown\}s/, "Provider cooldown should be visible in the metadata status summary");
assert.match(app, /value\.last_error\.replace\(/, "Metadata status should expose a bounded provider failure reason");
assert.match(app, /slice\(0, 96\)/, "Provider failure reason must remain bounded in the settings UI");
assert.match(app, /const listChanged = deferListCommit \? false : commitTrackListHtml\(listHtml\);/, "Track DOM replacement must retain the row markup guard while deferring a transient empty commit during snapshot loading");
assert.match(app, /fnAudioLibraryRenderPolicy\?\.shouldDeferListCommit\(/, "Snapshot defer decision must use the isolated render policy");
assert.match(renderPolicy, /function shouldDeferListCommit\(options\)/, "Snapshot defer decision must remain a pure bounded policy");
assert.match(app, /fnAudioLibraryRenderPolicy\?\.hasVisiblePresentation\(/, "Visible presentation detection must use the isolated render policy");
assert.match(renderPolicy, /function hasVisiblePresentation\(snapshot\)/, "Visible presentation detection must remain a pure bounded policy");
assert.match(renderPolicy, /index < value\.length && index < MAX_RENDER_ROWS && result\.length < max/, "Malformed early snapshot rows must not consume valid row slots");
assert.match(app, /function reuseSnapshotTrackMarkup\(previousItems, nextItems, snapshotHit\)/, "Warm first pages need an explicit snapshot-markup reuse boundary");
assert.match(app, /reuseSnapshotTrackMarkup\(snapshotItems, state\.pageItems, snapshotHit\);/, "An equivalent authoritative first page must retain the already-rendered snapshot markup");
assert.match(snapshotReusePolicy, /function canReuseMarkup\(previous, next\)/, "Snapshot markup reuse must stay in a pure bounded policy");
assert.match(app, /setTrackSelection\(\[\.\.\.state\.selectedTrackRowKeys\], listChanged\);/, "Stable list renders must avoid re-walking every track selection");
assert.match(app, /function sameTrackSelection\(left, right\)/, "Selection comparison must remain a pure bounded set check");
assert.match(app, /if \(!force && sameTrackSelection\(state\.selectedTrackRowKeys, requested\)\) return;/, "Unchanged selection must not traverse visible rows");
assert.match(app, /if \(nav\.dataset\.fnaudioPlaylistNavMarkup === markup\) return;/, "Stable playlist navigation must not be rebuilt on player-only renders");
assert.match(app, /if \(state\.sortKey !== previousKey\) writeStoredPreference\("fnaudio\.sortKey\.v1", state\.sortKey\);/, "Sort-key persistence must not run on every player-state render");
assert.doesNotMatch(app, /sortDirBtn|updateSortDirectionButton/, "Removed toolbar sort-direction projection must not return");
assert.match(app, /data-track-sort="\$\{sortKey\}"/, "Sort direction must remain projected through dynamic table-header controls");
assert.match(app, /track-sort-indicator/, "Active sort direction must remain visible in the table header");
assert.match(app, /state\.sortDir === "asc" \? "&#9650;" : "&#9660;"/, "Sort direction indicator must follow the active direction");
assert.match(app, /function setTextContentIfChanged\(node, value\)/, "Status decoration writes need a shared change guard");
assert.match(app, /function mergeAuthoritativePageItems\(items = \[\]\)/, "Authoritative pages must preserve session-local enrichment when fields are temporarily absent");
assert.match(app, /fnAudioLibraryMetadataMergePolicy\?\.merge\(items, state\.pageItems, state\.itemCache\)/, "Page merge should use the isolated metadata policy");
assert.match(metadataMerge, /const old = previous\.get\(id\) \|\| cached;/, "Cross-view page loads must reuse bounded item-cache metadata");
assert.match(metadataMerge, /if \(\(merged\[field\] == null \|\| String\(merged\[field\]\)\.trim\(\) === ""\)/, "Only empty authoritative fields may inherit session enrichment");
assert.match(metadataMerge, /const hasMergedSource = mergedSource && typeof mergedSource === "object"/, "Empty metadata-source objects must not hide cached provenance");
assert.match(app, /setTextContentIfChanged\(\$\("allCount"\), libraryCount\(state\.libraryStatus\?\.count\)\)/, "Library counters must use bounded counts and avoid unchanged text writes");
assert.match(app, /data-group-track-count="\$\{trackCount\}"/, "Group track counts must use bounded values");
assert.match(app, /Math\.ceil\(libraryCount\(state\.folderTotal\) \/ state\.folderPageSize\)/, "Folder pagination totals must use bounded values");
assert.match(app, /function updateNavigationActiveState\(\)/, "Navigation active-state updates need an explicit render guard");
assert.match(app, /if \(state\.renderedNavigationView === view\) return;/, "Stable navigation must not re-walk all items on player-only renders");
assert.match(app, /if \(button\.dataset\.repeat !== repeat\) \{\s*button\.dataset\.repeat = repeat;\s*icon\.innerHTML = repeatIconMarkup\(repeat\);/, "Repeat icon markup must only be replaced when its mode changes");
assert.match(app, /if \(listChanged\) \{\s*document\.querySelectorAll\("\[data-delete-playlist\]"\)/, "List-local controls should only be rebound after a list DOM change");
assert.match(app, /function refreshFavoritePresentation\(\)/, "Favorite changes need a dedicated presentation path");
assert.match(app, /if \(state\.view === "favorites"\) render\(\);/, "Only the favorites-derived view should redraw song rows after a favorite change");
assert.doesNotMatch(app, /saveFavorites\(\);\s*updateFavoriteControls\(\);\s*render\(\);/, "Favorite changes outside the favorites view must not force an unrelated list render");
assert.match(app, /const pagerChanged = pager\.innerHTML !== pagerHtml;/, "Unchanged pagination controls must not be recreated on ordinary renders");
assert.match(app, /if \(listChanged \|\| tableHeadChanged \|\| albumHeadChanged \|\| pagerChanged\)/, "Expensive row measurement must run only after list or layout DOM changes");
assert.match(app, /const fragment = orderUnchanged \? null : document\.createDocumentFragment\(\);/, "Stable keyed rows must not be detached into a fragment before an actual reorder");
assert.match(app, /if \(fragment\) list\.appendChild\(fragment\);/, "Only a real keyed reorder may move rows through a fragment");
assert.match(app, /if \(refresh\) \{[\s\S]*?updateLibraryStatusDecorations\(\);[\s\S]*?\}/, "Refresh progress must update labels without repainting the whole list");
assert.ok(app.includes('loading="${index < 8 ? "eager" : "lazy"}"'), "Track covers should use a bounded first-paint loading policy");
assert.ok(app.includes('decoding="async"'), "Track covers should decode asynchronously");
assert.match(app, /!this\.dataset\.coverSchedulerOwned&&source&&retry<1/, "scheduler-owned lazy covers must not double-schedule inline retries");
assert.ok(app.includes('src="${escapeHtml(localCover)}"'), "The bounded first cover burst should start loading immediately");
assert.match(app, /const coverFallback = `<span class="track-cover-fallback">♫<\/span>`;/, "Every cover row must retain its placeholder until image decode");
assert.match(app, /async function fetchLibraryResponse\(url, message, refresh = false, signal = undefined\)/);
assert.match(app, /state\.libraryResponseCache = fnAudioLruCache\(48, \{ maxWeight: 6000, weightOf: libraryResponseWeight \}\);/);
assert.match(app, /state\.libraryResponseInflight = new Map\(\);/, "Library loads must track in-flight requests");
assert.match(app, /state\.libraryResponseInflightLimit = 32;/, "In-flight library requests must have a hard bound");
assert.match(app, /state\.libraryResponseActive = \{ value: 0 \};/, "Refresh and ordinary library requests must share one active counter");
assert.match(app, /state\.libraryResponseEpoch = 0;/, "Library response cache must track invalidation generations");
assert.match(app, /state\.libraryStatusTimer = setTimeout\(\(\) => \{[\s\S]*?refreshLibraryStatus\(refresh\);[\s\S]*?\}, 120\);/, "Library status aggregation must yield to the first page paint and shared request boundary");
assert.match(app, /const responsePromise = fetch\(`api\/library\/status\$\{refresh \? \"\?refresh=1\" : \"\"\}`, \{[\s\S]*?cache: \"no-store\",[\s\S]*?signal: controller\.signal/, "Shared library status refresh must preserve the endpoint, explicit refresh mode, cache bypass, and cancellation signal");
assert.match(app, /state\.accessProfileTimer = setTimeout\(\(\) => \{[\s\S]*?accessProfileLoader\?\.load\(\)[\s\S]*?\}, 320\);/, "Access profile must yield to the first page paint");
assert.match(app, /state\.metadataProjectionSignature = "";/, "Metadata projection must have an explicit initial signature");
assert.match(app, /state\.filteredTracksCache = \{ signature: null, tracks: \[\] \};/, "Filtered library views must have an explicit bounded memo state");
assert.match(app, /cache\.signature\.every\(\(value, index\) => value === signature\[index\]\)/, "Filtered track memo must invalidate when view inputs change");
assert.match(app, /function invalidateTrackRowsMarkup\(items = state\.pageItems\)[\s\S]*?state\.filteredTracksCache = \{ signature: null, tracks: \[\] \};/, "In-place metadata backfill must invalidate filtered track memo");
assert.match(app, /function retryCurrentTrackMetadataAfterRecovery\(metadata\)/, "Recovered metadata workers must re-arm an exhausted current-track prefetch");
assert.match(app, /function fetchMetadataRequest\(url, timeoutMs = 10000, externalSignal = undefined\)/, "Metadata requests should accept an owning cancellation signal");
assert.match(app, /state\.metadataRequestLoader\?\.load\) return state\.metadataRequestLoader\.load\(url, run, externalSignal\)/,
  "current-track, visible-row and candidate callers must use one shared URL single-flight boundary");
assert.match(app, /async function fetchJsonResponseBounded\(input, init = \{\}, timeoutMs = 15000\)/, "Interactive JSON API reads must have a shared timeout and cancellation boundary");
assert.match(app, /function fetchLibraryItemsByIds\([\s\S]*?fetchJsonResponseBounded\(/, "Referenced item hydration must use the bounded JSON response loader");
assert.match(app, /async function resolveTrackLocation\([\s\S]*?fetchJsonResponseBounded\(/, "Track location lookup must use the bounded JSON response loader");
assert.match(app, /function fetchMetadataRequest\(url, timeoutMs = 10000, externalSignal = undefined\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?onTimeout: abort,/, "Metadata request timeouts must abort the shared underlying request");
assert.match(app, /function cancelCurrentTrackMetadataPrefetch\(\)/, "Current-track metadata should expose an explicit cancellation boundary");
assert.match(app, /state\.metadataPrefetchController\?\.abort\(\)/, "Switching tracks must abort the current metadata request");
assert.match(app, /state\.metadataPrefetchLyricsController\?\.abort\(\)/, "Switching tracks must abort the current lyrics request");
assert.match(app, /state\.metadataPrefetchLyricsTrackId = "";/, "Settled empty lyric projections must release their per-track dedupe marker");
assert.match(app, /state\.lyricsRequestController = null;/, "Lyrics view must own an active request controller");
assert.match(app, /function cancelLyricsRequest\(\)/, "Lyrics requests must expose an explicit cancellation boundary");
assert.match(app, /fetchMetadataRequest\(/, "Lyrics view must use the bounded metadata request helper");
assert.match(app, /cancelLyricsRequest\(\);\s*state\.lyricsPollAttempts = 0;/, "Switching lyric tracks must abort the previous request");
assert.match(app, /if \(error\?\.name === "AbortError"\) return;/, "Cancelled lyric requests must not be shown as provider failures");
assert.match(app, /fetchMetadataRequest\(`api\/lyrics\?track_id=\$\{encodeURIComponent\(trackId\)\}[\s\S]*?lyricsController\?\.signal\)/, "Priority lyrics requests must share the current-track cancellation signal");
assert.match(app, /fetchMetadataRequest\(`api\/metadata\/track\?track_id=\$\{encodeURIComponent\(trackId\)\}[\s\S]*?controller\?\.signal\)/, "Priority metadata requests must share the current-track cancellation signal");
assert.match(app, /async function showTrackMetadataCandidate\([\s\S]*?fetchMetadataRequest\([\s\S]*?api\/metadata\/track\?track_id=\$\{encodeURIComponent\(String\(trackId\)\)\}[\s\S]*?controller\?\.signal/, "Metadata candidate dialog requests must use the bounded cancellable loader");
assert.match(app, /externalSignal\.addEventListener\("abort", abortFromOwner/, "Visible metadata cancellation must propagate to in-flight requests");
assert.match(app, /controller\?\.signal,\s*\n\s*\);/, "Visible metadata requests must share the page-owned cancellation signal");
assert.match(app, /error\.name = "AbortError"/, "Metadata timeout must use cancellation semantics so it remains retryable");
assert.match(app, /scheduleLyricsRetry = \(retryFailed = false\) => \{[\s\S]*?metadataPrefetchLyricsAttempts >= 12/, "Lyrics timeout must retain a bounded retry path");
assert.match(app, /fetchMetadataRequest\(\s*`api\/metadata\/track\?track_id=\$\{encodeURIComponent\(id\)\}[\s\S]*?8000,\s*controller\?\.signal,\s*\)/, "Visible metadata prefetch must use a bounded request timeout and cancellation signal");
assert.match(app, /shouldReuseActiveLane\?\.\(\s*requestSeq,\s*state\.visibleMetadataPrefetchRequestSeq,\s*items === state\.visibleMetadataPrefetchItems,\s*hasPendingWork/, "Same-page metadata status refreshes must reuse active work");
assert.match(app, /\|\| state\.visibleMetadataPrefetchRearmTimer/, "A queued finite metadata re-arm must survive same-page status refreshes");
assert.match(app, /if \(!state\.visibleMetadataPrefetchRearmTimer\) \{\s*state\.visibleMetadataPrefetchRequestSeq = 0;/, "A pending finite re-arm must retain its page identity until it fires or is cancelled");
assert.match(app, /responsePending \|\| data\.retryable === true/, "Filename/negative-cache metadata candidates must keep bounded provider recovery alive");
assert.match(app, /state\.metadataPrefetchRecoverySeen === trackId/, "Metadata recovery retry must be deduplicated per track");
assert.match(app, /retryCurrentTrackMetadataAfterRecovery\(metadata\);/, "Metadata status refresh must re-arm current-track prefetch after worker recovery");
assert.match(app, /function metadataProjectionSignature\(data = \{\}\)/, "Metadata completion changes need a stable projection signature");
assert.match(app, /function coverUrl\(item, size = 160\)[\s\S]*?try \{[\s\S]*?new URL\([\s\S]*?catch \(error\)/, "Malformed cover URLs must be isolated from the full list render");
assert.match(app, /function coverUrl\(item, size = 160\)[\s\S]*?\["http:", "https:"\]\.includes\(url\.protocol\)/, "Cover URLs must reject executable or unsupported schemes");
assert.match(app, /function mediaUrl\(path\)[\s\S]*?path\.length <= 4096[\s\S]*?\["http:", "https:"\]\.includes\(url\.protocol\)/, "Shared media URLs must be bounded and restricted to HTTP(S)");
assert.match(app, /data-add-to-list="\$\{escapeHtml\(list\.id\)\}"/, "Playlist identifiers must be escaped before entering HTML attributes");
const coverPaintSource = app.match(/function setCoverArtwork\(node, source\) \{[\s\S]*?\n\}\nfunction setNowPlayingCover\(source\) \{[\s\S]*?\n\}/);
assert.ok(coverPaintSource, "The now-playing and lyric cover repaint path must stay independently testable");
assert.doesNotMatch(app, /\$\("(?:nowCover|lyricsCover)"\)\.(?:innerHTML|textContent)/, "Cover blocks must be painted only through the shared helper so a poll cannot destroy a decoded image");
assert.equal((app.match(/node\.innerHTML = next/g) || []).length, 1, "Only the shared cover helper may write cover markup");
const coverPaintNodes = {};
function createCoverPaintNode() {
  let html = "\u266b";
  let writes = 0;
  return {
    dataset: {},
    get innerHTML() { return html; },
    set innerHTML(value) { html = value; writes += 1; },
    get coverWrites() { return writes; },
  };
}
["nowCover", "lyricsCover"].forEach(id => { coverPaintNodes[id] = createCoverPaintNode(); });
const coverPaintContext = {
  coverPaintNodes,
  $: id => coverPaintNodes[id],
  escapeHtml: value => String(value || "").replace(/[&<>"']/g, x => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[x])),
};
vm.runInNewContext(`${coverPaintSource[0]}; globalThis.paintNow = setNowPlayingCover; globalThis.paintNode = (id, value) => setCoverArtwork(coverPaintNodes[id], value);`, coverPaintContext);
assert.equal(coverPaintNodes.nowCover.coverWrites, 0, "Nothing may repaint the cover before an address arrives");
assert.equal(coverPaintContext.paintNow("api/cover/a.jpg"), true, "The first cover address must paint");
assert.equal(coverPaintNodes.nowCover.coverWrites, 1);
assert.match(coverPaintNodes.nowCover.innerHTML, /^<img src="api\/cover\/a\.jpg"/, "The painted markup must carry the cover address");
assert.equal(coverPaintContext.paintNow("api/cover/a.jpg"), false, "A repeated address must be a no-op");
assert.equal(coverPaintNodes.nowCover.coverWrites, 1, "The 1.5s renderer poll must not re-decode the same cover");
assert.equal(coverPaintContext.paintNow("api/cover/b.jpg"), true, "A changed address must repaint");
assert.equal(coverPaintNodes.nowCover.coverWrites, 2);
assert.equal(coverPaintContext.paintNow("<img>"), true);
assert.match(coverPaintNodes.nowCover.innerHTML, /^<img src="&lt;img&gt;"/, "Cover addresses must pass through the HTML escaper");
assert.equal(coverPaintContext.paintNow(null), true, "A non-string address must clear the cover once");
assert.equal(coverPaintNodes.nowCover.innerHTML, "\u266b", "An absent cover must show the fallback glyph");
assert.equal(coverPaintContext.paintNow(""), false, "A cleared cover must stay cleared");
assert.equal(coverPaintNodes.nowCover.coverWrites, 4, "Only real address changes may touch the DOM");
assert.equal(coverPaintNodes.lyricsCover.coverWrites, 0);
assert.equal(coverPaintContext.paintNode("lyricsCover", "api/cover/c.jpg"), true, "The lyric cover must share the dedupe helper");
assert.match(coverPaintNodes.lyricsCover.innerHTML, /onerror="this\.parentNode\.innerHTML='\u266b'"/, "A failed cover must fall back to the glyph instead of leaving an empty box");
assert.equal(coverPaintContext.paintNode("lyricsCover", "api/cover/c.jpg"), false, "The 900ms lyric retry poll must not re-decode the same cover");
assert.equal(coverPaintNodes.lyricsCover.coverWrites, 1);
assert.equal(coverPaintContext.paintNode("missingCover", "api/cover/d.jpg"), false, "A missing cover node must be ignored");
assert.match(app, /function usableCoverSource\(value\)/, "Metadata artwork writes must validate the source before mutating a row");
assert.match(app, /const online = usableCoverSource\(metadataImage\)/, "Group metadata artwork must use the bounded cover source validator");
assert.match(app, /const onlineCover = usableCoverSource\(metadata\.image_url\)/, "Album metadata artwork must use the bounded cover source validator");
assert.match(app, /const candidateArtwork = usableCoverSource\([\s\S]*?selectDisplayArtwork/, "Candidate artwork must be selected independently from the displayed metadata candidate");
assert.match(app, /function applyGroupArtwork\(node, imageUrl\)[\s\S]*?const normalizedUrl = usableCoverSource\(imageUrl\)/, "Group artwork fallbacks must reuse the bounded cover source validator");
assert.match(app, /function applyGroupArtwork\(node, imageUrl\)[\s\S]*?data-cover-src/, "Group artwork fallbacks must enter the shared cover scheduler");
assert.match(app, /function applyGroupArtwork\(node, imageUrl\)[\s\S]*?hydrateVisibleTrackCovers\(\)/, "Group artwork fallbacks must trigger bounded hydration after local failure");
assert.match(app, /后台补全未开启（播放\/歌词页仍可按需获取）/, "Metadata status must distinguish disabled background enrichment from completion");
assert.match(app, /fnAudioMetadataProjectionPolicy\?\.signature\(data\)/, "Metadata projection signature must use the isolated policy module");
assert.match(metadataProjection, /global\.fnAudioMetadataProjectionPolicy = \{ signature \}/, "Metadata projection policy must expose a pure signature");
assert.doesNotMatch(metadataProjection, /safeCount\(source\.metadata_updated_at\)/, "Terminal-job timestamps must not independently invalidate the visible list");
assert.match(app, /async function fetchMetadataProjectionStatus\(externalSignal = undefined\)/, "Metadata projection status must have an isolated bounded request");
assert.match(app, /setTimeout\(\(\) => \{[\s\S]*controller\?\.abort\(\)/, "Metadata status observation must not block library status indefinitely");
assert.match(app, /const responsePromise = fetch\(`api\/library\/status\$\{refresh \? \"\?refresh=1\" : \"\"\}`, \{[\s\S]*?\}\);\s*const metadataProjectionDue = metadataProjectionIsDue\(Boolean\(refresh\)\);\s*if \(metadataProjectionDue\) state\.metadataProjectionLastFetchAt = Date\.now\(\);\s*const metadataPromise = metadataProjectionDue\s*\?\s*fetchMetadataProjectionStatus\(controller\?\.signal\)\s*:\s*Promise\.resolve\(null\);\s*const result = await globalThis\.fnAudioResponseJsonLoader\.read\(/, "Library status plus the throttled metadata projection must both start before the shared response-body timeout");
assert.match(app, /const result = await globalThis\.fnAudioResponseJsonLoader\.read\([\s\S]*?const response = result\.response;[\s\S]*?if \(token !== state\.libraryStatusRequestToken \|\| state\.libraryStatusController !== controller\) return;[\s\S]*?const payload = response\?\.ok \? result\.data : null;[\s\S]*?unwrapTransport\(payload, 4\)[\s\S]*?if \(!data\) return;[\s\S]*?state\.libraryStatus = data;[\s\S]*?updateLibraryStatusDecorations\(\);[\s\S]*?const metadata = await metadataPromise;/, "Library status must commit valid host envelopes before metadata status completes and preserve existing state on a failed response");
assert.match(app, /removeDeletedTracksFromClientState\(ids\);[\s\S]*?refreshLibraryStatus\(true\);/, "Post-delete status refresh must use the shared request boundary");
assert.match(app, /const queuedRefresh = state\.libraryStatusRefreshQueued;[\s\S]*?state\.libraryStatusRefreshQueued = false;[\s\S]*?if \(queuedRefresh\) refreshLibraryStatus\(true\);/, "A forced status refresh arriving during a poll must run once after the active request");
assert.match(app, /state\.libraryStatusTimer = setTimeout\(\(\) => \{[\s\S]*?refreshLibraryStatus\(refresh\);/, "Deferred library status refresh must reuse the shared request boundary");
assert.match(app, /async function refreshLibraryStatus\(refresh = false\)/, "Shared library status refresh must preserve explicit refresh semantics");
assert.match(app, /const data = payload\s*\?\s*\(globalThis\.fnAudioMetadataResponsePolicy\?\.unwrapTransport\(payload, 4\) \|\| \{\}\)\s*:\s*null;/, "Shared status failures must preserve the previous status instead of committing an empty object");
assert.match(app, /state\.libraryPageKey = isPagedTrackListing\(\) \? libraryLoadRequestKey\(state\.page\) : "";/, "Authoritative track pages must record their query identity after committing");
assert.match(app, /state\.libraryPageCursors = new Map\(\);/, "Sequential track-page continuation must have bounded client state");
assert.match(app, /params\.set\("cursor", continuation\);[\s\S]*?params\.set\("offset", "0"\);/, "Sequential track pages must prefer keyset continuation over deep offset traversal");
assert.match(app, /rememberLibraryPageCursor\(state\.page, data\);/, "Authoritative page responses must publish the next continuation token");
assert.match(app, /fnAudioLibraryPageCursorPolicy\?\.remember\(/, "Track continuation state must use the isolated cursor policy");
assert.match(app, /fnAudioLibraryPageCursorPolicy\?\.get\(/, "Track continuation reads must use the isolated cursor policy");
assert.match(pageCursorPolicy, /MAX_ENTRIES = 64/);
assert.match(pageCursorPolicy, /MAX_TOKEN_CHARS = 768/);
assert.match(app, /async function fetchAllTracksForCurrentView\(extra = \{\}\) \{[\s\S]*?const canReuseCurrentPage = state\.page === 1[\s\S]*?state\.view !== "random100"[\s\S]*?state\.libraryPageKey === libraryLoadRequestKey\(1\)[\s\S]*?state\.pageItems\.length <= pageSize[\s\S]*?const firstPage = canReuseCurrentPage[\s\S]*?\? \{ items: state\.pageItems, count: state\.pageTotal \}[\s\S]*?: await fetchPage\(0\)/, "Play-all should reuse a settled first page only when it exactly matches the current unfiltered track view");
assert.match(app, /async function fetchAllTracksForCurrentView\(extra = \{\}\) \{[\s\S]*?const baseQueryParams = currentQueryParams\(\);[\s\S]*?const params = new URLSearchParams\(baseQueryParams\.toString\(\)\);/, "Play-all batch requests must keep one frozen query identity across delayed workers");
assert.match(app, /async function fetchMetadataProjectionStatus\(externalSignal = undefined\)[\s\S]*?fnAudioResponseJsonLoader\.read\([\s\S]*?const data = unwrapMetadataResponsePayload\(result\.data\);[\s\S]*?return data\?\.ok === true \? data : null;/, "首屏 metadata 状态探测必须接受宿主包装响应并严格判断成功字段");
assert.match(app, /fetch\("api\/metadata\/status", \{[\s\S]*cache: "no-store"/, "Library status refresh must observe committed metadata changes");
assert.match(app, /if \(metadataChanged && state\.pageItems\?\.length && !state\.libraryLoading\)/, "Metadata refresh must be bounded to visible loaded pages");
assert.match(app, /state\.itemCache\.set\(trackId, item\);/, "Current-track metadata回投 must update the bounded identity cache");
assert.match(app, /function invalidateLibraryResponseForTrack\(trackId\)/, "Current-track metadata回投 needs targeted page-cache invalidation");
assert.match(app, /state\.libraryResponseCache\.deleteWhere\(/, "Page cache invalidation should remove only pages containing the changed track");
assert.match(app, /function invalidateLibraryResponseCacheForMetadataRevision\(\)/, "Global metadata revisions need a cache-only invalidation boundary");
assert.match(app, /async function fetchMetadataProjectionStatus\(externalSignal = undefined\)/, "Metadata status requests must accept the owning cancellation signal");
assert.match(app, /fetchMetadataProjectionStatus\(controller\?\.signal\)/, "Library status must cancel its parallel metadata request on invalidation");
assert.match(app, /const metadata = await metadataPromise;[\s\S]*?if \(token !== state\.libraryStatusRequestToken \|\| state\.libraryStatusController !== controller\) return;/, "Late metadata status results must not mutate a newer library view");
assert.match(app, /state\.libraryResponseCache\.clear\?\.\(\);/, "Global metadata revisions must retire completed page caches");
assert.match(app, /function invalidateLibraryResponseCacheForMetadataRevision\(\)[\s\S]*?state\.libraryResponseEpoch \+= 1;[\s\S]*?state\.libraryResponseCache\.clear\?\.\(\);/, "Global metadata revisions must reject stale in-flight cache writes");
assert.doesNotMatch(app, /metadataChanged && state\.pageItems\?\.length && !state\.libraryLoading\) \{\s*scheduleMetadataLibraryRefresh/, "Unrelated metadata changes must not reload a settled visible page");
assert.match(app, /invalidateLibraryResponseCacheForMetadataRevision\(\);/, "Metadata status changes must invalidate future-page cache without reloading the visible list");
assert.doesNotMatch(app, /metadataLibraryRefreshTimer|cancelMetadataLibraryRefresh/, "Cache-only metadata revisions must not retain the old whole-page refresh timer path");
assert.match(app, /if \(data\.scanning === true && !hasVisibleLibraryPresentation\(\)\) state\.libraryLoading = true;/, "A scan must keep the empty state hidden until the first authoritative page arrives");
assert.match(app, /if \(!retainedEmptySnapshot\) \{[\s\S]*?state\.librarySnapshot = \{[\s\S]*?hit: false/, "Authoritative pages must retire the bootstrap snapshot empty-response guard");
assert.match(app, /fnAudioLibraryPageSnapshotPolicy\?\.restore\(raw, \{[\s\S]*?boundItems: items => globalThis\.fnAudioLibraryRenderPolicy\?\.boundedTrackRows\(items, state\.pageSize\)/, "Bootstrap snapshots must be bounded and identity-checked before rendering");
assert.match(app, /index < 8/, "The first visible cover burst must remain bounded");
assert.match(app, /fetchpriority=\"\$\{index < 8 \? \"high\" : \"low\"\}\"/, "Track covers should use a bounded high/low browser fetch priority");
assert.match(app, /fetchpriority=\"\$\{index < 8 \? \"high\" : \"low\"\}\"/, "Non-visible covers should yield fetch priority to the first-paint burst");
assert.match(app, /The confirmation changes the metadata-backed projection immediately/, "Manual metadata confirmation must explain immediate projection refresh");
assert.match(app, /clearLibraryResponseCaches\(\);\s*if \(state\.pageItems\?\.length && !state\.libraryLoading\)\s*\{\s*await loadLibrary\(false\);/, "Confirmed metadata must refresh the visible cached page immediately");
assert.match(app, /function clearLibraryResponseCaches\(\)/, "Library response cache invalidation must clear in-flight requests");
assert.match(app, /for \(const request of state\.libraryResponseInflight\.values\(\)\)[\s\S]*?request\?\.__fnAudioAbort\?\.\(\);[\s\S]*?state\.libraryResponseInflight\.clear\(\);/, "Library response invalidation must cancel stale requests before clearing the in-flight map");
assert.match(app, /state\.albumMetadata\.clear\?\.\(\);/, "Library invalidation must clear derived album metadata");
assert.match(app, /function libraryResponseWeight\(data\)/);
assert.match(app, /globalThis\.fnAudioLibraryResponseLoader\.loadLibraryResponse\(/, "Library loading must use the shared response loader");
assert.match(loader, /if \(!refresh && cache\.has\(url\)\) return Promise\.resolve\(cache\.get\(url\)\);/, "Library response cache reads must refresh LRU order");
assert.match(loader, /if \(inflight\.has\(url\)\)[\s\S]*?return existing;/, "Concurrent identical library loads must share one request unless the existing request was aborted");
assert.match(loader, /existing\?\.__fnAudioAbortSignal\?\.aborted === true/, "An aborted library request must not capture its replacement");
assert.match(loader, /existing\.__fnAudioRelease\?\.\(\);/, "An abandoned request must hand its admission slot to the replacement instead of blocking the next page");
assert.match(loader, /if \(activeCount\(\) >= limit\)/, "Ordinary and refresh requests must share the same hard bound");
assert.match(loader, /const activeCount = \(\) => active && Number\.isFinite\(active\.value\)/, "A shared active counter must cover refresh requests outside the in-flight map");
assert.match(loader, /if \(!cacheWriteVoided && getEpoch\(\) === epoch\) cache\.set\(url, data\);/, "Stale responses, an older refresh, and a superseded request must not repopulate the invalidated cache");
assert.match(app, /fnAudioBatchRequestPool\(batches, fnAudioBatchRequestPool\.DEFAULT_CONCURRENCY,/);
assert.match(app, /const items = await pool\.get\(batchIndex\);/);
assert.match(app, /const firstPage = canReuseCurrentPage[\s\S]*?\? \{ items: state\.pageItems, count: state\.pageTotal \}[\s\S]*?: await fetchPage\(0\);/);
assert.match(app, /return fetchLibraryResponse\(`api\/library\?\$\{params\.toString\(\)\}`, "读取完整歌曲列表失败"\);/, "Full-list loading must reuse the bounded page response cache");
assert.match(app, /fnAudioLibraryPagePlan\.pageOffsetBatches\(total, pageSize, firstItems\.length, 200000, 32\)/);
assert.match(app, /const pool = fnAudioBatchRequestPool\(offsets, fnAudioBatchRequestPool\.DEFAULT_CONCURRENCY, fetchPage\);/);
assert.match(app, /fnAudioLibraryPageMerge\.appendPageItems\(merged, pageItems, total\)/);
assert.match(app, /pool\.cancel\("library result complete"\)/, "Full-list loading must cancel queued tail batches after completion");
assert.ok(!app.includes("pages.push(pageItems)"), "full-list loading must not retain every fetched page");
assert.match(app, /cacheLibraryItems\(pageItems, false\)/);
assert.match(app, /cacheLibraryItems\(items, false\)/);
assert.match(app, /state\.itemHydrationPool\?\.cancel/);
assert.match(app, /fnAudioItemHydrationRequest\?\.matches\(state\.itemHydrationRequest, requestedView, normalizedIds\)/, "Repeated client renders must reuse the identical hydration pool");
assert.match(app, /state\.itemHydrationRequest = globalThis\.fnAudioItemHydrationRequest\?\.create\(requestedView, normalizedIds\)/);
assert.match(hydrationRequest, /request\.ids\.every\(\(id, index\) => id === ids\[index\]\)/, "Hydration identity must compare bounded IDs without a giant joined key");
assert.ok(index.indexOf('src="item_hydration_request.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Hydration request policy must load before app.js");
assert.ok(index.indexOf('src="item_negative_cache.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Expiring item negative cache must load before app.js");
assert.match(app, /state\.hydratingIds\.clear\(\);/, "Cancelled hydration must release IDs synchronously for the next view");
assert.match(app, /state\.unresolvedItemIds = globalThis\.fnAudioItemNegativeCache\?\.create\?\.\(\) \|\| new Set\(\);/, "Missing item IDs must use the bounded, expiring negative cache");
assert.match(app, /state\.unresolvedItemIds\?\.delete\?\.\(id\);/, "Authoritative items must clear stale negative cache entries");
assert.match(app, /state\.unresolvedItemIds\.remember\(id\);/, "Missing hydration IDs must be remembered through the expiring cache");
assert.match(app, /const generation = \+\+state\.itemHydrationGeneration;/);
assert.match(app, /state\.itemHydrationPool = pool;/);
assert.match(app, /state\.itemHydrationGeneration !== generation \|\| state\.itemHydrationPool !== pool/);
assert.match(app, /const pool = fnAudioBatchRequestPool\(groups, fnAudioBatchRequestPool\.DEFAULT_CONCURRENCY,/);
assert.match(app, /const locationPool = fnAudioBatchRequestPool\(ids, fnAudioBatchRequestPool\.DEFAULT_CONCURRENCY, resolveTrackLocation\);/);
assert.match(app, /for \(let index = 0; index < batches\.length; index \+= 1\) \{\s*\/\/ A large favorite\/playlist[\s\S]*?cacheLibraryItems\(await pool\.get\(index\), false\);\s*\}\s*state\.itemCache\.trim\(new Set/, "ID hydration must defer cache eviction until all batches are written");
assert.match(app, /fnAudioDeviceTargetPresentation\.stableTargets\(targets, displayText\)/);
assert.match(app, /return targets\.some\(target => String\(target\.id \|\| ""\) === targetId\) \? targetId : "local"/);
assert.match(app, /fetchJson: \(requestUrl, requestMessage, requestSignal\) => fetchJsonChecked\(/, "Library loader must preserve checked API responses");
assert.match(app, /async function fetchJsonChecked\(input, init = \{\}, fallbackMessage = "请求失败", options = \{\}\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 15000,[\s\S]*?onTimeout: \(\) => \{ try \{ controller\?\.abort\(\);/, "Library response loading must bound headers and JSON-body parsing before it occupies an in-flight slot indefinitely");
assert.match(app, /const strictBody = options\?\.strictBody === true;[\s\S]*?if \(strictBody && globalThis\.fnAudioResponseJsonLoader\.usableBody\?\.\(result\.bodyStatus\) === false\) \{[\s\S]*?error\.name = "ResponseError";[\s\S]*?error\.bodyStatus = result\.bodyStatus;[\s\S]*?throw error;\s*\}\s*return data;/, "Only the strict caller may fail on an unreadable body, and it must still return a parsed one");
assert.match(app, /requestMessage,\s*\{\s*strictBody: true\s*\},/, "The cached library list must be the strict-body caller");
assert.doesNotMatch(app, /fetchJsonChecked\("api\/access", \{\}, "读取访问模式失败", \{ strictBody: true \}\)/, "Status reads outside the list must keep their existing fallback behaviour");
assert.match(app, /if \(state\.libraryAbortController\) state\.libraryAbortController\.abort\(\);/);
assert.match(app, /const controller = typeof AbortController === "function" \? new AbortController\(\) : null;/);
assert.match(app, /state\.libraryAbortController = controller;/);
assert.match(app, /const requestSignal = controller\?\.signal;/);
assert.match(app, /const releaseController = \(\) => \{\s*if \(state\.libraryAbortController === controller\) state\.libraryAbortController = null;\s*\};/, "Settled page requests must release only their own abort controller");
assert.match(app, /\} finally \{\s*releaseController\(\);\s*\}/, "Library request cleanup must run for success, failure, and cancellation");
assert.match(app, /state\.folderRootRows\.length === 1[\s\S]*?return loadPagedLibraryWorker\(page, refresh\);/, "A single configured library root must continue in the same worker chain rather than await its own deduplicated promise");
assert.match(app, /function prefetchFolderNavigationEntry\(\)[\s\S]*?fetchLibraryResponse\([\s\S]*?folderNavigationUrls\(/, "The first folder-category click must have a cached entry path built by the same URL helper");
assert.match(app, /function scheduleFolderNavigationPrefetch\(\)[\s\S]*?state\.libraryStatus\?\.scanning === true[\s\S]*?document\.hidden === true/, "Folder entry prefetch must stay off while scanning or when the document is hidden");
assert.match(app, /function setView\(view\) \{[\s\S]*?prefetchFolderNavigationEntry\(\);[\s\S]*?state\.view = nextView;/, "Entering the folder category must start the prefetch before the paged worker runs");
assert.match(app, /button\.dataset\.view === "folders"[\s\S]*?addEventListener\("pointerdown"[\s\S]*?prefetchFolderNavigationEntry\(\);/, "Pressing the folder category must start the same prefetch immediately");
assert.match(app, /function clearLibraryResponseCaches\(\)[\s\S]*?state\.folderNavigationPrefetchKey = \"\";/, "A library refresh must allow the folder entry cache to be warmed again");
assert.doesNotMatch(app, /state\.folderRootRows\.length === 1[\s\S]{0,700}?return loadPagedLibrary\(page, refresh\);/, "Single-root auto-entry must not create a self-referential public load promise");
assert.match(app, /libraryStatus\?\.library_paths[\s\S]*?state\.folderRootRows/, "Folder cold navigation must reuse the already-hydrated library roots before requesting the roots endpoint");
assert.match(app, /const rootParams = new URLSearchParams\(\);[\s\S]*?api\/library\/roots/, "The roots endpoint must remain the fallback when the status has no usable configured roots");
{
  const rootHelper = app.match(/function configuredLibraryRoots\(status = state\.libraryStatus\) \{[\s\S]*?\n\}/);
  assert.ok(rootHelper, "configured library roots must have a testable projection boundary");
  const rootContext = { Array, state: { libraryStatus: null } };
  vm.runInNewContext(`${rootHelper[0]}; globalThis.projectRoots = configuredLibraryRoots;`, rootContext);
  assert.deepEqual(Array.from(rootContext.projectRoots({ library_paths: [" /music ", "", null, 7, "  /archive  "] })), [" /music ", "  /archive  "],
    "the fast path accepts only non-empty configured path strings and leaves their exact values intact");
  assert.deepEqual(Array.from(rootContext.projectRoots({ library_path: "/legacy" })), [],
    "a legacy or missing multi-root projection must fall back to the authoritative roots endpoint");
  const worker = app.match(/async function loadPagedLibraryWorker\(page = 1, refresh = false\) \{[\s\S]*?\n\}\n/)[0];
  const fastPath = worker.slice(worker.indexOf("const configuredRoots = configuredLibraryRoots();"), worker.indexOf("const rootParams = new URLSearchParams();"));
  assert.ok(fastPath.includes("configuredRoots.length === 1") && fastPath.includes("state.folderRoot = root;")
    && fastPath.includes("return loadPagedLibraryWorker(page, refresh);"),
  "one known configured root must enter the folders+tracks pair directly instead of paying for /roots first");
}
assert.match(app, /if \(error\?\.name === "AbortError"\) return;/);
assert.match(app, /if \(seq !== state\.libraryRequestSeq\) return;[\s\S]*?state\.libraryLoading = false;\s*state\.libraryLoaded = state\.pageItems\.length;/, "Obsolete page responses must not clear the active loading guard");
assert.match(app, /if \(error\?\.name === "AbortError" && error\?\.code !== "RESPONSE_BODY_TIMEOUT"\) \{[\s\S]*?state\.libraryInteractionBlocked = false;[\s\S]*?return;[\s\S]*?\}\s*state\.libraryLoading = false;[\s\S]*?state\.libraryInteractionBlocked = false;[\s\S]*?render\(\);/, "A current library response-body timeout must leave loading state and render an error instead of spinning forever");
assert.match(app, /function libraryLoadRequestKey\(page = 1\)/);
assert.match(app, /function libraryPageNumber\(value, fallback = 1\)/, "Library page numbers must be normalized through one strict integer boundary");
assert.match(app, /function libraryPageStep\(value, fallback = 0\)/, "Pager steps must keep signed integer semantics");
assert.match(app, /state\.page = libraryPageNumber\(page\);/, "Loaded library pages must reject fractional and non-finite values");
assert.match(app, /const nextPage = libraryPageNumber\(button\.dataset\.pageGo, 1\);/, "Pager targets must reject fractional and non-finite values");
assert.match(app, /state\.folderPage = libraryPageNumber\(libraryPageNumber\(state\.folderPage\) \+ step\);/, "Folder pager state must remain an integer");
assert.match(app, /typeof value === "string" \? value\.trim\(\)\.slice\(0, 4096\) : ""/);
assert.match(app, /globalThis\.fnAudioLibraryLoadKey\.buildLibraryLoadKey\(/, "Request keys must use the shared pure policy");
assert.ok(index.indexOf('src="library_response_loader.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Response loader must load before app.js");
assert.ok(index.indexOf('src="library_load_key.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Load-key policy must load before app.js");
assert.ok(index.indexOf('src="metadata_request_loader.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'), "Metadata request loader must load before app.js");
assert.match(metadataRequestLoader, /const DEFAULT_TTL_MS = 750;/, "Metadata single-flight must retain a short TTL");
assert.match(metadataRequestLoader, /const inflight = new Map\(\);/, "Metadata single-flight must track pending URLs");
assert.match(metadataRequestLoader, /if \(entry\?\.controller\?\.signal\?\.aborted === true\)/, "Aborted shared entries must not capture replacement callers");
assert.match(metadataRequestLoader, /if \(entry\.epoch === epoch\) cache\.set\(url,/, "Cleared metadata requests must not repopulate the cache late");
assert.ok(index.indexOf('src="metadata_request_loader.js?v=__FNAUDIO_ASSET_BUILD__"') >= 0
  && index.indexOf('src="metadata_request_loader.js?v=__FNAUDIO_ASSET_BUILD__"') < index.indexOf('src="app.js?v=__FNAUDIO_ASSET_BUILD__"'),
"Metadata single-flight policy must load before app.js");
assert.match(loadKey, /function safeNumber\(value, fallback = 0\)/);
assert.match(loadKey, /const numericPage = safePage\(page, 1\);/);
assert.match(loadKey, /return JSON\.stringify\(key\);/);
assert.match(loadKey, /catch \(_\) \{\s*return "";/);
assert.match(app, /if \(key && state\.libraryLoadKey === key && state\.libraryLoadPromise\) return state\.libraryLoadPromise;/);
assert.match(app, /const promise = loadPagedLibraryWorker\(page, refresh\);/);
assert.match(app, /function requestLibraryLoad\(page = 1, refresh = false\) \{[\s\S]*?Promise\.resolve\(\)\.then\(\(\) => loadPagedLibrary\(page, refresh\)\)\.catch\(\(\) => \{\}\);/);
assert.match(app, /document\.querySelectorAll\("\[data-refresh-library\]"\)\.forEach\(button => button\.onclick = \(\) => requestLibraryLoad\(1, true\)\)/);
assert.match(app, /if \(restoreLibraryPageSnapshot\(1\)\) render\(\);\s*requestLibraryLoad\(1, false\);/);
assert.doesNotMatch(app, /document\.querySelectorAll\("\[data-refresh-library\]"\)\.forEach\(button => button\.onclick = \(\) => loadLibrary\(true\)\)/);
assert.match(app, /promise\.then\(clear, clear\);/);
assert.match(app, /let needsFinalRender = false;/);
assert.match(app, /if \(!renderedFirstBatch && batchChanged && state\.view === requestedView && isClientPagedView\(requestedView\)\)/);
assert.match(app, /else if \(renderedFirstBatch && batchChanged\)\s*\{[\s\S]*?needsFinalRender = true;/);
assert.match(app, /if \(needsFinalRender && changed && state\.view === requestedView && isClientPagedView\(requestedView\)\) render\(\);/);
assert.match(app, /cancelAnimationFrame\(state\.itemHydrationRenderTimer\)/, "Cancelled hydration must release its pending render frame");
assert.match(app, /state\.itemHydrationRenderTimer = 0;/, "Hydration render ownership must be reset on cancellation");
assert.match(app, /function updateCurrentQueueTrackRow\(queueIndex, current\)/);
assert.match(app, /fnAudioQueuePresentation\?\.queuePresentationPlan\?\./);
assert.match(app, /plan\.requiresFullRender \|\| !updateCurrentQueueTrackRow\(previousIndex, false\) \|\| !updateCurrentQueueTrackRow\(state\.index, true\)/);
assert.doesNotMatch(app, /syncCurrentQueuePresentation\(previousIndex\);\s*render\(\);\s*}\s*if \(options\.allowAdvance !== false\) maybeAdvanceRemoteQueue\(data\);/);

assert.match(app, /state\.itemCacheLimit = 12000;/);
assert.match(app, /state\.itemCache = fnAudioItemCache\(12000\);/);
assert.match(app, /state\.itemCache\.trim\(new Set/);
assert.match(app, /state\.itemCache\.trim\(new Set/);

assert.match(app, /async function validateRestoredPlaybackTarget\(\) \{[\s\S]*?const controller = typeof AbortController === "function" \? new AbortController\(\) : null;/, "Restored remote-target discovery must own a cancellable request");
assert.match(app, /async function validateRestoredPlaybackTarget\(\)[\s\S]*?fnAudioResponseJsonLoader\.read\(\{[\s\S]*?timeoutMs: 6000,[\s\S]*?onTimeout: \(\) => \{ try \{ controller\?\.abort\(\);/, "A half-open target discovery request must be aborted at its timeout");
assert.match(app, /const result = await globalThis\.fnAudioResponseJsonLoader\.read\([\s\S]*?const response = result\.response;/, "Restored target discovery must not block user-state recovery indefinitely");
assert.match(responseJsonLoader, /Promise\.race\(\[operation, timeout\]\)/, "Shared target discovery loader must release its timer after settlement");

// Every now-playing text and rail write has to compare before it writes (TODO.md:61). The point of
// this check is that the guard is not lost again: an unconditional `node.textContent = ...` on one
// of these ids reappears on every 1.5 s status poll even when the text is identical.
for (const id of ["nowTitle", "nowArtist", "nowTime", "elapsed", "duration"]) {
  assert.doesNotMatch(app, new RegExp("\\$\\(\"" + id + "\"\\)\\s*\\.textContent\\s*="),
    `${id} must never be written unconditionally`);
}
assert.match(app, /function setTextContentIfChanged\(node, value\) \{[\s\S]*?if \(node\.textContent !== text\) node\.textContent = text;/,
  "the shared guard must stay a real comparison, not an unconditional write");
assert.equal((app.match(/"--seek-fill"/g) || []).length, 1,
  "exactly one place may name the rail variable, and it is the guarded writer below");
assert.match(app, /function updateSeekRail\(value = \$\("seek"\)\?\.value \|\| 0\) \{\s*setStyleVarIfChanged\(\$\("seek"\), "--seek-fill"/,
  "the rail fill must go through the compare-then-write helper");

// An ended cast must leave no position behind when nothing is selected locally (TODO.md:58).
const restoreBody = app.match(/function restoreLibraryNowPlaying\(\) \{[\s\S]*?\n\}/);
assert.ok(restoreBody, "restoreLibraryNowPlaying must stay a top-level function");
assert.match(restoreBody[0], /if \(!item\) \{[\s\S]*?resetTransportRow\(\);/,
  "the empty-selection branch has to reset the transport row it no longer owns");
assert.doesNotMatch(restoreBody[0].split("} else {")[1] || "", /resetTransportRow\(\);/,
  "a loaded local track must not be zeroed: it owns the row");

function countedNode(initial) {
  const node = { value: initial.value ?? "", dataset: { ...(initial.dataset || {}) }, writes: 0, styleWrites: 0 };
  let text = initial.textContent ?? "";
  Object.defineProperty(node, "textContent", {
    get() { return text; },
    set(next) { node.writes += 1; text = next; },
  });
  const properties = { ...(initial.style || {}) };
  node.style = {
    getPropertyValue(name) { return properties[name] ?? ""; },
    setProperty(name, value) { node.styleWrites += 1; properties[name] = String(value); },
  };
  Object.defineProperty(node, "properties", { value: properties });
  return node;
}

const transportNodes = {
  elapsed: countedNode({ textContent: "1:40" }),
  duration: countedNode({ textContent: "4:05" }),
  seek: countedNode({ value: "62" }),
  playBtn: countedNode({ dataset: { playing: "playing" } }),
  nowTitle: countedNode({ textContent: "Cast me something" }),
};
const transportNames = ["setTextContentIfChanged", "setStyleVarIfChanged", "clock", "seekPercent",
                        "updateSeekRail", "setPlayButton", "resetTransportRow"];
const transportSource = transportNames.map(name => {
  const found = app.match(new RegExp("function " + name + "\\([\\s\\S]*?\\) \\{[\\s\\S]*?\\n\\}"));
  assert.ok(found, `${name} must stay a top-level function for this check`);
  return found[0];
}).join(";\n");
const transportState = { remoteUiLast: { transport: "PLAYING", duration: 245, seconds: 100, current: "cast-1" } };
const transportContext = {
  $: id => transportNodes[id],
  state: transportState,
  seekDuration: () => 0,
  String, Math, Number,
};
vm.runInNewContext(transportSource + "; globalThis.resetRow = resetTransportRow;", transportContext);

transportContext.resetRow();
assert.equal(transportNodes.elapsed.textContent, "0:00", "elapsed must return to zero");
assert.equal(transportNodes.duration.textContent, "0:00", "duration must follow the local element, not the cast");
assert.equal(transportNodes.seek.value, 0, "the rail must go back to the start");
assert.equal(transportNodes.seek.properties["--seek-fill"], "0%", "the painted fill has to follow the rail");
assert.equal(transportNodes.playBtn.dataset.playing, "paused", "nothing is playing, so the icon may not claim otherwise");
assert.strictEqual(transportState.remoteUiLast, null, "the memo describing the ended cast must be dropped");

// A second pass must not touch the DOM again: the reset is idempotent through the same guards.
const writesAfterReset = transportNodes.elapsed.writes + transportNodes.duration.writes;
transportContext.resetRow();
assert.equal(transportNodes.elapsed.writes + transportNodes.duration.writes, writesAfterReset,
  "repeating the reset must not rewrite identical text");
assert.equal(transportNodes.seek.styleWrites, 1, "the rail fill is written once and then compared");


// TODO.md:49 - the precondition "my callers already excluded remote playback" is now enforced in
// the function itself, because reading the caster's length here makes a finished cast advance this
// browser's own queue.
function durationContext(overrides) {
  const found = app.match(/function localPlaybackDuration\(\) \{[\s\S]*?\n\}/);
  assert.ok(found, "localPlaybackDuration must stay a top-level function for this check");
  const context = Object.assign({
    currentItem: () => ({ duration: 180 }),
    nativePlaybackAvailable: () => true,
    playbackSeconds: (value, fallback) => (Number.isFinite(Number(value)) ? Number(value) : (fallback || 0)),
    isIncomingRendererSession: () => false,
    isRemoteTarget: () => false,
    state: { nativePlayback: { duration: 210 } },
    audio: { duration: 180 },
    String, Math, Number,
  }, overrides);
  vm.runInNewContext(found[0] + "; globalThis.localDuration = localPlaybackDuration;", context);
  return context;
}
assert.throws(() => durationContext({ isRemoteTarget: () => true }).localDuration(),
  /requires a caller that excluded remote playback/, "a remote target must not be able to read the local pair");
assert.throws(() => durationContext({ isRemoteTarget: () => true, isIncomingRendererSession: () => true }).localDuration(),
  /requires a caller that excluded remote playback/, "an incoming cast must not excuse a remote target");
// An incoming cast is the case this helper exists for, not a violation of it: the gate's own
// authority suite drives `audio.ontimeupdate` with a cast active, and that must keep working.
assert.equal(durationContext({ isIncomingRendererSession: () => true }).localDuration(), 210,
  "a cast must not stop the local pair from being read");
assert.equal(durationContext({}).localDuration(), 210, "plain local playback answers with the local length");

// The only production caller is `audio.ontimeupdate`, and it excludes remote before reaching here,
// so the new throw cannot fire on the shipped path.
const timeupdateBody = app.match(/audio\.ontimeupdate = \(\) => \{[\s\S]*?\n\};/);
assert.ok(timeupdateBody, "the timeupdate handler must stay an inline arrow function");
assert.match(timeupdateBody[0], /if \(isRemoteTarget\(\)\) return;\s*const item = currentItem\(\);[\s\S]*?localPlaybackDuration\(\);/,
  "the handler has to return before it reaches the guarded helper");

// TODO.md:60 - the poll really does tick the progress pair twice (`updateIncomingRendererUi` and
// then `updateNowMarquee`). Measure what the second one costs before deciding to merge them.
// syncPlayerProgress grew a third writer, so the cost measurement has to run the real
// staleness lamp next to it: an extra text or style write per tick is exactly what the
// two assertions below are counting.
const progressSource = ["setTextContentIfChanged", "setStyleVarIfChanged", "clock", "seekPercent",
                        "syncNowPlayingTime", "updateSeekRail", "syncPlayerProgress",
                        "updateTransportStateUnknown", "transportStateIsUnknown",
                        "transportExtrapolation", "setDatasetStateIfChanged"]
  .map(name => {
    const found = app.match(new RegExp("function " + name + "\\([\\s\\S]*?\\) \\{[\\s\\S]*?\\n\\}"));
    assert.ok(found, `${name} must stay a top-level function for the cost measurement`);
    return found[0];
  }).join(";\n");
const progressNodes = {
  nowTime: countedNode({ textContent: "0:00 / 0:00" }),
  seek: countedNode({ value: "0" }),
};
const progressContext = {
  $: id => progressNodes[id],
  currentSeconds: () => 42,
  seekDuration: () => 180,
  state: { seeking: false },
  isIncomingRendererSession: () => false,
  isRemoteTarget: () => false,
  String, Math, Number,
};
const progressLimit = app.match(/^const TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS = [^\n]+/m);
assert.ok(progressLimit, "the extrapolation limit must stay a top-level const for the cost measurement");
vm.runInNewContext(progressLimit[0] + ";\n" + progressSource + "; globalThis.tick = syncPlayerProgress;", progressContext);
progressContext.tick();
assert.equal(progressNodes.nowTime.writes + progressNodes.seek.styleWrites, 2,
  "a real progress change costs exactly one text write and one rail write");
assert.equal(progressNodes.nowTime.textContent, "0:42 / 3:00");
const railAfterFirstTick = progressNodes.seek.properties["--seek-fill"];
assert.ok(typeof railAfterFirstTick === "string" && railAfterFirstTick.endsWith("%"),
  `the rail must be painted as a percentage, got ${railAfterFirstTick}`);
progressContext.tick();
progressContext.tick();
assert.equal(progressNodes.nowTime.writes + progressNodes.seek.styleWrites, 2,
  "re-ticking the same position must touch the DOM zero times - that is what the poll duplicate costs");

// R173 dead-code pin.  clearLibraryQueryState() had no caller anywhere in the tree: a
// full-repo scan over .js/.py/.html/.json/.ts/.md/.ps1/.sh found exactly one hit, its own
// declaration, and `git log -S` names only the baseline commit that introduced it.  Every
// field it reset keeps a live reset path (the boot block, the view/query switches and the
// page-commit lanes), so an unreferenced second answer to "what clears the query state" is
// what had to go -- not the reset itself, which the counts below keep pinned.
assert.doesNotMatch(app, /clearLibraryQueryState/,
  "the caller-less library query reset helper must not return");
for (const field of ["page", "pageItems", "pageTotal", "groupRows", "folderRows",
                     "folderRootRows", "folderPage", "folderTotal"]) {
  const writes = (app.match(new RegExp("state\\." + field + "\\s*=", "g")) || []).length;
  assert.ok(writes >= 2,
    `state.${field} must keep a live reset path beside the boot block (found ${writes})`);
}
// ---------------------------------------------------------------------------
// TODO.md R108 regex-constraint item + TODO.md R108 body-trust item - the bounded JSON lane is executed here, not matched
// ---------------------------------------------------------------------------
// TODO.md R108 body-trust item asked that a caller be able to tell "this browser could not read the body"
// from "the endpoint really answered with nothing", after enumerating what each endpoint
// actually sends. TODO.md R108 regex-constraint item asked for the same rigour on fetchJsonChecked, whose two known
// mutations were caught by exactly one thing: a regular expression over its source text. With
// that assertion commented out, either mutation leaves the whole suite green (re-measured this
// round). Every case below therefore runs the shipped code in a vm
// against a response object that carries a real body, and asserts what the caller does with
// it - including the cases where the new gate must stay out of the way.
(async () => {
  const NL = String.fromCharCode(10);
  const devicePresentationSource = fs.readFileSync("app/ui/device_target_presentation.js", "utf8");
  // The host intrinsics are passed in deliberately: the loader classifies a body through
  // TextDecoder, and an assertion whose subject came out of the wrong realm would compare
  // prototypes instead of values.
  const uiGlobals = {
    JSON, Math, Number, Object, Array, String, Boolean, Error, RegExp, Promise,
    Uint8Array, ArrayBuffer, TextDecoder, TextEncoder, AbortController,
    setTimeout, clearTimeout,
  };

  function appSlice(startText, endText, label) {
    const start = app.indexOf(startText);
    assert.ok(start >= 0, label + " must stay a top-level function for these checks");
    const end = app.indexOf(endText, start + startText.length);
    assert.ok(end > start, label + " must still be followed by " + endText);
    return app.slice(start, end);
  }

  function countOccurrences(text, needle) {
    return text.split(needle).length - 1;
  }

  function uiDisplayText(value) {
    return String(value === undefined || value === null ? "" : value).trim();
  }

  // A host that exposes no readable stream is measured through arrayBuffer(), which is the
  // same path the WebView takes when it buffers the body.
  function hostResponse(text, options = {}) {
    const bytes = new TextEncoder().encode(text);
    const status = options.status === undefined ? 200 : options.status;
    return {
      ok: options.ok === undefined ? status >= 200 && status < 300 : options.ok,
      status,
      headers: {
        get: name => (String(name).toLowerCase() === "content-length"
          && options.contentLength !== undefined) ? String(options.contentLength) : null,
      },
      arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset,
        bytes.byteOffset + bytes.byteLength),
    };
  }

  // The three answers that mean "no document arrived here". `empty` is the interesting one:
  // the loose gate accepts it on purpose, a caller that reads a document must not.
  const unreadableBodies = [
    ["empty", () => hostResponse("")],
    ["oversize", () => hostResponse("", { contentLength: 9 * 1024 * 1024 })],
    ["undecodable", () => hostResponse("{ not json")],
  ];

  async function rejectionOf(operation) {
    try {
      await operation;
    } catch (error) {
      return error;
    }
    return null;
  }

  function runUi(source, exportName, extras, bootstrap) {
    const context = Object.assign({}, uiGlobals, extras);
    vm.runInNewContext((bootstrap ? bootstrap + NL : "") + responseJsonLoader + NL + source + NL
      + "globalThis.__target = " + exportName + ";", context);
    return context;
  }

  // (1) fetchJsonChecked itself (TODO.md R108 regex-constraint item).
  const fetchCheckedSource = appSlice("async function fetchJsonChecked(",
    "async function fetchJsonResponseBounded(input", "fetchJsonChecked");

  for (const entry of unreadableBodies) {
    if (entry[0] === "empty") continue;
    const context = runUi(fetchCheckedSource, "fetchJsonChecked", {
      fetch: async () => entry[1](),
    });
    const failure = await rejectionOf(context.__target("api/library", {}, "读取曲库失败",
      { strictBody: true }));
    assert.ok(failure, entry[0] + " body must not resolve quietly on a strict read");
    assert.equal(failure.name, "ResponseError", "the strict gate keeps its typed error");
    assert.equal(failure.bodyStatus, entry[0], "the caller must be told which failure it was");
    assert.ok(failure.message.includes("响应体不完整"), "the message has to name the transport");
  }
  {
    const context = runUi(fetchCheckedSource, "fetchJsonChecked", {
      fetch: async () => hostResponse(""),
    });
    const data = await context.__target("api/library", {}, "读取曲库失败", { strictBody: true });
    // Objects built inside the vm carry that realm's prototype, so the shape is asserted by keys.
    assert.equal(Object.keys(data).length, 0, "a host that answered without content is still a usable answer");
  }
  {
    // Without the flag the contract is unchanged, so no legacy caller starts throwing. Deleting
    // the `strictBody &&` gate used to be visible only to a source regex; this loop is the
    // behavioural half of that proof (TODO.md R108 regex-constraint item).
    for (const entry of unreadableBodies) {
      const context = runUi(fetchCheckedSource, "fetchJsonChecked", {
        fetch: async () => entry[1](),
      });
      // The promise form keeps a mutated gate from escaping as an uncaught rejection,
      // so the failure names the contract instead of the stack.
      const outcome = await context.__target("api/library", {}, "读取曲库失败")
        .then(value => ({ value }), error => ({ error }));
      assert.equal(outcome.error, undefined,
        "a non-strict " + entry[0] + " body must keep the old contract, not throw");
      assert.equal(Object.keys(outcome.value).length, 0,
        "a non-strict " + entry[0] + " body still answers with the fallback");
    }
  }
  {
    const context = runUi(fetchCheckedSource, "fetchJsonChecked", {
      fetch: async () => hostResponse("{\"items\":[1]}"),
    });
    const strict = await context.__target("api/library", {}, "读取曲库失败", { strictBody: true });
    assert.equal(strict.items[0], 1, "a parsed strict body is returned untouched");
    assert.equal(Array.isArray(strict.items), true, "the parsed shape survives the gate");
    const loose = await context.__target("api/library", {}, "读取曲库失败");
    assert.equal(loose.items[0], 1, "a parsed body is returned untouched without the flag");
  }
  {
    const context = runUi(fetchCheckedSource, "fetchJsonChecked", {
      fetch: async () => hostResponse("{\"message\":\"nope\"}", { status: 503 }),
    });
    const failure = await rejectionOf(context.__target("api/library", {}, "读取曲库失败",
      { strictBody: true }));
    assert.ok(failure, "a failed response must still reject");
    assert.equal(failure.message, "nope", "the server message wins over the fallback text");
  }

  // (2) validateRestoredPlaybackTarget (TODO.md R108 body-trust item): a saved cast may only be disproved by a
  // device list this browser really read.
  const validateTargetSource = appSlice("async function validateRestoredPlaybackTarget() {",
    "function renderDeviceTargets(targets, currentTarget)", "validateRestoredPlaybackTarget");

  function restoredTargetHarness(response) {
    const calls = [];
    const state = { playTarget: "dlna:cast-9", playTargetName: "旧的投送设备" };
    const context = runUi(validateTargetSource, "validateRestoredPlaybackTarget", {
      state,
      isRemoteTarget: () => true,
      displayText: uiDisplayText,
      updateDeviceLabel: () => { calls.push("label"); },
      recoverUnavailablePlaybackTarget: async (notify, expected) => {
        calls.push(["recover", notify, expected]);
        return false;
      },
      fetch: async () => { calls.push("fetch"); return response; },
    });
    return { calls, context, state };
  }

  for (const entry of unreadableBodies) {
    const harness = restoredTargetHarness(entry[1]());
    const answer = await harness.context.__target();
    assert.equal(answer, true, "an unreadable device list must decide nothing: " + entry[0]);
    assert.deepEqual(harness.calls, ["fetch"],
      "an unreadable " + entry[0] + " answer may not reach recovery or repaint the label");
    assert.equal(harness.state.playTarget, "dlna:cast-9",
      "the still-playing cast stays selected when the body never arrived: " + entry[0]);
  }
  {
    const harness = restoredTargetHarness(hostResponse(
      "{\"targets\":[{\"id\":\"dlna:cast-9\",\"name\":\"  客厅 Casting \"}]}"));
    const answer = await harness.context.__target();
    assert.equal(answer, true, "a list that really still carries the cast confirms it");
    assert.equal(harness.calls.includes("recover"), false,
      "confirming the target must not be written as an array call");
    assert.deepEqual(harness.calls, ["fetch", "label"], "the confirmed name repaints the label once");
    assert.equal(harness.state.playTargetName, "客厅 Casting", "the name from the body is what shows");
  }
  {
    const harness = restoredTargetHarness(hostResponse("{\"targets\":[],\"refreshing\":false}"));
    const answer = await harness.context.__target();
    assert.equal(answer, false, "a genuinely empty device list does disprove the saved cast");
    assert.deepEqual(harness.calls, ["fetch", ["recover", false, "dlna:cast-9"]],
      "only a readable empty list may hand the cast back to this device");
  }
  {
    const harness = restoredTargetHarness(hostResponse("{\"targets\":[]}", { status: 503 }));
    const answer = await harness.context.__target();
    assert.equal(answer, true, "a failed discovery is still no information");
    assert.deepEqual(harness.calls, ["fetch"], "a failed response may not reach recovery either");
  }

  // (3) loadDevices (TODO.md R108 body-trust item): reading {} as "nobody is on the network" was the second way
  // to lose a live cast, and it also blanked the panel.
  const loadDevicesSource = appSlice("async function loadDevices(forceRefresh = false) {",
    "function cancelDeviceLoad() {", "loadDevices")
    + appSlice("function stableDeviceTargets(",
      "async function recoverUnavailablePlaybackTarget(notify", "stableDeviceTargets");

  function loadDevicesHarness(response) {
    const calls = [];
    const nodes = {
      deviceList: { innerHTML: "正在搜索播放设备...", childElementCount: 1 },
      deviceDialog: { open: false },
      scanDevices: { disabled: false, textContent: "" },
      deviceRefreshStatus: { textContent: "" },
    };
    const state = {
      deviceLoadInFlight: false,
      deviceLoadRequestToken: 0,
      deviceLoadController: null,
      deviceTargetRevision: 0,
      deviceTargetsSignature: "",
      playTarget: "dlna:cast-9",
      playTargetName: "旧的投送设备",
      devices: [],
    };
    const context = runUi(loadDevicesSource, "loadDevices", {
      state,
      $: id => nodes[id],
      displayText: uiDisplayText,
      isRemoteTarget: () => false,
      renderDeviceTargets: (targets, current) => {
        calls.push(["render", targets.length, current]);
      },
      scheduleDeviceRefresh: () => { calls.push("refresh"); },
      stopRemoteEventStream: () => { calls.push("stop"); },
      startRemoteEventStream: () => { calls.push("start"); },
      recoverUnavailablePlaybackTarget: async (notify, expected) => {
        calls.push(["recover", notify, expected]);
        return false;
      },
      fetch: async () => { calls.push("fetch"); return response; },
    }, devicePresentationSource);
    return { calls, context, nodes, state };
  }

  for (const entry of unreadableBodies) {
    const harness = loadDevicesHarness(entry[1]());
    await harness.context.__target();
    assert.deepEqual(harness.calls, ["fetch"],
      "an unreadable " + entry[0] + " device answer may not act on the fallback at all");
    assert.equal(harness.state.playTarget, "dlna:cast-9",
      "the cast stays selected when the list never arrived: " + entry[0]);
    assert.deepEqual(harness.state.devices, [], "the panel keeps its devices: " + entry[0]);
    assert.ok(harness.nodes.deviceList.innerHTML.includes("设备列表读取失败"),
      "the unreadable body has to be reported instead of painted as an empty room: " + entry[0]);
    assert.equal(harness.state.deviceLoadInFlight, false, "the failing lane still releases itself");
  }
  {
    const harness = loadDevicesHarness(hostResponse(
      "{\"targets\":[{\"id\":\"local\",\"name\":\"当前设备\"}],\"current_target\":\"dlna:cast-9\",\"refreshing\":false}"));
    await harness.context.__target();
    const recoveries = harness.calls.filter(call => Array.isArray(call) && call[0] === "recover");
    assert.equal(recoveries.length, 1, "a list that really no longer carries the cast recovers it");
    assert.deepEqual(recoveries[0], ["recover", false, "dlna:cast-9"],
      "recovery keeps its silent, expected-target form");
    assert.equal(harness.state.playTarget, "local", "recovery lands playback on this device");
    assert.equal(harness.nodes.deviceList.innerHTML.includes("设备列表读取失败"), false,
      "a readable list is never reported as a read failure");
  }
  {
    const harness = loadDevicesHarness(hostResponse(
      "{\"targets\":[{\"id\":\"dlna:cast-9\",\"name\":\"客厅\"},{\"id\":\"local\",\"name\":\"当前设备\"}],\"current_target\":\"dlna:cast-9\",\"refreshing\":false}"));
    await harness.context.__target();
    assert.equal(harness.calls.some(call => Array.isArray(call) && call[0] === "recover"), false,
      "a readable list that still shows the cast must leave it alone");
    assert.equal(harness.state.playTarget, "dlna:cast-9", "the cast survives a confirmed scan");
    assert.equal(harness.state.devices.length, 1, "only the non-local rows belong to the panel");
  }
  {
    const harness = loadDevicesHarness(hostResponse("{\"message\":\"nope\"}", { status: 500 }));
    await harness.context.__target();
    assert.deepEqual(harness.calls, ["fetch"], "a failed response uses the existing error path");
    assert.ok(harness.nodes.deviceList.innerHTML.includes("设备列表读取失败"),
      "and is still visible to the user");
  }

  // (4) saveUserStateNow (TODO.md R108 body-trust item): a 200 whose body was swallowed hit neither branch, so
  // the queued favourites stayed clean and were dropped without a retry.
  const saveStateSource = appSlice("async function saveUserStateNow() {",
    "async function loadServerUserState() {", "saveUserStateNow");

  function saveStateHarness(response) {
    const calls = [];
    const state = {
      userStateHydrated: true,
      userStateSaveInFlight: false,
      userStateDirty: false,
      userStateSaveTimer: 0,
      userStateBase: { favorites: [] },
      userStateRevision: 3,
    };
    const context = runUi(saveStateSource, "saveUserStateNow", {
      state,
      apiFetch: (input, init) => { calls.push(["api", input, init.method]); return response; },
      userStatePayload: () => ({ favorites: ["track-1"] }),
      userStateChanges: () => ({ favorites: ["track-1"] }),
      normalizeUserMediaState: value => ({ normalized: value.revision }),
      userStateRevision: (value, fallback) => (value === undefined ? fallback : value),
      applyUserStateChanges: (base, changes) => ({ merged: base.normalized, queued: changes }),
      persistUserMediaState: value => { calls.push(["persist", value]); },
      scheduleUserStateSave: delay => { calls.push(["schedule", delay]); },
    });
    return { calls, context, state };
  }

  function lastCall(calls) {
    return calls[calls.length - 1];
  }

  for (const entry of unreadableBodies) {
    const harness = saveStateHarness(entry[1]());
    await harness.context.__target();
    assert.equal(harness.state.userStateDirty, true,
      "a 200 whose body never arrived is not an acknowledgement: " + entry[0]);
    assert.deepEqual(lastCall(harness.calls), ["schedule", 2000],
      "the queued changes have to be retried instead of dropped: " + entry[0]);
    assert.deepEqual(harness.state.userStateBase, { favorites: [] },
      "an unreadable answer must not overwrite the revision base: " + entry[0]);
    assert.equal(harness.state.userStateSaveInFlight, false, "the save lane releases itself");
  }
  {
    const harness = saveStateHarness(hostResponse("{\"state\":{\"revision\":7}}"));
    await harness.context.__target();
    assert.equal(harness.state.userStateDirty, false, "an echoed state is an acknowledgement");
    assert.equal(harness.state.userStateRevision, 7, "the echoed revision advances the lane");
    assert.deepEqual(harness.state.userStateBase, { normalized: 7 }, "the base follows the document");
    assert.equal(harness.calls.some(call => Array.isArray(call) && call[0] === "persist"), true,
      "the merged local copy is rewritten once");
    assert.equal(harness.calls.some(call => Array.isArray(call) && call[0] === "schedule"), false,
      "nothing is pending, so no retry may be queued");
  }
  {
    const harness = saveStateHarness(hostResponse("{\"state\":{\"revision\":9}}", { status: 409 }));
    await harness.context.__target();
    assert.equal(harness.state.userStateRevision, 9, "a conflict still merges the authoritative state");
    assert.equal(harness.state.userStateDirty, true, "the changes that lost the race stay queued");
    assert.deepEqual(lastCall(harness.calls), ["schedule", 350], "the conflict retry keeps the short delay");
  }
  {
    // The gate classifies the body, it does not judge its contents: a document this browser
    // really parsed is still the server acknowledging the save.
    const harness = saveStateHarness(hostResponse("{\"ok\":true}"));
    await harness.context.__target();
    assert.equal(harness.state.userStateDirty, false, "a parsed answer without a state is accepted");
    assert.equal(harness.calls.some(call => Array.isArray(call) && call[0] === "schedule"), false,
      "the new gate must not turn into a demand for specific keys");
  }
  {
    const harness = saveStateHarness(hostResponse("{\"message\":\"boom\"}", { status: 500 }));
    await harness.context.__target();
    assert.equal(harness.state.userStateDirty, true, "a refused save is still retried");
    assert.deepEqual(lastCall(harness.calls), ["schedule", 2000], "with the transport delay");
  }

  // (5) wiring pins. The behaviour above is the proof; these only stop a fourth call site from
  // appearing without being classified, and stop the loose gate from being migrated by mistake.
  assert.equal(countOccurrences(app, "fnAudioResponseJsonLoader.read("), 16,
    "every bounded read is enumerated by this round: a new caller has to classify its body too");
  assert.equal(countOccurrences(app, "parsedBody(result.bodyStatus)"), 3,
    "exactly the three sites that act on the fallback ask for a parsed document");
  assert.equal(countOccurrences(app, "usableBody?.(result.bodyStatus)"), 1,
    "the list lane keeps the looser gate, so a no-content answer may still render an empty page");
  for (const slice of [validateTargetSource, loadDevicesSource, saveStateSource]) {
    assert.ok(slice.includes("parsedBody(result.bodyStatus)"),
      "each gated function has to carry the gate itself, not inherit it from a helper");
  }

  // R198: folder navigation must stay responsive, and a new page may not inherit
  // the outgoing page's cover queue or compete with the background pollers.
  {
    const selectorConst = app.match(/const LIBRARY_NAVIGATION_SELECTOR = "([^"]+)";/);
    assert.ok(selectorConst, "the navigation allow-list must stay one top-level constant");
    const gateNames = ["isLibraryNavigationTarget", "libraryInteractionBlockedFor",
      "armLibraryInteractionHold", "uiBackgroundWorkBlocked"];
    const gateSource = selectorConst[0] + ";\n" + gateNames.map(name => {
      const found = app.match(new RegExp("function " + name + "\\([\\s\\S]*?\\) \\{[\\s\\S]*?\\n\\}"));
      assert.ok(found, `${name} must stay a top-level function for this check`);
      return found[0];
    }).join(";\n");
    const insideList = [];
    const list = { contains: node => insideList.includes(node) };
    const node = (...attributes) => {
      const element = {
        attributes,
        closest(selector) {
          return selector.split(",").some(wanted => attributes.includes(wanted)) ? element : null;
        },
      };
      insideList.push(element);
      return element;
    };
    const detached = node("[data-group-row]");
    insideList.length = 0;
    const folderRow = node("[data-group-row]", "[data-open-folder-path]");
    const crumb = node("[data-folder-crumb-root]");
    const folderPagerButton = node("[data-folder-page-step]");
    const trackRow = node("[data-track-row-key]");
    let clock = 1000;
    const gateState = { libraryInteractionBlocked: false, libraryInteractionHoldUntil: 0 };
    const gateContext = {
      $: () => list,
      state: gateState,
      Number,
      Boolean,
      Math,
      LIBRARY_INTERACTION_HOLD_MS: 4000,
      Date: { now: () => clock },
    };
    vm.runInNewContext(
      gateSource
      + "; globalThis.gate = libraryInteractionBlockedFor;"
      + " globalThis.navTarget = isLibraryNavigationTarget;"
      + " globalThis.armHold = armLibraryInteractionHold;"
      + " globalThis.backgroundBlocked = uiBackgroundWorkBlocked;"
      + " globalThis.holdConstant = LIBRARY_INTERACTION_HOLD_MS;",
      gateContext,
    );
    gateState.libraryInteractionBlocked = true;
    gateState.libraryInteractionHoldUntil = 5000;
    assert.equal(gateContext.navTarget(folderRow, list), true, "a folder row click is navigation");
    assert.equal(gateContext.navTarget(crumb, list), true, "a breadcrumb click is navigation");
    assert.equal(gateContext.navTarget(folderPagerButton, list), true, "a folder pager click is navigation");
    assert.equal(gateContext.gate(folderRow, list), false, "the in-flight gate may not swallow a folder click");
    assert.equal(gateContext.gate(crumb, list), false, "drilling back out of a folder must stay live too");
    assert.equal(gateContext.gate(trackRow, list), true, "playing a row of a page that is still being replaced stays suppressed");
    assert.equal(gateContext.gate(detached, list), true, "a navigation node outside the list is not exempted");
    assert.equal(gateContext.gate(node("[data-open-folder-path]"), list), true, "only the row itself carries the navigation marker");
    gateState.libraryInteractionBlocked = false;
    assert.equal(gateContext.gate(trackRow, list), false, "outside a load nothing may be blocked");
    gateState.libraryInteractionBlocked = true;
    assert.equal(gateContext.backgroundBlocked(), true, "the background lanes yield while the page is in flight");
    clock = 5001;
    assert.equal(gateContext.backgroundBlocked(), false, "a request that never settles may not starve status forever");
    gateState.libraryInteractionBlocked = false;
    clock = 1;
    assert.equal(gateContext.backgroundBlocked(), true,
      "the hold outlives the flag: a folder click served from the prefetch cache commits in the same frame and must still hand the connections to the navigation the user is about to make");
    assert.equal(gateContext.holdConstant, 4000, "and the hold stays the one bounded window");
    assert.equal(gateContext.armHold(), 5000, "a press inside an armed window may not shorten it");
    clock = 5000;
    assert.equal(gateContext.armHold(), 9000, "a press at the deadline extends it by exactly one bounded window");
    gateState.libraryInteractionHoldUntil = 0;
    assert.equal(gateContext.backgroundBlocked(), false, "the deadline is the only thing that releases it");
    const binder = app.match(/function bindTrackListInteractions\([\s\S]*?\n\}/);
    assert.ok(binder, "the track list interaction binder must remain one top-level function");
    assert.equal(countOccurrences(binder[0], "libraryInteractionBlockedFor(event.target, list)"), 3,
      "click, contextmenu and pointerdown all have to consult the same predicate");
    assert.equal(binder[0].includes("state.libraryInteractionBlocked"), false,
      "the binder may not read the flag directly, or navigation would be swallowed again");
  }
  {
    const worker = app.match(/async function loadPagedLibraryWorker\([\s\S]*?\n\}/);
    assert.ok(worker, "the paged library worker must remain one top-level function");
    const body = worker[0];
    const stopAt = body.indexOf("state.coverLoadScheduler?.stop?.()");
    const holdAt = body.indexOf("armLibraryInteractionHold();");
    const blockedAt = body.indexOf("state.libraryInteractionBlocked = true;");
    assert.ok(stopAt >= 0, "a new page has to release the previous page's cover requests");
    assert.ok(holdAt >= 0, "the background lanes need an armed, bounded hold window");
    assert.ok(blockedAt >= 0, "the worker still marks the page as being replaced");
    assert.ok(stopAt < blockedAt && holdAt < blockedAt,
      "both the cover release and the hold must happen before the block is published");
    assert.match(app, /fnAudioUiSyncScheduler\.create\(\{[\s\S]{0,400}?isInteractionBlocked: uiBackgroundWorkBlocked,/,
      "the scheduler has to receive the interaction gate it checks on every tick");
    assert.equal(countOccurrences(app, "const LIBRARY_INTERACTION_HOLD_MS = 4000;"), 1,
      "the hold window is declared once and bounded");
  }

  // R201 (F4) - /api/metadata/status is background telemetry, not page content.
  // While a scan runs, ui_sync_scheduler asks for a status refresh about once a
  // second and every refresh used to add a metadata projection request that the
  // fnOS CGI gateway served in ~0.9 s, so the folder click queued behind
  // requests nobody had asked for. The projection now has its own floor.
  {
    const found = app.match(/function metadataProjectionIsDue\([\s\S]*?\) \{[\s\S]*?\n\}/);
    assert.ok(found, "metadataProjectionIsDue must stay a top-level function for this check");
    let nowMs = 1_000_000;
    const throttleState = { metadataProjectionLastFetchAt: 0 };
    const throttleContext = {
      state: throttleState,
      METADATA_PROJECTION_MIN_INTERVAL_MS: 3000,
      Date: { now: () => nowMs },
      Number,
    };
    vm.runInNewContext(
      found[0] + "; globalThis.due = metadataProjectionIsDue;",
      throttleContext,
    );

    assert.equal(throttleContext.due(false), true, "the first projection request must go out");
    throttleState.metadataProjectionLastFetchAt = nowMs;
    assert.equal(throttleContext.due(false), false, "a poll inside the window must be suppressed");
    nowMs += 2999;
    assert.equal(throttleContext.due(false), false, "the window is measured against its own bound");
    nowMs += 1;
    assert.equal(throttleContext.due(false), true, "once the window passes, the projection refreshes again");
    throttleState.metadataProjectionLastFetchAt = nowMs;
    assert.equal(throttleContext.due(true), true, "an explicit refresh always bypasses the floor");
    throttleState.metadataProjectionLastFetchAt = "not a number";
    nowMs += 10_000;
    assert.equal(throttleContext.due(false), true, "a corrupted stamp must fail toward refreshing");
  }
  {
    const statusFn = app.match(/async function refreshLibraryStatus\([\s\S]*?\n\}/);
    assert.ok(statusFn, "refreshLibraryStatus must remain one top-level function");
    const body = statusFn[0];
    assert.ok(body.includes("const metadataProjectionDue = metadataProjectionIsDue(Boolean(refresh));"),
      "the projection fetch has to be gated inside the status refresh");
    assert.ok(body.includes("if (metadataProjectionDue) state.metadataProjectionLastFetchAt = Date.now();"),
      "the window must be armed from the same decision that suppressed the request");
    assert.ok(body.includes("? fetchMetadataProjectionStatus(controller?.signal)"),
      "a due projection still uses the abortable loader");
    assert.ok(body.includes(": Promise.resolve(null);"),
      "a suppressed projection resolves null so the existing merge guard still skips it");
    assert.ok(body.includes("if (metadata) {"),
      "the merge path must keep treating a null projection as no observed change");
    assert.equal(countOccurrences(app, "const METADATA_PROJECTION_MIN_INTERVAL_MS = 3000;"), 1,
      "the projection floor is declared exactly once");
    assert.equal(countOccurrences(app, "state.metadataProjectionLastFetchAt = 0;"), 1,
      "the throttle stamp is initialised exactly once");
  }

  // R205 (F1/F2): the measured pointerdown->pointerup hold of a deliberate
  // folder click on the real device is 137-139 ms while one paged navigation
  // costs ~116 ms, so the entire round trip used to happen after the user had
  // already decided the control was dead. The press now activates the control
  // and the row is acknowledged in the same frame.
  {
    const sliceStart = app.indexOf("const LIBRARY_NAVIGATION_SELECTOR =");
    const sliceEnd = app.indexOf("// Fire-and-forget UI entry points already render the bounded error state.");
    assert.ok(sliceStart > 0 && sliceEnd > sliceStart,
      "the navigation gate and the press-time speculation must stay one contiguous top-level block");
    const navSource = app.slice(sliceStart, sliceEnd);
    for (const name of ["armLibraryNavigationSpeculation", "clearLibraryNavigationSpeculation",
      "libraryNavigationSpeculationPending", "speculateLibraryNavigation", "isConsumedNavigationClick"]) {
      assert.ok(navSource.includes("function " + name + "("), name + " must live in that block");
    }
    const inside = [];
    const element = (...attributes) => {
      const node = {
        attributes,
        clicks: 0,
        closest(selector) {
          return selector.split(",").some(wanted => attributes.includes(wanted)) ? node : null;
        },
      };
      node.onclick = () => { node.clicks += 1; };
      inside.push(node);
      return node;
    };
    const list = { contains: node => inside.includes(node) };
    let clock = 10000;
    let navLaneCancels = 0;
    let navCancelOptions = [];
    let navCoverStops = 0;
    const navState = {
      libraryInteractionBlocked: false,
      libraryInteractionHoldUntil: 0,
      libraryNavigationSpeculation: null,
      coverLoadScheduler: { stop: () => { navCoverStops += 1; } },
    };
    const navContext = {
      $: () => list, state: navState, Boolean, Number, Math,
      LIBRARY_INTERACTION_HOLD_MS: 4000,
      cancelVisibleMetadataPrefetch: (options) => {
        navLaneCancels += 1;
        navCancelOptions.push(String(options && options.cancelRearms));
      },
      Date: { now: () => clock },
    };
    vm.runInNewContext(navSource + `
      ; globalThis.press = speculateLibraryNavigation;
      ; globalThis.consumed = isConsumedNavigationClick;
      ; globalThis.pending = libraryNavigationSpeculationPending;`, navContext);
    const folderRow = element("[data-group-row]");
    const crumb = element("[data-folder-crumb-root]");
    const trackRow = element("[data-track-row-key]");
    const detached = element("[data-group-row]");
    inside.length = 0;
    inside.push(folderRow, crumb, trackRow);
    const press = (node, options = {}) => navContext.press(
      Object.assign({ target: node, pointerType: "mouse", button: 0, isPrimary: true }, options), list);
    assert.equal(press(folderRow), true, "a mouse press on a folder row activates it immediately");
    assert.equal(folderRow.clicks, 1, "the press ran the row's own handler exactly once");
    assert.equal(navContext.pending(), true, "the follow-up click is now owned by the press");
    assert.equal(navState.libraryInteractionHoldUntil, clock + 4000,
      "the press also arms the bounded background-work hold for the round trip it just started");
    assert.equal(navLaneCancels, 1, "and the press aborts the row-metadata polls that are already on the wire");
    assert.deepEqual(navCancelOptions, ["false"], "it keeps the completed dedupe keys, so the parked lane does not re-ask for chrome the rows already have");
    assert.equal(navCoverStops, 1, "the outgoing page cover queue is released at pointerdown too");
    assert.equal(press(folderRow), true, "a second press is a second activation");
    assert.equal(folderRow.clicks, 2, "each deliberate press activates once, never twice");
    assert.equal(press(crumb), true, "breadcrumbs and pagers use the same press path");
    assert.equal(press(trackRow), false, "a track row is not a navigation speculation");
    assert.equal(press(folderRow, { pointerType: "touch" }), false,
      "touch may not speculate: a scroll gesture starts with pointerdown too");
    assert.equal(press(folderRow, { pointerType: "pen" }), true, "a pen press is as deliberate as a mouse press");
    assert.equal(press(folderRow, { button: 2 }), false, "a right press belongs to the context menu, not navigation");
    assert.equal(press(folderRow, { isPrimary: false }), false, "secondary pointers may not navigate");
    assert.equal(press(detached), false, "a navigation node outside the list is not activated");
    assert.equal(navState.libraryInteractionHoldUntil, clock + 4000,
      "a touch, right-button, secondary-pointer or out-of-list press may not park the background lanes");
    assert.equal(navLaneCancels, 4, "only the accepted presses of that stretch reclaimed the lane: track rows, touch, right button and detached nodes reclaim nothing");
    assert.equal(navCoverStops, 4, "and a refused press may not tear down the cover queue of the page still on screen");
    assert.equal(navContext.consumed({ target: crumb }, list), true,
      "the click after a pressed control is swallowed");
    assert.equal(navContext.pending(), false, "the swallow token is single-use");
    assert.equal(navContext.consumed({ target: crumb }, list), false,
      "a later click on the same kind of control is live again");
    assert.equal(press(folderRow), true, "arm once more");
    assert.equal(navContext.consumed({ target: trackRow }, list), false,
      "a click that lands on a track row after the page changed may never be swallowed");
    assert.equal(navContext.pending(), false, "and the spent press is still consumed either way");
    clock = 12000;
    assert.equal(press(folderRow), true, "arm a press, then let the window lapse");
    clock = 12000 + 1501;
    assert.equal(navContext.pending(), false, "the swallow may not outlive its window");
    assert.equal(navContext.consumed({ target: crumb }, list), false, "an expired press cannot swallow a click");
    const hostile = element("[data-group-row]");
    inside.push(hostile);
    hostile.onclick = () => { throw new Error("handler"); };
    assert.equal(press(hostile), false, "a failing handler may not leave a swallow token armed");
    assert.equal(navContext.pending(), false, "and the token is cleared on that failure");
    navState.libraryInteractionBlocked = true;
    assert.equal(press(trackRow), false, "the in-flight gate still owns non-navigation presses");
    assert.equal(press(crumb), true, "but a folder press during a load is still honoured");
  }
  // R205 (F1/F2): the binder must wire the press, the single-use swallow and the
  // row acknowledgement, and the acknowledgement must reach the stylesheet.
  {
    const binder = app.match(/function bindTrackListInteractions\([\s\S]*?\n\}/);
    assert.ok(binder, "the track list interaction binder must remain one top-level function");
    assert.ok(binder[0].includes("speculateLibraryNavigation(event, list)"),
      "the binder has to activate navigation controls on pointerdown");
    assert.ok(binder[0].includes("isConsumedNavigationClick(event, list)"),
      "the binder has to discard the click the press already served");
    const swallowAt = binder[0].indexOf("isConsumedNavigationClick(event, list)");
    const captureAt = binder[0].indexOf("}, true);", swallowAt);
    assert.ok(swallowAt >= 0 && captureAt > swallowAt,
      "the swallow must run in the capture phase, before the row handler can fire again");
    assert.ok(binder[0].includes('list.addEventListener("pointercancel", () => clearLibraryNavigationSpeculation())'),
      "an abandoned press must drop its swallow token");
    const opener = app.match(/function openGroupRow\(row\) \{[\s\S]*?\n\}/);
    assert.ok(opener, "openGroupRow must stay one top-level function for this check");
    const addAt = opener[0].indexOf('row?.classList?.add?.("is-opening")');
    const loadAt = opener[0].indexOf("requestLibraryLoad(1, false)");
    const removeAt = opener[0].indexOf('row?.classList?.remove?.("is-opening")');
    assert.ok(addAt >= 0 && loadAt > addAt,
      "the acknowledgement must be painted in the same frame, before the request");
    assert.ok(removeAt > loadAt, "and it is cleared on the settled page, not the press");
    assert.ok(css.includes(".group-row.is-opening"), "the acknowledgement needs a visible style");
    assert.ok(css.includes("fnAudioOpeningPulse"), "the pulse must be defined, not just referenced");
    assert.equal(countOccurrences(app, "const NAVIGATION_SPECULATION_WINDOW_MS = 1500;"), 1,
      "the swallow window is declared once and bounded");
  }
  // R205 (F4 + F4b): a completed visible lookup that gained nothing holds its page
  // dedupe key on one page-owned, escalating cooldown instead of handing the key
  // straight back to the lane in the same tick. The exemption is information gain,
  // not payload shape: on the real device the ping-pong rows all carried a
  // filename-derived projection, which is why a shape test alone never stopped it.
  {
    const coolSource = app.match(/function scheduleVisibleMetadataPrefetchCooldown\([\s\S]*?\n\}/);
    assert.ok(coolSource, "the cooldown scheduler must stay one top-level function");
    const peekSource = app.match(/function nextVisibleMetadataPrefetchCooldownExpiry\([\s\S]*?\n\}/);
    assert.ok(peekSource, "the earliest expiry needs its own readable step");
    const armSource = app.match(/function armVisibleMetadataPrefetchCooldownTimer\([\s\S]*?\n\}/);
    assert.ok(armSource, "the cooldown timer needs its own arming step");
    const flushSource = app.match(/function flushVisibleMetadataPrefetchCooldowns\([\s\S]*?\n\}/);
    assert.ok(flushSource, "and its own flush step");
    let now = 1000;
    let nextId = 1;
    const armed = new Map();
    const delays = [];
    const coolState = {
      visibleMetadataPrefetchCooldownTimer: 0,
      visibleMetadataPrefetchCooldownKeys: new Map(),
      visibleMetadataPrefetchCooldownStreaks: new Map(),
      visibleMetadataPrefetchCooldownSeq: 0,
      visibleMetadataPrefetchKeys: new Set(["a:1", "a:2", "other"]),
      libraryRequestSeq: 7,
    };
    const coolContext = {
      state: coolState, Math, Number,
      Date: { now: () => now },
      setTimeout: (fn, ms) => { const id = nextId++; armed.set(id, fn); delays.push(ms); return id; },
      clearTimeout: (id) => { armed.delete(id); },
    };
    vm.runInNewContext(
      visibleMetadataPolicy + "\n" + coolSource[0] + "\n" + peekSource[0] + "\n" + armSource[0] + "\n" + flushSource[0]
      + "\nglobalThis.cool = scheduleVisibleMetadataPrefetchCooldown;"
      + "\nglobalThis.flush = flushVisibleMetadataPrefetchCooldowns;",
      coolContext,
    );
    const fireLatest = () => {
      const fn = armed.get(nextId - 1);
      if (!fn) return false;
      armed.delete(nextId - 1);
      fn();
      return true;
    };
    assert.equal(coolContext.cool("", 30000), false, "a keyless row is nothing to cool");
    assert.equal(armed.size, 0, "and it must not arm a timer");
    assert.equal(coolContext.cool("a:1", 30000), true, "a terminal row is taken over by the cooldown lane");
    assert.equal(coolState.visibleMetadataPrefetchKeys.has("a:1"), true,
      "the page key stays held, so the next lane pass skips the row");
    assert.equal(delays[0], 30000, "the first window is the default thirty seconds");
    assert.equal(coolState.visibleMetadataPrefetchCooldownStreaks.get("a:1"), 1,
      "the row starts at its first nothing-gained streak");
    now = 25000;
    assert.equal(coolContext.cool("a:2", 30000), true, "a second cooled row joins the same lane");
    assert.equal(armed.size, 1, "and the page still owns exactly one live cooldown timer");
    assert.equal(delays[delays.length - 1], 6000,
      "the live timer is re-armed for the earliest expiry, never a blind shared window");
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.get("a:2"), 55000,
      "while the later row keeps its own full window");
    now = 31000;
    assert.equal(fireLatest(), true, "the page timer fires once for the whole cohort");
    assert.equal(coolState.visibleMetadataPrefetchKeys.has("a:1"), false, "the cooled row is released");
    assert.equal(coolState.visibleMetadataPrefetchKeys.has("a:2"), true,
      "a row cooled later is not released early just because it shares the timer");
    assert.equal(delays[delays.length - 1], 24000, "and the lane re-arms for the next expiry");
    coolContext.cool("a:1", 30000);
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.get("a:1"), now + 60000,
      "the same row judged unhelpful again doubles its window");
    for (let index = 0; index < 9; index++) coolContext.cool("a:1", 30000);
    assert.equal(coolState.visibleMetadataPrefetchCooldownStreaks.get("a:1"), 10,
      "the streak stops counting up at ten");
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.get("a:1"), now + 300000,
      "so an unmatchable row settles at one request pair per five minutes");
    assert.equal(coolContext.cool("a:9", 0), false,
      "a zero window is the product off-switch, not a one second cooldown");
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.has("a:9"), false,
      "and the row is left to the immediate release");
    assert.equal(coolContext.cool("z:1", 50), true, "a bogus delay still cools");
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.get("z:1"), now + 1000,
      "but it clamps to the one second floor");
    assert.equal(delays[delays.length - 1], 1000,
      "the shared timer re-arms for the earliest expiry even when that row cooled last");
    assert.equal(armed.size, 1, "and the page still owns exactly one cooldown timer");
    coolContext.cool("z:2", 999999);
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.get("z:2"), now + 300000,
      "and stays bounded at five minutes");
    coolState.visibleMetadataPrefetchKeys.add("z:1");
    coolState.libraryRequestSeq = 8;
    now += 2000;
    assert.equal(fireLatest(), true, "a queued release still runs after the page settles");
    assert.equal(coolState.visibleMetadataPrefetchKeys.has("z:1"), true,
      "but a settled page may not release keys that now belong to the next page");
    assert.equal(coolState.visibleMetadataPrefetchCooldownKeys.has("z:1"), false,
      "and the stale cohort itself is always dropped");
    const cancel = app.match(/function cancelVisibleMetadataPrefetch\(options = \{\}\) \{[\s\S]*?\n\}/);
    assert.ok(cancel, "cancelVisibleMetadataPrefetch must stay one top-level function");
    assert.ok(cancel[0].includes("state.visibleMetadataPrefetchCooldownTimer) clearTimeout(state.visibleMetadataPrefetchCooldownTimer"),
      "cancelling the re-arms has to cancel the cooldown timer too");
    assert.ok(cancel[0].includes("state.visibleMetadataPrefetchCooldownKeys?.clear()"),
      "and drop the retained keys with them");
    assert.ok(cancel[0].includes("state.visibleMetadataPrefetchCooldownStreaks?.clear()"),
      "and start the escalation over for the new view");
    assert.ok(app.includes("informative: changed === true"),
      "the release verdict is owned by whether the row actually gained anything");
    assert.match(app, /if \(!rearmPending && \(terminalRelease\n\s*\|\| \(decision\.recoverable && state\.uiMetrics\.metadataPrefetchFailures < 1000000\)\)/,
      "only a terminal or recoverable verdict may even reach the cooldown lane");
    assert.ok(app.includes("if (decision.informative) state.visibleMetadataPrefetchCooldownStreaks?.delete(key);"),
      "a row that finally gained fields restarts its escalation");
    assert.ok(app.includes("{ informative: false, recoverable: false }"),
      "a projection-less negative is cooled at the bare lane as well");
    assert.ok(app.includes("?.releaseCompletedKey?.(key, data, scheduleVisibleMetadataPrefetchCooldown, decision)"),
      "and the projection-bearing lane routes through the same policy verdict");
    assert.equal(app.includes("?.shouldReleaseKey(data)"), false,
      "the old shape-based immediate release must not come back at either site");
  }

  // R206: dwelling a pointer on a folder row now issues, before the click, exactly the
  // pair of requests that click is going to issue. Three things have to hold or the
  // cache hit silently disappears: one builder for both paths, byte-identical URLs,
  // and a dwell that never outlives the row it was waiting for.
  {
    const navBlock = appSlice(
      "const LIBRARY_NAVIGATION_SELECTOR =",
      "// Fire-and-forget UI entry points already render the bounded error state.",
      "the folder navigation block",
    );
    for (const name of ["folderNavigationUrls", "navigationHoverCandidate",
      "libraryNavigationPrefetchUrls", "cancelLibraryNavigationHoverDwell",
      "prefetchLibraryNavigation", "armLibraryNavigationHover"]) {
      assert.ok(navBlock.includes("function " + name + "("),
        name + " must live inside the sliceable navigation block");
    }
    assert.equal(countOccurrences(app, "const folderParams = new URLSearchParams();"), 1,
      "only the shared pair builder may construct folder params, or a speculative URL can drift from the navigation URL");
    assert.ok(app.includes("const [foldersUrl, tracksUrl] = folderNavigationUrls("),
      "the folder branch of the loader has to take its URLs from the shared builder, not a second copy");
    assert.equal(countOccurrences(app, "return libraryQueryParamsFor(state.folderRoot, state.folderPath, state.page);"), 1,
      "currentQueryParams stays a projection of the one builder");
    assert.ok(app.includes('fetchLibraryResponse(foldersUrl, '),
      "the folder half of the navigation must fetch the builder's first URL");
    assert.ok(app.includes('${tracksUrl}${refresh ? "&refresh=1" : ""}'),
      "only the track half carries the refresh marker, and it is appended to the builder's second URL");

    const hoverRoot = "/vol2/1000/music";
    const hoverPath = "未整理";
    const expectedFolders = "api/library/folders?root=%2Fvol2%2F1000%2Fmusic&parent=%E6%9C%AA%E6%95%B4%E7%90%86&dir=asc&paged=1&limit=100&offset=0";
    const expectedTracks = "api/library?paged=1&limit=96&offset=0&view=folders&sort=title&dir=asc&root=%2Fvol2%2F1000%2Fmusic&folder=%E6%9C%AA%E6%95%B4%E7%90%86";

    const hoverInside = [];
    function hoverRow(attributes, dataset = {}) {
      const node = {
        dataset,
        closest(selector) {
          return selector.split(",").some(wanted => attributes.includes(wanted)) ? node : null;
        },
      };
      node.onclick = () => {};
      hoverInside.push(node);
      return node;
    }
    const hoverList = { contains: node => hoverInside.includes(node) };
    const searchInput = { value: "" };
    const cacheKeys = new Set();
    const hoverState = {
      view: "folders",
      page: 1,
      pageSize: 96,
      folderPage: 1,
      folderPageSize: 100,
      sortKey: "title",
      sortDir: "asc",
      folderRoot: hoverRoot,
      folderPath: "",
      groupName: "",
      libraryInteractionBlocked: false,
      libraryInteractionHoldUntil: 0,
      libraryNavigationSpeculation: null,
      libraryNavigationHoverTimer: 0,
      libraryNavigationHoverNode: null,
      libraryNavigationPrefetch: null,
      libraryResponseCache: { has: url => cacheKeys.has(url) },
    };
    const hoverRequests = [];
    const hoverSettlers = [];
    const hoverTimers = new Map();
    let hoverTimerId = 0;
    let hoverClock = 5000;
    const hoverContext = {
      $: id => (id === "searchInput" ? searchInput : hoverList),
      state: hoverState,
      URLSearchParams, encodeURIComponent, decodeURIComponent,
      Math, Number, String, Boolean, Array, Object, Promise, Error, RegExp, Set,
      Date: { now: () => hoverClock },
      browseCursorForPage: () => "",
      isCreatorView: () => false,
      currentCreatorName: () => "",
      isPlaylistView: () => false,
      groupViews: { albums: "album", artists: "artist", composers: "composer", genres: "genre" },
      setTimeout: (fn, ms) => { hoverTimerId += 1; hoverTimers.set(hoverTimerId, { fn, ms }); return hoverTimerId; },
      clearTimeout: id => { hoverTimers.delete(id); },
      fetchLibraryResponse: (url, message, refresh, signal) => {
        hoverRequests.push({ url, message, refresh, signal });
        return new Promise(resolve => {
          hoverSettlers.push(() => resolve({ items: [], folders: [], count: 0 }));
        });
      },
    };
    const queryParamsSource = fs.readFileSync("app/ui/library_query_params.js", "utf8");
    const builderSource = app.match(/function libraryQueryParamsFor\(folderRoot, folderPath, page, view = state\.view\) \{[\s\S]*?\n\}/);
    assert.ok(builderSource, "libraryQueryParamsFor must stay one top-level function");
    const queryTextSource = app.match(/function currentQueryText\(\) \{[\s\S]*?\n\}/);
    assert.ok(queryTextSource, "currentQueryText must stay one top-level function");
    vm.runInNewContext(
      queryParamsSource + NL + queryTextSource[0] + NL + builderSource[0] + NL + navBlock + NL
      + "globalThis.pair = folderNavigationUrls;"
      + NL + "globalThis.urlsFor = libraryNavigationPrefetchUrls;"
      + NL + "globalThis.arm = armLibraryNavigationHover;"
      + NL + "globalThis.cancelDwell = cancelLibraryNavigationHoverDwell;"
      + NL + "globalThis.prefetch = prefetchLibraryNavigation;",
      hoverContext,
    );
    const drain = async () => {
      for (let tick = 0; tick < 8; tick += 1) await Promise.resolve();
    };
    const settleAll = async () => {
      while (hoverSettlers.length) hoverSettlers.shift()();
      await drain();
    };
    const fireDwell = () => {
      const timer = hoverTimers.get(hoverState.libraryNavigationHoverTimer);
      assert.ok(timer, "the dwell timer must still be armed when it fires");
      hoverTimers.delete(hoverState.libraryNavigationHoverTimer);
      timer.fn();
    };
    const hover = (node, options = {}) => hoverContext.arm(
      Object.assign({ target: node, pointerType: "mouse", buttons: 0 }, options), hoverList);
    const folderRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent(hoverPath),
    });

    // The pair is built once, from the row's own coordinates, and is byte-stable.
    assert.deepEqual(Array.from(hoverContext.pair(hoverRoot, hoverPath, 1, 1)), [expectedFolders, expectedTracks],
      "the speculative pair must be the exact bytes a folder click is going to request");
    assert.ok(expectedFolders.includes("parent=") && !expectedFolders.includes("folder=")
      && expectedTracks.includes("folder=") && !expectedTracks.includes("parent="),
      "the folder half addresses parent= while the track half addresses folder=");
    assert.deepEqual(Array.from(hoverContext.urlsFor(folderRow)), [expectedFolders, expectedTracks],
      "a folder row's own declared coordinates reproduce that pair without mutating state");

    // Dwell, then fire.
    assert.equal(hover(folderRow), true, "a mouse resting on a folder row arms a dwell");
    assert.equal(hoverTimers.size, 1, "one dwell per pointer, not one per mouse-move event");
    assert.equal(hoverTimers.get(hoverState.libraryNavigationHoverTimer).ms, 40,
      "the dwell is short enough to beat a deliberate click and long enough to skip a sweep");
    assert.equal(hoverRequests.length, 0, "nothing leaves the page before the dwell expires");
    const dwellTimerId = hoverState.libraryNavigationHoverTimer;
    hover(folderRow);
    assert.equal(hoverTimers.size, 1, "moving inside the same row may not restart the dwell window");
    assert.equal(hoverState.libraryNavigationHoverTimer, dwellTimerId, "and may not replace its timer");
    fireDwell();
    assert.equal(hoverRequests.length, 2, "the dwell asks for exactly the two requests the click needs");
    assert.deepEqual(hoverRequests.map(request => request.url), [expectedFolders, expectedTracks],
      "with no reordering between the halves");
    assert.deepEqual(hoverRequests.map(request => request.message), ["", ""],
      "a speculative request owns no user-visible error text: the click renders failures");
    assert.deepEqual(hoverRequests.map(request => request.refresh), [false, false],
      "speculation never forces a refresh, which would clear the cache it is filling");
    assert.deepEqual(hoverRequests.map(request => request.signal), [undefined, undefined],
      "and carries no abort signal, so a later navigation cannot kill its own cache fill");
    assert.equal(hoverState.libraryNavigationPrefetch.inFlight.size, 2,
      "both halves of the issued pair are marked in flight");
    assert.equal(hoverState.libraryNavigationPrefetch.issued, 1,
      "and one issued pair costs exactly one unit of the budget");
    assert.equal(hoverState.libraryNavigationHoverTimer, 0, "a fired dwell leaves no timer behind");

    // A bounded budget, not a single slot. The pointer sweeps past a row on its way to the
    // row it actually clicks: refusing everything after the first pair starved exactly the
    // hover this feature exists for (measured on the device), while an unbounded lane would
    // put the R198 connection congestion straight back.
    const secondRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("DSD"),
    });
    assert.equal(hover(secondRow), true, "hovering a second row still arms");
    fireDwell();
    assert.equal(hoverRequests.length, 4, "a second pair is issued while the first is still in flight");
    assert.equal(hover(secondRow), true, "re-entering the same row arms again");
    fireDwell();
    assert.equal(hoverRequests.length, 4, "but its own in-flight pair is never requested twice");
    assert.equal(hoverState.libraryNavigationPrefetch.issued, 2,
      "and a refusal caused by in-flight dedup still spends its budget unit");
    const thirdRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("NEW"),
    });
    hover(thirdRow);
    fireDwell();
    assert.equal(hoverRequests.length, 6, "three pairs per window is what the budget buys");
    const fourthRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("DLP"),
    });
    assert.equal(hover(fourthRow), true, "a fourth hover still arms its dwell");
    fireDwell();
    assert.equal(hoverRequests.length, 6, "and the fourth pair inside the same window is refused");
    await settleAll();
    assert.equal(hoverState.libraryNavigationPrefetch.inFlight.size, 0,
      "a settled half leaves the in-flight set");
    assert.equal(hoverState.libraryNavigationPrefetch.issued, 3,
      "but settling early may not refund the window: the bound is a rate, not a slot count");
    const fifthRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("SACD"),
    });
    hover(fifthRow);
    fireDwell();
    assert.equal(hoverRequests.length, 6, "inside an exhausted window the fifth row gets nothing");
    hoverClock += 2001;
    hover(fifthRow);
    fireDwell();
    assert.equal(hoverRequests.length, 8, "a rolled window serves the same hover again");
    assert.equal(hoverState.libraryNavigationPrefetch.issued, 1, "and rebuilds the budget from zero");
    await settleAll();
    hoverRequests.length = 0;
    hoverClock += 2001;

    // A dwell never outlives its row, its page, or the pointer.
    const leavingRow = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("Hi-Res"),
    });
    hover(leavingRow);
    hoverInside.splice(hoverInside.indexOf(leavingRow), 1);
    fireDwell();
    assert.equal(hoverRequests.length, 0, "a row removed while the pointer dwells may never be fetched");
    hover(leavingRow);
    hoverContext.cancelDwell();
    assert.equal(hoverTimers.size, 0, "the pointer leaving the list cancels the dwell");
    assert.equal(hoverState.libraryNavigationHoverNode, null, "and drops the row it was watching");
    assert.equal(hoverRequests.length, 0, "a cancelled dwell never fires late");
    hoverState.libraryInteractionBlocked = true;
    hoverState.libraryInteractionHoldUntil = hoverClock + 1000;
    assert.equal(hover(folderRow), false,
      "a hover during a page replacement may not spend the connections on rows that are about to be destroyed");
    assert.equal(hoverTimers.size, 0, "and no dwell is armed for it");
    hoverState.libraryInteractionHoldUntil = 0;
    assert.equal(hover(folderRow), true, "outside the hold window the same hover arms again");
    hoverTimers.clear();
    hoverState.libraryNavigationHoverTimer = 0;
    hoverState.libraryNavigationHoverNode = null;
    hoverState.libraryInteractionBlocked = false;

    // Cache hits cost nothing, and a non-folder target costs nothing.
    cacheKeys.add(expectedFolders);
    cacheKeys.add(expectedTracks);
    assert.equal(hover(folderRow), true, "an already-warm row still arms a dwell");
    fireDwell();
    assert.equal(hoverRequests.length, 0, "a fully cached pair issues zero requests");
    assert.equal(hoverState.libraryNavigationPrefetch.issued, 0,
      "a fully cached pair may not spend the budget either");
    hoverRequests.length = 0;
    cacheKeys.clear();

    assert.equal(hover(hoverRow(["[data-group-row]"], {
      groupType: "album",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("album"),
    })), false, "only folder rows are prefetched: their dataset already names the pair");
    assert.equal(hoverTimers.size, 0, "an album row arms nothing");
    const detachedOnclick = hoverRow(["[data-group-row]"], {
      groupType: "folder",
      groupRoot: encodeURIComponent(hoverRoot),
      groupPath: encodeURIComponent("LP转录"),
    });
    detachedOnclick.onclick = undefined;
    assert.equal(hover(detachedOnclick), false,
      "a row without its own click handler cannot be hovered into a navigation");
    assert.equal(hoverTimers.size, 0, "and it arms nothing");
    detachedOnclick.onclick = () => {};
    assert.equal(hover(detachedOnclick, { pointerType: "touch" }), false,
      "a touch sweep may not spend a folder pair the user never meant to open");
    assert.equal(hoverTimers.size, 0, "a touch arms nothing either");
    assert.equal(hover(detachedOnclick, { pointerType: "pen" }), true, "a pen is a hover like a mouse");
    assert.equal(hoverTimers.size, 1, "and arms exactly one dwell");
    hoverTimers.clear();
    hoverState.libraryNavigationHoverTimer = 0;
    assert.equal(hover(detachedOnclick, { buttons: 1 }), false,
      "a held button is a drag or a selection, not a hover");
    assert.equal(hoverTimers.size, 0, "and it arms nothing");
    detachedOnclick.onclick = () => {};
    hoverState.view = "albums";
    assert.equal(hoverContext.urlsFor(detachedOnclick).length, 0,
      "outside the folder view a row dataset does not describe the request that is about to happen");
    assert.equal(hover(detachedOnclick), false, "so hovering there is inert");
    hoverState.view = "folders";

    // The active filter is part of the pair: lose it and the click misses the cache.
    searchInput.value = "周杰伦";
    const filtered = hoverContext.pair(hoverRoot, hoverPath, 1, 1);
    assert.ok(filtered[0].includes("search=%E5%91%A8%E6%9D%B0%E4%BC%A6")
      && filtered[1].includes("search=%E5%91%A8%E6%9D%B0%E4%BC%A6"),
      "the speculative pair carries the same search text the click will send");
    assert.notEqual(filtered[0], expectedFolders, "and therefore keys a different cache entry, never a false hit");
    hoverRequests.length = 0;
    hoverClock += 2001;
    assert.equal(hoverContext.prefetch(folderRow), true,
      "a prefetch with no cached half issues its own pair through the same builder");
    assert.deepEqual(hoverRequests.map(request => request.url), Array.from(filtered),
      "and issues both halves of it, search included, in the builder's order");
    searchInput.value = "";
    await settleAll();

    // Wiring: the dwell has to be fed by the pointer and dropped by the page.
    const hoverBinder = app.match(/function bindTrackListInteractions\([\s\S]*?\n\}/);
    assert.ok(hoverBinder, "the track list interaction binder must remain one top-level function");
    assert.ok(hoverBinder[0].includes('list.addEventListener("pointermove", event => { armLibraryNavigationHover(event, list); })'),
      "the binder has to watch the pointer resting inside the list");
    assert.ok(hoverBinder[0].includes('list.addEventListener("pointerleave", () => cancelLibraryNavigationHoverDwell())'),
      "and has to cancel the dwell when the pointer leaves it");
    const moveAt = hoverBinder[0].indexOf('armLibraryNavigationHover(event, list)');
    assert.ok(moveAt > hoverBinder[0].indexOf("speculateLibraryNavigation(event, list)"),
      "hover speculation is armed after the press path, so a press is never preceded by its own dwell");
    const workerHead = app.match(/async function loadPagedLibraryWorker\(page = 1, refresh = false\) \{[\s\S]*?\n\}\n/);
    assert.ok(workerHead, "the navigation worker must stay one top-level function");
    const cancelAt = workerHead[0].indexOf("cancelLibraryNavigationHoverDwell();");
    const gateAt = workerHead[0].indexOf("state.libraryInteractionBlocked = true;");
    assert.ok(cancelAt >= 0 && (gateAt < 0 || cancelAt < gateAt),
      "a new page drops the dwell that pointed at rows it is about to destroy");
    assert.equal(countOccurrences(app, "const NAVIGATION_HOVER_DWELL_MS = 40;"), 1,
      "the dwell is declared once and bounded");
    assert.equal(countOccurrences(app, "const NAVIGATION_PREFETCH_BUDGET = 3;"), 1,
      "the hover budget is declared once and bounded");
    assert.equal(countOccurrences(app, "const NAVIGATION_PREFETCH_WINDOW_MS = 2000;"), 1,
      "and so is the window that budget rolls inside");
    assert.equal(app.includes("if (state.libraryNavigationPrefetch) return false;"), false,
      "the single-slot gate must not come back: it starved the hover this feature exists for");
    assert.ok(navBlock.includes("budget.inFlight.delete(url)"),
      "a settled half frees its own URL only, never the whole lane");
  }
  // R207: a folder click that lands on a prefetched pair never enters the paged worker, so
  // nothing armed the interaction hold, and the row-metadata lane kept competing with the
  // next click. Measured on 198.51.100.24 with 0.2.50 and a 4x CPU throttle: the click that
  // opens the folders view issued 12 /api/metadata/track requests inside the 268 ms before
  // the list committed, and 13-14 more within the following 5 s.
  {
    const parkNames = ["parkVisibleMetadataPrefetch", "scheduleVisibleMetadataPrefetch", "uiBackgroundWorkBlocked"];
    const laneSource = parkNames.map(name => {
      const found = app.match(new RegExp("function " + name + "\\([\\s\\S]*?\\) \\{[\\s\\S]*?\\n\\}"));
      assert.ok(found, `${name} must stay a top-level function for this check`);
      return found[0];
    }).join(";\n");
    let laneClock = 1000;
    let laneTimer = null;
    let laneCancels = 0;
    const laneCalls = [];
    const laneState = {
      libraryRequestSeq: 7,
      libraryInteractionHoldUntil: 0,
      visibleMetadataPrefetchTimer: 0,
      visibleMetadataPrefetchUsesIdle: false,
      visibleMetadataPrefetchRequestSeq: 0,
      visibleMetadataPrefetchItems: null,
      visibleMetadataPrefetchSeq: 0,
      metadataPrefetchTrackId: "",
      metadataPrefetchController: null,
      pageItems: [],
    };
    const laneContext = {
      state: laneState,
      String, Number, Math, Boolean, Array, Object, Map, Set,
      Date: { now: () => laneClock },
      setTimeout: (fn, ms) => { laneTimer = { fn, ms }; return 1; },
      clearTimeout: () => { laneTimer = null; },
      cancelVisibleMetadataPrefetch: () => { laneCancels += 1; },
      currentItem: () => ({ id: "current-track" }),
      LIBRARY_INTERACTION_HOLD_MS: 4000,
      fnAudioVisibleMetadataPrefetchPolicy: {
        shouldReuseActiveLane: () => false,
        ownsCurrentTrackLane: () => false,
        selectCandidates: (items, cap, excluded) => { laneCalls.push({ items, cap, excluded }); return []; },
      },
    };
    vm.runInNewContext(laneSource + "\n"
      + "globalThis.schedule = scheduleVisibleMetadataPrefetch;"
      + "globalThis.park = parkVisibleMetadataPrefetch;", laneContext);
    const laneItems = [{ id: "one" }, { id: "two" }];

    laneState.libraryInteractionHoldUntil = laneClock + 4000;
    assert.equal(laneContext.schedule(laneItems, 7), undefined, "a parked lane reports nothing");
    assert.equal(laneCalls.length, 0, "while a navigation owns the connections no row may be looked up");
    assert.equal(laneCancels, 0, "and the park happens before the running lane is torn down");
    assert.ok(laneTimer, "the parked lane keeps one page-owned retry timer");
    assert.equal(laneTimer.ms, 4060, "which is scheduled on the hold deadline, not on a new poller cadence");
    assert.equal(laneContext.schedule(laneItems, 7), undefined, "a second schedule request cannot stack a timer");
    assert.equal(laneTimer.ms, 4060, "and cannot retime the one that is already armed");
    assert.equal(laneContext.park(laneItems, 7, laneClock), false, "parking an already parked lane is refused");

    laneClock += 4060;
    laneState.libraryInteractionHoldUntil = 0;
    const armed = laneTimer;
    laneTimer = null;
    armed.fn();
    assert.equal(laneCalls.length, 1, "the parked lane resumes itself exactly once on the deadline");
    assert.equal(laneCalls[0].items, laneItems, "for the page that asked for it");
    assert.equal(laneCalls[0].cap, 6, "with the bounded row cap");
    assert.equal(laneTimer, null, "and it leaves no timer behind");

    laneState.libraryInteractionHoldUntil = laneClock + 4000;
    laneState.libraryRequestSeq = 9;
    assert.equal(laneContext.schedule(laneItems, 7), undefined, "a stale page still parks");
    const stale = laneTimer;
    laneTimer = null;
    laneState.libraryInteractionHoldUntil = 0;
    stale.fn();
    assert.equal(laneCalls.length, 1, "a lane whose page moved on may not restart");
    assert.equal(laneCancels, 1, "and the resume that does run releases the previous generation once");

    laneState.libraryRequestSeq = 7;
    laneState.libraryInteractionHoldUntil = 0;
    laneContext.schedule(laneItems, 7);
    assert.equal(laneCalls.length, 2, "outside the hold window the same call looks the rows up at once");
  }
  {
    const speculation = app.match(/function speculateLibraryNavigation\([\s\S]*?\n\}/);
    assert.ok(speculation, "the press-time speculation must stay one top-level function");
    const body = speculation[0];
    const armAt = body.indexOf("armLibraryInteractionHold();");
    const clickAt = body.indexOf("node.onclick(event)");
    assert.ok(armAt >= 0 && clickAt > armAt,
      "the press arms the hold before it runs the control's own handler, so a cached navigation still parks the lanes");
    const laneAt = body.indexOf("cancelVisibleMetadataPrefetch({ cancelRearms: false });");
    const coverAt = body.indexOf("state.coverLoadScheduler?.stop?.();");
    assert.ok(armAt >= 0 && armAt < laneAt && laneAt < coverAt && coverAt < clickAt,
      "the press arms the hold first, then aborts the stale row lane and cover queue, and only then runs the control handler");
    assert.ok(body.indexOf('if (event.button || event.isPrimary === false) return false;') < armAt,
      "and only for a real primary press: a right button or a secondary pointer arms nothing");
  }
  console.log("Library loading cancellation regression checks passed.");
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
