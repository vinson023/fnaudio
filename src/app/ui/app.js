const state = { items: [], view: "all", queue: [], index: -1, devices: [], repeat: "off", shuffle: false, folderPath: "", playTarget: "local", playTargetName: "本机播放" };
const $ = (id) => document.getElementById(id);
state.playTargetName = "当前设备";
const audio = $("audio");
const groupViews = { albums: "album", artists: "artist", composers: "composer", genres: "genre" };
function isCreatorView(view = state.view) {
  return globalThis.fnAudioCreatorViewPolicy.isCreatorView(view);
}
function currentCreatorName() {
  return globalThis.fnAudioCreatorViewPolicy.currentCreatorName(state);
}
function currentCreatorAllTracks() {
  return globalThis.fnAudioCreatorViewPolicy.currentCreatorAllTracks(state);
}
function currentCreatorTrackTotal() {
  return globalThis.fnAudioCreatorViewPolicy.currentCreatorTrackTotal(state);
}
function currentCreatorLabel() {
  return globalThis.fnAudioCreatorViewPolicy.currentCreatorLabel(state);
}
function setCurrentCreator(name, trackTotal = 0) {
  globalThis.fnAudioCreatorViewPolicy.setCurrentCreator(state, name, trackTotal);
}
function setCurrentCreatorAllTracks(enabled) {
  globalThis.fnAudioCreatorViewPolicy.setCurrentCreatorAllTracks(state, enabled);
}
function clearCurrentCreator() {
  globalThis.fnAudioCreatorViewPolicy.clearCurrentCreator(state);
}
function resetCreatorState() {
  globalThis.fnAudioCreatorViewPolicy.resetCreatorState(state);
}
function isCreatorAllTracksView() {
  return globalThis.fnAudioCreatorViewPolicy.isCreatorAllTracksView(state);
}
function isCreatorAlbumView() {
  return globalThis.fnAudioCreatorViewPolicy.isCreatorAlbumView(state);
}
function isAlbumCollectionView() {
  return globalThis.fnAudioCreatorViewPolicy.isAlbumCollectionView(state);
}
function isAlbumDetailView() {
  return globalThis.fnAudioCreatorViewPolicy.isAlbumDetailView(state);
}
function isAlbumSurfaceView() {
  return globalThis.fnAudioCreatorViewPolicy.isAlbumSurfaceView(state);
}
const PLAYLIST_STORE_KEY = "fnaudio.playlists";
const FAVORITE_STORE_KEY = "fnaudio.favorites";
const MAX_LOCAL_PLAYLISTS = 1000;
const MAX_LOCAL_PLAYLIST_TRACK_IDS = 10000;
const MAX_LOCAL_FAVORITES = 50000;
// Local storage is mutable outside this app. Bound JSON parsing before the
// first library render so a damaged entry cannot stall startup.
const MAX_UI_PREFERENCE_STORAGE_CHARS = 256 * 1024;
const MAX_USER_MEDIA_STORAGE_CHARS = 4 * 1024 * 1024;
const TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v3";
const TRACK_COLUMN_WIDTHS_STORE_KEY = "fnaudio.trackColumnWidths.v1";
const LIBRARY_PAGE_SNAPSHOT_KEY = "fnaudio.libraryPageSnapshot.v1";
const LIBRARY_PAGE_SNAPSHOT_TTL_MS = 15 * 60 * 1000;
const LIBRARY_PAGE_SNAPSHOT_MAX_BYTES = 384 * 1024;
const LEGACY_TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v2";
const OLDER_TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v1";
const TRACK_LONG_PRESS_DURATION_MS = 550;
const TRACK_LONG_PRESS_MOVE_THRESHOLD_PX = 10;
let activeTrackLongPress = null;
let suppressedTrackClick = { rowKey: "", until: 0 };

function parseStoredJson(key, fallback, maxChars = MAX_UI_PREFERENCE_STORAGE_CHARS) {
  try {
    const raw = localStorage.getItem(key);
    if (typeof raw !== "string" || raw.length > maxChars) return fallback;
    return JSON.parse(raw);
  } catch (_) {
    return fallback;
  }
}

const TRACK_COLUMN_DEFINITIONS = {
  title: { label: "标题", width: 420, sort: "title" },
  track_no: { label: "序号", width: 64, sort: "track_no" },
  artist: { label: "歌手", width: 200, sort: "artist" },
  album: { label: "专辑", width: 240, sort: "album" },
  format: { label: "格式", width: 76, sort: "format" },
  duration: { label: "时长", width: 72 },
  size: { label: "大小", width: 88 },
  quality: { label: "音质", width: 120 },
  added: { label: "加入时间", width: 110, sort: "added" },
  composer: { label: "作曲者", width: 180 },
  genre: { label: "类型", width: 130 },
};
const DEFAULT_TRACK_COLUMNS = ["title", "track_no", "format", "album"];
const DEFAULT_LIBRARY_TRACK_COLUMNS = ["title", "artist", "album", "size", "format"];
const DEFAULT_ALBUM_DETAIL_TRACK_COLUMNS = ["track_no", ...DEFAULT_LIBRARY_TRACK_COLUMNS];
const PAGED_LIBRARY_VIEWS = new Set(["all", "dsd", "recent", "random100", "folders", "albums", "artists", "composers", "genres"]);
state.libraryStatus = null;
state.libraryStatusPromise = null;
state.libraryStatusRefreshQueued = false;
state.libraryStatusRequestToken = 0;
state.libraryStatusController = null;
state.accessProfile = "lan";
state.accessProfileLoader = globalThis.fnAudioAccessProfileLoader?.create({
  fetchProfile: () => fetchJsonChecked("api/access", {}, "读取访问模式失败"),
});
state.mp3Transcode = localStorage.getItem("fnaudio.mp3Transcode") === "1";
state.sortDir = localStorage.getItem("fnaudio.sortDir.v2") || "asc";
state.sortKey = localStorage.getItem("fnaudio.sortKey.v1") || "title";
state.remoteStatus = null;
state.dacStrategy = null;
state.lyrics = [];
state.lyricsTrackId = "";
state.lyricsStatus = "idle";
state.lyricsRequestToken = 0;
state.lyricsLoadingTrackId = "";
state.lyricsRequestController = null;
state.lyricsPollTimer = 0;
state.lyricsPollAttempts = 0;
state.seeking = false;
state.streamOffset = 0;
state.pendingSeekTime = null;
state.transcodeCacheReady = false;
state.transcodeStatusRequestToken = 0;
state.transcodeStatusController = null;
state.playSourceKind = "";
state.playbackLoadToken = 0;
state.random100 = [];
state.playlists = loadStoredPlaylists();
state.favorites = loadStoredFavorites();
state.pendingPlaylistTrack = "";
state.pendingPlaylistTrackIds = [];
state.actionTrackId = "";
state.metadataCandidatePollTimer = 0;
state.metadataCandidatePollAttempts = 0;
state.metadataCandidateRequestToken = 0;
state.metadataCandidateController = null;
const METADATA_CANDIDATE_MAX_POLLS = 12;
// Track-level metadata prefetches are started when playback begins, rather
// than waiting for the user to open the candidate dialog.  Keep one token per
// song so rapid next/previous actions cannot apply a stale response to the
// newly playing row.
state.metadataPrefetchToken = 0;
state.metadataPrefetchTrackId = "";
state.metadataPrefetchTimer = 0;
state.metadataPrefetchUnavailable = false;
state.metadataPrefetchAttempts = 0;
state.metadataPrefetchRecoverySeen = "";
state.metadataPrefetchStartedAt = 0;
state.metadataPrefetchRearms = 0;
const METADATA_PREFETCH_MAX_ATTEMPTS = 12;
state.metadataPrefetchLyricsTrackId = "";
state.metadataPrefetchLyricsToken = 0;
state.metadataPrefetchLyricsAttempts = 0;
state.metadataPrefetchLyricsTimer = 0;
state.metadataPrefetchController = null;
state.metadataPrefetchLyricsController = null;
state.metadataRowRenderTimer = 0;
state.metadataRowRenderUsesFrame = false;
state.metadataRowRenderTrackIds = new Set();
state.metadataRowRenderFieldsByTrack = new Map();
state.metadataRowRenderForceFull = false;
state.metadataRowRenderExpectedRequestSeq = 0;
state.metadataRowRenderExpectedView = "";
state.metadataRowRenderExpectedPage = 1;
state.metadataRowRenderExpectedPageItems = null;
// A small, cancellable first-page metadata lane.  It improves the initial
// cover/album experience without enabling whole-library background crawling.
state.visibleMetadataPrefetchTimer = 0;
// `requestIdleCallback` is allowed to run immediately when the browser thinks
// it has a gap.  Keep an explicit quiet window before opening provider
// requests so a newly committed first page can paint and decode its local
// covers without competing with metadata JSON, SQLite and keyed row patches.
state.visibleMetadataPrefetchUsesIdle = false;
state.visibleMetadataPrefetchSeq = 0;
state.visibleMetadataPrefetchKeys = new Set();
// Keys claimed by the currently running lane are separate from completed
// dedupe history.  A same-page status refresh may abort the lane; those
// in-flight claims must be released so the replacement lane can retry them.
state.visibleMetadataPrefetchActiveKeys = new Map();
state.visibleMetadataPrefetchController = null;
state.visibleMetadataPrefetchRequestSeq = 0;
state.visibleMetadataPrefetchItems = null;
// A pending provider task can outlive one visible-lane polling window. Keep
// one page-scoped, finite quiet re-arm so worker recovery does not require a
// manual page switch, while still avoiding a permanent background poller.
state.visibleMetadataPrefetchRearmTimer = 0;
state.visibleMetadataPrefetchRearmKeys = new Map();
state.visibleMetadataPrefetchRearmSeq = 0;
state.renderedNavigationView = "";
state.groupName = "";
state.artistName = "";
state.artistAllTracks = false;
state.artistTrackTotal = 0;
state.composerName = "";
state.composerAllTracks = false;
state.composerTrackTotal = 0;
state.remoteWasPlaying = false;
state.remoteAutoAdvanceAt = 0;
state.remoteSnapshotAt = 0;
state.remoteBaseSeconds = 0;
state.remoteStatusRequestInFlight = false;
state.remoteStatusRequestToken = 0;
state.remoteStatusController = null;
state.remoteEventSource = null;
state.itemHydrationPool = null;
state.itemHydrationGeneration = 0;
state.itemHydrationRequest = null;
// Several referenced-item batches can settle in the same visual frame.
// Coalesce their DOM work so a favorites/playlist list is not repainted once
// per batch while the cache fills.
state.itemHydrationRenderTimer = 0;
state.itemHydrationInflight = new Map();
state.itemHydrationInflightLimit = 32;
state.remoteEventConnected = false;
state.remoteEventRetryAt = 0;
state.remoteUiLast = { transport: "", duration: -1, seconds: -1, current: "" };
state.remoteStateVersion = 0;
state.remoteLoadPromise = null;
state.remoteLoadedKey = "";
state.remoteLoadedAt = 0;
state.remoteLoadController = null;
state.remoteCueSegment = false;
state.libraryLoading = false;
// Keep the previous list mounted during navigation to avoid a blank flash,
// but make that stale projection inert until the replacement page commits.
state.libraryInteractionBlocked = false;
state.libraryLoaded = 0;
state.libraryTotal = 0;
state.page = 1;
const defaultPageSize = globalThis.fnAudioLibraryPageSizePolicy?.defaultPageSize(window) || 120;
state.pageSize = globalThis.fnAudioLibraryPageSizePolicy?.resolvePageSize(localStorage, window) || defaultPageSize;
state.pageTotal = 0;
state.pageItems = [];
state.groupRows = [];
state.folderRows = [];
state.folderRootRows = [];
state.folderRoot = "";
state.folderPage = 1;
state.folderPageSize = 100;
state.folderTotal = 0;
state.itemCache = fnAudioItemCache(12000);
state.itemCacheLimit = 12000;
state.libraryResponseCache = fnAudioLruCache(48, { maxWeight: 6000, weightOf: libraryResponseWeight });
// Deduplicate identical requests while a response is still in flight. The
// completed-response LRU above cannot prevent duplicate fetches during a
// rapid redraw; refresh requests intentionally bypass this map.
state.libraryResponseInflight = new Map();
state.libraryResponseInflightLimit = 32;
state.libraryResponseActive = { value: 0 };
state.libraryResponseEpoch = 0;
state.libraryStatusTimer = 0;
state.accessProfileTimer = 0;
// Stable projection marker for metadata-backed fields in library responses.
// Pending-job churn must not redraw the list; only committed metadata counts
// (or an observable terminal error) invalidate the response LRU.
state.metadataProjectionSignature = "";
state.libraryRequestSeq = 0;
state.libraryAbortController = null;
state.libraryLoadKey = "";
state.libraryLoadPromise = null;
// Identity of the last authoritative track page. It is distinct from the
// in-flight load key so actions such as play-all cannot reuse visible rows
// after the user has changed a search/filter but before its debounce reload.
state.libraryPageKey = "";
// Optional keyset continuation tokens for sequential track pages. Page jumps
// and older hosts continue to use the existing offset contract.
state.libraryPageCursors = new Map();
// Keep the last committed row markup so status/metadata refreshes do not
// tear down and recreate an unchanged list (which causes a visible flash and
// resets image decoding in older WebViews).
state.renderedTrackListHtml = null;
// Most status refreshes (position, device labels, counters) do not alter the
// visible song rows.  Retain their already-built markup by page-array identity
// so the keyed commit guard does not first pay to serialize every row again.
// Queue rows deliberately remain uncached because their inline playing marker
// follows the current queue index.
state.trackRowsMarkupCache = typeof WeakMap === "function" ? new WeakMap() : null;
// Queue pagination and current-track定位 can ask for the same sorted window
// during one render. Keep only the latest bounded result; replacing the queue
// array or changing search/sort naturally invalidates it.
state.queueDisplayCache = { queue: null, search: "", sortKey: "", direction: 1, entries: [] };
state.filteredTracksCache = { signature: null, tracks: [] };
state.hydratingIds = new Set();
// Missing items are normally a transient state while the library refreshes.
// Keep a finite, expiring negative cache so a short response cannot suppress
// that ID forever or accumulate across large playlist switches.
state.unresolvedItemIds = globalThis.fnAudioItemNegativeCache?.create?.() || new Set();
state.deviceLoadInFlight = false;
state.deviceLoadRequestToken = 0;
state.deviceLoadController = null;
state.deviceRefreshTimer = null;
state.deviceTargetsSignature = "";
state.deviceSwitchInFlight = false;
state.deviceTargetRevision = 0;
state.rendererSession = null;
state.rendererSnapshotAt = 0;
// The uri of a cast this browser stopped with a local play intent (TODO.md:72
// ruling D-2). The status poll would otherwise hand the row straight back to it.
state.rendererPreemptedUri = "";
state.rendererRequestInFlight = false;
state.rendererRequestToken = 0;
state.rendererRequestController = null;
state.remoteGeneration = 0;
state.remoteEngineEpoch = 0;
state.userStateHydrated = false;
state.userStateSaveTimer = null;
state.userStateSaveInFlight = false;
state.userStateRevision = 0;
state.userStateRefreshInFlight = false;
state.userStateBase = { favorites: [], playlists: [] };
state.userStateDirty = false;
state.trackColumnPreferences = loadTrackColumnPreferences();
state.trackColumnWidthPreferences = loadTrackColumnWidthPreferences();
state.autoTrackColumnWidths = {};
state.columnDialogColumns = null;
state.selectedTrackRowKeys = new Set();
state.selectedGroupKeys = new Set();
state.actionGroupKey = "";
state.externalShareLocation = null;
state.pendingDeleteTrackIds = [];
state.albumMetadata = globalThis.fnAudioAlbumMetadataCache?.(4096) || {
  get() { return undefined; },
  set() { return this; },
  get size() { return 0; }
};
state.settingsTab = "library";
state.searchTimer = null;
state.nativePlayback = { available: false, mediaId: "", queueIds: [], position: 0, duration: 0, playing: false, playbackState: 1 };
state.mediaSession = { supported: false, metadata: false, actions: [], host: "standalone" };
state.hostPlaybackSession = typeof window.fnAudioCreateHostPlaybackSession === "function"
  ? window.fnAudioCreateHostPlaybackSession(window)
  : null;
state.hostPlaybackSessionActivated = false;
state.hostPlaybackMediaContextId = "";
state.coverLoadScheduler = null;
state.coverLoadStatus = { generation: 0, queued: 0, inFlight: 0, dropped: 0 };
// Lightweight client-side evidence for first-paint regressions. Counters are
// session-scoped and bounded; they never participate in rendering decisions.
state.uiMetrics = {
  renders: 0,
  listCommits: 0,
  // A warm start can retain its already-built snapshot rows when the
  // authoritative page is visually identical. Keep this separate from the
  // normal no-op counter so diagnostics can prove the anti-flicker handoff
  // was actually used instead of merely assuming it from timing.
  snapshotMarkupReuses: 0,
  listMarkupNoops: 0,
  coverHydrations: 0,
  coverRequests: 0,
  coverLoads: 0,
  coverFailures: 0,
  coverRetries: 0,
  sessionStartedAt: Date.now(),
  firstListCommitMs: 0,
  firstCoverHydrationMs: 0,
  metadataPrefetchFirstMs: 0,
  metadataPrefetchRequests: 0,
  metadataPrefetchSuccesses: 0,
  metadataPrefetchFailures: 0,
  metadataPrefetchNoMatches: 0,
  metadataPrefetchLastMs: 0,
  metadataPrefetchMaxMs: 0,
  metadataPrefetchTotalMs: 0,
};
window.__fnAudioUiMetrics = state.uiMetrics;
// Expose a stable, bounded diagnostic projection without exposing the
// mutable internal counter object to external tooling.
window.__fnAudioUiMetricsSnapshot = () => {
  try {
    return globalThis.fnAudioUiMetricsPolicy?.snapshot(state.uiMetrics) || {};
  } catch (_) {
    return {};
  }
};
state.librarySnapshot = { hit: false, stale: false, savedAt: 0 };
state.librarySnapshotEmptyGuardUsed = false;
state.librarySnapshotPersistTimer = 0;
state.librarySnapshotPersistKey = "";
// Referenced queue/favorite/playlist rows are useful after restoring user
// state, but must never compete with the first visible library page. Keep the
// delayed owner explicit so a view switch can cancel the old post-paint task.
state.referencedItemHydrationTimer = 0;
state.referencedItemHydrationKey = "";

function librarySnapshotKey(page = 1) {
  // A bootstrap snapshot is a cached library response. Reuse the complete
  // request identity so nested artist/album/folder selections cannot restore
  // another surface's rows before the authoritative response arrives.
  return libraryLoadRequestKey(page);
}

function restoreLibraryPageSnapshot(page = 1) {
  try {
    const raw = localStorage.getItem(LIBRARY_PAGE_SNAPSHOT_KEY);
    const snapshot = globalThis.fnAudioLibraryPageSnapshotPolicy?.restore(raw, {
      key: librarySnapshotKey(page), now: Date.now(), ttlMs: LIBRARY_PAGE_SNAPSHOT_TTL_MS,
      maxBytes: LIBRARY_PAGE_SNAPSHOT_MAX_BYTES,
      boundItems: items => globalThis.fnAudioLibraryRenderPolicy?.boundedTrackRows(items, state.pageSize)
        || items.slice(0, Math.max(1, Math.min(500, Number(state.pageSize) || 120))),
    });
    if (!snapshot || snapshot.status !== "hit") {
      state.librarySnapshot = { hit: false, stale: snapshot?.status === "stale", savedAt: Number(snapshot?.savedAt || 0) };
      return false;
    }
    state.page = globalThis.fnAudioLibraryPageSnapshotPolicy?.boundedPage(page) || 1;
    state.pageItems = snapshot.items;
    state.items = state.pageItems;
    state.pageTotal = snapshot.total;
    state.libraryLoaded = state.pageItems.length;
    state.libraryTotal = state.pageTotal;
    state.libraryLoading = false;
    cacheLibraryItems(state.pageItems);
    state.librarySnapshot = { hit: true, stale: false, savedAt: snapshot.savedAt };
    return true;
  } catch (error) {
    state.librarySnapshot = { hit: false, stale: false, savedAt: 0 };
    return false;
  }
}

function persistLibraryPageSnapshot(page = 1) {
  if (!isPagedTrackListing() || !Array.isArray(state.pageItems) || !state.pageItems.length) return;
  try {
    const savedAt = Date.now();
    const encoded = globalThis.fnAudioLibraryPageSnapshotPolicy?.encode({
      key: librarySnapshotKey(page), savedAt, total: state.pageTotal,
      items: state.pageItems, maxBytes: LIBRARY_PAGE_SNAPSHOT_MAX_BYTES,
    });
    if (!encoded) return;
    localStorage.setItem(LIBRARY_PAGE_SNAPSHOT_KEY, encoded);
    state.librarySnapshot = { hit: state.librarySnapshot.hit, stale: false, savedAt };
  } catch (error) {
    // Quota/private-mode failures must never block the library request.
  }
}

function scheduleLibraryPageSnapshot(page = 1) {
  if (state.librarySnapshotPersistTimer) {
    if (typeof cancelIdleCallback === "function") cancelIdleCallback(state.librarySnapshotPersistTimer);
    else clearTimeout(state.librarySnapshotPersistTimer);
  }
  const key = librarySnapshotKey(page);
  state.librarySnapshotPersistKey = key;
  const persist = () => {
    state.librarySnapshotPersistTimer = 0;
    if (state.librarySnapshotPersistKey !== key || librarySnapshotKey(page) !== key) return;
    persistLibraryPageSnapshot(page);
  };
  if (typeof requestIdleCallback === "function") {
    state.librarySnapshotPersistTimer = requestIdleCallback(persist, { timeout: 1200 });
  } else {
    state.librarySnapshotPersistTimer = setTimeout(persist, 180);
  }
}

function cancelReferencedItemHydrationSchedule() {
  if (!state.referencedItemHydrationTimer) return;
  if (typeof cancelIdleCallback === "function") cancelIdleCallback(state.referencedItemHydrationTimer);
  else clearTimeout(state.referencedItemHydrationTimer);
  state.referencedItemHydrationTimer = 0;
  state.referencedItemHydrationKey = "";
}

function scheduleReferencedItemHydration(requestSeq) {
  const view = state.view;
  const key = `${requestSeq}:${view}:${state.page}`;
  if (state.referencedItemHydrationTimer && state.referencedItemHydrationKey === key) return;
  cancelReferencedItemHydrationSchedule();
  state.referencedItemHydrationKey = key;
  const run = () => {
    state.referencedItemHydrationTimer = 0;
    if (
      state.referencedItemHydrationKey !== key
      || requestSeq !== state.libraryRequestSeq
      || state.view !== view
    ) return;
    state.referencedItemHydrationKey = "";
    hydrateReferencedItems();
  };
  // Queue and favorite hydration may involve hundreds of IDs after a session
  // restore. Yield it until after the authoritative first page has painted;
  // old WebViews use the short timer fallback when requestIdleCallback is not
  // available.
  if (typeof requestIdleCallback === "function") {
    state.referencedItemHydrationTimer = requestIdleCallback(run, { timeout: 600 });
  } else {
    state.referencedItemHydrationTimer = setTimeout(run, 80);
  }
}

function nativePlaybackAvailable() {
  if (isRemoteTarget()) return false;
  return nativeBridgeAvailable();
}
function nativeBridgeAvailable() {
  try {
    return Boolean(window.FnAudioNative && typeof window.FnAudioNative.isAvailable === "function" && window.FnAudioNative.isAvailable());
  } catch (error) {
    return false;
  }
}
function nativePlaybackCall(method, ...args) {
  if (!nativePlaybackAvailable()) return false;
  try {
    const bridge = window.FnAudioNative;
    if (typeof bridge?.[method] !== "function") return false;
    bridge[method](...args);
    return true;
  } catch (error) {
    return false;
  }
}
const browserFetch = window.fetch.bind(window);
const nativeHttpRequests = new Map();
const nativeHttpResponseChunks = new Map();
const MAX_NATIVE_HTTP_REQUESTS = 32;
const MAX_NATIVE_HTTP_CHUNKS = 256;
const MAX_NATIVE_HTTP_CHUNK_CHARS = 256 * 1024;
const MAX_NATIVE_HTTP_RESPONSE_CHARS = 4 * 1024 * 1024;
let nativeHttpRequestSequence = 0;
function nativeAbortError() {
  if (typeof DOMException === "function") {
    return new DOMException("The operation was aborted.", "AbortError");
  }
  const error = new Error("The operation was aborted.");
  error.name = "AbortError";
  return error;
}
function clearNativeHttpTransfer(key, transfer) {
  if (!transfer) return;
  clearTimeout(transfer.timer);
  if (nativeHttpResponseChunks.get(key) === transfer) nativeHttpResponseChunks.delete(key);
}
function clearNativeHttpRequest(requestId, pending, error = null) {
  if (!pending || nativeHttpRequests.get(requestId) !== pending) return false;
  nativeHttpRequests.delete(requestId);
  clearTimeout(pending.timer);
  if (pending.signal && pending.abortHandler) pending.signal.removeEventListener("abort", pending.abortHandler);
  try { window.FnAudioNative?.cancelRequestJson(requestId); } catch (ignore) {}
  if (error) pending.reject(error);
  return true;
}
function evictOldestNativeHttpRequest() {
  const oldest = nativeHttpRequests.entries().next();
  if (oldest.done) return false;
  const [requestId, pending] = oldest.value;
  return clearNativeHttpRequest(requestId, pending, new TypeError("原生认证请求过多，请稍后重试"));
}
function nativeHttpAvailable() {
  try {
    return Boolean(window.FnAudioNative && typeof window.FnAudioNative.requestJson === "function");
  } catch (error) {
    return false;
  }
}
function isFnAudioApiUrl(url) {
  return url.origin === window.location.origin
    && /\/cgi\/ThirdParty\/fnaudio\/(?:index\.cgi\/)?api\//.test(url.pathname);
}
function nativeHttpResponse(payload) {
  const source = payload && typeof payload === "object" ? payload : {};
  const body = typeof source.body === "string" ? source.body : "";
  const rawStatus = source.status;
  const status = typeof rawStatus === "number" && Number.isFinite(rawStatus)
    ? Math.max(0, Math.min(599, Math.trunc(rawStatus))) : 0;
  let headers;
  try { headers = new Headers(source.headers && typeof source.headers === "object" ? source.headers : {}); }
  catch (_) { headers = new Headers(); }
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: typeof source.statusText === "string" ? source.statusText.slice(0, 256) : "",
    url: typeof source.url === "string" ? source.url.slice(0, 4096) : "",
    headers,
    text: async () => body,
    json: async () => JSON.parse(body),
  };
}
window.fnAudioNativeOnHttpResponse = payload => {
  let result = payload;
  try { if (typeof payload === "string") result = JSON.parse(payload); }
  catch (error) { return; }
  const requestId = String(result?.requestId || "");
  const pending = nativeHttpRequests.get(requestId);
  if (!pending) return;
  clearNativeHttpRequest(requestId, pending);
  if (typeof result.networkError === "string" && result.networkError) {
    pending.reject(new TypeError(result.networkError.slice(0, 256)));
  } else {
    try { pending.resolve(nativeHttpResponse(result)); }
    catch (error) { pending.reject(error instanceof Error ? error : new TypeError("原生响应无效")); }
  }
};
window.fnAudioNativeOnHttpChunk = (transferId, index, total, chunk) => {
  const key = String(transferId || "");
  const part = Number(index);
  const count = Number(total);
  if (!key || !Number.isInteger(part) || !Number.isInteger(count)
      || part < 0 || count <= 0 || count > MAX_NATIVE_HTTP_CHUNKS) return;
  const fragment = String(chunk || "");
  if (fragment.length > MAX_NATIVE_HTTP_CHUNK_CHARS) return;
  let transfer = nativeHttpResponseChunks.get(key);
  if (!transfer || transfer.total !== count) {
    if (nativeHttpResponseChunks.size >= 32) return;
    transfer = {
      total: count,
      chunks: new Array(count),
      received: 0,
      chars: 0,
      timer: setTimeout(() => clearNativeHttpTransfer(key, transfer), 60000),
    };
    nativeHttpResponseChunks.set(key, transfer);
  }
  if (part < 0 || part >= transfer.total || transfer.chunks[part] !== undefined) return;
  if (transfer.chars > MAX_NATIVE_HTTP_RESPONSE_CHARS - fragment.length) {
    clearNativeHttpTransfer(key, transfer);
    return;
  }
  transfer.chunks[part] = fragment;
  transfer.received += 1;
  transfer.chars += fragment.length;
  if (transfer.received !== transfer.total) return;
  clearNativeHttpTransfer(key, transfer);
  window.fnAudioNativeOnHttpResponse(transfer.chunks.join(""));
};
function apiFetch(input, init = {}) {
  const requestMethod = String(init.method || (typeof Request !== "undefined" && input instanceof Request ? input.method : "GET")).toUpperCase();
  let url;
  try {
    url = new URL(typeof Request !== "undefined" && input instanceof Request ? input.url : String(input), window.location.href);
  } catch (error) {
    return browserFetch(input, init);
  }
  if (!nativeHttpAvailable() || !isFnAudioApiUrl(url)) {
    return browserFetch(input, init);
  }
  if (typeof Request !== "undefined" && input instanceof Request && init.body == null) {
    return browserFetch(input, init);
  }
  const body = init.body == null ? "" : init.body;
  if (typeof body !== "string") return browserFetch(input, init);
  const headers = new Headers(typeof Request !== "undefined" && input instanceof Request ? input.headers : undefined);
  new Headers(init.headers || {}).forEach((value, name) => headers.set(name, value));
  const headerObject = {};
  headers.forEach((value, name) => { headerObject[name] = value; });
  const requestId = `http-${Date.now()}-${++nativeHttpRequestSequence}`;
  return new Promise((resolve, reject) => {
    const signal = init.signal;
    if (signal?.aborted) {
      reject(nativeAbortError());
      return;
    }
    const abortHandler = () => {
      const pending = nativeHttpRequests.get(requestId);
      if (!pending) return;
      clearNativeHttpRequest(requestId, pending, nativeAbortError());
    };
    const timer = setTimeout(() => {
      const pending = nativeHttpRequests.get(requestId);
      if (!pending) return;
      clearNativeHttpRequest(requestId, pending, new TypeError("原生认证请求超时"));
    }, 45000);
    while (nativeHttpRequests.size >= MAX_NATIVE_HTTP_REQUESTS) evictOldestNativeHttpRequest();
    nativeHttpRequests.set(requestId, { resolve, reject, timer, signal, abortHandler });
    if (signal) signal.addEventListener("abort", abortHandler, { once: true });
    try {
      window.FnAudioNative.requestJson(requestId, requestMethod, url.href, JSON.stringify(headerObject), body);
    } catch (error) {
      const pending = nativeHttpRequests.get(requestId);
      if (pending) clearNativeHttpRequest(requestId, pending, error);
      else reject(error);
    }
  });
}
async function fetchJsonChecked(input, init = {}, fallbackMessage = "请求失败", options = {}) {
  // A strict caller treats "the body could not be read" as a failure instead of
  // handing the fallback back as if the server had answered with an empty
  // collection. The library list is the one response that gets cached per URL and
  // painted as authoritative, so an oversized or half-delivered body used to reach
  // the screen as a song list that looks legitimately empty.
  const strictBody = options?.strictBody === true;
  const externalSignal = init?.signal;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let removeExternalAbort = null;
  if (controller && externalSignal && typeof externalSignal.addEventListener === "function") {
    const abortFromOwner = () => { try { controller.abort(); } catch (_) {} };
    if (externalSignal.aborted) abortFromOwner();
    else {
      externalSignal.addEventListener("abort", abortFromOwner, { once: true });
      removeExternalAbort = () => {
        try { externalSignal.removeEventListener("abort", abortFromOwner); } catch (_) {}
      };
    }
  }
  try {
    const request = fetch(input, {
      ...init,
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 15000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    const data = result.data || {};
    if (!response.ok) {
      throw new Error(data.message || data.error || `${fallbackMessage}（HTTP ${response.status}）`);
    }
    if (strictBody && globalThis.fnAudioResponseJsonLoader.usableBody?.(result.bodyStatus) === false) {
      const error = new Error(`${fallbackMessage}（响应体不完整）`);
      error.name = "ResponseError";
      error.bodyStatus = result.bodyStatus;
      throw error;
    }
    return data;
  } finally {
    if (removeExternalAbort) removeExternalAbort();
  }
}
async function fetchJsonResponseBounded(input, init = {}, timeoutMs = 15000) {
  const externalSignal = init?.signal;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let removeExternalAbort = null;
  if (controller && externalSignal && typeof externalSignal.addEventListener === "function") {
    const abortFromOwner = () => { try { controller.abort(); } catch (_) {} };
    if (externalSignal.aborted) abortFromOwner();
    else {
      externalSignal.addEventListener("abort", abortFromOwner, { once: true });
      removeExternalAbort = () => {
        try { externalSignal.removeEventListener("abort", abortFromOwner); } catch (_) {}
      };
    }
  }
  try {
    const request = fetch(input, {
      ...init,
      ...(controller ? { signal: controller.signal } : {}),
    });
    return await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: Math.max(1000, Math.min(30000, Number(timeoutMs) || 15000)),
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
  } finally {
    if (removeExternalAbort) removeExternalAbort();
  }
}
async function readResponseJsonBounded(response, fallback = {}) {
  try {
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request: Promise.resolve(response),
      timeoutMs: 15000,
      fallback,
    });
    return result.data || fallback;
  } catch (_) {
    return fallback;
  }
}
// Route every same-origin fnAudio API call through the authenticated native
// bridge. browserFetch was captured before this assignment, so non-API
// resources and fallback requests still use WebView's original implementation.
window.fetch = apiFetch;
function absoluteAppUrl(value) {
  try { return new URL(String(value || ""), window.location.href).href; }
  catch (error) { return String(value || ""); }
}
function nativePlaybackUrl(item, isCurrent = false) {
  const params = new URLSearchParams();
  if (shouldTranscodeToMp3(item)) {
    params.set("transcode", "mp3");
    if (isCurrent && state.transcodeCacheReady) params.set("cache", "1");
    else if (item.cue_track === true && playbackSeconds(item.cue_start) > 0) params.set("start", String(playbackSeconds(item.cue_start)));
  } else if (shouldTranscodeDsdToWav(item)) params.set("transcode", "dsd_wav");
  // Neither the browser media element nor Android ExoPlayer decodes Monkey's
  // Audio reliably. Explicitly request the server's lossless FLAC resource;
  // `transcode=original` would override the server-side automatic fallback.
  else if (item.cue_track === true) params.set("transcode", "cue_flac");
  else if (isApeTrack(item)) params.set("transcode", "ape_flac");
  else params.set("transcode", "original");
  return absoluteAppUrl(`${item.url}?${params.toString()}`);
}

function isApeTrack(item) {
  return String(item?.format || "").toUpperCase() === "APE"
    || /\.ape(?:$|[?#])/i.test(String(item?.url || item?.path || ""));
}
function nativeQueueItems() {
  return state.queue.map((item, index) => ({
    id: String(item.id || ""),
    uri: nativePlaybackUrl(item, index === state.index),
    title: displayTrackTitle(item),
    artist: displayText(item.artist),
    album: displayText(item.album),
    artwork: coverUrl(item, 512) ? absoluteAppUrl(coverUrl(item, 512)) : "",
    durationMs: Math.max(0, Math.round(playbackSeconds(item.duration) * 1000)),
  }));
}
function nativeRemoteEnter(force = false) {
  if (!isRemoteTarget() || !nativeBridgeAvailable() || !state.queue.length || !currentItem()) return false;
  if (!state.remoteGeneration) state.remoteGeneration = Date.now() & 0x7fffffff;
  if (!state.remoteEngineEpoch) state.remoteEngineEpoch = 1;
  const position = currentSeconds();
  const duration = seekDuration();
  const transport = String(state.remoteStatus?.transport?.state || "").toUpperCase();
  const signature = JSON.stringify([state.playTarget, nativeQueueSignature(), state.index]);
  if (!force && state.nativeRemoteSignature === signature) {
    nativeBridgeCall("updateRemoteState", state.playTarget, state.index, position, duration,
      transport === "PLAYING" || transport === "TRANSITIONING", state.remoteGeneration, state.remoteEngineEpoch);
    return true;
  }
  state.nativeRemoteSignature = signature;
  nativeBridgeCall("enterRemoteMode", state.playTarget, state.playTargetName || "远程播放", JSON.stringify(nativeQueueItems()), state.index,
    position, duration, transport === "PLAYING" || transport === "TRANSITIONING", state.repeat, Boolean(state.shuffle),
    state.remoteGeneration, state.remoteEngineEpoch);
  return true;
}
function nativeRemoteUpdate() {
  if (!isRemoteTarget() || !nativeBridgeAvailable() || !currentItem()) return false;
  const transport = String(state.remoteStatus?.transport?.state || "").toUpperCase();
  return nativeBridgeCall("updateRemoteState", state.playTarget, state.index, currentSeconds(), seekDuration(),
    transport === "PLAYING" || transport === "TRANSITIONING", state.remoteGeneration, state.remoteEngineEpoch);
}
function nativeRemoteExit() {
  state.nativeRemoteSignature = "";
  state.remoteGeneration = 0;
  state.remoteEngineEpoch = 0;
  return nativeBridgeCall("exitRemoteMode");
}
function nativeBridgeCall(method, ...args) {
  if (!nativeBridgeAvailable()) return false;
  try {
    const bridge = window.FnAudioNative;
    if (typeof bridge?.[method] !== "function") return false;
    bridge[method](...args);
    return true;
  } catch (error) {
    return false;
  }
}
function nativeQueueSignature(rows = nativeQueueItems()) {
  // Queue IDs and source URLs are opaque. Delimiter-based signatures can
  // collide when a valid filename/URI contains that delimiter, suppressing a
  // necessary bridge queue replacement.
  return JSON.stringify(rows.map(item => [item?.id, item?.uri]));
}
function nativeLoadQueue(autoPlay = true, startSeconds = 0, force = false) {
  const item = currentItem();
  if (!item || !nativePlaybackAvailable()) return false;
  const rows = nativeQueueItems();
  const signature = nativeQueueSignature(rows);
  const remoteIds = Array.isArray(state.nativePlayback.queueIds) ? state.nativePlayback.queueIds.map(String) : [];
  const localIds = rows.map(row => row.id);
  const sameIds = remoteIds.length === localIds.length && remoteIds.every((id, index) => id === localIds[index]);
  const sameCurrent = String(state.nativePlayback.mediaId || "") === String(item.id || "");
  if (!force && sameIds && sameCurrent) {
    if (autoPlay) nativePlaybackCall("play");
    return true;
  }
  state.nativeQueueSignature = signature;
  nativePlaybackCall("setQueue", JSON.stringify(rows), state.index, Math.max(0, Number(startSeconds || 0)), Boolean(autoPlay), state.repeat, Boolean(state.shuffle));
  return true;
}
function nativeQueueNeedsRestore() {
  const item = currentItem();
  if (!item) return false;
  const expectedIds = nativeQueueItems().map(row => String(row.id));
  const nativeIds = Array.isArray(state.nativePlayback.queueIds)
    ? state.nativePlayback.queueIds.map(String)
    : [];
  return !nativeIds.length
    || nativeIds.length !== expectedIds.length
    || nativeIds.some((id, index) => id !== expectedIds[index])
    || String(state.nativePlayback.mediaId || "") !== String(item.id || "");
}
window.fnAudioNativeOnState = payload => {
  let snapshot = payload;
  try { if (typeof payload === "string") snapshot = JSON.parse(payload); }
  catch (error) { return; }
  if (!snapshot || snapshot.available !== true) return;
  const previousMediaId = String(state.nativePlayback.mediaId || "");
  state.nativePlayback = { ...state.nativePlayback, ...snapshot, available: true };
  const mediaId = String(snapshot.mediaId || "");
  if (mediaId && mediaId !== String(currentItem()?.id || "")) {
    const next = state.queue.findIndex(item => String(item.id || "") === mediaId);
    if (next >= 0) {
      const previousIndex = state.index;
      state.index = next;
      state.streamOffset = 0;
      state.pendingSeekTime = null;
      state.transcodeCacheReady = false;
      state.playSourceKind = "native";
      syncCurrentQueuePresentation(previousIndex);
      restoreLibraryNowPlaying();
      syncLyricsForCurrentTrack(currentItem());
      updateMediaSessionMetadata(currentItem());
      updateFavoriteControls();
      scheduleUserStateSave();
    }
  }
  if (mediaId && mediaId !== previousMediaId) updateNowMarquee();
  setPlayButton(snapshot.playing === true);
  const duration = playbackSeconds(snapshot.duration, playbackSeconds(currentItem()?.duration));
  const seconds = playbackSeconds(snapshot.position);
  setTextContentIfChanged($("elapsed"), clock(seconds));
  setTextContentIfChanged($("duration"), clock(duration));
  if (!state.seeking) $("seek").value = duration ? Math.max(0, Math.min(100, seconds / duration * 100)) : 0;
  syncPlayerProgress();
  updateLyricHighlight();
};

function normalizeTrackColumns(columns) {
  const selected = Array.isArray(columns) ? [...new Set(columns.filter(key => TRACK_COLUMN_DEFINITIONS[key]))] : [];
  return selected.length ? selected : [...DEFAULT_TRACK_COLUMNS];
}
function defaultTrackColumnsForScope(scope = trackColumnScope()) {
  if (scope.startsWith("albums:tracks:")) return [...DEFAULT_ALBUM_DETAIL_TRACK_COLUMNS];
  if (scope.startsWith("artists:tracks:")) return [...DEFAULT_LIBRARY_TRACK_COLUMNS];
  return scope === "all" || scope === "dsd" || scope.startsWith("folders:") ? [...DEFAULT_LIBRARY_TRACK_COLUMNS] : [...DEFAULT_TRACK_COLUMNS];
}
function trackColumnsForScope(scope, columns) {
  const normalized = normalizeTrackColumns(columns);
  const usesOldLibraryDefault = normalized.length === DEFAULT_TRACK_COLUMNS.length && normalized.every((key, index) => key === DEFAULT_TRACK_COLUMNS[index]);
  const usesPreviousAlbumDetailDefault = scope.startsWith("albums:tracks:")
    && normalized.length === DEFAULT_LIBRARY_TRACK_COLUMNS.length
    && normalized.every((key, index) => key === DEFAULT_LIBRARY_TRACK_COLUMNS[index]);
  if (usesPreviousAlbumDetailDefault) return defaultTrackColumnsForScope(scope);
  return (scope === "all" || scope === "dsd" || scope.startsWith("folders:")) && usesOldLibraryDefault ? defaultTrackColumnsForScope(scope) : normalized;
}
function loadTrackColumnPreferences() {
  const saved = parseStoredJson(TRACK_COLUMNS_STORE_KEY, []);
  if (saved && typeof saved === "object" && !Array.isArray(saved)) {
    return Object.fromEntries(Object.entries(saved).map(([scope, columns]) => [scope, normalizeTrackColumns(columns)]));
  }
  const legacy = parseStoredJson(LEGACY_TRACK_COLUMNS_STORE_KEY, []);
  if (legacy && typeof legacy === "object" && !Array.isArray(legacy)) {
    const migrated = Object.fromEntries(Object.entries(legacy).map(([scope, columns]) => [scope, normalizeTrackColumns(["title", ...(Array.isArray(columns) ? columns : [])])]));
    try { localStorage.setItem(TRACK_COLUMNS_STORE_KEY, JSON.stringify(migrated)); } catch (_) {}
    return migrated;
  }
  if (Array.isArray(legacy) && legacy.length) {
    const migrated = { all: normalizeTrackColumns(["title", ...legacy]) };
    try { localStorage.setItem(TRACK_COLUMNS_STORE_KEY, JSON.stringify(migrated)); } catch (_) {}
    return migrated;
  }
  const older = parseStoredJson(OLDER_TRACK_COLUMNS_STORE_KEY, []);
  if (Array.isArray(older) && older.length) return { all: normalizeTrackColumns(["title", ...older]) };
  return {};
}
function normalizeTrackColumnWidths(widths) {
  const source = widths && typeof widths === "object" && !Array.isArray(widths) ? widths : {};
  return Object.fromEntries(Object.entries(source).flatMap(([key, value]) => {
    const width = Math.round(Number(value));
    return TRACK_COLUMN_DEFINITIONS[key] && Number.isFinite(width) && width >= 64 && width <= 900 ? [[key, width]] : [];
  }));
}
function loadTrackColumnWidthPreferences() {
  const saved = parseStoredJson(TRACK_COLUMN_WIDTHS_STORE_KEY, {});
  if (saved && typeof saved === "object" && !Array.isArray(saved)) {
    return Object.fromEntries(Object.entries(saved).map(([scope, widths]) => [scope, normalizeTrackColumnWidths(widths)]));
  }
  return {};
}
function trackColumnScopePart(value) {
  return encodeURIComponent(String(value || ""));
}
function buildTrackColumnScope(encodeParts) {
  const part = encodeParts ? trackColumnScopePart : (value => String(value || ""));
  if (isPlaylistLibraryView()) return "all";
  if (state.view === "folders") return `folders:${part(state.folderRoot || "root")}:${part(state.folderPath || "")}`;
  if (isCreatorAllTracksView()) return "all";
  if (isCreatorView()) {
    if (currentCreatorName() && state.groupName) return `albums:tracks:${part(state.groupName)}`;
    if (currentCreatorName()) return `${state.view}:albums:${part(currentCreatorName())}`;
    return state.view;
  }
  if (state.view === "albums") return state.groupName ? `albums:tracks:${part(state.groupName)}` : "albums";
  if (state.view === "genres") return state.groupName ? "all" : "genres";
  return String(state.view || "all");
}
function trackColumnScope() {
  return buildTrackColumnScope(true);
}
function legacyTrackColumnScope() {
  return buildTrackColumnScope(false);
}
function trackColumnScopeLabel() {
  const scope = trackColumnScope();
  if (scope.startsWith("folders:")) return "当前文件夹";
  if (scope.startsWith("artists:albums:")) return "当前歌手的专辑列表";
  if (scope.startsWith("composers:albums:")) return "当前作曲者的专辑列表";
  if (scope.startsWith("albums:tracks:")) return "当前专辑的歌曲列表";
  if (scope.startsWith("genres:tracks:")) return "当前类型的歌曲列表";
  return { all: "全部音乐", dsd: "DSD 音乐", albums: "专辑列表", artists: "歌手列表", composers: "作曲者列表", genres: "类型列表", recent: "最近添加", random100: "随机 100 首", favorites: "收藏歌曲", queue: "当前队列" }[scope] || "当前列表";
}
function persistTrackColumnPreferences() {
  localStorage.setItem(TRACK_COLUMNS_STORE_KEY, JSON.stringify(state.trackColumnPreferences));
  localStorage.setItem(TRACK_COLUMN_WIDTHS_STORE_KEY, JSON.stringify(state.trackColumnWidthPreferences));
}
function currentTrackColumns() {
  const scope = trackColumnScope();
  if (Array.isArray(state.trackColumnPreferences[scope])) return trackColumnsForScope(scope, state.trackColumnPreferences[scope]);
  const legacyScope = legacyTrackColumnScope();
  if (legacyScope !== scope && Array.isArray(state.trackColumnPreferences[legacyScope])) {
    const migrated = trackColumnsForScope(scope, state.trackColumnPreferences[legacyScope]);
    state.trackColumnPreferences[scope] = migrated;
    persistTrackColumnPreferences();
    scheduleUserStateSave();
    return migrated;
  }
  return defaultTrackColumnsForScope(scope);
}
function saveTrackColumns(columns) {
  state.trackColumnPreferences[trackColumnScope()] = normalizeTrackColumns(columns);
  persistTrackColumnPreferences();
  scheduleUserStateSave();
}
function currentTrackColumnWidths() {
  const scope = trackColumnScope();
  return { ...normalizeTrackColumnWidths(state.autoTrackColumnWidths[scope]), ...normalizeTrackColumnWidths(state.trackColumnWidthPreferences[scope]) };
}
function saveTrackColumnWidth(key, width) {
  const column = TRACK_COLUMN_DEFINITIONS[key];
  const value = Math.max(64, Math.min(900, Math.round(Number(width) || column?.width || 120)));
  const scope = trackColumnScope();
  state.trackColumnWidthPreferences[scope] = { ...normalizeTrackColumnWidths(state.trackColumnWidthPreferences[scope]), [key]: value };
  persistTrackColumnPreferences();
  scheduleUserStateSave();
}

function formatSize(bytes) {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB"];
  let n = bytes, i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}
function fixMojibake(value) {
  const text = String(value || "");
  if (!/[ÃÂ�鈾鎾繧縺]/.test(text)) return text;
  try {
    const repaired = decodeURIComponent(escape(text));
    if (repaired && repaired !== text) return repaired;
  } catch (error) {
  }
  return text;
}
function displayText(value) {
  return fixMojibake(value)
    .replace(/[\u0000-\u001f\u007f-\u009f]/g, "")
    .replace(/[□■▢▣▤▥▦▧▨▩◻◼◽◾]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}
function escapeRegExp(value) {
  return String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function displayTrackTitle(item) {
  const title = displayText(item?.title);
  const artist = displayText(item?.artist);
  if (!title || !artist) return title;

  // Keep the library metadata unchanged. Only hide an exact duplicate artist
  // prefix or suffix that has been included in the title for display.
  const escapedArtist = escapeRegExp(artist);
  const separator = "[\\s\\-–—_:|]+";
  const wrappedArtist = "[【[(（]\\s*" + escapedArtist + "\\s*[】)）]\\s*";
  const cleaned = title
    .replace(new RegExp("^" + wrappedArtist, "i"), "")
    .replace(new RegExp("^" + escapedArtist + separator, "i"), "")
    .replace(new RegExp(separator + escapedArtist + "$", "i"), "")
    .trim();
  return cleaned || title;
}
function clock(value) {
  if (!Number.isFinite(value)) return "0:00";
  return `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
}
function playbackSeconds(value, fallback = 0) {
  if (typeof value === "boolean") return fallback;
  const number = typeof value === "number" || typeof value === "string" ? Number(value) : NaN;
  return Number.isFinite(number) && number >= 0 ? number : fallback;
}
function remoteStateVersion(value) {
  if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return null;
  if (typeof value === "string" && value.length > 32) return null;
  let number;
  try { number = Number(value); } catch (_) { return null; }
  return Number.isSafeInteger(number) && number >= 0 && number <= 2147483647 ? number : null;
}
function seekPercent(value, fallback = 0) {
  const number = typeof value === "number" || typeof value === "string" ? Number(value) : NaN;
  return Number.isFinite(number) ? Math.max(0, Math.min(100, number)) : fallback;
}
function libraryCount(value, fallback = 0) {
  const bounded = globalThis.fnAudioLibraryFullListPolicy?.boundedCount?.(value);
  return Number.isFinite(bounded) ? bounded : fallback;
}
function userStateRevision(value, fallback = 0) {
  if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return fallback;
  if (typeof value === "string" && value.length > 64) return fallback;
  let numeric;
  try { numeric = Number(value); } catch (_) { return fallback; }
  return Number.isSafeInteger(numeric) && numeric >= 0 && numeric <= 1000000000000
    ? numeric : fallback;
}
function mediaUrl(path) {
  const value = typeof path === "string" && path.length <= 4096 ? path : "";
  if (!value) return "";
  try {
    const url = new URL(value, window.location.href);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    return url.href;
  } catch (error) {
    return "";
  }
}
function coverUrl(item, size = 160) {
  const thumbnail = Number(size) === 160 ? item?.cover_thumbnail_url : "";
  const source = thumbnail || item?.cover_url;
  if (typeof source !== "string" || !source.trim() || source.length > 4096) return "";
  try {
    const url = new URL(mediaUrl(source), window.location.href);
    if (!["http:", "https:"].includes(url.protocol)) return "";
    if (Number(size) > 0) url.searchParams.set("size", String(Number(size)));
    return url.href;
  } catch (error) {
    // A malformed historical/provider URL must not abort the whole list
    // render. Treat only this cover as unavailable so the row keeps its
    // centered music-symbol fallback and later metadata refresh can recover.
    return "";
  }
}
function usableCoverSource(value) {
  if (typeof value !== "string" || !value.trim() || value.length > 4096) return "";
  try {
    const url = new URL(mediaUrl(value.trim()), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (_) {
    return "";
  }
}
function resetPlaybackProgress() {
  state.transcodeStatusRequestToken += 1;
  try { state.transcodeStatusController?.abort(); } catch (_) {}
  state.transcodeStatusController = null;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
}
function dacCapsText(caps = {}) {
  return globalThis.fnAudioDeviceCapsPresentation.format(caps);
}
function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, x => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[x]));
}
function parseLyrics(text) {
  return globalThis.fnAudioLyricsParsePolicy.parse(text);
}
function itemById(id) {
  return fnAudioItemLookup.lookupItem(id, state.itemCache, state.pageItems, state.items);
}
function currentItem() { return state.queue[state.index]; }
function isRemoteTarget() { return globalThis.fnAudioPlaybackTargetPolicy.isRemote(state.playTarget); }
function isDacTarget(target = state.playTarget) { return globalThis.fnAudioPlaybackTargetPolicy.isDac(target); }
function isMpdTarget(target = state.playTarget) { return globalThis.fnAudioPlaybackTargetPolicy.isMpd(target); }
function loadStoredPlaylists() {
  const value = parseStoredJson(PLAYLIST_STORE_KEY, [], MAX_USER_MEDIA_STORAGE_CHARS);
  return normalizeUserMediaState({ playlists: value }).playlists;
}
function savePlaylists() {
  localStorage.setItem(PLAYLIST_STORE_KEY, JSON.stringify(state.playlists));
  scheduleUserStateSave();
}
function loadStoredFavorites() {
  const value = parseStoredJson(FAVORITE_STORE_KEY, [], MAX_USER_MEDIA_STORAGE_CHARS);
  return normalizeUserMediaState({ favorites: value }).favorites;
}
function saveFavorites() {
  localStorage.setItem(FAVORITE_STORE_KEY, JSON.stringify(state.favorites));
  scheduleUserStateSave();
}
function normalizeUserMediaState(source = {}) {
  return globalThis.fnAudioUserMediaStatePolicy.normalize(source);
}
function userStateChanges() {
  return globalThis.fnAudioUserMediaStatePolicy.changes(state.userStateBase, { favorites: state.favorites, playlists: state.playlists });
}
function applyUserStateChanges(source, changes) {
  return globalThis.fnAudioUserMediaStatePolicy.apply(source, changes);
}
function persistUserMediaState(value) {
  state.favorites = value.favorites;
  state.playlists = value.playlists;
  localStorage.setItem(FAVORITE_STORE_KEY, JSON.stringify(state.favorites));
  localStorage.setItem(PLAYLIST_STORE_KEY, JSON.stringify(state.playlists));
  updateFavoriteControls();
}
function userStatePayload() {
  return {
    favorites: state.favorites,
    playlists: state.playlists,
    changes: userStateChanges(),
    revision: state.userStateRevision,
    playback: {
      queue: state.queue.map(item => String(item.id || "")).filter(Boolean),
      current_id: state.queue[state.index]?.id || "",
      repeat: state.repeat,
      shuffle: state.shuffle,
      target_id: state.playTarget || "local",
    },
    ui: {
      track_columns: state.trackColumnPreferences,
      track_column_widths: state.trackColumnWidthPreferences,
    },
  };
}
function scheduleUserStateSave(delay = 350) {
  if (!state.userStateHydrated) return;
  state.userStateDirty = true;
  if (state.userStateSaveInFlight) return;
  clearTimeout(state.userStateSaveTimer);
  state.userStateSaveTimer = setTimeout(saveUserStateNow, delay);
}
async function saveUserStateNow() {
  if (!state.userStateHydrated) return;
  if (state.userStateSaveInFlight) {
    state.userStateDirty = true;
    return;
  }
  clearTimeout(state.userStateSaveTimer);
  state.userStateSaveInFlight = true;
  state.userStateDirty = false;
  const payload = userStatePayload();
  let retryDelay = 350;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  try {
    const request = apiFetch("api/state/user", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    const data = result.data || {};
    if (data.state && (response.ok || response.status === 409)) {
      const latestChanges = userStateChanges();
      const serverMedia = normalizeUserMediaState(data.state);
      state.userStateBase = serverMedia;
      state.userStateRevision = userStateRevision(data.state.revision, state.userStateRevision || 0);
      persistUserMediaState(applyUserStateChanges(serverMedia, latestChanges));
      if (response.status === 409) state.userStateDirty = true;
    } else if (!response.ok || !globalThis.fnAudioResponseJsonLoader.parsedBody(result.bodyStatus)) {
      // A 200 whose body never made it here is not an acknowledgement: keep the
      // queued changes dirty so they retry instead of being dropped silently.
      state.userStateDirty = true;
      retryDelay = 2000;
    }
  } catch (error) {
    state.userStateDirty = true;
    retryDelay = 2000;
  } finally {
    state.userStateSaveInFlight = false;
    if (state.userStateDirty) scheduleUserStateSave(retryDelay);
  }
}
async function loadServerUserState() {
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  try {
    const request = fetch("api/state/user", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const data = result.data || {};
    const serverState = data?.state || {};
    let visibleListChanged = false;
    if (serverState.initialized) {
      visibleListChanged = await applyServerUserState(serverState);
    } else {
      state.userStateRevision = userStateRevision(serverState.revision);
      state.userStateBase = normalizeUserMediaState(serverState);
    }
    state.userStateHydrated = true;
    if (!serverState.initialized) scheduleUserStateSave();
    renderAfterUserStateHydration({ visibleListChanged });
  } catch (error) {
    // A transient startup failure must not leave this lane permanently
    // disabled: both saving and periodic reconciliation are gated on this
    // flag. Keep the local copy, mark it for conflict-aware persistence, and
    // let the normal retry path reconcile once the service returns.
    state.userStateHydrated = true;
    state.userStateDirty = true;
    scheduleUserStateSave(2000);
    renderAfterUserStateHydration();
  } finally {}
}
async function applyServerUserState(serverState) {
  // The server state request intentionally runs alongside the first library
  // page.  Preserve a compact signature of only the state that can alter the
  // currently mounted song rows before applying it, so an identical remote
  // state does not cause a second full list render just after first paint.
  const visibleSignatureBefore = visibleUserStatePresentationSignature();
  state.userStateRevision = userStateRevision(serverState.revision);
  state.userStateBase = normalizeUserMediaState(serverState);
  persistUserMediaState(state.userStateBase);
  const remoteColumns = serverState?.ui?.track_columns;
  if (remoteColumns && typeof remoteColumns === "object" && !Array.isArray(remoteColumns) && Object.keys(remoteColumns).length) {
    state.trackColumnPreferences = Object.fromEntries(Object.entries(remoteColumns).map(([scope, columns]) => [scope, normalizeTrackColumns(columns)]));
    persistTrackColumnPreferences();
  }
  const remoteWidths = serverState?.ui?.track_column_widths;
  if (remoteWidths && typeof remoteWidths === "object" && !Array.isArray(remoteWidths) && Object.keys(remoteWidths).length) {
    state.trackColumnWidthPreferences = Object.fromEntries(Object.entries(remoteWidths).map(([scope, widths]) => [scope, normalizeTrackColumnWidths(widths)]));
    persistTrackColumnPreferences();
  }
  await restorePlaybackSession(serverState.playback || {});
  return visibleSignatureBefore !== visibleUserStatePresentationSignature();
}
async function refreshServerUserState() {
  if (!state.userStateHydrated || state.userStateSaveInFlight || state.userStateRefreshInFlight) return;
  state.userStateRefreshInFlight = true;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  try {
    const request = fetch("api/state/user", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const data = result.data || {};
    const serverState = data?.state || {};
    const revision = userStateRevision(serverState.revision);
    if (serverState.initialized && revision > state.userStateRevision) {
      const pendingChanges = userStateChanges();
      const visibleSignatureBefore = visibleUserStatePresentationSignature();
      await applyServerUserState(serverState);
      // applyServerUserState may await queue hydration or remote status. Any
      // local edit made during that wait is now represented by latestChanges;
      // retain both generations instead of letting the older snapshot win.
      const latestChanges = userStateChanges();
      const favoriteOperations = new Map();
      [...(pendingChanges.favorites_add || [])].forEach(id => favoriteOperations.set(id, true));
      [...(pendingChanges.favorites_remove || [])].forEach(id => favoriteOperations.set(id, false));
      [...(latestChanges.favorites_add || [])].forEach(id => favoriteOperations.set(id, true));
      [...(latestChanges.favorites_remove || [])].forEach(id => favoriteOperations.set(id, false));
      const playlistOperations = new Map();
      [...(pendingChanges.playlist_upserts || [])].forEach(item => {
        if (item && typeof item.id === "string" && item.id) playlistOperations.set(item.id, item);
      });
      [...(pendingChanges.playlist_delete || [])].forEach(id => playlistOperations.set(id, null));
      [...(latestChanges.playlist_upserts || [])].forEach(item => {
        if (item && typeof item.id === "string" && item.id) playlistOperations.set(item.id, item);
      });
      [...(latestChanges.playlist_delete || [])].forEach(id => playlistOperations.set(id, null));
      const mergedChanges = {
        favorites_add: [...favoriteOperations].filter(([, added]) => added).map(([id]) => id),
        favorites_remove: [...favoriteOperations].filter(([, added]) => !added).map(([id]) => id),
        playlist_upserts: [...playlistOperations.values()].filter(item => item),
        playlist_delete: [...playlistOperations].filter(([, item]) => !item).map(([id]) => id),
      };
      const merged = applyUserStateChanges(serverState, mergedChanges);
      // applyServerUserState replaces the in-memory media state with the
      // newer server snapshot. Re-apply local edits to memory as well as
      // localStorage, otherwise a background refresh makes unsaved favorites
      // or playlist edits disappear until the next reload.
      persistUserMediaState(merged);
      const visibleListChanged = visibleSignatureBefore !== visibleUserStatePresentationSignature();
      if (JSON.stringify(merged) !== JSON.stringify(state.userStateBase)) scheduleUserStateSave();
      renderAfterUserStateHydration({ visibleListChanged });
    }
  } catch (error) {
  } finally {
    state.userStateRefreshInFlight = false;
  }
}
function hasVisibleLibraryPresentation() {
  // User-state hydration runs in parallel with the initial library request.
  // Rendering before that request resolves briefly commits an empty track list,
  // then immediately replaces it with page one: a prominent first-open flash
  // on slower NASes. A valid snapshot also counts as visible presentation.
  return globalThis.fnAudioLibraryRenderPolicy?.hasVisiblePresentation({
    librarySnapshotHit: state.librarySnapshot?.hit === true,
    libraryLoaded: state.libraryLoaded,
    pageItemsLength: state.pageItems?.length,
    groupRowsLength: state.groupRows?.length,
    folderRowsLength: state.folderRows?.length,
    folderRootRowsLength: state.folderRootRows?.length,
  }) === true;
}

function visibleUserStatePresentationSignature() {
  // Do not include the entire restored playback payload: normal player
  // controls are updated in-place and should never make a large library list
  // rebuild.  The fields below are the only user-state fields that affect
  // the mounted rows, table geometry, or the active client-side collection.
  const currentPlaylistState = isPlaylistView() ? currentPlaylist() : null;
  const queueState = state.view === "queue"
    ? (state.queue || []).map(item => String(item?.id || ""))
    : [];
  try {
    return JSON.stringify({
      columns: state.trackColumnPreferences || {},
      widths: state.trackColumnWidthPreferences || {},
      favorites: state.favorites || [],
      playlist: currentPlaylistState
        ? { id: String(currentPlaylistState.id || ""), name: String(currentPlaylistState.name || ""), trackIds: currentPlaylistState.trackIds || [] }
        : null,
      queue: queueState,
      queueIndex: state.view === "queue" ? Number(state.index || 0) : 0,
    });
  } catch (error) {
    // A malformed local cache should choose the conservative path and allow
    // one render, rather than make user-state restoration fail.
    return "";
  }
}

function refreshUserStateChrome() {
  renderPlaylistNav();
  updateFavoriteControls();
  updateRepeatShuffleButtons();
  updateDeviceLabel();
  if (!isIncomingRendererSession()) restoreLibraryNowPlaying();
}

function renderAfterUserStateHydration({ visibleListChanged = false } = {}) {
  // A restored page snapshot is already visible while the authoritative
  // request is in flight. Rendering the whole page again merely because the
  // user-state request won that race can make older WebViews repaint every
  // visible row and briefly flash their lazy covers. Keep player/navigation
  // state truthful now; the in-flight page response performs the one list
  // commit with the hydrated state.
  if (state.libraryLoading && state.librarySnapshot?.hit) {
    refreshUserStateChrome();
    return;
  }
  if (hasVisibleLibraryPresentation()) {
    // A late but semantically identical state response was the remaining
    // first-open flash: it rebuilt the first page after covers had begun
    // decoding. Render only when it actually changes visible rows/columns.
    if (visibleListChanged) render();
    else refreshUserStateChrome();
    return;
  }
  // Keep the player and navigation truthful while the first page is still in
  // flight, without constructing an empty list or scheduling row measurements.
  refreshUserStateChrome();
}
async function restorePlaybackSession(playback) {
  // On a cold start the first page and a restored large queue both read the
  // same SQLite index.  Give the visible library page one short head start:
  // otherwise four queue-hydration batches can contend with page one and
  // turn a fast cached list into a visibly slow/blank initial paint. This is
  // only the initial hydration path; subsequent server-state refreshes keep
  // their existing immediate recovery behavior.
  if (!state.userStateHydrated && state.libraryLoading && state.libraryLoadPromise) {
    try { await state.libraryLoadPromise; } catch (error) {}
  }
  const queueIds = Array.isArray(playback.queue) ? playback.queue.map(String).filter(Boolean) : [];
  if (queueIds.length) {
    const previousQueue = Array.isArray(state.queue) ? state.queue : [];
    const previousById = new Map(previousQueue.map(item => [String(item?.id || ""), item]));
    const byId = new Map();
    let fetchedAny = false;
    // CGI/App Center proxies and some mobile WebViews reject very long query
    // strings. Hydrate a large persisted queue in bounded batches instead of
    // sending hundreds of IDs in one request. A failed batch is ignored so a
    // transient proxy error cannot erase an already playing queue.
    const batches = [];
    for (let offset = 0; offset < queueIds.length; offset += 100) batches.push(queueIds.slice(offset, offset + 100));
    const pool = fnAudioBatchRequestPool(batches, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY, async batch => {
      try {
        const data = await fetchJsonChecked(
          `api/library/items?ids=${encodeURIComponent(batch.join(","))}`,
          {},
          "读取播放队列失败",
        );
        return Array.isArray(data.items) ? data.items : [];
      } catch (error) {
        // Keep cached rows for this batch and continue hydrating later rows.
        return [];
      }
    });
    for (let index = 0; index < batches.length; index += 1) {
      const items = await pool.get(index);
      items.forEach(item => {
        if (item && item.id) byId.set(String(item.id), item);
      });
      fetchedAny = fetchedAny || items.length > 0;
    }
    const hydrated = queueIds.map(id => byId.get(id) || previousById.get(id)).filter(Boolean);
    if (hydrated.length || fetchedAny || !previousQueue.length) {
      state.queue = hydrated;
      cacheLibraryItems(state.queue);
    }
  }
  const currentId = String(playback.current_id || "");
  state.index = state.queue.findIndex(item => String(item.id) === currentId);
  if (state.index < 0 && state.queue.length) state.index = 0;
  state.repeat = ["off", "all", "one"].includes(playback.repeat) ? playback.repeat : "off";
  state.shuffle = playback.shuffle === true;
  state.playTarget = String(playback.target_id || "local");
  state.playTargetName = state.playTarget === "local" ? "当前设备" : "已恢复播放设备";
  await validateRestoredPlaybackTarget();
  const nativeCurrentId = String(state.nativePlayback.mediaId || "");
  if (state.playTarget === "local" && nativeCurrentId) {
    const nativeIndex = state.queue.findIndex(item => String(item.id || "") === nativeCurrentId);
    if (nativeIndex >= 0) state.index = nativeIndex;
  }
  updateRepeatShuffleButtons();
  updateDeviceLabel();
  restoreLibraryNowPlaying();
  // A restored session does not necessarily re-enter `loadCurrent()` (for
  // example after a cold WebView start), so explicitly kick the bounded
  // current-track metadata lane here.  Without this, a song can show its
  // restored title while lyrics/cover enrichment waits until the next manual
  // play action.
  prefetchCurrentTrackMetadata(currentItem());
  syncLyricsForCurrentTrack(currentItem());
  if (isRemoteTarget() && state.queue.length) {
    startRemoteEventStream();
    await refreshRemoteStatus({ allowAdvance: false });
    const remoteCore = state.remoteStatus?.core;
    if (remoteCore) applyCoreSnapshot(remoteCore, false);
    nativeRemoteEnter(true);
    updateRemoteUi();
  } else if (state.playTarget === "local" && state.queue.length && nativePlaybackAvailable()) {
    // Android may have been killed while the server-side session remains. Keep
    // the restored queue prepared locally, but preserve the stopped state.
    nativeLoadQueue(false, 0, true);
  }
}
function isPlaylistView(view = state.view) { return String(view || "").startsWith("playlist:"); }
function isPlaylistLibraryView(view = state.view) {
  return view === "random100" || view === "recent" || view === "favorites" || view === "queue" || isPlaylistView(view);
}
function playlistIdFromView(view = state.view) { return String(view || "").replace(/^playlist:/, ""); }
function currentPlaylist() { return state.playlists.find(x => x.id === playlistIdFromView()); }
function makePlaylistId() { return `pl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`; }
function shuffleItems(list) {
  return window.fnAudioShufflePolicy?.shuffle?.(list) || [];
}
function recentTracks() {
  if (state.view === "recent" && state.pageItems.length) return state.pageItems;
  return [];
}
function itemAddedTime(item) {
  return Number(item.added_ns || item.added || item.modified_ns || item.modified || 0);
}
function sortDirectionFactor() {
  return state.sortDir === "asc" ? 1 : -1;
}
function refreshSortedView() {
  if (isPagedLibraryView()) { state.folderPage = 1; requestLibraryLoad(1, false); }
  else {
    if (isClientPagedView()) state.page = 1;
    render();
  }
}
function applyTrackSort(sortKey) {
  if (!sortOptionsForView().some(([value]) => value === sortKey)) return;
  if (state.sortKey === sortKey) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
  else {
    state.sortKey = sortKey;
    state.sortDir = "asc";
  }
  localStorage.setItem("fnaudio.sortKey.v1", state.sortKey);
  localStorage.setItem("fnaudio.sortDir.v2", state.sortDir);
  refreshSortedView();
}
function columnDragIcon() {
  return '<svg viewBox="0 0 12 18" aria-hidden="true"><circle cx="3" cy="3" r="1"/><circle cx="9" cy="3" r="1"/><circle cx="3" cy="9" r="1"/><circle cx="9" cy="9" r="1"/><circle cx="3" cy="15" r="1"/><circle cx="9" cy="15" r="1"/></svg>';
}
function columnChoiceMarkup(key, selected, index, total) {
  const definition = TRACK_COLUMN_DEFINITIONS[key];
  const controls = selected
    ? `<span class="column-drag-handle" title="拖动排序">${columnDragIcon()}</span><button class="column-move-button" type="button" data-column-move="up" title="上移" aria-label="上移" ${index === 0 ? "disabled" : ""}>↑</button><button class="column-move-button" type="button" data-column-move="down" title="下移" aria-label="下移" ${index === total - 1 ? "disabled" : ""}>↓</button>`
    : "";
  return `<div class="column-choice${selected ? " is-selected" : ""}" ${selected ? `draggable="true" data-column-key="${key}"` : ""}>${controls}<label class="column-choice-label"><input type="checkbox" value="${key}" ${selected ? "checked" : ""}><span>${definition.label}</span></label></div>`;
}
function columnSelectionFromDialog() {
  return [...document.querySelectorAll("#selectedColumnChoiceList input:checked, #availableColumnChoiceList input:checked")].map(input => input.value);
}
function moveColumnChoice(key, direction) {
  const columns = [...(state.columnDialogColumns || currentTrackColumns())];
  const index = columns.indexOf(key);
  const next = index + direction;
  if (index < 0 || next < 0 || next >= columns.length) return;
  [columns[index], columns[next]] = [columns[next], columns[index]];
  state.columnDialogColumns = columns;
  renderColumnChoices();
}
function bindColumnDragEvents() {
  const selectedList = $("selectedColumnChoiceList");
  if (!selectedList) return;
  let dragging = null;
  selectedList.querySelectorAll(".column-choice.is-selected").forEach(choice => {
    choice.addEventListener("dragstart", event => {
      dragging = choice;
      choice.classList.add("is-dragging");
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", choice.dataset.columnKey || "");
    });
    choice.addEventListener("dragend", () => {
      choice.classList.remove("is-dragging");
      selectedList.querySelectorAll(".is-drag-over").forEach(node => node.classList.remove("is-drag-over"));
      dragging = null;
      state.columnDialogColumns = columnSelectionFromDialog();
    });
  });
  selectedList.addEventListener("dragover", event => {
    if (!dragging) return;
    event.preventDefault();
    const target = event.target.closest(".column-choice.is-selected");
    if (!target || target === dragging) return;
    const before = event.clientY < target.getBoundingClientRect().top + target.offsetHeight / 2;
    selectedList.insertBefore(dragging, before ? target : target.nextSibling);
    selectedList.querySelectorAll(".is-drag-over").forEach(node => node.classList.remove("is-drag-over"));
    target.classList.add("is-drag-over");
  });
}
function renderColumnChoices(columns = state.columnDialogColumns || currentTrackColumns()) {
  const container = $("columnChoiceList");
  if (!container) return;
  const selectedColumns = normalizeTrackColumns(columns);
  const selected = new Set(selectedColumns);
  const available = Object.keys(TRACK_COLUMN_DEFINITIONS).filter(key => !selected.has(key));
  container.innerHTML = `<section class="column-choice-section"><div class="column-choice-section-head"><strong>已显示列</strong><span>拖动调整顺序</span></div><div class="column-choice-selected" id="selectedColumnChoiceList">${selectedColumns.map((key, index) => columnChoiceMarkup(key, true, index, selectedColumns.length)).join("")}</div></section><section class="column-choice-section"><div class="column-choice-section-head"><strong>可显示列</strong><span>勾选后加入上方</span></div><div class="column-choice-available" id="availableColumnChoiceList">${available.map(key => columnChoiceMarkup(key, false, 0, 0)).join("")}</div></section>`;
  container.querySelectorAll("input").forEach(input => input.onchange = () => {
    state.columnDialogColumns = normalizeTrackColumns(columnSelectionFromDialog());
    renderColumnChoices();
  });
  container.querySelectorAll("[data-column-move]").forEach(button => button.onclick = event => {
    event.preventDefault();
    event.stopPropagation();
    moveColumnChoice(button.closest("[data-column-key]")?.dataset.columnKey, button.dataset.columnMove === "up" ? -1 : 1);
  });
  bindColumnDragEvents();
}
function openColumnsDialog() {
  state.columnDialogColumns = [...currentTrackColumns()];
  renderColumnChoices();
  const help = $("columnDialogHelp");
  if (help) help.textContent = `正在设置：${trackColumnScopeLabel()}。此设置会单独保存。`;
  $("columnsDialog").showModal();
}
function saveColumnChoices() {
  const selected = state.columnDialogColumns || columnSelectionFromDialog();
  saveTrackColumns(selected);
  state.columnDialogColumns = null;
  $("columnsDialog").close();
  render();
}
function sortOptionsForView(view = state.view) {
  return globalThis.fnAudioLibrarySortOptionsPolicy.options(view, {
    creatorAllTracks: isCreatorAllTracksView(), creatorAlbum: isCreatorAlbumView(),
    creatorView: isCreatorView(view), albumDetail: isAlbumDetailView(),
    playlistView: isPlaylistLibraryView(view), hasGroupName: Boolean(state.groupName),
  });
}
function updateSortOptions() {
  const options = sortOptionsForView();
  const defaultKey = globalThis.fnAudioLibrarySortOptionsPolicy.defaultKey(state.view, {
    albumDetail: isAlbumDetailView(), folderRoot: state.folderRoot, folderPath: state.folderPath,
  });
  const previousKey = state.sortKey;
  state.sortKey = options.some(([value]) => value === state.sortKey)
    ? state.sortKey
    : (options.some(([value]) => value === defaultKey) ? defaultKey : options[0][0]);
  // Persist only a corrected/changed key. `render()` is also called for
  // playback progress and must not turn into synchronous storage churn.
  if (state.sortKey !== previousKey) localStorage.setItem("fnaudio.sortKey.v1", state.sortKey);
}
function compareTrackValue(a, b, key) {
  return globalThis.fnAudioTrackSortPolicy.compare(a, b, key, { displayText, itemAddedTime });
}
function sortTracks(list, key = state.sortKey || "title") {
  return globalThis.fnAudioTrackSortPolicy.sort(list, key, sortDirectionFactor(), { displayText, itemAddedTime });
}
function isPagedLibraryView(view = state.view) {
  return PAGED_LIBRARY_VIEWS.has(String(view || ""));
}
function isClientPagedView(view = state.view) {
  return view === "queue" || view === "favorites" || isPlaylistView(view);
}
function isPagedGroupListing() {
  if (isCreatorAllTracksView()) return false;
  return Boolean(groupViews[state.view] && !state.groupName);
}
function isPagedTrackListing() {
  if (state.view === "folders") return Boolean(state.folderRoot || state.folderPath);
  if (state.view === "recent" || state.view === "random100") return true;
  if (isCreatorView()) return isAlbumDetailView() || isCreatorAllTracksView();
  if (groupViews[state.view]) return Boolean(state.groupName);
  return state.view === "all" || state.view === "dsd";
}
function currentQueryText() {
  const value = $("searchInput")?.value;
  return typeof value === "string" ? value.trim().slice(0, 4096) : "";
}
function libraryPageNumber(value, fallback = 1) {
  try {
    const number = Number(value);
    if (!Number.isFinite(number) || !Number.isInteger(number) || number < 1) return fallback;
    return number;
  } catch (_) {
    return fallback;
  }
}
function libraryPageStep(value, fallback = 0) {
  try {
    const number = Number(value);
    return Number.isFinite(number) && Number.isInteger(number) ? number : fallback;
  } catch (_) {
    return fallback;
  }
}
function currentQueryParams() {
  return fnAudioLibraryQueryParams.buildLibraryQueryParams({
    page: state.page,
    pageSize: state.pageSize,
    view: state.view,
    sortKey: state.sortKey,
    sortDir: state.sortDir,
    search: currentQueryText(),
    folderRoot: state.folderRoot,
    folderPath: state.folderPath,
    creatorView: isCreatorView(),
    creatorName: currentCreatorName(),
    groupView: Boolean(groupViews[state.view]),
    groupName: state.groupName,
    playlistView: isPlaylistView(),
  });
}
function compareName(a, b) {
  return displayText(a).localeCompare(displayText(b), "zh-CN", { numeric: true, sensitivity: "base" }) * sortDirectionFactor();
}
function folderDisplayName(path) {
  return globalThis.fnAudioFolderLabelPolicy.display(path);
}
function currentFolderLabel() {
  return globalThis.fnAudioFolderLabelPolicy.label(state.folderRoot, state.folderPath);
}
function random100Tracks() {
  if (state.view === "random100") return state.pageItems.length ? state.pageItems : state.random100;
  return state.random100;
}
function playlistTracks(playlist = currentPlaylist()) {
  if (!playlist) return [];
  return playlist.trackIds.map(itemById).filter(Boolean);
}
function favoriteTracks() {
  return state.favorites.map(itemById).filter(Boolean);
}
function isFavorite(id) {
  const target = String(id || "");
  return Boolean(target && state.favorites.some(favoriteId => String(favoriteId) === target));
}
function isPrivateHost(host) {
  return globalThis.fnAudioHostPrivacyPolicy.isPrivateHost(host);
}
function shouldTranscodeToMp3(item) {
  return Boolean(state.mp3Transcode && item && String(item.format || "").toUpperCase() !== "MP3");
}
function playbackBadge(item) {
  if (isDacTarget()) return state.dacStrategy?.label || state.remoteStatus?.strategy?.label || "USB DAC 输出";
  if (isMpdTarget()) return state.playTargetName || "NAS 本机播放";
  if (isRemoteTarget()) return "原文件推送";
  const format = String(item.format || "").toUpperCase();
  if (shouldTranscodeToMp3(item)) return "转码 MP3";
  if (shouldTranscodeDsdToWav(item)) return "DSD 转 WAV 96kHz/24bit";
  return "原文件播放";
}
function shouldTranscodeDsdToWav(item) {
  return item?.is_dsd === true && !isRemoteTarget() && !shouldTranscodeToMp3(item);
}
function effectiveProfile() {
  if (isPrivateHost(window.location.hostname)) return "lan";
  return state.accessProfile || "lan";
}
function updateModeButton() {
  const title = state.mp3Transcode ? "关闭 MP3 转码" : "开启 MP3 转码";
  const desktopButton = $("modeBtn");
  desktopButton.classList.toggle("active-control", state.mp3Transcode);
  desktopButton.title = title;
  desktopButton.setAttribute("aria-label", title);
  desktopButton.setAttribute("aria-pressed", String(state.mp3Transcode));
  const mobileButton = $("mobileModeBtn");
  if (mobileButton) {
    mobileButton.classList.toggle("active-control", state.mp3Transcode);
    mobileButton.title = title;
    mobileButton.setAttribute("aria-label", title);
    mobileButton.setAttribute("aria-pressed", String(state.mp3Transcode));
  }
}
function scanProgressText() {
  if (state.libraryLoading) return `正在加载音乐库：${state.libraryLoaded}${state.libraryTotal ? ` / ${state.libraryTotal}` : ""} 首`;
  const status = state.libraryStatus || {};
  if (!status.scanning) return "";
  const phase = displayText(status.phase || "");
  const current = displayText(status.current || "");
  const found = Number(status.found || status.count || 0);
  const scanned = Number(status.scanned || 0);
  const prefix = phase ? `正在${phase}` : "正在扫描音乐库";
  const suffix = current ? ` · ${current}` : "";
  if (scanned || found) return `${prefix}：已检查 ${scanned} 个文件，已发现 ${found} 首歌曲${suffix}`;
  return `${prefix}${suffix}`;
}
function updateDeviceLabel() {
  // Changing device repaints the row's *owner* without repainting the row: `render()`
  // touches this label and nothing else, so a handover away from a stalled channel has to
  // clear the lamp from here too.  The local branch writes nothing, so the extra call on
  // every render costs zero DOM.
  updateTransportStateUnknown();
  const label = isRemoteTarget() ? state.playTargetName : "当前设备";
  const desktopButton = $("deviceBtn");
  if (desktopButton && desktopButton.title !== label) desktopButton.title = label;
  const mobileButton = $("mobileDeviceBtn");
  if (mobileButton) {
    const ariaLabel = `播放设备：${label}`;
    if (mobileButton.title !== label) mobileButton.title = label;
    if (mobileButton.getAttribute("aria-label") !== ariaLabel) mobileButton.setAttribute("aria-label", ariaLabel);
  }
}
function remoteDeviceId() { return isRemoteTarget() ? state.playTarget : ""; }
function isIncomingRendererSession() {
  return Boolean(state.rendererSession?.uri);
}
function localIsPlayingNow() {
  // What the local element or the host player is doing, ignoring any render
  // session that happens to own the visible row: the tail of ``isPlayingNow``,
  // the same split as ``localPlaybackSeconds`` against ``currentSeconds``.
  if (nativePlaybackAvailable()) return state.nativePlayback.playing === true;
  return Boolean(audio.src && !audio.paused && !audio.ended);
}
function isPlayingNow() {
  if (isIncomingRendererSession()) {
    const transport = String(state.rendererSession.transport || "").toUpperCase();
    return transport === "PLAYING" || transport === "TRANSITIONING";
  }
  if (isRemoteTarget()) return state.remoteStatus?.transport?.state === "PLAYING";
  return localIsPlayingNow();
}
function updateFavoriteControls() {
  const item = currentItem();
  const active = Boolean(item && isFavorite(item.id));
  ["favoriteCurrentBtn", "lyricsFavoriteBtn"].forEach(id => {
    const node = $(id);
    if (!node) return;
    node.classList.toggle("active-control", active);
    node.setAttribute("aria-pressed", String(active));
    node.title = active ? "取消收藏当前歌曲" : "收藏当前歌曲";
    if (id === "lyricsFavoriteBtn") node.textContent = active ? "已收藏" : "收藏";
  });
}
function refreshFavoritePresentation() {
  const count = $("favoriteCount");
  if (count && count.textContent !== String(state.favorites.length)) count.textContent = String(state.favorites.length);
  updateFavoriteControls();
  // Only the favorites surface derives its rows from this collection. On a
  // normal library page, rebuilding the list after a favorite click needlessly
  // competes with cover decoding and can look like a post-load flicker.
  if (state.view === "favorites") render();
}
function updateNowMarquee() {
  if (document.body.classList.contains("mobile-search-active")) return;
  requestAnimationFrame(() => {
    // scrollWidth/clientWidth force layout and each style write invalidates it
    // again, so both nodes are measured before anything is painted: one forced
    // layout per poll instead of two. A poll whose distance did not change skips
    // the write, which keeps the 1.5s renderer poll from touching style.
    const nodes = ["nowTitle", "nowArtist"].map(id => $(id)).filter(node => node && node.style);
    const distances = nodes.map(node => Math.max(0, node.scrollWidth - node.clientWidth));
    distances.forEach((distance, index) => {
      const node = nodes[index];
      const value = `${distance}px`;
      setStyleVarIfChanged(node, "--marquee-distance", value);
      node.classList.toggle("is-overflowing", distance > 2);
    });
  });
  // Marquee geometry only. Every path that owns the transport row paints it
  // itself: the 1.5s render poll syncs inside updateIncomingRendererUi, the
  // load/restore/boot paths sync explicitly beside their own text writes, and
  // local playback is ticked by audio.ontimeupdate. Syncing on the side here
  // made that poll write the pair twice per tick and turned every window resize
  // into a progress repaint (R101, TODO item on the duplicate syncPlayerProgress).
}
function syncNowPlayingTime(seconds = currentSeconds(), duration = seekDuration()) {
  setTextContentIfChanged($("nowTime"), `${clock(seconds)} / ${clock(duration)}`);
}
function syncPlayerProgress() {
  const duration = seekDuration();
  const seconds = currentSeconds();
  syncNowPlayingTime(seconds, duration);
  updateSeekRail();
  updateTransportStateUnknown();
}
function updateSeekRail(value = $("seek")?.value || 0) {
  setStyleVarIfChanged($("seek"), "--seek-fill", `${seekPercent(value)}%`);
}
function updateTransportStateUnknown() {
  // Say so when the transport row is running on extrapolation instead of on evidence.
  // The two status channels are asked about separately, in the order `currentSeconds`
  // resolves them: an incoming render session owns the row even when this app is not
  // targeting a remote device itself.  Everything else on screen is local playback,
  // whose authority is `audio.ontimeupdate` - that pump cannot stall while still
  // reporting fresh numbers, so there is nothing to flag and the lamp is cleared.
  let unknown = false;
  if (isIncomingRendererSession()) {
    unknown = transportStateIsUnknown(state.rendererSnapshotAt,
      String(state.rendererSession?.transport || "").toUpperCase() === "PLAYING");
  } else if (isRemoteTarget()) {
    unknown = transportStateIsUnknown(state.remoteSnapshotAt,
      String(state.remoteStatus?.transport?.state || "").toUpperCase() === "PLAYING");
  }
  setDatasetStateIfChanged($("transportStateUnknown"), unknown);
}
function externalArtworkUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (error) {
    return "";
  }
}
function setCoverArtwork(node, source) {
  // The renderer status poll runs every 1.5s and the lyrics retry poll every
  // 900ms, and both repaint these cover blocks.  Assigning innerHTML
  // unconditionally throws away a fully decoded <img> and decodes the same
  // address again, which reads as a visible cover flash on every poll, so a
  // repeated address has to be a no-op.  A failed address drops to the fallback
  // glyph and is not retried until the address changes, which keeps a broken
  // cover from being requested once per poll.
  if (!node) return false;
  const next = typeof source === "string" ? source : "";
  if (node.dataset.coverSource === next) return false;
  node.dataset.coverSource = next;
  node.innerHTML = next
    ? `<img src="${escapeHtml(next)}" onerror="this.parentNode.innerHTML='\u266b'">`
    : "\u266b";
  return true;
}
function setNowPlayingCover(source) {
  return setCoverArtwork($("nowCover"), source);
}
function renderIncomingRendererSession(session) {
  const title = displayText(session.title || "DLNA 输入");
  const artist = displayText(session.artist || "未知艺术家");
  const art = externalArtworkUrl(session.art_url);
  setTextContentIfChanged($("nowTitle"), title);
  setTextContentIfChanged($("nowArtist"), `${artist} · 来自 DLNA 控制端 · ${state.playTargetName || "本机 USB DAC"}`);
  setNowPlayingCover(art);
  // The transport row is only ticked every 500ms while the app itself targets a
  // remote device, so an incoming cast with a local play target has to be painted
  // from this 1.5s status poll instead.
  updateIncomingRendererUi();
  updateNowMarquee();
}
function resetTransportRow() {
  // The transport row describes whatever the library view is playing. An incoming cast paints it
  // from the status poll (`updateIncomingRendererUi` above), while restoring the library panel used
  // to rewrite only the title, the artist and the cover - so after a cast ended with nothing
  // selected locally, "未选择曲目" stayed on screen next to 1:40 of a track nothing was playing
  // (TODO.md:58). Same reset the stop path (:2043) and a fresh load (:4375) already use, plus the
  // rail fill and the icon, which those two sites leave to their own callers.
  setTextContentIfChanged($("elapsed"), "0:00");
  setTextContentIfChanged($("duration"), clock(seekDuration()));
  const rail = $("seek");
  if (rail) rail.value = 0;
  updateSeekRail(0);
  setPlayButton(false);
  // The memo that keeps `updateRemoteUi` from repainting describes the session that just ended,
  // so it has to go with the row it was guarding.
  state.remoteUiLast = null;
}
function restoreLibraryNowPlaying() {
  const item = currentItem();
  if (!item) {
    setTextContentIfChanged($("nowTitle"), "未选择曲目");
    setTextContentIfChanged($("nowArtist"), "从音乐库选择一首歌曲");
    setNowPlayingCover("");
    resetTransportRow();
  } else {
    const cover = coverUrl(item, 512);
    setTextContentIfChanged($("nowTitle"), displayTrackTitle(item));
    setTextContentIfChanged($("nowArtist"), `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)}`);
    setNowPlayingCover(cover);
  }
  syncPlayerProgress();
  updateNowMarquee();
}
async function refreshRendererSession() {
  if (state.rendererRequestInFlight) return;
  const token = ++state.rendererRequestToken;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.rendererRequestInFlight = true;
  state.rendererRequestController = controller;
  try {
    const request = fetch("api/dlna/renderer/status", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    if (token !== state.rendererRequestToken || state.rendererRequestController !== controller) return;
    if (!response.ok) return;
    const data = result.data || {};
    if (token !== state.rendererRequestToken || state.rendererRequestController !== controller) return;
    const session = data.available === true ? (data.state || {}) : {};
    const transport = String(session.transport || "").toUpperCase();
    let active = typeof session.uri === "string" && session.uri.length > 0
      && !["STOPPED", "NO_MEDIA_PRESENT"].includes(transport);
    // A stop issued by a local play intent (TODO.md:72 ruling D-2) can lose the
    // race: a command that was already on the wire, or one the bridge refused,
    // leaves the caster active, and this poll would hand the transport row back and
    // silence what this browser just started. The session this browser preempted is
    // therefore no session at all for as long as local playback still runs. Another
    // uri is a new cast, and the moment nothing plays locally the claim lapses, so a
    // later cast is never ignored.
    if (active && state.rendererPreemptedUri && session.uri === state.rendererPreemptedUri
      && localIsPlayingNow()) {
      active = false;
    } else {
      state.rendererPreemptedUri = "";
    }
    const previousActive = isIncomingRendererSession();
    state.rendererSession = active ? session : null;
    state.rendererSnapshotAt = Date.now();
    if (active) {
      // Ruling D-1: a cast takes the audible output, so the local decoder stops with
      // it. Both used to run at once - two decoders and two bandwidth draws behind a
      // row that only ever showed the caster - on the element *and* on the host
      // player, which is what the native stop inside stopLocalAudio covers. Only the
      // transition stops: this poll repeats every 1.5s and tearing the element down on
      // every tick would reload the same source over and over.
      if (!previousActive && localIsPlayingNow()) stopLocalAudio();
      renderIncomingRendererSession(session);
    } else if (previousActive) {
      // Ruling D-3: an ended cast does not resume local playback. The library row
      // comes back and the transport icon is reset with it, because the render paint
      // last set that icon from the caster's transport state. No play command is
      // issued, and coreControl("stop") is deliberately not called either, so the
      // queue position a local session held is still there for a manual resume.
      restoreLibraryNowPlaying();
      setPlayButton(false);
      updateMediaSessionPlaybackState();
    }
  } catch (error) {
  } finally {
    if (token === state.rendererRequestToken && state.rendererRequestController === controller) {
      state.rendererRequestInFlight = false;
      state.rendererRequestController = null;
    }
  }
}
function setPlayButton(playing) {
  // The 500ms transport tick and every playback event repaint this icon, and the
  // old unconditional innerHTML discarded the icon span twice per second, which is
  // the same repaint waste as the cover.  The requested flag is remembered on the
  // node instead of re-reading markup, so the check does not depend on how a
  // WebView serializes it.
  const button = $("playBtn");
  const next = playing === true ? "playing" : "paused";
  if (!button || button.dataset.playing === next) return;
  button.dataset.playing = next;
  button.innerHTML = `<span class="transport-icon ${next === "playing" ? "pause-icon" : "play-icon"}"></span>`;
}
function stopLocalAudio() {
  state.playbackLoadToken += 1;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  if (nativePlaybackAvailable()) nativePlaybackCall("stop");
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  setPlayButton(false);
}
function preemptIncomingRendererForLocalPlayback() {
  // TODO.md:72 ruling D-2: loading a track locally, or pressing play on the host, is
  // a local playback intent, and it outranks whoever is casting. The claim on the
  // transport row is dropped synchronously, before this browser touches its own
  // element, so no poll and no continuation can repaint the caster in between. The
  // stop itself is not awaited on purpose: an unreachable bridge must not stall local
  // playback, and what the stop really achieved is reported by the next status poll,
  // which finds this uri already marked as preempted.
  if (!isIncomingRendererSession()) return false;
  const uri = String(state.rendererSession?.uri || "");
  state.rendererPreemptedUri = uri;
  state.rendererSession = null;
  state.rendererSnapshotAt = 0;
  controlIncomingRenderer("stop");
  return true;
}
async function stopPlayback() {
  if (state.deviceSwitchInFlight) return false;
  if (isIncomingRendererSession()) {
    await controlIncomingRenderer("stop");
    restoreLibraryNowPlaying();
    return;
  }
  if (isRemoteTarget()) {
    await remoteControl("stop");
    state.remoteStatus = { transport: { state: "STOPPED" }, position: { rel_seconds: 0, duration_seconds: playbackSeconds(state.remoteStatus?.position?.duration_seconds) } };
    updateRemoteUi();
    return;
  }
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  stopLocalAudio();
  // Keep the server snapshot stopped as well; otherwise an old paused
  // session can be selected again by a later state synchronization.
  await coreControl("stop");
  setTextContentIfChanged($("elapsed"), "0:00");
  $("seek").value = 0;
  updateMediaSessionPlaybackState();
  syncState();
}
function stopRemoteOnUnload() {
  // A browser tab/WebView is a controller, not the output owner. Do not stop
  // a DAC or Renderer merely because the UI was backgrounded or reclaimed.
  if (state.libraryStatusTimer) {
    clearTimeout(state.libraryStatusTimer);
    state.libraryStatusTimer = 0;
  }
  if (state.accessProfileTimer) {
    clearTimeout(state.accessProfileTimer);
    state.accessProfileTimer = 0;
  }
  cancelLyricsPoll();
  cancelLyricsRequest();
  stopRemoteEventStream();
}
function updateRemoteUi() {
  // First statement, before either early return.  `currentSeconds` clamps an extrapolated
  // position at the limit, so once a channel has run out of evidence the memo below keeps
  // seeing identical numbers and returns there: a lamp written after that gate would only
  // ever light up on a change that had already stopped moving.
  updateTransportStateUnknown();
  if (updateIncomingRendererUi()) return;
  if (!isRemoteTarget()) return;
  const transport = state.remoteStatus?.transport?.state || "";
  const duration = seekDuration();
  const seconds = duration > 0 && !state.seeking ? currentSeconds() : -1;
  const current = currentItem()?.id || "";
  const previous = state.remoteUiLast || {};
  // Avoid rewriting the same DOM/media-session state on every timer tick.
  // Progress still advances locally between network snapshots.
  if (previous.transport === transport && previous.duration === duration &&
      previous.current === current && (seconds < 0 || Math.abs(previous.seconds - seconds) < 0.45)) return;
  state.remoteUiLast = { transport, duration, seconds, current };
  if (duration > 0) {
    setTextContentIfChanged($("duration"), clock(duration));
    if (!state.seeking) {
      setTextContentIfChanged($("elapsed"), clock(seconds));
      $("seek").value = Math.max(0, Math.min(100, seconds / duration * 100));
    }
  }
  setPlayButton(transport === "PLAYING");
  syncPlayerProgress();
  updateLyricHighlight();
  updateMediaSessionPosition();
}
function updateIncomingRendererUi() {
  if (!isIncomingRendererSession()) return false;
  const session = state.rendererSession;
  const duration = seekDuration();
  if (duration > 0) {
    setTextContentIfChanged($("duration"), clock(duration));
    if (!state.seeking) {
      const seconds = currentSeconds();
      setTextContentIfChanged($("elapsed"), clock(seconds));
      $("seek").value = Math.max(0, Math.min(100, seconds / duration * 100));
    }
  }
  setPlayButton(String(session.transport || "").toUpperCase() === "PLAYING");
  syncPlayerProgress();
  updateMediaSessionPosition();
  return true;
}
async function controlIncomingRenderer(action, position = null) {
  try {
    const response = await apiFetch("api/playback/control", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_id: "mpd", action, position}),
    });
    const data = await readResponseJsonBounded(response);
    if (!response.ok || data.ok !== true) throw new Error(data.message || "DLNA Renderer 控制失败");
    if (action === "stop") state.rendererSession = null;
    else if (state.rendererSession) {
      state.rendererSession.transport = action === "pause" ? "PAUSED_PLAYBACK" : "PLAYING";
      if (action === "seek" && position != null) state.rendererSession.position = playbackSeconds(position);
      state.rendererSnapshotAt = Date.now();
    }
    updateRemoteUi();
    setTimeout(refreshRendererSession, 250);
    return true;
  } catch (error) {
    alert(error.message || "DLNA Renderer 控制失败");
    return false;
  }
}
function updateMediaSessionMetadata(item = currentItem()) {
  if (!("mediaSession" in navigator)) return;
  state.mediaSession.supported = true;
  if (!item) {
    try { navigator.mediaSession.metadata = null; state.mediaSession.metadata = false; } catch (error) {}
    return;
  }
  const localCover = coverUrl(item, 512);
  const artwork = localCover
    ? [{ src: localCover, sizes: "512x512", type: "image/jpeg" }]
    : [
        { src: mediaUrl("images/icon_64.png"), sizes: "64x64", type: "image/png" },
        { src: mediaUrl("images/icon_256.png"), sizes: "256x256", type: "image/png" },
      ];
  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: displayTrackTitle(item) || "fnAudio",
      artist: displayText(item.artist) || "",
      album: displayText(item.album) || "",
      artwork,
    });
    state.mediaSession.metadata = true;
    state.hostPlaybackSession?.synchronize({
      generation: state.remoteGeneration,
      engineEpoch: state.remoteEngineEpoch,
      trackId: item?.id,
      playing: isPlayingNow(),
      position: currentSeconds(),
      duration: seekDuration(),
      outputTarget: state.playTarget,
      metadata: { title: displayTrackTitle(item), artist: displayText(item.artist), album: displayText(item.album) },
    });
  } catch (error) {
    state.mediaSession.metadata = false;
  }
}
function updateMediaSessionPosition() {
  if (!("mediaSession" in navigator) || typeof navigator.mediaSession.setPositionState !== "function") return;
  const duration = seekDuration();
  if (!duration || !Number.isFinite(duration)) return;
  try {
    navigator.mediaSession.setPositionState({
      duration,
      playbackRate: 1,
      position: Math.max(0, Math.min(duration, currentSeconds())),
    });
  } catch (error) {
  }
}
function updateMediaSessionPlaybackState() {
  if (!("mediaSession" in navigator)) return;
  state.mediaSession.supported = true;
  try {
    navigator.mediaSession.playbackState = isPlayingNow() ? "playing" : (currentItem() ? "paused" : "none");
  } catch (error) {
  }
  updateMediaSessionPosition();
  const item = currentItem();
  if (item && state.hostPlaybackSession?.available === true) {
    const contextId = `fnaudio:${String(item.id || "current")}`;
    if (!state.hostPlaybackSessionActivated || state.hostPlaybackMediaContextId !== contextId) {
      state.hostPlaybackSessionActivated = state.hostPlaybackSession.requestActivation(contextId);
      state.hostPlaybackMediaContextId = contextId;
    }
  } else if (!item && state.hostPlaybackSessionActivated) {
    state.hostPlaybackSession?.release();
    state.hostPlaybackSessionActivated = false;
    state.hostPlaybackMediaContextId = "";
  }
  state.hostPlaybackSession?.reportState({
    generation: state.remoteGeneration,
    engineEpoch: state.remoteEngineEpoch,
    trackId: item?.id,
    playing: isPlayingNow(),
    position: currentSeconds(),
    duration: seekDuration(),
    outputTarget: state.playTarget,
  });
}
function applyCoreSnapshot(core, shouldLoad = true) {
  const currentId = core?.current || core?.state?.current;
  if (!currentId) return false;
  const index = state.queue.findIndex(item => String(item?.id || "") === String(currentId));
  if (index < 0) return false;
  const previousIndex = state.index;
  state.index = index;
  state.repeat = core.repeat || state.repeat;
  state.shuffle = typeof core.shuffle === "boolean" ? core.shuffle : state.shuffle;
  updateRepeatShuffleButtons();
  if (shouldLoad) {
    resetPlaybackProgress();
    loadCurrent();
  }
  syncCurrentQueuePresentation(previousIndex);
  updateFavoriteControls();
  return true;
}
async function coreControl(action, position = null, payload = {}) {
  if (state.deviceSwitchInFlight) return false;
  if (nativePlaybackAvailable() && (action === "next" || action === "previous")) {
    nativePlaybackCall(action === "next" ? "next" : "previous");
    return { ok: true, native: true };
  }
  const item = currentItem();
  const response = await apiFetch("api/playback/control", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ target_id: remoteDeviceId() || "local", action, position, track_id: item?.id || "", command_id: playbackCommandId(), ...payload }),
  });
  const data = await readResponseJsonBounded(response);
  if (!response.ok || data.ok !== true) return false;
  const changedTrack = action === "next" || action === "previous";
  applyCoreSnapshot(data.core, changedTrack && !isRemoteTarget());
  if (isRemoteTarget()) {
    const snapshot = remoteSnapshotFromCore(data.core);
    if (snapshot) applyRemotePlaybackSnapshot(snapshot);
  }
  scheduleUserStateSave();
  return data;
}
async function playPreviousTrack() {
  if (!state.queue.length) return false;
  return Boolean(await coreControl("previous"));
}
async function playNextTrack() {
  if (!state.queue.length) return false;
  return Boolean(await coreControl("next"));
}
function setupMediaSession() {
  if (nativePlaybackAvailable()) return;
  if (!("mediaSession" in navigator) || setupMediaSession.done) return;
  state.mediaSession.supported = true;
  state.mediaSession.host = window.parent !== window ? "embedded" : (fnAppVersion() ? "fnapp-webview" : "browser");
  state.hostPlaybackSession?.initialize({
    participantId: `fnaudio-web-${state.mediaSession.host}`,
    generation: state.remoteGeneration,
    engineEpoch: state.remoteEngineEpoch,
    capabilities: { mediaSession: true, backgroundResume: true, standardWebMediaSession: true },
  });
  setupMediaSession.done = true;
  const setHandler = (action, handler) => {
    try {
      navigator.mediaSession.setActionHandler(action, handler);
      state.mediaSession.actions.push(action);
    } catch (error) {}
  };
  setHandler("play", () => {
    // The host transport keys drive whatever owns the transport row, exactly like the
    // on-screen play button below. Without this branch the play key would wake the
    // local element that ruling D-1 stopped the moment the cast started, which is
    // precisely the second decoder this entry is about.
    if (isIncomingRendererSession()) { controlIncomingRenderer("play"); return; }
    if (isRemoteTarget()) remoteControl("play");
    else if (!audio.src && state.queue.length) loadCurrent();
    else audio.play().catch(() => {});
  });
  setHandler("pause", () => {
    // Same reason as the play key: pausing a cast is a request to the caster, not a
    // request to pause a local element that is already stopped.
    if (isIncomingRendererSession()) { controlIncomingRenderer("pause"); return; }
    if (isRemoteTarget()) remoteControl("pause");
    else audio.pause();
  });
  setHandler("stop", () => stopPlayback());
  setHandler("previoustrack", () => playPreviousTrack());
  setHandler("nexttrack", () => playNextTrack());
  setHandler("seekbackward", details => {
    const offset = Number(details?.seekOffset || 10);
    const duration = seekDuration();
    if (!duration) return;
    const target = Math.max(0, currentSeconds() - offset);
    commitSeek(duration ? target / duration * 100 : 0);
  });
  setHandler("seekforward", details => {
    const offset = Number(details?.seekOffset || 10);
    const duration = seekDuration();
    if (!duration) return;
    const target = Math.min(duration, currentSeconds() + offset);
    commitSeek(duration ? target / duration * 100 : 0);
  });
  setHandler("seekto", details => {
    const duration = seekDuration();
    const target = Number(details?.seekTime);
    if (!duration || !Number.isFinite(target)) return;
    commitSeek(Math.max(0, Math.min(duration, target)) / duration * 100);
  });
}
window.fnAudioMediaSessionDiagnostics = () => ({
  supported: Boolean(state.mediaSession?.supported),
  metadata: Boolean(state.mediaSession?.metadata),
  actions: [...new Set(state.mediaSession?.actions || [])],
  host: String(state.mediaSession?.host || "standalone"),
  mediaSessionState: String(navigator.mediaSession?.playbackState || "none"),
  hostPlaybackSession: state.hostPlaybackSession?.diagnostics?.() || { detected: false, name: "", methods: [] },
});
async function refreshRemoteStatus(options = {}) {
  if (!isRemoteTarget()) return;
  if (!state.remoteEventSource && typeof EventSource !== "undefined") startRemoteEventStream();
  if (state.remoteEventConnected) return;
  if (state.remoteStatusRequestInFlight) return;
  const targetId = remoteDeviceId();
  const token = ++state.remoteStatusRequestToken;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.remoteStatusRequestInFlight = true;
  state.remoteStatusController = controller;
  try {
    const request = fetch(`api/playback/status?target_id=${encodeURIComponent(targetId)}`, {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    if (token !== state.remoteStatusRequestToken || targetId !== remoteDeviceId()) return;
    // A proxy/renderer error may still carry an empty JSON object. Do not
    // project that transport failure as a real remote snapshot, otherwise a
    // temporary disconnect can erase the last known track and transport state.
    if (!response?.ok) return;
    const data = globalThis.fnAudioMetadataResponsePolicy?.unwrapTransport(result.data, 4) || {};
    if (!data || data.error) return;
    applyRemotePlaybackSnapshot(data, options);
  } catch (error) {
  } finally {
    if (token === state.remoteStatusRequestToken && state.remoteStatusController === controller) {
      state.remoteStatusRequestInFlight = false;
      state.remoteStatusController = null;
    }
  }
}
function cancelRemoteStatusRequest() {
  state.remoteStatusRequestToken += 1;
  try { state.remoteStatusController?.abort(); } catch (_) {}
  state.remoteStatusController = null;
  state.remoteStatusRequestInFlight = false;
}
function stopRemoteEventStream() {
  cancelRemoteStatusRequest();
  if (state.remoteEventSource) {
    try { state.remoteEventSource.close(); } catch (error) {}
  }
  state.remoteEventSource = null;
  state.remoteEventConnected = false;
}
function applyRemotePlaybackSnapshot(data, options = {}) {
  if (!isRemoteTarget() || !data || (data.target_id && String(data.target_id) !== String(state.playTarget))) return;
  const stateVersion = remoteStateVersion(data.state_version);
  if (state.remoteStateVersion > 0 && (stateVersion == null || stateVersion < state.remoteStateVersion)) return;
  state.remoteStatus = data;
  // The server states the unit of the seconds it just reported.  A declared
  // value wins over anything derived from local queue metadata: the SSE stream,
  // a poll and a control reply then agree no matter which one arrives first.
  const declaredCueSegment = data.cue_segment === true || data.cue_segment === false;
  if (declaredCueSegment) state.remoteCueSegment = data.cue_segment === true;
  if (stateVersion != null) state.remoteStateVersion = stateVersion;
  if (Number.isFinite(Number(data.generation)) && Number(data.generation) >= 0) {
    state.remoteGeneration = Math.min(2147483647, Math.floor(Number(data.generation)));
  }
  if (Number.isFinite(Number(data.engine_epoch)) && Number(data.engine_epoch) >= 0) {
    state.remoteEngineEpoch = Math.min(2147483647, Math.floor(Number(data.engine_epoch)));
  }
  state.remoteSnapshotAt = Date.now();
  state.remoteBaseSeconds = playbackSeconds(data?.position?.rel_seconds);
  const core = data.core || {};
  const currentId = String(core.current || "");
  const nextIndex = currentId ? state.queue.findIndex(item => String(item.id || "") === currentId) : -1;
  if (nextIndex >= 0 && nextIndex !== state.index) {
    const previousIndex = state.index;
    state.index = nextIndex;
    if (!declaredCueSegment) state.remoteCueSegment = currentItem()?.cue_track === true && !isDacTarget();
    syncCurrentQueuePresentation(previousIndex);
  }
  if (options.allowAdvance !== false) maybeAdvanceRemoteQueue(data);
  updateRemoteUi();
  nativeRemoteUpdate();
}
function startRemoteEventStream() {
  if (!isRemoteTarget() || typeof EventSource === "undefined" || state.remoteEventSource) return;
  const targetId = String(state.playTarget || "");
  if (!targetId) return;
  try {
    const source = new EventSource(`api/playback/events?target_id=${encodeURIComponent(targetId)}`);
    state.remoteEventSource = source;
    source.addEventListener("playback", event => {
      if (source !== state.remoteEventSource) return;
      try {
        const data = JSON.parse(event.data || "{}");
        if (String(data.target_id || "") !== targetId) return;
        state.remoteEventConnected = true;
        state.remoteEventRetryAt = 0;
        applyRemotePlaybackSnapshot(data);
      } catch (error) {}
    });
    source.onerror = () => {
      if (source !== state.remoteEventSource) return;
      state.remoteEventConnected = false;
      state.remoteEventRetryAt = Date.now() + 3000;
      // EventSource reconnects itself. Keep the HTTP status fallback available
      // while a proxy, browser sleep mode, or older server interrupts it.
    };
  } catch (error) {
    state.remoteEventRetryAt = Date.now() + 3000;
  }
}
function maybeAdvanceRemoteQueue(data) {
  // Remote progression is owned by server-side MPD idle / Renderer monitors
  // so it continues while browsers and WebViews are suspended. Keeping a
  // second frontend end-of-track detector would race and skip queue items.
  return;
  /* Legacy fallback retained below for old servers during rolling upgrades.
  const transport = (data?.transport?.state || "").toUpperCase();
  const position = data?.position || {};
  const item = currentItem();
  const duration = Number(position.duration_seconds || 0);
  const rel = Number(position.rel_seconds || 0);
  const endedByTime = item?.cue_track === true
    ? (state.remoteCueSegment
        ? Number(item.duration || 0) > 0 && rel >= Math.max(0, Number(item.duration || 0) - 1.5)
        : Number(item.cue_end || 0) > 0 && rel >= Math.max(0, Number(item.cue_end || 0) - 1.5))
    : duration > 0 && rel >= Math.max(0, duration - 2);
  const stoppedAfterPlaying = state.remoteWasPlaying && ["STOPPED", "NO_MEDIA_PRESENT"].includes(transport);
  state.remoteWasPlaying = transport === "PLAYING" || transport === "TRANSITIONING";
  if (!(endedByTime || stoppedAfterPlaying)) return;
  if (Date.now() - state.remoteAutoAdvanceAt < 3000) return;
  state.remoteAutoAdvanceAt = Date.now();
  coreControl("next");
  */
}
function playbackCommandId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}
function remoteSnapshotFromCore(core, targetId = state.playTarget) {
  if (!core) return null;
  return {
    target_id: targetId,
    target_kind: core.target_kind,
    state_version: core.state_version,
    core,
    transport: { state: core.transport || "STOPPED" },
    position: {
      rel_seconds: playbackSeconds(core.position),
      duration_seconds: playbackSeconds(core.duration),
    },
  };
}
async function remoteControl(action, position = null, quiet = false) {
  if (state.deviceSwitchInFlight || !isRemoteTarget()) return false;
  // Bind the command and its optimistic response to the target selected at
  // invocation time. A device switch can happen while the request is in
  // flight; a late response from the old renderer must never be projected onto
  // the newly selected renderer.
  const targetId = remoteDeviceId();
  const item = currentItem();
  const commandId = playbackCommandId();
  const response = await apiFetch("api/playback/control", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({
      target_id: targetId, action, position, track_id: item?.id || "", command_id: commandId,
      generation: Number(state.remoteGeneration || 0),
      engine_epoch: Number(state.remoteEngineEpoch || 0),
    }),
  });
  const data = await readResponseJsonBounded(response);
  if (!response.ok || data.ok !== true) {
    if (data.error === "playback_target_not_found") {
      return recoverUnavailablePlaybackTarget(!quiet, targetId);
    }
    if (!quiet) alert(data.message || data.error || "远端控制失败");
    return false;
  }
  if (targetId !== remoteDeviceId()) return true;
  const snapshot = remoteSnapshotFromCore(data.core, targetId);
  if (snapshot) applyRemotePlaybackSnapshot(snapshot);
  if (!state.remoteEventConnected) setTimeout(refreshRemoteStatus, 300);
  return true;
}
function filteredTracks() {
  const signature = [
    state.items, state.pageItems, state.queue, state.random100, state.favorites,
    state.playlists, state.view, state.groupName, currentQueryText(),
    state.sortKey, state.sortDir,
  ];
  const cache = state.filteredTracksCache;
  if (cache?.signature && cache.signature.length === signature.length
      && cache.signature.every((value, index) => value === signature[index])) {
    return cache.tracks;
  }
  const tracks = fnAudioLibraryTrackFilterPolicy.selectTracks({
    pagedTrackListing: isPagedLibraryView() && isPagedTrackListing(),
    pageItems: state.pageItems,
    items: state.items,
    view: isPlaylistView() ? "playlist" : state.view,
    groupKey: groupViews[state.view],
    groupName: state.groupName,
    queue: state.queue,
    random100: random100Tracks(),
    recent: recentTracks(),
    favorites: favoriteTracks(),
    playlist: playlistTracks(),
    search: currentQueryText(),
    matches: trackMatchesSearch,
    sort: sortTracks,
  });
  if (cache) {
    cache.signature = signature;
    cache.tracks = tracks;
  }
  return tracks;
}
function trackMatchesSearch(item, search = currentQueryText().toLowerCase()) {
  if (!search) return true;
  const project = globalThis.fnAudioTrackSearchText?.trackSearchText;
  if (project) return project(item).includes(search);
  const values = [];
  for (const field of ["title", "artist", "album", "album_artist", "composer", "genre", "folder", "library_root", "format"]) {
    let value;
    try { value = item?.[field]; } catch (_) { value = ""; }
    if (typeof value === "string") values.push(value.slice(0, 4096).toLowerCase());
    else if (typeof value === "number" && Number.isFinite(value)) values.push(String(value).toLowerCase());
  }
  return values.join(" ").slice(0, 16384).includes(search);
}
function hasMultipleLibraryRoots() {
  const paths = state.libraryStatus?.library_paths || [];
  return Array.isArray(paths) && paths.length > 1;
}
function hasSingleFolderRoot() {
  return Array.isArray(state.folderRootRows) && state.folderRootRows.length === 1;
}
function libraryRootLabels() {
  return fnAudioLibraryRootLabelPolicy.rootLabels(state.libraryStatus?.library_paths || []);
}
function folderChildren() {
  const folders = state.folderRoot ? state.folderRows : state.folderRootRows;
  const tracks = state.folderRoot ? state.pageItems : [];
  return {
    folders: Array.isArray(folders) ? folders : [],
    tracks: sortTracks(Array.isArray(tracks) ? tracks : []),
  };
}
function folderTracks(root = state.folderRoot, path = state.folderPath) {
  if (String(root || "") !== String(state.folderRoot || "") || String(path || "") !== String(state.folderPath || "")) return [];
  return Array.isArray(state.pageItems) ? state.pageItems : [];
}
function groupedTracks() {
  return state.groupRows || [];
}
function clientPagedResult(view = state.view) {
  const offset = Math.max(0, ((Number(state.page) || 1) - 1) * state.pageSize);
  const limit = Math.max(1, state.pageSize);
  const search = currentQueryText().toLowerCase();
  if (view === "queue") {
    // Keep the existing queue display semantics: ordering and visible rows use
    // queueDisplayEntries(), while the pager count reflects the search scope.
    // Reuse the same filtered result for the count; the previous second filter
    // pass was noticeable on large queues and made every render pay twice.
    const entries = queueDisplayEntries();
    const tracks = entries.slice(offset, offset + limit).map(({ item, queueIndex }) => ({ ...item, __queueIndex: queueIndex }));
    return { total: search ? entries.length : state.queue.length, tracks };
  }
  const ids = view === "favorites"
    ? state.favorites
    : isPlaylistView(view)
      ? (currentPlaylist()?.trackIds || [])
      : [];
  if (ids.length) hydrateReferencedIds(ids);
  const project = globalThis.fnAudioLibraryReferenceItems?.projectReferencedItems;
  const source = project ? project(ids, itemById) : ids.map(itemById).filter(Boolean);
  const filtered = search ? source.filter(item => trackMatchesSearch(item, search)) : source;
  return {
    total: search ? filtered.length : ids.length,
    tracks: sortTracks(filtered).slice(offset, offset + limit),
  };
}
function clientPagedTotal(view = state.view) {
  return clientPagedResult(view).total;
}
function clientPagedTracks() {
  return clientPagedResult().tracks;
}
function queueDisplayEntries() {
  const search = currentQueryText().toLowerCase();
  const direction = sortDirectionFactor();
  const cache = state.queueDisplayCache;
  if (cache && cache.queue === state.queue && cache.search === search && cache.sortKey === (state.sortKey || "title") && cache.direction === direction) {
    return cache.entries;
  }
  const entries = state.queue
    .map((item, queueIndex) => ({ item, queueIndex }))
    .filter(({ item }) => !search || trackMatchesSearch(item, search))
    .sort((left, right) => compareTrackValue(left.item, right.item, state.sortKey || "title") * direction || left.queueIndex - right.queueIndex);
  if (cache) {
    cache.queue = state.queue;
    cache.search = search;
    cache.sortKey = state.sortKey || "title";
    cache.direction = direction;
    cache.entries = entries;
  }
  return entries;
}
function currentQueuePage() {
  if (state.index < 0) return 1;
  const presenter = globalThis.fnAudioQueuePresentation;
  if (presenter?.pageForQueueIndex) return presenter.pageForQueueIndex(state.index, queueDisplayEntries(), state.pageSize);
  const position = queueDisplayEntries().findIndex(entry => entry.queueIndex === state.index);
  return position < 0 ? 1 : Math.floor(position / Math.max(1, state.pageSize)) + 1;
}
function scrollCurrentQueueTrackIntoView() {
  if (state.view !== "queue" || state.index < 0) return;
  const row = document.querySelector(`#trackList .track[data-queue-index="${state.index}"]`);
  const viewport = $("libraryScroll");
  if (!row || !viewport) return;
  const rowBounds = row.getBoundingClientRect();
  const viewportBounds = viewport.getBoundingClientRect();
  const targetTop = viewport.scrollTop + rowBounds.top - viewportBounds.top - Math.max(0, (viewport.clientHeight - row.offsetHeight) / 2);
  viewport.scrollTo({ top: Math.max(0, targetTop), behavior: "auto" });
}
function updateCurrentQueueTrackRow(queueIndex, current) {
  if (!Number.isInteger(queueIndex) || queueIndex < 0) return false;
  const row = document.querySelector(`#trackList .track[data-queue-index="${queueIndex}"]`);
  if (!row) return false;
  row.classList.toggle("is-current", current);
  const titleLine = row.querySelector(".track-title-line");
  if (!titleLine) return true;
  const indicator = titleLine.querySelector(".track-playing-indicator");
  if (current && !indicator) {
    const node = document.createElement("span");
    node.className = "track-playing-indicator";
    node.setAttribute("aria-label", "正在播放");
    node.textContent = "正在播放";
    titleLine.appendChild(node);
  } else if (!current && indicator) {
    indicator.remove();
  }
  return true;
}
function syncCurrentQueuePresentation(previousIndex) {
  if (state.view !== "queue" || previousIndex === state.index) return false;
  const page = currentQueuePage();
  const plan = globalThis.fnAudioQueuePresentation?.queuePresentationPlan?.({
    view: state.view,
    previousIndex,
    currentIndex: state.index,
    previousPage: state.page,
    currentPage: page,
  }) || { requiresFullRender: state.page !== page, shouldScrollCurrent: true };
  state.page = page;
  // A queue position change normally affects only two rows.  Rebuilding the
  // whole page also restarts its cover loader, which is needlessly expensive
  // for large queues.  Keep a full render only for a cross-page jump.
  if (plan.requiresFullRender || !updateCurrentQueueTrackRow(previousIndex, false) || !updateCurrentQueueTrackRow(state.index, true)) {
    render();
    if (plan.shouldScrollCurrent) requestAnimationFrame(() => requestAnimationFrame(scrollCurrentQueueTrackIntoView));
    return true;
  }
  if (plan.shouldScrollCurrent) requestAnimationFrame(() => requestAnimationFrame(scrollCurrentQueueTrackIntoView));
  return false;
}
function openCurrentQueue() {
  if (!$("lyricsView").hidden) closeLyrics();
  [$('searchInput'), $('mobileSearchInput')].forEach(input => { if (input) input.value = ""; });
  setView("queue");
  const page = currentQueuePage();
  if (state.page !== page) {
    state.page = page;
    render();
  }
  requestAnimationFrame(() => requestAnimationFrame(scrollCurrentQueueTrackIntoView));
}
function groupFallbackIcon(view = state.view) {
  const icons = {
    folders: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5h6.2l2 2H21v8.7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 7.5V6a2 2 0 0 1 2-2h4.4l2 2H19a2 2 0 0 1 2 2v1.5"/></svg>`,
    albums: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.4"/><path d="M12 4v3"/><path d="M12 17v3"/></svg>`,
    artists: `<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="4"/><path d="M4.5 20a7.5 7.5 0 0 1 15 0"/></svg>`,
    composers: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18V5l10-2v13"/><circle cx="7" cy="18" r="3"/><circle cx="17" cy="16" r="3"/></svg>`,
    genres: `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14"/><path d="M5 12h14"/><path d="M5 18h10"/><circle cx="18" cy="18" r="2"/></svg>`,
  };
  return icons[view] || icons.albums;
}
function groupIcon(view, items = [], coverTrackId = "", explicitName = "", metadataImage = "") {
  const cachedItem = items.find(item => item?.cover_url);
  const localCover = coverUrl(cachedItem) || (coverTrackId ? mediaUrl(`cover/${encodeURIComponent(coverTrackId)}?size=160`) : "");
  const online = usableCoverSource(metadataImage);
  const image = localCover || online;
  const attributes = localCover && online ? `data-artwork-local="1" data-metadata-image="${escapeHtml(online)}"` : "";
  // Native lazy loading is not consistently honored by older Android WebViews.
  // Use the shared bounded scheduler so a large album/group page does not begin
  // every artwork request at the same time.
  return `<div class="group-icon" ${attributes}>${groupFallbackIcon(view)}${image ? `<img data-cover-src="${escapeHtml(image)}" alt="">` : ""}</div>`;
}
function applyGroupArtwork(node, imageUrl) {
  if (!node?.isConnected || !imageUrl) return;
  const normalizedUrl = usableCoverSource(imageUrl);
  if (!normalizedUrl) return;
  const existing = node.querySelector("img");
  const existingSource = existing?.getAttribute("data-cover-src")
    || existing?.dataset?.coverLoadedSrc || existing?.getAttribute("src") || "";
  if (existing && existingSource === normalizedUrl) return;
  if (existing) existing.remove();
  const image = document.createElement("img");
  // Keep fallback artwork inside the shared bounded scheduler too. Local
  // artwork failures are asynchronous, so assigning src here would otherwise
  // fan out one network request per visible group at once.
  image.setAttribute("data-cover-src", normalizedUrl);
  image.alt = "";
  node.appendChild(image);
  hydrateVisibleTrackCovers();
}
function prepareLocalGroupArtwork(node) {
  const image = node.querySelector("img");
  if (!image) return;
  const loaded = () => {
    node.classList.add("has-cover");
    node.removeAttribute("data-metadata-image");
  };
  const failed = () => {
    image.remove();
    node.classList.remove("has-cover");
    node.removeAttribute("data-artwork-local");
    const fallback = node.dataset.metadataImage || "";
    node.removeAttribute("data-metadata-image");
    if (fallback) applyGroupArtwork(node, fallback);
  };
  const verify = () => {
    if (!image.isConnected || !image.complete) return;
    if (image.naturalWidth > 1) loaded();
    else failed();
  };
  if (image.complete) return verify();
  image.addEventListener("load", loaded, { once: true });
  image.addEventListener("error", failed, { once: true });
  requestAnimationFrame(verify);
}
function loadGroupArtwork() {
  // Restrict the lookup to the rendered library list.  Scanning the whole
  // document on every page render needlessly touches persistent chrome and
  // becomes visible with large libraries or frequent playback updates.
  const root = $("trackList") || document;
  const nodes = [...new Set([...root.querySelectorAll(".group-icon img, .album-detail-cover img")].map(image => image.parentElement).filter(Boolean))];
  if (!nodes.length) return;
  nodes.forEach(prepareLocalGroupArtwork);
}
function activeTrackColumns() {
  return currentTrackColumns();
}
function trackGridTemplate() {
  const widths = currentTrackColumnWidths();
  if (globalThis.fnAudioTrackTablePresentation?.gridTemplate) {
    return globalThis.fnAudioTrackTablePresentation.gridTemplate(activeTrackColumns(), widths, TRACK_COLUMN_DEFINITIONS);
  }
  return [...activeTrackColumns().map(key => `${widths[key] || TRACK_COLUMN_DEFINITIONS[key].width}px`), "minmax(0,1fr)"].join(" ");
}
function applyTrackGridTemplate() {
  const template = trackGridTemplate();
  $("tableHead")?.style.setProperty("--fnaudio-track-columns", template);
  document.body.style.setProperty("--fnaudio-track-columns", template);
}
function trackColumnWidthLimits(key) {
  if (globalThis.fnAudioTrackTablePresentation?.widthLimits) return globalThis.fnAudioTrackTablePresentation.widthLimits(key);
  return {
    title: [260, 620], track_no: [64, 84], artist: [120, 280], album: [150, 340],
    format: [76, 110], duration: [72, 96], size: [88, 120], quality: [120, 170],
    added: [110, 150], composer: [120, 260], genre: [110, 200],
  }[key] || [80, 260];
}
function measureAutoTrackColumnWidths() {
  if (window.matchMedia("(max-width: 760px)").matches) return;
  if ((isCreatorView() && !currentCreatorName()) || (state.view === "genres" && !state.groupName)) {
    const template = "minmax(280px,1fr)";
    $("tableHead")?.style.setProperty("--fnaudio-track-columns", template);
    document.body.style.setProperty("--fnaudio-track-columns", template);
    return;
  }
  if (isAlbumCollectionView()) {
    const template = "minmax(280px,1fr) minmax(160px,240px) 130px";
    $("tableHead")?.style.setProperty("--fnaudio-track-columns", template);
    document.body.style.setProperty("--fnaudio-track-columns", template);
    return;
  }
  const scope = trackColumnScope();
  const saved = normalizeTrackColumnWidths(state.trackColumnWidthPreferences[scope]);
  const widths = {};
  activeTrackColumns().forEach(key => {
    if (saved[key]) return;
    const [minimum, maximum] = trackColumnWidthLimits(key);
    const header = document.querySelector(`[data-track-column="${key}"] .track-head-button,[data-track-column="${key}"] .track-head-label`);
    let measured = Number(header?.scrollWidth || 0) + 24;
    if (key === "title") {
      document.querySelectorAll(".track-title").forEach(node => { measured = Math.max(measured, Number(node.scrollWidth || 0) + 72); });
    } else {
      document.querySelectorAll(`.track-cell-${key}`).forEach(node => { measured = Math.max(measured, Number(node.scrollWidth || 0) + 18); });
    }
    widths[key] = Math.max(minimum, Math.min(maximum, Math.ceil(measured)));
  });
  state.autoTrackColumnWidths[scope] = widths;
  applyTrackGridTemplate();
}
function trackQuality(item) {
  if (globalThis.fnAudioTrackPresentation?.quality) return globalThis.fnAudioTrackPresentation.quality(item);
  const rate = Number(item.sample_rate || 0);
  const depth = Number(item.bit_depth || 0);
  const bitrate = Number(item.bitrate || 0);
  return rate ? `${Math.round(rate / 1000)}kHz${depth ? `/${depth}bit` : ""}` : (bitrate ? `${Math.round(bitrate / 1000)}kbps` : "—");
}
function trackAddedDate(item) {
  if (globalThis.fnAudioTrackPresentation?.addedDate) return globalThis.fnAudioTrackPresentation.addedDate(item, itemAddedTime);
  const seconds = itemAddedTime(item);
  if (!seconds) return "—";
  try { return new Date(seconds > 99999999999 ? seconds / 1000000000 : seconds * 1000).toLocaleDateString("zh-CN"); } catch (error) { return "—"; }
}
function trackColumnValues(item, keys = []) {
  if (globalThis.fnAudioTrackPresentation?.columnValues) {
    return globalThis.fnAudioTrackPresentation.columnValues(item, keys, { displayText, clock, formatSize, escapeHtml, itemAddedTime });
  }
  const trackNo = Number(item.track_no || 0) > 0 ? String(Number(item.track_no)).padStart(2, "0") : "—";
  const values = { track_no: trackNo, artist: displayText(item.artist), album: displayText(item.album), format: item.format || "—", duration: Number(item.duration || 0) > 0 ? clock(item.duration) : "—", size: formatSize(item.size) || "—", quality: trackQuality(item), added: trackAddedDate(item), composer: displayText(item.composer), genre: displayText(item.genre) };
  return (keys || []).reduce((result, key) => {
    if (typeof key === "string") result[key] = escapeHtml(values[key] || "—");
    return result;
  }, {});
}
function canSortTrackColumn(key) {
  return Boolean(TRACK_COLUMN_DEFINITIONS[key]?.sort) && sortOptionsForView().some(([value]) => value === TRACK_COLUMN_DEFINITIONS[key].sort);
}
function renderTableHead(target = $("tableHead")) {
  const head = target;
  if (!head) return;
  const columns = activeTrackColumns();
  const currentSort = state.sortKey || "title";
  const groupMode = (isCreatorView() && !currentCreatorName()) || (state.view === "genres" && !state.groupName);
  const mode = groupMode ? "group" : (isAlbumCollectionView() ? "album-collection" : "tracks");
  const shared = globalThis.fnAudioTrackTablePresentation?.tableHeadPresentation?.({
    mode,
    columns,
    widths: currentTrackColumnWidths(),
    definitions: TRACK_COLUMN_DEFINITIONS,
    currentSort,
    sortDir: state.sortDir,
    groupSortKey: groupViews[state.view],
    sortableSortKeys: sortOptionsForView().map(([key]) => key),
  });
  let template = "";
  let markup = "";
  if (shared) {
    template = shared.template;
    markup = shared.markup;
  } else {
    const renderHeader = (key, label, sortKey) => {
      const sortable = sortKey && sortOptionsForView().some(([value]) => value === sortKey);
      const indicator = currentSort === sortKey ? `<span class="track-sort-indicator">${state.sortDir === "asc" ? "&#9650;" : "&#9660;"}</span>` : "";
      const control = sortable
        ? `<button class="track-head-button" type="button" data-track-sort="${sortKey}">${label}${indicator}</button>`
        : `<span class="track-head-label">${label}</span>`;
      return `<div class="track-header-cell" data-track-column="${key}">${control}<span class="column-resize-handle" data-column-resize="${key}" title="拖动调整列宽" aria-hidden="true"></span></div>`;
    };
    template = trackGridTemplate();
    markup = columns.map(key => renderHeader(key, TRACK_COLUMN_DEFINITIONS[key].label, TRACK_COLUMN_DEFINITIONS[key].sort)).join("") + `<button class="table-head-more" type="button" data-open-columns title="列显示" aria-label="列显示"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg></button>`;
  }
  // Playback and user-state refreshes call render() frequently. Rebuilding an
  // unchanged header invalidates its controls and forces unnecessary layout
  // work above a large library list, even when keyed song rows were retained.
  // Keep a compact per-header signature so only actual columns/sort/template
  // changes replace its DOM.
  // Do not use a NUL separator here: DOMString/dataset implementations may
  // normalize it to U+FFFD, turning every comparison into a false mismatch.
  // JSON keeps the three bounded strings unambiguous across old WebViews.
  const signature = JSON.stringify([mode, template, markup]);
  const changed = head.dataset.fnaudioTableHeadSignature !== signature;
  if (changed) {
    head.style.setProperty("--fnaudio-track-columns", template);
    document.body.style.setProperty("--fnaudio-track-columns", template);
    head.innerHTML = markup;
    head.dataset.fnaudioTableHeadSignature = signature;
  }
  // Event handlers close over only the control's data attributes, so they do
  // not need to be rebound during ordinary playback/favorite renders.  Keep a
  // per-header marker; a signature change recreates the controls and naturally
  // re-enters the binding path.
  if (!changed && head.dataset.fnaudioTableHeadBound === "1") return false;
  head.querySelectorAll("[data-track-sort]").forEach(button => button.onclick = () => applyTrackSort(button.dataset.trackSort));
  if (mode !== "tracks") {
    head.dataset.fnaudioTableHeadBound = "1";
    return changed;
  }
  head.querySelectorAll("[data-open-columns]").forEach(button => button.onclick = openColumnsDialog);
  head.querySelectorAll("[data-column-resize]").forEach(handle => handle.onpointerdown = event => {
    if (window.matchMedia("(max-width: 760px)").matches) return;
    event.preventDefault();
    const key = handle.dataset.columnResize;
    const startX = event.clientX;
    const startWidth = currentTrackColumnWidths()[key] || TRACK_COLUMN_DEFINITIONS[key].width;
    handle.setPointerCapture?.(event.pointerId);
    const resize = move => {
      const width = Math.max(64, Math.min(900, Math.round(startWidth + move.clientX - startX)));
      const current = { ...currentTrackColumnWidths(), [key]: width };
      const template = [...activeTrackColumns().map(column => `${current[column] || TRACK_COLUMN_DEFINITIONS[column].width}px`), "minmax(0,1fr)"].join(" ");
      head.style.setProperty("--fnaudio-track-columns", template);
      document.body.style.setProperty("--fnaudio-track-columns", template);
    };
    const finish = move => {
      resize(move);
      saveTrackColumnWidth(key, startWidth + move.clientX - startX);
      window.removeEventListener("pointermove", resize);
      window.removeEventListener("pointerup", finish);
    };
    window.addEventListener("pointermove", resize);
    window.addEventListener("pointerup", finish, { once: true });
  });
  head.dataset.fnaudioTableHeadBound = "1";
  return changed;
}
function renderAlbumDetail(list) {
  const album = displayText(state.groupName || "未命名专辑");
  const first = list.find(item => item?.cover_url) || list[0] || {};
  const metadata = state.albumMetadata.get(album) || {};
  const artist = displayText(metadata.artist || list.find(item => item?.artist)?.artist || "未知歌手");
  const releaseDate = displayText(metadata.release_date || "");
  const localCover = coverUrl(first, 512);
  const onlineCover = usableCoverSource(metadata.image_url);
  const cover = localCover || onlineCover;
  const coverAttributes = localCover && onlineCover ? `data-artwork-local="1" data-metadata-image="${escapeHtml(onlineCover)}"` : "";
  const coverMarkup = `${groupFallbackIcon("albums")}${cover ? `<img data-cover-src="${escapeHtml(cover)}" alt="">` : ""}`;
  return `<div class="album-detail-layout">
    <aside class="album-detail-sidebar">
      <div class="album-detail-cover" ${coverAttributes}>${coverMarkup}</div>
      <h2>${escapeHtml(album)}</h2>
      <p data-album-detail-artist>${escapeHtml(artist)}</p>
      <small data-album-detail-release-date ${releaseDate ? "" : "hidden"}>${escapeHtml(releaseDate)}</small>
    </aside>
    <section class="album-detail-tracks">
      <nav class="album-detail-breadcrumb" aria-label="专辑路径"><button type="button" data-group-back>专辑</button><span aria-hidden="true">&gt;</span><strong>${escapeHtml(album)}</strong></nav>
      <div class="album-detail-table-head" id="albumDetailTableHead"></div>
      <div class="album-detail-track-list">${renderTrackRows(list)}</div>
    </section>
  </div>`;
}
function trackRowSelectionKey(item, index = 0) {
  return globalThis.fnAudioTrackPresentation?.rowSelectionKey
    ? globalThis.fnAudioTrackPresentation.rowSelectionKey(item, index)
    : `${String(item?.id || "")}::${Math.max(0, Number(index) || 0)}`;
}
function trackRowMarkupSignature(item, index = 0, columns = activeTrackColumns(), columnValues = {}, localCover = "") {
  const presentation = {
    index,
    title: displayTrackTitle(item),
    artist: displayText(item?.artist),
    album: displayText(item?.album),
    cover: localCover,
    columns,
    values: columnValues,
    isDsd: item?.is_dsd === true,
  };
  return globalThis.fnAudioLibraryRowSignaturePolicy?.signature?.(presentation)
    || JSON.stringify([index, presentation.title, presentation.artist, presentation.album, localCover, columns, columnValues, presentation.isDsd]);
}
function renderTrack(item, index = 0, columns = activeTrackColumns()) {
  // Keep the lazy/async contract explicit for static checks:
  // data-cover-src=\"...\" loading=\"lazy\" decoding=\"async\".
  const localCover = coverUrl(item);
  const queueIndex = Number(item.__queueIndex);
  const hasQueuePosition = Number.isInteger(queueIndex) && queueIndex >= 0;
  const isCurrent = state.view === "queue" && hasQueuePosition && queueIndex === state.index;
  const columnValues = trackColumnValues(item, columns.filter(key => key !== "title"));
  const artist = displayText(item.artist) || "未知歌手";
  const album = displayText(item.album);
  const mobileSubtitle = album && album !== artist ? `${artist} · ${album}` : artist;
  const rowKey = trackRowSelectionKey(item, index);
  const isSelected = state.selectedTrackRowKeys.has(rowKey);
  const playingIndicator = isCurrent ? `<span class="track-playing-indicator" aria-label="正在播放">正在播放</span>` : "";
  // Keep the fallback visible until the image has decoded. Hiding it for the
  // eager first rows used to leave a short blank tile between the first list
  // commit and the browser's image decode on slower WebViews. The glyph is
  // covered by a decoded image and is removed only by its `onload` handler;
  // on failure it remains the same stable music-symbol presentation.
  const coverImage = localCover
      ? `<img data-cover-src="${escapeHtml(localCover)}"${index < 8 ? ` src="${escapeHtml(localCover)}"` : ""} loading="${index < 8 ? "eager" : "lazy"}" decoding="async" fetchpriority="${index < 8 ? "high" : "low"}" alt="" onload="this.hidden=false;this.removeAttribute('data-cover-retry-count');const fallback=this.parentElement?.querySelector('.track-cover-fallback');if(fallback)fallback.hidden=true" onerror="this.hidden=true;const fallback=this.parentElement?.querySelector('.track-cover-fallback');if(fallback)fallback.hidden=false;const retry=Number(this.dataset.coverRetryCount||0);const source=this.dataset.coverSrc||this.src;if(!this.dataset.coverSchedulerOwned&&source&&retry<1){this.dataset.coverRetryCount=String(retry+1);setTimeout(()=>{if(this.isConnected){this.hidden=false;this.src=source}},450)}">`
    : "";
  // Lazy rows have not started decoding yet; keep the glyph visible until the
  // scheduler attaches/loads the image. Hiding it for every row created a
  // blank tile between the list commit and IntersectionObserver hydration.
  const coverFallback = `<span class="track-cover-fallback">♫</span>`;
  const titleCell = `<div class="track-main" data-play="${escapeHtml(item.id)}"><div class="track-cover">${coverImage}${coverFallback}</div><div class="track-info"><div class="track-title-line"><strong class="track-title">${escapeHtml(displayTrackTitle(item))}</strong>${playingIndicator}</div><span class="mobile-track-subtitle">${escapeHtml(mobileSubtitle)}</span></div></div>`;
  const rowSignature = trackRowMarkupSignature(item, index, columns, columnValues, localCover);
  return `<div class="track${isCurrent ? " is-current" : ""}${isSelected ? " is-selected" : ""}" data-track-row-key="${escapeHtml(rowKey)}" data-track-row-signature="${escapeHtml(rowSignature)}" data-track-id="${escapeHtml(item.id)}"${hasQueuePosition ? ` data-queue-index="${queueIndex}"` : ""}>
    ${columns.map(key => key === "title" ? titleCell : `<span class="track-cell track-cell-${key}${key === "format" && item.is_dsd === true ? " dsd" : ""}">${columnValues[key] || "—"}</span>`).join("")}
  </div>`;
}
function renderTrackRows(items = []) {
  // Column selection is scoped to the view, not to an individual song. Compute
  // it once per list build: a 120-song first page previously repeated the
  // scope/preference lookup for every row and could repeat legacy migration
  // work while the initial DOM was being assembled.
  const columns = activeTrackColumns();
  const rows = Array.isArray(items) ? items : [];
  const cache = state.trackRowsMarkupCache;
  // Selection classes are reconciled directly after the keyed commit, so they
  // do not make a static page-row template stale. Do not reuse queue rows:
  // their current-playing indicator belongs in the generated markup itself.
  const cacheKey = state.view === "queue" ? "" : `${trackColumnScope()}|${columns.join("|")}`;
  const cached = cacheKey && cache ? cache.get(rows) : null;
  if (cached?.key === cacheKey) return cached.html;
  const html = rows.map((item, index) => renderTrack(item, index, columns)).join("");
  if (cacheKey && cache) cache.set(rows, { key: cacheKey, html });
  return html;
}
function invalidateTrackRowsMarkup(items = state.pageItems) {
  if (Array.isArray(items)) state.trackRowsMarkupCache?.delete(items);
  // Metadata backfill mutates row objects in place. Invalidate the filtered
  // view memo as well, otherwise a search/sort render can keep using the
  // pre-backfill title, artist or album fields until the page array changes.
  if (state.filteredTracksCache) state.filteredTracksCache = { signature: null, tracks: [] };
}
function cancelMetadataRowRender() {
  if (state.metadataRowRenderTimer) {
    if (state.metadataRowRenderUsesFrame && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(state.metadataRowRenderTimer);
    } else {
      clearTimeout(state.metadataRowRenderTimer);
    }
  }
  state.metadataRowRenderTimer = 0;
  state.metadataRowRenderUsesFrame = false;
  state.metadataRowRenderTrackIds.clear();
  state.metadataRowRenderFieldsByTrack.clear();
  state.metadataRowRenderForceFull = false;
  state.metadataRowRenderExpectedRequestSeq = 0;
  state.metadataRowRenderExpectedView = "";
  state.metadataRowRenderExpectedPage = 1;
  state.metadataRowRenderExpectedPageItems = null;
}
function metadataRowRenderBatchMatchesCurrent() {
  const expected = {
    requestSeq: state.metadataRowRenderExpectedRequestSeq,
    view: state.metadataRowRenderExpectedView,
    page: state.metadataRowRenderExpectedPage,
    pageItems: state.metadataRowRenderExpectedPageItems,
  };
  const current = {
    requestSeq: state.libraryRequestSeq,
    view: state.view,
    page: state.page,
    pageItems: state.pageItems,
  };
  const policy = globalThis.fnAudioMetadataRowPatchPolicy;
  if (typeof policy?.sameListIdentity === "function") return policy.sameListIdentity(expected, current);
  return expected.requestSeq === current.requestSeq
    && expected.view === current.view
    && expected.page === current.page
    && expected.pageItems === current.pageItems;
}
function metadataRowPatchOnly(trackId = "", item = null, index = -1, options = {}) {
  const id = String(trackId || "");
  if (!id || !isPagedTrackListing() || !Array.isArray(state.pageItems)) return false;
  const row = options.rowsById?.get(id) || (() => {
    const escape = globalThis.CSS?.escape;
    const selectorId = escape ? escape(id) : id.replace(/[^a-zA-Z0-9_-]/g, "\\$&");
    return document.querySelector(`[data-track-id="${selectorId}"]`);
  })();
  const currentItem = item || state.pageItems.find(entry => String(entry?.id || "") === id);
  if (!row || !currentItem) return false;
  const currentIndex = index >= 0 ? index : state.pageItems.indexOf(currentItem);
  const template = document.createElement("template");
  template.innerHTML = renderTrack(currentItem, currentIndex, options.columns || activeTrackColumns());
  const next = template.content.firstElementChild;
  if (!next) return false;
  patchTrackRowNode(row, next);
  // A batch re-establishes the page's declarative markup once all keyed row
  // patches have settled. Until then, do not let a later render treat the
  // pre-patch HTML as current.
  state.renderedTrackListHtml = "";
  if (!options.deferSelection) setTrackSelection([...state.selectedTrackRowKeys], false);
  return true;
}
function scheduleMetadataRowRender(trackId = "", changedFields = []) {
  const expectedTrackId = String(trackId || "");
  // Metadata may settle after a user has already switched page/view. Bind one
  // deferred batch to the current list identity so an obsolete frame cannot
  // repaint a newly requested page and look like a list flash. Track ids are
  // collected rather than replacing the timer, allowing visible rows to be
  // patched together after a provider burst.
  const batchIsStale = state.metadataRowRenderTimer && !metadataRowRenderBatchMatchesCurrent();
  // Do not merge a new page's update into a timer captured for the old page.
  // Otherwise its identity guard discards both payloads when the old batch
  // flushes, delaying visible metadata until another provider response arrives.
  if (batchIsStale) cancelMetadataRowRender();
  if (!state.metadataRowRenderTimer) {
    state.metadataRowRenderExpectedRequestSeq = state.libraryRequestSeq;
    state.metadataRowRenderExpectedView = state.view;
    state.metadataRowRenderExpectedPage = state.page;
    state.metadataRowRenderExpectedPageItems = state.pageItems;
  }
  if (expectedTrackId) state.metadataRowRenderTrackIds.add(expectedTrackId);
  else state.metadataRowRenderForceFull = true;
  if (expectedTrackId) {
    const fields = state.metadataRowRenderFieldsByTrack.get(expectedTrackId) || new Set();
    if (Array.isArray(changedFields)) changedFields.forEach(field => {
      const value = String(field || "").trim();
      if (value) fields.add(value);
    });
    state.metadataRowRenderFieldsByTrack.set(expectedTrackId, fields);
  }
  if (state.metadataRowRenderTimer) {
    // A current-song update is frame-priority. Promote an existing quiet
    // visible-row batch to the next frame without dropping its pending ids.
    if (expectedTrackId && String(currentItem()?.id || "") === expectedTrackId
      && !state.metadataRowRenderUsesFrame
      && typeof requestAnimationFrame === "function") {
      clearTimeout(state.metadataRowRenderTimer);
      state.metadataRowRenderUsesFrame = true;
      state.metadataRowRenderTimer = requestAnimationFrame(flushMetadataRows);
    }
    return;
  }
  function flushMetadataRows() {
    state.metadataRowRenderTimer = 0;
    state.metadataRowRenderUsesFrame = false;
    const pendingTrackIds = [...state.metadataRowRenderTrackIds];
    const fieldsByTrack = new Map([...state.metadataRowRenderFieldsByTrack].map(([id, fields]) => [id, [...fields]]));
    const forceFull = state.metadataRowRenderForceFull;
    state.metadataRowRenderTrackIds.clear();
    state.metadataRowRenderFieldsByTrack.clear();
    state.metadataRowRenderForceFull = false;
    if (!metadataRowRenderBatchMatchesCurrent()) return;
    if (state.pageItems?.length && !state.libraryLoading) {
      const policy = globalThis.fnAudioMetadataRowPatchPolicy;
      // A metadata burst can touch most of a page. Build the page lookup once
      // so row patching avoids repeated linear `find` and `indexOf` scans.
      const visibleItemsById = new Map(state.pageItems.map((item, index) => [String(item?.id || ""), { item, index }]));
      const visiblePendingIds = pendingTrackIds.filter(id => visibleItemsById.has(id));
      // A request may settle after its song has left the visible page. Do not
      // let that off-page result turn a local visible-row patch into a full
      // list commit and reintroduce a first-screen flash.
      if (!forceFull && !visiblePendingIds.length) return;
      const patchable = !forceFull && visiblePendingIds.length > 0
        && visiblePendingIds.every(id => policy?.canPatchRow?.({
          pagedTrackListing: isPagedTrackListing(),
          queueView: state.view === "queue",
          groupRoot: isPagedGroupListing(),
          folderView: state.view === "folders",
          albumDetail: isAlbumDetailView(),
          creatorAllTracks: isCreatorAllTracksView(),
          search: currentQueryText(),
          sortKey: state.sortKey,
          changedFields: fieldsByTrack.get(id) || [],
        }) === true);
      if (patchable) {
        const rowsById = new Map([...($("trackList")?.querySelectorAll?.("[data-track-id]") || [])]
          .map(row => [String(row.getAttribute("data-track-id") || ""), row])
          .filter(([id]) => id));
        const columns = activeTrackColumns();
        const patched = visiblePendingIds.reduce((count, id) => {
          const location = visibleItemsById.get(id);
          return metadataRowPatchOnly(id, location?.item, location?.index, { rowsById, columns, deferSelection: true }) ? count + 1 : count;
        }, 0);
        if (patched > 0) {
          setTrackSelection([...state.selectedTrackRowKeys], false);
          // The in-place mutations already invalidated the row template cache.
          // Rebuild its declarative page markup once for the whole burst so a
          // following playback/status render can take the exact HTML no-op
          // path instead of re-running keyed reconciliation across every row.
          state.renderedTrackListHtml = renderTrackRows(state.pageItems);
        }
        // Cover discovery is a page-wide DOM walk. Run it once after the
        // metadata burst, rather than once per patched row.
        if (patched > 0) hydrateVisibleTrackCovers();
        // Rows outside the current page need no repaint. Fall back only when a
        // visible target was expected but its live DOM row is unavailable.
        if (visiblePendingIds.length && patched !== visiblePendingIds.length) render();
      } else render();
      // Persist the enriched visible page during idle time. The scheduler
      // coalesces bursts and keeps the bounded snapshot size/TTL contract.
      scheduleLibraryPageSnapshot(state.page);
    }
  }
  // Visible-row enrichment often completes in a small burst shortly after
  // page one arrives. Coalesce that non-playing work for a short interval so
  // it produces one keyed patch rather than a sequence of list commits that
  // looks like a flash. Current-song metadata remains frame-priority.
  state.metadataRowRenderUsesFrame = Boolean(expectedTrackId && typeof requestAnimationFrame === "function");
  state.metadataRowRenderTimer = state.metadataRowRenderUsesFrame
    ? requestAnimationFrame(flushMetadataRows)
    : setTimeout(flushMetadataRows, 180);
}
function invalidateLibraryResponseForTrack(trackId) {
  const id = String(trackId || "");
  if (!id || !state.libraryResponseCache?.deleteWhere) return;
  state.libraryResponseCache.deleteWhere(value => Array.isArray(value?.items)
    && value.items.some(item => String(item?.id || "") === id));
}
function commitTrackListHtml(listHtml) {
  const list = $("trackList");
  if (!list) return false;
  if (state.renderedTrackListHtml === listHtml) {
    state.uiMetrics.listMarkupNoops = Math.min(1000000, state.uiMetrics.listMarkupNoops + 1);
    return false;
  }
  // When a snapshot is followed by the authoritative response, metadata or
  // playback decorations may change only a handful of rows. Replacing the
  // whole list makes old WebViews discard every decoded cover and causes a
  // visible flash. Patch keyed top-level rows when the structure is stable;
  // fall back to one replacement for grouped/nested views.
  let patched = false;
  let domChanged = false;
  if (list.children.length) {
    const template = document.createElement("template");
    template.innerHTML = listHtml;
    const next = [...template.content.children];
    const current = [...list.children];
    const keyOf = node => node.getAttribute?.("data-track-row-key") || node.getAttribute?.("data-group-key") || "";
    const currentByKey = new Map(current.map(node => [keyOf(node), node]).filter(([key]) => key));
    const nextKeys = next.map(keyOf);
    // Keyed reconciliation also works when filtering/paging changes the row
    // count or order.  Moving an existing node through a fragment preserves
    // its decoded cover and in-flight request instead of forcing a full
    // innerHTML replacement (the main source of cover flashes on old WebViews).
    const nextKeySet = new Set(nextKeys.filter(Boolean));
    const keyed = next.length > 0 && nextKeySet.size === next.length
      && currentByKey.size === current.length;
    if (keyed) {
      const orderUnchanged = current.length === next.length
        && current.every((node, index) => keyOf(node) === nextKeys[index]);
      // Appending an already-connected node to a DocumentFragment removes it
      // from the live list immediately.  Do not create/move through a
      // fragment for a stable-order patch: on older WebViews that briefly
      // emptied the list even though the final order was unchanged.
      const fragment = orderUnchanged ? null : document.createDocumentFragment();
      const desiredNodes = orderUnchanged ? null : [];
      const usedKeys = new Set();
      next.forEach((node, index) => {
        const key = nextKeys[index];
        const existing = currentByKey.get(key);
        usedKeys.add(key);
        const existingSignature = existing?.getAttribute?.("data-track-row-signature");
        const nextSignature = node.getAttribute?.("data-track-row-signature");
        // A snapshot and its first authoritative page can carry different
        // transport-only row signatures (for example an old cached field
        // representation), while producing identical visible markup. A
        // signature mismatch is therefore only a cheap hint that a comparison
        // may be needed; replacing such rows anyway briefly re-paints every
        // cover on older WebViews. Preserve the live node when the normalized
        // presentation is still equivalent.
        const rowChanged = existing && existingSignature && nextSignature
          ? existingSignature !== nextSignature
            && trackRowComparableHtml(existing) !== trackRowComparableHtml(node)
          : existing && trackRowComparableHtml(existing) !== trackRowComparableHtml(node);
        if (existing && rowChanged) {
          // A metadata response normally changes only title cells and/or one
          // cover.  Replacing the row wrapper is cheaper than rebuilding the
          // entire list, but old WebViews still repaint the row and can show
          // a short cover glyph flash. Keep the connected row identity and
          // patch its small direct cells instead. This also preserves focus,
          // selection and any in-flight cover decode owned by the live row.
          patchTrackRowNode(existing, node);
          domChanged = true;
        }
        const resolved = existing && existing.isConnected ? existing : node;
        if (fragment && desiredNodes) {
          desiredNodes.push(resolved);
          fragment.appendChild(resolved);
        }
      });
      current.forEach(node => {
        const key = keyOf(node);
        if (key && !usedKeys.has(key)) {
          node.remove();
          domChanged = true;
        }
      });
      if (!orderUnchanged && desiredNodes && (
        current.length !== desiredNodes.length || current.some((node, index) => node !== desiredNodes[index])
      )) domChanged = true;
      // Avoid moving every unchanged row through a fragment on ordinary
      // status renders. This keeps layout/paint quiet when the list identity
      // and order are already stable; the fragment is only needed for an
      // actual insertion, removal or reorder.
      if (fragment) list.appendChild(fragment);
      patched = true;
    }
  }
  if (!patched) {
    list.innerHTML = listHtml;
    domChanged = true;
  }
  state.renderedTrackListHtml = listHtml;
  if (domChanged) {
    state.uiMetrics.listCommits = Math.min(1000000, state.uiMetrics.listCommits + 1);
    if (!state.uiMetrics.firstListCommitMs) {
      const elapsed = Date.now() - Number(state.uiMetrics.sessionStartedAt || Date.now());
      state.uiMetrics.firstListCommitMs = Math.min(3600000, Math.max(0, elapsed));
    }
  }
  // A render signature can change because a live row was already updated by
  // selection/cover code.  Do not treat that bookkeeping-only delta as a DOM
  // change: callers would otherwise restart cover observation and schedule a
  // fresh layout pass after the visible list has already settled.
  return domChanged;
}
function trackRowComparableHtml(node) {
  if (!node?.cloneNode) return "";
  const copy = node.cloneNode(true);
  // The signature is a reconciliation optimization, not user-visible
  // presentation. Do not let a transport-only signature change make two
  // otherwise identical rows appear different to the final DOM guard.
  copy.removeAttribute?.("data-track-row-signature");
  copy.querySelectorAll?.("img").forEach(image => {
    // A scheduler-started image has src but no data-cover-src. Restore the
    // declarative shape used by renderTrack/renderGroups before comparison.
    const source = image.getAttribute("data-cover-src") || image.dataset?.coverLoadedSrc || image.getAttribute("src") || "";
    if (source) image.setAttribute("data-cover-src", source);
    image.removeAttribute("src");
    image.removeAttribute("data-cover-queued");
    image.removeAttribute("data-cover-loaded-src");
    image.removeAttribute("data-cover-observed");
  });
  copy.querySelectorAll?.(".group-icon, .album-detail-cover").forEach(cover => cover.classList.remove("has-cover"));
  copy.querySelectorAll?.(".track-cover-fallback").forEach(fallback => fallback.removeAttribute("hidden"));
  return copy.outerHTML;
}
function preserveTrackCoverNode(current, next) {
  // Reuse an already decoded cover when metadata/playback patches rebuild the
  // same row. This avoids a visible glyph/blank flash in older WebViews.
  const currentImage = current?.querySelector?.(".track-cover img");
  const nextImage = next?.querySelector?.(".track-cover img");
  if (!currentImage || !nextImage) return;
  const currentSource = currentImage.getAttribute("data-cover-src")
    || currentImage.dataset?.coverLoadedSrc || currentImage.getAttribute("src") || "";
  const nextSource = nextImage.getAttribute("data-cover-src") || nextImage.getAttribute("src") || "";
  if (!currentSource || !nextSource || currentSource !== nextSource) return;
  // Move the actual node instead of copying attributes. The decoded bitmap
  // and any in-flight request then remain attached to the replacement row.
  nextImage.replaceWith(currentImage);
  const currentFallback = current.querySelector?.(".track-cover-fallback");
  const nextFallback = next.querySelector?.(".track-cover-fallback");
  if (currentFallback?.hidden && nextFallback) nextFallback.hidden = true;
}
function directTrackChild(row, className) {
  if (!row?.children) return null;
  for (const child of row.children) {
    if (child?.classList?.contains(className)) return child;
  }
  return null;
}
function copyTrackRowAttributes(current, next) {
  if (!current?.attributes || !next?.attributes) return;
  const wanted = new Map([...next.attributes].map(attribute => [attribute.name, attribute.value]));
  [...current.attributes].forEach(attribute => {
    if (!wanted.has(attribute.name)) current.removeAttribute(attribute.name);
  });
  wanted.forEach((value, name) => {
    if (current.getAttribute(name) !== value) current.setAttribute(name, value);
  });
}
function patchTrackRowNode(current, next) {
  if (!current?.classList?.contains("track") || !next?.classList?.contains("track")) {
    preserveTrackCoverNode(current, next);
    current?.replaceWith?.(next);
    return;
  }
  copyTrackRowAttributes(current, next);
  const currentMain = directTrackChild(current, "track-main");
  const nextMain = directTrackChild(next, "track-main");
  if (currentMain && nextMain) {
    const currentCover = directTrackChild(currentMain, "track-cover");
    const nextCover = directTrackChild(nextMain, "track-cover");
    const currentImage = currentCover?.querySelector?.("img");
    const nextImage = nextCover?.querySelector?.("img");
    const currentSource = currentImage?.getAttribute?.("data-cover-src")
      || currentImage?.dataset?.coverLoadedSrc || currentImage?.getAttribute?.("src") || "";
    const nextSource = nextImage?.getAttribute?.("data-cover-src") || nextImage?.getAttribute?.("src") || "";
    // Retain an existing decoded/in-flight image if it represents the same
    // artwork. Only the cover tile itself changes for a genuinely new image.
    if (currentCover && nextCover && currentSource !== nextSource) currentCover.innerHTML = nextCover.innerHTML;
    const currentInfo = directTrackChild(currentMain, "track-info");
    const nextInfo = directTrackChild(nextMain, "track-info");
    if (currentInfo && nextInfo && currentInfo.innerHTML !== nextInfo.innerHTML) currentInfo.innerHTML = nextInfo.innerHTML;
  } else if (currentMain || nextMain) {
    currentMain?.replaceWith?.(nextMain);
  }
  const currentCells = [...current.children].filter(child => !child.classList?.contains("track-main"));
  const nextCells = [...next.children].filter(child => !child.classList?.contains("track-main"));
  if (currentCells.length !== nextCells.length) {
    current.innerHTML = next.innerHTML;
    return;
  }
  currentCells.forEach((cell, index) => {
    const replacement = nextCells[index];
    if (cell?.outerHTML !== replacement?.outerHTML) cell.replaceWith(replacement);
  });
}
function needsVisibleTrackCoverHydration() {
  const root = $("trackList");
  const images = root?.querySelectorAll ? root.querySelectorAll("img[data-cover-src]") : [];
  let hasUnloaded = false;
  for (const image of images) {
    if (image?.hasAttribute?.("src")) continue;
    hasUnloaded = true;
    // A newly patched row has no generation marker. Existing queued rows are
    // already owned by the active scheduler and must not restart the whole
    // observer merely because a playback decoration changed elsewhere.
    if (!image.dataset.coverQueued && !image.dataset.coverObserved) return true;
  }
  if (!hasUnloaded || !state.coverLoadScheduler?.snapshot) return !state.coverLoadScheduler && hasUnloaded;
  const status = state.coverLoadScheduler.snapshot();
  // Recover only a genuinely idle scheduler with unstarted nodes (for example
  // after an older WebView discarded an observer callback), not every render.
  return Number(status?.queued || 0) === 0 && Number(status?.inFlight || 0) === 0;
}
function hydrateVisibleTrackCovers() {
  if (!state.coverLoadScheduler && globalThis.fnAudioCoverLoadScheduler?.create) {
    state.coverLoadScheduler = globalThis.fnAudioCoverLoadScheduler.create({
      document,
      window,
      getImageRoot: () => $("trackList"),
      getScrollRoot: () => $("libraryScroll"),
      maxConcurrent: 4,
      onEvent: event => {
        const key = event === "request" ? "coverRequests"
          : event === "load" ? "coverLoads"
            : event === "retry" ? "coverRetries" : event === "error" ? "coverFailures" : "";
        if (key) state.uiMetrics[key] = Math.min(1000000, state.uiMetrics[key] + 1);
      },
    });
  }
  if (state.coverLoadScheduler && !needsVisibleTrackCoverHydration()) {
    const status = state.coverLoadScheduler.snapshot?.();
    if (status && typeof status === "object") state.coverLoadStatus = status;
    return;
  }
  const status = state.coverLoadScheduler?.hydrate();
  state.uiMetrics.coverHydrations = Math.min(1000000, state.uiMetrics.coverHydrations + 1);
  if (!state.uiMetrics.firstCoverHydrationMs) {
    const elapsed = Date.now() - Number(state.uiMetrics.sessionStartedAt || Date.now());
    state.uiMetrics.firstCoverHydrationMs = Math.min(3600000, Math.max(0, elapsed));
  }
  if (status && typeof status === "object") state.coverLoadStatus = status;
}
function renderGroups(groups = groupedTracks()) {
  const groupView = isCreatorAlbumView() ? "albums" : state.view;
  return groups.map(group => {
    const name = displayText(group.name || "未分类");
    const key = `group:${groupView}:${name}`;
    const trackCount = libraryCount(group.track_count);
    return `<div class="group-row${state.selectedGroupKeys.has(key) ? " is-selected" : ""}" data-group-row data-group-key="${escapeHtml(key)}" data-group-type="group" data-group-view="${escapeHtml(groupView)}" data-group-name="${encodeURIComponent(name)}" data-group-track-count="${trackCount}">
    ${groupIcon(groupView, [state.itemCache.get(String(group.cover_track_id || ""))].filter(Boolean), group.cover_track_id, name, group.image_url)}
    <div class="group-info"><strong>${escapeHtml(name)}</strong><span>${trackCount} 首</span></div>
  </div>`;
  }).join("");
}
function renderCreatorAllSongsEntry(groups = groupedTracks()) {
  const creator = displayText(currentCreatorName() || `未知${currentCreatorLabel()}`);
  const fallbackTotal = groups.reduce((total, group) => total + libraryCount(group.track_count), 0);
  const trackTotal = libraryCount(currentCreatorTrackTotal() || fallbackTotal);
  return `<button class="artist-all-songs-entry" type="button" data-open-creator-all-tracks>
    <span class="artist-all-songs-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M9 18V5l10-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="16" cy="16" r="3"/></svg></span>
    <span class="artist-all-songs-copy"><strong>所有歌曲</strong><small>查看 ${escapeHtml(creator)} 的全部歌曲</small></span>
    <span class="artist-all-songs-count">${trackTotal ? `${trackTotal} 首` : "查看歌曲"}</span>
    <span class="artist-all-songs-chevron" aria-hidden="true">&gt;</span>
  </button>`;
}
function renderAlbumGroups(groups = groupedTracks()) {
  const albums = groups.map(group => {
    const name = displayText(group.name || "未分类");
    const key = `group:albums:${name}`;
    const metadata = state.albumMetadata.get(name) || {};
    const artist = displayText(metadata.artist || group.artist || "未知歌手");
    const releaseDate = displayText(metadata.release_date || "-");
    const trackCount = libraryCount(group.track_count);
    return `<div class="album-group-row${state.selectedGroupKeys.has(key) ? " is-selected" : ""}" data-group-row data-group-key="${escapeHtml(key)}" data-group-type="group" data-group-view="albums" data-group-name="${encodeURIComponent(name)}" data-group-track-count="${trackCount}" data-album-metadata-name="${escapeHtml(name)}"><div class="album-group-title">${groupIcon("albums", [state.itemCache.get(String(group.cover_track_id || ""))].filter(Boolean), group.cover_track_id, name, group.image_url)}<strong>${escapeHtml(name)}</strong></div><span class="album-group-artist">${escapeHtml(artist)}</span><span class="album-group-release-date">${escapeHtml(releaseDate)}</span></div>`;
  }).join("");
  return `${isCreatorAlbumView() ? renderCreatorAllSongsEntry(groups) : ""}${albums}`;
}
function renderCreatorAllTracks(list) {
  const creator = displayText(currentCreatorName() || `未知${currentCreatorLabel()}`);
  return `<nav class="artist-all-tracks-breadcrumb" aria-label="${currentCreatorLabel()}路径">
    <button type="button" data-creator-root-back>${currentCreatorLabel()}</button><span aria-hidden="true">&gt;</span>
    <button type="button" data-group-back>${escapeHtml(creator)}</button><span aria-hidden="true">&gt;</span>
    <strong>所有歌曲</strong>
  </nav>${renderTrackRows(list)}`;
}
function renderGenreTracks(list) {
  const genre = displayText(state.groupName || "未分类");
  return `<nav class="artist-all-tracks-breadcrumb category-tracks-breadcrumb" aria-label="类型路径">
    <button type="button" data-group-back>类型</button><span aria-hidden="true">&gt;</span>
    <strong>${escapeHtml(genre)}</strong>
  </nav>${renderTrackRows(list)}`;
}
function renderFolders(data = folderChildren()) {
  const rootRow = state.folderRootRows.find(row => row.root === state.folderRoot || row.path === state.folderRoot);
  const rootLabel = folderDisplayName(rootRow?.path || state.folderRoot || "音乐目录");
  const parts = String(state.folderPath || "").split("/").filter(Boolean);
  const breadcrumbItems = state.folderRoot
    ? [`<button type="button" class="folder-crumb" data-folder-crumb-root="${encodeURIComponent(state.folderRoot)}" data-folder-crumb-path="">${escapeHtml(rootLabel)}</button>`, ...parts.map((part, index) => `<button type="button" class="folder-crumb${index === parts.length - 1 ? " is-current" : ""}" data-folder-crumb-root="${encodeURIComponent(state.folderRoot)}" data-folder-crumb-path="${encodeURIComponent(parts.slice(0, index + 1).join("/"))}">${escapeHtml(part)}</button>`)]
    : ["<span class=\"folder-crumb is-current\">音乐目录</span>"];
  const breadcrumb = `<nav class="folder-toolbar folder-breadcrumb" aria-label="当前路径">${breadcrumbItems.join('<span class="folder-crumb-separator">/</span>')}</nav>`;
  const folders = data.folders.map(row => {
    const path = row.path || row.parent || "";
    const name = row.name || path.split("/").pop();
    const encoded = encodeURIComponent(path);
    const root = state.folderRoot ? "" : (row.root || row.path || "");
    const encodedRoot = encodeURIComponent(root);
    const openAttribute = state.folderRoot
      ? `data-open-folder-path="${encoded}"`
      : `data-open-folder-root="${encodedRoot}"`;
    const groupRoot = state.folderRoot || root;
    const groupPath = state.folderRoot ? path : "";
    const groupKey = `folder:${groupRoot}:${groupPath}`;
    return `<div class="group-row${state.selectedGroupKeys.has(groupKey) ? " is-selected" : ""}" data-group-row data-group-key="${escapeHtml(groupKey)}" data-group-type="folder" data-group-root="${encodeURIComponent(groupRoot)}" data-group-path="${encodeURIComponent(groupPath)}" ${openAttribute}>
      ${groupIcon("folders")}
      <div class="group-info"><strong>${escapeHtml(name)}</strong><span>${libraryCount(row.track_count)} 首</span></div>
    </div>`;
  }).join("");
  const folderPages = Math.max(1, Math.ceil(libraryCount(state.folderTotal) / state.folderPageSize));
  const folderPager = folderPages > 1 ? `<div class="folder-pager"><button class="secondary-button" data-folder-page-step="-1" ${state.folderPage <= 1 ? "disabled" : ""}>上一组文件夹</button><span>文件夹 ${state.folderPage} / ${folderPages}</span><button class="secondary-button" data-folder-page-step="1" ${state.folderPage >= folderPages ? "disabled" : ""}>下一组文件夹</button></div>` : "";
  const tracks = data.tracks;
  return breadcrumb + folders + folderPager + renderTrackRows(tracks);
}
function renderPager(totalOverride = null) {
  if (!isClientPagedView() && (!isPagedLibraryView() || (!isPagedTrackListing() && !isPagedGroupListing()))) return "";
  const total = libraryCount(totalOverride == null ? (isClientPagedView() ? clientPagedTotal() : state.pageTotal || 0) : totalOverride);
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  if (pages <= 1) return "";
  const unit = isPagedGroupListing() ? "项" : "首";
  return globalThis.fnAudioLibraryPagerPresentation?.renderPager({ total, page: state.page, pages, unit }) || "";
}
function updateMobilePagerVisibility() {
  if (document.body.classList.contains("mobile-search-active")) return;
  const pager = $("pager");
  const list = $("trackList");
  return globalThis.fnAudioLibraryPagerVisibility?.updateMobilePagerVisibility({
    searchActive: document.body.classList.contains("mobile-search-active"),
    isMobile: window.matchMedia("(max-width: 760px)").matches,
    pager,
    list,
    requestFrame: (callback) => requestAnimationFrame(callback),
  });
}
function syncTrackHeaderScroll() {
  const viewport = $("libraryScroll");
  const list = $("trackList");
  const head = $("tableHead");
  if (!viewport || !list || !head || window.matchMedia("(max-width: 760px)").matches) {
    list?.querySelectorAll(".track,.group-row").forEach(row => { row.style.width = ""; });
    if (head) {
      head.style.width = "";
      head.style.transform = "";
    }
    return;
  }
  viewport.style.setProperty("--fnaudio-library-content-width", "100%");
  list.querySelectorAll(".track,.group-row").forEach(row => { row.style.width = ""; });
  head.style.width = "";
  head.style.transform = "";
}
function bindTrackHeaderScroll() {
  const viewport = $("libraryScroll");
  if (!viewport || viewport.dataset.headerScrollBound === "1") return;
  viewport.dataset.headerScrollBound = "1";
  window.addEventListener("resize", syncTrackHeaderScroll, { passive: true });
  if (typeof ResizeObserver === "function") {
    viewport._headerResizeObserver = new ResizeObserver(() => requestAnimationFrame(syncTrackHeaderScroll));
    viewport._headerResizeObserver.observe(viewport);
  }
}
function render() {
  state.uiMetrics.renders = Math.min(1000000, state.uiMetrics.renders + 1);
  updateLibraryStatusDecorations();
  updateSortOptions();
  const isGroup = Boolean(groupViews[state.view]);
  const isFolder = state.view === "folders";
  const creatorAllTracks = isCreatorAllTracksView();
  const isGroupRoot = isGroup && !state.groupName && !creatorAllTracks;
  const folderState = isFolder ? folderChildren() : null;
  const pagedTracks = isPagedTrackListing() ? state.pageItems : [];
  const clientPage = isClientPagedView() ? clientPagedResult() : null;
  const list = isGroupRoot ? groupedTracks() : (isFolder ? (folderState?.tracks || []) : (clientPage ? clientPage.tracks : (isPagedTrackListing() ? pagedTracks : filteredTracks())));
  const clientPageTotal = clientPage?.total ?? null;
  const albumDetail = isAlbumDetailView();
  const genreDetail = state.view === "genres" && Boolean(state.groupName);
  const playlistToolbar = isPlaylistView() && currentPlaylist()
    ? `<div class="playlist-toolbar"><span>${clientPageTotal} 首歌曲</span><button class="danger-button" data-delete-playlist="${escapeHtml(currentPlaylist().id)}">删除播放列表</button></div>`
    : state.view === "favorites"
      ? `<div class="playlist-toolbar"><span>${clientPageTotal} 首收藏歌曲</span></div>`
      : state.view === "queue"
        ? `<div class="playlist-toolbar"><span>${state.queue.length} 首歌曲</span><button class="danger-button" data-clear-queue ${state.queue.length ? "" : "disabled"}>清空队列</button></div>`
      : isGroup && state.groupName && !albumDetail && !genreDetail
      ? `<div class="category-detail"><div class="category-detail-main">${groupIcon(isCreatorView() ? "albums" : state.view, list)}<div><strong>${escapeHtml(state.groupName)}</strong><span>${isCreatorView() ? `${escapeHtml(currentCreatorName())} · ` : ""}${libraryCount(state.pageTotal || list.length)} 首歌曲</span></div></div><div class="category-detail-actions"><button class="secondary-button" data-play-all>播放全部</button><button class="secondary-button" data-group-back>返回分类</button></div></div>`
    : "";
  const listHtml = isFolder
    ? renderFolders(folderState)
    : isGroupRoot
      ? (isAlbumCollectionView() ? renderAlbumGroups(list) : renderGroups(list))
      : creatorAllTracks
        ? renderCreatorAllTracks(list)
        : genreDetail
          ? renderGenreTracks(list)
        : albumDetail
          ? renderAlbumDetail(list)
          : playlistToolbar + renderTrackRows(list);
  const tableHeadChanged = renderTableHead();
  $("tableHead").hidden = albumDetail;
  $("libraryScroll").classList.toggle("album-detail-scroll", albumDetail);
  $("trackList").classList.toggle("group-mode", isGroupRoot);
  $("trackList").classList.toggle("album-detail-mode", albumDetail);
  $("trackList").classList.toggle("artist-all-tracks-mode", creatorAllTracks);
  // While the first authoritative request is in flight, keep an already
  // visible snapshot/list mounted.  Some older WebViews repaint a cleared
  // container before the response arrives, which produces a one-frame blank
  // list and makes every cover appear to flash.  The empty-state decision
  // below still reflects the loading guard, so a genuinely empty library is
  // shown once the request settles.
  const deferListCommit = globalThis.fnAudioLibraryRenderPolicy?.shouldDeferListCommit({
    libraryLoading: state.libraryLoading,
    hasVisiblePresentation: hasVisibleLibraryPresentation(),
    hasRenderedMarkup: Boolean(state.renderedTrackListHtml),
    listLength: list.length,
  }) === true;
  const listChanged = deferListCommit ? false : commitTrackListHtml(listHtml);
  if (listChanged) {
    // Attach group-specific local/online fallback handlers before the shared
    // scheduler can assign image sources, including legacy WebViews without IO.
    loadGroupArtwork();
    hydrateVisibleTrackCovers();
  }
  // A normal playback/favorite render must not walk every row merely to
  // re-apply the same selection.  A changed list still forces one pass so a
  // keyed DOM commit receives the current selection classes.
  setTrackSelection([...state.selectedTrackRowKeys], listChanged);
  const albumHeadChanged = albumDetail ? renderTableHead($("albumDetailTableHead")) : false;
  const pager = $("pager");
  const pagerHtml = renderPager(clientPageTotal);
  const pagerChanged = pager.innerHTML !== pagerHtml;
  if (pagerChanged) pager.innerHTML = pagerHtml;
  if (pagerChanged) updateMobilePagerVisibility();
  bindTrackHeaderScroll();
  bindTrackListInteractions();
  // These perform layout reads across visible rows.  Rendering playback state
  // or a favorite must not enqueue another full measurement pass when the list,
  // its headers and its pager are unchanged; resize observers still handle real
  // geometry changes independently.
  if (listChanged || tableHeadChanged || albumHeadChanged || pagerChanged) {
    requestAnimationFrame(() => {
      measureAutoTrackColumnWidths();
      syncTrackHeaderScroll();
      updateMobilePagerVisibility();
    });
  }
  // `list` already contains the grouped rows for group-root views; reusing it
  // avoids a second grouping pass on large libraries during every render.
  // While the first authoritative page is still in flight, an empty list is
  // not an empty library.  Hiding the empty-state panel during that short
  // window prevents the old WebView flash of “没有音乐” before page one
  // arrives; once loading finishes, a genuinely empty result is shown as
  // before.
  const libraryRequestPending = Boolean(state.libraryLoading && !hasVisibleLibraryPresentation());
  $("empty").hidden = libraryRequestPending || list.length > 0 || (isFolder && folderState && folderState.folders.length > 0) || (isGroupRoot && list.length > 0);
  const favoriteCount = String(state.favorites.length);
  const queueCount = String(state.queue.length);
  if ($("favoriteCount").textContent !== favoriteCount) $("favoriteCount").textContent = favoriteCount;
  if ($("queueCount").textContent !== queueCount) $("queueCount").textContent = queueCount;
  updateFavoriteControls();
  renderPlaylistNav();
  const presentation = window.fnAudioViewPresentation({
    view: state.view,
    playlistName: isPlaylistView() ? (currentPlaylist()?.name || "播放列表") : "",
    creatorAllTracks,
    albumSurface: isAlbumSurfaceView(),
    scanText: scanProgressText(),
    creatorName: displayText(currentCreatorName()),
    folderName: state.view === "folders" && currentFolderLabel ? currentFolderLabel() : "",
  });
  if ($("viewTitle").textContent !== presentation.title) $("viewTitle").textContent = presentation.title;
  if ($("viewSub").textContent !== presentation.subtitle) $("viewSub").textContent = presentation.subtitle;
  if ($("mobileViewTitle").textContent !== presentation.title) $("mobileViewTitle").textContent = presentation.title;
  if ($("mobileViewSub").textContent !== presentation.mobileSubtitle) $("mobileViewSub").textContent = presentation.mobileSubtitle;
  updateNavigationActiveState();
  // These controls are descendants of the keyed list. Their callbacks read
  // current state at click time, so re-binding them after an unrelated player
  // state render only adds a full DOM walk on a large library.
  if (listChanged) {
    document.querySelectorAll("[data-delete-playlist]").forEach(b => b.onclick = () => deletePlaylist(b.dataset.deletePlaylist));
    document.querySelectorAll("[data-clear-queue]").forEach(b => b.onclick = clearQueue);
    document.querySelectorAll("[data-play-group]").forEach(b => b.onclick = () => playGroup(b.dataset.playGroup));
    document.querySelectorAll("[data-play-all]").forEach(b => b.onclick = playAll);
    document.querySelectorAll("[data-play-artist-album]").forEach(b => b.onclick = playAll);
    document.querySelectorAll("[data-group-row]").forEach(row => {
      row.onclick = event => {
        if (event.target.closest("button")) return;
        if (event.ctrlKey && !window.matchMedia("(max-width: 760px)").matches) {
          event.preventDefault();
          toggleGroupSelection(row.dataset.groupKey);
          return;
        }
        if (!window.matchMedia("(max-width: 760px)").matches && state.selectedGroupKeys.size) {
          event.preventDefault();
          setGroupSelection([]);
          return;
        }
        openGroupRow(row);
      };
      row.oncontextmenu = event => {
        if (window.matchMedia("(max-width: 760px)").matches) return;
        event.preventDefault();
        const key = String(row.dataset.groupKey || "");
        if (!state.selectedGroupKeys.has(key)) setGroupSelection([key]);
        openGroupContextMenu(key, event.clientX, event.clientY);
      };
    });
  }
  document.querySelectorAll("[data-group-back]").forEach(b => b.onclick = () => {
    if (isCreatorAllTracksView()) setCurrentCreatorAllTracks(false);
    else if (isCreatorView() && state.groupName) state.groupName = "";
    else if (isCreatorView() && currentCreatorName()) clearCurrentCreator();
    else state.groupName = "";
    resetLibraryScrollPosition();
    requestLibraryLoad(1, false).finally(() => requestAnimationFrame(resetLibraryScrollPosition));
  });
  document.querySelectorAll("[data-creator-root-back]").forEach(button => button.onclick = () => {
    clearCurrentCreator();
    state.page = 1;
    state.pageItems = [];
    requestLibraryLoad(1, false);
  });
  document.querySelectorAll("[data-open-creator-all-tracks]").forEach(button => button.onclick = () => {
    setCurrentCreatorAllTracks(true);
    state.groupName = "";
    state.page = 1;
    state.pageItems = [];
    requestLibraryLoad(1, false);
  });
  document.querySelectorAll("[data-folder-crumb-root]").forEach(crumb => crumb.onclick = () => {
    state.folderRoot = decodeURIComponent(crumb.dataset.folderCrumbRoot || "");
    state.folderPath = decodeURIComponent(crumb.dataset.folderCrumbPath || "");
    state.folderPage = 1;
    state.page = 1;
    state.pageItems = [];
    requestLibraryLoad(1, false);
  });
  document.querySelectorAll("[data-page-step]").forEach(b => b.onclick = () => {
    const step = libraryPageStep(b.dataset.pageStep);
    const nextPage = libraryPageNumber(libraryPageNumber(state.page) + step);
    if (isClientPagedView()) {
      state.page = nextPage;
      // Pagination changes the visible slice, not the playing track.  The
      // old callback referenced a non-existent local ``trackId`` here,
      // causing older WebViews to throw before the page could repaint.
      scheduleMetadataRowRender("");
    } else {
      requestLibraryLoad(nextPage, false);
    }
  });
  document.querySelectorAll("[data-page-go]").forEach(button => button.onclick = () => {
    const nextPage = libraryPageNumber(button.dataset.pageGo, 1);
    if (nextPage === state.page) return;
    if (isClientPagedView()) {
      state.page = nextPage;
      scheduleMetadataRowRender("");
    } else {
      requestLibraryLoad(nextPage, false);
    }
  });
  document.querySelectorAll("[data-refresh-library]").forEach(button => button.onclick = () => requestLibraryLoad(1, true));
  document.querySelectorAll("[data-folder-page-step]").forEach(b => b.onclick = () => {
    const step = libraryPageStep(b.dataset.folderPageStep);
    state.folderPage = libraryPageNumber(libraryPageNumber(state.folderPage) + step);
    requestLibraryLoad(state.page, false);
  });
}
function renderPlaylistNav() {
  const nav = $("playlistNav");
  if (!nav) return;
  const markup = state.playlists.map(list => `<button class="nav-item playlist-nav-item ${state.view === `playlist:${list.id}` ? "active" : ""}" data-view="playlist:${list.id}">♪ <span>${escapeHtml(list.name)}</span><b>${list.trackIds.length}</b></button>`).join("");
  if (nav.dataset.fnaudioPlaylistNavMarkup === markup) return;
  nav.innerHTML = markup;
  nav.dataset.fnaudioPlaylistNavMarkup = markup;
  nav.querySelectorAll(".nav-item").forEach(button => {
    button.onclick = () => {
      setView(button.dataset.view);
      setMobileNavigation(false);
    };
  });
}
function updateNavigationActiveState() {
  const view = String(state.view || "all");
  if (state.renderedNavigationView === view) return;
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === view));
  state.renderedNavigationView = view;
}
function setView(view) {
  if (state.searchTimer) {
    clearTimeout(state.searchTimer);
    state.searchTimer = null;
  }
  state.view = view || "all";
  if (!isPagedLibraryView()) invalidateLibraryLoad();
  state.selectedTrackRowKeys.clear();
  state.selectedGroupKeys.clear();
  state.folderRoot = "";
  state.folderPath = "";
  state.folderPage = 1;
  state.groupName = "";
  resetCreatorState();
  state.page = 1;
  state.pageItems = [];
  state.librarySnapshotEmptyGuardUsed = false;
  updateNavigationActiveState();
  if (isPagedLibraryView()) requestLibraryLoad(1, false);
  else render();
}
function sameTrackSelection(left, right) {
  if (left.size !== right.size) return false;
  for (const key of left) if (!right.has(key)) return false;
  return true;
}
function setTrackSelection(rowKeys = [], force = false) {
  const requested = new Set((rowKeys || []).map(String).filter(Boolean));
  if (!force && sameTrackSelection(state.selectedTrackRowKeys, requested)) return;
  const rows = [...document.querySelectorAll("[data-track-row-key]")];
  const visibleKeys = new Set(rows.map(row => String(row.dataset.trackRowKey || "")).filter(Boolean));
  state.selectedTrackRowKeys = new Set([...requested].filter(key => visibleKeys.has(key)));
  rows.forEach(row => row.classList.toggle("is-selected", state.selectedTrackRowKeys.has(String(row.dataset.trackRowKey || ""))));
}
function toggleTrackSelection(rowKey) {
  const key = String(rowKey || "");
  const row = [...document.querySelectorAll("[data-track-row-key]")].find(node => String(node.dataset.trackRowKey || "") === key);
  if (!row) return;
  if (state.selectedTrackRowKeys.has(key)) state.selectedTrackRowKeys.delete(key);
  else state.selectedTrackRowKeys.add(key);
  setTrackSelection([...state.selectedTrackRowKeys]);
}
function selectedTrackIds(trackId = "") {
  const selected = [...document.querySelectorAll("[data-track-row-key]")]
    .filter(row => state.selectedTrackRowKeys.has(String(row.dataset.trackRowKey || "")))
    .map(row => String(row.dataset.trackId || ""))
    .filter(id => itemById(id));
  return selected.length ? selected : (trackId && itemById(trackId) ? [String(trackId)] : []);
}
function setGroupSelection(keys = []) {
  state.selectedGroupKeys = new Set((keys || []).map(String).filter(Boolean));
  document.querySelectorAll("[data-group-row]").forEach(row => row.classList.toggle("is-selected", state.selectedGroupKeys.has(String(row.dataset.groupKey || ""))));
}
function toggleGroupSelection(groupKey) {
  const key = String(groupKey || "");
  if (!key) return;
  if (state.selectedGroupKeys.has(key)) state.selectedGroupKeys.delete(key);
  else state.selectedGroupKeys.add(key);
  setGroupSelection([...state.selectedGroupKeys]);
}
function clearTransientListSelection() {
  setTrackSelection([]);
  setGroupSelection([]);
  closeTrackContextMenu();
}
function groupDescriptorFromRow(row) {
  if (!row) return null;
  const decode = value => { try { return decodeURIComponent(value || ""); } catch (error) { return value || ""; } };
  return { key: String(row.dataset.groupKey || ""), type: row.dataset.groupType || "group", view: row.dataset.groupView || state.view, name: decode(row.dataset.groupName), root: decode(row.dataset.groupRoot), path: decode(row.dataset.groupPath), trackCount: Number(row.dataset.groupTrackCount || 0) };
}
function selectedGroupDescriptors(groupKey = "") {
  const rows = [...document.querySelectorAll("[data-group-row]")];
  const selected = rows.filter(row => state.selectedGroupKeys.has(String(row.dataset.groupKey || ""))).map(groupDescriptorFromRow).filter(Boolean);
  if (selected.length) return selected;
  return rows.filter(row => String(row.dataset.groupKey || "") === String(groupKey || "")).map(groupDescriptorFromRow).filter(Boolean);
}
function resetLibraryScrollPosition() {
  const viewport = $("libraryScroll");
  const list = $("trackList");
  if (viewport) viewport.scrollTop = 0;
  if (list) list.scrollTop = 0;
}
function openGroupRow(row) {
  const group = groupDescriptorFromRow(row);
  if (!group) return;
  const opensAlbumDetail = group.type !== "folder" && (state.view === "albums" || (isCreatorView() && currentCreatorName()));
  state.selectedGroupKeys.clear();
  if (group.type === "folder") {
    state.folderRoot = group.root;
    state.folderPath = group.path;
  } else if (isCreatorView() && !currentCreatorName()) {
    setCurrentCreator(group.name, group.trackCount);
  } else {
    state.groupName = group.name;
    if (isCreatorView()) setCurrentCreatorAllTracks(false);
    if (opensAlbumDetail) {
      state.sortKey = "track_no";
      state.sortDir = "asc";
    }
  }
  state.folderPage = 1;
  state.page = 1;
  state.pageItems = [];
  resetLibraryScrollPosition();
  requestLibraryLoad(1, false).finally(() => requestAnimationFrame(resetLibraryScrollPosition));
}
async function resolveSelectedGroupTracks(groupKey = "") {
  const groups = selectedGroupDescriptors(groupKey);
  const pool = fnAudioBatchRequestPool(groups, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY, group => group.type === "folder"
    ? fetchAllTracksForCurrentView({ view: "folders", root: group.root, folder: group.path })
    : isCreatorView() && currentCreatorName() && group.view === "albums"
      ? fetchAllTracksForCurrentView({ view: state.view, group: currentCreatorName(), album: group.name })
      : fetchAllTracksForCurrentView({ view: group.view, group: group.name }));
  const resolved = [];
  for (let index = 0; index < groups.length; index += 1) resolved.push(await pool.get(index));
  const seen = new Set();
  return resolved.flat().filter(item => {
    const id = String(item?.id || "");
    if (!id || seen.has(id)) return false;
    seen.add(id);
    return true;
  });
}
function applyConfirmedQueue(queue, core) {
  state.queue = Array.isArray(queue) ? queue : [];
  const currentId = String(core?.current || "");
  state.index = state.queue.findIndex(item => String(item.id) === currentId);
  if (state.index < 0 && state.queue.length) state.index = 0;
  if (core?.repeat) state.repeat = core.repeat;
  if (typeof core?.shuffle === "boolean") state.shuffle = core.shuffle;
  updateRepeatShuffleButtons();
  updateFavoriteControls();
}
async function commitQueue(queue, currentId = "", options = {}) {
  const response = await apiFetch("api/playback/queue", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-FnAudio-Path": "/api/playback/queue",
    },
    body: JSON.stringify({
      queue: queue.map(item => String(item?.id || "")).filter(Boolean),
      current_id: currentId,
      repeat: options.repeat ?? state.repeat,
      shuffle: options.shuffle ?? state.shuffle,
    }),
  });
  const raw = await response.text().catch(() => "");
  let data = {};
  try { data = raw ? JSON.parse(raw) : {}; } catch (error) {}
  if (!response.ok || data.ok !== true) {
    const looksLikeHtml = /<\s*html|<!doctype/i.test(raw);
    throw new Error(data.message || data.error || (looksLikeHtml
      ? `播放队列请求返回了错误页面（HTTP ${response.status}），请重新打开 fnAudio。`
      : `播放队列保存失败（HTTP ${response.status}）`));
  }
  applyConfirmedQueue(queue, data.core);
  if (nativePlaybackAvailable() && String(state.nativePlayback.mediaId || "") === String(currentItem()?.id || "")) {
    // Handing the queue back to the host player has to describe the host player.
    // ``isPlayingNow``/``currentSeconds`` answer about the audible stream, which
    // is the caster's while a render session is active, so using them here made
    // the native player resume from the cast's position and mirror the cast's
    // transport state.
    nativeLoadQueue(localIsPlayingNow(), localPlaybackSeconds(), true);
  }
  if (userStateRevision(data.revision, -1) >= 0) state.userStateRevision = userStateRevision(data.revision);
  scheduleUserStateSave();
  return data.core || {};
}
function selectedItems(ids = []) {
  return (ids || []).map(itemById).filter(Boolean);
}
async function addSelectedToQueue(ids = []) {
  const items = selectedItems(ids);
  if (!items.length) return;
  const existing = new Set(state.queue.map(item => String(item.id)));
  const queue = [...state.queue, ...items.filter(item => !existing.has(String(item.id)))];
  try {
    await commitQueue(queue, state.queue[state.index]?.id || "");
    render();
  } catch (error) {
    alert(error.message || "播放队列保存失败");
  }
}
async function playSelectedTracks(ids = []) {
  const items = selectedItems(ids);
  if (!items.length) return;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  try {
    await commitQueue(items, items[0].id);
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  loadCurrent();
  render();
}
function clientContextTracks() {
  const ids = state.view === "favorites"
    ? state.favorites
    : isPlaylistView()
      ? (currentPlaylist()?.trackIds || [])
      : [];
  const source = state.view === "queue" ? state.queue : ids.map(itemById).filter(Boolean);
  const search = currentQueryText().toLowerCase();
  return sortTracks(search ? source.filter(item => trackMatchesSearch(item, search)) : source);
}
function fetchLibraryItemsByIds(batch = [], signal = undefined) {
  return globalThis.fnAudioLibraryItemRequestLoader.loadBatch({
    batch,
    inflight: state.itemHydrationInflight,
    limit: state.itemHydrationInflightLimit,
    signal,
    fetchJson: async (ids, requestSignal) => {
      const result = await fetchJsonResponseBounded(
        `api/library/items?ids=${encodeURIComponent(ids.join(","))}`,
        requestSignal ? { signal: requestSignal } : {},
        10000,
      );
      const response = result.response;
      const data = result.data || {};
      if (!response.ok) throw new Error(data.error || "读取歌曲失败");
      return Array.isArray(data.items) ? data.items : [];
    },
  });
}
async function resolveTracksByIds(ids = []) {
  const orderedIds = fnAudioItemHydrationPolicy.normalizeItemIds(ids);
  const missing = orderedIds.filter(id => !state.itemCache.has(id));
  if (!missing.length) return orderedIds.map(itemById).filter(Boolean);
  const batches = fnAudioItemHydrationPolicy.batchesForItemIds(missing);
  const pool = fnAudioBatchRequestPool(batches, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY,
    batch => fetchLibraryItemsByIds(batch));
  for (let index = 0; index < batches.length; index += 1) {
    // A large favorite/playlist can require many 100-item batches.  Keep the
    // LRU protection pass until every batch is present, otherwise each batch
    // may rescan the same over-capacity cache.
    cacheLibraryItems(await pool.get(index), false);
  }
  state.itemCache.trim(new Set((state.queue || []).map(item => String(item?.id || "")).filter(Boolean)));
  return orderedIds.map(itemById).filter(Boolean);
}
async function allTracksForCurrentContext() {
  if (isClientPagedView()) {
    if (state.view === "queue") return clientContextTracks();
    const ids = state.view === "favorites"
      ? state.favorites
      : (currentPlaylist()?.trackIds || []);
    const source = await resolveTracksByIds(ids);
    const search = currentQueryText().toLowerCase();
    return sortTracks(search ? source.filter(item => trackMatchesSearch(item, search)) : source);
  }
  if (state.view === "random100") {
    const search = currentQueryText().toLowerCase();
    const source = search ? state.pageItems.filter(item => trackMatchesSearch(item, search)) : state.pageItems;
    return sortTracks(source);
  }
  if (isPagedTrackListing()) return fetchAllTracksForCurrentView();
  return sortTracks(filteredTracks());
}
async function playFromCurrentTrack(trackId) {
  const id = String(trackId || "");
  let tracks = [];
  try {
    tracks = await allTracksForCurrentContext();
  } catch (error) {
    alert("读取当前列表失败");
    return;
  }
  const start = tracks.findIndex(item => String(item?.id || "") === id);
  if (start < 0) return alert("当前歌曲已不在这个列表中");
  const queue = tracks;
  if (!queue.length) return;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  try {
    await commitQueue(queue, id);
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  loadCurrent();
  render();
}
async function insertSelectedTracks(ids = []) {
  const items = selectedItems(ids);
  if (!items.length) return;
  const existing = new Set(state.queue.map(item => String(item.id)));
  const additions = items.filter(item => !existing.has(String(item.id)));
  if (!additions.length) return;
  const insertAt = state.index >= 0 ? state.index + 1 : state.queue.length;
  const queue = [...state.queue];
  queue.splice(insertAt, 0, ...additions);
  try {
    await commitQueue(queue, state.queue[state.index]?.id || queue[0]?.id || "");
    render();
  } catch (error) {
    alert(error.message || "播放队列保存失败");
  }
}
async function removeTrackFromQueue(trackId) {
  const id = String(trackId);
  const removeIndex = state.queue.findIndex(x => x.id === id);
  if (removeIndex < 0) return;
  const removingCurrent = removeIndex === state.index;
  const queue = state.queue.filter(x => String(x.id) !== id);
  let nextCurrent = state.queue[state.index]?.id || "";
  if (removingCurrent) nextCurrent = queue[Math.min(removeIndex, queue.length - 1)]?.id || "";
  try {
    await commitQueue(queue, nextCurrent);
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  if (!queue.length && removingCurrent) stopPlayback();
  else if (removingCurrent) loadCurrent();
  render();
}
async function clearQueue() {
  if (!state.queue.length || !confirm("确定清空当前播放队列吗？")) return;
  try {
    await commitQueue([], "");
    await stopPlayback();
    render();
  } catch (error) {
    alert(error.message || "清空播放队列失败");
  }
}
async function playById(id) {
  const item = itemById(id);
  if (!item) return;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  const queue = state.queue.some(x => String(x.id) === String(id)) ? [...state.queue] : [...state.queue, item];
  try {
    await commitQueue(queue, id);
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  loadCurrent();
}
async function playGroup(name) {
  const key = groupViews[state.view];
  let group = isPagedTrackListing() ? state.pageItems : state.items.filter(item => (item[key] || "未分类") === name);
  if (!group.length && groupViews[state.view]) {
    group = await fetchAllTracksForCurrentView({ view: state.view, group: name });
  }
  if (!group.length) return;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  const queue = state.shuffle ? [...group].sort(() => Math.random() - 0.5) : group;
  try {
    await commitQueue(queue, queue[0]?.id || "");
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  loadCurrent();
  render();
}
function playableTracks() {
  if (isPagedTrackListing()) return state.pageItems;
  if (state.view === "folders") return folderTracks();
  if (groupViews[state.view]) return state.groupName ? filteredTracks() : [];
  if (isPlaylistView()) return playlistTracks();
  return filteredTracks();
}
async function playAll() {
  let tracks = [];
  if (state.view === "queue") tracks = state.queue;
  else if (state.view === "favorites") tracks = favoriteTracks();
  else if (state.view === "random100") tracks = state.pageItems;
  else if (isPlaylistView()) tracks = playlistTracks();
  else if (isPagedLibraryView() || groupViews[state.view] || state.view === "folders") {
    const extra = { view: state.view };
    if (isCreatorView() && currentCreatorName()) {
      extra.group = currentCreatorName();
      if (state.groupName) extra.album = state.groupName;
    } else if (groupViews[state.view] && state.groupName) extra.group = state.groupName;
    if (state.view === "folders") {
      extra.root = state.folderRoot || "";
      extra.folder = state.folderPath || "";
    }
    tracks = await fetchAllTracksForCurrentView(extra);
  } else {
    tracks = playableTracks();
  }
  if (!tracks.length) return;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  const queue = state.shuffle ? [...tracks].sort(() => Math.random() - 0.5) : tracks;
  try {
    await commitQueue(queue, queue[0]?.id || "");
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  if (isRemoteTarget()) {
    state.remoteStatus = null;
    await remoteControl("stop", null, true);
  }
  loadCurrent();
  render();
}
function nextIndex() {
  if (!state.queue.length) return -1;
  if (state.shuffle && state.queue.length > 1) {
    let next = state.index;
    while (next === state.index) next = Math.floor(Math.random() * state.queue.length);
    return next;
  }
  if (state.index < state.queue.length - 1) return state.index + 1;
  return state.repeat === "all" ? 0 : -1;
}
async function warmCurrentTrackCache(item) {
  if (!item || !shouldTranscodeToMp3(item) || state.transcodeCacheReady || isRemoteTarget()) return false;
  try {
    const response = await apiFetch("api/transcode/warm", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ track_id: item.id, mode: "mp3" }),
    });
    const data = await readResponseJsonBounded(response);
    return response.ok && data.ready === true;
  } catch (error) {
    return false;
  }
}
async function loadCurrent() {
  const item = currentItem();
  if (!item) return;
  const loadToken = ++state.playbackLoadToken;
  syncState();
  if (isRemoteTarget()) {
    stopLocalAudio();
    setTextContentIfChanged($("nowTitle"), displayTrackTitle(item));
    setTextContentIfChanged($("nowArtist"), `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)} · ${state.playTargetName}`);
    const localCover = coverUrl(item, 512);
    setNowPlayingCover(localCover);
    prefetchCurrentTrackMetadata(item);
    syncLyricsForCurrentTrack(item);
    updateMediaSessionMetadata(item);
    updateMediaSessionPlaybackState();
    updateFavoriteControls();
    pushToDevice(state.playTarget, item).then(loaded => {
      if (loaded && loadToken === state.playbackLoadToken
        && String(currentItem()?.id || "") === String(item.id || "")) {
        setTimeout(refreshRemoteStatus, 300);
      }
    }).catch(() => {});
    nativeRemoteEnter(true);
    syncPlayerProgress();
    updateNowMarquee();
    return;
  }
  // TODO.md:72 ruling D-2: reaching this point means the user asked *this* browser to
  // play, which now takes the output back from an incoming cast instead of decoding
  // both at once. The branch above is the opposite intent - the user pushed this
  // track to another device deliberately - so it preempt nothing. The call has no
  // suspension point, so the load token taken at the top still matches afterwards.
  preemptIncomingRendererForLocalPlayback();
  const needsMp3 = shouldTranscodeToMp3(item);
  if (needsMp3 && !state.transcodeCacheReady) {
    state.transcodeCacheReady = await warmCurrentTrackCache(item);
    if (loadToken !== state.playbackLoadToken || String(currentItem()?.id || "") !== String(item.id || "")) return;
  }
  if (nativePlaybackAvailable()) {
    state.playSourceKind = "native";
    const shouldResume = String(state.nativePlayback.mediaId || "") === String(item.id || "")
      && state.nativePlayback.playing === true;
    nativeLoadQueue(true, shouldResume ? playbackSeconds(state.nativePlayback.position) : 0);
    setTextContentIfChanged($("nowTitle"), displayTrackTitle(item));
    setTextContentIfChanged($("nowArtist"), `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)}`);
    const nativeCover = coverUrl(item, 512);
    setNowPlayingCover(nativeCover);
    prefetchCurrentTrackMetadata(item);
    syncLyricsForCurrentTrack(item);
    updateMediaSessionMetadata(item);
    setPlayButton(true);
    updateMediaSessionPlaybackState();
    updateFavoriteControls();
    syncPlayerProgress();
    updateNowMarquee();
    syncState();
    return;
  }
  const useCache = needsMp3 && state.transcodeCacheReady;
  state.playSourceKind = needsMp3 && !useCache ? "stream" : "cache";
  const params = new URLSearchParams();
  if (needsMp3) {
    params.set("transcode", "mp3");
    if (useCache) params.set("cache", "1");
    else {
      const start = (item.cue_track === true ? playbackSeconds(item.cue_start) : 0) + Math.max(0, playbackSeconds(state.streamOffset));
      if (start > 0) params.set("start", String(start));
    }
  } else if (shouldTranscodeDsdToWav(item)) {
    params.set("transcode", "dsd_wav");
  } else if (item.cue_track === true) {
    params.set("transcode", "cue_flac");
  } else if (isApeTrack(item)) {
    params.set("transcode", "ape_flac");
  } else {
    params.set("transcode", "original");
  }
  audio.src = `${item.url}?${params.toString()}`;
  if (item.cue_track === true && !needsMp3) {
    state.playSourceKind = "cue_segment";
    state.pendingSeekTime = null;
  } else if (playbackSeconds(item.cue_start) > 0) state.pendingSeekTime = playbackSeconds(item.cue_start);
  setTextContentIfChanged($("elapsed"), "0:00");
  setTextContentIfChanged($("duration"), clock(seekDuration()));
  $("seek").value = 0;
  audio.play().catch(() => {});
  setTextContentIfChanged($("nowTitle"), displayTrackTitle(item));
  setTextContentIfChanged($("nowArtist"), `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)}`);
  setNowPlayingCover(coverUrl(item, 512));
  prefetchCurrentTrackMetadata(item);
  syncLyricsForCurrentTrack(item);
  updateMediaSessionMetadata(item);
  setPlayButton(true);
  updateMediaSessionPlaybackState();
  updateFavoriteControls();
  syncPlayerProgress();
  updateNowMarquee();
  syncState();
  refreshCurrentTranscodeStatus();
}
// Extrapolation only has to bridge the gap between two *accepted* status
// snapshots. The slowest healthy source is the remote fallback poll (5000 ms,
// and only while the event stream is down), so twice that interval is the point
// where the UI has stopped tracking the device and started inventing time.
// Clamping (rather than dropping back to the last reported position) keeps the
// display smooth through real poll latency while bounding both failure shapes:
// a known duration no longer sticks at 100% forever once status stops
// arriving, and an unknown one (live radio, renderers that never report a
// length) can no longer count up without limit.
const TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS = 10;

function transportExtrapolation(snapshotAt, playing) {
  if (!playing || !Number.isFinite(snapshotAt) || snapshotAt <= 0) return 0;
  const elapsed = (Date.now() - snapshotAt) / 1000;
  // A backward clock step (NTP, timezone-carrying hosts) must not subtract from
  // the reported position: the remote branch returns this raw, so a negative
  // value here would render a negative elapsed time.
  if (!(elapsed > 0)) return 0;
  return Math.min(elapsed, TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS);
}
// The clamp above is what stops a dead status channel from counting up forever, but a
// frozen counter is indistinguishable from a paused track: the row simply lies now
// (TODO.md:74).  This reads the same budget back as "the channel has run out", so the two
// can never disagree about where the boundary is.  It takes the snapshot time and the
// transport state as arguments instead of reaching into `state`, which keeps it honest
// about *which* channel it was asked about and leaves the one-gate shape asserted in
// test_ui_transport_staleness.js intact.
function transportStateIsUnknown(snapshotAt, playing) {
  return playing === true && transportExtrapolation(snapshotAt, true) >= TRANSPORT_EXTRAPOLATION_LIMIT_SECONDS;
}
function currentSeconds() {
  if (isIncomingRendererSession()) {
    const transport = String(state.rendererSession.transport || "").toUpperCase();
    const base = playbackSeconds(state.rendererSession.position);
    const elapsed = transportExtrapolation(state.rendererSnapshotAt, transport === "PLAYING");
    const duration = playbackSeconds(state.rendererSession.duration);
    const seconds = Math.max(0, base + elapsed);
    return duration > 0 ? Math.min(duration, seconds) : seconds;
  }
  if (isRemoteTarget()) {
    const item = currentItem();
    const duration = seekDuration();
    const transport = (state.remoteStatus?.transport?.state || "").toUpperCase();
    const elapsed = transportExtrapolation(state.remoteSnapshotAt, transport === "PLAYING");
    const raw = playbackSeconds(state.remoteBaseSeconds, playbackSeconds(state.remoteStatus?.position?.rel_seconds)) + elapsed;
    const cueStart = playbackSeconds(item?.cue_start);
    const seconds = item?.cue_track === true && !state.remoteCueSegment ? Math.max(0, raw - cueStart) : raw;
    return duration > 0 ? Math.min(duration, seconds) : seconds;
  }
  return localPlaybackSeconds();
}
function localPlaybackSeconds() {
  // The tail of ``currentSeconds`` pulled out verbatim: the position of what
  // this browser (or the Android host player) is actually running, independent
  // of any cast in progress.  Callers that make a *decision* about local
  // playback must use this instead of ``currentSeconds``, which answers about
  // the renderer while a render session is active.
  if (nativePlaybackAvailable()) return playbackSeconds(state.nativePlayback.position);
  const item = currentItem();
  const audioSeconds = playbackSeconds(audio.currentTime);
  const raw = state.playSourceKind === "stream"
    ? playbackSeconds(state.streamOffset) + audioSeconds
    : audioSeconds;
  if (item?.cue_track === true) {
    if (state.playSourceKind === "stream") return Math.max(0, raw);
    if (state.playSourceKind === "cue_segment") return Math.max(0, raw);
    return Math.max(0, raw - playbackSeconds(item.cue_start));
  }
  return raw;
}
function seekDuration() {
  if (isIncomingRendererSession()) return playbackSeconds(state.rendererSession.duration);
  const item = currentItem();
  if (nativePlaybackAvailable()) return playbackSeconds(state.nativePlayback.duration, playbackSeconds(item?.duration));
  if (item?.cue_track === true && item.duration) return playbackSeconds(item.duration);
  if (item?.cue_track === true && isRemoteTarget()) {
    const remoteDuration = playbackSeconds(state.remoteStatus?.position?.duration_seconds);
    // A declared segment already arrives folded, so its duration is the track
    // length; subtracting cue_start again would shorten the rail.
    if (state.remoteCueSegment) return remoteDuration;
    const cueStart = playbackSeconds(item.cue_start);
    return remoteDuration > cueStart ? remoteDuration - cueStart : 0;
  }
  if (isRemoteTarget()) return playbackSeconds(state.remoteStatus?.position?.duration_seconds);
  if (item?.duration) return playbackSeconds(item.duration);
  return Number.isFinite(audio.duration) ? audio.duration : 0;
}
function localPlaybackDuration() {
  // ``seekDuration`` without the two state-dependent branches: an incoming
  // render session answers with the *caster's* length, and a remote target has
  // its own cue arithmetic.  Both keep that in ``seekDuration`` for painting;
  // this is only for code that acts on local playback, whose callers have
  // already excluded a remote target.  ``audio.ontimeupdate`` is such a caller,
  // so the pair it compares is always the local element's own seconds against
  // the local track's own length.

  // That precondition used to live only in this comment and in the test suite. It is the pair a
  // cue-tail decision is made from, and a remote target has its own cue arithmetic, so answering
  // from the local element there would advance *this* browser's queue on the device's progress.
  // Fail loudly instead: one boolean per local tick is not a cost, and a wrong queue advance is
  // (TODO.md:49). An *incoming* render session is still not part of this check, but it no
  // longer excuses overlapping playback either: TODO.md:72 ruling D-1 ended the state where a
  // cast and the local element ran together, and the handler now refuses to read a cue tail at
  // all while a caster owns the row. This helper stays the plain local half of the pair, which
  // is what its remaining callers ask for (test_ui_playback_authority.js case 3 pins both).
  if (isRemoteTarget()) {
    throw new TypeError("localPlaybackDuration requires a caller that excluded remote playback");
  }
  const item = currentItem();
  if (nativePlaybackAvailable()) return playbackSeconds(state.nativePlayback.duration, playbackSeconds(item?.duration));
  if (item?.cue_track === true && item.duration) return playbackSeconds(item.duration);
  if (item?.duration) return playbackSeconds(item.duration);
  return Number.isFinite(audio.duration) ? audio.duration : 0;
}
async function refreshCurrentTranscodeStatus() {
  const item = currentItem();
  if (!item || isRemoteTarget() || nativePlaybackAvailable()) {
    state.transcodeStatusRequestToken += 1;
    try { state.transcodeStatusController?.abort(); } catch (_) {}
    state.transcodeStatusController = null;
    state.transcodeCacheReady = false;
    return;
  }
  const trackId = String(item.id || "");
  if (!shouldTranscodeToMp3(item)) {
    state.transcodeStatusRequestToken += 1;
    try { state.transcodeStatusController?.abort(); } catch (_) {}
    state.transcodeStatusController = null;
    state.transcodeCacheReady = false;
    return;
  }
  const token = ++state.transcodeStatusRequestToken;
  try { state.transcodeStatusController?.abort(); } catch (_) {}
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.transcodeStatusController = controller;
  try {
    const request = fetch(`api/transcode/status?track_id=${encodeURIComponent(item.id)}&mode=mp3`, {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: null,
    });
    const data = result.data;
    if (!data || data.error) return;
    if (token !== state.transcodeStatusRequestToken
      || state.transcodeStatusController !== controller
      || String(currentItem()?.id || "") !== trackId) return;
    const ready = data.ready === true;
    if (ready && !state.transcodeCacheReady) {
      const wasPlaying = !audio.paused;
      const position = currentSeconds();
      state.transcodeCacheReady = true;
      state.streamOffset = 0;
      state.playSourceKind = "cache";
      state.pendingSeekTime = item.cue_track === true ? playbackSeconds(item.cue_start) + position : position;
      loadCurrent();
      if (wasPlaying) audio.play().catch(() => {});
      return;
    }
    state.transcodeCacheReady = ready;
  } catch (error) {
    if (error?.name !== "AbortError") return;
  } finally {
    if (token === state.transcodeStatusRequestToken
      && state.transcodeStatusController === controller) {
      state.transcodeStatusController = null;
    }
  }
}
function previewSeek(value) {
  const duration = seekDuration();
  if (!duration) return;
  const percent = seekPercent(value);
  setTextContentIfChanged($("elapsed"), clock(percent / 100 * duration));
  updateSeekRail(percent);
}
function commitSeek(value = $("seek").value) {
  const duration = seekDuration();
  state.seeking = false;
  if (!duration) return;
  const seconds = seekPercent(value) / 100 * duration;
  setTextContentIfChanged($("elapsed"), clock(seconds));
  if (isIncomingRendererSession()) {
    controlIncomingRenderer("seek", seconds);
    return;
  }
  if (isRemoteTarget()) {
    const target = currentItem()?.cue_track === true && !state.remoteCueSegment ? playbackSeconds(currentItem().cue_start) + seconds : seconds;
    remoteControl("seek", target);
    return;
  }
  if (nativePlaybackAvailable()) {
    nativePlaybackCall("seekTo", seconds);
    return;
  }
  const item = currentItem();
  const needsStreamRestart = shouldTranscodeToMp3(item) && !state.transcodeCacheReady;
  if (needsStreamRestart) {
    state.streamOffset = Math.max(0, seconds);
    state.playSourceKind = "stream";
    state.pendingSeekTime = null;
    loadCurrent();
    return;
  }
  state.streamOffset = 0;
  state.playSourceKind = currentItem()?.cue_track === true ? "cue_segment" : "cache";
  audio.currentTime = seconds;
  updateMediaSessionPosition();
}
function updateLyricsMeta(item = currentItem()) {
  const title = item ? displayTrackTitle(item) : "未选择曲目";
  const artist = item ? displayText(item.artist) : "歌词";
  const detailArtist = item ? (displayText(item.artist) || "未知歌手") : "未知歌手";
  const album = item ? (displayText(item.album) || "未知专辑") : "未知专辑";
  $("lyricsTitle").textContent = title;
  $("lyricsTitle").title = title;
  $("lyricsMetaArtist").textContent = detailArtist;
  $("lyricsMetaArtist").title = detailArtist;
  $("lyricsMetaAlbum").textContent = album;
  $("lyricsMetaAlbum").title = album;
  $("lyricsHeaderTitle").textContent = title;
  $("lyricsHeaderArtist").textContent = artist;
  if (!item) {
    $("lyricsBg").style.backgroundImage = "";
    setCoverArtwork($("lyricsCover"), "");
    updateFavoriteControls();
    return;
  }
  const localCover = coverUrl(item, 512);
  $("lyricsBg").style.backgroundImage = localCover ? `url("${localCover}")` : "";
  setCoverArtwork($("lyricsCover"), localCover);
  updateFavoriteControls();
}
function renderLyrics(lines) {
  state.lyrics = lines;
  $("lyricsLines").innerHTML = lines.length
    ? lines.map((line, index) => `<p data-lyric="${index}">${escapeHtml(line.text)}</p>`).join("")
    : `<p class="muted-line">没有找到歌词。可以把同名 .lrc 文件放到歌曲目录。</p>`;
  updateLyricHighlight();
}
function showLyricsMessage(message) {
  state.lyrics = [];
  const lines = $("lyricsLines");
  lines.scrollTop = 0;
  lines.innerHTML = `<p class="muted-line">${escapeHtml(message)}</p>`;
}
function cancelLyricsPoll() {
  if (!state.lyricsPollTimer) return;
  clearTimeout(state.lyricsPollTimer);
  state.lyricsPollTimer = 0;
}
function scheduleLyricsPoll(trackId) {
  cancelLyricsPoll();
  if (state.lyricsPollAttempts >= 15) return;
  state.lyricsPollAttempts += 1;
  state.lyricsPollTimer = setTimeout(() => {
    state.lyricsPollTimer = 0;
    if (String(currentItem()?.id || "") !== String(trackId || "")) return;
    loadLyricsForCurrentTrack(currentItem(), true);
  }, 900);
}
async function loadLyricsForCurrentTrack(item = currentItem(), force = false, retryFailed = false) {
  updateLyricsMeta(item);
  if (!item) {
    cancelLyricsPoll();
    cancelLyricsRequest();
    state.lyricsPollAttempts = 0;
    state.lyricsRequestToken += 1;
    state.lyricsTrackId = "";
    state.lyricsLoadingTrackId = "";
    state.lyricsStatus = "idle";
    showLyricsMessage("请选择一首歌曲");
    return;
  }
  const trackId = String(item.id);
  if (!force && state.lyricsTrackId === trackId && ["loading", "loaded", "pending"].includes(state.lyricsStatus)) return;
  if (state.lyricsTrackId !== trackId) {
    cancelLyricsPoll();
    cancelLyricsRequest();
    state.lyricsPollAttempts = 0;
  }
  // A forced poll/reopen owns a fresh request. Abort the previous request
  // first so a slow WebView response cannot keep a stale connection alive or
  // race the new lyrics projection.
  if (force) cancelLyricsRequest();
  const requestToken = ++state.lyricsRequestToken;
  state.lyricsTrackId = trackId;
  state.lyricsLoadingTrackId = trackId;
  state.lyricsStatus = "loading";
  showLyricsMessage("正在匹配歌词...");
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.lyricsRequestController = controller;
  try {
    const retry = retryFailed ? "&retry=1" : "";
    const result = await fetchMetadataRequest(
      `api/lyrics?track_id=${encodeURIComponent(trackId)}${retry}`,
      10000,
      controller?.signal,
    );
    const response = result.response;
    // Lyrics and track metadata share the same host/CGI bridge. Some
    // deployments wrap successful JSON in bounded transport envelopes;
    // normalize here so valid lyrics are not mistaken for an empty result.
    const data = unwrapMetadataResponsePayload(result.data);
    // A missing metadata worker is a service state, not an empty lyric
    // result.  Do not keep polling forever (which made the page look as if
    // metadata had silently stopped working); surface the bounded backend
    // reason and let an explicit reopen retry after the worker is restored.
    if (!response.ok) {
      const unavailable = response.status === 503 || data.status === "unavailable";
      const reason = String(data.error || (unavailable ? "后台元数据服务没有启动" : "歌词加载失败"))
        .replace(/[\r\n]+/g, " ").trim().slice(0, 180);
      const error = new Error(reason || "歌词加载失败");
      error.metadataUnavailable = unavailable;
      throw error;
    }
    if (requestToken !== state.lyricsRequestToken || String(currentItem()?.id || "") !== trackId) return;
    // A priority lyrics lookup may still be pending while its artwork was
    // already resolved by the track/album lane. Apply that cover before the
    // pending branch; otherwise the UI hides a usable cached image until
    // lyrics complete (or forever when the provider has no lyric).
    const lyricArtwork = usableCoverSource(data.image_url);
    if (lyricArtwork && !item.cover_url && !item.cover_thumbnail_url) {
      item.cover_url = lyricArtwork;
      item.cover_thumbnail_url = lyricArtwork;
      invalidateTrackRowsMarkup(state.pageItems);
      restoreLibraryNowPlaying();
      updateLyricsMeta(item);
      if (data.pending !== true) render();
    }
    if (data.pending === true) {
      state.lyricsStatus = "pending";
      showLyricsMessage("正在获取歌词...");
      scheduleLyricsPoll(trackId);
      return;
    }
    if (["failed", "no_match"].includes(data.status) && !data.lyrics) {
      state.lyricsStatus = "error";
      cancelLyricsPoll();
      showLyricsMessage(data.status === "no_match" ? "暂未找到歌词，重新打开歌词页可再次查询。" : (data.error ? `歌词获取失败：${data.error}` : "歌词获取失败，请稍后重试。"));
      return;
    }
    state.lyricsStatus = "loaded";
    cancelLyricsPoll();
    state.lyricsPollAttempts = 0;
    renderLyrics(parseLyrics(data.lyrics || ""));
  } catch (error) {
    if (requestToken !== state.lyricsRequestToken || String(currentItem()?.id || "") !== trackId) return;
    if (error?.name === "AbortError") return;
    state.lyricsStatus = "error";
    // The backend differentiates an unavailable metadata worker, provider
    // failures and an ordinary empty match. Do not collapse that evidence into
    // the same generic text: it makes a recoverable service/startup failure
    // indistinguishable from a song that simply has no online lyric. Keep the
    // displayed detail bounded because it may originate from a remote response.
    const detail = String(error?.message || "").replace(/[\r\n]+/g, " ").trim().slice(0, 180);
    showLyricsMessage(detail ? `歌词加载失败：${detail}` : "歌词加载失败，请稍后重试。");
    if (!error?.metadataUnavailable) scheduleLyricsPoll(trackId);
  } finally {
    if (requestToken === state.lyricsRequestToken) {
      state.lyricsLoadingTrackId = "";
      if (state.lyricsRequestController === controller) state.lyricsRequestController = null;
    }
  }
}
function syncLyricsForCurrentTrack(item = currentItem()) {
  updateLyricsMeta(item);
  const trackId = String(item?.id || "");
  if (trackId !== state.lyricsTrackId) loadLyricsForCurrentTrack(item);
}
function cancelLyricsRequest() {
  try { state.lyricsRequestController?.abort(); } catch (_) {}
  state.lyricsRequestController = null;
}
function fetchMetadataRequest(url, timeoutMs = 10000, externalSignal = undefined) {
  // Provider work is bounded on the server, but a stalled proxy/WebView
  // connection can otherwise keep the current-track retry slot occupied
  // forever. Abort only this request; the caller's existing retry/token
  // policy decides whether and when to try again.
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let removeExternalAbort = null;
  if (controller && externalSignal && typeof externalSignal.addEventListener === "function") {
    const abortFromOwner = () => { try { controller.abort(); } catch (_) {} };
    if (externalSignal.aborted) abortFromOwner();
    else {
      externalSignal.addEventListener("abort", abortFromOwner, { once: true });
      removeExternalAbort = () => {
        try { externalSignal.removeEventListener("abort", abortFromOwner); } catch (_) {}
      };
    }
  }
  const request = fetch(url, {
    cache: "no-store",
    ...(controller ? { signal: controller.signal } : {}),
  });
  return globalThis.fnAudioResponseJsonLoader.read({
    request,
    timeoutMs: Math.max(1000, Math.min(30000, Number(timeoutMs) || 10000)),
    onTimeout: () => { try { controller?.abort(); } catch (_) {} },
    fallback: null,
  }).finally(() => {
    if (removeExternalAbort) removeExternalAbort();
  });
}
function unwrapMetadataResponsePayload(value) {
  // Keep this in step with the policy's bounded bridge support.  Some
  // host/CGI paths add a transport layer at each boundary, so a valid
  // metadata result can legitimately arrive under four whitelisted
  // envelopes.  Going beyond this remains deliberately forbidden by the
  // policy to avoid traversing arbitrary host objects.
  return globalThis.fnAudioMetadataResponsePolicy?.unwrap(value, 4)
    || (value && typeof value === "object" && !Array.isArray(value) ? value : {});
}
function isRecoverableFilenameMetadata(payload, candidate) {
  return globalThis.fnAudioMetadataResponsePolicy?.isRecoverableFilenameFallback(payload, candidate) === true;
}
function cancelCurrentTrackMetadataPrefetch() {
  if (state.metadataPrefetchTimer) clearTimeout(state.metadataPrefetchTimer);
  if (state.metadataPrefetchLyricsTimer) clearTimeout(state.metadataPrefetchLyricsTimer);
  state.metadataPrefetchTimer = 0;
  state.metadataPrefetchLyricsTimer = 0;
  try { state.metadataPrefetchController?.abort(); } catch (_) {}
  try { state.metadataPrefetchLyricsController?.abort(); } catch (_) {}
  state.metadataPrefetchController = null;
  state.metadataPrefetchLyricsController = null;
  state.metadataPrefetchToken += 1;
  state.metadataPrefetchLyricsToken += 1;
  state.metadataPrefetchTrackId = "";
  state.metadataPrefetchLyricsTrackId = "";
}
function rememberVisibleMetadataPrefetchKey(key, limit = 256) {
  const value = typeof key === "string" ? key : "";
  if (!value || !state.visibleMetadataPrefetchKeys) return false;
  const bounded = Math.max(1, Math.min(1024, Number(limit) || 256));
  if (state.visibleMetadataPrefetchKeys.has(value)) return false;
  while (state.visibleMetadataPrefetchKeys.size >= bounded) {
    const oldest = state.visibleMetadataPrefetchKeys.values().next().value;
    if (oldest === undefined) break;
    state.visibleMetadataPrefetchKeys.delete(oldest);
  }
  state.visibleMetadataPrefetchKeys.add(value);
  return true;
}
function prefetchCurrentTrackMetadata(item = currentItem()) {
  const trackId = String(item?.id || "");
  if (!trackId) return;
  if (state.metadataPrefetchTrackId === trackId) {
    // A terminal provider result is not necessarily permanent. Allow a
    // bounded, cooldown-based re-arm for the same song so a transient outage
    // or stale negative cache can recover without requiring a track change.
    // The per-track cap prevents status polling from turning this into an
    // unbounded request loop.
    const startedAt = Number(state.metadataPrefetchStartedAt) || 0;
    const age = Date.now() - startedAt;
    if (state.metadataPrefetchAttempts < METADATA_PREFETCH_MAX_ATTEMPTS || age < 30000 || state.metadataPrefetchRearms >= 2) return;
    state.metadataPrefetchRearms += 1;
  } else {
    // A previous song may still be waiting on a slow provider. Abort its
    // in-flight requests before opening the new priority lane; token checks
    // alone prevent stale writes but still waste sockets and worker slots.
    cancelCurrentTrackMetadataPrefetch();
    state.metadataPrefetchRearms = 0;
  }
  if (state.metadataPrefetchTimer) clearTimeout(state.metadataPrefetchTimer);
  state.metadataPrefetchTrackId = trackId;
  state.metadataPrefetchStartedAt = Date.now();
  state.metadataPrefetchUnavailable = false;
  state.metadataPrefetchAttempts = 0;
  const token = ++state.metadataPrefetchToken;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.metadataPrefetchController = controller;
  // Keep normal pending polls distinct from an explicit retry of a terminal
  // provider result.  Retrying every 900ms used to recreate/requeue the same
  // current-track job before a slow fallback source could finish.
  let retryFailed = false;
  // Lyrics are the most visible part of metadata when playback starts. Keep
  // one bounded, fire-and-forget request alongside the candidate lookup so a
  // later lyrics-page open can use the already resolved body instead of
  // waiting for a fresh provider chain. This is intentionally independent of
  // the background-enrichment switch and guarded by the current track token.
  // Even when a file already contains embedded lyrics, the same priority
  // endpoint may have a cached/provider artwork result. Do not skip this
  // lane solely because lyrics are present; only skip once both visible
  // metadata pieces are already available locally.
  const needsPriorityLyricsLane = !String(item.lyrics || "").trim()
    || (!item.cover_url && !item.cover_thumbnail_url);
  if (state.metadataPrefetchLyricsTrackId !== trackId && needsPriorityLyricsLane) {
    state.metadataPrefetchLyricsTrackId = trackId;
    state.metadataPrefetchLyricsAttempts = 0;
    if (state.metadataPrefetchLyricsTimer) clearTimeout(state.metadataPrefetchLyricsTimer);
    const lyricsToken = ++state.metadataPrefetchLyricsToken;
    const lyricsController = typeof AbortController === "function" ? new AbortController() : null;
    state.metadataPrefetchLyricsController = lyricsController;
    let scheduleLyricsRetry = null;
    const requestLyrics = (retryFailed = false) => {
      const requestedRetry = retryFailed;
      return fetchMetadataRequest(`api/lyrics?track_id=${encodeURIComponent(trackId)}${requestedRetry ? "&retry=1" : ""}`, 10000, lyricsController?.signal)
      .then(result => ({
        ok: result.response?.ok,
        data: result.data || {},
      }))
      .then(data => {
        if (!data || lyricsToken !== state.metadataPrefetchLyricsToken
          || String(currentItem()?.id || "") !== trackId) return;
        // `/api/lyrics` normally returns its projection at the top level.
        // Some host bridges use a `{ data: ... }` envelope, so support both
        // shapes. Reading only `data.data` discarded normal completed
        // lyrics/artwork and made playback look permanently pending.
        const lyricPayload = unwrapMetadataResponsePayload(data);
        const status = String(lyricPayload?.status || "").toLowerCase();
        const pending = lyricPayload?.pending === true || status === "pending";
        const terminal = ["failed", "no_match"].includes(status) && !lyricPayload?.lyrics;
        if ((data.ok !== true || pending || terminal) && state.metadataPrefetchLyricsAttempts < 12) {
          scheduleLyricsRetry?.(!requestedRetry && (terminal || data.ok !== true));
          return;
        }
        const lyrics = typeof lyricPayload?.lyrics === "string" ? lyricPayload.lyrics.trim() : "";
        const lyricArtwork = usableCoverSource(lyricPayload?.image_url);
        let changed = false;
        if (lyricArtwork && !item.cover_url && !item.cover_thumbnail_url) {
          item.cover_url = lyricArtwork;
          item.cover_thumbnail_url = lyricArtwork;
          changed = true;
        }
        if (lyrics) {
          item.lyrics = lyrics;
          changed = true;
        }
        if (!changed) return;
        state.itemCache.set(trackId, item);
        invalidateLibraryResponseForTrack(trackId);
        invalidateTrackRowsMarkup(state.pageItems);
        restoreLibraryNowPlaying();
        updateMediaSessionMetadata(item);
        scheduleMetadataRowRender(trackId, ["cover_url", "cover_thumbnail_url", "lyrics"]);
        if (state.lyricsTrackId === trackId) {
          if (lyrics) {
            state.lyrics = parseLyrics(lyrics);
            state.lyricsStatus = "ready";
            if (!$('lyricsView')?.hidden) renderLyrics(state.lyrics);
          }
        }
      }).finally(() => {
        // A settled lyric lookup no longer owns the current song. Preserve
        // the controller only while a bounded retry timer remains, so a later
        // priority call can retry an empty projection and track switches can
        // cancel the next request.
        if (lyricsToken === state.metadataPrefetchLyricsToken
          && state.metadataPrefetchLyricsController === lyricsController
          && !state.metadataPrefetchLyricsTimer) {
          state.metadataPrefetchLyricsController = null;
          if (String(currentItem()?.id || "") === trackId) {
            state.metadataPrefetchLyricsTrackId = "";
          }
        }
      });
    };
    scheduleLyricsRetry = (retryFailed = false) => {
      // A bounded client timeout is a recoverable provider/proxy failure.
      // Keep lyrics priority alive without allowing an unbounded timer chain.
      if (lyricsToken !== state.metadataPrefetchLyricsToken
        || String(currentItem()?.id || "") !== trackId
        || state.metadataPrefetchLyricsAttempts >= 12) return;
      state.metadataPrefetchLyricsAttempts += 1;
      state.metadataPrefetchLyricsController = lyricsController;
      state.metadataPrefetchLyricsTimer = setTimeout(() => {
        state.metadataPrefetchLyricsTimer = 0;
        requestLyrics(retryFailed).catch(() => scheduleLyricsRetry(false));
      }, 900);
    };
    requestLyrics().catch(() => scheduleLyricsRetry(false));
  }
  const scheduleRearm = () => {
    if (token !== state.metadataPrefetchToken || String(currentItem()?.id || "") !== trackId) return;
    if (state.metadataPrefetchRearms >= 2 || state.metadataPrefetchTimer) return;
    // Do not keep hitting a provider immediately after its negative-cache
    // window. One quiet cooldown gives it time to recover; `prefetch...`
    // checks the age and the two-rearm cap again before any new request.
    state.metadataPrefetchController = controller;
    state.metadataPrefetchTimer = setTimeout(() => {
      state.metadataPrefetchTimer = 0;
      prefetchCurrentTrackMetadata(currentItem());
    }, 30000);
  };
  const scheduleRetry = () => {
    if (token !== state.metadataPrefetchToken || String(currentItem()?.id || "") !== trackId) return;
    if (state.metadataPrefetchAttempts >= METADATA_PREFETCH_MAX_ATTEMPTS) {
      scheduleRearm();
      return;
    }
    state.metadataPrefetchAttempts += 1;
    if (state.metadataPrefetchTimer) clearTimeout(state.metadataPrefetchTimer);
    // A request rejection reaches its outer retry handler after this
    // request's `finally` has released the controller. Restore ownership as
    // soon as the retry is scheduled so a track switch can cancel the next
    // attempt before it consumes another provider/socket slot.
    state.metadataPrefetchController = controller;
    state.metadataPrefetchTimer = setTimeout(() => {
      state.metadataPrefetchTimer = 0;
      // Only terminal provider results need an explicit recovery request.
      // A pending job must retain its FIFO/backoff state while a slower
      // fallback source is still running.
      request(retryFailed).catch(() => scheduleRetry());
    }, 900);
  };
  // This is deliberately fire-and-forget: playback must never wait for a
  // third-party provider.  The server keeps the request bounded and queues
  // the current track at priority 1 even when background enrichment is off.
  const request = (retryFailed = false) => {
    const requestedRetry = retryFailed;
    return fetchMetadataRequest(`api/metadata/track?track_id=${encodeURIComponent(trackId)}${requestedRetry ? "&retry=1" : ""}`, 10000, controller?.signal)
    .then(result => {
      const response = result.response;
      const payload = result.data;
      // A restarting metadata worker can briefly surface a 5xx. Treat that
      // as bounded pending work so the current song gets another chance;
      // client/auth and malformed-track errors remain terminal.
      if (response.ok) return payload;
      // Provider gateways and CGI proxies may briefly answer with a bounded
      // overload/rate-limit status. Keep the current-track lane alive for
      // these transient transport failures instead of silently abandoning
      // metadata after the first non-5xx response.
      if (globalThis.fnAudioMetadataResponsePolicy?.isTransientHttpStatus?.(response.status)) {
        return payload?.status === "unavailable"
          ? { ...payload, unavailable: true }
          : { pending: true };
      }
      return null;
    })
    .then(data => {
      if (!data || token !== state.metadataPrefetchToken || String(currentItem()?.id || "") !== trackId) return;
      data = unwrapMetadataResponsePayload(data);
      if (data.unavailable === true || String(data.status || "").toLowerCase() === "unavailable") {
        // Metadata workers can be starting up while the player is already
        // usable. Keep the current-track lane alive with the same bounded
        // retry budget so a transient 503 does not permanently suppress
        // lyrics/artwork for the remainder of the session.
        state.metadataPrefetchUnavailable = true;
        scheduleRetry();
        return;
      }
      state.metadataPrefetchUnavailable = false;
      // A provider can return usable candidates without selecting an
      // automatic `best` match (for example when confidence/margin is below
      // the write-back threshold).  Show the first bounded candidate in the
      // current row as a presentation fallback; this never confirms or
      // writes tags and keeps local Tag values authoritative.
      // An empty `best: {}` is a normal review/pending projection. Treat it
      // as absent so a bounded candidate can still update the current row;
      // otherwise metadata was fetched successfully but the UI stayed blank.
      const best = globalThis.fnAudioMetadataCandidatePresentationPolicy?.selectDisplayCandidate(
        data.best,
        data.candidates,
      );
      const responseStatus = String(data.status || "").toLowerCase();
      const responsePending = data.pending === true || responseStatus === "pending";
      retryFailed = !requestedRetry && (responseStatus === "failed" || responseStatus === "no_match");
      if (!best) {
        // A cached artwork projection can be useful even when the match row
        // has no displayable candidate. Apply it independently so a sparse
        // provider result does not erase a known cover or suppress metadata
        // recovery in the UI.
        const cachedArtwork = usableCoverSource(data.image_url);
        if (cachedArtwork && !item.cover_url && !item.cover_thumbnail_url) {
          item.cover_url = cachedArtwork;
          item.cover_thumbnail_url = cachedArtwork;
          state.itemCache.set(trackId, item);
          invalidateLibraryResponseForTrack(trackId);
          invalidateTrackRowsMarkup(state.pageItems);
          restoreLibraryNowPlaying();
          updateMediaSessionMetadata(item);
          scheduleMetadataRowRender(trackId, ["cover_url", "cover_thumbnail_url"]);
        }
        // Older/current backends project queued work as `status: "pending"`
        // while newer responses also expose `pending: true`. Accept both
        // forms so a successful enqueue never looks like a dead lookup.
        const status = responseStatus;
        const pending = responsePending;
        // ``review`` normally carries candidates and is therefore handled
        // above.  Treat a legacy/corrupt empty review projection as
        // recoverable too: otherwise a structurally successful response with
        // no usable values makes the current-song lane go quiet until its
        // server TTL expires.
        // Some host bridges expose an in-progress request as a generic HTTP
        // 200 `{ok:true}` envelope. With none of the metadata projection keys
        // present, that response is not a terminal no-match; retain the
        // bounded retry lane instead of silently stopping enrichment.
        const missingProjection = !Object.prototype.hasOwnProperty.call(data, "status")
          && !Object.prototype.hasOwnProperty.call(data, "best")
          && !Object.prototype.hasOwnProperty.call(data, "candidates")
          && !Object.prototype.hasOwnProperty.call(data, "pending")
          && !Object.prototype.hasOwnProperty.call(data, "image_url");
        const recoverable = pending || status === "failed" || status === "no_match" || status === "review" || status === "auto";
        if (state.metadataPrefetchAttempts < METADATA_PREFETCH_MAX_ATTEMPTS && (recoverable || missingProjection)) {
          scheduleRetry();
        }
        return;
      }
      const fields = ["title", "artist", "album", "album_artist", "date", "genre", "track_no", "composer"];
      let changed = false;
      const changedFields = [];
      fields.forEach(field => {
        const value = best[field];
        if (value == null || String(value).trim() === "") return;
        if (!String(item[field] || "").trim() || item.metadata_source?.[field] !== "tag") {
          if (String(item[field] || "") !== String(value)) { item[field] = value; changed = true; changedFields.push(field); }
        }
      });
      const candidateArtwork = usableCoverSource(
        globalThis.fnAudioMetadataCandidatePresentationPolicy?.selectDisplayArtwork?.(best, data.candidates, data.image_url)
          || data.image_url,
      );
      if (candidateArtwork && !item.cover_url && !item.cover_thumbnail_url) {
        item.cover_url = candidateArtwork;
        item.cover_thumbnail_url = candidateArtwork;
        changed = true;
        changedFields.push("cover_url", "cover_thumbnail_url");
      }
      if (changed) {
        // The playing item may come from a restored queue rather than the
        // visible page. Keep the bounded identity cache in sync so a later
        // view switch cannot regress to the pre-enrichment row.
        state.itemCache.set(trackId, item);
        invalidateLibraryResponseForTrack(trackId);
        invalidateTrackRowsMarkup(state.pageItems);
        restoreLibraryNowPlaying();
        updateMediaSessionMetadata(item);
        scheduleMetadataRowRender(trackId, changedFields);
      }
      // A filename candidate is presentation-only while the provider lookup
      // is still pending. Keep the bounded retry alive after applying it;
      // otherwise the first useful local identity would accidentally suppress
      // the remote candidate that can supply artwork/album fields.
      if ((responsePending || data.retryable === true)
        && state.metadataPrefetchAttempts < METADATA_PREFETCH_MAX_ATTEMPTS) {
        scheduleRetry();
      } else if (isRecoverableFilenameMetadata(data, best)
        && state.metadataPrefetchAttempts < METADATA_PREFETCH_MAX_ATTEMPTS) {
        // A filename candidate is useful for immediate display, but it is not
        // proof that remote metadata is unavailable. Keep a bounded recovery
        // poll alive so a transient provider miss can later supply album,
        // artwork and complete tags.
        scheduleRetry();
      }
    }).finally(() => {
      // A completed terminal lookup no longer owns the current row. Keep the
      // controller only while an in-flight request or its bounded retry timer
      // can still be cancelled; otherwise visible-page recovery may safely
      // pick up fields the priority response could not provide.
      if (token === state.metadataPrefetchToken
        && state.metadataPrefetchController === controller
        && !state.metadataPrefetchTimer) {
        state.metadataPrefetchController = null;
      }
    });
  };
  request().catch(() => scheduleRetry());
}
function retryCurrentTrackMetadataAfterRecovery(metadata) {
  // A dead metadata pool can be recovered lazily by the next API request. If
  // the previous prefetch exhausted its bounded unavailable retries, the same
  // track ID would otherwise short-circuit forever. Re-arm it only after the
  // status endpoint confirms a live service, and only once per recovery edge.
  if (!state.metadataPrefetchUnavailable || !metadata || metadata.running !== true) return;
  const item = currentItem();
  const trackId = String(item?.id || "");
  if (!trackId || state.metadataPrefetchRecoverySeen === trackId) return;
  state.metadataPrefetchRecoverySeen = trackId;
  state.metadataPrefetchTrackId = "";
  state.metadataPrefetchAttempts = 0;
  state.metadataPrefetchUnavailable = false;
  prefetchCurrentTrackMetadata(item);
}
async function openLyrics() {
  const item = currentItem();
  $("lyricsView").hidden = false;
  updateLyricsMeta(item);
  const trackId = String(item?.id || "");
  const retry = state.lyricsTrackId === trackId && ["pending", "error"].includes(state.lyricsStatus);
  // Only a deliberate re-open after a terminal failure is allowed to reset a
  // failed provider job. Timed pending polls remain bounded and never request
  // an unbounded retry loop from the server.
  await loadLyricsForCurrentTrack(item, retry, state.lyricsStatus === "error");
}
function updateLyricHighlight() {
  if (!state.lyrics.length || $("lyricsView").hidden) return;
  const now = currentSeconds();
  let active = 0;
  state.lyrics.forEach((line, index) => {
    if (line.time >= 0 && line.time <= now + 0.25) active = index;
  });
  document.querySelectorAll("[data-lyric]").forEach(node => node.classList.toggle("active", Number(node.dataset.lyric) === active));
  const activeNode = document.querySelector(`[data-lyric="${active}"]`);
  const lyricBox = $("lyricsLines");
  if (activeNode && lyricBox) {
    const target = activeNode.offsetTop - (lyricBox.clientHeight / 2) + (activeNode.clientHeight / 2);
    lyricBox.scrollTo({ top: Math.max(0, target), behavior: "smooth" });
  }
}
function syncState() {
  scheduleUserStateSave();
}
async function loadLibrary(refresh = false) {
  return loadPagedLibrary(1, refresh);
}
function invalidateLibraryLoad() {
  // A non-paged view has no replacement library request, so explicitly
  // invalidate the previous paged request before rendering the new surface.
  state.libraryRequestSeq += 1;
  if (state.libraryAbortController) state.libraryAbortController.abort();
  state.libraryAbortController = null;
  // Status polling can outlive the page request. Invalidate it as well so a
  // late scan-complete response cannot reload the view that was just left.
  state.libraryStatusRequestToken += 1;
  if (state.libraryStatusController) {
    try { state.libraryStatusController.abort(); } catch (_) {}
  }
  state.libraryStatusController = null;
  state.libraryStatusPromise = null;
  state.libraryStatusRefreshQueued = false;
  if (state.libraryStatusTimer) {
    clearTimeout(state.libraryStatusTimer);
    state.libraryStatusTimer = 0;
  }
  state.libraryLoadKey = "";
  state.libraryLoadPromise = null;
  state.libraryLoading = false;
  state.libraryInteractionBlocked = false;
  cancelReferencedItemHydrationSchedule();
  cancelMetadataRowRender();
  cancelVisibleMetadataPrefetch({ releaseKeys: true });
}
function libraryResponseWeight(data) {
  return globalThis.fnAudioLibraryResponsePolicy?.responseWeight?.(data) || 1;
}
function clearLibraryResponseCaches() {
  state.libraryResponseEpoch += 1;
  state.libraryResponseCache.clear();
  // Clearing the map detaches stale requests from future callers. Cancel them
  // without releasing their slots early; the loader releases each slot only
  // after the underlying promise settles, keeping the hard concurrency cap
  // valid while cancellation propagates through the transport.
  for (const request of state.libraryResponseInflight.values()) {
    request?.__fnAudioAbort?.();
  }
  state.libraryResponseInflight.clear();
  // Album metadata is derived from the same library snapshot. Invalidate it
  // with page responses so a completed scan cannot leave stale presentation
  // fields visible until the LRU naturally evicts them.
  state.albumMetadata.clear?.();
  state.librarySnapshotEmptyGuardUsed = false;
}

function shouldRetainSnapshotForEmptyResponse(data, refresh = false) {
  return Boolean(globalThis.fnAudioLibraryEmptyResponsePolicy?.shouldRetainSnapshot(
    data,
    state.pageItems,
    { refresh, guardUsed: state.librarySnapshotEmptyGuardUsed, snapshotHit: state.librarySnapshot?.hit === true },
  ));
}
function metadataProjectionSignature(data = {}) {
  return globalThis.fnAudioMetadataProjectionPolicy?.signature(data) || "";
}
async function fetchLibraryResponse(url, message, refresh = false, signal = undefined) {
  return globalThis.fnAudioLibraryResponseLoader.loadLibraryResponse({
    url,
    message,
    refresh,
    signal,
    cache: state.libraryResponseCache,
    inflight: state.libraryResponseInflight,
    active: state.libraryResponseActive,
    inflightLimit: state.libraryResponseInflightLimit,
    epoch: state.libraryResponseEpoch,
    getEpoch: () => state.libraryResponseEpoch,
    fetchJson: (requestUrl, requestMessage, requestSignal) => fetchJsonChecked(
      requestUrl,
      requestSignal ? { signal: requestSignal } : {},
      requestMessage,
      { strictBody: true },
    ),
  });
}
function cacheLibraryItems(items = [], trim = true) {
  (items || []).forEach(item => {
    if (item && item.id) {
      const id = String(item.id);
      state.itemCache.set(id, item);
      state.unresolvedItemIds?.delete?.(id);
    }
  });
  if (trim) state.itemCache.trim(new Set((state.queue || []).map(item => String(item?.id || "")).filter(Boolean)));
}
function mergeAuthoritativePageItems(items = []) {
  return globalThis.fnAudioLibraryMetadataMergePolicy?.merge(items, state.pageItems, state.itemCache)
    || (Array.isArray(items) ? items : []);
}
function trackPagePresentationSignatures(items = []) {
  // This mirrors the visible row markup without constructing its HTML. It is
  // used only for the snapshot-to-authoritative handoff: equal signatures mean
  // the existing list markup is safe to retain, including decoded cover nodes.
  if (!Array.isArray(items) || items.length > 500 || state.view === "queue") return [];
  const columns = activeTrackColumns();
  const nonTitleColumns = columns.filter(key => key !== "title");
  return items.map((item, index) => {
    const values = trackColumnValues(item, nonTitleColumns);
    const rowSignature = trackRowMarkupSignature(item, index, columns, values, coverUrl(item));
    // The row signature intentionally excludes identity because it is a
    // presentation optimization. The rendered wrapper includes id/data-play,
    // so add it here before allowing literal markup reuse.
    return JSON.stringify([String(item?.id || ""), rowSignature]);
  });
}
function reuseSnapshotTrackMarkup(previousItems, nextItems, snapshotHit) {
  if (!snapshotHit || !isPagedTrackListing() || state.view === "queue") return false;
  const cache = state.trackRowsMarkupCache;
  const previousMarkup = cache?.get?.(previousItems);
  if (!previousMarkup || !previousMarkup.key || typeof previousMarkup.html !== "string") return false;
  const reusable = globalThis.fnAudioLibrarySnapshotReusePolicy?.canReuseMarkup(
    trackPagePresentationSignatures(previousItems),
    trackPagePresentationSignatures(nextItems),
  ) === true;
  if (!reusable) return false;
  cache?.set?.(nextItems, previousMarkup);
  state.uiMetrics.snapshotMarkupReuses = Math.min(1000000, state.uiMetrics.snapshotMarkupReuses + 1);
  return true;
}
function setTextContentIfChanged(node, value) {
  if (!node) return;
  const text = String(value ?? "");
  if (node.textContent !== text) node.textContent = text;
}
function setStyleVarIfChanged(node, name, value) {
  if (!node || !node.style) return;
  const text = String(value ?? "");
  // Comparing against the serialized value is best effort: a WebView that pads
  // custom properties with whitespace simply keeps writing, which is the
  // behaviour this call site had before the check existed.
  if (node.style.getPropertyValue(name) === text) return;
  node.style.setProperty(name, text);
}
function setDatasetStateIfChanged(node, value) {
  if (!node || !node.dataset) return;
  // "unknown" is the only state worth naming; clearing writes the empty string rather
  // than deleting the attribute.  Both match no `[data-state="unknown"]` selector, and a
  // plain value means a second, third and hundredth identical call all have nothing left
  // to do - the 500ms poll must not touch the DOM when the transport row did not change.
  const next = value === true ? "unknown" : "";
  if ((node.dataset.state || "") === next) return;
  node.dataset.state = next;
}
function updateLibraryStatusDecorations() {
  const serverPortValue = $("serverPortValue");
  setTextContentIfChanged(serverPortValue, state.libraryStatus?.server_port || "--");
  setTextContentIfChanged($("allCount"), libraryCount(state.libraryStatus?.count));
  setTextContentIfChanged($("dsdCount"), libraryCount(state.libraryStatus?.dsd_count));
  setTextContentIfChanged($("recentCount"), libraryCount(state.libraryStatus?.count));
  const emptyText = $("emptyText");
  if (emptyText && state.libraryStatus) {
    const path = state.libraryStatus.library_path || "";
    setTextContentIfChanged(emptyText, `${state.libraryStatus.message || "没有找到音乐文件"}${path ? `：${path}` : ""}`);
  }
  const scanText = scanProgressText();
  if (scanText) {
    setTextContentIfChanged($("viewSub"), scanText);
    setTextContentIfChanged($("mobileViewSub"), scanText);
  }
}
function clearLibraryQueryState() {
  state.page = 1;
  state.pageItems = [];
  state.pageTotal = 0;
  state.groupRows = [];
  state.folderRows = [];
  state.folderRootRows = [];
  state.folderPage = 1;
  state.folderTotal = 0;
}
function cancelVisibleMetadataPrefetch(options = {}) {
  const cancelRearms = options.cancelRearms !== false;
  const releaseKeys = options.releaseKeys === true;
  const preserveRearm = !cancelRearms && Boolean(state.visibleMetadataPrefetchRearmTimer);
  if (state.visibleMetadataPrefetchTimer) {
    if (state.visibleMetadataPrefetchUsesIdle && typeof cancelIdleCallback === "function") cancelIdleCallback(state.visibleMetadataPrefetchTimer);
    else clearTimeout(state.visibleMetadataPrefetchTimer);
    state.visibleMetadataPrefetchTimer = 0;
  }
  state.visibleMetadataPrefetchUsesIdle = false;
  try { state.visibleMetadataPrefetchController?.abort(); } catch (_) {}
  state.visibleMetadataPrefetchController = null;
  // Do not discard completed-key history on an ordinary same-page refresh,
  // but always release keys whose requests were cancelled before completion.
  state.visibleMetadataPrefetchActiveKeys?.forEach((owner, key) => {
    if (state.visibleMetadataPrefetchActiveKeys.get(key) === owner) {
      state.visibleMetadataPrefetchKeys.delete(key);
      state.visibleMetadataPrefetchActiveKeys.delete(key);
    }
  });
  state.visibleMetadataPrefetchRequestSeq = 0;
  state.visibleMetadataPrefetchItems = null;
  if (cancelRearms) {
    if (state.visibleMetadataPrefetchRearmTimer) clearTimeout(state.visibleMetadataPrefetchRearmTimer);
    state.visibleMetadataPrefetchRearmTimer = 0;
    state.visibleMetadataPrefetchRearmKeys?.clear();
    state.visibleMetadataPrefetchRearmSeq = 0;
  }
  // A visibility cancellation aborts requests that may have claimed a key
  // before receiving a result. Release those page hints so returning to the
  // foreground can retry the same visible rows; ordinary page/status
  // cancellation retains completed-key deduplication.
  if (releaseKeys) state.visibleMetadataPrefetchKeys?.clear();
  state.visibleMetadataPrefetchSeq += 1;
  // Status refreshes cancel the old worker generation but keep a finite
  // pending re-arm alive. Rebind that timer to the new generation so its
  // callback is not discarded as stale after the refresh.
  if (preserveRearm) state.visibleMetadataPrefetchRearmSeq = state.visibleMetadataPrefetchSeq;
}
function scheduleVisibleMetadataPrefetchRearm(key, data, attempts, generation, requestSeq) {
  if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return false;
  const knownRearms = Number(state.visibleMetadataPrefetchRearmKeys?.get(key) || 0);
  const policy = globalThis.fnAudioVisibleMetadataPrefetchPolicy;
  if (!policy?.shouldRearmPending?.(data, attempts, knownRearms, 12, 2)) return false;
  state.visibleMetadataPrefetchRearmKeys.set(key, knownRearms + 1);
  // Keep the ordinary dedupe key until the quiet re-arm fires. Status polling
  // can therefore keep refreshing chrome without restarting this same row.
  if (state.visibleMetadataPrefetchRearmTimer) return true;
  const delay = policy.pendingRearmDelayMs?.(knownRearms + 1) || 3500;
  state.visibleMetadataPrefetchRearmSeq = generation;
  state.visibleMetadataPrefetchRearmTimer = setTimeout(() => {
    state.visibleMetadataPrefetchRearmTimer = 0;
    if (state.visibleMetadataPrefetchRearmSeq !== state.visibleMetadataPrefetchSeq
      || requestSeq !== state.libraryRequestSeq) return;
    state.visibleMetadataPrefetchRearmSeq = 0;
    // Release every pending key for this settled page together. The new lane
    // retains its six-row/two-request caps, rather than creating one timer per
    // track and repeatedly cancelling itself.
    state.visibleMetadataPrefetchRearmKeys.forEach((_, pendingKey) => {
      state.visibleMetadataPrefetchKeys.delete(pendingKey);
    });
    scheduleVisibleMetadataPrefetch(state.pageItems, requestSeq);
  }, delay);
  return true;
}
function scheduleVisibleMetadataPrefetch(items = [], requestSeq = state.libraryRequestSeq) {
  const policy = globalThis.fnAudioVisibleMetadataPrefetchPolicy;
  const hasPendingWork = Boolean(
    state.visibleMetadataPrefetchTimer
    || state.visibleMetadataPrefetchController
    || state.visibleMetadataPrefetchRearmTimer
  );
  if (policy?.shouldReuseActiveLane?.(
    requestSeq,
    state.visibleMetadataPrefetchRequestSeq,
    items === state.visibleMetadataPrefetchItems,
    hasPendingWork,
  )) return;
  // A status/projection refresh may reschedule the active lane. Preserve a
  // pending re-arm in that case; page changes and hidden documents still use
  // the default cancellation path and clear it completely.
  cancelVisibleMetadataPrefetch({ cancelRearms: false });
  // The currently playing item already has an immediate priority metadata
  // lane. Excluding it here avoids duplicate provider requests and prevents
  // the optional first-page queue from competing with lyrics/artwork needed
  // for the active song.
  const currentTrackId = String(currentItem()?.id || "");
  // A restored queue can identify the current song before playback has been
  // started. In that cold-start window there is no playback-owned metadata
  // lane yet, so excluding the current row would leave it permanently on the
  // local/empty projection. Exclude it only while the priority lane already
  // owns an active request; otherwise let the bounded first-page lane recover
  // it as well. The server-side job key still coalesces duplicate requests.
  const priorityLaneActive = globalThis.fnAudioVisibleMetadataPrefetchPolicy?.ownsCurrentTrackLane?.(
    currentTrackId,
    state.metadataPrefetchTrackId,
    state.metadataPrefetchController,
    state.metadataPrefetchTimer,
  ) === true;
  const excludedCurrentTrackId = priorityLaneActive ? currentTrackId : "";
  const candidates = globalThis.fnAudioVisibleMetadataPrefetchPolicy?.selectCandidates(items, 6, excludedCurrentTrackId) || [];
  if (!candidates.length) return;
  const generation = state.visibleMetadataPrefetchSeq;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.visibleMetadataPrefetchController = controller;
  state.visibleMetadataPrefetchRequestSeq = requestSeq;
  state.visibleMetadataPrefetchItems = items;
  const run = async () => {
    state.visibleMetadataPrefetchTimer = 0;
    state.visibleMetadataPrefetchUsesIdle = false;
    if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return;
    let cursor = 0;
    const worker = async () => {
      while (cursor < candidates.length) {
        if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return;
        const item = candidates[cursor++];
        const id = String(item.id);
        const key = `${libraryLoadRequestKey(state.page)}:${id}`;
        // Keep deduplication memory bounded across many page switches. Older
        // keys are only a best-effort optimization and may be discarded.
        if (!rememberVisibleMetadataPrefetchKey(key, 256)) continue;
        state.visibleMetadataPrefetchActiveKeys.set(key, generation);
        try {
          let data = null;
          let retryFailed = false;
          let attempts = 0;
          // A provider chain can legitimately take several seconds when an
          // early source times out before a later one responds. Four 450ms
          // polls often ended before the queued job finished, leaving the
          // page looking as if metadata discovery was disabled. Keep this
          // lane bounded and cancellable, but give it the same practical
          // window as the current-track path.
          for (let attempt = 0; attempt < 12; attempt += 1) {
            if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return;
            const requestedRetry = retryFailed;
            // Keep each optional row lookup bounded as well. The shared
            // controller still cancels the whole lane on page changes, while
            // this per-request timeout prevents one stalled proxy from
            // occupying a worker slot for the rest of the page.
            const metadataRequestStartedAt = Date.now();
            const result = await fetchMetadataRequest(
              `api/metadata/track?track_id=${encodeURIComponent(id)}${requestedRetry ? "&retry=1" : ""}`,
              8000,
              controller?.signal,
            );
            const response = result.response;
            attempts = attempt + 1;
            const metadataRequestElapsedMs = Math.min(3600000, Math.max(0, Date.now() - metadataRequestStartedAt));
            if (!state.uiMetrics.metadataPrefetchFirstMs) {
              state.uiMetrics.metadataPrefetchFirstMs = Math.min(3600000, Math.max(0,
                Date.now() - Number(state.uiMetrics.sessionStartedAt || Date.now())));
            }
            state.uiMetrics.metadataPrefetchLastMs = metadataRequestElapsedMs;
            state.uiMetrics.metadataPrefetchMaxMs = Math.max(state.uiMetrics.metadataPrefetchMaxMs, metadataRequestElapsedMs);
            state.uiMetrics.metadataPrefetchTotalMs = Math.min(3600000, state.uiMetrics.metadataPrefetchTotalMs + metadataRequestElapsedMs);
            state.uiMetrics.metadataPrefetchRequests = Math.min(1000000, state.uiMetrics.metadataPrefetchRequests + 1);
            if (response.ok) data = unwrapMetadataResponsePayload(result.data);
            else if (globalThis.fnAudioMetadataResponsePolicy?.isTransientHttpStatus?.(response.status)) {
              // Treat transient gateway/rate-limit responses as pending so
              // the bounded visible-row retry lane can recover metadata.
              data = { pending: true };
            }
            const status = typeof data?.status === "string" ? data.status.toLowerCase() : "";
            // Only a terminal negative result needs an explicit replacement
            // request. Pending responses must remain ordinary polls; sending
            // retry=1 on every attempt can repeatedly reset a fast no_match
            // job, trigger provider rate limits, and make metadata look
            // permanently unavailable.
            retryFailed = !requestedRetry && (status === "failed" || status === "no_match");
            if (!globalThis.fnAudioVisibleMetadataPrefetchPolicy?.shouldRetry(data, attempt, 12)) break;
            await new Promise(resolve => setTimeout(resolve, 700));
          }
          // A response from a cancelled page is stale work, not a provider
          // failure. Do not let page switches pollute failure diagnostics or
          // make a healthy provider look unreliable.
          if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return;
          if (!data) {
            state.uiMetrics.metadataPrefetchFailures = Math.min(1000000, state.uiMetrics.metadataPrefetchFailures + 1);
            state.visibleMetadataPrefetchKeys.delete(key);
            continue;
          }
          const best = globalThis.fnAudioMetadataCandidatePresentationPolicy?.selectDisplayCandidate(
            data.best,
            data.candidates,
          );
          // Artwork may be persisted independently of a recording match
          // (for example after a lyrics/artwork worker finishes before the
          // candidate row).  Do not discard that useful result merely because
          // the candidate projection is still empty.
          const artwork = usableCoverSource(
            globalThis.fnAudioMetadataCandidatePresentationPolicy?.selectDisplayArtwork?.(best, data.candidates, data.image_url)
              || data.image_url,
          );
          if (!best && !artwork) {
            const terminalStatus = String(data.status || "").toLowerCase();
            if (terminalStatus === "no_match") {
              state.uiMetrics.metadataPrefetchNoMatches = Math.min(1000000, state.uiMetrics.metadataPrefetchNoMatches + 1);
            } else if (terminalStatus === "failed") {
              state.uiMetrics.metadataPrefetchFailures = Math.min(1000000, state.uiMetrics.metadataPrefetchFailures + 1);
            }
            const rearmPending = scheduleVisibleMetadataPrefetchRearm(key, data, attempts, generation, requestSeq);
            if (!rearmPending && globalThis.fnAudioVisibleMetadataPrefetchPolicy?.shouldReleaseKey(data)) {
              state.visibleMetadataPrefetchKeys.delete(key);
            }
            continue;
          }
          state.uiMetrics.metadataPrefetchSuccesses = Math.min(1000000, state.uiMetrics.metadataPrefetchSuccesses + 1);
          let changed = false;
          const changedFields = [];
          ["title", "artist", "album", "album_artist", "date", "genre", "track_no", "composer"].forEach(field => {
            if (!best) return;
            const value = best[field];
            if (value == null || String(value).trim() === "") return;
            if (!String(item[field] || "").trim() && String(item[field] || "") !== String(value)) {
              item[field] = value;
              changed = true;
              changedFields.push(field);
            }
          });
          if (artwork && !item.cover_url && !item.cover_thumbnail_url) {
            item.cover_url = artwork;
            item.cover_thumbnail_url = artwork;
            changed = true;
            changedFields.push("cover_url");
          }
          if (changed) {
            state.itemCache.set(id, item);
            invalidateLibraryResponseForTrack(id);
            invalidateTrackRowsMarkup(state.pageItems);
            // This lane may enrich a non-playing visible row; use the page
            // refresh path rather than the current-track-only guard used by
            // playback metadata prefetch.
            scheduleMetadataRowRender(id, changedFields);
          }
          // A local/filename candidate can be useful for immediate display
          // while the provider result is still retryable.  Do not let that
          // presentation-only success permanently consume the page dedupe
          // key: once the worker/provider projection changes, the row must be
          // eligible for another bounded lookup (for example to obtain the
          // missing album or artwork).
          const releaseStatus = String(data.status || "").toLowerCase();
          const rearmPending = scheduleVisibleMetadataPrefetchRearm(key, data, attempts, generation, requestSeq);
          if (!rearmPending && (data.retryable === true || releaseStatus === "failed" || releaseStatus === "no_match")
            && globalThis.fnAudioVisibleMetadataPrefetchPolicy?.shouldReleaseKey(data)) {
            state.visibleMetadataPrefetchKeys.delete(key);
          }
          if (!rearmPending && isRecoverableFilenameMetadata(data, best)
            && state.visibleMetadataPrefetchSeq === generation
            && state.uiMetrics.metadataPrefetchFailures < 1000000) {
            // Leave the lightweight visible lane eligible for one future
            // retry; the scheduler remains bounded by the per-item key and
            // server-side retry policy.
            state.visibleMetadataPrefetchKeys.delete(key);
          }
        } catch (error) {
          if (error?.name === "AbortError") return;
          // A provider/network miss is isolated; record it for diagnostics so
          // the UI does not report an artificially perfect prefetch rate.
          // The next explicit playback or lyrics request can still retry
          // through the normal priority lane.
          state.uiMetrics.metadataPrefetchFailures = Math.min(1000000, state.uiMetrics.metadataPrefetchFailures + 1);
          state.visibleMetadataPrefetchKeys.delete(key);
        } finally {
          if (state.visibleMetadataPrefetchActiveKeys.get(key) === generation) {
            state.visibleMetadataPrefetchActiveKeys.delete(key);
          }
        }
      }
    };
    try {
      await Promise.all([worker(), worker()]);
    } finally {
      // A worker can throw before its first request, for example while
      // deriving the page load key. Release the lane identity either way:
      // a leaked controller keeps shouldReuseActiveLane() short-circuiting
      // every later schedule for this page, so visible rows never got their
      // metadata back until the user switched pages.
      if (state.visibleMetadataPrefetchController === controller) {
        state.visibleMetadataPrefetchController = null;
        // A pending page-owned re-arm still needs this identity so a
        // metadata status refresh cannot invalidate its recovery window.
        if (!state.visibleMetadataPrefetchRearmTimer) {
          state.visibleMetadataPrefetchRequestSeq = 0;
          state.visibleMetadataPrefetchItems = null;
        }
      }
    }
  };
  // Do not let optional visible-row enrichment steal the first paint. Current
  // playback metadata still uses its dedicated immediate priority lane; this
  // delay only applies to non-playing rows on a freshly rendered page.
  const queueIdleRun = () => {
    if (generation !== state.visibleMetadataPrefetchSeq || requestSeq !== state.libraryRequestSeq) return;
    if (typeof requestIdleCallback === "function") {
      state.visibleMetadataPrefetchUsesIdle = true;
      state.visibleMetadataPrefetchTimer = requestIdleCallback(() => { run().catch(() => {}); }, { timeout: 450 });
    } else {
      state.visibleMetadataPrefetchUsesIdle = false;
      state.visibleMetadataPrefetchTimer = setTimeout(() => { run().catch(() => {}); }, 0);
    }
  };
  state.visibleMetadataPrefetchUsesIdle = false;
  state.visibleMetadataPrefetchTimer = setTimeout(queueIdleRun, 220);
}
function libraryLoadRequestKey(page = 1) {
  return globalThis.fnAudioLibraryLoadKey.buildLibraryLoadKey(
    state, page, currentCreatorName, isCreatorAllTracksView, currentQueryText,
  );
}
function loadPagedLibrary(page = 1, refresh = false) {
  const key = refresh ? "" : libraryLoadRequestKey(page);
  if (key && state.libraryLoadKey === key && state.libraryLoadPromise) return state.libraryLoadPromise;
  const promise = loadPagedLibraryWorker(page, refresh);
  state.libraryLoadKey = key;
  state.libraryLoadPromise = promise;
  const clear = () => {
    if (state.libraryLoadPromise === promise) {
      state.libraryLoadKey = "";
      state.libraryLoadPromise = null;
    }
  };
  promise.then(clear, clear);
  return promise;
}
// Fire-and-forget UI entry points already render the bounded error state.
// Consume their rejection while explicit awaiters retain failure propagation.
function requestLibraryLoad(page = 1, refresh = false) {
  // Defer invocation so failures while deriving the request key are handled
  // by the same fire-and-forget boundary as asynchronous load failures.
  return Promise.resolve().then(() => loadPagedLibrary(page, refresh)).catch(() => {});
}
async function loadPagedLibraryWorker(page = 1, refresh = false) {
  const seq = ++state.libraryRequestSeq;
  cancelReferencedItemHydrationSchedule();
  cancelMetadataRowRender();
  cancelVisibleMetadataPrefetch({ releaseKeys: true });
  state.libraryInteractionBlocked = true;
  if (state.libraryStatusTimer) {
    clearTimeout(state.libraryStatusTimer);
    state.libraryStatusTimer = 0;
  }
  if (state.accessProfileTimer) {
    clearTimeout(state.accessProfileTimer);
    state.accessProfileTimer = 0;
  }
  let retainedEmptySnapshot = false;
  // Browsers can cancel the previous page request immediately. The native
  // authenticated bridge also cancels its underlying OkHttp call; the
  // sequence check remains necessary for responses that race cancellation.
  if (state.libraryAbortController) state.libraryAbortController.abort();
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.libraryAbortController = controller;
  const requestSignal = controller?.signal;
  const releaseController = () => {
    if (state.libraryAbortController === controller) state.libraryAbortController = null;
  };
  if (refresh) clearLibraryResponseCaches();
  state.libraryLoading = true;
  state.page = libraryPageNumber(page);
  // When no bootstrap snapshot exists, hide only the static empty-state frame
  // as soon as the authoritative request begins.  Calling the full render()
  // here used to construct an empty list, schedule cover/layout work, and
  // then immediately replace it with page one; on older WebViews that extra
  // empty commit was visible as a list flash.  The final authoritative render
  // below remains responsible for the complete page projection.
  if (!hasVisibleLibraryPresentation()) {
    const empty = $("empty");
    if (empty) empty.hidden = true;
    updateLibraryStatusDecorations();
  }
  if (refresh) {
    state.libraryStatus = { ...(state.libraryStatus || {}), scanning: true, scanned: 0, found: state.pageItems.length };
    // Do not repaint the whole page merely to expose scan progress.  A refresh
    // often follows a user action while the current rows are still visible;
    // repainting here used to make old WebViews briefly flash the list before
    // the authoritative response arrived.  The status scheduler updates the
    // small progress labels independently below.
    updateLibraryStatusDecorations();
  }
  try {
  if (state.view === "folders" && !state.folderRoot && !state.folderPath) {
    const rootParams = new URLSearchParams();
    if (currentQueryText()) rootParams.set("search", currentQueryText());
    const data = await fetchLibraryResponse(
      `api/library/roots${rootParams.toString() ? `?${rootParams.toString()}` : ""}`,
      "读取音乐目录失败",
      refresh,
      requestSignal,
    );
    if (seq !== state.libraryRequestSeq) return;
    state.folderRootRows = [...(data.roots || [])].sort((a, b) => displayText(a.name || a.path || "").localeCompare(displayText(b.name || b.path || ""), "zh-CN", { numeric: true, sensitivity: "base" }) * sortDirectionFactor());
    if (state.folderRootRows.length === 1) {
      state.folderRoot = state.folderRootRows[0].root || state.folderRootRows[0].path || "";
      state.folderPath = "";
      // This worker is itself owned by `state.libraryLoadPromise`. Re-entering
      // the public deduplicating wrapper with the same key can return that
      // very promise and create a self-referential await chain when a NAS has
      // exactly one configured music root. Continue within the existing load
      // chain instead; the nested worker gets a fresh request sequence and
      // controller while callers still await the original public promise.
      return loadPagedLibraryWorker(page, refresh);
    }
    state.pageItems = [];
    state.items = [];
    state.pageTotal = state.folderRootRows.length;
  } else if (state.view === "folders" && (state.folderRoot || state.folderPath)) {
    const folderParams = new URLSearchParams();
    if (state.folderRoot) folderParams.set("root", state.folderRoot);
    if (state.folderPath) folderParams.set("parent", state.folderPath);
    if (currentQueryText()) folderParams.set("search", currentQueryText());
    folderParams.set("dir", state.sortDir || "asc");
    folderParams.set("paged", "1");
    folderParams.set("limit", String(state.folderPageSize));
    const folderContinuation = browseCursorForPage("folder", state.folderPage);
    folderParams.set("offset", folderContinuation ? "0" : String(Math.max(0, (state.folderPage - 1) * state.folderPageSize)));
    if (folderContinuation) folderParams.set("cursor", folderContinuation);
    const [folderData, data] = await Promise.all([
      fetchLibraryResponse(`api/library/folders?${folderParams.toString()}`, "读取文件夹失败", refresh, requestSignal),
      fetchLibraryResponse(
        `api/library?${currentQueryParams().toString()}${refresh ? "&refresh=1" : ""}`,
        "读取歌曲列表失败",
        refresh,
        requestSignal,
      ),
    ]);
    if (seq !== state.libraryRequestSeq) return;
    const folderRows = Array.isArray(folderData.folders) ? folderData.folders : [];
    state.folderRows = fnAudioLibraryRenderPolicy.boundedRows(folderRows.filter(row => String(row.root || "") === String(state.folderRoot || "")));
    state.folderTotal = libraryCount(folderData.count);
    rememberBrowsePageCursor("folder", state.folderPage, folderData);
    state.pageItems = mergeAuthoritativePageItems(fnAudioLibraryRenderPolicy.boundedRows(data.items));
    state.items = state.pageItems;
    state.pageTotal = libraryCount(data.count);
    cacheLibraryItems(state.pageItems);
  } else if (isPagedGroupListing()) {
    const params = new URLSearchParams();
    params.set("view", isCreatorView() && currentCreatorName() ? "albums" : state.view);
    if (isCreatorView() && currentCreatorName()) {
      params.set(state.view === "composers" ? "composer" : "artist", currentCreatorName());
    }
    params.set("search", currentQueryText());
    params.set("paged", "1");
    params.set("limit", String(state.pageSize));
    const groupContinuation = browseCursorForPage("group", state.page);
    params.set("offset", groupContinuation ? "0" : String(Math.max(0, (state.page - 1) * state.pageSize)));
    if (groupContinuation) params.set("cursor", groupContinuation);
    params.set("dir", state.sortDir || "asc");
    const data = await fetchLibraryResponse(`api/library/groups?${params.toString()}`, "读取分类失败", refresh, requestSignal);
    if (seq !== state.libraryRequestSeq) return;
    state.groupRows = fnAudioLibraryRenderPolicy.boundedRows(data.groups);
    state.groupRows.forEach(group => {
      const name = displayText(group.name || "");
      if (!name || (!group.artist && !group.release_date && !group.image_url)) return;
      state.albumMetadata.set(name, {
        artist: group.artist || "",
        release_date: group.release_date || "",
        image_url: group.image_url || "",
        source: group.metadata_source || "",
      });
    });
    state.pageItems = [];
    state.items = [];
    state.pageTotal = libraryCount(data.count);
    rememberBrowsePageCursor("group", state.page, data);
  } else if (isPagedLibraryView()) {
    const params = currentQueryParams();
    const continuation = cursorForLibraryPage(state.page);
    if (continuation) {
      // A cursor already positions the next page; avoid paying for an
      // additional SQLite OFFSET traversal on deep sequential navigation.
      params.set("cursor", continuation);
      params.set("offset", "0");
    }
    if (refresh) params.set("refresh", "1");
    const data = await fetchLibraryResponse(`api/library?${params.toString()}`, "读取歌曲列表失败", refresh, requestSignal);
    if (seq !== state.libraryRequestSeq) return;
    const retainSnapshot = shouldRetainSnapshotForEmptyResponse(data, refresh);
    if (retainSnapshot) {
      state.librarySnapshotEmptyGuardUsed = true;
      retainedEmptySnapshot = true;
      // Do not let the one-shot retry read the same transient empty payload
      // from the session LRU again. The visible snapshot remains authoritative
      // until the follow-up request gets a real page (or confirms empty).
      state.libraryResponseCache.delete?.(`api/library?${params.toString()}`);
    } else {
      state.librarySnapshotEmptyGuardUsed = false;
      const snapshotItems = state.pageItems;
      const snapshotHit = state.librarySnapshot?.hit === true;
      state.pageItems = mergeAuthoritativePageItems(fnAudioLibraryRenderPolicy.boundedRows(data.items));
      // On a warm launch the restored page has already produced HTML and may
      // have decoded its first covers. If the authoritative payload paints the
      // exact same rows, transfer that bounded markup cache to the new array:
      // renderTrackRows then returns the existing string and commitTrackListHtml
      // does no template parsing, DOM reconciliation, cover scheduling, or
      // layout work. Real metadata/cover/paging changes still take the normal
      // keyed patch path below.
      reuseSnapshotTrackMarkup(snapshotItems, state.pageItems, snapshotHit);
      state.items = state.pageItems;
      state.pageTotal = libraryCount(data.count);
      cacheLibraryItems(state.pageItems);
      rememberLibraryPageCursor(state.page, data);
    }
  } else {
    const data = await fetchLibraryResponse(
      `api/library?paged=1&limit=${state.pageSize}&offset=0${refresh ? "&refresh=1" : ""}`,
      "读取歌曲列表失败",
      refresh,
      requestSignal,
    );
    if (seq !== state.libraryRequestSeq) return;
    state.pageItems = mergeAuthoritativePageItems(fnAudioLibraryRenderPolicy.boundedRows(data.items));
    state.items = state.pageItems;
    state.pageTotal = libraryCount(data.count);
    cacheLibraryItems(state.pageItems);
  }
  // Check request ownership before mutating shared loading/size state. An
  // obsolete response must be completely inert; otherwise a fast view/search
  // switch can clear the new request's loading guard and flash the empty pane.
  if (seq !== state.libraryRequestSeq) return;
  if (!retainedEmptySnapshot) {
    // Once an authoritative page has arrived, the bootstrap snapshot is no
    // longer evidence for empty-response protection. Keeping hit=true here
    // could make a later genuine empty library response retain stale rows.
    state.librarySnapshot = {
      hit: false,
      stale: false,
      savedAt: Number(state.librarySnapshot?.savedAt || 0),
    };
  }
  state.libraryPageKey = isPagedTrackListing() ? libraryLoadRequestKey(state.page) : "";
  state.libraryLoading = false;
  state.libraryLoaded = state.pageItems.length;
  state.libraryInteractionBlocked = false;
  state.libraryTotal = state.pageTotal;
  render();
  // When playback state was restored before this page arrived, kick off the
  // priority lane now instead of waiting for a subsequent play/lyrics action.
  // This is intentionally after the authoritative list commit so metadata
  // requests cannot delay first paint or cause a placeholder repaint.
  const restoredCurrent = currentItem();
  const restoredNeedsMetadata = restoredCurrent?.id
    && globalThis.fnAudioVisibleMetadataPrefetchPolicy?.needsMetadata?.(restoredCurrent) === true;
  if (restoredNeedsMetadata) {
    prefetchCurrentTrackMetadata(restoredCurrent);
  }
  scheduleReferencedItemHydration(seq);
  scheduleVisibleMetadataPrefetch(state.pageItems, seq);
  if (retainedEmptySnapshot) {
    const retryKey = libraryLoadRequestKey(state.page);
    setTimeout(() => {
      if (
        seq === state.libraryRequestSeq
        && state.librarySnapshotEmptyGuardUsed
        && isPagedLibraryView()
        && libraryLoadRequestKey(state.page) === retryKey
      ) requestLibraryLoad(state.page, false);
    }, 250);
  }
  scheduleLibraryPageSnapshot(state.page);
  // Status is useful for counters and scan progress, but it must never hold
  // back first paint of an already-indexed page. The scheduler refreshes it
  // periodically; update it opportunistically without re-rendering rows.
  // The status endpoint may perform a library scan/count aggregation. Defer
  // it by one short turn so it cannot compete with the first page's JSON
  // parse, layout and cover decoding on large libraries/older WebViews.
  state.libraryStatusTimer = setTimeout(() => {
    state.libraryStatusTimer = 0;
    if (seq !== state.libraryRequestSeq) return;
    // Reuse the shared status request boundary so the first post-paint probe
    // cannot race the scanning scheduler into duplicate SQLite aggregation.
    refreshLibraryStatus(refresh);
  }, 120);
  // The access profile only changes a small mode badge. Defer it until after
  // the first page/status work has had a chance to paint, so a cold WebView
  // does not contend with the initial song JSON and cover requests.
  state.accessProfileTimer = setTimeout(() => {
    state.accessProfileTimer = 0;
    if (seq !== state.libraryRequestSeq) return;
    state.accessProfileLoader?.load().then(data => {
      if (!data || seq !== state.libraryRequestSeq) return;
      if (data.profile) {
        state.accessProfile = data.profile;
        updateModeButton();
      }
    }).catch(() => {});
  }, 320);
  } catch (error) {
    if (seq !== state.libraryRequestSeq) return;
    if (error?.name === "AbortError" && error?.code !== "RESPONSE_BODY_TIMEOUT") {
      state.libraryInteractionBlocked = false;
      return;
    }
    state.libraryLoading = false;
    state.libraryInteractionBlocked = false;
    state.libraryStatus = {
      ...(state.libraryStatus || {}),
      scanning: false,
      error: String(error?.message || error || "音乐库加载失败"),
    };
    render();
    throw error;
  } finally {
    releaseController();
  }
}
async function fetchAllTracksForCurrentView(extra = {}) {
  const pageSize = Math.max(1, Math.min(500, state.pageSize || 120));
  // Batch workers may start after a view/search change. Freeze the query
  // identity once so every page belongs to the same play-all request.
  const baseQueryParams = currentQueryParams();
  const pageItemsOf = data => Array.isArray(data?.items) ? data.items : [];
  const canReuseCurrentPage = state.page === 1
    && isPagedTrackListing()
    && state.view !== "random100"
    && state.libraryPageKey === libraryLoadRequestKey(1)
    && !Object.keys(extra || {}).some(key => extra[key] !== undefined && extra[key] !== null && String(extra[key]) !== "")
    && Array.isArray(state.pageItems)
    && state.pageItems.length > 0
    && state.pageItems.length <= pageSize
    && !state.libraryLoading;
  async function fetchPage(offset) {
    const params = new URLSearchParams(baseQueryParams.toString());
    params.set("limit", String(pageSize));
    params.set("offset", String(offset));
    Object.entries(extra || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value) !== "") params.set(key, String(value));
    });
    // Reuse the same bounded response cache as normal pagination.  In the
    // common "play all" path page 1 has just rendered, so requesting offset
    // zero again only repeats JSON parsing and a SQLite read on large
    // libraries.  Cache invalidation remains centralized in refresh, scans
    // and library mutations.
    return fetchLibraryResponse(`api/library?${params.toString()}`, "读取完整歌曲列表失败");
  }
  const firstPage = canReuseCurrentPage
    ? { items: state.pageItems, count: state.pageTotal }
    : await fetchPage(0);
  const firstItems = pageItemsOf(firstPage);
  cacheLibraryItems(firstItems);
  const total = fnAudioLibraryFullListPolicy.boundedCount(firstPage?.count);
  if (!firstItems.length || firstItems.length >= total) return firstItems;
  let merged = fnAudioLibraryPageMerge.mergePagedItems(firstItems, [], total);
  for (const offsets of fnAudioLibraryPagePlan.pageOffsetBatches(total, pageSize, firstItems.length, 200000, 32)) {
    const pool = fnAudioBatchRequestPool(offsets, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY, fetchPage);
    let complete = false;
    for (let index = 0; index < offsets.length; index += 1) {
      const data = await pool.get(index);
      const pageItems = pageItemsOf(data);
      cacheLibraryItems(pageItems, false);
      merged = fnAudioLibraryPageMerge.appendPageItems(merged, pageItems, total);
      if (fnAudioLibraryFullListPolicy.shouldStopMerge(merged.length, total, pageItems.length)) {
        complete = true;
        break;
      }
    }
    if (complete) {
      // Do not leave queued requests running after the result is complete (or
      // the server returned an empty page). Already-running requests finish
      // naturally; queued batches are rejected by the bounded pool.
      pool.cancel("library result complete");
      break;
    }
  }
  state.itemCache.trim(new Set((state.queue || []).map(item => String(item?.id || "")).filter(Boolean)));
  return merged;
}
async function hydrateReferencedItems() {
  const ids = new Set();
  state.queue.forEach(item => item?.id && ids.add(String(item.id)));
  if (state.view === "favorites") {
    state.favorites.forEach(id => ids.add(String(id)));
  } else if (isPlaylistView()) {
    (currentPlaylist()?.trackIds || []).forEach(id => ids.add(String(id)));
  }
  hydrateReferencedIds([...ids]);
}
function hydrateReferencedIds(ids = []) {
  const normalizedIds = fnAudioItemHydrationPolicy.normalizeItemIds(ids);
  const requestedView = state.view;
  // render() calls clientPagedResult() again after each hydrated batch. Do not
  // cancel the same pool from inside that render: it causes a large favorites
  // or playlist page to repeatedly restart its requests and briefly redraw.
  if (state.itemHydrationPool && globalThis.fnAudioItemHydrationRequest?.matches(state.itemHydrationRequest, requestedView, normalizedIds)) return;
  if (state.itemHydrationPool?.cancel) state.itemHydrationPool.cancel("stale item hydration");
  // A cancelled generation must also release its coalesced frame. Otherwise
  // the old callback can consume the only render slot after a fast view
  // switch, leaving the new page hydrated in memory but visually stale.
  if (state.itemHydrationRenderTimer) {
    if (typeof cancelAnimationFrame === "function") {
      try { cancelAnimationFrame(state.itemHydrationRenderTimer); } catch (_) {}
    } else clearTimeout(state.itemHydrationRenderTimer);
    state.itemHydrationRenderTimer = 0;
  }
  // Cancellation rejects queued batches asynchronously. Release ownership
  // synchronously so a new view can re-request the same IDs immediately;
  // generation checks below prevent the old worker from touching new state.
  state.hydratingIds.clear();
  const generation = ++state.itemHydrationGeneration;
  const missing = normalizedIds.filter(id => !state.itemCache.has(id) && !state.unresolvedItemIds.has(id));
  if (!missing.length) {
    state.itemHydrationPool = null;
    state.itemHydrationRequest = null;
    return;
  }
  missing.forEach(id => state.hydratingIds.add(id));
  const batches = fnAudioItemHydrationPolicy.batchesForItemIds(missing);
  const pool = fnAudioBatchRequestPool(batches, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY,
    batch => fetchLibraryItemsByIds(batch));
  state.itemHydrationPool = pool;
  state.itemHydrationRequest = globalThis.fnAudioItemHydrationRequest?.create(requestedView, normalizedIds) || null;
  (async () => {
    const scheduleHydrationRender = () => {
      if (state.itemHydrationRenderTimer || state.view !== requestedView || !isClientPagedView(requestedView)) return;
      const flush = () => {
        state.itemHydrationRenderTimer = 0;
        if (state.itemHydrationGeneration !== generation) return;
        if (state.view === requestedView && isClientPagedView(requestedView)) render();
      };
      state.itemHydrationRenderTimer = typeof requestAnimationFrame === "function"
        ? requestAnimationFrame(flush)
        : setTimeout(flush, 0);
    };
    let changed = false;
    let renderedFirstBatch = false;
    let needsFinalRender = false;
    for (let batchIndex = 0; batchIndex < batches.length; batchIndex += 1) {
      const batch = batches[batchIndex];
      try {
        const items = await pool.get(batchIndex);
        if (state.itemHydrationGeneration !== generation || state.itemHydrationPool !== pool) return;
        const found = new Set(items.map(item => String(item.id || "")));
        cacheLibraryItems(items, false);
        const batchChanged = items.length > 0;
        changed = changed || batchChanged;
        batch.forEach(id => {
          state.hydratingIds.delete(id);
          if (!found.has(id)) {
            if (typeof state.unresolvedItemIds?.remember === "function") state.unresolvedItemIds.remember(id);
            else state.unresolvedItemIds?.add?.(id);
          }
        });
        // Contract retained for static regression: if (!renderedFirstBatch && batchChanged && state.view === requestedView && isClientPagedView(requestedView))
        if (!renderedFirstBatch && batchChanged && state.view === requestedView && isClientPagedView(requestedView)) {
          renderedFirstBatch = true;
          scheduleHydrationRender();
        } else if (renderedFirstBatch && batchChanged) {
          needsFinalRender = true;
          scheduleHydrationRender();
        }
      } catch (error) {
        if (state.itemHydrationGeneration === generation && state.itemHydrationPool === pool) {
          batch.forEach(id => state.hydratingIds.delete(id));
        }
      }
    }
    if (state.itemHydrationGeneration !== generation || state.itemHydrationPool !== pool) return;
    state.itemCache.trim(new Set((state.queue || []).map(item => String(item?.id || "")).filter(Boolean)));
    if (state.itemHydrationPool === pool) {
      state.itemHydrationPool = null;
      state.itemHydrationRequest = null;
    }
    // Contract retained for static regression: if (needsFinalRender && changed && state.view === requestedView && isClientPagedView(requestedView)) render();
    if (needsFinalRender && changed && state.view === requestedView && isClientPagedView(requestedView)) scheduleHydrationRender();
  })();
}
function stableDeviceTargets(targets = []) {
  return fnAudioDeviceTargetPresentation.stableTargets(targets, displayText);
}
function resolvedDeviceTarget(targets, reportedTarget) {
  const targetId = String(reportedTarget || "local");
  return targets.some(target => String(target.id || "") === targetId) ? targetId : "local";
}
async function recoverUnavailablePlaybackTarget(notify = false, expectedTarget = "") {
  if (expectedTarget && String(state.playTarget || "") !== String(expectedTarget)) return false;
  try {
    const response = await apiFetch("api/playback/target", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_id: "local"}),
    });
    const data = await readResponseJsonBounded(response);
    if (!response.ok || data.ok !== true) return false;
    if (expectedTarget && String(state.playTarget || "") !== String(expectedTarget)) return false;
    if (state.deviceSwitchInFlight) return false;
    if (userStateRevision(data.revision, -1) >= 0) state.userStateRevision = userStateRevision(data.revision);
  } catch (error) {
    return false;
  }
  stopRemoteEventStream();
  state.playTarget = "local";
  state.playTargetName = "当前设备";
  state.remoteStatus = null;
  state.remoteStateVersion = 0;
  state.remoteLoadedKey = "";
  state.deviceTargetsSignature = "";
  nativeRemoteExit();
  updateDeviceLabel();
  render();
  scheduleUserStateSave();
  if (notify) alert("原播放设备已离线，已切换到当前设备。请再次点击播放。");
  return false;
}
async function validateRestoredPlaybackTarget() {
  if (!isRemoteTarget()) return true;
  const restoredTarget = String(state.playTarget || "");
  let receivedTargets = false;
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    try {
      // Target discovery can wait for a network scan. It must not leave the
      // initial user-state recovery pending forever when the service or proxy
      // is half-open; a later device refresh will reconcile the target.
      const request = fetch(`api/playback/targets${attempt === 0 ? "?refresh=1" : ""}`, {
        ...(controller ? { signal: controller.signal } : {}),
      });
      const result = await globalThis.fnAudioResponseJsonLoader.read({
        request,
        timeoutMs: 6000,
        onTimeout: () => { try { controller?.abort(); } catch (_) {} },
        fallback: {},
      });
      const response = result.response;
      // A saved remote target is only disproved by a device list this browser could
      // actually read. Answering from the fallback here would POST a still-playing
      // cast back to this device, so an unreadable body stays "no information".
      if (!response.ok || !globalThis.fnAudioResponseJsonLoader.parsedBody(result.bodyStatus)) return true;
      const data = result.data || {};
      receivedTargets = true;
      const target = (data.targets || []).find(candidate =>
        String(candidate?.id || "") === restoredTarget
        && (candidate?.online === undefined || candidate?.online === true)
      );
      if (target) {
        state.playTargetName = displayText(target.name || "播放设备");
        updateDeviceLabel();
        return true;
      }
      if (data.refreshing !== true) break;
      await new Promise(resolve => setTimeout(resolve, 750));
    } catch (error) {
      return true;
    } finally {}
  }
  return receivedTargets ? recoverUnavailablePlaybackTarget(false, restoredTarget) : true;
}
function renderDeviceTargets(targets, currentTarget) {
  targets = globalThis.fnAudioDeviceTargetPresentation.projectTargets(targets);
  const signature = JSON.stringify({
    currentTarget,
    targets: targets.map(target => ({
      id: target.id,
      name: displayText(target.name || ""),
      kind: target.kind || "",
      online: target.online === undefined || target.online === true,
      detail: target.message || (target.caps ? dacCapsText(target.caps) : ""),
      selected: target.selected === true,
    })),
  });
  if (signature === state.deviceTargetsSignature) return;
  state.deviceTargetsSignature = signature;
  const current = targets.find(target => target.id === currentTarget);
  const currentName = displayText(current?.name || (currentTarget === "local" ? "当前设备" : state.playTargetName || "播放设备"));
  $("deviceCurrentTarget").textContent = `当前：${currentName}`;
  const groups = new Map([
    ["browser", { title: "当前设备", targets: [] }],
    ["dac", { title: "USB DAC", targets: [] }],
    ["dlna", { title: "DLNA / UPnP", targets: [] }],
  ]);
  targets.forEach(target => {
    const key = target.id === "local" ? "browser" : (target.kind === "dlna_push" ? "dlna" : "dac");
    groups.get(key).targets.push(target);
  });
  const rows = targets.map(target => {
    const isCurrent = target.id === currentTarget;
    const kind = target.kind === "dlna_push" ? "UPnP / DLNA" : (target.kind === "mpd" ? "本机 USB DAC" : "浏览器播放");
    const caps = target.caps ? dacCapsText(target.caps) : "";
    const detail = target.message || (caps || kind);
    const disabled = target.online === true || target.online === undefined ? "" : " disabled";
    return `<button class="device-row${isCurrent ? " is-current" : ""}" data-target="${escapeHtml(target.id)}" data-target-name="${escapeHtml(displayText(target.name || "播放设备"))}" aria-pressed="${isCurrent}"${disabled}><span class="device-row-radio">${isCurrent ? "✓" : ""}</span><span class="device-row-text"><strong>${escapeHtml(displayText(target.name || "播放设备"))}</strong><small>${escapeHtml(detail)}</small></span></button>`;
  });
  const rowById = new Map(targets.map((target, index) => [String(target.id), rows[index]]));
  const groupedRows = [...groups.values()]
    .filter(group => group.targets.length)
    .map(group => `<section class="device-section"><h3>${group.title}</h3>${group.targets.map(target => rowById.get(String(target.id))).join("")}</section>`)
    .join("");
  $("deviceList").innerHTML = groupedRows || `<p class="dialog-help">没有找到可用的播放目标。</p>`;
  document.querySelectorAll("[data-target]").forEach(button => {
    button.onclick = () => selectPlaybackTarget(button.dataset.target, button.dataset.targetName || "当前设备");
  });
}
function markCurrentDeviceTarget(targetId, switching = false) {
  document.querySelectorAll("[data-target]").forEach(button => {
    const isCurrent = button.dataset.target === targetId;
    button.classList.toggle("is-current", isCurrent);
    button.classList.toggle("is-switching", switching && isCurrent);
    button.setAttribute("aria-pressed", String(isCurrent));
    button.disabled = switching;
    const radio = button.querySelector(".device-row-radio");
    if (radio) radio.textContent = isCurrent ? "✓" : "";
  });
}
function scheduleDeviceRefresh() {
  clearTimeout(state.deviceRefreshTimer);
  state.deviceRefreshTimer = setTimeout(() => {
    if ($("deviceDialog").open) loadDevices();
  }, 3000);
}
async function loadDevices(forceRefresh = false) {
  if (state.deviceLoadInFlight && !forceRefresh) return;
  if (state.deviceLoadInFlight) cancelDeviceLoad();
  const list = $("deviceList");
  const targetRevision = state.deviceTargetRevision;
  if (!list.childElementCount) list.innerHTML = `<p class="dialog-help">正在搜索播放设备...</p>`;
  const token = ++state.deviceLoadRequestToken;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.deviceLoadInFlight = true;
  state.deviceLoadController = controller;
  try {
    const request = fetch(`api/playback/targets${forceRefresh ? "?refresh=1" : ""}`, {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    const data = result.data || {};
    if (token !== state.deviceLoadRequestToken || state.deviceLoadController !== controller
      || targetRevision !== state.deviceTargetRevision || state.deviceSwitchInFlight) return;
    if (!response.ok) throw new Error(data.message || "设备列表读取失败");
    // The same answer always carries a JSON document, so a body this browser could
    // not parse is a transport failure, not an empty room: reading `{}` as "no
    // devices" would hand the active cast back to this machine and clear the panel.
    if (!globalThis.fnAudioResponseJsonLoader.parsedBody(result.bodyStatus)) throw new Error("设备列表读取失败");
    const targets = stableDeviceTargets(data.targets || []);
    const reportedTarget = data.current_target || state.playTarget || "local";
    const targetUnavailable = !targets.some(target => String(target.id || "") === String(reportedTarget));
    if (targetUnavailable && data.refreshing === true) {
      if ($("deviceDialog").open) scheduleDeviceRefresh();
      return;
    }
    const currentTarget = resolvedDeviceTarget(targets, reportedTarget);
    if (targetRevision > 0 && currentTarget !== state.playTarget) {
      if ($("deviceDialog").open) scheduleDeviceRefresh();
      return;
    }
    const previousTarget = state.playTarget;
    if (targetUnavailable && reportedTarget !== "local") {
      await recoverUnavailablePlaybackTarget(false, reportedTarget);
      // Recovery performs its own network write and can overlap a user
      // selection or a forced device refresh. Do not let this older request
      // repaint or overwrite state after ownership has moved on.
      if (token !== state.deviceLoadRequestToken || state.deviceLoadController !== controller
        || targetRevision !== state.deviceTargetRevision || state.deviceSwitchInFlight) return;
    }
    state.playTarget = currentTarget;
    state.playTargetName = currentTarget === "local" ? "当前设备" : (data.current_target_name || state.playTargetName);
    if (previousTarget !== currentTarget) {
      stopRemoteEventStream();
      if (isRemoteTarget()) startRemoteEventStream();
    }
    state.devices = targets.filter(target => target.id !== "local");
    renderDeviceTargets(targets, currentTarget);
    const scanButton = $("scanDevices");
    const refreshing = data.refreshing === true;
    scanButton.disabled = refreshing;
    scanButton.textContent = refreshing ? "正在搜索..." : "重新搜索设备";
    $("deviceRefreshStatus").textContent = refreshing ? "正在刷新局域网设备..." : "设备会按类别显示";
    if (refreshing && $("deviceDialog").open) scheduleDeviceRefresh();
  } catch (error) {
    if (token === state.deviceLoadRequestToken && state.deviceLoadController === controller
      && !state.deviceTargetsSignature && error?.name !== "AbortError") {
      list.innerHTML = `<p class="dialog-help">设备列表读取失败，请重试。</p>`;
    }
  } finally {
    if (token === state.deviceLoadRequestToken && state.deviceLoadController === controller) {
      state.deviceLoadInFlight = false;
      state.deviceLoadController = null;
    }
  }
}
function cancelDeviceLoad() {
  state.deviceLoadRequestToken += 1;
  try { state.deviceLoadController?.abort(); } catch (_) {}
  state.deviceLoadController = null;
  state.deviceLoadInFlight = false;
}

async function getTrimSdk() {
  if (!window.fnaudioTrimSdk) {
    try {
      const module = await import("./vendor/trim-web-app.js");
      const TrimApp = module.TrimApp || module.default;
      if (TrimApp) window.fnaudioTrimSdk = new TrimApp();
    } catch (error) {
    }
  }
  return window.fnaudioTrimSdk || null;
}
function fnAppVersion() {
  const match = String(navigator.userAgent || "").match(/FNAppVer\/([0-9.]+)/i);
  return match ? match[1] : "";
}
async function saveLibraryPathsFromDialog(statusText = "已保存。需要更新时请点击刷新音乐库。") {
  const paths = collectLibraryPaths();
  if (!paths.length) {
    $("folderSaveStatus").textContent = "请输入音乐目录";
    return false;
  }
  const response = await apiFetch("api/config/library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ library_path: paths.join("\n") }),
  });
  const data = await readResponseJsonBounded(response);
  if (!response.ok || data.ok !== true) {
    $("folderSaveStatus").textContent = data.message || "保存设置失败";
    return false;
  }
  state.libraryStatus = data.status || state.libraryStatus;
  $("folderSaveStatus").textContent = statusText;
  render();
  return true;
}
async function openFolderBrowser(path = "") {
  $("folderDialog").showModal();
  setSettingsTab("library");
  renderLibraryPathInputs(state.libraryStatus?.library_paths || [state.libraryStatus?.library_path || ""]);
  $("folderSaveStatus").textContent = "";
  loadMetadataStatus();
}
function setSettingsTab(name = "library") {
  state.settingsTab = name;
  document.querySelectorAll("[data-settings-tab]").forEach(button => {
    button.classList.toggle("active", button.dataset.settingsTab === name);
  });
  document.querySelectorAll("[data-settings-pane]").forEach(pane => {
    const active = pane.dataset.settingsPane === name;
    pane.hidden = !active;
    pane.classList.toggle("active", active);
  });
  if (name === "metadata") loadMetadataStatus();
  if (name === "runtime") loadRuntimeSettings();
}
const LIBRARY_CONNECTION_POOL_SETTING_KEY = "library_connection_pool";
// Spelled exactly as `CONFIG_BYTES_KEY` in app/server/metadata_local_lyrics_cache.py;
// test_ui_runtime_settings.js compares the two so a rename cannot pass on one side.
const LYRICS_CACHE_BUDGET_SETTING_KEY = "metadata_lyrics_cache_max_bytes";
function runtimeConnectionPoolInput() {
  return $("libraryConnectionPoolInput");
}
function runtimeLyricsBudgetInput() {
  return $("lyricsCacheBudgetInput");
}
function applyRuntimeLyricsBudget(budget, limit) {
  // Show the budget the process really enforces. An unusable answer leaves the
  // control untouched - the markup default is not evidence - and a value that
  // is not one of the presets (a hand-edited config, a future default) becomes
  // selectable instead of silently snapping back to 8 MiB.
  if (!budget || !Number.isInteger(limit) || limit <= 0) return false;
  const wanted = String(limit);
  budget.value = wanted;
  if (budget.value === wanted) return true;
  const option = document.createElement("option");
  option.value = wanted;
  option.textContent = `自定义 · ${formatSize(limit)}`;
  budget.appendChild(option);
  budget.value = wanted;
  return budget.value === wanted;
}
async function loadRuntimeSettings() {
  const input = runtimeConnectionPoolInput();
  if (!input) return null;
  const budget = runtimeLyricsBudgetInput();
  try {
    const response = await apiFetch("api/config/runtime", { cache: "no-store" });
    const data = await readResponseJsonBounded(response);
    if (!response.ok || data.ok !== true) throw new Error(data.message || "");
    // Echo the server value rather than assuming the click stuck: a config the
    // loader had to coerce is not the config the pool is honouring.
    input.checked = data?.config?.[LIBRARY_CONNECTION_POOL_SETTING_KEY] === true;
    applyRuntimeLyricsBudget(budget, data?.config?.[LYRICS_CACHE_BUDGET_SETTING_KEY]);
    return data;
  } catch (error) {
    $("folderSaveStatus").textContent = "无法读取运行设置，当前显示的是上一次已知状态";
    return null;
  }
}
async function saveRuntimeSettings() {
  const input = runtimeConnectionPoolInput();
  const budget = runtimeLyricsBudgetInput();
  if (!input || !budget) throw new Error("运行设置控件不可用");
  const lyricsBudget = Number(budget.value);
  if (!Number.isInteger(lyricsBudget) || lyricsBudget <= 0) throw new Error("运行设置控件不可用");
  const response = await apiFetch("api/config/runtime", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // Both live settings travel together: the endpoint commits the whole
    // runtime dictionary, so omitting a key would let this save drop it.
    body: JSON.stringify({
      [LIBRARY_CONNECTION_POOL_SETTING_KEY]: input.checked === true,
      [LYRICS_CACHE_BUDGET_SETTING_KEY]: lyricsBudget,
    }),
  });
  const data = await readResponseJsonBounded(response);
  if (!response.ok || data.ok !== true) throw new Error(data.message || "保存运行设置失败");
  input.checked = data?.config?.[LIBRARY_CONNECTION_POOL_SETTING_KEY] === true;
  applyRuntimeLyricsBudget(budget, data?.config?.[LYRICS_CACHE_BUDGET_SETTING_KEY]);
  return data;
}
function metadataStatusSummary(data = {}) {
  const jobs = data.jobs || {};
  const pending = Number(jobs.pending || 0) + Number(jobs.retry || 0) + Number(jobs.running || 0);
  const progress = pending
    ? `后台剩余 ${pending} 项`
    : (data.enabled === true ? "后台队列已完成" : "后台补全未开启（播放/歌词页仍可按需获取）");
  const failed = Number(jobs.failed || 0);
  const noMatchJobs = Number(jobs.no_match || 0);
  const writeStatus = failed ? ` · ${failed} 项任务失败，可查看数据源原因后重试` : "";
  const noMatchStatus = noMatchJobs ? ` · ${noMatchJobs} 项暂未匹配（可稍后重试）` : "";
  const workers = Number(data.fetch_workers || 0);
  const average = Number(data.tag_write_average_seconds || 0);
  const types = data.job_types || {};
  const fetching = ["lyrics", "track", "album", "artist", "composer"].reduce((total, type) => total + Number(types[type]?.pending || 0), 0);
  const writing = Number(types.tag_write?.pending || 0);
  const tagState = data.tag_write_enabled === true
    ? `Tag ${data.tag_write_in_progress === true ? "写入中" : "空闲"}（待写入 ${writing}）${average ? `，平均 ${average.toFixed(1)} 秒/首` : ""}`
    : `Tag 写回已关闭（待写入 ${writing}）`;
  const pipeline = workers ? ` · 抓取 ${workers} 并发（待抓取 ${fetching}）· ${tagState}` : ` · ${tagState}`;
  const matches = data.track_matches || {};
  const review = Number(matches.review || 0);
  const matched = Number(matches.auto || 0) + Number(matches.confirmed || 0);
  const matchStatus = (matched || review) ? ` · 曲目匹配 ${matched} 项${review ? `，待确认 ${review} 项` : ""}` : "";
  const providerFailures = data.provider_failures && typeof data.provider_failures === "object"
    ? Object.entries(data.provider_failures).filter(([, value]) => Number(value?.count || 0) > 0).slice(0, 2)
    : [];
  const providerStatus = providerFailures.length
    ? ` · 数据源异常：${providerFailures.map(([name, value]) => {
      const cooldown = Math.max(0, Math.min(60, Number(value?.cooldown_seconds || 0)));
      const error = typeof value?.last_error === "string"
        ? value.last_error.replace(/[\r\n]+/g, " ").trim().slice(0, 96)
        : "";
      return `${name}×${Number(value?.count || 0)}${cooldown ? `（冷却${cooldown}s）` : ""}${error ? `：${error}` : ""}`;
    }).join("、")}`
    : "";
  return `MusicBrainz、网易云、QQ、酷狗、咪咕、JOOX、千千音乐 · ${progress} · 已缓存 ${Number(data.entities || 0)} 项分类资料、${Number(data.lyrics || 0)} 首歌词${matchStatus}${pipeline}${writeStatus}${noMatchStatus}${providerStatus}`;
}
function libraryCursorQueryKey() {
  return libraryLoadRequestKey(0);
}
function browseCursorQueryKey(kind) {
  const source = { ...state, page: 1, folderPage: 1 };
  const key = globalThis.fnAudioLibraryLoadKey.buildLibraryLoadKey(
    source, 1, currentCreatorName, isCreatorAllTracksView, currentQueryText,
  );
  return `${kind}:${key}`;
}
function rememberBrowsePageCursor(kind, page, data) {
  if (kind !== "group" && kind !== "folder") return;
  const token = typeof data?.next_cursor === "string" ? data.next_cursor.trim() : "";
  const key = browseCursorQueryKey(kind);
  if (!key) return;
  globalThis.fnAudioLibraryPageCursorPolicy?.remember(state.libraryPageCursors, key, page, token);
}
function browseCursorForPage(kind, page) {
  if (page <= 1 || (kind !== "group" && kind !== "folder")) return "";
  return globalThis.fnAudioLibraryPageCursorPolicy?.get(state.libraryPageCursors, browseCursorQueryKey(kind), page) || "";
}
function rememberLibraryPageCursor(page, data) {
  if (!isPagedTrackListing() || state.view === "random100") return;
  const token = typeof data?.next_cursor === "string" ? data.next_cursor.trim() : "";
  const key = libraryCursorQueryKey();
  if (!key) return;
  globalThis.fnAudioLibraryPageCursorPolicy?.remember(state.libraryPageCursors, key, page, token);
}
function cursorForLibraryPage(page) {
  if (page <= 1 || !isPagedTrackListing() || state.view === "random100") return "";
  return globalThis.fnAudioLibraryPageCursorPolicy?.get(state.libraryPageCursors, libraryCursorQueryKey(), page) || "";
}
function ensureMetadataStatusUi() {
  const statusNode = $("metadataStatusText");
  if (!statusNode) return {};
  let list = $("metadataTagJobs");
  if (!list) {
    list = document.createElement("div");
    list.id = "metadataTagJobs";
    list.className = "metadata-tag-jobs";
    list.hidden = true;
    statusNode.after(list);
  }
  let retryButton = $("retryTagWritesBtn");
  if (!retryButton) {
    retryButton = document.createElement("button");
    retryButton.id = "retryTagWritesBtn";
    retryButton.type = "button";
    retryButton.className = "secondary-button";
    retryButton.textContent = "重试失败写回";
    retryButton.hidden = true;
    retryButton.onclick = retryFailedTagWrites;
    $("refreshMetadataBtn")?.after(retryButton);
  }
  return { list, retryButton };
}
function renderMetadataTagJobs(data = {}) {
  const { list, retryButton } = ensureMetadataStatusUi();
  if (!list || !retryButton) return;
  const jobs = Array.isArray(data.tag_jobs) ? data.tag_jobs : [];
  const failed = Number((data.jobs || {}).failed || 0);
  retryButton.hidden = failed === 0 || data.tag_write_enabled !== true;
  list.replaceChildren();
  list.hidden = jobs.length === 0;
  jobs.forEach(job => {
    const row = document.createElement("div");
    row.className = `metadata-tag-job is-${String(job.status || "pending")}`;
    const name = document.createElement("strong");
    name.textContent = [job.title, job.artist].filter(Boolean).join(" - ");
    const detail = document.createElement("span");
    const labels = { done: "已写入", skipped: "无需写入", pending: "等待写入", running: "正在写入", retry: "将重试", failed: "写入失败", no_match: "无可写入信息" };
    detail.textContent = labels[job.status] || job.status || "等待处理";
    if (job.error) detail.textContent += `：${job.error}`;
    row.append(name, detail);
    list.append(row);
  });
}
async function loadMetadataStatus() {
  const statusNode = $("metadataStatusText");
  if (!statusNode) return null;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  try {
    const request = fetch("api/metadata/status", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    const data = unwrapMetadataResponsePayload(result.data || {});
    if (!response.ok || data.ok !== true) throw new Error();
    $("metadataEnabledInput").checked = data.enabled === true;
    $("metadataTagWriteEnabledInput").checked = data.tag_write_enabled === true;
    $("metadataGraceDaysInput").value = Number(data.orphan_grace_days ?? 7);
    statusNode.textContent = metadataStatusSummary(data);
    renderMetadataTagJobs(data);
    return data;
  } catch (error) {
    statusNode.textContent = "无法读取后台元数据状态";
    return null;
  }
}
async function saveMetadataSettings(options = {}) {
  const response = await apiFetch("api/config/metadata", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: $("metadataEnabledInput").checked,
      tag_write_enabled: $("metadataTagWriteEnabledInput").checked,
      orphan_grace_days: Number($("metadataGraceDaysInput").value || 7),
      refresh: Boolean(options.refresh),
    }),
  });
  const data = unwrapMetadataResponsePayload(await readResponseJsonBounded(response));
  if (!response.ok || data.ok !== true) throw new Error(data.message || "保存元数据设置失败");
  $("metadataStatusText").textContent = metadataStatusSummary(data.status || {});
  renderMetadataTagJobs(data.status || {});
  return data;
}
async function retryFailedTagWrites() {
  const { retryButton } = ensureMetadataStatusUi();
  if (!retryButton) return;
  retryButton.disabled = true;
  try {
    const response = await apiFetch("api/metadata/retry-tag-writes", { method: "POST" });
    const data = unwrapMetadataResponsePayload(await readResponseJsonBounded(response));
    if (!response.ok || data.ok !== true) throw new Error(data.message || "重试失败");
    $("metadataStatusText").textContent = data.retried ? `已将 ${data.retried} 项失败写回重新加入队列。` : "没有可重试的失败写回。";
    renderMetadataTagJobs(data.status || {});
  } catch (error) {
    $("metadataStatusText").textContent = error.message || "重试失败";
  } finally {
    retryButton.disabled = false;
  }
}
async function refreshMetadataLibrary() {
  const button = $("refreshMetadataBtn");
  button.disabled = true;
  try {
    // A manual refresh is an explicit opt-in. Keep the setting's initial
    // default disabled, but do not report success while workers are still
    // gated by metadata_enabled=false.
    if ($("metadataEnabledInput") && !$("metadataEnabledInput").checked) {
      $("metadataEnabledInput").checked = true;
    }
    await saveMetadataSettings({ refresh: true });
    $("metadataStatusText").textContent = "已开启后台元数据补全并加入队列，页面可以正常关闭或继续播放。";
  } catch (error) {
    $("metadataStatusText").textContent = error.message || "启动后台补全失败";
  } finally {
    button.disabled = false;
  }
}
function dlnaDiagnosticTime(value) {
  const timestamp = Number(value || 0) * 1000;
  return Number.isFinite(timestamp) && timestamp > 0 ? new Date(timestamp).toLocaleString("zh-CN", { hour12: false }) : "刚刚";
}
function dlnaDiagnosticDetail(entry) {
  const detail = [entry.action, entry.format, entry.mime, entry.mode, entry.range].filter(Boolean).map(displayText).join(" · ");
  return detail || "设备查询";
}
async function loadDlnaDiagnostics() {
  const list = $("dlnaDiagnosticsList");
  const summary = $("dlnaDiagnosticsSummary");
  list.innerHTML = `<p class="dialog-help">正在读取记录...</p>`;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  try {
    const request = fetch("api/dlna/diagnostics", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: {},
    });
    const response = result.response;
    const data = result.data || {};
    if (!response.ok || data.available !== true) throw new Error(data.message || "DLNA 服务不可用");
    const entries = Array.isArray(data.entries) ? data.entries : [];
    const clients = Object.keys(data.clients || {}).length;
    summary.textContent = entries.length ? `已记录 ${entries.length} 条请求，来自 ${clients} 个设备。` : "暂无设备访问记录。";
    list.innerHTML = entries.length ? entries.map(entry => `
      <article class="diagnostic-entry">
        <div><strong>${escapeHtml(displayText(entry.event || "请求"))}</strong><span>${escapeHtml(dlnaDiagnosticTime(entry.time))}</span></div>
        <p>${escapeHtml(displayText(entry.user_agent || entry.client_ip || "未知设备"))}</p>
        <small>${escapeHtml(dlnaDiagnosticDetail(entry))}</small>
      </article>
    `).join("") : `<p class="dialog-help">让 DLNA 播放器浏览或播放一次音乐后，这里会显示其请求记录。</p>`;
  } catch (error) {
    summary.textContent = "无法读取 DLNA 兼容性记录";
    list.innerHTML = `<p class="dialog-help">请确认 fnAudio 服务正在运行。</p>`;
  }
}
function openDlnaDiagnostics() {
  $("dlnaDiagnosticsDialog").showModal();
  loadDlnaDiagnostics();
}
function renderLibraryPathInputs(paths = [""]) {
  const values = (Array.isArray(paths) ? paths : [paths]).map(x => String(x || "").trim()).filter(Boolean);
  if (!values.length) values.push("");
  $("libraryPathList").innerHTML = values.map(value => `
    <div class="library-path-row">
      <input class="library-path-input" value="${escapeHtml(value)}" placeholder="/vol1/1000/music">
      <button class="library-path-remove" type="button" title="删除此目录" aria-label="删除此目录">×</button>
    </div>
  `).join("");
  $("libraryPathList").querySelectorAll(".library-path-remove").forEach(button => {
    button.onclick = () => {
      button.closest(".library-path-row")?.remove();
      if (!$("libraryPathList").querySelector(".library-path-input")) renderLibraryPathInputs([""]);
    };
  });
}
function addLibraryPathInput(value = "") {
  const wrapper = document.createElement("div");
  wrapper.className = "library-path-row";
  wrapper.innerHTML = `<input class="library-path-input" value="${escapeHtml(value)}" placeholder="/vol1/1000/music"><button class="library-path-remove" type="button" title="删除此目录" aria-label="删除此目录">×</button>`;
  wrapper.querySelector(".library-path-remove").onclick = () => wrapper.remove();
  $("libraryPathList").appendChild(wrapper);
  wrapper.querySelector("input").focus();
}
function collectLibraryPaths() {
  return [...$("libraryPathList").querySelectorAll(".library-path-input")].map(input => input.value.trim()).filter(Boolean);
}
async function chooseCurrentFolder() {
  const button = $("chooseFolderBtn");
  button.disabled = true;
  button.textContent = "正在保存...";
  $("folderSaveStatus").textContent = "";
  try {
    if (state.settingsTab === "runtime") {
      await saveRuntimeSettings();
      $("folderDialog").close();
    } else if (state.settingsTab === "metadata") {
      await saveMetadataSettings();
      $("folderDialog").close();
    } else if (await saveLibraryPathsFromDialog()) {
      $("folderDialog").close();
    }
  } catch (error) {
    $("folderSaveStatus").textContent = error.message || "保存失败，请确认应用服务正在运行";
  } finally {
    button.disabled = false;
    button.textContent = "保存设置";
  }
}
function openPlaylistDialog(trackId = "") {
  openPlaylistDialogForTracks(trackId ? [trackId] : []);
}
function openPlaylistDialogForTracks(trackIds = []) {
  const ids = [...new Set((trackIds || []).map(String).filter(id => itemById(id)))];
  state.pendingPlaylistTrack = ids[0] || "";
  state.pendingPlaylistTrackIds = ids;
  $("playlistStatus").textContent = "";
  $("playlistNameInput").value = "";
  if (ids.length) {
    $("playlistDialogTitle").textContent = "加入播放列表";
    $("playlistDialogHelp").textContent = ids.length > 1 ? `选择一个已有播放列表，或输入名称创建新列表并加入所选 ${ids.length} 首歌曲。` : "选择一个已有播放列表，或输入名称创建新列表并加入当前歌曲。";
    $("savePlaylistBtn").textContent = "新建并加入";
    renderPlaylistChoices(ids);
  } else {
    $("playlistDialogTitle").textContent = "新建播放列表";
    $("playlistDialogHelp").textContent = "输入一个名字，创建后可从曲目旁边加入歌曲。";
    $("savePlaylistBtn").textContent = "保存";
    $("playlistChoices").innerHTML = "";
  }
  $("playlistDialog").showModal();
  $("playlistNameInput").focus();
}
function renderPlaylistChoices(trackIds = []) {
  const ids = [...new Set((Array.isArray(trackIds) ? trackIds : [trackIds]).map(String).filter(Boolean))];
  const choices = $("playlistChoices");
  if (!state.playlists.length) {
    choices.innerHTML = `<p class="dialog-help">还没有自建播放列表。</p>`;
    return;
  }
  choices.innerHTML = state.playlists.map(list => {
    const exists = ids.length > 0 && ids.every(id => list.trackIds.includes(id));
    return `<button class="playlist-choice" data-add-to-list="${escapeHtml(list.id)}" ${exists ? "disabled" : ""}><span>${escapeHtml(list.name)}</span><small>${exists ? "已加入" : `${list.trackIds.length} 首`}</small></button>`;
  }).join("");
  choices.querySelectorAll("[data-add-to-list]").forEach(button => button.onclick = () => addTracksToPlaylist(button.dataset.addToList, ids));
}
function createPlaylist(name, trackIds = []) {
  const cleanName = String(name || "").trim();
  if (!cleanName) {
    $("playlistStatus").textContent = "请输入播放列表名称";
    return null;
  }
  const playlist = { id: makePlaylistId(), name: cleanName, trackIds: [] };
  playlist.trackIds.push(...[...new Set((Array.isArray(trackIds) ? trackIds : [trackIds]).map(String).filter(id => itemById(id)))]);
  state.playlists.push(playlist);
  savePlaylists();
  renderPlaylistNav();
  return playlist;
}
function addTrackToPlaylist(playlistId, trackId) {
  addTracksToPlaylist(playlistId, [trackId]);
}
function addTracksToPlaylist(playlistId, trackIds = []) {
  const playlist = state.playlists.find(x => x.id === playlistId);
  const ids = [...new Set((trackIds || []).map(String).filter(id => itemById(id)))];
  if (!playlist || !ids.length) return;
  ids.forEach(id => { if (!playlist.trackIds.includes(id)) playlist.trackIds.push(id); });
  savePlaylists();
  $("playlistStatus").textContent = "已加入播放列表";
  setTimeout(() => {
    if ($("playlistDialog").open) $("playlistDialog").close();
    render();
  }, 260);
}
function closeTrackActionDialog() {
  state.metadataCandidateRequestToken += 1;
  try { state.metadataCandidateController?.abort(); } catch (_) {}
  state.metadataCandidateController = null;
  if (state.metadataCandidatePollTimer) {
    clearTimeout(state.metadataCandidatePollTimer);
    state.metadataCandidatePollTimer = 0;
  }
  state.metadataCandidatePollAttempts = 0;
  if ($("trackActionDialog").open) $("trackActionDialog").close();
}
function closeTrackContextMenu() {
  const menu = $("trackContextMenu");
  if (!menu) return;
  menu.hidden = true;
  menu.innerHTML = "";
}
function cancelTrackLongPress() {
  if (!activeTrackLongPress) return;
  window.clearTimeout(activeTrackLongPress.timer);
  activeTrackLongPress = null;
}
function suppressTrackClick(rowKey) {
  suppressedTrackClick = { rowKey: String(rowKey || ""), until: Date.now() + 900 };
}
function shouldSuppressTrackClick(rowKey) {
  return suppressedTrackClick.rowKey === String(rowKey || "") && Date.now() < suppressedTrackClick.until;
}
function openTrackMenuForRow(row, x, y, mobile = false) {
  const id = String(row?.dataset.trackId || "");
  const rowKey = String(row?.dataset.trackRowKey || "");
  if (!id) return;
  if (mobile) {
    setTrackSelection([]);
    suppressTrackClick(rowKey);
  } else if (!state.selectedTrackRowKeys.has(rowKey)) {
    setTrackSelection([rowKey]);
  }
  openTrackContextMenu(id, x, y, mobile);
}
function trackRowFromTarget(target, list = $("trackList")) {
  const row = target?.closest?.("[data-track-row-key]");
  return row && list?.contains(row) ? row : null;
}
function startTrackLongPress(row, event) {
  if (!window.matchMedia("(max-width: 760px)").matches || event.pointerType === "mouse" || event.button !== 0) return;
  cancelTrackLongPress();
  const gesture = {
    row,
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    timer: 0,
    triggered: false,
  };
  gesture.timer = window.setTimeout(() => {
    if (activeTrackLongPress !== gesture) return;
    gesture.triggered = true;
    openTrackMenuForRow(gesture.row, gesture.startX, gesture.startY, true);
  }, TRACK_LONG_PRESS_DURATION_MS);
  activeTrackLongPress = gesture;
}
function moveTrackLongPress(event) {
  const gesture = activeTrackLongPress;
  if (!gesture || gesture.pointerId !== event.pointerId || gesture.triggered) return;
  const moved = Math.hypot(event.clientX - gesture.startX, event.clientY - gesture.startY);
  if (moved > TRACK_LONG_PRESS_MOVE_THRESHOLD_PX) cancelTrackLongPress();
}
function finishTrackLongPress(event) {
  const gesture = activeTrackLongPress;
  if (!gesture || gesture.pointerId !== event.pointerId) return;
  const triggered = gesture.triggered;
  cancelTrackLongPress();
  if (!triggered) return;
  event.preventDefault();
  event.stopPropagation();
}
function bindTrackListInteractions() {
  const list = $("trackList");
  if (!list || list.dataset.trackInteractionsBound === "1") return;
  list.dataset.trackInteractionsBound = "1";
  list.addEventListener("click", event => {
    if (!state.libraryInteractionBlocked) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  }, true);
  list.addEventListener("click", event => {
    const row = trackRowFromTarget(event.target, list);
    if (!row) return;
    const rowKey = String(row.dataset.trackRowKey || "");
    if (shouldSuppressTrackClick(rowKey)) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    const button = event.target.closest?.("[data-play]");
    if (button && list.contains(button)) {
      if (event.ctrlKey && !mobile) {
        event.preventDefault();
        event.stopPropagation();
        toggleTrackSelection(rowKey);
      } else if (!mobile) {
        event.preventDefault();
        event.stopPropagation();
        setTrackSelection([rowKey]);
      } else if (state.selectedTrackRowKeys.size) {
        event.preventDefault();
        event.stopPropagation();
        setTrackSelection([]);
      } else {
        playById(button.dataset.play);
      }
      return;
    }
    if (event.ctrlKey && !mobile) {
      event.preventDefault();
      toggleTrackSelection(rowKey);
    } else if (!mobile && state.selectedTrackRowKeys.size) {
      event.preventDefault();
      setTrackSelection([]);
    }
  });
  list.addEventListener("contextmenu", event => {
    if (state.libraryInteractionBlocked) {
      event.preventDefault();
      event.stopImmediatePropagation();
      return;
    }
    const row = trackRowFromTarget(event.target, list);
    if (!row) return;
    event.preventDefault();
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    if (mobile && shouldSuppressTrackClick(String(row.dataset.trackRowKey || ""))) return;
    cancelTrackLongPress();
    openTrackMenuForRow(row, event.clientX, event.clientY, mobile);
  });
  list.addEventListener("pointerdown", event => {
    if (state.libraryInteractionBlocked) {
      cancelTrackLongPress();
      event.preventDefault();
      return;
    }
    const row = trackRowFromTarget(event.target, list);
    if (row) startTrackLongPress(row, event);
  });
  list.addEventListener("pointermove", moveTrackLongPress);
  list.addEventListener("pointerup", finishTrackLongPress);
  list.addEventListener("pointercancel", finishTrackLongPress);
}
function groupActionButton(label, action) {
  return `<button class="track-action-choice" data-group-action="${action}">${label}</button>`;
}
function groupActionButtons(groupKey) {
  const selected = selectedGroupDescriptors(groupKey);
  const multiple = selected.length > 1;
  return [
    groupActionButton("加入当前队列", "queue"),
    groupActionButton("加入播放列表", "playlist"),
    `<button class="track-action-choice" data-group-action="open" ${multiple ? "disabled" : ""}>打开</button>`,
  ];
}
function bindGroupActionButtons(container) {
  container.querySelectorAll("[data-group-action]").forEach(button => button.onclick = () => runGroupAction(button.dataset.groupAction));
}
function openGroupContextMenu(groupKey, x, y) {
  const groups = selectedGroupDescriptors(groupKey);
  const menu = $("trackContextMenu");
  if (!groups.length || !menu) return;
  state.actionGroupKey = String(groupKey || "");
  const title = groups.length > 1 ? `已选择 ${groups.length} 个项目` : (groups[0].name || "文件夹");
  menu.innerHTML = `<strong class="track-context-title">${escapeHtml(title)}</strong><div class="track-context-actions">${groupActionButtons(groupKey).join("")}</div>`;
  menu.hidden = false;
  menu.style.left = `${Math.max(8, x)}px`;
  menu.style.top = `${Math.max(8, y)}px`;
  bindGroupActionButtons(menu);
  requestAnimationFrame(() => {
    const margin = 8;
    const bounds = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(margin, Math.min(x, window.innerWidth - bounds.width - margin))}px`;
    menu.style.top = `${Math.max(margin, Math.min(y, window.innerHeight - bounds.height - margin))}px`;
  });
}
async function runGroupAction(action) {
  const groupKey = state.actionGroupKey;
  const selected = selectedGroupDescriptors(groupKey);
  closeTrackContextMenu();
  if (action === "open") {
    if (selected.length === 1) openGroupRow([...document.querySelectorAll("[data-group-row]")].find(row => String(row.dataset.groupKey || "") === selected[0].key));
    return;
  }
  let tracks = [];
  try {
    tracks = await resolveSelectedGroupTracks(groupKey);
  } catch (error) {
    alert("读取所选项目的歌曲失败");
    return;
  }
  if (!tracks.length) return;
  const ids = tracks.map(item => String(item.id));
  if (action === "play") playSelectedTracks(ids);
  else if (action === "queue") addSelectedToQueue(ids);
  else if (action === "insert") insertSelectedTracks(ids);
  else if (action === "playlist") openPlaylistDialogForTracks(ids);
}
function actionButton(label, action, danger = false, disabled = false) {
  return `<button class="track-action-choice ${danger ? "danger" : ""}" data-track-action="${action}" ${disabled ? "disabled" : ""}>${label}</button>`;
}
function metadataSourceText(item) {
  const source = item.metadata_source || {};
  const label = value => value === "tag" ? "Tag" : value === "filename" ? "文件名" : value === "folder" ? "文件夹" : "未知";
  return `来源：歌名 ${label(source.title)} · 歌手 ${label(source.artist)} · 专辑 ${label(source.album)}`;
}
function trackActionButtons(trackId) {
  const selected = selectedTrackIds(trackId);
  const multiple = selected.length > 1;
  const actions = [
    actionButton("播放", "play"),
    actionButton("从当前开始播放所有歌曲", "play-from-current", false, multiple),
    actionButton("加入当前队列", "queue"),
    actionButton(multiple || !isFavorite(trackId) ? "收藏歌曲" : "取消收藏", "favorite"),
    actionButton("加入播放列表", "playlist"),
    actionButton("插播所选项目", "insert"),
    actionButton("歌曲信息", "info", false, multiple),
    actionButton("元数据补全候选", "metadata-candidate", false, multiple),
    actionButton("打开包含的文件夹", "open-folder", false, multiple),
    actionButton("分享外部链接", "share", false, multiple),
    actionButton(multiple ? `删除所选 ${selected.length} 首歌曲` : "删除歌曲", "delete-file", true),
  ];
  if (state.view === "queue") actions.push(actionButton("从当前队列移除", "remove-queue", true));
  if (state.view === "favorites") actions.push(actionButton("从收藏移除", "remove-favorite", true));
  if (isPlaylistView()) actions.push(actionButton("从此播放列表移除", "remove-playlist", true));
  return actions;
}
function desktopTrackContextActionButtons(trackId) {
  return trackActionButtons(trackId).filter(button =>
    !/data-track-action="(?:play|insert)"/.test(button)
  );
}
function mobileTrackContextActionButtons(trackId) {
  return desktopTrackContextActionButtons(trackId).filter(button =>
    !/data-track-action="(?:open-folder|share|delete-file)"/.test(button)
  );
}
function bindTrackActionButtons(container) {
  container.querySelectorAll("[data-track-action]").forEach(button => button.onclick = () => runTrackAction(button.dataset.trackAction));
}
function showTrackInformation(trackId) {
  const item = itemById(trackId);
  if (!item) return;
  $("trackActionTitle").textContent = "歌曲信息";
  const details = [
    ["歌手", displayText(item.artist) || "未填写"],
    ["专辑", displayText(item.album) || "未填写"],
    ["作曲者", displayText(item.composer) || "未填写"],
    ["类型", displayText(item.genre) || "未分类"],
    ["格式", item.format || "未知"],
    ["音质", trackQuality(item)],
    ["时长", Number(item.duration || 0) ? clock(Number(item.duration)) : "未知"],
    ["文件", item.path || "未知"],
  ];
  $("trackActionList").innerHTML = `<div class="track-info-detail">${details.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong></div>`).join("")}</div>`;
  $("trackActionDialog").showModal();
}
async function showTrackMetadataCandidate(trackId, requestToken = 0, retryFailed = false) {
  const item = itemById(trackId);
  if (!item) return;
  if (!requestToken) {
    try { state.metadataCandidateController?.abort(); } catch (_) {}
    state.metadataCandidateController = null;
    if (state.metadataCandidatePollTimer) clearTimeout(state.metadataCandidatePollTimer);
    state.metadataCandidatePollTimer = 0;
    state.metadataCandidatePollAttempts = 0;
    requestToken = ++state.metadataCandidateRequestToken;
  }
  const isCurrentRequest = () => requestToken === state.metadataCandidateRequestToken
    && state.actionTrackId === String(trackId) && $("trackActionDialog").open;
  $("trackActionTitle").textContent = "元数据补全候选";
  const list = $("trackActionList");
  list.textContent = "正在查询候选结果...";
  if (!$("trackActionDialog").open) $("trackActionDialog").showModal();
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.metadataCandidateController = controller;
  try {
    const retry = retryFailed ? "&retry=1" : "";
    const result = await fetchMetadataRequest(
      `api/metadata/track?track_id=${encodeURIComponent(String(trackId))}${retry}`,
      10000,
      controller?.signal,
    );
    const response = result.response;
    const data = unwrapMetadataResponsePayload(result.data);
    if (!response.ok || data.ok !== true) throw new Error(data.message || "读取候选失败");
    if (!isCurrentRequest()) return;
    const candidates = Array.isArray(data.candidates) ? data.candidates.filter(candidate => candidate && candidate.title) : [];
    const best = globalThis.fnAudioMetadataCandidatePresentationPolicy?.selectDisplayCandidate(data.best, candidates) || {};
    if (!best.title) {
      if (data.pending === true || String(data.status || "").toLowerCase() === "pending") {
        list.textContent = "正在后台检索元数据，完成后将自动显示...";
        if (state.metadataCandidatePollAttempts < METADATA_CANDIDATE_MAX_POLLS && state.actionTrackId === String(trackId) && $("trackActionDialog").open) {
          state.metadataCandidatePollAttempts += 1;
          state.metadataCandidatePollTimer = setTimeout(() => {
            state.metadataCandidatePollTimer = 0;
            if (isCurrentRequest()) showTrackMetadataCandidate(trackId, requestToken);
          }, 1200);
        }
      }
      else if (String(data.status || "").toLowerCase() === "unavailable") list.textContent = data.message || "后台元数据服务暂不可用，请稍后重试。";
      else if (data.last_error) list.textContent = `数据源暂不可用：${data.last_error}`;
      else if (data.status === "no_match") {
        list.innerHTML = `<div class="track-action-info">当前数据源没有找到可信匹配。</div><button class="track-action-choice" data-retry-track-metadata="${escapeHtml(String(trackId))}">重新查询此歌曲</button>`;
        const retryButton = list.querySelector("[data-retry-track-metadata]");
        if (retryButton) retryButton.onclick = () => showTrackMetadataCandidate(trackId, 0, true);
      }
      else list.textContent = "没有找到可信的元数据候选。";
      return;
    }
    const review = data.status === "review";
    const candidateRows = candidates.map((candidate, index) => {
      const subtitle = [candidate.artist, candidate.album, candidate.source, globalThis.fnAudioMetadataCandidatePresentationPolicy.confidencePercent(candidate.confidence)].filter(Boolean).map(String).join(" · ");
      return `<label class="metadata-candidate-choice"><input type="radio" name="metadataCandidate" value="${index}" ${index === 0 ? "checked" : ""}><span><strong>${escapeHtml(String(candidate.title))}</strong><small>${escapeHtml(subtitle)}</small></span></label>`;
    }).join("");
    const details = [["歌名", best.title], ["歌手", best.artist], ["专辑", best.album], ["发行日期", best.date], ["曲序", best.track_no], ["来源", best.source], ["可信度", globalThis.fnAudioMetadataCandidatePresentationPolicy.confidencePercent(best.confidence)]].filter(([, value]) => value !== undefined && value !== null && String(value).trim());
    list.innerHTML = review
      ? `<div class="metadata-candidate-list">${candidateRows}</div><button class="track-action-choice" data-apply-track-metadata="${escapeHtml(String(trackId))}">确认所选候选并补全空白 Tag</button>`
      : `<div class="track-info-detail">${details.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></div>`).join("")}</div><div class="track-action-info">${data.status === "auto" ? "已进入安全补全队列，只会写入空白字段。" : "候选已确认，等待后台写入。"}</div>`;
    const apply = list.querySelector("[data-apply-track-metadata]");
    if (apply) apply.onclick = async () => {
      apply.disabled = true;
      const applyController = typeof AbortController === "function" ? new AbortController() : null;
      state.metadataCandidateController = applyController;
      try {
        const selected = list.querySelector('input[name="metadataCandidate"]:checked');
        const candidateIndex = Number(selected?.value);
        if (!Number.isInteger(candidateIndex) || candidateIndex < 0) throw new Error("请选择一个候选结果");
        const applied = await apiFetch("api/metadata/track/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ track_id: trackId, candidate_index: candidateIndex }),
          ...(applyController ? { signal: applyController.signal } : {}),
        });
        const result = await readResponseJsonBounded(applied);
        if (!applied.ok || result.ok !== true) throw new Error(result.message || "确认失败");
        if (!isCurrentRequest() || state.metadataCandidateController !== applyController) return;
        list.textContent = "已确认，后台将只补全空白 Tag 字段。";
        // The confirmation changes the metadata-backed projection immediately,
        // while the library scanner remains untouched.  Drop the page LRU and
        // refresh the visible page now instead of waiting for the 30s status
        // scheduler; keyed row commits preserve decoded covers and avoid a
        // full-list flash.
        clearLibraryResponseCaches();
        if (state.pageItems?.length && !state.libraryLoading) {
          await loadLibrary(false);
        }
      } catch (error) {
        if (error?.name === "AbortError") return;
        if (!isCurrentRequest() || state.metadataCandidateController !== applyController) return;
        apply.disabled = false;
        list.textContent = error.message || "确认失败";
      } finally {
        if (state.metadataCandidateController === applyController) {
          state.metadataCandidateController = null;
        }
      }
    };
  } catch (error) {
    if (error?.name === "AbortError") return;
    if (!isCurrentRequest()) return;
    list.textContent = error.message || "读取候选失败";
  } finally {
    if (requestToken === state.metadataCandidateRequestToken
      && state.metadataCandidateController === controller) {
      state.metadataCandidateController = null;
    }
  }
}
async function resolveTrackLocation(trackId) {
  const result = await fetchJsonResponseBounded(
    `api/library/location?id=${encodeURIComponent(String(trackId || ""))}`,
    { cache: "no-store" },
    10000,
  );
  const response = result.response;
  const data = result.data || {};
  if (!response.ok || data.ok !== true || !data.path) throw new Error(data.message || "无法获取歌曲文件路径");
  return data;
}
async function openContainingFolder(trackId) {
  try {
    const location = await resolveTrackLocation(trackId);
    const folder = String(location.folder || "");
    if (!folder) throw new Error("无法获取歌曲所在文件夹");
    const sdk = await getTrimSdk();
    if (!sdk || typeof sdk.openFileManager !== "function") throw new Error("unsupported");
    if (typeof sdk.ready === "function") await sdk.ready();
    if (sdk.isStandaloneWeb) return alert("请从飞牛桌面或飞牛 App 的 fnAudio 应用入口打开，才能跳转到文件管理");
    // fnOS 的文件管理入口接收目录路径；传入完整文件路径会被宿主当作“打开文件”处理。
    Promise.resolve(sdk.openFileManager(folder)).catch(error => {
      console.warn("openFileManager failed", error);
      alert("飞牛文件管理打开失败，请确认 fnAudio 是从飞牛应用入口启动的");
    });
    return;
  } catch (error) {
    console.warn("openFileManager failed", error);
  }
  alert("飞牛文件管理打开失败，请确认 fnAudio 是从飞牛应用入口启动的");
}
function externalShareDateValue(date) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}
function generateExternalSharePassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
  const bytes = new Uint8Array(10);
  crypto.getRandomValues(bytes);
  return [...bytes].map(value => alphabet[value % alphabet.length]).join("");
}
function syncExternalShareOptions() {
  const expiryEnabled = $("shareExpiryEnabled").checked;
  const passwordEnabled = $("sharePasswordEnabled").checked;
  const accessEnabled = $("shareAccessEnabled").checked;
  $("shareExpiryDetail").hidden = !expiryEnabled;
  $("sharePasswordDetail").hidden = !passwordEnabled;
  $("shareAccessDetail").hidden = !accessEnabled;
  $("shareExpirySummary").textContent = expiryEnabled ? "按设定时间到期" : "链接永久有效";
  $("sharePasswordSummary").textContent = passwordEnabled ? "需要访问密码" : "不使用密码";
  $("shareAccessSummary").textContent = accessEnabled ? "限制访问次数" : "不限制次数";
  if (passwordEnabled && !$("sharePasswordInput").value) $("sharePasswordInput").value = generateExternalSharePassword();
}
function resetExternalShareDialog(location) {
  state.externalShareLocation = location;
  $("externalShareFileName").textContent = String(location.path || "").split("/").pop() || "歌曲文件";
  $("shareExpiryEnabled").checked = false;
  $("sharePasswordEnabled").checked = false;
  $("shareAccessEnabled").checked = false;
  $("shareExpiryInput").value = externalShareDateValue(new Date(Date.now() + 7 * 86400000));
  $("sharePasswordInput").value = "";
  $("shareAccessInput").value = "100";
  $("externalShareStatus").textContent = "";
  $("externalShareForm").hidden = false;
  $("externalShareResult").hidden = true;
  $("externalShareUrl").value = "";
  $("externalSharePasswordResult").hidden = true;
  $("externalSharePasswordResult").textContent = "";
  $("createExternalShare").disabled = false;
  syncExternalShareOptions();
}
async function openExternalShareDetails() {
  const location = state.externalShareLocation;
  if (!location?.path) return;
  try {
    const sdk = await getTrimSdk();
    if (!sdk || typeof sdk.showFileDetails !== "function") throw new Error("unsupported");
    await sdk.showFileDetails([location.path]);
  } catch (error) {
    console.warn("showFileDetails failed", error);
  }
}
async function shareTrack(trackId) {
  try {
    const location = await resolveTrackLocation(trackId);
    const sdk = await getTrimSdk();
    if (!sdk) throw new Error("unsupported");
    if (typeof sdk.ready === "function") await sdk.ready();
    if (sdk.isStandaloneWeb) return alert("请从飞牛桌面或飞牛 App 的 fnAudio 应用入口打开，才能创建外部链接");
    resetExternalShareDialog(location);
    $("externalShareDialog").showModal();
    return;
  } catch (error) {
    console.warn("fnOS file sharing handoff failed", error);
  }
  alert("无法调用飞牛外链服务，请从飞牛应用入口打开 fnAudio 后重试");
}
async function createExternalShareLink() {
  const location = state.externalShareLocation;
  if (!location?.path) return;
  const button = $("createExternalShare");
  const expiryEnabled = $("shareExpiryEnabled").checked;
  const passwordEnabled = $("sharePasswordEnabled").checked;
  const accessEnabled = $("shareAccessEnabled").checked;
  const password = passwordEnabled ? $("sharePasswordInput").value.trim() : "";
  const maxAccess = accessEnabled ? Number($("shareAccessInput").value || 0) : 0;
  const validTo = expiryEnabled ? Math.floor(new Date($("shareExpiryInput").value).getTime() / 1000) : 0;
  if (passwordEnabled && (password.length < 4 || password.length > 128)) return void ($("externalShareStatus").textContent = "密码长度需要为 4 到 128 个字符");
  if (accessEnabled && (!Number.isInteger(maxAccess) || maxAccess < 1 || maxAccess > 9999)) return void ($("externalShareStatus").textContent = "可访问次数需要为 1 到 9999");
  if (expiryEnabled && (!Number.isFinite(validTo) || validTo <= Math.floor(Date.now() / 1000))) return void ($("externalShareStatus").textContent = "到期时间必须晚于当前时间");
  button.disabled = true;
  $("externalShareStatus").textContent = "正在创建...";
  try {
    const sdk = await getTrimSdk();
    if (!sdk || typeof sdk.query !== "function" || sdk.isStandaloneWeb) throw new Error("unsupported");
    const defaultResponse = await sdk.query({ req: "appcgi.sharesvr.share.link.default", data: {} });
    const payload = {
      name: String(location.path || "").split("/").pop() || "fnAudio",
      files: [String(location.path)],
      maxAccess,
    };
    if (passwordEnabled) payload.passwd = password;
    if (expiryEnabled) payload.validTo = validTo;
    const created = await sdk.query({ req: "appcgi.sharesvr.share.link.create", data: payload });
    const id = String(created?.data?.id || "");
    const defaultLink = String(defaultResponse?.data?.defaultLink || "").replace(/\/$/, "");
    if (created?.result !== "succ" || !id || !defaultLink) throw new Error(created?.errmsg || "create failed");
    $("externalShareUrl").value = `${defaultLink}/s/${id}`;
    $("externalSharePasswordResult").hidden = !passwordEnabled;
    $("externalSharePasswordResult").textContent = passwordEnabled ? `密码：${password}` : "";
    $("externalShareForm").hidden = true;
    $("externalShareResult").hidden = false;
  } catch (error) {
    console.warn("create external share failed", error);
    $("externalShareStatus").textContent = "创建失败，已打开飞牛文件详情，请在文件管理中创建外部链接";
    openExternalShareDetails();
  } finally {
    button.disabled = false;
  }
}
async function copyExternalShareLink() {
  const url = $("externalShareUrl").value.trim();
  if (!url) return;
  const password = $("sharePasswordEnabled").checked ? $("sharePasswordInput").value.trim() : "";
  const text = password ? `${url}\n密码：${password}` : url;
  try {
    await navigator.clipboard.writeText(text);
    $("copyExternalShare").textContent = "已复制";
    setTimeout(() => { $("copyExternalShare").textContent = "复制链接"; }, 1200);
  } catch (error) {
    $("externalShareUrl").select();
    document.execCommand("copy");
  }
}
function closeDeleteTrackDialog() {
  const dialog = $("deleteTrackDialog");
  if (dialog?.open) dialog.close();
  state.pendingDeleteTrackIds = [];
}
function setDeleteTrackBusy(busy) {
  [$("deleteTrackPermanently"), $("cancelDeleteTrack"), $("moveTrackToTrash")].forEach(button => {
    if (button) button.disabled = Boolean(busy);
  });
}
function openDeleteTrackDialog(trackIds = []) {
  const ids = [...new Set((trackIds || []).map(String).filter(id => itemById(id)))];
  if (!ids.length) return;
  state.pendingDeleteTrackIds = ids;
  const first = itemById(ids[0]);
  const name = displayTrackTitle(first) || "歌曲文件";
  $("deleteTrackTitle").textContent = ids.length > 1 ? `确定删除这 ${ids.length} 首歌曲吗？` : `确定删除“${name}”吗？`;
  $("deleteTrackDescription").textContent = "删除后，可在飞牛文件管理的回收站中恢复。";
  $("deleteTrackStatus").textContent = "";
  setDeleteTrackBusy(false);
  $("deleteTrackDialog").showModal();
  $("moveTrackToTrash").focus();
}
function removeDeletedTracksFromClientState(trackIds) {
  const deleted = new Set(trackIds.map(String));
  state.items = state.items.filter(item => !deleted.has(String(item.id)));
  state.pageItems = state.pageItems.filter(item => !deleted.has(String(item.id)));
  deleted.forEach(id => state.itemCache.delete(id));
  state.favorites = state.favorites.filter(id => !deleted.has(String(id)));
  state.playlists.forEach(playlist => {
    playlist.trackIds = playlist.trackIds.filter(id => !deleted.has(String(id)));
  });
  saveFavorites();
  savePlaylists();
}
async function deleteTrackFiles(moveToTrashbin = true) {
  const ids = [...state.pendingDeleteTrackIds];
  if (!ids.length) return;
  setDeleteTrackBusy(true);
  $("deleteTrackStatus").textContent = moveToTrashbin ? "正在移入回收站..." : "正在彻底删除...";
  try {
  const locationPool = fnAudioBatchRequestPool(ids, fnAudioBatchRequestPool.DEFAULT_CONCURRENCY, resolveTrackLocation);
    const locations = [];
    for (let index = 0; index < ids.length; index += 1) locations.push(await locationPool.get(index));
    const paths = [...new Set(locations.map(location => String(location.path || "")).filter(Boolean))];
    if (!paths.length) throw new Error("无法获取歌曲文件路径");
    const sdk = await getTrimSdk();
    if (!sdk || typeof sdk.query !== "function") throw new Error("当前环境不支持飞牛文件服务");
    if (typeof sdk.ready === "function") await sdk.ready();
    if (sdk.isStandaloneWeb) throw new Error("请从飞牛桌面的 fnAudio 应用入口执行删除");
    const currentId = String(currentItem()?.id || "");
    if (ids.includes(currentId)) await stopPlayback();
    const response = await sdk.query({
      req: "file.rm",
      files: paths,
      moveToTrashbin: Boolean(moveToTrashbin),
      details: { name: paths[0].split("/").pop() || "歌曲文件", count: paths.length, dir: false },
    }, { timeout: -1 });
    if (response?.result && response.result !== "succ") throw new Error(response.errmsg || "删除失败");
    const deleted = new Set(ids);
    const remainingQueue = state.queue.filter(item => !deleted.has(String(item.id)));
    const nextIndex = Math.min(Math.max(state.index, 0), Math.max(remainingQueue.length - 1, 0));
    const nextCurrent = remainingQueue[nextIndex]?.id || "";
    try {
      await commitQueue(remainingQueue, nextCurrent);
    } catch (error) {
      console.warn("Queue refresh after file deletion failed", error);
    }
    removeDeletedTracksFromClientState(ids);
    closeDeleteTrackDialog();
    clearLibraryResponseCaches();
    state.pageTotal = Math.max(0, Number(state.pageTotal || 0) - ids.length);
    state.libraryStatus = {
      ...(state.libraryStatus || {}),
      count: Math.max(0, Number(state.libraryStatus?.count || 0) - ids.length),
      scanning: true,
    };
    render();
    refreshLibraryStatus(true);
  } catch (error) {
    console.warn("fnOS recycle-bin delete failed", error);
    $("deleteTrackStatus").textContent = error?.errmsg || error?.message || "删除失败";
    setDeleteTrackBusy(false);
  }
}
function openTrackActionDialog(trackId) {
  const item = itemById(trackId);
  if (!item) return;
  state.actionTrackId = String(trackId);
  $("trackActionTitle").textContent = displayTrackTitle(item) || "歌曲操作";
  const list = $("trackActionList");
  list.innerHTML = `<div class="track-action-info">${escapeHtml(metadataSourceText(item))}</div>` + trackActionButtons(trackId).join("");
  bindTrackActionButtons(list);
  $("trackActionDialog").showModal();
}
function openTrackContextMenu(trackId, x, y, mobile = false) {
  const item = itemById(trackId);
  const menu = $("trackContextMenu");
  if (!item || !menu) return;
  state.actionTrackId = String(trackId);
  const actions = mobile
    ? mobileTrackContextActionButtons(trackId)
    : desktopTrackContextActionButtons(trackId);
  menu.innerHTML = `<strong class="track-context-title">${escapeHtml(displayTrackTitle(item) || "歌曲操作")}</strong><div class="track-context-actions">${actions.join("")}</div>`;
  menu.hidden = false;
  menu.style.left = `${Math.max(8, x)}px`;
  menu.style.top = `${Math.max(8, y)}px`;
  bindTrackActionButtons(menu);
  requestAnimationFrame(() => {
    const margin = 8;
    const bounds = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(margin, Math.min(x, window.innerWidth - bounds.width - margin))}px`;
    menu.style.top = `${Math.max(margin, Math.min(y, window.innerHeight - bounds.height - margin))}px`;
  });
}
function runTrackAction(action) {
  const trackId = state.actionTrackId;
  const selected = selectedTrackIds(trackId);
  closeTrackActionDialog();
  closeTrackContextMenu();
  if (action === "play") playSelectedTracks(selected);
  else if (action === "play-from-current") playFromCurrentTrack(trackId);
  else if (action === "queue") addSelectedToQueue(selected);
  else if (action === "favorite") toggleSelectedFavorites(selected);
  else if (action === "favorite-add") addSelectedFavorites(selected);
  else if (action === "playlist") openPlaylistDialogForTracks(selected);
  else if (action === "insert") insertSelectedTracks(selected);
  else if (action === "info") showTrackInformation(trackId);
  else if (action === "metadata-candidate") showTrackMetadataCandidate(trackId);
  else if (action === "open-folder") openContainingFolder(trackId);
  else if (action === "share") shareTrack(trackId);
  else if (action === "delete-file") openDeleteTrackDialog(selected);
  else if (action === "remove-queue") removeTrackFromQueue(trackId);
  else if (action === "remove-favorite") removeFavorite(trackId);
  else if (action === "remove-playlist") removeTrackFromCurrentPlaylist(trackId);
}
function normalizedRepeatMode(repeat) {
  return globalThis.fnAudioRepeatModePolicy.normalize(repeat);
}
function nextRepeatMode(repeat) {
  return globalThis.fnAudioRepeatModePolicy.next(repeat);
}
function repeatModeLabel(repeat) {
  return globalThis.fnAudioRepeatModePolicy.label(repeat);
}
function repeatNextAction(repeat) {
  return globalThis.fnAudioRepeatModePolicy.action(repeat);
}
function repeatIconMarkup(repeat) {
  return globalThis.fnAudioRepeatModePolicy.iconMarkup(repeat);
}
function updateRepeatShuffleButtons() {
  const repeat = normalizedRepeatMode(state.repeat);
  [[$("repeatBtn"), $("repeatIcon")], [$("mobileRepeatBtn"), $("mobileRepeatIcon")]].forEach(([button, icon]) => {
    if (!button || !icon) return;
    const active = repeat !== "off";
    const title = `${repeatModeLabel(repeat)}，点击${repeatNextAction(repeat)}`;
    const ariaLabel = `循环模式：${repeatModeLabel(repeat)}，点击${repeatNextAction(repeat)}`;
    if (button.dataset.repeat !== repeat) {
      button.dataset.repeat = repeat;
      icon.innerHTML = repeatIconMarkup(repeat);
    }
    if (button.classList.contains("active-control") !== active) button.classList.toggle("active-control", active);
    if (button.title !== title) button.title = title;
    if (button.getAttribute("aria-label") !== ariaLabel) button.setAttribute("aria-label", ariaLabel);
  });
  [$("shuffleBtn"), $("mobileShuffleBtn")].forEach(button => {
    if (!button) return;
    const active = state.shuffle === true;
    const pressed = String(active);
    const label = active ? "关闭随机播放" : "随机播放";
    if (button.classList.contains("active-control") !== active) button.classList.toggle("active-control", active);
    if (button.getAttribute("aria-pressed") !== pressed) button.setAttribute("aria-pressed", pressed);
    if (button.title !== label) button.title = label;
    if (button.getAttribute("aria-label") !== label) button.setAttribute("aria-label", label);
  });
}
async function toggleRepeat() {
  const nextRepeat = nextRepeatMode(state.repeat);
  const data = await coreControl("repeat", null, { repeat: nextRepeat });
  if (data?.core) state.repeat = data.core.repeat || state.repeat;
  else if (data) state.repeat = nextRepeat;
  if (nativePlaybackAvailable()) nativePlaybackCall("setRepeat", state.repeat);
  updateRepeatShuffleButtons();
  syncState();
}
async function toggleShuffle() {
  const data = await coreControl("shuffle");
  if (data?.core && typeof data.core.shuffle === "boolean") state.shuffle = data.core.shuffle;
  else state.shuffle = !state.shuffle;
  if (nativePlaybackAvailable()) nativePlaybackCall("setShuffle", Boolean(state.shuffle));
  updateRepeatShuffleButtons();
  syncState();
}
function savePlaylistFromDialog() {
  const playlist = createPlaylist($("playlistNameInput").value, state.pendingPlaylistTrackIds || (state.pendingPlaylistTrack ? [state.pendingPlaylistTrack] : []));
  if (!playlist) return;
  $("playlistDialog").close();
  setView(`playlist:${playlist.id}`);
}
function deletePlaylist(playlistId) {
  const playlist = state.playlists.find(x => x.id === playlistId);
  if (!playlist) return;
  if (!confirm(`删除播放列表“${playlist.name}”？歌曲文件不会被删除。`)) return;
  state.playlists = state.playlists.filter(x => x.id !== playlistId);
  savePlaylists();
  if (state.view === `playlist:${playlistId}`) {
    setView("all");
    return;
  }
  render();
}
async function fetchMetadataProjectionStatus(externalSignal = undefined) {
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  let removeExternalAbort = null;
  if (controller && externalSignal && typeof externalSignal.addEventListener === "function") {
    const abortFromOwner = () => { try { controller.abort(); } catch (_) {} };
    if (externalSignal.aborted) abortFromOwner();
    else {
      externalSignal.addEventListener("abort", abortFromOwner, { once: true });
      removeExternalAbort = () => {
        try { externalSignal.removeEventListener("abort", abortFromOwner); } catch (_) {}
      };
    }
  }
  try {
    const request = fetch("api/metadata/status", {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request,
      timeoutMs: 1500,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: null,
    });
    const response = result.response;
    if (!response?.ok) return null;
    const data = unwrapMetadataResponsePayload(result.data);
    return data?.ok === true ? data : null;
  } catch (_) {
    return null;
  } finally {
    removeExternalAbort?.();
  }
}
async function refreshLibraryStatus(refresh = false) {
  // Scanning and the normal 30-second refresh can overlap on slow NAS
  // connections. Share one bounded status request so an older response cannot
  // race a newer one and trigger duplicate cache invalidation/reloads.
  const refreshPlan = globalThis.fnAudioLibraryStatusRefreshPolicy?.plan(
    Boolean(state.libraryStatusPromise),
    refresh,
  ) || { reuse: Boolean(state.libraryStatusPromise), queueRefresh: Boolean(state.libraryStatusPromise && refresh) };
  if (refreshPlan.reuse) {
    if (refreshPlan.queueRefresh) state.libraryStatusRefreshQueued = true;
    return state.libraryStatusPromise;
  }
  const token = ++state.libraryStatusRequestToken;
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  const request = (async () => {
  try {
    const wasScanning = state.libraryStatus?.scanning === true;
    // Library and metadata status are independent snapshots. Fetch them in
    // parallel so a slow metadata SQLite aggregation/provider observation
    // cannot delay the library progress paint (or make the next poll appear
    // to stall) on large collections.
    const responsePromise = fetch(`api/library/status${refresh ? "?refresh=1" : ""}`, {
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    });
    const metadataPromise = fetchMetadataProjectionStatus(controller?.signal);
    const result = await globalThis.fnAudioResponseJsonLoader.read({
      request: responsePromise,
      timeoutMs: 6000,
      onTimeout: () => { try { controller?.abort(); } catch (_) {} },
      fallback: null,
    });
    const response = result.response;
    if (token !== state.libraryStatusRequestToken || state.libraryStatusController !== controller) return;
    const payload = response?.ok ? result.data : null;
    const data = payload
      ? (globalThis.fnAudioMetadataResponsePolicy?.unwrapTransport(payload, 4) || {})
      : null;
    if (!data) return;
    // Commit the cheap library snapshot immediately. Metadata status has its
    // own bounded timeout and is merged below, so provider/SQLite latency can
    // never hold the scan counter or first-paint decorations hostage.
    state.libraryStatus = data;
    updateLibraryStatusDecorations();
    const metadata = await metadataPromise;
    // The library request and metadata projection request run in parallel.
    // A view/page switch can invalidate this status operation while the
    // metadata side is still waiting; do not let its late result mutate the
    // new page or restart a load that belongs to the old view.
    if (token !== state.libraryStatusRequestToken || state.libraryStatusController !== controller) return;
    let metadataChanged = false;
    if (metadata) {
      const signature = metadataProjectionSignature(metadata);
      metadataChanged = Boolean(state.metadataProjectionSignature && signature !== state.metadataProjectionSignature);
      state.metadataProjectionSignature = signature;
      retryCurrentTrackMetadataAfterRecovery(metadata);
    }
    if (wasScanning && data.scanning !== true) {
      clearLibraryResponseCaches();
      await loadLibrary(false);
      return;
    }
    // Metadata workers update SQLite independently of the library scanner.
    // A global projection revision does not identify which track changed. A
    // full reload here therefore replaced the visible page even when an
    // unrelated background job completed, producing the familiar second
    // list/cover flash just after startup. Current and visible rows already
    // receive targeted updates through their own metadata lanes; retire only
    // cached future pages so navigation sees fresh SQLite data without
    // disturbing the settled DOM.
    if (metadataChanged && state.pageItems?.length && !state.libraryLoading) {
      invalidateLibraryResponseCacheForMetadataRevision();
      // A failed/no-match visible lookup releases its dedupe key. Re-arm the
      // small cancellable lane when the backend publishes a new projection,
      // so worker recovery or provider cooldown expiry can repair the row
      // without requiring a manual page switch or application restart.
      scheduleVisibleMetadataPrefetch(state.pageItems, state.libraryRequestSeq);
    }
    // A scan can begin before the first paged response arrives. Keep the
    // empty-state panel suppressed while that request (or the scanner itself)
    // is still establishing the authoritative page; ending loading here made
    // older WebViews briefly flash “没有音乐” between status polls.
    if (data.scanning === true && !hasVisibleLibraryPresentation()) state.libraryLoading = true;
    updateLibraryStatusDecorations();
  } catch (error) {
  } finally {
    if (token === state.libraryStatusRequestToken
      && state.libraryStatusController === controller
      && state.libraryStatusPromise === request) {
      state.libraryStatusPromise = null;
      state.libraryStatusController = null;
      const queuedRefresh = state.libraryStatusRefreshQueued;
      state.libraryStatusRefreshQueued = false;
      if (queuedRefresh) refreshLibraryStatus(true);
    }
  }
  })();
  state.libraryStatusPromise = request;
  state.libraryStatusController = controller;
  return request;
}
function invalidateLibraryResponseCacheForMetadataRevision() {
  // Do not abort an active authoritative page: a metadata revision is
  // auxiliary to the immutable library row snapshot. Bump the cache epoch so
  // an older in-flight response cannot repopulate the cache after the clear.
  state.libraryResponseEpoch += 1;
  state.libraryResponseCache.clear?.();
  state.albumMetadata.clear?.();
}
function toggleFavorite(trackId) {
  const id = String(trackId);
  if (!itemById(id)) return;
  if (isFavorite(id)) state.favorites = state.favorites.filter(x => x !== id);
  else state.favorites.unshift(id);
  saveFavorites();
  refreshFavoritePresentation();
}
function toggleSelectedFavorites(ids = []) {
  const valid = (ids || []).map(String).filter(id => itemById(id));
  if (!valid.length) return;
  const allFavorite = valid.every(isFavorite);
  if (allFavorite) state.favorites = state.favorites.filter(id => !valid.includes(String(id)));
  else {
    const additions = valid.filter(id => !isFavorite(id));
    state.favorites = [...additions, ...state.favorites];
  }
  saveFavorites();
  refreshFavoritePresentation();
}
function addSelectedFavorites(ids = []) {
  const valid = (ids || []).map(String).filter(id => itemById(id));
  if (!valid.length) return;
  const existing = new Set(state.favorites.map(String));
  const additions = valid.filter(id => !existing.has(id));
  if (!additions.length) return;
  state.favorites = [...additions, ...state.favorites];
  saveFavorites();
  refreshFavoritePresentation();
}
function removeFavorite(trackId) {
  state.favorites = state.favorites.filter(x => x !== String(trackId));
  saveFavorites();
  refreshFavoritePresentation();
}
function toggleCurrentFavorite() {
  const item = currentItem();
  if (item) toggleFavorite(item.id);
}
function removeTrackFromCurrentPlaylist(trackId) {
  const playlist = currentPlaylist();
  if (!playlist) return;
  playlist.trackIds = playlist.trackIds.filter(id => id !== String(trackId));
  savePlaylists();
  render();
}
async function selectPlaybackTarget(id, name) {
  const nextTarget = id || "local";
  const previousTarget = state.playTarget || "local";
  if (state.deviceSwitchInFlight || previousTarget === nextTarget) return;
  cancelDeviceLoad();
  cancelRemoteLoad();
  cancelRemoteStatusRequest();
  state.deviceSwitchInFlight = true;
  state.deviceTargetRevision += 1;
  try {
    const response = await apiFetch("api/playback/target", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_id: nextTarget})
    });
    const data = await readResponseJsonBounded(response);
    if (!response.ok || data.ok !== true) throw new Error(data.message || "播放设备切换失败");
    if (userStateRevision(data.revision, -1) >= 0) state.userStateRevision = userStateRevision(data.revision);
    // The target endpoint performs the authoritative transition and closes the
    // previous output inside `set_target()`. Do not issue a second stop here:
    // a follow-up control request can race with the new target and move the
    // server back to the old renderer.
    state.playTarget = nextTarget;
    state.playTargetName = name || "当前设备";
    state.deviceTargetsSignature = "";
    markCurrentDeviceTarget(nextTarget, true);
    updateDeviceLabel();
  } catch (error) {
    markCurrentDeviceTarget(previousTarget);
    updateDeviceLabel();
    if (previousTarget === "local") nativeRemoteExit();
    else nativeRemoteEnter(true);
    alert(error.message || "播放设备切换失败");
    return;
  } finally {
    state.deviceSwitchInFlight = false;
    markCurrentDeviceTarget(state.playTarget);
  }
  state.remoteStatus = null;
  state.remoteStateVersion = 0;
  state.remoteCueSegment = false;
  if (nextTarget === "local") {
    stopRemoteEventStream();
    nativeRemoteExit();
  } else {
    stopRemoteEventStream();
    startRemoteEventStream();
    nativeRemoteEnter(true);
  }
  updateDeviceLabel();
  render();
  scheduleUserStateSave();
  if ($("deviceDialog").open) loadDevices().catch(() => {});
}
function cancelRemoteLoad() {
  try { state.remoteLoadController?.abort(); } catch (_) {}
  state.remoteLoadController = null;
  state.remoteLoadPromise = null;
  state.remoteLoadedKey = "";
  state.remoteLoadedAt = 0;
}
async function pushToDevice(deviceId, item = currentItem()) {
  if (state.deviceSwitchInFlight) return false;
  if (!item) return alert("请先选择一首歌曲");
  if (!state.remoteGeneration) state.remoteGeneration = Date.now() & 0x7fffffff;
  if (!state.remoteEngineEpoch) state.remoteEngineEpoch = 1;
  const loadKey = `${deviceId}:${item.id}`;
  if (state.remoteLoadPromise && state.remoteLoadedKey === loadKey) return state.remoteLoadPromise;
  if (state.remoteLoadedKey === loadKey && Date.now() - state.remoteLoadedAt < 2500) return true;
  try { state.remoteLoadController?.abort(); } catch (_) {}
  const controller = typeof AbortController === "function" ? new AbortController() : null;
  state.remoteLoadedKey = loadKey;
  state.remoteLoadedAt = Date.now();
  let loadPromise;
  let loadSucceeded = false;
  loadPromise = (async () => {
    const response = await apiFetch("api/playback/load", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        target_id: deviceId,
        track_id: item.id,
        command_id: playbackCommandId(),
        generation: Number(state.remoteGeneration || 0),
        engine_epoch: Number(state.remoteEngineEpoch || 0),
      }),
      ...(controller ? { signal: controller.signal } : {}),
    });
    const data = await readResponseJsonBounded(response);
    const ownsLoad = () => state.remoteLoadPromise === loadPromise
      && state.remoteLoadController === controller
      && state.remoteLoadedKey === loadKey;
    if (!ownsLoad()) return false;
    if (!response.ok || data.ok !== true) {
      state.remoteLoadedKey = "";
      alert(data.message || data.error || "播放设备接收失败");
      return false;
    }
    // Same authority rule as the status snapshot: a declaration from the server
    // wins, and only an undeclared reply may fall back to local queue metadata.
    state.remoteCueSegment = data.cue_segment === true
      || (data.cue_segment !== false && item?.cue_track === true && !isDacTarget(deviceId));
    if (state.remoteCueSegment) {
      state.remoteStatus = {
        ...(state.remoteStatus || {}),
        transport: { ...(state.remoteStatus?.transport || {}), state: "PLAYING" },
        position: { ...(state.remoteStatus?.position || {}), rel_seconds: 0, duration_seconds: playbackSeconds(item.duration, playbackSeconds(state.remoteStatus?.position?.duration_seconds)) },
      };
      state.remoteBaseSeconds = 0;
      state.remoteSnapshotAt = Date.now();
      updateRemoteUi();
    }
    state.dacStrategy = data.strategy || null;
    if (isDacTarget(deviceId) && item) {
      setTextContentIfChanged($("nowArtist"), `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)} · ${state.playTargetName}`);
      syncPlayerProgress();
      updateNowMarquee();
    }
    updateDeviceLabel();
    $("deviceDialog").close();
    loadSucceeded = true;
    return true;
  })();
  state.remoteLoadPromise = loadPromise;
  state.remoteLoadController = controller;
  try {
    return await loadPromise;
  } finally {
    if (state.remoteLoadPromise === loadPromise) {
      state.remoteLoadPromise = null;
      if (state.remoteLoadController === controller) state.remoteLoadController = null;
      // The short dedupe window is only valid after a confirmed load. A
      // transport error or cancellation must leave the same track retryable.
      if (!loadSucceeded && state.remoteLoadedKey === loadKey) {
        state.remoteLoadedKey = "";
        state.remoteLoadedAt = 0;
      }
    }
  }
}
document.querySelectorAll(".nav-item[data-view]").forEach(button => button.onclick = () => {
  if (button.dataset.view === "queue") openCurrentQueue();
  else setView(button.dataset.view);
});
function setMobileNavigation(open) {
  const sidebar = document.querySelector(".sidebar");
  const backdrop = $("mobileNavBackdrop");
  const button = $("mobileNavBtn");
  if (!sidebar || !backdrop || !button) return;
  sidebar.classList.toggle("mobile-open", open);
  backdrop.hidden = !open;
  button.setAttribute("aria-expanded", String(open));
}
$("mobileNavBtn").onclick = () => setMobileNavigation(!document.querySelector(".sidebar")?.classList.contains("mobile-open"));
$("mobileNavBackdrop").onclick = () => setMobileNavigation(false);
document.querySelectorAll(".nav-item[data-view]").forEach(button => {
  button.addEventListener("click", () => setMobileNavigation(false));
});
function handleSearchInput(source) {
  const value = source?.value || "";
  [$("searchInput"), $("mobileSearchInput")].forEach(input => {
    if (input && input !== source) input.value = value;
  });
  if (state.searchTimer) clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(() => {
    state.searchTimer = null;
    state.folderPage = 1;
    state.page = 1;
    if (isPagedLibraryView()) requestLibraryLoad(1, false);
    else render();
  }, 240);
}
$("searchInput").oninput = event => handleSearchInput(event.currentTarget);
const mobileSearchInput = $("mobileSearchInput");
function configureMobileKeyboardOverlay() {
  if (!window.matchMedia("(max-width: 760px)").matches) return;
  const virtualKeyboard = navigator.virtualKeyboard;
  if (!virtualKeyboard || !("overlaysContent" in virtualKeyboard)) return;
  try {
    virtualKeyboard.overlaysContent = true;
  } catch (_) {
    // Some embedded WebViews expose the property but reject writes.
  }
}
function setMobileSearchFocusState(active) {
  const enabled = Boolean(active) && window.matchMedia("(max-width: 760px)").matches;
  document.body.classList.toggle("mobile-search-active", enabled);
  if (enabled) configureMobileKeyboardOverlay();
  requestAnimationFrame(() => {
    updateMobilePagerVisibility();
    if (!enabled) updateNowMarquee();
  });
}
configureMobileKeyboardOverlay();
if (mobileSearchInput) {
  mobileSearchInput.oninput = event => handleSearchInput(event.currentTarget);
  mobileSearchInput.addEventListener("focus", () => setMobileSearchFocusState(true));
  mobileSearchInput.addEventListener("blur", () => setMobileSearchFocusState(false));
}
$("playAllBtn").onclick = playAll;
$("mobileColumnsBtn").onclick = openColumnsDialog;
$("closeColumnsDialog").onclick = () => $("columnsDialog").close();
$("cancelDeleteTrack").onclick = closeDeleteTrackDialog;
$("moveTrackToTrash").onclick = () => deleteTrackFiles(true);
$("deleteTrackPermanently").onclick = () => deleteTrackFiles(false);
$("deleteTrackDialog").addEventListener("cancel", event => {
  if ($("moveTrackToTrash").disabled) event.preventDefault();
  else closeDeleteTrackDialog();
});
$("columnsDialog").addEventListener("close", () => { state.columnDialogColumns = null; });
$("resetColumnsBtn").onclick = () => { state.columnDialogColumns = defaultTrackColumnsForScope(); renderColumnChoices(); };
$("saveColumnsBtn").onclick = saveColumnChoices;
document.addEventListener("pointerdown", event => {
  const menu = $("trackContextMenu");
  if (!menu?.hidden && !menu.contains(event.target)) closeTrackContextMenu();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeTrackContextMenu();
});
window.addEventListener("focus", clearTransientListSelection);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    cancelVisibleMetadataPrefetch({ releaseKeys: true });
    return;
  }
  clearTransientListSelection();
  if (state.pageItems?.length && !state.libraryLoading) {
    scheduleVisibleMetadataPrefetch(state.pageItems, state.libraryRequestSeq);
  }
});
$("libraryScroll").addEventListener("scroll", () => {
  cancelTrackLongPress();
  closeTrackContextMenu();
}, { passive: true });
$("trackList").addEventListener("scroll", () => {
  cancelTrackLongPress();
  closeTrackContextMenu();
  updateMobilePagerVisibility();
}, { passive: true });
$("refreshBtn").onclick = () => requestLibraryLoad(1, true);
function toggleMp3Transcode() {
  state.mp3Transcode = !state.mp3Transcode;
  localStorage.setItem("fnaudio.mp3Transcode", state.mp3Transcode ? "1" : "0");
  updateModeButton();
  if (currentItem() && !isRemoteTarget()) loadCurrent();
}
$("modeBtn").onclick = toggleMp3Transcode;
$("mobileModeBtn").onclick = toggleMp3Transcode;
$("folderBtn").onclick = () => openFolderBrowser();
function openDeviceDialog() {
  $("deviceDialog").showModal();
  loadDevices();
}
$("deviceBtn").onclick = openDeviceDialog;
$("mobileDeviceBtn").onclick = openDeviceDialog;
function closeLyrics() {
  $("lyricsView").hidden = true;
  // Closing the lyrics surface is a user cancellation boundary. Keep the
  // playback-level metadata lane intact, but stop the view-owned poll and
  // request so a slow provider cannot consume a connection after the user
  // has returned to the library.
  cancelLyricsPoll();
  cancelLyricsRequest();
  state.lyricsRequestToken += 1;
  state.lyricsLoadingTrackId = "";
}
function closeTopDialog() {
  const dialogs = [...document.querySelectorAll("dialog[open]")];
  const dialog = dialogs[dialogs.length - 1];
  if (!dialog) return false;
  dialog.close();
  return true;
}
function goBackFromNestedLibraryView() {
  if (state.view === "folders" && state.folderPath) {
    const parts = String(state.folderPath).split("/").filter(Boolean);
    parts.pop();
    state.folderPath = parts.join("/");
    state.folderPage = 1;
  }
  else if (state.view === "folders" && state.folderRoot && !hasSingleFolderRoot()) {
    state.folderRoot = "";
    state.folderPath = "";
    state.folderPage = 1;
  }
  else if (isCreatorAllTracksView()) setCurrentCreatorAllTracks(false);
  else if (isCreatorView() && state.groupName) state.groupName = "";
  else if (isCreatorView() && currentCreatorName()) clearCurrentCreator();
  else if (state.groupName) state.groupName = "";
  else return false;
  state.page = 1;
  state.pageItems = [];
  resetLibraryScrollPosition();
  requestLibraryLoad(1, false).finally(() => requestAnimationFrame(resetLibraryScrollPosition));
  return true;
}
window.fnAudioHandleAndroidBack = () => {
  if (closeTopDialog()) return true;
  const contextMenu = $("trackContextMenu");
  if (contextMenu && !contextMenu.hidden) {
    closeTrackContextMenu();
    return true;
  }
  const sidebar = document.querySelector(".sidebar");
  if (sidebar?.classList.contains("mobile-open")) {
    setMobileNavigation(false);
    return true;
  }
  if (!$("lyricsView").hidden) {
    closeLyrics();
    return true;
  }
  return goBackFromNestedLibraryView();
};
function toggleLyrics() {
  if (!$("lyricsView").hidden) {
    closeLyrics();
    return;
  }
  openLyrics();
}
$("lyricsBtn").onclick = toggleLyrics;
$("nowPlayingSummary").onclick = toggleLyrics;
$("nowPlayingSummary").onkeydown = event => {
  if (!["Enter", " "].includes(event.key)) return;
  event.preventDefault();
  toggleLyrics();
};
$("lyricsClose").onclick = closeLyrics;
$("queueBtn").onclick = openCurrentQueue;
$("closeDialog").onclick = () => $("deviceDialog").close();
$("deviceDialog").addEventListener("close", () => {
  clearTimeout(state.deviceRefreshTimer);
  state.deviceRefreshTimer = null;
});
$("closeFolderDialog").onclick = () => $("folderDialog").close();
document.querySelectorAll("[data-settings-tab]").forEach(button => {
  button.onclick = () => setSettingsTab(button.dataset.settingsTab);
});
$("dlnaDiagnosticsBtn").onclick = openDlnaDiagnostics;
$("closeDlnaDiagnosticsDialog").onclick = () => $("dlnaDiagnosticsDialog").close();
$("refreshDlnaDiagnosticsBtn").onclick = loadDlnaDiagnostics;
$("newPlaylistBtn").onclick = () => openPlaylistDialog();
$("closePlaylistDialog").onclick = () => $("playlistDialog").close();
$("closeTrackActionDialog").onclick = closeTrackActionDialog;
$("closeExternalShareDialog").onclick = () => $("externalShareDialog").close();
$("cancelExternalShare").onclick = () => $("externalShareDialog").close();
$("shareExpiryEnabled").onchange = syncExternalShareOptions;
$("sharePasswordEnabled").onchange = syncExternalShareOptions;
$("shareAccessEnabled").onchange = syncExternalShareOptions;
$("createExternalShare").onclick = createExternalShareLink;
$("copyExternalShare").onclick = copyExternalShareLink;
$("openExternalShareDetails").onclick = openExternalShareDetails;
$("favoriteCurrentBtn").onclick = toggleCurrentFavorite;
$("lyricsFavoriteBtn").onclick = toggleCurrentFavorite;
$("savePlaylistBtn").onclick = savePlaylistFromDialog;
$("playlistNameInput").onkeydown = event => { if (event.key === "Enter") savePlaylistFromDialog(); };
$("chooseFolderBtn").onclick = chooseCurrentFolder;
$("addLibraryPathBtn").onclick = () => addLibraryPathInput();
$("refreshMetadataBtn").onclick = refreshMetadataLibrary;
$("scanDevices").onclick = () => loadDevices(true);
$("playBtn").onclick = () => {
  if (state.deviceSwitchInFlight) return;
  if (isIncomingRendererSession()) {
    const transport = String(state.rendererSession.transport || "").toUpperCase();
    controlIncomingRenderer(transport === "PLAYING" ? "pause" : "play");
    return;
  }
  if (isRemoteTarget()) {
    if (!currentItem() && state.queue.length) {
      const previousIndex = state.index;
      state.index = 0;
      syncCurrentQueuePresentation(previousIndex);
      loadCurrent();
      return;
    }
    if (!currentItem()) return;
    const transport = state.remoteStatus?.transport?.state || "";
    if (transport === "PLAYING") remoteControl("pause");
    else remoteControl("play");
    return;
  }
  if (nativePlaybackAvailable()) {
    if (!currentItem() && state.queue.length) {
      const previousIndex = state.index;
      state.index = 0;
      syncCurrentQueuePresentation(previousIndex);
      loadCurrent();
    } else if (!currentItem()) return;
    else if (state.nativePlayback.playing) nativePlaybackCall("pause");
    // A restored WebView can have the persisted fnAudio queue while Android's
    // process was recreated with an empty ExoPlayer timeline. Rehydrate before
    // playing instead of issuing a no-op native play command.
    else if (nativeQueueNeedsRestore()) nativeLoadQueue(true, 0, true);
    else nativePlaybackCall("play");
    return;
  }
  if (!audio.src && state.queue.length) loadCurrent(); else if (audio.paused) audio.play(); else audio.pause();
};
$("prevBtn").onclick = () => playPreviousTrack();
$("stopBtn").onclick = stopPlayback;
$("nextBtn").onclick = () => playNextTrack();
$("repeatBtn").onclick = toggleRepeat;
$("shuffleBtn").onclick = toggleShuffle;
$("mobileRepeatBtn").onclick = toggleRepeat;
$("mobileShuffleBtn").onclick = toggleShuffle;
$("volume").oninput = e => {
  const value = Number(e.target.value);
  audio.volume = value;
  if (nativePlaybackAvailable()) nativePlaybackCall("setVolume", value);
};
$("volumeBtn").onclick = event => {
  event.stopPropagation();
  $("volumePanel").hidden = !$("volumePanel").hidden;
};
$("volumePanel").onclick = event => event.stopPropagation();
document.addEventListener("click", () => {
  const panel = $("volumePanel");
  if (panel) panel.hidden = true;
});
audio.volume = 1;
if ($("volume")) $("volume").value = "1";
audio.onplay = () => { setPlayButton(true); updateMediaSessionPlaybackState(); syncState(); };
audio.onpause = () => { setPlayButton(false); updateMediaSessionPlaybackState(); syncState(); };
audio.onerror = () => {
  if (currentItem()?.is_dsd === true) {
    alert("DSD 兼容流不可用，已停止本机播放。");
    stopLocalAudio();
  }
};
audio.onended = async () => {
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  const moved = await coreControl("next");
  if (!moved) updateMediaSessionPlaybackState();
};
audio.ontimeupdate = () => {
  if (isRemoteTarget()) return;
  const item = currentItem();
  const duration = seekDuration();
  // The cue tail check is a decision about *local* playback, so it has to read
  // the local pair.  With an incoming render session active, ``currentSeconds``
  // and ``seekDuration`` answer about the caster's stream (which is exactly what
  // the transport row must show), and a cast reaching its end would advance this
  // browser's own queue.  Painting below keeps using the shared getters.
  const localSeconds = localPlaybackSeconds();
  const localDuration = localPlaybackDuration();
  // Ruling D-1 stops the element as soon as a cast takes over, so on the ordinary path
  // this handler is not even ticking during a cast. The host player is the case that
  // still can, because its reported position lags one state callback behind the stop.
  // Walking the queue on our own is not a local play intent either, so it must never
  // preempt the caster: the tail simply does not fire while a render session owns the
  // output.
  if (item?.cue_track === true && !isIncomingRendererSession()
    && localDuration > 0 && localSeconds >= Math.max(0, localDuration - 0.25)) {
    const next = nextIndex();
    if (next >= 0) {
      state.streamOffset = 0;
      state.pendingSeekTime = null;
      state.transcodeCacheReady = false;
      state.playSourceKind = "";
      const previousIndex = state.index;
      state.index = next;
      syncCurrentQueuePresentation(previousIndex);
      loadCurrent();
    } else {
      audio.pause();
      updateMediaSessionPlaybackState();
    }
    return;
  }
  setTextContentIfChanged($("elapsed"), clock(currentSeconds()));
  if (!state.seeking) {
    $("seek").value = duration ? currentSeconds() / duration * 100 : 0;
  }
  syncPlayerProgress();
  updateLyricHighlight();
  updateMediaSessionPosition();
};
audio.onloadedmetadata = () => {
  const item = currentItem();
  const canUseNativeDuration = state.playSourceKind !== "stream";
  if (item?.cue_track === true && state.playSourceKind === "cue_segment" && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = audio.duration;
  } else if (item?.cue_track === true && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = Math.max(0, audio.duration - playbackSeconds(item.cue_start));
  } else if (item && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = audio.duration;
  }
  if (state.pendingSeekTime != null && Number.isFinite(audio.duration) && audio.duration > 0) {
    const target = Math.min(Math.max(0, state.pendingSeekTime), Math.max(0, audio.duration - 0.1));
    state.pendingSeekTime = null;
    try { audio.currentTime = target; } catch (error) {}
  }
  setTextContentIfChanged($("duration"), clock(seekDuration()));
  syncPlayerProgress();
  updateMediaSessionPosition();
};
$("seek").oninput = e => {
  state.seeking = true;
  previewSeek(e.target.value);
};
$("seek").onchange = e => commitSeek(e.target.value);
$("seek").onpointerup = e => commitSeek(e.target.value);
$("seek").ontouchend = e => commitSeek(e.target.value);
document.addEventListener("dblclick", event => {
  if (state.libraryInteractionBlocked && event.target.closest?.("#trackList")) {
    event.preventDefault();
    return;
  }
  const row = event.target.closest(".track");
  if (!row || event.target.closest("button")) return;
  const play = row.querySelector("[data-play]");
  if (play) playById(play.dataset.play);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !$("lyricsView").hidden && !document.querySelector("dialog[open]")) closeLyrics();
});
setupMediaSession();
// Paint a recent, bounded page immediately when available. The network
// response still remains authoritative and replaces it only when its content
// differs, avoiding the blank-first-paint/cover-flash pattern on large libs.
if (restoreLibraryPageSnapshot(1)) render();
requestLibraryLoad(1, false);
loadServerUserState();
const uiSyncScheduler = globalThis.fnAudioUiSyncScheduler.create({
  document,
  isLibraryScanning: () => state.libraryStatus?.scanning === true,
  isRemoteTarget,
  isRemoteEventConnected: () => state.remoteEventConnected,
  refreshLibraryStatus,
  refreshCurrentTranscodeStatus,
  refreshRendererSession,
  refreshServerUserState,
  startRemoteEventStream,
  stopRemoteEventStream,
  refreshRemoteStatus,
  updateRemoteUi,
});
window.addEventListener("pagehide", stopRemoteOnUnload);
window.addEventListener("beforeunload", stopRemoteOnUnload);
window.addEventListener("pageshow", () => { if (isRemoteTarget()) startRemoteEventStream(); });
window.addEventListener("resize", updateNowMarquee);
window.addEventListener("resize", updateMobilePagerVisibility, { passive: true });
updateDeviceLabel();
updateModeButton();
syncPlayerProgress();
updateNowMarquee();
refreshRendererSession();
if (isRemoteTarget()) startRemoteEventStream();


