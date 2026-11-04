const assert = require('node:assert/strict');
const fs = require('node:fs');

const root = __dirname + '/..';
const index = fs.readFileSync(root + '/app/ui/index.html', 'utf8');
const app = fs.readFileSync(root + '/app/ui/app.js', 'utf8');
const css = fs.readFileSync(root + '/app/ui/app.css', 'utf8');

assert.match(index, /id="libraryHealth"/, 'Music library settings must expose a health summary region');
assert.match(index, /id="libraryScanNowBtn"/, 'Music library settings must expose an independent scan action');
assert.match(index, /id="libraryHealthStatus"/, 'Music library settings must expose a status label');
assert.match(app, /function renderLibraryHealth\(\)/, 'Library health must have one render boundary');
assert.match(app, /libraryScanNowBtn[\s\S]*?requestLibraryLoad\(1, true\)/, 'Scan action must use the shared refresh path');
assert.match(app, /status\.exists === true[\s\S]*?status\.readable === true/, 'Health rendering must distinguish missing and unreadable roots');
assert.match(app, /last_error/, 'Health rendering must expose the last scan error');
assert.match(css, /\.library-health/, 'Library health must have a dedicated layout style');

console.log('Library settings health UI regression checks passed');

const vm = require('node:vm');
const source = app.match(/^function renderLibraryHealth\([^]*?^}/m)?.[0];
const toggles = [];
const nodes = Object.fromEntries(['libraryHealth', 'libraryHealthStatus', 'libraryHealthPath', 'libraryHealthCount', 'libraryHealthLastScan', 'libraryHealthDetail', 'libraryScanNowBtn'].map(id => [id, {classList: {toggle(name, value) { toggles.push([id, name, value]); }}, textContent: ''}]));
const context = {state: {libraryStatus: {library_path: '', library_paths: [], exists: false, readable: false}},
  $: id => nodes[id], displayText: String, scanProgressText: () => '',
  setTextContentIfChanged: (node, text) => {node.textContent = text;}};
vm.createContext(context);
vm.runInContext(source, context);
context.renderLibraryHealth();
assert.equal(nodes.libraryHealthStatus.textContent, '尚未配置音乐目录');
assert.equal(nodes.libraryScanNowBtn.disabled, true, 'a fresh installation has no directory to scan');
assert.match(nodes.libraryHealthDetail.textContent, /还没有配置音乐目录/,
  'an unconfigured library must explain the next step instead of counting zero paths');
const errorFlags = () => toggles.filter(([id, name]) => id === 'libraryHealth' && name === 'is-error').map(([, , value]) => value);
assert.equal(errorFlags().at(-1), false,
  'a fresh installation is a setup state, not a failure: no danger fill');
context.state.libraryStatus = {library_path: '/vol1/music', library_paths: ['/vol1/music'], exists: false, readable: false};
context.renderLibraryHealth();
assert.equal(nodes.libraryHealthStatus.textContent, '目录不存在', 'a missing configured directory remains a distinct failure');
assert.equal(errorFlags().at(-1), true, 'a configured but missing directory must still raise the danger state');
console.log('Fresh-install setup and missing-directory health states passed');
