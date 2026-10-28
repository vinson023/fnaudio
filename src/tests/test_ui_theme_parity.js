// Theme parity regression: the shipped UI must consume the approved Hallmark
// prototype tokens verbatim and expose the data-theme switch in settings.
// Deviant re-invented values must never reappear as token definitions.
const fs = require("node:fs");
const assert = require("node:assert/strict");

const html = fs.readFileSync("app/ui/index.html", "utf8");
const tokens = fs.readFileSync("app/ui/design-tokens.css", "utf8");
const theme = fs.readFileSync("app/ui/fnos-theme.css", "utf8");
const appCss = fs.readFileSync("app/ui/app.css", "utf8");

// The theme select lives in the runtime settings pane with the choice hook.
const pane = html.match(/<section\b[^>]*data-settings-pane="runtime"[^>]*>([\s\S]*?)<\/section>/);
assert.ok(pane, "runtime settings pane exists");
assert.match(pane[1], /id="themeModeInput"/, "theme select lives in the runtime pane");
assert.match(pane[1], /data-theme-choice/, "theme select carries the choice hook");
assert.match(pane[1], /<option value="">跟随系统<\/option>/, "follow-system option present");
assert.match(pane[1], /<option value="light">浅色<\/option>/, "light option present");
assert.match(pane[1], /<option value="dark">深色<\/option>/, "dark option present");

// Approved FNOS official token values must exist verbatim in production tokens.
[
  "--fn-bg-brand:#0066ff",
  "--fn-bg-brand-hovered:#005feb",
  "--fn-bg-surface:#f3f3f3",
  "--fn-bg-surface:#1e1e21",
  "--fn-topbar-h:70px",
  "--fn-player-h:88px",
  "--fn-sidebar-w:220px",
  "--fn-radius-s:4px",
  "--fn-radius-m:6px",
  "--fn-radius-l:8px",
  "--fn-fs-3xl:23px",
  "--fn-text-default:#0b0b0c",
  "--fn-text-default:#ffffff",
  "--fn-text-success:#23b178",
].forEach(v => assert.ok(tokens.includes(v), "official token missing: " + v));

// The re-invented palette must never reappear as a token definition.
[
  "--ui-canvas: #f3f5f8",
  "--ui-accent: #0066e6",
  "--ui-header-height: 80px",
  "--ui-player-height: 112px",
].forEach(bad => assert.ok(!tokens.includes(bad), "deviant token must be gone: " + bad));

