const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

const app = fs.readFileSync(__dirname + '/../app/ui/app.js', 'utf8');
test('host handshake starts during boot before the host expires its listener', () => {
  const boot = app.slice(app.lastIndexOf('\nsetupMediaSession();'));
  assert.match(boot, /getTrimSdk\(\)/);
  assert.ok(boot.indexOf('getTrimSdk()') < boot.indexOf('requestLibraryLoad(1, false)'));
});

test('overlapping SDK loads construct only one host connector', async () => {
  let release, constructed = 0;
  const module = new Promise(resolve => { release = resolve; });
  const context = {window: {}, loadSdkModule: () => module};
  const source = app.match(/^async function getTrimSdk\([^]*?^}/m)[0]
    .replace('import("./vendor/trim-web-app.js")', 'loadSdkModule()');
  vm.createContext(context); vm.runInContext(source, context);
  const first = context.getTrimSdk(), second = context.getTrimSdk();
  release({TrimApp: class { constructor() { constructed++; } }});
  const [a, b] = await Promise.all([first, second]);
  assert.equal(a, b);
  assert.equal(constructed, 1);
});

function harness(sdk) {
  const nodes = {};
  const node = id => nodes[id] ||= {
    open: false, disabled: false, checked: false, value: '', textContent: '',
    close() { this.open = false; }, showModal() { this.open = true; },
  };
  const timers = new Map();
  const timeoutDurations = [];
  const alerts = [];
  const context = {
    $: node, state: { externalShareLocation: {path: '/vol1/music/song.flac'} },
    getTrimSdk: async () => sdk,
    collectLibraryPaths: () => ['/vol1/existing'],
    renderLibraryPathInputs: paths => { context.paths = Array.from(paths); },
    // The server-side directory browser is a separate dialog with its own fetch
    // path; the picker contract only cares that it is opened, and with which path.
    openLibraryDirBrowser: path => { context.browsedFrom = path; return true; },
    resolveTrackLocation: async () => ({path: '/vol1/music/song.flac', folder: '/vol1/music'}),
    resetExternalShareDialog: location => { context.state.externalShareLocation = location; },
    alert: message => alerts.push(message), console: {warn() {}},
    setTimeout: (callback, duration) => {
      timeoutDurations.push(duration);
      const id = {}; timers.set(id, callback); return id;
    },
    clearTimeout: id => timers.delete(id),
  };
  vm.createContext(context);
  for (const name of ['hostUnavailable', 'runTrimHostAction', 'chooseLibraryPath', 'openContainingFolder',
    'openExternalShareDetails', 'shareTrack', 'createExternalShareLink']) {
    const source = app.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'))?.[0];
    if (source) vm.runInContext(source, context);
  }
  return {context, node, alerts, timers, timeoutDurations, async flush() {
    for (let i = 0; i < 30; i++) await Promise.resolve();
  }, expire() { for (const callback of [...timers.values()]) callback(); }};
}

test('directory picker releases modal blocking and restores settings after selection', async () => {
  let h;
  h = harness({ready: async () => {}, pickUserFile: async options => {
    assert.equal(h.node('folderDialog').open, false, 'settings modal must release the host picker');
    assert.equal(options.directory, true);
    return {code: 0, data: ['/vol1/music']};
  }});
  h.node('folderDialog').open = true;
  assert.equal(await h.context.chooseLibraryPath(), true);
  assert.deepEqual(h.context.paths, ['/vol1/existing', '/vol1/music']);
  assert.equal(h.node('folderDialog').open, true);
  assert.equal(h.node('chooseLibraryPathBtn').disabled, false);
});

test('picker cancellation restores settings and preserves existing directories', async () => {
  const h = harness({pickUserFile: async () => undefined});
  h.node('folderDialog').open = true;
  assert.equal(await h.context.chooseLibraryPath(), false);
  assert.equal(h.node('folderDialog').open, true);
  assert.equal(h.context.paths, undefined);
});

test('stalled SDK readiness times out, unlocks picker and never dispatches late', async () => {
  let ready, picks = 0;
  const h = harness({ready: () => new Promise(resolve => { ready = resolve; }),
    pickUserFile: async () => { picks++; return {code: 0, data: ['/late']}; }});
  const pending = h.context.chooseLibraryPath();
  await h.flush();
  h.expire();
  await h.flush();
  assert.match(h.node('librarySettingsStatus').textContent, /超时/);
  assert.equal(await pending, false);
  assert.equal(h.node('chooseLibraryPathBtn').disabled, false);
  ready(); await h.flush();
  assert.equal(picks, 0);
});

test('containing-folder action waits for host failure and reports it', async () => {
  let reject, path;
  const h = harness({openFileManager: value => { path = value;
    return new Promise((_, fail) => { reject = fail; }); }});
  let finished = false;
  const pending = h.context.openContainingFolder('track').then(() => { finished = true; });
  await h.flush();
  assert.equal(path, '/vol1/music');
  assert.equal(finished, false, 'action must track the host handoff');
  reject(new Error('denied')); await pending;
  assert.equal(h.alerts.length, 1);
});

