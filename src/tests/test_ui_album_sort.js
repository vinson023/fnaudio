// 专辑列表按专辑名 / 歌手 / 发行日期排序，靠的是**已有的那三个列标题**。
//
// 这一轮先走错过一次，写下来免得再犯：专辑列表一直有列标题行（`标题 / 歌手 /
// 发行日期`），由 `track_table_presentation.js` 的 `album-collection` 模式生成。
// 其中只有「标题」是按钮，另两个是纯 `<div>` —— 看起来一样，点下去什么都不发生，
// 而服务端的组查询也从来没读过排序键。所以负责人那句「要可以按歌手和发行日期
// 排序」问的是这两格，不是要再造一套控件。
//
// 于是这里钉三件事：
//
//   1. 三个表头都得是 `data-track-sort` 按钮，并且键要在 `sortOptionsForView()`
//      里登记过 —— `applyTrackSort` 会拒绝没登记的键，漏了就是一个点不动的按钮；
//   2. 请求必须把 `state.sortKey` / `state.sortDir` 发给服务端。这两个状态一直由
//      表头维护，缺的是最后一段接线，不是新的状态；
//   3. 不许再出现第二套排序控件（上一轮那三个 `album-sort-btn` 按钮）。
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.join(__dirname, "..");
const appSource = fs.readFileSync(path.join(root, "app", "ui", "app.js"), "utf8");
const cssSource = fs.readFileSync(path.join(root, "app", "ui", "app.css"), "utf8");
const specSource = fs.readFileSync(path.join(root, "app", "server", "library_query_spec.py"), "utf8");
const presentationSource = fs.readFileSync(path.join(root, "app", "server", "library_group_presentation.py"), "utf8");
const librarySource = fs.readFileSync(path.join(root, "app", "server", "library.py"), "utf8");

function loadUiModule(file, name) {
  const context = { globalThis: {}, Object, Array, Math, Number, String, Boolean };
  vm.runInNewContext(fs.readFileSync(path.join(root, "app", "ui", file), "utf8"), context);
  return context.globalThis[name];
}

function sourceBetween(start, end) {
  const from = appSource.indexOf(start);
  const to = appSource.indexOf(end, from);
  assert.ok(from >= 0 && to > from, `expected ${start} before ${end}; re-read app.js before editing this test`);
  return appSource.slice(from, to);
}

// --- 1. 三个键都登记过 -------------------------------------------------------
const sortOptions = loadUiModule("library_sort_options_policy.js", "fnAudioLibrarySortOptionsPolicy");
// `Array.from` rather than `.map`: the policy module runs in its own vm realm, so
// an array built there fails `deepStrictEqual` against a local literal even when
// the contents match.
const albumOptions = Array.from(sortOptions.options("albums"), ([key]) => key);
assert.deepEqual(albumOptions, ["album", "artist", "release_date"]);
assert.equal(sortOptions.defaultKey("albums"), "album", "an upgrade must keep reading the album list by name");

// --- 2. 三个表头都是按钮，键与登记的一致 -------------------------------------
const tableHead = loadUiModule("track_table_presentation.js", "fnAudioTrackTablePresentation");
const head = tableHead.tableHeadPresentation({
  mode: "album-collection", currentSort: "album", sortDir: "asc", sortableSortKeys: albumOptions,
});
const headerKeys = [...head.markup.matchAll(/data-track-sort="([a-z_]+)"/g)].map(match => match[1]);
assert.deepEqual(headerKeys, albumOptions, "every registered album order needs a button, and no button may lack one");
assert.equal((head.markup.match(/<button/g) || []).length, 3, "歌手 and 发行日期 used to be plain labels");

const descHead = tableHead.tableHeadPresentation({
  mode: "album-collection", currentSort: "release_date", sortDir: "desc", sortableSortKeys: albumOptions,
});
assert.match(descHead.markup, /发行日期<span class="track-sort-indicator"/, "the header in force shows which way it points");
assert.equal((descHead.markup.match(/track-sort-indicator/g) || []).length, 1, "only one column is the current order");
assert.match(descHead.markup, /m6 10 6 6 6-6/, "and the arrow turns over with the direction");

// 同一个表头也用在「某个歌手的专辑列表」里，那个视图只登记了一部分顺序 ——
// 没登记的必须退回纯标签，否则又是一个点了不会有任何变化的死按钮（R523）。
const creatorHead = tableHead.tableHeadPresentation({
  mode: "album-collection", currentSort: "album", sortDir: "asc",
  sortableSortKeys: Array.from(sortOptions.options("albums", { creatorAlbum: true, creatorView: true }), ([key]) => key),
});
assert.deepEqual(
  [...creatorHead.markup.matchAll(/data-track-sort="([a-z_]+)"/g)].map(match => match[1]),
  ["album", "release_date"],
  "an artist's own album list can order by year but not by artist -- every row shares it",
);
assert.match(creatorHead.markup, /<span class="track-head-label">歌手<\/span>/, "the header it cannot sort is a label, not a dead button");

// --- 3. 请求把表头维护的那两个状态发出去 --------------------------------------
const requestSource = sourceBetween('params.set("dir", state.sortDir || "asc");', "const data = await fetchLibraryResponse(`api/library/groups");
assert.match(requestSource, /params\.set\("sort", state\.sortKey \|\| "album"\)/, "the album order is state.sortKey");
assert.match(requestSource, /=== "albums"\) params\.set\("sort"/, "only albums send a key; the other group lists have one order");

