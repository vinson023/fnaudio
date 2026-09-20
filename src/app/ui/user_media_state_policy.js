(function (root) {
  "use strict";

  const LIMITS = { favorites: 50000, playlists: 1000, playlistTracks: 10000, length: 100000 };
  const MAX_TEXT = 512;
  const safeLength = value => {
    try { return Math.max(0, Math.min(LIMITS.length, Number(value.length) || 0)); } catch (error) { return 0; }
  };

  function safeText(value) {
    if (typeof value === "string") return value.slice(0, MAX_TEXT);
    if (typeof value !== "number" || !Number.isFinite(value)) return "";
    try { return String(value).slice(0, MAX_TEXT); } catch (_) { return ""; }
  }

  function safeValue(source, key) {
    try { return source && typeof source === "object" ? source[key] : undefined; } catch (_) { return undefined; }
  }

  function normalizeIds(values, maximum) {
    const result = [];
    const seen = new Set();
    if (!Array.isArray(values)) return result;
    for (let index = 0; index < Math.min(safeLength(values), maximum); index += 1) {
      let id;
      try { id = safeText(values[index]); } catch (_) { continue; }
      if (!id || seen.has(id)) continue;
      seen.add(id);
      result.push(id);
    }
    return result;
  }

  function normalize(source = {}) {
    const favorites = [];
    const favoriteSet = new Set();
    if (Array.isArray(source.favorites)) {
      for (let index = 0; index < Math.min(safeLength(source.favorites), LIMITS.favorites); index += 1) {
        let value;
        try { value = source.favorites[index]; } catch (error) { break; }
        const id = safeText(value);
        if (id && !favoriteSet.has(id)) { favoriteSet.add(id); favorites.push(id); }
      }
    }
    const playlists = [];
    if (Array.isArray(source.playlists)) {
      for (let index = 0; index < Math.min(source.playlists.length, LIMITS.playlists); index += 1) {
        let item;
        try { item = source.playlists[index]; } catch (_) { break; }
        const itemId = safeText(safeValue(item, "id"));
        const itemName = safeText(safeValue(item, "name"));
        if (!itemId || !itemName) continue;
        const trackIds = [];
        const trackSet = new Set();
        const rawTrackIds = safeValue(item, "trackIds");
        if (Array.isArray(rawTrackIds)) {
          for (let trackIndex = 0; trackIndex < Math.min(safeLength(rawTrackIds), LIMITS.playlistTracks); trackIndex += 1) {
            let value;
            try { value = rawTrackIds[trackIndex]; } catch (error) { break; }
            const id = safeText(value);
            if (id && !trackSet.has(id)) { trackSet.add(id); trackIds.push(id); }
          }
        }
        playlists.push({ id: itemId, name: itemName, trackIds });
      }
    }
    return { favorites, playlists };
  }

  function changes(baseSource, currentSource) {
    const base = normalize(baseSource);
    const current = normalize(currentSource);
    const baseFavorites = new Set(base.favorites);
    const currentFavorites = new Set(current.favorites);
    const basePlaylists = new Map(base.playlists.map(item => [item.id, item]));
    const currentPlaylists = new Map(current.playlists.map(item => [item.id, item]));
    return {
      favorites_add: current.favorites.filter(id => !baseFavorites.has(id)),
      favorites_remove: base.favorites.filter(id => !currentFavorites.has(id)),
      playlist_upserts: current.playlists.filter(item => JSON.stringify(item) !== JSON.stringify(basePlaylists.get(item.id) || null)),
      playlist_delete: base.playlists.filter(item => !currentPlaylists.has(item.id)).map(item => item.id),
    };
  }

  function apply(source, delta = {}) {
    const result = normalize(source);
    const removeFavorites = new Set(normalizeIds(delta && delta.favorites_remove, LIMITS.favorites));
    result.favorites = result.favorites.filter(id => !removeFavorites.has(id));
    normalizeIds(delta && delta.favorites_add, LIMITS.favorites).forEach(id => {
      if (!result.favorites.includes(id) && result.favorites.length < LIMITS.favorites) result.favorites.push(id);
    });
    const deleted = new Set(normalizeIds(delta && delta.playlist_delete, LIMITS.playlists));
    const playlists = new Map(result.playlists.filter(item => !deleted.has(item.id)).map(item => [item.id, item]));
    (Array.isArray(delta.playlist_upserts) ? delta.playlist_upserts : []).forEach(item => {
      const normalized = normalize({ playlists: [item] }).playlists[0];
      if (normalized) playlists.set(normalized.id, normalized);
    });
    result.playlists = [...playlists.values()].slice(0, LIMITS.playlists);
    return result;
  }

  root.fnAudioUserMediaStatePolicy = { normalize, changes, apply, limits: Object.freeze({ ...LIMITS }) };
})(globalThis);