test('share nests every field in the data envelope the share service reads', async () => {
  const requests = [];
  const h = harness({query: async request => {
    requests.push(request);
    if (request.req.endsWith('.default')) return {result: 'succ', data: {defaultLink: 'https://share.example/'}};
    // fnOS reads share.link.create arguments from `data`. Its own file manager
    // sends {req, data:{name, files, maxAccess, passwd, validTo}}; the flat form
    // is answered with errno 3000001 "Invalid Params" while every field name is
    // still correct, which reads like a permissions problem and sent this code
    // through three unrelated fixes before the request was read off the wire.
    assert.equal(request.name, undefined, 'fields must not also sit beside req');
    assert.deepEqual(Array.from(request.data.files), ['/vol1/music/song.flac']);
    assert.equal(request.data.name, 'song.flac');
    assert.equal(request.data.maxAccess, 0);
    return {result: 'succ', data: {id: 'link-id'}};
  }});
  h.node('sharePasswordEnabled').checked = true;
  h.node('sharePasswordInput').value = 'Abcd1234';
  await h.context.createExternalShareLink();
  const create = requests.find(request => request.req.endsWith('.create'));
  assert.equal(create.data.passwd, 'Abcd1234', 'the password rides inside the envelope too');
  assert.equal(h.node('externalSharePasswordResult').hidden, false);
  assert.equal(h.node('externalShareHint').hidden, true, 'a public share host needs no warning');
  assert.equal(h.node('externalShareUrl').value, 'https://share.example/s/link-id');
  assert.equal(h.node('externalShareResult').hidden, false);
});

test('share falls back to the page origin when the host will not name a default link', async () => {
  const h = harness({query: async request => {
    if (request.req.endsWith('.default')) return {result: 'fail', errmsg: 'unsupported'};
    return {result: 'succ', data: {id: 'link-id'}};
  }});
  // The page is served from the NAS itself, and /s/<id> is served from the same
  // origin, so a host that cannot answer share.link.default still leaves a usable
  // link — that is the phone case, where only the Flutter bridge is present.
  h.context.location = {origin: 'https://nas.example'};
  await h.context.createExternalShareLink();
  assert.equal(h.node('externalShareUrl').value, 'https://nas.example/s/link-id');
});

test('a LAN share link warns that it only opens on the same network', async () => {
  const h = harness({query: async request => {
    if (request.req.endsWith('.default')) return {result: 'succ', data: {defaultLink: 'http://192.168.1.5:5666'}};
    return {result: 'succ', data: {id: 'link-id'}};
  }});
  await h.context.createExternalShareLink();
  // A NAS that has no remote-access address answers with its LAN one; the link
  // still works, but only from the same network. Saying so is what keeps
  // "分享出去打不开" from looking like a broken panel.
  assert.equal(h.node('externalShareHint').hidden, false);
  assert.match(h.node('externalShareHint').textContent, /局域网/);
  assert.equal(h.node('externalShareUrl').value, 'http://192.168.1.5:5666/s/link-id');
});

test('a host without the share service names the path that still works', async () => {
  let details = 0;
  const h = harness({showFileDetails: async () => { details += 1; return true; }});
  // No query method at all, so runTrimHostAction reports hostUnavailable. The
  // file-details fallback is not offered: on that host the file manager's menu is
  // unreachable as well, so it would only replace one dead end with another.
  await h.context.createExternalShareLink();
  assert.equal(details, 0);
  assert.match(h.node('externalShareStatus').textContent, /文件管理/);
});

test('failed share defaults do not create an unusable external link', async () => {
  let creates = 0;
  const h = harness({query: async request => {
    if (request.req.endsWith('.create')) creates++;
    return {result: 'fail', errmsg: 'denied'};
  }, showFileDetails: async () => {}});
  await h.context.createExternalShareLink();
  assert.equal(creates, 0);
  assert.equal(h.node('createExternalShare').disabled, false);
});

test('share fallback releases modal before opening documented host file details', async () => {
  let h, opened = false;
  h = harness({showFileDetails: async paths => {
    assert.equal(h.node('externalShareDialog').open, false);
    assert.deepEqual(Array.from(paths), ['/vol1/music/song.flac']);
    opened = true;
  }});
  h.node('externalShareDialog').open = true;
  assert.equal(await h.context.openExternalShareDetails(), true);
  assert.equal(opened, true);
  assert.equal(h.node('externalShareDialog').open, true);
});

test('stalled folder handoff returns an actionable timeout', async () => {
  const h = harness({openFileManager: () => new Promise(() => {})});
  const pending = h.context.openContainingFolder('track');
  await h.flush(); h.expire(); await h.flush();
  assert.equal(h.alerts.length, 1);
  assert.match(h.alerts[0], /超时/);
  await pending;
});

