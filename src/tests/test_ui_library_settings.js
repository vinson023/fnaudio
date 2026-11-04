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

// A status that never arrived is a third state, distinct from both "no directory
// configured" and "the configured directory is gone".  The server always sends
// library_paths (an array, possibly empty), so a payload without it means the
// request failed or has not answered yet.  Counting its paths as zero used to
// print "0 configured directories, supports 0 formats" under a danger fill.
context.state.libraryStatus = null;
context.renderLibraryHealth();
assert.equal(nodes.libraryHealthStatus.textContent, '音乐库状态未就绪',
  'a status that never arrived must not be described as an empty library');
assert.match(nodes.libraryHealthDetail.textContent, /还没有读取到音乐库状态/,
  'a pending status must say so instead of counting zero paths');
assert.equal(errorFlags().at(-1), false,
  'a request that has not answered is not a fault: no danger fill');
assert.equal(nodes.libraryScanNowBtn.disabled, true,
  'scanning is meaningless before the status has been read');

// The failed-request shape is an empty object rather than null, and it must land
// in the same state: neither the danger fill nor the zero-path sentence.
context.state.libraryStatus = {};
context.renderLibraryHealth();
assert.equal(nodes.libraryHealthStatus.textContent, '音乐库状态未就绪',
  'an empty payload object is the same pending state, not a configured library');
assert.equal(errorFlags().at(-1), false,
  'an empty payload object must not paint the danger fill');
assert.doesNotMatch(nodes.libraryHealthDetail.textContent, /0 个配置目录/,
  'the zero-path sentence belongs to a real payload with an empty list, not to a missing one');

// The real payload with an empty list keeps the first-run wording and the
// "configured but missing" case keeps the danger fill, both pinned above.
console.log('Pending-status health state passed');
