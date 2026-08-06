const assert = require("node:assert/strict");
const fs = require("node:fs");

const index = fs.readFileSync("app/ui/index.html", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");

const sidebarStart = index.indexOf('<aside class="sidebar">');
const mainStart = index.indexOf('<main class="shell">');
assert.ok(mainStart >= 0 && sidebarStart > mainStart);
const sidebarMarkup = index.slice(sidebarStart, index.indexOf("</aside>", sidebarStart));

assert.match(sidebarMarkup, /id="searchInput"/);
assert.doesNotMatch(sidebarMarkup, /id="mobileBackBtn"/);
assert.doesNotMatch(sidebarMarkup, /class="mobile-menu-tools"/);
assert.match(index, /class="mobile-library-search"[\s\S]*?id="mobileSearchInput"[\s\S]*?type="search"/);
assert.match(index, /interactive-widget=overlays-content/);
assert.doesNotMatch(index, /class="mobile-library-tabs"/);
assert.doesNotMatch(app, /function handleMobileBack\(\)/);
assert.doesNotMatch(app, /\$\("mobileBackBtn"\)/);
assert.doesNotMatch(app, /querySelector\("\.mobile-library-tabs"\)/);
assert.match(app, /const mobileSearchInput = \$\("mobileSearchInput"\)/);
assert.match(app, /function setMobileSearchFocusState\(active\)/);
assert.match(app, /document\.body\.classList\.toggle\("mobile-search-active", enabled\)/);
assert.match(app, /mobileSearchInput\.addEventListener\("focus", \(\) => setMobileSearchFocusState\(true\)\)/);
assert.match(app, /mobileSearchInput\.addEventListener\("blur", \(\) => setMobileSearchFocusState\(false\)\)/);
assert.doesNotMatch(app, /window\.addEventListener\("resize", setMobileSearchFocusState/);
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
assert.match(css, /\.mobile-library-search\{[\s\S]*?flex:0 0 42px!important;[\s\S]*?margin:8px 10px 6px!important;[\s\S]*?border-radius:10px!important;/);
assert.match(css, /\.mobile-library-search:focus-within\{[\s\S]*?box-shadow:0 0 0 3px #12b8a816!important/);
assert.doesNotMatch(css, /\.mobile-menu-back\{/);
assert.match(css, /\.pager-inner\{[\s\S]*?width:100%!important;[\s\S]*?justify-content:center!important;/);
assert.match(css, /\.pager-nav\{[\s\S]*?width:100%!important;[\s\S]*?justify-content:center!important;/);
assert.match(css, /\.pager-page-summary\{flex:0 0 auto!important;/);
assert.match(css, /body\.mobile-search-active \.player\{[\s\S]*?position:absolute!important;[\s\S]*?display:grid!important;[\s\S]*?contain:layout paint!important;/);
assert.doesNotMatch(css, /body\.mobile-search-active \.player\{display:none!important\}/);
assert.doesNotMatch(css, /body\.mobile-search-active \.content\{height:calc\(100dvh - 60px\)!important/);
assert.match(css, /body\.mobile-search-active \.now-playing \.is-overflowing\{animation-play-state:paused!important;/);
assert.match(css, /\.pager\.mobile-visible\{display:block!important\}/);

console.log("Mobile layout regression checks passed.");
