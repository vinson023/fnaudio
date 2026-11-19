(function (root) {
  "use strict";
  const ALL = Object.freeze([
    ["title", "按标题"], ["added", "按加入时间"], ["artist", "按艺术家"],
    ["album", "按专辑"], ["format", "按格式"], ["track_no", "按歌曲序号"],
  ]);
  const GROUPS = Object.freeze({
    // The album list's three headers are all sortable, so all three have to be
    // registered here: `applyTrackSort` refuses a key this list does not name,
    // and the header's own button would then be a dead control.
    albums: [["album", "按专辑名"], ["artist", "按歌手"], ["release_date", "按发行日期"]],
    artists: [["artist", "按歌手"]],
    composers: [["composer", "按作曲者"]], genres: [["genre", "按类型名称"]],
  });
  function options(view, flags = {}) {
    const group = GROUPS[view];
    if (flags.creatorAllTracks && flags.creatorView) return ALL.slice();
    if (flags.creatorAlbum && flags.creatorView) return [["album", "按专辑名"], ["release_date", "按发行日期"]];
    if (flags.albumDetail || flags.playlistView || !group || flags.hasGroupName) return ALL.slice();
    return group.map(item => item.slice());
  }
  function defaultKey(view, flags = {}) {
    return flags.albumDetail || (view === "folders" && (flags.folderRoot || flags.folderPath))
      ? "track_no" : options(view, flags)[0][0];
  }
  root.fnAudioLibrarySortOptionsPolicy = Object.freeze({ options, defaultKey });
})(globalThis);
