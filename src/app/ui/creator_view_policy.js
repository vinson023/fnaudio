(function (root) {
  "use strict";

  const CREATOR_VIEWS = new Set(["artists", "composers"]);
  const MAX_TRACK_TOTAL = 1000000000;
  const MAX_CREATOR_NAME = 512;

  function boundedCreatorName(value) {
    return typeof value === "string" && value.length <= MAX_CREATOR_NAME ? value.trim() : "";
  }

  function boundedTrackTotal(value) {
    if (typeof value === "boolean" || (typeof value !== "number" && typeof value !== "string")) return 0;
    let number;
    try { number = Number(value); } catch (_) { return 0; }
    return Number.isFinite(number) && number >= 0 && Number.isInteger(number)
      ? Math.min(MAX_TRACK_TOTAL, number)
      : 0;
  }

  function isCreatorView(view) {
    return CREATOR_VIEWS.has(view);
  }

  function creatorPart(state, part, fallback) {
    if (!state || typeof state !== "object") return fallback;
    try {
      const composer = state.view === "composers";
      const key = composer ? `composer${part}` : `artist${part}`;
      return Object.prototype.hasOwnProperty.call(state, key) ? state[key] : fallback;
    } catch (_) {
      return fallback;
    }
  }

  function currentCreatorName(state) { return boundedCreatorName(creatorPart(state, "Name", "")); }
  function currentCreatorAllTracks(state) { return creatorPart(state, "AllTracks", false) === true; }
  function currentCreatorTrackTotal(state) { return boundedTrackTotal(creatorPart(state, "TrackTotal", 0)); }
  function currentCreatorLabel(state) { return state && state.view === "composers" ? "作曲者" : "歌手"; }

  function setCurrentCreator(state, name, trackTotal) {
    if (!state || typeof state !== "object") return state;
    const composer = state.view === "composers";
    const prefix = composer ? "composer" : "artist";
    state[`${prefix}Name`] = boundedCreatorName(name);
    state[`${prefix}TrackTotal`] = boundedTrackTotal(trackTotal);
    state[`${prefix}AllTracks`] = false;
    return state;
  }

  function setCurrentCreatorAllTracks(state, enabled) {
    if (!state || typeof state !== "object") return state;
    const prefix = state.view === "composers" ? "composer" : "artist";
    state[`${prefix}AllTracks`] = enabled === true;
    return state;
  }

  function clearCurrentCreator(state) {
    if (!state || typeof state !== "object") return state;
    const prefix = state.view === "composers" ? "composer" : "artist";
    state[`${prefix}Name`] = "";
    state[`${prefix}TrackTotal`] = 0;
    state[`${prefix}AllTracks`] = false;
    return state;
  }

  function resetCreatorState(state) {
    if (!state || typeof state !== "object") return state;
    state.artistName = "";
    state.artistAllTracks = false;
    state.artistTrackTotal = 0;
    state.composerName = "";
    state.composerAllTracks = false;
    state.composerTrackTotal = 0;
    return state;
  }

  function isCreatorAllTracksView(state) {
    return isCreatorView(state && state.view) && Boolean(currentCreatorName(state)) && Boolean(currentCreatorAllTracks(state));
  }

  function isCreatorAlbumView(state) {
    return isCreatorView(state && state.view) && Boolean(currentCreatorName(state)) && !state.groupName && !currentCreatorAllTracks(state);
  }

  function isAlbumCollectionView(state) {
    return Boolean(state) && ((state.view === "albums" && !state.groupName) || isCreatorAlbumView(state));
  }

  function isAlbumDetailView(state) {
    return Boolean(state && state.groupName) && (state.view === "albums" || (isCreatorView(state.view) && currentCreatorName(state)));
  }

  function isAlbumSurfaceView(state) {
    return isAlbumCollectionView(state) || isAlbumDetailView(state);
  }

  root.fnAudioCreatorViewPolicy = {
    isCreatorView,
    currentCreatorName,
    currentCreatorAllTracks,
    currentCreatorTrackTotal,
    currentCreatorLabel,
    setCurrentCreator,
    setCurrentCreatorAllTracks,
    clearCurrentCreator,
    resetCreatorState,
    isCreatorAllTracksView,
    isCreatorAlbumView,
    isAlbumCollectionView,
    isAlbumDetailView,
    isAlbumSurfaceView,
    boundedCreatorName,
    boundedTrackTotal,
  };
})(globalThis);
