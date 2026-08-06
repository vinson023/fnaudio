const assert = require("node:assert/strict");
const fs = require("node:fs");

const index = fs.readFileSync("app/ui/index.html", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");

const sidebarStart = index.indexOf('<aside class="sidebar">');
const mainStart = index.indexOf('<main class="shell">');
assert.ok(mainStart >= 0 && sidebarStart > mainStart);
const sidebarMarkup = index.slice(sidebarStart, index.indexOf("</aside>", sidebarStart));

assert.match(sidebarMarkup, /id="mobileBackBtn"/);
assert.match(sidebarMarkup, /id="searchInput"/);
assert.match(sidebarMarkup, /class="mobile-menu-tools"/);
assert.match(sidebarMarkup, /class="mobile-menu-tools">[\s\S]*?class="library-search"[\s\S]*?class="nav-title">音乐库[\s\S]*?id="mobileBackBtn"/);
assert.match(sidebarMarkup, /id="mobileBackBtn"[\s\S]*?<svg viewBox="0 0 24 24"/);
assert.doesNotMatch(index, /class="mobile-library-tabs"/);
assert.match(app, /function handleMobileBack\(\)/);
assert.match(app, /\$\("mobileBackBtn"\)\.onclick = handleMobileBack/);
assert.doesNotMatch(app, /querySelector\("\.mobile-library-tabs"\)/);
assert.doesNotMatch(app, /\$\("mobileSearchInput"\)\.oninput/);
assert.doesNotMatch(app, /actionButton\("显示歌词", "lyrics"\)/);
assert.match(app, /if \(pages <= 1\) return "";/);
assert.match(app, /function updateMobilePagerVisibility\(\)/);

assert.match(css, /\.content\{\s*display:flex!important;\s*flex-direction:column!important;/);
assert.match(css, /\.library-scroll\{\s*display:flex!important;\s*flex:1 1 auto!important;/);
assert.match(css, /\.library-scroll \.track-list\{\s*flex:1 1 auto!important;[\s\S]*?overflow-y:auto!important;/);
assert.match(css, /\.pager\{\s*display:block!important;\s*flex:0 0 52px!important;/);
assert.match(css, /\.lyrics-view\{[\s\S]*?grid-template-rows:48px minmax\(0,1fr\)!important;/);
assert.match(css, /\.lyrics-header\{\s*display:grid!important;\s*grid-template-columns:52px minmax\(0,1fr\) 52px!important;[\s\S]*?min-height:48px!important;[\s\S]*?padding:0 8px!important;/);
assert.match(css, /\.lyrics-close\{\s*position:static!important;/);
assert.match(css, /\.lyrics-header-actions \.lyrics-favorite\{\s*position:static!important;/);
assert.match(css, /\.lyrics-panel\{gap:6px!important;padding:8px 14px 10px!important\}/);
assert.doesNotMatch(css, /grid-template-rows:calc\(56px \+ env\(safe-area-inset-top,0px\)\)/);
assert.match(css, /\.sidebar\{[\s\S]*?width:min\(76vw,268px\)!important;[\s\S]*?padding:8px 10px 14px!important;/);
assert.match(css, /\.mobile-menu-tools\{[\s\S]*?grid-template-columns:32px minmax\(0,1fr\)!important;[\s\S]*?grid-template-areas:"back title" "search search"!important;/);
assert.match(css, /\.mobile-menu-back\{[\s\S]*?width:32px!important;[\s\S]*?height:32px!important;/);
assert.match(css, /\.sidebar \.library-search\{[\s\S]*?grid-area:search!important;[\s\S]*?min-height:34px!important;[\s\S]*?margin:0!important;/);
assert.match(css, /\.mobile-menu-tools > \.nav-title\{[\s\S]*?grid-area:title!important;[\s\S]*?line-height:32px!important;/);
assert.match(css, /\.pager\.mobile-visible\{display:block!important\}/);

console.log("Mobile layout regression checks passed.");
