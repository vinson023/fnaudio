/* Pure track-table layout and header markup helpers. */
(function (global) {
  const MAX_COLUMNS = 32;
  function safeColumns(columns) {
    return Array.isArray(columns)
      ? columns.filter(key => typeof key === "string").slice(0, MAX_COLUMNS)
      : [];
  }
  function gridTemplate(columns, widths, definitions) {
    return [...safeColumns(columns).map(key => `${safeWidth(key, widths?.[key], definitions?.[key]?.width || 120)}px`), "minmax(0,1fr)"].join(" ");
  }

  function widthLimits(key) {
    return {
      title: [260, 620], track_no: [64, 84], artist: [120, 280], album: [150, 340],
      format: [76, 110], duration: [72, 96], size: [88, 120], quality: [120, 170],
      added: [110, 150], composer: [120, 260], genre: [110, 200],
    }[key] || [80, 260];
  }

  function safeWidth(key, value, fallback) {
    const numeric = Number(value);
    const preferred = Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
    const limits = widthLimits(key);
    return Math.min(limits[1], Math.max(limits[0], preferred));
  }

  function sortIndicator(sortKey, currentSort, sortDir) {
    return currentSort === sortKey ? `<span class="track-sort-indicator">${sortDir === "asc" ? "&#9650;" : "&#9660;"}</span>` : "";
  }

  function tableHeadPresentation({ mode = "tracks", columns = [], widths = {}, definitions = {}, currentSort = "title", sortDir = "asc", groupSortKey = "title", sortableSortKeys = [] } = {}) {
    if (mode === "group") return {
      template: "minmax(280px,1fr)",
      markup: `<div class="album-header-cell"><button class="track-head-button" type="button" data-track-sort="${groupSortKey}">标题${sortIndicator(groupSortKey, currentSort, sortDir)}</button></div>`,
    };
    if (mode === "album-collection") return {
      template: "minmax(280px,1fr) minmax(160px,240px) 130px",
      markup: `<div class="album-header-cell"><button class="track-head-button" type="button" data-track-sort="album">标题${sortIndicator("album", currentSort, sortDir)}</button></div><div class="album-header-cell">歌手</div><div class="album-header-cell">发行日期</div>`,
    };
    const sortable = new Set(safeColumns(sortableSortKeys));
    const markup = safeColumns(columns).map(key => {
      const definition = definitions[key] || {};
      const sortKey = definition.sort;
      const control = sortKey && sortable.has(sortKey)
        ? `<button class="track-head-button" type="button" data-track-sort="${sortKey}">${definition.label || key}${sortIndicator(sortKey, currentSort, sortDir)}</button>`
        : `<span class="track-head-label">${definition.label || key}</span>`;
      return `<div class="track-header-cell" data-track-column="${key}">${control}<span class="column-resize-handle" data-column-resize="${key}" title="拖动调整列宽" aria-hidden="true"></span></div>`;
    }).join("");
    return { template: gridTemplate(columns, widths, definitions), markup: markup + `<button class="table-head-more" type="button" data-open-columns title="列显示" aria-label="列显示"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg></button>` };
  }

  global.fnAudioTrackTablePresentation = { gridTemplate, tableHeadPresentation, widthLimits, safeWidth };
})(globalThis);
