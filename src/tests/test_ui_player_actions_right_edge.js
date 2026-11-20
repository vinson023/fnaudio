// 播放条右下角那排图标的位置守卫。
//
// 背景：R603 把 761–1100 这一档改成靠右，注释里写着
// `test_ui_player_actions_right_edge.js` 会钉住它 —— 但那个文件从来没有建过。
// 于是 760 以下整排被手机版隐藏、图标从右边缘跳到条中间这件事，一直没有任何
// 守卫能发现，owner 报了两轮才被量出来。这条守卫把三件事钉死：
//
//   1. 桌面端（>=761）单行三列，图标组在第三列靠右；
//   2. 600–760 的窄窗两行版里，图标组占满整行并靠右，且七个控件全部还原
//      display（app.css 是逐个 display:none 的，只还原容器会得到一排空气）；
//   3. 手机（<=760）和安卓客户端仍然是「隐藏整排 + 传输键居中」——那是手机端
//      的既定约定，不许被这次改动顺手破坏。
//
// 位置：src/tests，运行时 cwd 为 src/。
const assert = require("node:assert/strict");
const fs = require("node:fs");

const themeCss = fs.readFileSync("app/ui/fnos-theme.css", "utf8");
const baseCss = fs.readFileSync("app/ui/app.css", "utf8");

// —— 1. 桌面端：单行三列，图标在第三列，靠右 ——
const desktopStart = themeCss.indexOf("/* Desktop player layout: the seek rail is the top edge");
assert.ok(desktopStart > 0, "desktop player layout block must still exist");
const desktop = themeCss.slice(desktopStart, themeCss.indexOf("@media (min-width: 601px)", desktopStart));
assert.match(desktop, /@media \(min-width: 761px\)/, "the desktop player layout must start at 761px");
assert.match(
  desktop,
  /grid-template-columns:\s*minmax\(0,\s*1fr\)\s*max-content\s*minmax\(0,\s*1fr\)\s*!important/,
  "the desktop bar must keep the centred transport column between two equal shares"
);
assert.match(
  desktop,
  /\.player \.player-actions\s*\{[^}]*grid-column:\s*3\s*!important/,
  "the desktop icon cluster must stay in the third column"
);
assert.match(
  themeCss,
  /\.player-actions \{[^}]*justify-content: end !important/,
  "the desktop icon cluster must be right-aligned, not centred (R603)"
);

// —— 2. 窄窗两行版：图标组占满整行并靠右 ——
const narrowStart = themeCss.indexOf("@media (min-width: 600px) and (max-width: 760px) and (min-height: 541px)");
assert.ok(narrowStart > 0, "a 600-760px band must keep the desktop icon cluster visible");
const narrow = themeCss.slice(narrowStart);
const narrowBlock = narrow.slice(0, narrow.indexOf("\n}\n") + 3);
assert.match(
  narrowBlock,
  /\.player \.player-actions\s*\{[^}]*display:\s*flex\s*!important/,
  "the narrow band must show the icon cluster the phone block hid"
);
assert.match(
  narrowBlock,
  /\.player \.player-actions\s*\{[^}]*grid-column:\s*1 \/ -1\s*!important/,
  "the icon cluster must own a full-width row so it can sit on the right edge at any width"
);
assert.match(
  narrowBlock,
  /\.player \.player-actions\s*\{[^}]*justify-content:\s*end\s*!important/,
  "the icon cluster must stay right-aligned in the narrow band"
);
for (const id of ["deviceBtn", "lyricsBtn", "favoriteCurrentBtn", "repeatBtn", "shuffleBtn", "queueBtn"]) {
  assert.match(
    narrowBlock,
    new RegExp(`\\.player \\.player-actions #${id}`),
    `#${id} must be un-hidden in the narrow band, or the cluster renders empty`
  );
}
assert.match(
  narrowBlock,
  /\.player \.player-actions \.volume-control \{ display: inline-grid !important; \}/,
  "the volume control is hidden as a container in app.css, so it needs its own display back"
);
assert.match(
  narrowBlock,
  /\.player \.transport \.mobile-transport-control \{ display: none !important; \}/,
  "the narrow band keeps the real shuffle/repeat in the icon cluster, so the phone duplicates must go"
);
assert.match(
  narrowBlock,
  /html\.android-app \.player-actions \{ display: none !important; \}/,
  "the Android client hides this row on purpose; the narrow band must not resurrect it"
);

// 这两处必须仍然存在：app.css 在 760 以下逐个隐藏控件，只还原容器会得到一排空气。
assert.match(
  baseCss,
  /\.player-actions #deviceBtn,\.player-actions #lyricsBtn,\.player-actions #favoriteCurrentBtn,\.player-actions #repeatBtn,\.player-actions #shuffleBtn,\.player-actions #queueBtn,\.player-actions \.volume-control\{display:none!important\}/,
  "app.css must still hide the seven controls below 760px -- the narrow band above depends on knowing which ones"
);

// —— 3. 手机端约定没被动过 ——
assert.match(
  baseCss,
  /\.player-actions\{display:none!important\}/,
  "the phone stylesheet must still hide the footer action row"
);
assert.match(
  themeCss,
  /@media \(max-width: 760px\) \{[\s\S]*?\.player-actions \{ display: none !important; \}/,
  "the theme's phone block must still hide the footer action row"
);
assert.match(
  baseCss,
  /\.transport\{[^}]*justify-content:center!important/,
  "the phone transport group must stay centred against the full footer width"
);

// 窄窗那一档不能把手机宽度也圈进来，否则手机上会同时出现图标排和居中的手机版。
const narrowQuery = /@media \(min-width: 600px\) and \(max-width: 760px\) and \(min-height: 541px\)/.exec(themeCss);
assert.ok(narrowQuery, "the narrow band must be bounded on both sides");
assert.ok(
  /min-height:\s*541px/.test(narrowQuery[0]),
  "short landscape windows own a side player at <=540px tall; the narrow band must not fight it"
);

console.log("player-actions right edge guard: OK");