test('picker timeout ignores late selection and restores the settings modal', async () => {
  let select;
  const h = harness({pickUserFile: () => new Promise(resolve => { select = resolve; })});
  h.node('folderDialog').open = true;
  const pending = h.context.chooseLibraryPath();
  await h.flush();
  assert.equal(h.node('folderDialog').open, false);
  assert.deepEqual(h.timeoutDurations, [10000, 120000], 'readiness and picker have separate bounded waits');
  assert.equal(await h.context.chooseLibraryPath(), false, 'duplicate click must not open another picker');
  h.expire(); await h.flush();
  assert.equal(await pending, false);
  assert.equal(h.node('folderDialog').open, true);
  select({code: 0, data: ['/late']}); await h.flush();
  assert.equal(h.context.paths, undefined);
  assert.equal(h.timers.size, 0);
});

test('standalone browser and authorization denial preserve configured roots', async () => {
  let calls = 0;
  const sdk = {isStandaloneWeb: true, pickUserFile: async () => {
    calls++; return {code: 5, msg: '授权被拒绝'};
  }};
  const h = harness(sdk);
  // A standalone browser has no fnOS host at all, so the picker cannot be
  // offered: the settings pane must hand over to the server-side browser
  // instead of doing nothing.
  assert.equal(await h.context.chooseLibraryPath(), false);
  assert.equal(calls, 0);
  assert.equal(h.context.browsedFrom, '', 'standalone browser falls back to the server directory browser');
  assert.equal(h.context.paths, undefined, 'the fallback must not invent a directory');
  sdk.isStandaloneWeb = false;
  h.context.browsedFrom = undefined;
  assert.equal(await h.context.chooseLibraryPath(), false);
  // A denial is a different failure: the host was reached and said no, so it
  // must be reported rather than papered over by another dialog.
  assert.equal(h.node('librarySettingsStatus').textContent, '授权被拒绝');
  assert.equal(h.context.browsedFrom, undefined, 'a denial must not open the fallback browser');
  assert.equal(h.context.paths, undefined);
});

test('share query timeout reenables creation and awaits details fallback', async () => {
  let details = 0;
  const h = harness({query: () => new Promise(() => {}),
    showFileDetails: async () => { details++; }});
  const pending = h.context.createExternalShareLink();
  await h.flush(); h.expire(); await h.flush(); await pending;
  assert.equal(h.node('createExternalShare').disabled, false);
  assert.equal(details, 1);
  assert.equal(h.node('externalShareUrl').value, '');
  assert.equal(h.timers.size, 0);
});

async function bundledSdk() {
  const source = fs.readFileSync(__dirname + '/../app/ui/vendor/trim-web-app.js', 'utf8');
  const window = {addEventListener() {}};
  window.parent = window;
  const context = {window, navigator: {userAgent: ''}, console};
  vm.createContext(context);
  vm.runInContext(source.replace(/export\{[^}]+\};?\s*$/, 'globalThis.TrimApp = Ve;'), context);
  const sdk = new context.TrimApp();
  await sdk.ready();
  return sdk;
}

test('bundled fnOS SDK forwards query fields unchanged to the host connector', async () => {
  const sdk = await bundledSdk();
  let forwarded;
  sdk.osConnector = {methods: {query: async request => {
    forwarded = request; return {result: 'succ', data: {id: 'id'}};
  }}};
  const request = {req: 'appcgi.sharesvr.share.link.create', files: ['/vol1/music/song.flac'], maxAccess: 0};
  await sdk.query(request);
  assert.equal(forwarded, request, 'the SDK does not convert gateway-style data envelopes');
});

test('official SDK ready waits on the existing initialization without retrying it', async () => {
  const sdk = await bundledSdk();
  let release, initialized = 0, completed = 0;
  sdk.initPromise = new Promise(resolve => { release = resolve; });
  sdk.init = () => { initialized++; };
  const first = sdk.ready().then(() => { completed++; });
  const second = sdk.ready().then(() => { completed++; });
  for (let i = 0; i < 10; i++) await Promise.resolve();
  assert.equal(completed, 0, 'ready has no immediate fallback while initialization is pending');
  assert.equal(initialized, 0, 'repeated ready calls do not restart the SDK connector');
  release(); await Promise.all([first, second]);
  assert.equal(completed, 2);
});

test('real SDK can be manually retried after readiness timeout without replaying old picker', async () => {
  const sdk = await bundledSdk();
  let release, picks = 0;
  sdk.initPromise = new Promise(resolve => { release = resolve; });
  sdk.isStandaloneWeb = false;
  sdk.osConnector = {methods: {pickUserFile: async () => {
    picks++; return {code: 0, data: ['/vol1/recovered']};
  }}};
  const h = harness(sdk);
  const pending = h.context.chooseLibraryPath();
  await h.flush();
  assert.deepEqual(h.timeoutDurations, [10000]);
  h.expire(); await h.flush();
  assert.equal(await pending, false);
  assert.equal(h.node('chooseLibraryPathBtn').disabled, false);
  release(); await h.flush();
  assert.equal(picks, 0, 'late readiness must not automatically replay a timed-out request');
  assert.equal(await h.context.chooseLibraryPath(), true);
  assert.equal(picks, 1, 'only the explicit retry opens the picker');
  assert.deepEqual(h.context.paths, ['/vol1/existing', '/vol1/recovered']);
  assert.equal(h.timers.size, 0);
});
