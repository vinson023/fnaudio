const state = { items: [], view: "all", queue: [], index: -1, devices: [], repeat: "off", shuffle: false, folderPath: "", playTarget: "local", playTargetName: "本机播放" };
const $ = (id) => document.getElementById(id);
const audio = $("audio");
const groupViews = { albums: "album", artists: "artist", composers: "composer", genres: "genre" };
function isCreatorView(view = state.view) {
  return view === "artists" || view === "composers";
}
function currentCreatorName() {
  return state.view === "composers" ? state.composerName : state.artistName;
}
function currentCreatorAllTracks() {
  return state.view === "composers" ? state.composerAllTracks : state.artistAllTracks;
}
function currentCreatorTrackTotal() {
  return state.view === "composers" ? state.composerTrackTotal : state.artistTrackTotal;
}
function currentCreatorLabel() {
  return state.view === "composers" ? "作曲者" : "歌手";
}
function setCurrentCreator(name, trackTotal = 0) {
  if (state.view === "composers") {
    state.composerName = name;
    state.composerTrackTotal = Number(trackTotal || 0);
    state.composerAllTracks = false;
  } else {
    state.artistName = name;
    state.artistTrackTotal = Number(trackTotal || 0);
    state.artistAllTracks = false;
  }
}
function setCurrentCreatorAllTracks(enabled) {
  if (state.view === "composers") state.composerAllTracks = Boolean(enabled);
  else state.artistAllTracks = Boolean(enabled);
}
function clearCurrentCreator() {
  if (state.view === "composers") {
    state.composerName = "";
    state.composerTrackTotal = 0;
    state.composerAllTracks = false;
  } else {
    state.artistName = "";
    state.artistTrackTotal = 0;
    state.artistAllTracks = false;
  }
}
function resetCreatorState() {
  state.artistName = "";
  state.artistAllTracks = false;
  state.artistTrackTotal = 0;
  state.composerName = "";
  state.composerAllTracks = false;
  state.composerTrackTotal = 0;
}
function isCreatorAllTracksView() {
  return isCreatorView() && Boolean(currentCreatorName()) && Boolean(currentCreatorAllTracks());
}
function isCreatorAlbumView() {
  return isCreatorView() && Boolean(currentCreatorName()) && !state.groupName && !currentCreatorAllTracks();
}
function isAlbumCollectionView() {
  return (state.view === "albums" && !state.groupName) || isCreatorAlbumView();
}
function isAlbumDetailView() {
  return Boolean(state.groupName) && (state.view === "albums" || (isCreatorView() && currentCreatorName()));
}
function isAlbumSurfaceView() {
  return isAlbumCollectionView() || isAlbumDetailView();
}
const PLAYLIST_STORE_KEY = "fnaudio.playlists";
const FAVORITE_STORE_KEY = "fnaudio.favorites";
const TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v3";
const TRACK_COLUMN_WIDTHS_STORE_KEY = "fnaudio.trackColumnWidths.v1";
const LEGACY_TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v2";
const OLDER_TRACK_COLUMNS_STORE_KEY = "fnaudio.trackColumns.v1";
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
state.accessProfile = "lan";
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
state.seeking = false;
state.streamOffset = 0;
state.pendingSeekTime = null;
state.transcodeCacheReady = false;
state.playSourceKind = "";
state.playbackLoadToken = 0;
state.random100 = [];
state.playlists = loadStoredPlaylists();
state.favorites = loadStoredFavorites();
state.pendingPlaylistTrack = "";
state.pendingPlaylistTrackIds = [];
state.actionTrackId = "";
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
state.remoteCueSegment = false;
state.libraryLoading = false;
state.libraryLoaded = 0;
state.libraryTotal = 0;
state.page = 1;
state.pageSize = Number(localStorage.getItem("fnaudio.pageSize") || 120);
state.pageTotal = 0;
state.pageItems = [];
state.groupRows = [];
state.folderRows = [];
state.folderRootRows = [];
state.folderRoot = "";
state.folderPage = 1;
state.folderPageSize = 100;
state.folderTotal = 0;
state.itemCache = new Map();
state.libraryRequestSeq = 0;
state.hydratingIds = new Set();
state.unresolvedItemIds = new Set();
state.deviceLoadInFlight = false;
state.deviceRefreshTimer = null;
state.deviceTargetsSignature = "";
state.deviceSwitchInFlight = false;
state.deviceTargetRevision = 0;
state.rendererSession = null;
state.rendererSnapshotAt = 0;
state.rendererRequestInFlight = false;
state.userStateHydrated = false;
state.userStateSaveTimer = null;
state.userStateSaveInFlight = false;
state.userStateRevision = 0;
state.userStateRefreshInFlight = false;
state.trackColumnPreferences = loadTrackColumnPreferences();
state.trackColumnWidthPreferences = loadTrackColumnWidthPreferences();
state.autoTrackColumnWidths = {};
state.columnDialogColumns = null;
state.selectedTrackRowKeys = new Set();
state.selectedGroupKeys = new Set();
state.actionGroupKey = "";
state.externalShareLocation = null;
state.albumMetadata = {};
state.settingsTab = "library";
state.searchTimer = null;

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
  try {
    const saved = JSON.parse(localStorage.getItem(TRACK_COLUMNS_STORE_KEY) || "[]");
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      return Object.fromEntries(Object.entries(saved).map(([scope, columns]) => [scope, normalizeTrackColumns(columns)]));
    }
  } catch (error) {
  }
  try {
    const legacy = JSON.parse(localStorage.getItem(LEGACY_TRACK_COLUMNS_STORE_KEY) || "[]");
    if (legacy && typeof legacy === "object" && !Array.isArray(legacy)) {
      const migrated = Object.fromEntries(Object.entries(legacy).map(([scope, columns]) => [scope, normalizeTrackColumns(["title", ...(Array.isArray(columns) ? columns : [])])]));
      localStorage.setItem(TRACK_COLUMNS_STORE_KEY, JSON.stringify(migrated));
      return migrated;
    }
    if (Array.isArray(legacy) && legacy.length) {
      const migrated = { all: normalizeTrackColumns(["title", ...legacy]) };
      localStorage.setItem(TRACK_COLUMNS_STORE_KEY, JSON.stringify(migrated));
      return migrated;
    }
  } catch (error) {
  }
  try {
    const older = JSON.parse(localStorage.getItem(OLDER_TRACK_COLUMNS_STORE_KEY) || "[]");
    if (Array.isArray(older) && older.length) return { all: normalizeTrackColumns(["title", ...older]) };
  } catch (error) {
  }
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
  try {
    const saved = JSON.parse(localStorage.getItem(TRACK_COLUMN_WIDTHS_STORE_KEY) || "{}");
    if (saved && typeof saved === "object" && !Array.isArray(saved)) {
      return Object.fromEntries(Object.entries(saved).map(([scope, widths]) => [scope, normalizeTrackColumnWidths(widths)]));
    }
  } catch (error) {
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
function mediaUrl(path) {
  try {
    return new URL(path || "images/icon_256.png", window.location.href).href;
  } catch (error) {
    return path || "images/icon_256.png";
  }
}
function coverUrl(item) {
  return item?.cover_url ? mediaUrl(item.cover_url) : "";
}
function resetPlaybackProgress() {
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
}
function dacCapsText(caps = {}) {
  const pcmRate = caps.pcm_max_rate ? `${Math.round(Number(caps.pcm_max_rate) / 1000)}kHz` : "未知采样率";
  const bits = caps.pcm_max_bits ? `${caps.pcm_max_bits}bit` : "未知位深";
  const dsd = caps.dsd ? ` · DSD ${Array.isArray(caps.dsd_rates) && caps.dsd_rates.length ? caps.dsd_rates.join("/") : "支持"}` : "";
  return `PCM ${pcmRate}/${bits}${dsd}`;
}
function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, x => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;" }[x]));
}
function parseLyrics(text) {
  const rows = [];
  String(text || "").split(/\r?\n/).forEach(line => {
    const matches = [...line.matchAll(/\[(\d{1,2}):(\d{2})(?:\.(\d{1,3}))?\]/g)];
    const content = line.replace(/\[[^\]]+\]/g, "").trim();
    if (!content) return;
    if (!matches.length) {
      rows.push({ time: -1, text: content });
      return;
    }
    matches.forEach(match => {
      const time = Number(match[1]) * 60 + Number(match[2]) + Number(`0.${match[3] || 0}`);
      rows.push({ time, text: content });
    });
  });
  return rows.sort((a, b) => a.time - b.time);
}
function itemById(id) {
  const key = String(id || "");
  return state.itemCache.get(key) || state.pageItems.find(x => x.id === key) || state.items.find(x => x.id === key);
}
function currentItem() { return state.queue[state.index]; }
function isRemoteTarget() { return state.playTarget && state.playTarget !== "local"; }
function isDacTarget(target = state.playTarget) { return String(target || "").startsWith("dac:"); }
function isMpdTarget(target = state.playTarget) { return String(target || "").startsWith("mpd:"); }
function loadStoredPlaylists() {
  try {
    const value = JSON.parse(localStorage.getItem(PLAYLIST_STORE_KEY) || "[]");
    return Array.isArray(value) ? value.filter(x => x && x.id && x.name).map(x => ({ id: String(x.id), name: String(x.name), trackIds: Array.isArray(x.trackIds) ? x.trackIds.map(String) : [] })) : [];
  } catch (error) {
    return [];
  }
}
function savePlaylists() {
  localStorage.setItem(PLAYLIST_STORE_KEY, JSON.stringify(state.playlists));
  scheduleUserStateSave();
}
function loadStoredFavorites() {
  try {
    const value = JSON.parse(localStorage.getItem(FAVORITE_STORE_KEY) || "[]");
    return Array.isArray(value) ? value.map(String) : [];
  } catch (error) {
    return [];
  }
}
function saveFavorites() {
  localStorage.setItem(FAVORITE_STORE_KEY, JSON.stringify(state.favorites));
  scheduleUserStateSave();
}
function userStatePayload() {
  return {
    favorites: state.favorites,
    playlists: state.playlists,
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
function scheduleUserStateSave() {
  if (!state.userStateHydrated) return;
  clearTimeout(state.userStateSaveTimer);
  state.userStateSaveTimer = setTimeout(saveUserStateNow, 350);
}
async function saveUserStateNow() {
  if (!state.userStateHydrated || state.userStateSaveInFlight) return;
  state.userStateSaveInFlight = true;
  try {
    let response = await fetch("api/state/user", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(userStatePayload()),
    });
    let data = await response.json().catch(() => ({}));
    if (response.status === 409 && data.state) {
      mergeUserState(data.state);
      response = await fetch("api/state/user", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(userStatePayload()),
      });
      data = await response.json().catch(() => ({}));
    }
    if (response.ok && data.state) state.userStateRevision = Number(data.state.revision || state.userStateRevision || 0);
  } catch (error) {
  } finally {
    state.userStateSaveInFlight = false;
  }
}
function mergeUserState(serverState) {
  const remoteFavorites = Array.isArray(serverState.favorites) ? serverState.favorites.map(String) : [];
  state.favorites = [...new Set([...state.favorites.map(String), ...remoteFavorites])];
  const remotePlaylists = Array.isArray(serverState.playlists) ? serverState.playlists : [];
  const merged = new Map(remotePlaylists.map(item => [String(item.id), item]));
  state.playlists.forEach(item => merged.set(String(item.id), item));
  state.playlists = [...merged.values()];
  const remoteColumns = serverState?.ui?.track_columns;
  if (remoteColumns && typeof remoteColumns === "object" && !Array.isArray(remoteColumns)) {
    state.trackColumnPreferences = { ...Object.fromEntries(Object.entries(remoteColumns).map(([scope, columns]) => [scope, normalizeTrackColumns(columns)])), ...state.trackColumnPreferences };
    persistTrackColumnPreferences();
  }
  const remoteWidths = serverState?.ui?.track_column_widths;
  if (remoteWidths && typeof remoteWidths === "object" && !Array.isArray(remoteWidths)) {
    state.trackColumnWidthPreferences = { ...Object.fromEntries(Object.entries(remoteWidths).map(([scope, widths]) => [scope, normalizeTrackColumnWidths(widths)])), ...state.trackColumnWidthPreferences };
    persistTrackColumnPreferences();
  }
  state.userStateRevision = Number(serverState.revision || 0);
  localStorage.setItem(FAVORITE_STORE_KEY, JSON.stringify(state.favorites));
  localStorage.setItem(PLAYLIST_STORE_KEY, JSON.stringify(state.playlists));
}
async function loadServerUserState() {
  try {
    const response = await fetch("api/state/user");
    const data = await response.json();
    const serverState = data?.state || {};
    if (serverState.initialized) {
      await applyServerUserState(serverState);
    } else {
      state.userStateRevision = Number(serverState.revision || 0);
    }
    state.userStateHydrated = true;
    if (!serverState.initialized) scheduleUserStateSave();
    render();
  } catch (error) {
    // Keep the legacy local copy available while the service is unavailable.
  }
}
async function applyServerUserState(serverState) {
  state.userStateRevision = Number(serverState.revision || 0);
  state.favorites = Array.isArray(serverState.favorites) ? serverState.favorites.map(String) : [];
  state.playlists = Array.isArray(serverState.playlists) ? serverState.playlists : [];
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
  localStorage.setItem(FAVORITE_STORE_KEY, JSON.stringify(state.favorites));
  localStorage.setItem(PLAYLIST_STORE_KEY, JSON.stringify(state.playlists));
  await restorePlaybackSession(serverState.playback || {});
}
async function refreshServerUserState() {
  if (!state.userStateHydrated || state.userStateSaveInFlight || state.userStateRefreshInFlight) return;
  state.userStateRefreshInFlight = true;
  try {
    const response = await fetch("api/state/user");
    const data = await response.json().catch(() => ({}));
    const serverState = data?.state || {};
    const revision = Number(serverState.revision || 0);
    if (serverState.initialized && revision > state.userStateRevision) {
      await applyServerUserState(serverState);
      render();
    }
  } catch (error) {
  } finally {
    state.userStateRefreshInFlight = false;
  }
}
async function restorePlaybackSession(playback) {
  const queueIds = Array.isArray(playback.queue) ? playback.queue.map(String).filter(Boolean) : [];
  if (queueIds.length) {
    try {
      const response = await fetch(`api/library/items?ids=${encodeURIComponent(queueIds.join(","))}`);
      const data = await response.json();
      const items = Array.isArray(data.items) ? data.items : [];
      const byId = new Map(items.map(item => [String(item.id), item]));
      state.queue = queueIds.map(id => byId.get(id)).filter(Boolean);
      cacheLibraryItems(state.queue);
    } catch (error) {
      state.queue = [];
    }
  }
  const currentId = String(playback.current_id || "");
  state.index = state.queue.findIndex(item => String(item.id) === currentId);
  if (state.index < 0 && state.queue.length) state.index = 0;
  state.repeat = ["off", "all", "one"].includes(playback.repeat) ? playback.repeat : "off";
  state.shuffle = Boolean(playback.shuffle);
  state.playTarget = String(playback.target_id || "local");
  state.playTargetName = state.playTarget === "local" ? "本机播放" : "已恢复播放设备";
  updateRepeatShuffleButtons();
  updateDeviceLabel();
  restoreLibraryNowPlaying();
  syncLyricsForCurrentTrack(currentItem());
}
function isPlaylistView(view = state.view) { return String(view || "").startsWith("playlist:"); }
function isPlaylistLibraryView(view = state.view) {
  return view === "random100" || view === "recent" || view === "favorites" || view === "queue" || isPlaylistView(view);
}
function playlistIdFromView(view = state.view) { return String(view || "").replace(/^playlist:/, ""); }
function currentPlaylist() { return state.playlists.find(x => x.id === playlistIdFromView()); }
function makePlaylistId() { return `pl-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`; }
function shuffleItems(list) {
  const items = [...list];
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
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
function updateSortDirectionButton() {
  const button = $("sortDirBtn");
  if (!button) return;
  const asc = state.sortDir === "asc";
  button.textContent = asc ? "升序" : "降序";
  button.title = asc ? "当前为升序，点击切换为降序" : "当前为降序，点击切换为升序";
}
function refreshSortedView() {
  if (isPagedLibraryView()) { state.folderPage = 1; loadPagedLibrary(1, false); }
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
  const allOptions = [
    ["title", "按标题"],
    ["added", "按加入时间"],
    ["artist", "按艺术家"],
    ["album", "按专辑"],
    ["format", "按格式"],
    ["track_no", "按歌曲序号"],
  ];
  const groupOptions = { albums: [["album", "按专辑名"]], artists: [["artist", "按歌手"]], composers: [["composer", "按作曲者"]], genres: [["genre", "按类型名称"]] };
  if (isCreatorAllTracksView() && isCreatorView(view)) return allOptions;
  if (isCreatorAlbumView() && isCreatorView(view)) return [["album", "按专辑名"]];
  if (isAlbumDetailView()) return allOptions;
  if (groupOptions[view] && !state.groupName) return groupOptions[view];
  if (isPlaylistLibraryView(view)) return allOptions;
  return allOptions;
}
function updateSortOptions() {
  const options = sortOptionsForView();
  const defaultKey = isAlbumDetailView()
    ? "track_no"
    : state.view === "folders" && (state.folderRoot || state.folderPath)
      ? "track_no"
      : options[0][0];
  state.sortKey = options.some(([value]) => value === state.sortKey)
    ? state.sortKey
    : (options.some(([value]) => value === defaultKey) ? defaultKey : options[0][0]);
  localStorage.setItem("fnaudio.sortKey.v1", state.sortKey);
}
function compareTrackValue(a, b, key) {
  if (key === "added") return itemAddedTime(a) - itemAddedTime(b);
  if (key === "track_no") {
    const aNo = Number(a.track_no || 0) || 2147483647;
    const bNo = Number(b.track_no || 0) || 2147483647;
    return aNo - bNo || displayText(a.title || "").localeCompare(displayText(b.title || ""), "zh-CN", { numeric: true, sensitivity: "base" });
  }
  return displayText(a[key] || "").localeCompare(displayText(b[key] || ""), "zh-CN", { numeric: true, sensitivity: "base" });
}
function sortTracks(list, key = state.sortKey || "title") {
  const direction = sortDirectionFactor();
  return [...list].sort((a, b) => compareTrackValue(a, b, key) * direction);
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
  return $("searchInput") ? $("searchInput").value.trim() : "";
}
function currentQueryParams() {
  const params = new URLSearchParams();
  params.set("paged", "1");
  params.set("limit", String(state.pageSize));
  params.set("offset", String(Math.max(0, (state.page - 1) * state.pageSize)));
  params.set("view", state.view);
  params.set("sort", state.sortKey || "title");
  params.set("dir", state.sortDir || "asc");
  const search = currentQueryText();
  if (search) params.set("search", search);
  if (state.view === "folders" && state.folderRoot) params.set("root", state.folderRoot);
  if (state.view === "folders" && state.folderPath) params.set("folder", state.folderPath);
  if (isCreatorView() && currentCreatorName()) {
    params.set("group", currentCreatorName());
    if (state.groupName) params.set("album", state.groupName);
  } else if (groupViews[state.view] && state.groupName) params.set("group", state.groupName);
  if (isPlaylistView()) params.set("view", state.view);
  return params;
}
function compareName(a, b) {
  return displayText(a).localeCompare(displayText(b), "zh-CN", { numeric: true, sensitivity: "base" }) * sortDirectionFactor();
}
function folderDisplayName(path) {
  const text = String(path || "").replace(/[\\\/]+$/, "");
  const parts = text.split(/[\\\/]/).filter(Boolean);
  return parts[parts.length - 1] || "根目录";
}
function currentFolderLabel() {
  if (!state.folderRoot) return "根目录";
  const parts = [folderDisplayName(state.folderRoot)];
  if (state.folderPath) parts.push(...String(state.folderPath).split("/").filter(Boolean));
  return parts.join(" / ");
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
  return state.favorites.includes(String(id));
}
function isPrivateHost(host) {
  const value = String(host || "").toLowerCase();
  if (!value || value === "localhost" || value === "127.0.0.1" || value === "::1" || value.endsWith(".local") || value.endsWith(".lan")) return true;
  const parts = value.split(".").map(Number);
  return parts.length === 4 && (
    parts[0] === 10 ||
    parts[0] === 127 ||
    (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) ||
    (parts[0] === 192 && parts[1] === 168) ||
    (parts[0] === 169 && parts[1] === 254)
  );
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
  return Boolean(item?.is_dsd && !isRemoteTarget() && !shouldTranscodeToMp3(item));
}
function effectiveProfile() {
  if (isPrivateHost(window.location.hostname)) return "lan";
  return state.accessProfile || "lan";
}
function updateModeButton() {
  $("modeBtn").textContent = state.mp3Transcode ? "MP3 转码：开" : "MP3 转码：关";
  $("modeBtn").title = state.mp3Transcode ? "当前会把非 MP3 转为 MP3 播放" : "当前优先原格式播放，DSD 本机播放仍转 WAV";
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
  const label = isRemoteTarget() ? state.playTargetName : "本机播放";
  $("deviceBtn").title = label;
}
function remoteDeviceId() { return isRemoteTarget() ? state.playTarget : ""; }
function isIncomingRendererSession() {
  return Boolean(state.rendererSession?.uri);
}
function isPlayingNow() {
  if (isIncomingRendererSession()) {
    const transport = String(state.rendererSession.transport || "").toUpperCase();
    return transport === "PLAYING" || transport === "TRANSITIONING";
  }
  if (isRemoteTarget()) return state.remoteStatus?.transport?.state === "PLAYING";
  return Boolean(audio.src && !audio.paused && !audio.ended);
}
function updateFavoriteControls() {
  const item = currentItem();
  const active = Boolean(item && isFavorite(item.id));
  ["favoriteCurrentBtn", "lyricsFavoriteBtn"].forEach(id => {
    const node = $(id);
    if (!node) return;
    node.classList.toggle("active-control", active);
    node.title = active ? "取消收藏当前歌曲" : "收藏当前歌曲";
    if (id === "lyricsFavoriteBtn") node.textContent = active ? "已收藏" : "收藏";
  });
}
function updateNowMarquee() {
  requestAnimationFrame(() => {
    ["nowTitle", "nowArtist"].forEach(id => {
      const node = $(id);
      if (!node) return;
      const distance = Math.max(0, node.scrollWidth - node.clientWidth);
      node.style.setProperty("--marquee-distance", `${distance}px`);
      node.classList.toggle("is-overflowing", distance > 2);
    });
  });
  syncPlayerProgress();
}
function syncNowPlayingTime(seconds = currentSeconds(), duration = seekDuration()) {
  const node = $("nowTime");
  if (node) node.textContent = `${clock(seconds)} / ${clock(duration)}`;
}
function syncPlayerProgress() {
  const duration = seekDuration();
  const seconds = currentSeconds();
  syncNowPlayingTime(seconds, duration);
  updateSeekRail();
}
function updateSeekRail(value = $("seek")?.value || 0) {
  const seek = $("seek");
  if (seek) seek.style.setProperty("--seek-fill", `${Math.max(0, Math.min(100, Number(value) || 0))}%`);
}
function externalArtworkUrl(value) {
  try {
    const url = new URL(String(value || ""), window.location.href);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch (error) {
    return "";
  }
}
function renderIncomingRendererSession(session) {
  const title = displayText(session.title || "DLNA 输入");
  const artist = displayText(session.artist || "未知艺术家");
  const art = externalArtworkUrl(session.art_url);
  $("nowTitle").textContent = title;
  $("nowArtist").textContent = `${artist} · 来自 DLNA 控制端 · ${state.playTargetName || "本机 USB DAC"}`;
  $("nowCover").innerHTML = art ? `<img src="${escapeHtml(art)}" onerror="this.remove()">` : "♫";
  updateNowMarquee();
}
function restoreLibraryNowPlaying() {
  const item = currentItem();
  if (!item) {
    $("nowTitle").textContent = "未选择曲目";
    $("nowArtist").textContent = "从音乐库选择一首歌曲";
    $("nowCover").textContent = "♫";
  } else {
    const cover = coverUrl(item);
    $("nowTitle").textContent = displayTrackTitle(item);
    $("nowArtist").textContent = `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)}`;
    $("nowCover").innerHTML = cover ? `<img src="${cover}" onerror="this.remove()">` : "♫";
  }
  updateNowMarquee();
}
async function refreshRendererSession() {
  if (state.rendererRequestInFlight) return;
  state.rendererRequestInFlight = true;
  try {
    const response = await fetch("api/dlna/renderer/status");
    const data = await response.json().catch(() => ({}));
    const session = data.available ? (data.state || {}) : {};
    const transport = String(session.transport || "").toUpperCase();
    const active = Boolean(session.uri) && !["STOPPED", "NO_MEDIA_PRESENT"].includes(transport);
    const previousActive = isIncomingRendererSession();
    state.rendererSession = active ? session : null;
    state.rendererSnapshotAt = Date.now();
    if (active) renderIncomingRendererSession(session);
    else if (previousActive) restoreLibraryNowPlaying();
  } catch (error) {
  } finally {
    state.rendererRequestInFlight = false;
  }
}
function setPlayButton(playing) {
  $("playBtn").innerHTML = `<span class="transport-icon ${playing ? "pause-icon" : "play-icon"}"></span>`;
}
function stopLocalAudio() {
  state.playbackLoadToken += 1;
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
  setPlayButton(false);
}
async function stopPlayback() {
  if (isIncomingRendererSession()) {
    await controlIncomingRenderer("stop");
    restoreLibraryNowPlaying();
    return;
  }
  if (isRemoteTarget()) {
    await remoteControl("stop");
    state.remoteStatus = { transport: { state: "STOPPED" }, position: { rel_seconds: 0, duration_seconds: state.remoteStatus?.position?.duration_seconds || 0 } };
    updateRemoteUi();
    return;
  }
  state.streamOffset = 0;
  state.pendingSeekTime = null;
  state.transcodeCacheReady = false;
  state.playSourceKind = "";
  stopLocalAudio();
  $("elapsed").textContent = "0:00";
  $("seek").value = 0;
  updateMediaSessionPlaybackState();
  syncState();
}
function stopRemoteOnUnload() {
  if (!isRemoteTarget() || isMpdTarget()) return;
  const payload = JSON.stringify({ target_id: state.playTarget, action: "stop", track_id: currentItem()?.id || "" });
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon("api/playback/control", new Blob([payload], { type: "application/json" }));
      return;
    }
  } catch (error) {
  }
  try {
    fetch("api/playback/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      keepalive: true,
    }).catch(() => {});
  } catch (error) {
  }
}
function updateRemoteUi() {
  if (updateIncomingRendererUi()) return;
  const transport = state.remoteStatus?.transport?.state || "";
  const duration = seekDuration();
  if (!isRemoteTarget()) return;
  if (duration > 0) {
    $("duration").textContent = clock(duration);
    if (!state.seeking) {
      const seconds = currentSeconds();
      $("elapsed").textContent = clock(seconds);
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
    $("duration").textContent = clock(duration);
    if (!state.seeking) {
      const seconds = currentSeconds();
      $("elapsed").textContent = clock(seconds);
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
    const response = await fetch("api/playback/control", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_id: "mpd", action, position}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.message || "DLNA Renderer 控制失败");
    if (action === "stop") state.rendererSession = null;
    else if (state.rendererSession) {
      state.rendererSession.transport = action === "pause" ? "PAUSED_PLAYBACK" : "PLAYING";
      if (action === "seek" && position != null) state.rendererSession.position = Number(position) || 0;
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
  if (!("mediaSession" in navigator) || !item) return;
  const localCover = coverUrl(item);
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
  } catch (error) {
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
  try {
    navigator.mediaSession.playbackState = isPlayingNow() ? "playing" : "paused";
  } catch (error) {
  }
  updateMediaSessionPosition();
}
function applyCoreSnapshot(core, shouldLoad = true) {
  const currentId = core?.current || core?.state?.current;
  if (!currentId) return false;
  const index = state.queue.findIndex(item => item.id === currentId);
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
  return true;
}
async function coreControl(action, position = null) {
  const item = currentItem();
  const response = await fetch("api/playback/control", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ target_id: remoteDeviceId() || "local", action, position, track_id: item?.id || "" }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) return false;
  applyCoreSnapshot(data.core, action === "next" || action === "previous");
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
  if (!("mediaSession" in navigator) || setupMediaSession.done) return;
  setupMediaSession.done = true;
  const setHandler = (action, handler) => {
    try { navigator.mediaSession.setActionHandler(action, handler); } catch (error) {}
  };
  setHandler("play", () => {
    if (isRemoteTarget()) remoteControl("play");
    else if (!audio.src && state.queue.length) loadCurrent();
    else audio.play().catch(() => {});
  });
  setHandler("pause", () => {
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
async function refreshRemoteStatus() {
  if (!isRemoteTarget()) return;
  try {
    const response = await fetch(`api/playback/status?target_id=${encodeURIComponent(remoteDeviceId())}`);
    const data = await response.json();
    if (data.error) return;
    state.remoteStatus = data;
    state.remoteSnapshotAt = Date.now();
    state.remoteBaseSeconds = Number(data?.position?.rel_seconds || 0);
    maybeAdvanceRemoteQueue(data);
    updateRemoteUi();
  } catch (error) {
  }
}
function maybeAdvanceRemoteQueue(data) {
  const transport = (data?.transport?.state || "").toUpperCase();
  const position = data?.position || {};
  const item = currentItem();
  const duration = Number(position.duration_seconds || 0);
  const rel = Number(position.rel_seconds || 0);
  const endedByTime = item?.cue_track
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
}
async function remoteControl(action, position = null, quiet = false) {
  if (!isRemoteTarget()) return false;
  const item = currentItem();
  const response = await fetch("api/playback/control", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ target_id: remoteDeviceId(), action, position, track_id: item?.id || "" }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    if (!quiet) alert(data.message || data.error || "远端控制失败");
    return false;
  }
  setTimeout(refreshRemoteStatus, 300);
  return true;
}
function filteredTracks() {
  if (isPagedLibraryView() && isPagedTrackListing()) return state.pageItems;
  const search = currentQueryText().toLowerCase();
  let list = state.items;
  if (groupViews[state.view] && state.groupName) list = state.items.filter(x => (x[groupViews[state.view]] || "未分类") === state.groupName);
  else if (state.view === "dsd") list = state.items.filter(x => x.is_dsd);
  else if (state.view === "queue") list = state.queue;
  else if (state.view === "random100") list = random100Tracks();
  else if (state.view === "recent") list = recentTracks();
  else if (state.view === "favorites") list = favoriteTracks();
  else if (isPlaylistView()) list = playlistTracks();
  if (search) list = list.filter(item => trackMatchesSearch(item, search));
  return sortTracks(list);
}
function trackMatchesSearch(item, search = currentQueryText().toLowerCase()) {
  if (!search) return true;
  return [
    item?.title,
    item?.artist,
    item?.album,
    item?.album_artist,
    item?.composer,
    item?.genre,
    item?.folder,
    item?.library_root,
    item?.format,
  ].map(value => String(value || "").toLowerCase()).join(" ").includes(search);
}
function hasMultipleLibraryRoots() {
  const paths = state.libraryStatus?.library_paths || [];
  return Array.isArray(paths) && paths.length > 1;
}
function hasSingleFolderRoot() {
  return Array.isArray(state.folderRootRows) && state.folderRootRows.length === 1;
}
function libraryRootLabels() {
  const paths = state.libraryStatus?.library_paths || [];
  const bases = paths.map(path => {
    const parts = String(path || "").replace(/[\\\/]+$/, "").split(/[\\\/]/).filter(Boolean);
    return parts[parts.length - 1] || "音乐目录";
  });
  const counts = bases.reduce((map, name) => (map[name] = (map[name] || 0) + 1, map), {});
  return paths.map((path, index) => {
    const parts = String(path || "").replace(/[\\\/]+$/, "").split(/[\\\/]/).filter(Boolean);
    const base = bases[index];
    return counts[base] > 1 && parts.length > 1 ? `${parts[parts.length - 2]}/${base}` : base;
  });
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
function clientPagedTotal(view = state.view) {
  const ids = view === "favorites"
    ? state.favorites
    : isPlaylistView(view)
      ? (currentPlaylist()?.trackIds || [])
      : [];
  const source = view === "queue" ? state.queue : ids.map(itemById).filter(Boolean);
  const search = currentQueryText().toLowerCase();
  if (search) return source.filter(item => trackMatchesSearch(item, search)).length;
  if (view === "queue") return state.queue.length;
  if (view === "favorites" || isPlaylistView(view)) return ids.length;
  return 0;
}
function clientPagedTracks() {
  const offset = Math.max(0, ((Number(state.page) || 1) - 1) * state.pageSize);
  const limit = Math.max(1, state.pageSize);
  if (state.view === "queue") {
    return queueDisplayEntries().slice(offset, offset + limit).map(({ item, queueIndex }) => ({ ...item, __queueIndex: queueIndex }));
  }
  const ids = state.view === "favorites"
    ? state.favorites
    : isPlaylistView()
      ? (currentPlaylist()?.trackIds || [])
      : [];
  if (ids.length) hydrateReferencedIds(ids);
  const source = ids.map(itemById).filter(Boolean);
  const search = currentQueryText().toLowerCase();
  const filtered = search ? source.filter(item => trackMatchesSearch(item, search)) : source;
  return sortTracks(filtered).slice(offset, offset + limit);
}
function queueDisplayEntries() {
  const search = currentQueryText().toLowerCase();
  const direction = sortDirectionFactor();
  return state.queue
    .map((item, queueIndex) => ({ item, queueIndex }))
    .filter(({ item }) => !search || trackMatchesSearch(item, search))
    .sort((left, right) => compareTrackValue(left.item, right.item, state.sortKey || "title") * direction || left.queueIndex - right.queueIndex);
}
function currentQueuePage() {
  if (state.index < 0) return 1;
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
function syncCurrentQueuePresentation(previousIndex) {
  if (state.view !== "queue" || previousIndex === state.index) return;
  state.page = currentQueuePage();
  render();
  requestAnimationFrame(() => requestAnimationFrame(scrollCurrentQueueTrackIntoView));
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
  const localCover = coverUrl(cachedItem) || (coverTrackId ? mediaUrl(`cover/${encodeURIComponent(coverTrackId)}`) : "");
  const online = metadataImage ? mediaUrl(metadataImage) : "";
  const image = localCover || online;
  const attributes = localCover && online ? `data-artwork-local="1" data-metadata-image="${escapeHtml(online)}"` : "";
  return `<div class="group-icon" ${attributes}>${groupFallbackIcon(view)}${image ? `<img src="${escapeHtml(image)}" loading="lazy" alt="">` : ""}</div>`;
}
function applyGroupArtwork(node, imageUrl) {
  if (!node?.isConnected || !imageUrl) return;
  const existing = node.querySelector("img");
  if (existing && existing.src === new URL(imageUrl, location.href).href) return;
  if (existing) existing.remove();
  const image = document.createElement("img");
  image.src = imageUrl;
  image.loading = "lazy";
  image.alt = "";
  image.addEventListener("load", () => node.classList.add("has-cover"), { once: true });
  image.addEventListener("error", () => {
    image.remove();
    node.classList.remove("has-cover");
  }, { once: true });
  node.appendChild(image);
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
  const nodes = [...document.querySelectorAll(".group-icon img, .album-detail-cover img")].map(image => image.parentElement).filter(Boolean);
  if (!nodes.length) return;
  nodes.forEach(prepareLocalGroupArtwork);
}
function activeTrackColumns() {
  return currentTrackColumns();
}
function trackGridTemplate() {
  const widths = currentTrackColumnWidths();
  return [...activeTrackColumns().map(key => `${widths[key] || TRACK_COLUMN_DEFINITIONS[key].width}px`), "minmax(0,1fr)"].join(" ");
}
function applyTrackGridTemplate() {
  const template = trackGridTemplate();
  $("tableHead")?.style.setProperty("--fnaudio-track-columns", template);
  document.body.style.setProperty("--fnaudio-track-columns", template);
}
function trackColumnWidthLimits(key) {
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
  const rate = Number(item.sample_rate || 0);
  const depth = Number(item.bit_depth || 0);
  const bitrate = Number(item.bitrate || 0);
  const pcm = rate ? `${Math.round(rate / 1000)}kHz${depth ? `/${depth}bit` : ""}` : "";
  return pcm || (bitrate ? `${Math.round(bitrate / 1000)}kbps` : "—");
}
function trackAddedDate(item) {
  const seconds = itemAddedTime(item);
  if (!seconds) return "—";
  try { return new Date(seconds > 99999999999 ? seconds / 1000000000 : seconds * 1000).toLocaleDateString("zh-CN"); } catch (error) { return "—"; }
}
function trackColumnValue(item, key) {
  const trackNo = Number(item.track_no || 0) > 0 ? String(Number(item.track_no)).padStart(2, "0") : "—";
  const values = {
    track_no: trackNo,
    artist: displayText(item.artist),
    album: displayText(item.album),
    format: item.format || "—",
    duration: Number(item.duration || 0) > 0 ? clock(item.duration) : "—",
    size: formatSize(item.size) || "—",
    quality: trackQuality(item),
    added: trackAddedDate(item),
    composer: displayText(item.composer),
    genre: displayText(item.genre),
  };
  return escapeHtml(values[key] || "—");
}
function canSortTrackColumn(key) {
  return Boolean(TRACK_COLUMN_DEFINITIONS[key]?.sort) && sortOptionsForView().some(([value]) => value === TRACK_COLUMN_DEFINITIONS[key].sort);
}
function renderTableHead(target = $("tableHead")) {
  const head = target;
  if (!head) return;
  const columns = activeTrackColumns();
  if ((isCreatorView() && !currentCreatorName()) || (state.view === "genres" && !state.groupName)) {
    head.style.setProperty("--fnaudio-track-columns", "minmax(280px,1fr)");
    const sortKey = groupViews[state.view];
    const indicator = state.sortKey === sortKey ? `<span class="track-sort-indicator">${state.sortDir === "asc" ? "&#9650;" : "&#9660;"}</span>` : "";
    head.innerHTML = `<div class="album-header-cell"><button class="track-head-button" type="button" data-track-sort="${sortKey}">标题${indicator}</button></div>`;
    document.body.style.setProperty("--fnaudio-track-columns", "minmax(280px,1fr)");
    head.querySelectorAll("[data-track-sort]").forEach(button => button.onclick = () => applyTrackSort(button.dataset.trackSort));
    return;
  }
  if (isAlbumCollectionView()) {
    head.style.setProperty("--fnaudio-track-columns", "minmax(280px,1fr) minmax(160px,240px) 130px");
    const indicator = state.sortKey === "album" ? `<span class="track-sort-indicator">${state.sortDir === "asc" ? "&#9650;" : "&#9660;"}</span>` : "";
    head.innerHTML = `<div class="album-header-cell"><button class="track-head-button" type="button" data-track-sort="album">标题${indicator}</button></div><div class="album-header-cell">歌手</div><div class="album-header-cell">发行日期</div>`;
    document.body.style.setProperty("--fnaudio-track-columns", "minmax(280px,1fr) minmax(160px,240px) 130px");
    head.querySelectorAll("[data-track-sort]").forEach(button => button.onclick = () => applyTrackSort(button.dataset.trackSort));
    return;
  }
  const currentSort = state.sortKey || "title";
  const renderHeader = (key, label, sortKey) => {
    const sortable = sortKey && sortOptionsForView().some(([value]) => value === sortKey);
    const indicator = currentSort === sortKey ? `<span class="track-sort-indicator">${state.sortDir === "asc" ? "&#9650;" : "&#9660;"}</span>` : "";
    const control = sortable
      ? `<button class="track-head-button" type="button" data-track-sort="${sortKey}">${label}${indicator}</button>`
      : `<span class="track-head-label">${label}</span>`;
    return `<div class="track-header-cell" data-track-column="${key}">${control}<span class="column-resize-handle" data-column-resize="${key}" title="拖动调整列宽" aria-hidden="true"></span></div>`;
  };
  applyTrackGridTemplate();
  head.innerHTML = columns.map(key => renderHeader(key, TRACK_COLUMN_DEFINITIONS[key].label, TRACK_COLUMN_DEFINITIONS[key].sort)).join("") + `<button class="table-head-more" type="button" data-open-columns title="列显示" aria-label="列显示"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg></button>`;
  head.querySelectorAll("[data-track-sort]").forEach(button => button.onclick = () => applyTrackSort(button.dataset.trackSort));
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
}
function renderAlbumDetail(list) {
  const album = displayText(state.groupName || "未命名专辑");
  const first = list.find(item => item?.cover_url) || list[0] || {};
  const metadata = state.albumMetadata[album] || {};
  const artist = displayText(metadata.artist || list.find(item => item?.artist)?.artist || "未知歌手");
  const releaseDate = displayText(metadata.release_date || "");
  const localCover = coverUrl(first);
  const onlineCover = metadata.image_url ? mediaUrl(metadata.image_url) : "";
  const cover = localCover || onlineCover;
  const coverAttributes = localCover && onlineCover ? `data-artwork-local="1" data-metadata-image="${escapeHtml(onlineCover)}"` : "";
  const coverMarkup = `${groupFallbackIcon("albums")}${cover ? `<img src="${escapeHtml(cover)}" loading="lazy" alt="">` : ""}`;
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
      <div class="album-detail-track-list">${list.map(renderTrack).join("")}</div>
    </section>
  </div>`;
}
function trackRowSelectionKey(item, index = 0) {
  return `${String(item?.id || "")}::${Math.max(0, Number(index) || 0)}`;
}
function renderTrack(item, index = 0) {
  const localCover = coverUrl(item);
  const queueIndex = Number(item.__queueIndex);
  const hasQueuePosition = Number.isInteger(queueIndex) && queueIndex >= 0;
  const isCurrent = state.view === "queue" && hasQueuePosition && queueIndex === state.index;
  const columns = activeTrackColumns();
  const artist = displayText(item.artist) || "未知歌手";
  const album = displayText(item.album);
  const mobileSubtitle = album && album !== artist ? `${artist} · ${album}` : artist;
  const rowKey = trackRowSelectionKey(item, index);
  const isSelected = state.selectedTrackRowKeys.has(rowKey);
  const playingIndicator = isCurrent ? `<span class="track-playing-indicator" aria-label="正在播放">正在播放</span>` : "";
  const titleCell = `<div class="track-main" data-play="${escapeHtml(item.id)}"><div class="track-cover">${localCover ? `<img src="${coverUrl(item)}" loading="lazy" onerror="this.remove()">` : ""}<span>${item.is_dsd ? "◈" : "♫"}</span></div><div class="track-info"><div class="track-title-line"><strong class="track-title">${escapeHtml(displayTrackTitle(item))}</strong>${playingIndicator}</div><span class="mobile-track-subtitle">${escapeHtml(mobileSubtitle)}</span></div></div>`;
  return `<div class="track${isCurrent ? " is-current" : ""}${isSelected ? " is-selected" : ""}" data-track-row-key="${escapeHtml(rowKey)}" data-track-id="${escapeHtml(item.id)}"${hasQueuePosition ? ` data-queue-index="${queueIndex}"` : ""}>
    ${columns.map(key => key === "title" ? titleCell : `<span class="track-cell track-cell-${key}${key === "format" && item.is_dsd ? " dsd" : ""}">${trackColumnValue(item, key)}</span>`).join("")}
  </div>`;
}
function renderGroups() {
  const groupView = isCreatorAlbumView() ? "albums" : state.view;
  return groupedTracks().map(group => {
    const name = displayText(group.name || "未分类");
    const key = `group:${groupView}:${name}`;
    return `<div class="group-row${state.selectedGroupKeys.has(key) ? " is-selected" : ""}" data-group-row data-group-key="${escapeHtml(key)}" data-group-type="group" data-group-view="${escapeHtml(groupView)}" data-group-name="${encodeURIComponent(name)}" data-group-track-count="${Number(group.track_count || 0)}">
    ${groupIcon(groupView, [state.itemCache.get(String(group.cover_track_id || ""))].filter(Boolean), group.cover_track_id, name, group.image_url)}
    <div class="group-info"><strong>${escapeHtml(name)}</strong><span>${Number(group.track_count || 0)} 首</span></div>
  </div>`;
  }).join("");
}
function renderCreatorAllSongsEntry() {
  const creator = displayText(currentCreatorName() || `未知${currentCreatorLabel()}`);
  const fallbackTotal = groupedTracks().reduce((total, group) => total + Number(group.track_count || 0), 0);
  const trackTotal = Number(currentCreatorTrackTotal() || fallbackTotal || 0);
  return `<button class="artist-all-songs-entry" type="button" data-open-creator-all-tracks>
    <span class="artist-all-songs-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M9 18V5l10-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="16" cy="16" r="3"/></svg></span>
    <span class="artist-all-songs-copy"><strong>所有歌曲</strong><small>查看 ${escapeHtml(creator)} 的全部歌曲</small></span>
    <span class="artist-all-songs-count">${trackTotal ? `${trackTotal} 首` : "查看歌曲"}</span>
    <span class="artist-all-songs-chevron" aria-hidden="true">&gt;</span>
  </button>`;
}
function renderAlbumGroups() {
  const albums = groupedTracks().map(group => {
    const name = displayText(group.name || "未分类");
    const key = `group:albums:${name}`;
    const metadata = state.albumMetadata[name] || {};
    const artist = displayText(metadata.artist || group.artist || "未知歌手");
    const releaseDate = displayText(metadata.release_date || "-");
    return `<div class="album-group-row${state.selectedGroupKeys.has(key) ? " is-selected" : ""}" data-group-row data-group-key="${escapeHtml(key)}" data-group-type="group" data-group-view="albums" data-group-name="${encodeURIComponent(name)}" data-group-track-count="${Number(group.track_count || 0)}" data-album-metadata-name="${escapeHtml(name)}"><div class="album-group-title">${groupIcon("albums", [state.itemCache.get(String(group.cover_track_id || ""))].filter(Boolean), group.cover_track_id, name, group.image_url)}<strong>${escapeHtml(name)}</strong></div><span class="album-group-artist">${escapeHtml(artist)}</span><span class="album-group-release-date">${escapeHtml(releaseDate)}</span></div>`;
  }).join("");
  return `${isCreatorAlbumView() ? renderCreatorAllSongsEntry() : ""}${albums}`;
}
function renderCreatorAllTracks(list) {
  const creator = displayText(currentCreatorName() || `未知${currentCreatorLabel()}`);
  return `<nav class="artist-all-tracks-breadcrumb" aria-label="${currentCreatorLabel()}路径">
    <button type="button" data-creator-root-back>${currentCreatorLabel()}</button><span aria-hidden="true">&gt;</span>
    <button type="button" data-group-back>${escapeHtml(creator)}</button><span aria-hidden="true">&gt;</span>
    <strong>所有歌曲</strong>
  </nav>${list.map(renderTrack).join("")}`;
}
function renderGenreTracks(list) {
  const genre = displayText(state.groupName || "未分类");
  return `<nav class="artist-all-tracks-breadcrumb category-tracks-breadcrumb" aria-label="类型路径">
    <button type="button" data-group-back>类型</button><span aria-hidden="true">&gt;</span>
    <strong>${escapeHtml(genre)}</strong>
  </nav>${list.map(renderTrack).join("")}`;
}
function renderFolders() {
  const data = folderChildren();
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
      <div class="group-info"><strong>${escapeHtml(name)}</strong><span>${Number(row.track_count || 0)} 首</span></div>
    </div>`;
  }).join("");
  const folderPages = Math.max(1, Math.ceil(Number(state.folderTotal || 0) / state.folderPageSize));
  const folderPager = folderPages > 1 ? `<div class="folder-pager"><button class="secondary-button" data-folder-page-step="-1" ${state.folderPage <= 1 ? "disabled" : ""}>上一组文件夹</button><span>文件夹 ${state.folderPage} / ${folderPages}</span><button class="secondary-button" data-folder-page-step="1" ${state.folderPage >= folderPages ? "disabled" : ""}>下一组文件夹</button></div>` : "";
  const tracks = data.tracks;
  return breadcrumb + folders + folderPager + tracks.map(renderTrack).join("");
}
function renderPager() {
  if (!isClientPagedView() && (!isPagedLibraryView() || (!isPagedTrackListing() && !isPagedGroupListing()))) return "";
  const total = Math.max(0, Number(isClientPagedView() ? clientPagedTotal() : state.pageTotal || 0));
  const pages = Math.max(1, Math.ceil(total / state.pageSize));
  if (pages <= 1) return "";
  const page = Math.min(Math.max(1, Number(state.page) || 1), pages);
  const prevDisabled = page <= 1 ? "disabled" : "";
  const nextDisabled = page >= pages ? "disabled" : "";
  const unit = isPagedGroupListing() ? "项" : "首";
  return `<div class="pager-inner">
    <div class="pager-nav">
      <button class="pager-nav-button" type="button" data-page-go="1" title="首页" aria-label="首页" ${prevDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 12 12l6 6"/><path d="m11 6-6 6 6 6"/></svg></button>
      <button class="pager-nav-button" type="button" data-page-step="-1" title="上一页" aria-label="上一页" ${prevDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg></button>
      <span class="pager-page-summary" aria-label="当前页">第 ${page} / ${pages} 页</span>
      <button class="pager-nav-button" type="button" data-page-step="1" title="下一页" aria-label="下一页" ${nextDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg></button>
      <button class="pager-nav-button" type="button" data-page-go="${pages}" title="尾页" aria-label="尾页" ${nextDisabled}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 6 6-6 6"/><path d="m13 6 6 6-6 6"/></svg></button>
    </div>
    <div class="pager-status"><span>共 ${total} ${unit}</span><button class="pager-refresh-button" type="button" data-refresh-library title="刷新音乐库" aria-label="刷新音乐库"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6v5h-5"/><path d="M4 18v-5h5"/><path d="M18.4 9A7 7 0 0 0 6.2 6.8L4 9"/><path d="M5.6 15a7 7 0 0 0 12.2 2.2L20 15"/></svg></button></div>
  </div>`;
}
function updateMobilePagerVisibility() {
  const pager = $("pager");
  const list = $("trackList");
  if (!pager) return;
  const hasPager = Boolean(pager.querySelector(".pager-inner"));
  if (!hasPager || !window.matchMedia("(max-width: 760px)").matches) {
    pager.classList.toggle("mobile-visible", hasPager);
    return;
  }
  const atBottom = !list || list.scrollHeight <= list.clientHeight + 1
    || list.scrollTop + list.clientHeight >= list.scrollHeight - 2;
  const wasVisible = pager.classList.contains("mobile-visible");
  pager.classList.toggle("mobile-visible", atBottom);
  if (atBottom && !wasVisible && list) {
    requestAnimationFrame(() => {
      if (pager.classList.contains("mobile-visible")) list.scrollTop = list.scrollHeight;
    });
  }
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
  updateSortOptions();
  updateSortDirectionButton();
  const isGroup = Boolean(groupViews[state.view]);
  const isFolder = state.view === "folders";
  const creatorAllTracks = isCreatorAllTracksView();
  const isGroupRoot = isGroup && !state.groupName && !creatorAllTracks;
  const folderState = isFolder ? folderChildren() : null;
  const pagedTracks = isPagedTrackListing() ? state.pageItems : [];
  const list = isGroupRoot ? groupedTracks() : (isFolder ? (folderState?.tracks || []) : (isClientPagedView() ? clientPagedTracks() : (isPagedTrackListing() ? pagedTracks : filteredTracks())));
  const albumDetail = isAlbumDetailView();
  const genreDetail = state.view === "genres" && Boolean(state.groupName);
  const playlistToolbar = isPlaylistView() && currentPlaylist()
    ? `<div class="playlist-toolbar"><span>${clientPagedTotal()} 首歌曲</span><button class="danger-button" data-delete-playlist="${escapeHtml(currentPlaylist().id)}">删除播放列表</button></div>`
    : state.view === "favorites"
      ? `<div class="playlist-toolbar"><span>${clientPagedTotal()} 首收藏歌曲</span></div>`
      : state.view === "queue"
        ? `<div class="playlist-toolbar"><span>${state.queue.length} 首歌曲</span><button class="danger-button" data-clear-queue ${state.queue.length ? "" : "disabled"}>清空队列</button></div>`
      : isGroup && state.groupName && !albumDetail && !genreDetail
      ? `<div class="category-detail"><div class="category-detail-main">${groupIcon(isCreatorView() ? "albums" : state.view, list)}<div><strong>${escapeHtml(state.groupName)}</strong><span>${isCreatorView() ? `${escapeHtml(currentCreatorName())} · ` : ""}${Number(state.pageTotal || list.length)} 首歌曲</span></div></div><div class="category-detail-actions"><button class="secondary-button" data-play-all>播放全部</button><button class="secondary-button" data-group-back>返回分类</button></div></div>`
    : "";
  const listHtml = isFolder
    ? renderFolders()
    : isGroupRoot
      ? (isAlbumCollectionView() ? renderAlbumGroups() : renderGroups())
      : creatorAllTracks
        ? renderCreatorAllTracks(list)
        : genreDetail
          ? renderGenreTracks(list)
        : albumDetail
          ? renderAlbumDetail(list)
          : playlistToolbar + list.map(renderTrack).join("");
  renderTableHead();
  $("tableHead").hidden = albumDetail;
  $("libraryScroll").classList.toggle("album-detail-scroll", albumDetail);
  $("trackList").classList.toggle("group-mode", isGroupRoot);
  $("trackList").classList.toggle("album-detail-mode", albumDetail);
  $("trackList").classList.toggle("artist-all-tracks-mode", creatorAllTracks);
  $("trackList").innerHTML = listHtml;
  setTrackSelection([...state.selectedTrackRowKeys]);
  if (albumDetail) renderTableHead($("albumDetailTableHead"));
  $("pager").innerHTML = renderPager();
  updateMobilePagerVisibility();
  bindTrackHeaderScroll();
  requestAnimationFrame(() => {
    measureAutoTrackColumnWidths();
    syncTrackHeaderScroll();
    updateMobilePagerVisibility();
  });
  loadGroupArtwork();
  $("empty").hidden = list.length > 0 || (isFolder && folderState && folderState.folders.length > 0) || (isGroupRoot && groupedTracks().length > 0);
  const emptyText = $("emptyText");
  if (emptyText && state.libraryStatus) {
    const path = state.libraryStatus.library_path || "";
    emptyText.textContent = `${state.libraryStatus.message || "没有找到音乐文件"}${path ? `：${path}` : ""}`;
  }
  $("allCount").textContent = String(Number(state.libraryStatus?.count || 0));
  $("dsdCount").textContent = String(Number(state.libraryStatus?.dsd_count || 0));
  $("recentCount").textContent = String(Number(state.libraryStatus?.count || 0));
  $("favoriteCount").textContent = state.favorites.length;
  $("queueCount").textContent = state.queue.length;
  updateSortDirectionButton();
  renderPlaylistNav();
  const labels = { all: "全部音乐", dsd: "DSD 音乐", queue: "当前队列", folders: "文件夹", albums: "专辑", artists: "歌手", composers: "作曲者", genres: "类型", random100: "随机 100 首", recent: "最近添加", favorites: "收藏歌曲" };
  $("viewTitle").textContent = isPlaylistView()
    ? (currentPlaylist()?.name || "播放列表")
    : creatorAllTracks
      ? "所有歌曲"
      : (isAlbumSurfaceView() ? "专辑" : (labels[state.view] || "音乐库"));
  $("viewSub").textContent = scanProgressText() || "你的音乐，只在你的 NAS 上。";
  $("mobileViewTitle").textContent = $("viewTitle").textContent;
  $("mobileViewSub").textContent = creatorAllTracks
    ? displayText(currentCreatorName())
    : state.view === "folders" && currentFolderLabel
      ? currentFolderLabel()
      : "本地音乐库";
  document.querySelectorAll(".nav-item").forEach(x => x.classList.toggle("active", x.dataset.view === state.view));
  document.querySelectorAll("[data-play]").forEach(button => button.onclick = event => {
    const row = button.closest("[data-track-row-key]");
    const mobile = window.matchMedia("(max-width: 760px)").matches;
    if (event.ctrlKey && row && !mobile) {
      event.preventDefault();
      event.stopPropagation();
      toggleTrackSelection(row.dataset.trackRowKey);
      return;
    }
    if (!mobile) {
      event.preventDefault();
      event.stopPropagation();
      if (row) setTrackSelection([row.dataset.trackRowKey]);
      return;
    }
    if (state.selectedTrackRowKeys.size) {
      event.preventDefault();
      event.stopPropagation();
      setTrackSelection([]);
      return;
    }
    playById(button.dataset.play);
  });
  document.querySelectorAll("[data-track-row-key]").forEach(row => {
    row.onclick = event => {
      if (!event.ctrlKey || window.matchMedia("(max-width: 760px)").matches) return;
      event.preventDefault();
      toggleTrackSelection(row.dataset.trackRowKey);
    };
    row.addEventListener("click", event => {
      if (event.ctrlKey || window.matchMedia("(max-width: 760px)").matches || !state.selectedTrackRowKeys.size) return;
      event.preventDefault();
      setTrackSelection([]);
    });
    row.oncontextmenu = event => {
      if (window.matchMedia("(max-width: 760px)").matches) return;
      event.preventDefault();
      const id = String(row.dataset.trackId || "");
      const rowKey = String(row.dataset.trackRowKey || "");
      if (!state.selectedTrackRowKeys.has(rowKey)) setTrackSelection([rowKey]);
      openTrackContextMenu(id, event.clientX, event.clientY);
    };
  });
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
  document.querySelectorAll("[data-group-back]").forEach(b => b.onclick = () => {
    if (isCreatorAllTracksView()) setCurrentCreatorAllTracks(false);
    else if (isCreatorView() && state.groupName) state.groupName = "";
    else if (isCreatorView() && currentCreatorName()) clearCurrentCreator();
    else state.groupName = "";
    resetLibraryScrollPosition();
    Promise.resolve(loadPagedLibrary(1, false)).finally(() => requestAnimationFrame(resetLibraryScrollPosition));
  });
  document.querySelectorAll("[data-creator-root-back]").forEach(button => button.onclick = () => {
    clearCurrentCreator();
    state.page = 1;
    state.pageItems = [];
    loadPagedLibrary(1, false);
  });
  document.querySelectorAll("[data-open-creator-all-tracks]").forEach(button => button.onclick = () => {
    setCurrentCreatorAllTracks(true);
    state.groupName = "";
    state.page = 1;
    state.pageItems = [];
    loadPagedLibrary(1, false);
  });
  document.querySelectorAll("[data-folder-crumb-root]").forEach(crumb => crumb.onclick = () => {
    state.folderRoot = decodeURIComponent(crumb.dataset.folderCrumbRoot || "");
    state.folderPath = decodeURIComponent(crumb.dataset.folderCrumbPath || "");
    state.folderPage = 1;
    state.page = 1;
    state.pageItems = [];
    loadPagedLibrary(1, false);
  });
  document.querySelectorAll("[data-page-step]").forEach(b => b.onclick = () => {
    const step = Number(b.dataset.pageStep || 0);
    const nextPage = Math.max(1, (Number(state.page) || 1) + step);
    if (isClientPagedView()) {
      state.page = nextPage;
      render();
    } else {
      loadPagedLibrary(nextPage, false);
    }
  });
  document.querySelectorAll("[data-page-go]").forEach(button => button.onclick = () => {
    const nextPage = Math.max(1, Number(button.dataset.pageGo || 1));
    if (nextPage === state.page) return;
    if (isClientPagedView()) {
      state.page = nextPage;
      render();
    } else {
      loadPagedLibrary(nextPage, false);
    }
  });
  document.querySelectorAll("[data-refresh-library]").forEach(button => button.onclick = () => loadLibrary(true));
  document.querySelectorAll("[data-folder-page-step]").forEach(b => b.onclick = () => {
    const step = Number(b.dataset.folderPageStep || 0);
    state.folderPage = Math.max(1, (Number(state.folderPage) || 1) + step);
    loadPagedLibrary(state.page, false);
  });
}
function renderPlaylistNav() {
  const nav = $("playlistNav");
  if (!nav) return;
  nav.innerHTML = state.playlists.map(list => `<button class="nav-item playlist-nav-item ${state.view === `playlist:${list.id}` ? "active" : ""}" data-view="playlist:${list.id}">♪ <span>${escapeHtml(list.name)}</span><b>${list.trackIds.length}</b></button>`).join("");
  nav.querySelectorAll(".nav-item").forEach(button => {
    button.onclick = () => {
      setView(button.dataset.view);
      setMobileNavigation(false);
    };
  });
}
function setView(view) {
  if (state.searchTimer) {
    clearTimeout(state.searchTimer);
    state.searchTimer = null;
  }
  state.view = view || "all";
  state.selectedTrackRowKeys.clear();
  state.selectedGroupKeys.clear();
  state.folderRoot = "";
  state.folderPath = "";
  state.folderPage = 1;
  state.groupName = "";
  resetCreatorState();
  state.page = 1;
  state.pageItems = [];
  document.querySelectorAll(".nav-item").forEach(x => x.classList.toggle("active", x.dataset.view === state.view));
  if (isPagedLibraryView()) loadPagedLibrary(1, false);
  else render();
}
function setTrackSelection(rowKeys = []) {
  const rows = [...document.querySelectorAll("[data-track-row-key]")];
  const visibleKeys = new Set(rows.map(row => String(row.dataset.trackRowKey || "")).filter(Boolean));
  state.selectedTrackRowKeys = new Set((rowKeys || []).map(String).filter(key => visibleKeys.has(key)));
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
  Promise.resolve(loadPagedLibrary(1, false)).finally(() => requestAnimationFrame(resetLibraryScrollPosition));
}
async function resolveSelectedGroupTracks(groupKey = "") {
  const groups = selectedGroupDescriptors(groupKey);
  const resolved = await Promise.all(groups.map(group => group.type === "folder"
    ? fetchAllTracksForCurrentView({ view: "folders", root: group.root, folder: group.path })
    : isCreatorView() && currentCreatorName() && group.view === "albums"
      ? fetchAllTracksForCurrentView({ view: state.view, group: currentCreatorName(), album: group.name })
      : fetchAllTracksForCurrentView({ view: group.view, group: group.name })));
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
}
async function commitQueue(queue, currentId = "", options = {}) {
  const response = await fetch("api/playback/queue", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      queue,
      current_id: currentId,
      repeat: options.repeat ?? state.repeat,
      shuffle: options.shuffle ?? state.shuffle,
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) throw new Error(data.message || "播放队列保存失败");
  applyConfirmedQueue(queue, data.core);
  if (Number.isFinite(Number(data.revision))) state.userStateRevision = Number(data.revision);
  scheduleUserStateSave();
  return data.core || {};
}
async function addQueue(id) {
  const item = itemById(id);
  if (!item || state.queue.some(x => String(x.id) === String(id))) return;
  try {
    await commitQueue([...state.queue, item], state.queue[state.index]?.id || "");
    render();
  } catch (error) {
    alert(error.message || "播放队列保存失败");
  }
}
async function addQueueAndPlay(id) {
  const item = itemById(id);
  if (!item) return;
  const queue = state.queue.some(x => String(x.id) === String(id)) ? [...state.queue] : [...state.queue, item];
  if (isPlayingNow()) {
    try {
      await commitQueue(queue, state.queue[state.index]?.id || "");
      render();
    } catch (error) {
      alert(error.message || "播放队列保存失败");
    }
    return;
  }
  try {
    await commitQueue(queue, id);
  } catch (error) {
    alert(error.message || "播放队列保存失败");
    return;
  }
  loadCurrent();
  render();
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
async function resolveTracksByIds(ids = []) {
  const orderedIds = [];
  const seen = new Set();
  (ids || []).forEach(value => {
    const id = String(value || "");
    if (!id || seen.has(id)) return;
    seen.add(id);
    orderedIds.push(id);
  });
  const missing = orderedIds.filter(id => !state.itemCache.has(id));
  for (let index = 0; index < missing.length; index += 100) {
    const batch = missing.slice(index, index + 100);
    const response = await fetch(`api/library/items?ids=${encodeURIComponent(batch.join(","))}`);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "读取歌曲失败");
    cacheLibraryItems(Array.isArray(data.items) ? data.items : []);
  }
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
async function playFolder(root = state.folderRoot, path = state.folderPath) {
  const selectedRoot = String(root || "");
  const selectedPath = String(path || "");
  let tracks = selectedRoot === state.folderRoot && selectedPath === state.folderPath ? state.pageItems : [];
  if (!tracks.length && (selectedPath || selectedRoot)) {
    tracks = await fetchAllTracksForCurrentView({ view: "folders", folder: selectedPath, root: selectedRoot });
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
    const response = await fetch("api/transcode/warm", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ track_id: item.id, mode: "mp3" }),
    });
    const data = await response.json().catch(() => ({}));
    return Boolean(response.ok && data.ready);
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
    $("nowTitle").textContent = displayTrackTitle(item);
    $("nowArtist").textContent = `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)} · ${state.playTargetName}`;
    const localCover = coverUrl(item);
    $("nowCover").innerHTML = localCover ? `<img src="${localCover}" onerror="this.remove()">` : "♫";
    syncLyricsForCurrentTrack(item);
    updateMediaSessionMetadata(item);
    updateMediaSessionPlaybackState();
    updateFavoriteControls();
    pushToDevice(state.playTarget, item).then(() => setTimeout(refreshRemoteStatus, 300)).catch(() => {});
    updateNowMarquee();
    return;
  }
  const needsMp3 = shouldTranscodeToMp3(item);
  if (needsMp3 && !state.transcodeCacheReady) {
    state.transcodeCacheReady = await warmCurrentTrackCache(item);
    if (loadToken !== state.playbackLoadToken || String(currentItem()?.id || "") !== String(item.id || "")) return;
  }
  const useCache = needsMp3 && state.transcodeCacheReady;
  state.playSourceKind = needsMp3 && !useCache ? "stream" : "cache";
  const params = new URLSearchParams();
  if (needsMp3) {
    params.set("transcode", "mp3");
    if (useCache) params.set("cache", "1");
    else {
      const start = (item.cue_track ? Number(item.cue_start || 0) : 0) + Math.max(0, state.streamOffset);
      if (start > 0) params.set("start", String(start));
    }
  } else if (shouldTranscodeDsdToWav(item)) {
    params.set("transcode", "dsd_wav");
  } else if (item.cue_track) {
    params.set("transcode", "cue_flac");
  } else {
    params.set("transcode", "original");
  }
  audio.src = `${item.url}?${params.toString()}`;
  if (item.cue_track && !needsMp3) {
    state.playSourceKind = "cue_segment";
    state.pendingSeekTime = null;
  } else if (item.cue_start) state.pendingSeekTime = Number(item.cue_start) || null;
  $("elapsed").textContent = "0:00";
  $("duration").textContent = clock(seekDuration());
  $("seek").value = 0;
  audio.play().catch(() => {});
  $("nowTitle").textContent = displayTrackTitle(item);
  $("nowArtist").textContent = `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)}`;
  const localCover = coverUrl(item);
  $("nowCover").innerHTML = localCover ? `<img src="${localCover}" onerror="this.remove()">` : "♫";
  syncLyricsForCurrentTrack(item);
  updateMediaSessionMetadata(item);
  setPlayButton(true);
  updateMediaSessionPlaybackState();
  updateFavoriteControls();
  updateNowMarquee();
  syncState();
  refreshCurrentTranscodeStatus();
}
function currentSeconds() {
  if (isIncomingRendererSession()) {
    const transport = String(state.rendererSession.transport || "").toUpperCase();
    const base = Number(state.rendererSession.position || 0);
    const elapsed = transport === "PLAYING" && state.rendererSnapshotAt ? (Date.now() - state.rendererSnapshotAt) / 1000 : 0;
    const duration = Number(state.rendererSession.duration || 0);
    const seconds = Math.max(0, base + elapsed);
    return duration > 0 ? Math.min(duration, seconds) : seconds;
  }
  if (isRemoteTarget()) {
    const item = currentItem();
    const duration = seekDuration();
    const transport = (state.remoteStatus?.transport?.state || "").toUpperCase();
    const elapsed = transport === "PLAYING" && state.remoteSnapshotAt ? (Date.now() - state.remoteSnapshotAt) / 1000 : 0;
    const raw = Number(state.remoteBaseSeconds || state.remoteStatus?.position?.rel_seconds || 0) + elapsed;
    const seconds = item?.cue_track && !state.remoteCueSegment ? Math.max(0, raw - Number(item.cue_start || 0)) : raw;
    return duration > 0 ? Math.min(duration, seconds) : seconds;
  }
  const item = currentItem();
  const raw = state.playSourceKind === "stream" ? state.streamOffset + (audio.currentTime || 0) : (audio.currentTime || 0);
  if (item?.cue_track) {
    if (state.playSourceKind === "stream") return Math.max(0, raw);
    if (state.playSourceKind === "cue_segment") return Math.max(0, raw);
    return Math.max(0, raw - Number(item.cue_start || 0));
  }
  return raw;
}
function seekDuration() {
  if (isIncomingRendererSession()) return Number(state.rendererSession.duration || 0);
  const item = currentItem();
  if (item?.cue_track && item.duration) return Number(item.duration) || 0;
  if (item?.cue_track && isRemoteTarget()) {
    const remoteDuration = Number(state.remoteStatus?.position?.duration_seconds || 0);
    return remoteDuration > Number(item.cue_start || 0) ? remoteDuration - Number(item.cue_start || 0) : 0;
  }
  if (isRemoteTarget()) return state.remoteStatus?.position?.duration_seconds || 0;
  if (item?.duration) return Number(item.duration) || 0;
  return Number.isFinite(audio.duration) ? audio.duration : 0;
}
async function refreshCurrentTranscodeStatus() {
  const item = currentItem();
  if (!item || isRemoteTarget()) return;
  const trackId = String(item.id || "");
  if (!shouldTranscodeToMp3(item)) {
    state.transcodeCacheReady = false;
    return;
  }
  try {
    const response = await fetch(`api/transcode/status?track_id=${encodeURIComponent(item.id)}&mode=mp3`);
    const data = await response.json();
    if (!data || data.error) return;
    if (String(currentItem()?.id || "") !== trackId) return;
    const ready = Boolean(data.ready);
    if (ready && !state.transcodeCacheReady) {
      const wasPlaying = !audio.paused;
      const position = currentSeconds();
      state.transcodeCacheReady = true;
      state.streamOffset = 0;
      state.playSourceKind = "cache";
      state.pendingSeekTime = item.cue_track ? Number(item.cue_start || 0) + position : position;
      loadCurrent();
      if (wasPlaying) audio.play().catch(() => {});
      return;
    }
    state.transcodeCacheReady = ready;
  } catch (error) {
  }
}
function previewSeek(value) {
  const duration = seekDuration();
  if (!duration) return;
  $("elapsed").textContent = clock(Number(value) / 100 * duration);
  updateSeekRail(value);
}
function commitSeek(value = $("seek").value) {
  const duration = seekDuration();
  state.seeking = false;
  if (!duration) return;
  const seconds = Number(value) / 100 * duration;
  $("elapsed").textContent = clock(seconds);
  if (isIncomingRendererSession()) {
    controlIncomingRenderer("seek", seconds);
    return;
  }
  if (isRemoteTarget()) {
    const target = currentItem()?.cue_track && !state.remoteCueSegment ? Number(currentItem().cue_start || 0) + seconds : seconds;
    remoteControl("seek", target);
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
  state.playSourceKind = currentItem()?.cue_track ? "cue_segment" : "cache";
  audio.currentTime = currentItem()?.cue_track ? seconds : seconds;
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
    $("lyricsCover").textContent = "♫";
    updateFavoriteControls();
    return;
  }
  const localCover = coverUrl(item);
  $("lyricsBg").style.backgroundImage = localCover ? `url("${localCover}")` : "";
  $("lyricsCover").innerHTML = localCover ? `<img src="${localCover}" onerror="this.remove()">` : "♫";
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
async function loadLyricsForCurrentTrack(item = currentItem(), force = false) {
  updateLyricsMeta(item);
  if (!item) {
    state.lyricsRequestToken += 1;
    state.lyricsTrackId = "";
    state.lyricsLoadingTrackId = "";
    state.lyricsStatus = "idle";
    showLyricsMessage("请选择一首歌曲");
    return;
  }
  const trackId = String(item.id);
  if (!force && state.lyricsTrackId === trackId && ["loading", "loaded", "pending"].includes(state.lyricsStatus)) return;
  const requestToken = ++state.lyricsRequestToken;
  state.lyricsTrackId = trackId;
  state.lyricsLoadingTrackId = trackId;
  state.lyricsStatus = "loading";
  showLyricsMessage("正在匹配歌词...");
  try {
    const response = await fetch(`api/lyrics?track_id=${encodeURIComponent(trackId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "歌词加载失败");
    if (requestToken !== state.lyricsRequestToken || String(currentItem()?.id || "") !== trackId) return;
    if (data.pending) {
      state.lyricsStatus = "pending";
      showLyricsMessage("歌词正在后台补全，稍后重新打开即可查看。");
      return;
    }
    state.lyricsStatus = "loaded";
    renderLyrics(parseLyrics(data.lyrics || ""));
  } catch (error) {
    if (requestToken !== state.lyricsRequestToken || String(currentItem()?.id || "") !== trackId) return;
    state.lyricsStatus = "error";
    showLyricsMessage("歌词加载失败，请稍后重试。");
  } finally {
    if (requestToken === state.lyricsRequestToken) state.lyricsLoadingTrackId = "";
  }
}
function syncLyricsForCurrentTrack(item = currentItem()) {
  updateLyricsMeta(item);
  if ($("lyricsView").hidden) return;
  const trackId = String(item?.id || "");
  if (trackId !== state.lyricsTrackId) loadLyricsForCurrentTrack(item);
}
async function openLyrics() {
  const item = currentItem();
  $("lyricsView").hidden = false;
  updateLyricsMeta(item);
  const trackId = String(item?.id || "");
  const retry = state.lyricsTrackId === trackId && ["pending", "error"].includes(state.lyricsStatus);
  await loadLyricsForCurrentTrack(item, retry);
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
function cacheLibraryItems(items = []) {
  (items || []).forEach(item => {
    if (item && item.id) state.itemCache.set(String(item.id), item);
  });
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
async function loadPagedLibrary(page = 1, refresh = false) {
  const seq = ++state.libraryRequestSeq;
  fetch("api/access").then(response => response.json()).then(data => { state.accessProfile = data.profile || "lan"; updateModeButton(); }).catch(() => {});
  state.libraryLoading = true;
  state.page = Math.max(1, Number(page) || 1);
  if (refresh) {
    state.libraryStatus = { ...(state.libraryStatus || {}), scanning: true, scanned: 0, found: state.pageItems.length };
    render();
  }
  if (state.view === "folders" && !state.folderRoot && !state.folderPath) {
    const rootParams = new URLSearchParams();
    if (currentQueryText()) rootParams.set("search", currentQueryText());
    const response = await fetch(`api/library/roots${rootParams.toString() ? `?${rootParams.toString()}` : ""}`);
    const data = await response.json().catch(() => ({}));
    if (seq !== state.libraryRequestSeq) return;
    state.folderRootRows = [...(data.roots || [])].sort((a, b) => displayText(a.name || a.path || "").localeCompare(displayText(b.name || b.path || ""), "zh-CN", { numeric: true, sensitivity: "base" }) * sortDirectionFactor());
    if (state.folderRootRows.length === 1) {
      state.folderRoot = state.folderRootRows[0].root || state.folderRootRows[0].path || "";
      state.folderPath = "";
      return loadPagedLibrary(page, refresh);
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
    folderParams.set("offset", String(Math.max(0, (state.folderPage - 1) * state.folderPageSize)));
    const folderResponse = await fetch(`api/library/folders?${folderParams.toString()}`);
    const folderData = await folderResponse.json().catch(() => ({}));
    const response = await fetch(`api/library?${currentQueryParams().toString()}${refresh ? "&refresh=1" : ""}`);
    const data = await response.json().catch(() => ({}));
    if (seq !== state.libraryRequestSeq) return;
    state.folderRows = (folderData.folders || []).filter(row => String(row.root || "") === String(state.folderRoot || ""));
    state.folderTotal = Number(folderData.count || 0);
    state.pageItems = data.items || [];
    state.items = state.pageItems;
    state.pageTotal = Number(data.count || 0);
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
    params.set("offset", String(Math.max(0, (state.page - 1) * state.pageSize)));
    params.set("dir", state.sortDir || "asc");
    const response = await fetch(`api/library/groups?${params.toString()}`);
    const data = await response.json().catch(() => ({}));
    if (seq !== state.libraryRequestSeq) return;
    state.groupRows = data.groups || [];
    state.groupRows.forEach(group => {
      const name = displayText(group.name || "");
      if (!name || (!group.artist && !group.release_date && !group.image_url)) return;
      state.albumMetadata[name] = {
        artist: group.artist || "",
        release_date: group.release_date || "",
        image_url: group.image_url || "",
        source: group.metadata_source || "",
      };
    });
    state.pageItems = [];
    state.items = [];
    state.pageTotal = Number(data.count || 0);
  } else if (isPagedLibraryView()) {
    const params = currentQueryParams();
    if (refresh) params.set("refresh", "1");
    const response = await fetch(`api/library?${params.toString()}`);
    const data = await response.json().catch(() => ({}));
    if (seq !== state.libraryRequestSeq) return;
    state.pageItems = data.items || [];
    state.items = state.pageItems;
    state.pageTotal = Number(data.count || 0);
    cacheLibraryItems(state.pageItems);
  } else {
    const response = await fetch(`api/library?paged=1&limit=${state.pageSize}&offset=0${refresh ? "&refresh=1" : ""}`);
    const data = await response.json().catch(() => ({}));
    if (seq !== state.libraryRequestSeq) return;
    state.pageItems = data.items || [];
    state.items = state.pageItems;
    state.pageTotal = Number(data.count || 0);
    cacheLibraryItems(state.pageItems);
  }
  state.libraryLoading = false;
  state.libraryLoaded = state.pageItems.length;
  state.libraryTotal = state.pageTotal;
  hydrateReferencedItems();
  fetch(`api/library/status${refresh ? "?refresh=1" : ""}`)
    .then(response => response.json())
    .then(data => { state.libraryStatus = data; render(); })
    .catch(() => {});
  render();
}
async function fetchAllTracksForCurrentView(extra = {}) {
  const pageSize = Math.max(1, Math.min(500, state.pageSize || 120));
  const tracks = [];
  for (let offset = 0; ; offset += pageSize) {
    const params = currentQueryParams();
    params.set("limit", String(pageSize));
    params.set("offset", String(offset));
    Object.entries(extra || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value) !== "") params.set(key, String(value));
    });
    const response = await fetch(`api/library?${params.toString()}`);
    const data = await response.json().catch(() => ({}));
    const pageItems = data.items || [];
    cacheLibraryItems(pageItems);
    tracks.push(...pageItems);
    if (!pageItems.length || tracks.length >= Number(data.count || 0)) break;
  }
  return tracks;
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
  const missing = (ids || [])
    .map(String)
    .filter(id => id && !state.itemCache.has(id) && !state.hydratingIds.has(id) && !state.unresolvedItemIds.has(id));
  if (!missing.length) return;
  missing.forEach(id => state.hydratingIds.add(id));
  const requestedView = state.view;
  const batches = [];
  for (let index = 0; index < missing.length; index += 100) batches.push(missing.slice(index, index + 100));
  (async () => {
    let changed = false;
    let renderedFirstBatch = false;
    for (const batch of batches) {
      try {
        const response = await fetch(`api/library/items?ids=${encodeURIComponent(batch.join(","))}`);
        const data = await response.json().catch(() => ({}));
        const items = data.items || [];
        const found = new Set(items.map(item => String(item.id || "")));
        cacheLibraryItems(items);
        changed = changed || items.length > 0;
        batch.forEach(id => {
          state.hydratingIds.delete(id);
          if (!found.has(id)) state.unresolvedItemIds.add(id);
        });
        if (!renderedFirstBatch && changed && state.view === requestedView && isClientPagedView(requestedView)) {
          renderedFirstBatch = true;
          render();
        }
      } catch (error) {
        batch.forEach(id => state.hydratingIds.delete(id));
      }
    }
    if (changed && state.view === requestedView && isClientPagedView(requestedView)) render();
  })();
}
function deviceTargetRank(target) {
  if (target.id === "local") return 0;
  if (target.kind === "mpd") return 1;
  return 2;
}
function stableDeviceTargets(targets = []) {
  return [...targets].sort((left, right) => {
    const rank = deviceTargetRank(left) - deviceTargetRank(right);
    if (rank) return rank;
    return displayText(left.name || "").localeCompare(displayText(right.name || ""), "zh-Hans-CN");
  });
}
function renderDeviceTargets(targets, currentTarget) {
  const signature = JSON.stringify({
    currentTarget,
    targets: targets.map(target => ({
      id: target.id,
      name: displayText(target.name || ""),
      kind: target.kind || "",
      online: target.online !== false,
      detail: target.message || (target.caps ? dacCapsText(target.caps) : ""),
      selected: target.selected === true,
    })),
  });
  if (signature === state.deviceTargetsSignature) return;
  state.deviceTargetsSignature = signature;
  const current = targets.find(target => target.id === currentTarget || target.selected === true);
  const currentName = displayText(current?.name || (currentTarget === "local" ? "本机播放" : state.playTargetName || "播放设备"));
  $("deviceCurrentTarget").textContent = `当前：${currentName}`;
  const groups = new Map([
    ["browser", { title: "本机播放", targets: [] }],
    ["dac", { title: "USB DAC", targets: [] }],
    ["dlna", { title: "DLNA / UPnP", targets: [] }],
  ]);
  targets.forEach(target => {
    const key = target.id === "local" ? "browser" : (target.kind === "dlna_push" ? "dlna" : "dac");
    groups.get(key).targets.push(target);
  });
  const rows = targets.map(target => {
    const isCurrent = target.id === currentTarget || target.selected === true;
    const kind = target.kind === "dlna_push" ? "UPnP / DLNA" : (target.kind === "mpd" ? "本机 USB DAC" : "浏览器播放");
    const caps = target.caps ? dacCapsText(target.caps) : "";
    const detail = target.message || (caps || kind);
    const disabled = target.online === false ? " disabled" : "";
    return `<button class="device-row${isCurrent ? " is-current" : ""}" data-target="${escapeHtml(target.id)}" data-target-name="${escapeHtml(displayText(target.name || "播放设备"))}" aria-pressed="${isCurrent}"${disabled}><span class="device-row-radio">${isCurrent ? "✓" : ""}</span><span class="device-row-text"><strong>${escapeHtml(displayText(target.name || "播放设备"))}</strong><small>${escapeHtml(detail)}</small></span></button>`;
  });
  const rowById = new Map(targets.map((target, index) => [String(target.id), rows[index]]));
  const groupedRows = [...groups.values()]
    .filter(group => group.targets.length)
    .map(group => `<section class="device-section"><h3>${group.title}</h3>${group.targets.map(target => rowById.get(String(target.id))).join("")}</section>`)
    .join("");
  $("deviceList").innerHTML = groupedRows || `<p class="dialog-help">没有找到可用的播放目标。</p>`;
  document.querySelectorAll("[data-target]").forEach(button => {
    button.onclick = () => selectPlaybackTarget(button.dataset.target, button.dataset.targetName || "本机播放");
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
  if (state.deviceLoadInFlight) return;
  const list = $("deviceList");
  const targetRevision = state.deviceTargetRevision;
  if (!list.childElementCount) list.innerHTML = `<p class="dialog-help">正在搜索播放设备...</p>`;
  state.deviceLoadInFlight = true;
  try {
    const response = await fetch(`api/playback/targets${forceRefresh ? "?refresh=1" : ""}`);
    const data = await response.json().catch(() => ({}));
    if (targetRevision !== state.deviceTargetRevision || state.deviceSwitchInFlight) return;
    const targets = stableDeviceTargets(data.targets || []);
    const currentTarget = data.current_target || state.playTarget || "local";
    if (targetRevision > 0 && currentTarget !== state.playTarget) {
      if ($("deviceDialog").open) scheduleDeviceRefresh();
      return;
    }
    state.playTarget = currentTarget;
    if (data.current_target_name) state.playTargetName = data.current_target_name;
    state.devices = targets.filter(target => target.id !== "local");
    renderDeviceTargets(targets, currentTarget);
    const scanButton = $("scanDevices");
    scanButton.disabled = Boolean(data.refreshing);
    scanButton.textContent = data.refreshing ? "正在搜索..." : "重新搜索设备";
    $("deviceRefreshStatus").textContent = data.refreshing ? "正在刷新局域网设备..." : "设备会按类别显示";
    if (data.refreshing && $("deviceDialog").open) scheduleDeviceRefresh();
  } catch (error) {
    if (!state.deviceTargetsSignature) list.innerHTML = `<p class="dialog-help">设备列表读取失败，请重试。</p>`;
  } finally {
    state.deviceLoadInFlight = false;
  }
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
function versionAtLeast(actual, required) {
  const a = String(actual || "").split(".").map(Number);
  const b = String(required || "").split(".").map(Number);
  for (let index = 0; index < Math.max(a.length, b.length); index += 1) {
    const left = Number.isFinite(a[index]) ? a[index] : 0;
    const right = Number.isFinite(b[index]) ? b[index] : 0;
    if (left !== right) return left > right;
  }
  return true;
}
async function findTrimSharedFilePicker() {
  const sdk = await getTrimSdk();
  const candidates = [
    sdk,
    window.TrimApp,
    window.trimApp,
    window.trimapp,
    window.FnApp,
    window.fnApp,
    window.fnnas,
    window.__TRIM_APP__,
    window.__FNOS_APP__,
  ].filter(Boolean);
  for (const candidate of candidates) {
    if (typeof candidate.pickSharedFile === "function") return options => candidate.pickSharedFile(options);
    if (candidate.file && typeof candidate.file.pickSharedFile === "function") return options => candidate.file.pickSharedFile(options);
    if (candidate.default && typeof candidate.default.pickSharedFile === "function") return options => candidate.default.pickSharedFile(options);
  }
  return null;
}
function renderAuthorizedFolders(paths = [], message = "") {
  const list = $("authorizedFolderList");
  if (!list) return;
  if (paths.length) {
    list.innerHTML = paths.map(path => `<div class="authorized-folder-row"><span>${escapeHtml(path)}</span></div>`).join("");
    return;
  }
  list.innerHTML = message ? `<p class="dialog-help">${escapeHtml(message)}</p>` : "";
}
function normalizeAuthorizedPaths(result) {
  if (!result) return [];
  if (Array.isArray(result)) return result.map(String).map(x => x.trim()).filter(Boolean);
  if (Array.isArray(result.data)) return result.data.map(String).map(x => x.trim()).filter(Boolean);
  if (Array.isArray(result.paths)) return result.paths.map(String).map(x => x.trim()).filter(Boolean);
  if (result.data && Array.isArray(result.data.paths)) return result.data.paths.map(String).map(x => x.trim()).filter(Boolean);
  return [];
}
function mergeLibraryPathValues(extraPaths = []) {
  const seen = new Set();
  const merged = [];
  [...collectLibraryPaths(), ...extraPaths].forEach(path => {
    const value = String(path || "").trim();
    if (!value || seen.has(value)) return;
    seen.add(value);
    merged.push(value);
  });
  renderLibraryPathInputs(merged);
  return merged;
}
async function saveLibraryPathsFromDialog(statusText = "已保存。需要更新时请点击刷新音乐库。") {
  const paths = collectLibraryPaths();
  const serverPort = Number($("serverPortInput").value);
  if (!paths.length) {
    $("folderSaveStatus").textContent = "请输入音乐目录";
    return false;
  }
  if (!Number.isInteger(serverPort) || serverPort < 1024 || serverPort > 65535) {
    $("folderSaveStatus").textContent = "TCP 端口必须在 1024-65535 之间";
    return false;
  }
  const response = await fetch("api/config/library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ library_path: paths.join("\n"), server_port: serverPort }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    $("folderSaveStatus").textContent = data.message || "保存设置失败";
    return false;
  }
  state.libraryStatus = data.status || state.libraryStatus;
  $("folderSaveStatus").textContent = data.restart_required
    ? "端口已保存，请在飞牛应用中心停止并重新启动 fnAudio 后生效"
    : statusText;
  render();
  return true;
}
async function loadAuthorizedFolders() {
  const appVersion = fnAppVersion();
  if (appVersion && !versionAtLeast(appVersion, "1.34.0")) {
    renderAuthorizedFolders([], `当前飞牛 App 版本为 ${appVersion}，官方目录授权需要 1.34.0 或更高版本；当前可继续手动输入音乐目录`);
    return { ok: false, paths: [], unsupported: true };
  }
  try {
    const response = await fetch("api/fnos/shared-folders");
    const data = await response.json().catch(() => ({}));
    const fallback = data.token_source === "service"
      ? "fnAudio 后台服务没有拿到飞牛授权 token，请从飞牛应用中心停止并重新启动应用；如果仍失败，说明当前系统没有向第三方后台注入 token"
      : "当前没有读取到飞牛授权目录";
    renderAuthorizedFolders(data.paths || [], data.ok ? "" : (data.message || fallback));
    return data;
  } catch (error) {
    renderAuthorizedFolders([], "读取飞牛授权目录失败");
    return { ok: false, paths: [] };
  }
}
async function openFolderBrowser(path = "") {
  $("folderDialog").showModal();
  setSettingsTab("library");
  renderLibraryPathInputs(state.libraryStatus?.library_paths || [state.libraryStatus?.library_path || ""]);
  $("serverPortInput").value = state.libraryStatus?.server_port || 18080;
  $("folderSaveStatus").textContent = "";
  loadAuthorizedFolders();
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
}
function metadataStatusSummary(data = {}) {
  const jobs = data.jobs || {};
  const pending = Number(jobs.pending || 0) + Number(jobs.retry || 0) + Number(jobs.running || 0);
  const provider = data.spotify_configured ? "Spotify 已配置" : "Spotify 未配置，将使用其他数据源";
  const progress = pending ? `后台剩余 ${pending} 项` : "后台队列已完成";
  return `${provider} · ${progress} · 已缓存 ${Number(data.entities || 0)} 项分类资料、${Number(data.lyrics || 0)} 首歌词`;
}
async function loadMetadataStatus() {
  const statusNode = $("metadataStatusText");
  if (!statusNode) return null;
  try {
    const response = await fetch("api/metadata/status");
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error();
    $("metadataEnabledInput").checked = data.enabled !== false;
    $("spotifyClientIdInput").value = data.spotify_client_id || "";
    $("spotifyClientSecretInput").value = "";
    $("metadataGraceDaysInput").value = Number(data.orphan_grace_days ?? 7);
    statusNode.textContent = metadataStatusSummary(data);
    return data;
  } catch (error) {
    statusNode.textContent = "无法读取后台元数据状态";
    return null;
  }
}
async function saveMetadataSettings(options = {}) {
  const response = await fetch("api/config/metadata", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      enabled: $("metadataEnabledInput").checked,
      spotify_client_id: $("spotifyClientIdInput").value.trim(),
      spotify_client_secret: $("spotifyClientSecretInput").value.trim(),
      orphan_grace_days: Number($("metadataGraceDaysInput").value || 7),
      clear_spotify: Boolean(options.clearSpotify),
      refresh: Boolean(options.refresh),
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) throw new Error(data.message || "保存元数据设置失败");
  $("spotifyClientSecretInput").value = "";
  if (options.clearSpotify) $("spotifyClientIdInput").value = "";
  $("metadataStatusText").textContent = metadataStatusSummary(data.status || {});
  return data;
}
async function refreshMetadataLibrary() {
  const button = $("refreshMetadataBtn");
  button.disabled = true;
  try {
    await saveMetadataSettings({ refresh: true });
    $("metadataStatusText").textContent = "已加入后台补全队列，页面可以正常关闭或继续播放。";
  } catch (error) {
    $("metadataStatusText").textContent = error.message || "启动后台补全失败";
  } finally {
    button.disabled = false;
  }
}
async function clearSpotifyCredentials() {
  const button = $("clearSpotifyBtn");
  button.disabled = true;
  try {
    await saveMetadataSettings({ clearSpotify: true });
    $("metadataStatusText").textContent = "Spotify 凭据已清除，后台将继续使用网易云、QQ 音乐和 MusicBrainz。";
  } catch (error) {
    $("metadataStatusText").textContent = error.message || "清除 Spotify 凭据失败";
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
  try {
    const response = await fetch("api/dlna/diagnostics");
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.available) throw new Error(data.message || "DLNA 服务不可用");
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
    if (state.settingsTab === "metadata") {
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
async function authorizeSharedFolder() {
  const appVersion = fnAppVersion();
  if (appVersion && !versionAtLeast(appVersion, "1.34.0")) {
    $("folderSaveStatus").textContent = `当前飞牛 App ${appVersion} 不支持官方目录授权，请升级到 1.34.0 或更高版本；也可以继续手动输入目录`;
    return;
  }
  const sdk = await getTrimSdk();
  if (sdk?.ready) {
    try { await sdk.ready(); } catch (error) {}
  }
  if (sdk?.isStandaloneWeb && typeof sdk.openAppAuth === "function") {
    $("folderSaveStatus").textContent = "已打开飞牛授权页面，完成授权后请回到这里点击“同步授权目录”";
    try {
      await sdk.openAppAuth("pickSharedFile", {
        appName: "fnaudio",
        sidebarGroup: ["myFiles", "otherShare", "favorites"],
        redirectUri: window.location.href,
        state: `fnaudio-${Date.now()}`,
      }, {
        target: "_blank",
        features: "width=750,height=630",
      });
    } catch (error) {
      $("folderSaveStatus").textContent = "无法打开飞牛授权页面，请从飞牛应用入口打开后重试";
    }
    return;
  }
  const picker = await findTrimSharedFilePicker();
  if (!picker) {
    $("folderSaveStatus").textContent = "当前环境没有检测到飞牛官方目录授权选择器，可继续手动输入目录";
    return;
  }
  $("folderSaveStatus").textContent = "正在打开飞牛目录授权...";
  try {
    const result = await picker({
      title: "选择音乐目录",
      okText: "确认授权",
      sidebarGroup: ["myFiles", "otherShare", "favorites"],
    });
    const paths = normalizeAuthorizedPaths(result);
    if (paths.length) {
      mergeLibraryPathValues(paths);
      renderAuthorizedFolders(paths);
      await saveLibraryPathsFromDialog("已通过飞牛授权添加音乐目录。需要更新时请点击刷新音乐库。");
      return;
    }
    await syncAuthorizedFolders();
  } catch (error) {
    $("folderSaveStatus").textContent = "目录授权未完成或被取消";
  }
}
async function consumeAppAuthCallback() {
  const sdk = await getTrimSdk();
  if (!sdk || typeof sdk.parseAppAuthCallback !== "function") return;
  let result = null;
  try {
    result = sdk.parseAppAuthCallback(window.location.href);
  } catch (error) {
    return;
  }
  const paths = normalizeAuthorizedPaths(result?.path || result?.data);
  if (!paths.length || result?.status === "error") return;
  if (!$("folderDialog").open) $("folderDialog").showModal();
  mergeLibraryPathValues(paths);
  renderAuthorizedFolders(paths);
  $("serverPortInput").value = state.libraryStatus?.server_port || 18080;
  $("folderSaveStatus").textContent = "已收到飞牛授权目录，正在保存...";
  await saveLibraryPathsFromDialog("已通过飞牛授权添加音乐目录。需要更新时请点击刷新音乐库。");
  const cleanUrl = window.location.origin + window.location.pathname + window.location.hash;
  window.history.replaceState({}, document.title, cleanUrl);
}
async function syncAuthorizedFolders() {
  const appVersion = fnAppVersion();
  if (appVersion && !versionAtLeast(appVersion, "1.34.0")) {
    $("folderSaveStatus").textContent = `当前飞牛 App ${appVersion} 不支持官方目录授权，请升级到 1.34.0 或更高版本`;
    return;
  }
  const button = $("syncAuthorizedFoldersBtn");
  if (button) button.disabled = true;
  $("folderSaveStatus").textContent = "正在同步飞牛授权目录...";
  try {
    const response = await fetch("api/fnos/shared-folders/sync", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      $("folderSaveStatus").textContent = /token/i.test(data.message || "")
        ? "当前 fnOS 没有向应用后端提供授权 token，请点击“授权目录”选择目录，fnAudio 会直接把返回的目录写入设置"
        : (data.message || "同步飞牛授权目录失败");
      await loadAuthorizedFolders();
      return;
    }
    state.libraryStatus = data.status || state.libraryStatus;
    const paths = normalizeAuthorizedPaths(data.authorized_paths || data.paths || []);
    if (paths.length) {
      mergeLibraryPathValues(paths);
      await saveLibraryPathsFromDialog("已同步飞牛授权目录。需要更新时请点击刷新音乐库。");
    } else {
      renderLibraryPathInputs(data.paths || state.libraryStatus?.library_paths || []);
    }
    renderAuthorizedFolders(paths.length ? paths : (data.authorized_paths || data.paths || []));
    $("folderSaveStatus").textContent = data.message || "已同步飞牛授权目录。需要更新时请点击刷新音乐库。";
    render();
  } catch (error) {
    $("folderSaveStatus").textContent = "同步失败，请确认应用服务正在运行";
  } finally {
    if (button) button.disabled = false;
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
    return `<button class="playlist-choice" data-add-to-list="${list.id}" ${exists ? "disabled" : ""}><span>${escapeHtml(list.name)}</span><small>${exists ? "已加入" : `${list.trackIds.length} 首`}</small></button>`;
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
  if ($("trackActionDialog").open) $("trackActionDialog").close();
}
function closeTrackContextMenu() {
  const menu = $("trackContextMenu");
  if (!menu) return;
  menu.hidden = true;
  menu.innerHTML = "";
}
function groupActionButton(label, action) {
  return `<button class="track-action-choice" data-group-action="${action}">${label}</button>`;
}
function groupActionButtons(groupKey) {
  const selected = selectedGroupDescriptors(groupKey);
  const multiple = selected.length > 1;
  return [
    groupActionButton("播放", "play"),
    groupActionButton("加入当前队列", "queue"),
    groupActionButton("加入播放列表", "playlist"),
    groupActionButton("插播所选项目", "insert"),
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
    actionButton("打开包含的文件夹", "open-folder", false, multiple),
    actionButton("分享外部链接", "share", false, multiple),
  ];
  if (state.view === "queue") actions.push(actionButton("从当前队列移除", "remove-queue", true));
  if (state.view === "favorites") actions.push(actionButton("从收藏移除", "remove-favorite", true));
  if (isPlaylistView()) actions.push(actionButton("从此播放列表移除", "remove-playlist", true));
  return actions;
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
async function resolveTrackLocation(trackId) {
  const response = await fetch(`api/library/location?id=${encodeURIComponent(String(trackId || ""))}`, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok || !data.path) throw new Error(data.message || "无法获取歌曲文件路径");
  return data;
}
async function openContainingFolder(trackId) {
  try {
    const location = await resolveTrackLocation(trackId);
    const folder = String(location.folder || "");
    if (!folder) throw new Error("无法获取所在文件夹");
    const sdk = await getTrimSdk();
    if (!sdk || typeof sdk.openFileManager !== "function") throw new Error("unsupported");
    if (typeof sdk.ready === "function") await sdk.ready();
    if (sdk.isStandaloneWeb) return alert("请从飞牛桌面或飞牛 App 的 fnAudio 应用入口打开，才能跳转到文件管理");
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
function openTrackContextMenu(trackId, x, y) {
  const item = itemById(trackId);
  const menu = $("trackContextMenu");
  if (!item || !menu) return;
  state.actionTrackId = String(trackId);
  menu.innerHTML = `<strong class="track-context-title">${escapeHtml(displayTrackTitle(item) || "歌曲操作")}</strong><div class="track-context-actions">${trackActionButtons(trackId).join("")}</div>`;
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
  else if (action === "queue" || action === "queue-play") addSelectedToQueue(selected);
  else if (action === "favorite") toggleSelectedFavorites(selected);
  else if (action === "playlist") openPlaylistDialogForTracks(selected);
  else if (action === "insert") insertSelectedTracks(selected);
  else if (action === "info") showTrackInformation(trackId);
  else if (action === "open-folder") openContainingFolder(trackId);
  else if (action === "share") shareTrack(trackId);
  else if (action === "remove-queue") removeTrackFromQueue(trackId);
  else if (action === "remove-favorite") removeFavorite(trackId);
  else if (action === "remove-playlist") removeTrackFromCurrentPlaylist(trackId);
}
function closeMobileMoreDialog() {
  if ($("mobileMoreDialog").open) $("mobileMoreDialog").close();
}
function openMobileMoreDialog() {
  const item = currentItem();
  const actions = [
    actionButton("选择播放设备", "device"),
    actionButton(state.shuffle ? "关闭随机播放" : "开启随机播放", "shuffle"),
    actionButton(state.repeat === "all" ? "关闭循环播放" : "开启循环播放", "repeat"),
  ];
  if (item) actions.push(actionButton(isFavorite(item.id) ? "取消收藏当前歌曲" : "收藏当前歌曲", "favorite-current"));
  $("mobileMoreList").innerHTML = actions.join("");
  $("mobileMoreList").querySelectorAll("[data-track-action]").forEach(button => button.onclick = () => runMobileMoreAction(button.dataset.trackAction));
  $("mobileMoreDialog").showModal();
}
function runMobileMoreAction(action) {
  closeMobileMoreDialog();
  if (action === "device") {
    $("deviceDialog").showModal();
    loadDevices();
  } else if (action === "shuffle") {
    toggleShuffle();
  } else if (action === "repeat") {
    toggleRepeat();
  } else if (action === "favorite-current") {
    toggleCurrentFavorite();
  }
}
function updateRepeatShuffleButtons() {
  $("repeatBtn").classList.toggle("active-control", state.repeat === "all");
  $("repeatBtn").title = state.repeat === "all" ? "列表循环" : "循环关闭";
  $("shuffleBtn").classList.toggle("active-control", state.shuffle);
  $("shuffleBtn").title = state.shuffle ? "关闭随机播放" : "随机播放";
}
async function toggleRepeat() {
  const data = await coreControl("repeat");
  if (data?.core) state.repeat = data.core.repeat || state.repeat;
  else state.repeat = state.repeat === "all" ? "off" : "all";
  updateRepeatShuffleButtons();
  syncState();
}
async function toggleShuffle() {
  const data = await coreControl("shuffle");
  if (data?.core && typeof data.core.shuffle === "boolean") state.shuffle = data.core.shuffle;
  else state.shuffle = !state.shuffle;
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
  if (state.view === `playlist:${playlistId}`) state.view = "all";
  render();
}
async function refreshLibraryStatus() {
  try {
    const wasScanning = Boolean(state.libraryStatus?.scanning);
    const response = await fetch("api/library/status");
    const data = await response.json();
    state.libraryStatus = data;
    if (wasScanning && !data.scanning) {
      await loadLibrary(false);
      return;
    }
    if (data.scanning) {
      state.libraryLoading = false;
    }
    render();
  } catch (error) {
  }
}
function toggleFavorite(trackId) {
  const id = String(trackId);
  if (!itemById(id)) return;
  if (isFavorite(id)) state.favorites = state.favorites.filter(x => x !== id);
  else state.favorites.unshift(id);
  saveFavorites();
  updateFavoriteControls();
  render();
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
  updateFavoriteControls();
  render();
}
function removeFavorite(trackId) {
  state.favorites = state.favorites.filter(x => x !== String(trackId));
  saveFavorites();
  updateFavoriteControls();
  render();
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
  if (previousTarget !== nextTarget) {
    if (previousTarget !== "local") {
      remoteControl("stop", null, true).catch(() => {});
    } else {
      stopLocalAudio();
    }
  }
  state.deviceSwitchInFlight = true;
  state.deviceTargetRevision += 1;
  state.playTarget = nextTarget;
  state.playTargetName = name || "本机播放";
  state.deviceTargetsSignature = "";
  markCurrentDeviceTarget(nextTarget, true);
  updateDeviceLabel();
  try {
    const response = await fetch("api/playback/target", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({target_id: nextTarget})
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.message || "播放设备切换失败");
    if (Number.isFinite(Number(data.revision))) state.userStateRevision = Number(data.revision);
  } catch (error) {
    state.playTarget = previousTarget;
    state.deviceTargetRevision += 1;
    state.deviceTargetsSignature = "";
    markCurrentDeviceTarget(previousTarget);
    updateDeviceLabel();
    alert(error.message || "播放设备切换失败");
    return;
  } finally {
    state.deviceSwitchInFlight = false;
    markCurrentDeviceTarget(state.playTarget);
  }
  state.remoteStatus = null;
  state.remoteCueSegment = false;
  updateDeviceLabel();
  render();
  scheduleUserStateSave();
  if ($("deviceDialog").open) loadDevices().catch(() => {});
}
async function pushToDevice(deviceId, item = currentItem()) {
  if (!item) return alert("请先选择一首歌曲");
  const response = await fetch("api/playback/load", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({target_id:deviceId, track_id:item.id}) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    alert(data.message || data.error || "播放设备接收失败");
    return;
  }
  state.remoteCueSegment = Boolean(data.cue_segment || (item?.cue_track && !isDacTarget(deviceId)));
  if (state.remoteCueSegment) {
    state.remoteStatus = {
      ...(state.remoteStatus || {}),
      transport: { ...(state.remoteStatus?.transport || {}), state: "PLAYING" },
      position: { ...(state.remoteStatus?.position || {}), rel_seconds: 0, duration_seconds: Number(item.duration || 0) || state.remoteStatus?.position?.duration_seconds || 0 },
    };
    state.remoteBaseSeconds = 0;
    state.remoteSnapshotAt = Date.now();
    updateRemoteUi();
  }
  state.dacStrategy = data.strategy || null;
  if (isDacTarget(deviceId) && item) {
    $("nowArtist").textContent = `${displayText(item.artist)} · ${item.format} · ${playbackBadge(item)} · ${state.playTargetName}`;
    updateNowMarquee();
  }
  updateDeviceLabel();
  $("deviceDialog").close();
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
    if (isPagedLibraryView()) loadPagedLibrary(1, false);
    else render();
  }, 240);
}
$("searchInput").oninput = event => handleSearchInput(event.currentTarget);
const mobileSearchInput = $("mobileSearchInput");
function setMobileSearchFocusState(active) {
  const enabled = Boolean(active) && window.matchMedia("(max-width: 760px)").matches;
  document.body.classList.toggle("mobile-search-active", enabled);
  requestAnimationFrame(updateMobilePagerVisibility);
}
if (mobileSearchInput) {
  mobileSearchInput.oninput = event => handleSearchInput(event.currentTarget);
  mobileSearchInput.addEventListener("focus", () => setMobileSearchFocusState(true));
  mobileSearchInput.addEventListener("blur", () => setMobileSearchFocusState(false));
}
$("playAllBtn").onclick = playAll;
$("mobileColumnsBtn").onclick = openColumnsDialog;
$("closeColumnsDialog").onclick = () => $("columnsDialog").close();
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
  if (!document.hidden) clearTransientListSelection();
});
$("libraryScroll").addEventListener("scroll", closeTrackContextMenu, { passive: true });
$("trackList").addEventListener("scroll", updateMobilePagerVisibility, { passive: true });
$("refreshBtn").onclick = () => loadLibrary(true);
$("modeBtn").onclick = () => {
  state.mp3Transcode = !state.mp3Transcode;
  localStorage.setItem("fnaudio.mp3Transcode", state.mp3Transcode ? "1" : "0");
  updateModeButton();
  if (currentItem() && !isRemoteTarget()) loadCurrent();
};
$("folderBtn").onclick = () => openFolderBrowser();
$("deviceBtn").onclick = () => { $("deviceDialog").showModal(); loadDevices(); };
function closeLyrics() {
  $("lyricsView").hidden = true;
}
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
$("closeMobileMoreDialog").onclick = closeMobileMoreDialog;
$("mobileMoreBtn").onclick = openMobileMoreDialog;
$("favoriteCurrentBtn").onclick = toggleCurrentFavorite;
$("lyricsFavoriteBtn").onclick = toggleCurrentFavorite;
$("savePlaylistBtn").onclick = savePlaylistFromDialog;
$("playlistNameInput").onkeydown = event => { if (event.key === "Enter") savePlaylistFromDialog(); };
$("chooseFolderBtn").onclick = chooseCurrentFolder;
$("addLibraryPathBtn").onclick = () => addLibraryPathInput();
$("authorizeFolderBtn").onclick = authorizeSharedFolder;
$("syncAuthorizedFoldersBtn").onclick = syncAuthorizedFolders;
$("refreshMetadataBtn").onclick = refreshMetadataLibrary;
$("clearSpotifyBtn").onclick = clearSpotifyCredentials;
$("scanDevices").onclick = () => loadDevices(true);
$("playBtn").onclick = () => {
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
  if (!audio.src && state.queue.length) loadCurrent(); else if (audio.paused) audio.play(); else audio.pause();
};
$("prevBtn").onclick = () => playPreviousTrack();
$("stopBtn").onclick = stopPlayback;
$("nextBtn").onclick = () => playNextTrack();
$("repeatBtn").onclick = toggleRepeat;
$("shuffleBtn").onclick = toggleShuffle;
$("volume").oninput = e => audio.volume = Number(e.target.value);
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
  if (currentItem()?.is_dsd) {
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
  if (item?.cue_track && duration > 0 && currentSeconds() >= Math.max(0, duration - 0.25)) {
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
  $("elapsed").textContent = clock(currentSeconds());
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
  if (item?.cue_track && state.playSourceKind === "cue_segment" && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = audio.duration;
  } else if (item?.cue_track && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = Math.max(0, audio.duration - Number(item.cue_start || 0));
  } else if (item && canUseNativeDuration && !item.duration && Number.isFinite(audio.duration) && audio.duration > 0) {
    item.duration = audio.duration;
  }
  if (state.pendingSeekTime != null && Number.isFinite(audio.duration) && audio.duration > 0) {
    const target = Math.min(Math.max(0, state.pendingSeekTime), Math.max(0, audio.duration - 0.1));
    state.pendingSeekTime = null;
    try { audio.currentTime = target; } catch (error) {}
  }
  $("duration").textContent = clock(seekDuration());
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
  const row = event.target.closest(".track");
  if (!row || event.target.closest("button")) return;
  const play = row.querySelector("[data-play]");
  if (play) playById(play.dataset.play);
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !$("lyricsView").hidden && !document.querySelector("dialog[open]")) closeLyrics();
});
setupMediaSession();
loadLibrary();
loadServerUserState();
setTimeout(() => consumeAppAuthCallback(), 300);
setInterval(() => refreshLibraryStatus(), 30000);
setInterval(() => { if (state.libraryStatus?.scanning) refreshLibraryStatus(); }, 1000);
setInterval(() => { refreshCurrentTranscodeStatus(); }, 1200);
setInterval(() => { if (isRemoteTarget()) refreshRemoteStatus(); }, 1500);
setInterval(refreshRendererSession, 1500);
setInterval(() => { if (isRemoteTarget()) updateRemoteUi(); }, 250);
setInterval(refreshServerUserState, 3000);
window.addEventListener("pagehide", stopRemoteOnUnload);
window.addEventListener("beforeunload", stopRemoteOnUnload);
window.addEventListener("resize", updateNowMarquee);
window.addEventListener("resize", updateMobilePagerVisibility, { passive: true });
updateDeviceLabel();
updateModeButton();
updateNowMarquee();
refreshRendererSession();


