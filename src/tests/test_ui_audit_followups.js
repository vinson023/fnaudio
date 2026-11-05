// Static contracts for the second UI-audit batch (P1-6..P1-8 and the P2 list).
// These are regression guards: every rule below is one of the defects the audit
// found, and the assertion states the invariant that replaced it.
const assert = require("node:assert/strict");
const fs = require("node:fs");

const html = fs.readFileSync("app/ui/index.html", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");

// P2: the header settings button was unreachable at every breakpoint (the whole
// .top-actions row was display:none on desktop, phones and the Android client,
// and the row itself has since been removed), so it only existed as a 0x0 node
// duplicating the sidebar entry.
assert.doesNotMatch(html, /id="folderBtn"/, "the unreachable header settings button must stay deleted");
assert.doesNotMatch(app, /folderBtn/, "no script may keep binding the deleted header settings button");
assert.match(html, /id="mobileSettingsNavBtn"[\s\S]*?M4 6h16M4 12h16M4 18h16/,
  "the sidebar entry must own the settings affordance");

// P1-6: five panes all reading "保存" said nothing about what was being written.
assert.doesNotMatch(app, /normalizeSettingsSaveLabels/, "settings must not flatten every pane label to a bare 保存");
assert.match(app, /button\.dataset\.saveLabel = label/, "the pane label must be captured before the saving state overwrites it");
assert.match(app, /button\.textContent = button\.dataset\?\.saveLabel \|\| "保存"/,
  "a finished save must restore the pane-specific label");

// P1-8: the phone surface uses 44px targets everywhere else.
assert.match(theme, /\.settings-pane \.secondary-button \{ min-height: 44px !important; \}/,
  "settings buttons must meet the 44px touch target on phones");

// P2: the navigation drawer had no title and no way to close it except the backdrop.
assert.match(html, /class="sidebar-head"[\s\S]*?id="mobileNavCloseBtn"/, "the drawer must expose a header with a close button");
assert.match(css, /\.sidebar-head\{display:none\}/, "the drawer header must not appear on the desktop sidebar");
assert.match(theme, /\.sidebar-head \{ display: flex !important;/, "the drawer header must appear once the sidebar becomes an overlay");
assert.match(app, /\$\("mobileNavCloseBtn"\)\.onclick = \(\) => setMobileNavigation\(false\)/,
  "the drawer close button must use the shared navigation setter");

// P2: 随机 100 首 is a library-wide view, not a playlist.
assert.match(html, /data-view="genres"[\s\S]*?data-view="random100"[\s\S]*?nav-title secondary/,
  "随机 100 首 must sit in the 音乐库 group, before the 播放列表 heading");

// P2: an empty install is a setup state, not a failure; and "0 个配置目录" told
// the user nothing when the fix was simply to pick a directory.
assert.match(app, /classList\.toggle\("is-error", hasPayload && !unconfigured &&/, "an unconfigured or not-yet-loaded library must not use the danger fill");
assert.match(app, /还没有配置音乐目录，选择目录后即可扫描并收录歌曲。/, "the unconfigured card must explain the next step");

// P2: the placeholder row is not a directory, so it must not offer "remove".
assert.match(app, /\$\{value \? `<button class="library-path-remove"/, "an empty path row must not render a remove button");

// R469 read the 词 glyph as the odd one out among the line icons and swapped it
// for a note symbol; the operator has since asked for the glyph back, which is
// what R346 did too.  It keeps the svg wrapper and viewBox the icon guards look
// for, but it has to paint with fill — the shared 1.75px stroke would render the
// character as an outline.
assert.match(html, /id="lyricsBtn"[\s\S]*?class="lyric-symbol"[^>]*viewBox="0 0 24 24"[\s\S]*?<text[^>]*>词<\/text>/,
  "the lyrics control must render 词 inside its svg");
assert.match(theme, /\.player-actions #lyricsBtn \.lyric-symbol \{[\s\S]*?fill: currentColor !important;[\s\S]*?stroke: none !important;/,
  "the 词 glyph must paint with fill instead of the shared stroke");

// P1-7: a single placeholder line in a 720px column looked anchored to the corner.
assert.match(css, /\.lyrics-lines\.is-empty\{display:grid!important;place-items:center!important/, "the empty lyrics state must be centred");
assert.match(app, /box\.classList\.toggle\("is-empty", !lines\.length\)/, "rendering lyrics must clear the empty state");
assert.match(app, /lines\.classList\.add\("is-empty"\)/, "a lyrics message must restore the empty state");

// P2: metadata inputs were 231x34 in the probe row and 349x38 everywhere else.
assert.match(css, /\.metadata-probe-query\{display:grid;grid-template-columns:1fr 1fr;gap:8px\}/,
  "the probe row must use the same two-column grid as the rest of the pane");
assert.match(css, /\.metadata-probe-query input\{width:100%;min-width:0;height:38px/, "probe inputs must share the 38px height");

console.log("UI audit follow-up contracts verified");
