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
assert.match(css, /\.lyrics-header\{\s*display:grid!important;\s*grid-template-columns:64px minmax\(0,1fr\) 64px!important;/);
assert.match(css, /\.lyrics-close\{\s*position:static!important;/);
assert.match(css, /\.lyrics-header-actions \.lyrics-favorite\{\s*position:static!important;/);
assert.match(css, /\.mobile-menu-back\{[\s\S]*?width:34px!important;[\s\S]*?height:32px!important;/);
assert.match(css, /\.sidebar \.library-search\{[\s\S]*?min-height:34px!important;[\s\S]*?margin:0 0 7px!important;/);
assert.match(css, /\.pager\.mobile-visible\{display:block!important\}/);

console.log("Mobile layout regression checks passed.");