// --- 4. 不许有第二套排序控件 -------------------------------------------------
for (const name of ["albumSortBar", "data-album-sort", "album-sort-btn", "album-sort-group"]) {
  assert.equal(appSource.includes(name), false, `app.js still carries ${name}`);
  assert.equal(cssSource.includes(name), false, `app.css still styles ${name}`);
}
assert.match(sourceBetween("function albumListBar", "function renderAlbumGroups"),
  /张专辑/, "the strip that is left reports the count and nothing else");
for (const name of ["album-layout-bar", "album-grid", "album-tile", "data-album-layout"]) {
  assert.equal(appSource.includes(name), false, `app.js still references ${name}`);
  assert.equal(cssSource.includes(name), false, `app.css still styles ${name}`);
}

// --- 5. 服务端认得前端的键 ---------------------------------------------------
const columnsBlock = specSource.slice(
  specSource.indexOf("GROUP_SORT_COLUMNS = {"),
  specSource.indexOf("GROUP_SORT_KEYS"),
);
const backKeys = [...columnsBlock.matchAll(/^\s{4}"([a-z_]+)":/gm)].map(match => match[1]);
const aliasBlock = specSource.slice(
  specSource.indexOf("GROUP_SORT_ALIASES = {"),
  specSource.indexOf("\n", specSource.indexOf("GROUP_SORT_ALIASES = {")),
);
const aliases = Object.fromEntries([...aliasBlock.matchAll(/"([a-z_]+)":\s*"([a-z_]+)"/g)].map(m => [m[1], m[2]]));
// Front-end vocabulary → SQL vocabulary, one alias per extra name and no gaps.
const resolved = albumOptions.map(key => aliases[key] || key);
assert.deepEqual(resolved, backKeys, "the buttons and the SQL whitelist must name the same orders");

// --- 6. 投影不能把排序依据丢掉 -----------------------------------------------
const fieldsLine = presentationSource.slice(
  presentationSource.indexOf("GROUP_FIELDS = ("),
  presentationSource.indexOf("FOLDER_FIELDS"),
);
assert.match(fieldsLine, /"release_year"/, "projection drops unknown fields; release_year must be listed or the row has no year");

// --- 7. 旧库要能升级，不是直接报错 -------------------------------------------
assert.match(
  librarySource,
  /ALTER TABLE albums ADD COLUMN release_year/,
  "CREATE TABLE IF NOT EXISTS cannot add a column to an existing index; the migration has to",
);

// --- 8. 手机端必须留着这行表头 -----------------------------------------------
// 窄屏规则原本是 `.table-head{display:none!important}`，于是手机上整行排序入口
// 一起消失：0.2.167 新加的按歌手/发行日期排序在真机上根本够不着。歌曲表的列在
// 手机上塌成一行，表头确实没东西可标；但专辑列表和分类列表的排序只有这一处，
// 所以它们要把这行留成一条可点的排序条。
const narrowStart = cssSource.indexOf("/* The song table's columns collapse");
const narrowEnd = cssSource.indexOf("/* Desktop right-click menu", narrowStart);
assert.ok(narrowStart >= 0 && narrowEnd > narrowStart, "the narrow-screen header rule moved; re-read app.css before editing this test");
const narrowBlock = cssSource.slice(narrowStart, narrowEnd);
assert.match(narrowBlock, /\.table-head\{display:none!important\}/, "the song table still drops its header on a phone");
for (const mode of ["album-collection", "group"]) {
  assert.ok(
    narrowBlock.includes(`.table-head[data-table-mode="${mode}"]`),
    `${mode} lists must keep their sort row on a phone`,
  );
}
assert.match(narrowBlock, /display:flex!important/, "the kept row is a sort bar, not a column ruler");
assert.match(
  appSource,
  /head\.dataset\.tableMode = mode/,
  "the narrow-screen rules key off the header mode, so renderTableHead must publish it",
);

// --- 9. 手机端专辑详情的曲目行必须塌成一列 ------------------------------------
// 窄屏把除 .track-main 以外的单元格全隐藏了（`.track-cell{display:none}`），
// 但 `.album-detail-track-list .track{grid-template-columns:var(--fnaudio-track-columns)}`
// 的优先级是 0,2,0，压过手机端通用的 `.track{grid-template-columns:minmax(0,1fr) 40px 54px}`，
// 于是这一行还按桌面的六列模板排。`.track-main` 被钉在第 1 列，第 1 列是「序号」
// 时只有 48px，标题和歌手被塞进去再裁掉 —— 真机上整片曲目区只剩一个封面缩略图。
// 列集合是用户可配的，所以这里不能靠「第 1 列刚好是宽的标题列」蒙对。
const detailNarrowStart = cssSource.indexOf("/* The library viewport owns scrolling on phones");
const detailNarrowEnd = cssSource.indexOf(".album-group-row{display:grid", detailNarrowStart);
assert.ok(
  detailNarrowStart >= 0 && detailNarrowEnd > detailNarrowStart,
  "the album-detail narrow-screen block moved; re-read app.css before editing this test",
);
const detailNarrowBlock = cssSource.slice(detailNarrowStart, detailNarrowEnd);
assert.match(
  detailNarrowBlock,
  /\.album-detail-track-list \.track\{grid-template-columns:minmax\(0,1fr\)!important\}/,
  "album-detail rows must collapse to one column on a phone, or the title inherits the 序号 column's 48px",
);
assert.match(
  detailNarrowBlock,
  /\.album-detail-track-list \.track-main\{grid-column:1 \/ -1!important\}/,
  "the single visible cell has to span the whole row, not just column 1",
);

console.log("Album sort regression checks passed.");
