const assert = require("node:assert/strict");
const fs = require("node:fs");

const html = fs.readFileSync("app/ui/index.html", "utf8");
const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");

// Button icons are visual chrome. Their accessible name belongs to the button's
// aria-label, title, or visible text; exposing the same SVG to assistive tech
// causes the control to be announced twice.
const buttonBlocks = html.match(/<button\b[^>]*>[\s\S]*?<\/button>/gi) || [];
const iconButtons = buttonBlocks.filter((block) => /<svg\b/i.test(block));
const untypedStaticButtons = buttonBlocks.filter((block) => !/\btype="(?:button|submit|reset)"/i.test(block));
assert.deepEqual(untypedStaticButtons, [], "static buttons must declare an explicit type");
const missing = [];
for (const block of iconButtons) {
  for (const svg of block.matchAll(/<svg\b[^>]*>/gi)) {
    if (!/\baria-hidden="true"/i.test(svg[0])) missing.push(block.slice(0, 160));
  }
}
assert.deepEqual(missing, [], `static button SVGs must be decorative: ${missing.join(" | ")}`);

for (const [needle, label] of [
  ['artist-all-songs-icon" aria-hidden="true"><svg aria-hidden="true"', "artist entry icon"],
  ['folder-group-chevron" aria-hidden="true"><svg aria-hidden="true"', "folder chevron"],
  ['device-row-radio" aria-hidden="true">${isCurrent ? \'<svg aria-hidden="true"', "device selection icon"],
]) {
  assert.ok(app.includes(needle), `${label} must remain explicitly decorative`);
}
assert.doesNotMatch(css, /metadata-provider-move[^\n]*content:\s*["'](?:↑|↓)["']/,
  "legacy metadata provider arrow pseudo-elements must not remain in the base stylesheet");
assert.doesNotMatch(css, /#folderBtn:before|#folderBtn::before/,
  "settings must use the real SVG icon instead of a duplicate folderBtn pseudo-element");
assert.doesNotMatch(css, /metadata-settings-tabs button\.active:after|metadata-settings-tabs button\.active::after/,
  "metadata settings tabs must not retain the retired underline pseudo-element");
assert.doesNotMatch(css, /settings-tabs button\.active:after|settings-tabs button\.active::after/,
  "settings tabs must use the FNOS selected surface instead of the retired underline pseudo-element");
assert.match(html, /id="folderBtn"[^>]*>[\s\S]*class="settings-menu-icon"[^>]*aria-hidden="true"[\s\S]*M4 6h16M4 12h16M4 18h16/,
  "settings button must use the approved three-line menu SVG icon");
assert.match(html, /id="shuffleBtn"[^>]*aria-label="乱序播放"/,
  "shuffle control must expose a stable accessible name");
assert.match(html, /id="deviceBtn"[^>]*title="播放设备"[^>]*aria-label="播放设备"/,
  "device picker tooltip and accessible name must describe the picker action");
assert.match(html, /id="favoriteCurrentBtn"[^>]*aria-label="收藏当前歌曲"/,
  "favorite control must expose an explicit accessible name");
assert.match(html, /id="queueBtn"[^>]*aria-label="播放队列"/,
  "queue control must expose an explicit accessible name");
for (const legacyClass of [
  "top-folder-icon", "top-refresh-icon", "gear-main", "gear-soft", "gear-hole", "gear-ring",
  "repeat-symbol", "shuffle-symbol", "queue-symbol", "repeat-mode-label", "repeat-mode-mark",
  "dlna-icon", "dlna-screen", "dlna-wave", "row-play", "row-more", "mobile-quality",
]) {
  assert.doesNotMatch(css, new RegExp("\\." + legacyClass + "\\b"),
    `retired icon class must not remain in app.css: ${legacyClass}`);
}
assert.doesNotMatch(theme, /repeat-mode-mark|repeat-mode-label/,
  "retired repeat badge styles must not remain in the FNOS theme");
assert.doesNotMatch(css, /\.top-mode-button svg\b/,
  "text MP3 mode control must not retain retired SVG-only styling");
assert.match(css, /\.track-sort-indicator svg\{[^}]*stroke-width:2/,
  "sort direction indicators must use the shared line SVG treatment");
assert.match(html, /id="lyricsBtn"[^>]*>[\s\S]*class="lyric-symbol"[^>]*>词<\//,
  "lyrics must retain the approved Chinese text button");
assert.match(html, /id="modeBtn"[^>]*aria-label="MP3 转码：关"[^>]*>MP3 转码：关<\//,
  "MP3 transcode control must retain the original state text button");
const modeButton = html.match(/<button\b[^>]*id="modeBtn"[^>]*>[\s\S]*?<\/button>/i)?.[0] || "";
assert.doesNotMatch(modeButton, /<svg\b/i,
  "MP3 transcode control must not regress to an icon-only button");
assert.match(app, /desktopButton\.textContent = state\.mp3Transcode \? "MP3 转码：开" : "MP3 转码：关"/,
  "MP3 transcode control must update its visible state text");
assert.match(app, /function groupActionButton\(label, action, disabled = false\)/,
  "dynamic group actions must share one button builder");
assert.match(app, /track-action-choice" type="button" data-group-action=/,
  "dynamic group actions must explicitly remain non-submit buttons");
assert.match(app, /groupActionButton\("打开", "open", multiple\)/,
  "the group open action must use the shared icon action builder");
assert.match(app, /open: '<path d="M3 7\.5h6\.2l2 2H21v8\.7/,
  "the group open action must use the shared folder icon vocabulary");
assert.match(app, /function breadcrumbChevronMarkup\(className = "breadcrumb-chevron"\)/,
  "breadcrumb navigation must use the shared chevron builder");
assert.ok(!app.includes('artist-all-songs-chevron" aria-hidden="true">&gt;</span>'),
  "artist navigation must not regress to a text chevron");
assert.match(css, /\.breadcrumb-chevron svg\{[^}]*stroke-width:1\.8/,
  "breadcrumb chevrons must use the shared line icon treatment");
assert.match(app, /function normalizeButtonTypes\(\)/,
  "the UI must normalize legacy button elements that omit an explicit type");
assert.match(app, /form\?\.id === "metadataCandidateSearchForm" \? "submit" : "button"/,
  "only the metadata search form may retain submit semantics");
for (const [needle, label] of [
  ['<button type="button" class="device-row', "device rows"],
  ['<button type="button" class="playlist-choice"', "playlist choices"],
  ['<button type="button" class="track-action-choice ${danger', "track actions"],
  ['<button type="button" class="track-action-choice" data-apply-track-metadata=', "metadata apply action"],
]) {
  assert.ok(app.includes(needle), `${label} must explicitly use type=button`);
}

console.log(`button icon semantics: ${iconButtons.length} static icon buttons and dynamic chrome verified`);