// Every core --ui-* alias points at the official --fn-* tokens, not a literal.
const aliasBlock = tokens.slice(tokens.indexOf("/* Legacy aliases"));
assert.ok(aliasBlock.length > 0, "alias block present");
const aliasNames = [
  "canvas","surface","sidebar","raised","hover","selected","text","secondary",
  "muted","line","border","accent","accent-hover","success","danger","backdrop",
];
aliasNames.forEach(name => {
  const rule = aliasBlock.match(new RegExp("--ui-" + name + ":\\s*([^;]+);"));
  assert.ok(rule, "alias exists: --ui-" + name);
  assert.match(rule[1], /var\(--fn-/, "alias must reference official tokens: --ui-" + name);
});

// The record-console presentation shares one SVG scale and visible keyboard
// focus, while missing artwork uses a stable disc fallback instead of a glyph.
assert.match(theme, /\.nav-item\s*>\s*svg[\s\S]*?stroke-width:\s*1\.8/);
assert.match(theme, /:focus-visible[\s\S]*?outline:\s*2px solid var\(--ui-accent\)/);
assert.doesNotMatch(theme, /#[0-9a-fA-F]{3,8}\b/, "theme overrides must consume design tokens instead of literal colors");
assert.doesNotMatch(theme, /\brgba?\s*\(/, "theme overrides must consume design tokens instead of rgb literals");
assert.doesNotMatch(appCss, /:root\{--bg:\s*#[0-9a-fA-F]/, "app.css base palette must consume FNOS aliases");
assert.doesNotMatch(appCss, /:root\{--fn-bg:\s*#[0-9a-fA-F]/, "app.css compatibility palette must consume FNOS aliases");
assert.doesNotMatch(appCss, /\.track-cover\{[^}]*background:linear-gradient\([^}]*#[0-9a-fA-F]/,
  "track cover fallback must use FNOS semantic surfaces instead of a legacy hard-coded gradient");
assert.match(appCss, /\.track-cover\{[^}]*background:var\(--ui-selected\)/,
  "track cover fallback must use the shared selected surface token");
assert.doesNotMatch(appCss, /font:\s*14px\/1\.5\s+Inter,system-ui/, "app.css body must consume the shared --ui-font token");
assert.doesNotMatch(
  appCss,
  /#(?:12b8a8|0ca99b|079d91|55d6bc|0aa89d|e8f9f6|e8fbf9|edf8f6|eef9f7|f6fbfa|dff7f3|bdebe4|bdebe7|9bded6|d9f5f0)/i,
  "app.css must not retain retired teal literals",
);
assert.match(appCss, /\.top-mode-button:hover\{background:var\(--ui-hover\)/,
  "top mode hover must use the shared FNOS hover token");
assert.match(appCss, /\.track-actions button:hover\{background:var\(--ui-hover\)!important/,
  "track action hover must use the shared FNOS hover token");
assert.match(theme, /\.record-placeholder\s*\{[^}]*stroke-width:\s*1\.5/);
assert.match(theme, /\.record-placeholder-center\s*\{[^}]*fill:\s*currentColor/);
assert.match(fs.readFileSync("app/ui/app.js", "utf8"), /function recordPlaceholderMarkup\(\)[\s\S]*?class="record-placeholder"/);
assert.match(theme, /\.device-row-radio svg\s*\{[^}]*stroke-width:\s*2/);
assert.match(theme, /\.lyrics-close svg, \.lyrics-favorite svg\s*\{/);
assert.match(theme, /\.lyrics-cover:not\(:has\(img\)\)\s*\{[^}]*display:\s*grid/);
assert.match(fs.readFileSync("app/ui/index.html", "utf8"), /class="lyrics-cover"[\s\S]*class="record-placeholder"/);
assert.match(fs.readFileSync("app/ui/app.js", "utf8"), /node\.classList\.toggle\("has-artwork", Boolean\(next\)\)/);
assert.match(fs.readFileSync("app/ui/index.html", "utf8"), /id="lyricsFavoriteBtn"[^>]*aria-label="收藏当前歌曲"/);
assert.match(fs.readFileSync("app/ui/index.html", "utf8"), /id="modeBtn"[^>]*aria-label="MP3 转码：关"[^>]*>MP3 转码：关<\//,
  "desktop MP3 control must retain the original state text");
assert.doesNotMatch(fs.readFileSync("app/ui/app.css", "utf8"), /#modeBtn\s+svg/,
  "base CSS must not retain SVG-only rules for the text MP3 control");
assert.doesNotMatch(theme, /#modeBtn\s+svg/,
  "FNOS theme must not retain SVG-only rules for the text MP3 control");
assert.match(appCss, /\.player-actions #favoriteCurrentBtn:not\(.active-control\):hover,[\s\S]*?background:var\(--ui-hover\)!important;[\s\S]*?color:var\(--ui-secondary\)!important;[\s\S]*?border-color:var\(--ui-border\)!important;/,
  "non-active player hover guard must use FNOS color tokens");
assert.match(appCss, /\.metadata-candidate-dialog\{[^}]*background:var\(--ui-canvas\)/,
  "metadata candidate dialog must use the FNOS canvas token");
assert.match(appCss, /\.metadata-candidate-source-bar\{[^}]*border-bottom:1px solid var\(--ui-line\);background:var\(--ui-sidebar\)/,
  "metadata candidate source bar must use FNOS surface tokens");
assert.match(appCss, /\.metadata-candidate-choice:hover\{border-color:var\(--ui-accent\);background:var\(--ui-selected\)/,
  "metadata candidate hover must use FNOS selection tokens");
assert.match(appCss, /\.external-share-dialog\{[^}]*color:var\(--ui-text\)!important;background:var\(--ui-raised\)!important\}/,
  "external share dialog must use FNOS surface tokens");
assert.match(appCss, /\.external-share-detail input,\.external-share-result input\{[^}]*border:1px solid var\(--ui-border\)[^}]*color:var\(--ui-text\)[^}]*background:var\(--ui-surface\)/,
  "external share inputs must use FNOS field tokens");
assert.match(appCss, /\.switch-control input:checked\+span\{background:var\(--ui-accent\)\}/,
  "external share switch must use the FNOS accent token");
assert.match(appCss, /\.library-path-remove:hover\{color:var\(--ui-danger\);border-color:var\(--ui-danger\);background:var\(--ui-danger-bg\)\}/,
  "library path removal hover must use FNOS danger tokens");
assert.match(appCss, /\.settings-pane-status\{color:var\(--ui-success\)!important\}/,
  "settings status fallback must use the FNOS success token");
assert.match(appCss, /\.library-path-input\[readonly\]\{background:var\(--ui-sidebar\)!important;color:var\(--ui-secondary\)!important\}/,
  "readonly library path fallback must use FNOS surface and text tokens");
assert.match(appCss, /\.metadata-settings-tabs\{border-bottom-color:var\(--ui-line\)!important\}/,
  "metadata settings tabs fallback must use the FNOS line token");
assert.match(appCss, /\.metadata-tag-job\.is-failed\{background:var\(--ui-danger-bg\)!important;color:var\(--ui-danger\)!important;border-left-color:var\(--ui-danger\)!important\}/,
  "metadata failed job fallback must use FNOS danger tokens");
assert.match(fs.readFileSync("app/ui/app.js", "utf8"), /function normalizeDialogCloseControls\(\)/);
assert.match(theme, /\.dialog-close-button svg, \.library-path-remove svg\s*\{/);
assert.match(theme, /\.settings-tabs\s*\{\s*display:\s*flex !important;\s*flex-wrap:\s*nowrap !important;[\s\S]*?overflow-x:\s*auto !important;/, "mobile settings tabs must stay in one horizontally scrollable row");
assert.match(theme, /\.settings-tabs button\s*\{\s*flex:\s*0 0 auto !important;\s*white-space:\s*nowrap !important;/, "mobile settings tab labels must not wrap");
assert.match(theme, /\.switch-control input:focus-visible \+ span\s*\{[^}]*outline:2px solid var\(--ui-accent\)[^}]*outline-offset:2px/, "custom switches must expose a visible keyboard focus ring");
assert.match(theme, /\.top-actions \.mode-mp3-icon\s*\{[\s\S]*?font-size:\s*12px;/, "MP3 control must retain the original text treatment");
assert.match(theme, /prefers-color-scheme:\s*dark[\s\S]*?\.player-actions #deviceBtn[\s\S]*?color:\s*var\(--ui-secondary\) !important;/,
  "dark inactive player controls must use the readable secondary token");
assert.match(theme, /\.track-cell-format\s*\{[\s\S]*?color:\s*var\(--ui-secondary\) !important;[\s\S]*?background:\s*var\(--ui-sidebar\) !important;/,
  "format cells must use the shared FNOS surface tokens");
assert.match(theme, /\.track-cell-format\.dsd\s*\{[\s\S]*?color:\s*var\(--ui-warning\) !important;[\s\S]*?background:\s*var\(--ui-warning-bg\) !important;/,
  "DSD format cells must use the shared FNOS warning tokens");
assert.match(theme, /\.player-actions #deviceBtn,[\s\S]*?\.player-actions #queueBtn\s*\{\s*color:\s*var\(--ui-secondary\) !important;/,
  "inactive player controls must use the shared secondary token in every theme");

// Every native dialog close action must consume the shared linear close icon
// treatment. The text fallback used by the older dialogs bypassed the theme
// sizing and made the close affordance visually inconsistent.
for (const id of [
  "closeDialog",
  "closeFolderDialog",
  "closeDlnaDiagnosticsDialog",
  "closePlaylistDialog",
  "closeTrackActionDialog",
  "closeMetadataCandidateDialog",
  "closeExternalShareDialog",
  "closeColumnsDialog",
]) {
  const button = html.match(new RegExp(`<button[^>]*id="${id}"[^>]*>[\\s\\S]*?<\\/button>`));
  assert.ok(button, `dialog close button #${id} exists`);
  assert.match(button[0], /class="[^"]*dialog-close-button[^"]*"/, `#${id} uses the shared close button class`);
  assert.match(button[0], /aria-label="关闭"/, `#${id} keeps an explicit accessible name`);
  assert.match(button[0], /<svg[^>]*aria-hidden="true"/, `#${id} uses a decorative SVG icon`);
  assert.match(
    html,
    new RegExp(`<button[^>]*id="${id}"[^>]*>[\\s\\S]*?<\\/button><\\/div>`),
    `#${id} must leave the dialog header container closed`,
  );
}
