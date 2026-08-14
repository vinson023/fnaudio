(() => {
  const labels = {
    all: "全部音乐", dsd: "DSD 音乐", queue: "当前队列", folders: "文件夹",
    albums: "专辑", artists: "歌手", composers: "作曲者", genres: "类型",
    random100: "随机 100 首", recent: "最近添加", favorites: "收藏歌曲",
  };

  window.fnAudioViewPresentation = ({ view, playlistName, creatorAllTracks, albumSurface, scanText, creatorName, folderName }) => ({
    title: playlistName || (creatorAllTracks ? "所有歌曲" : (albumSurface ? "专辑" : (labels[view] || "音乐库"))),
    subtitle: scanText || "飞牛私人音乐库",
    mobileSubtitle: creatorAllTracks ? (creatorName || "飞牛私人音乐库") : (view === "folders" && folderName ? folderName : "飞牛私人音乐库"),
  });
})();
