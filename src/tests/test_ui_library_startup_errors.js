const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../app/ui');
const app = fs.readFileSync(path.join(root, 'app.js'), 'utf8').replace(/\r\n/g, '\n');
const fn = name => {
  const m = app.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert.ok(m, name + ' must be extractable');
  return m[0];
};

(async () => {
  const c = {Promise, Error, TypeError, Number, String, Object, Array, Math, Set, Map, AbortController, TextEncoder, TextDecoder, Uint8Array, setTimeout, clearTimeout};
  vm.createContext(c);
  vm.runInContext(fs.readFileSync(path.join(root, 'response_json_loader.js'), 'utf8'), c);
  vm.runInContext(fn('fetchJsonChecked'), c);
  for (const [status, body] of [[200, ''], [204, '']]) {
    c.fetch = async () => ({ok: true, status, text: async () => body});
    await assert.rejects(c.fetchJsonChecked('api/library', {}, '读取歌曲列表失败', {strictBody: true}), e => e.name === 'ResponseError');
  }
  c.fetch = async () => ({ok: false, status: 401, text: async () => '{"error":"unauthorized"}'});
  await assert.rejects(c.fetchJsonChecked('api/library'), e => e.status === 401 && /登录/.test(e.message));

  vm.runInContext(fs.readFileSync(path.join(root, 'library_response_loader.js'), 'utf8'), c);
  vm.runInContext(fn('validateLibraryResponse') + '\n' + fn('fetchLibraryResponse'), c);
  c.state = {libraryResponseCache: new Map(), libraryResponseInflight: new Map(), libraryResponseActive: {value: 0}, libraryResponseEpoch: 1};
  for (const body of ['{}', '{"items":null}', '{"items":[],"count":-1}', '{"items":[],"count":"0"}']) {
    c.state.libraryResponseCache.clear();
    c.fetch = async () => ({ok: true, status: 200, text: async () => body});
    await assert.rejects(c.fetchLibraryResponse('api/library?paged=1', '读取歌曲列表失败'));
    assert.equal(c.state.libraryResponseCache.size, 0, 'malformed library documents must not poison the cache');
  }
  for (const [url, key] of [['api/library?paged=1','items'], ['api/library/folders?paged=1','folders'], ['api/library/groups?paged=1','groups'], ['api/library/roots','roots']]) {
    for (const row of [null, [], {}, ...(['api/library/roots'].includes(url) ? [{root: {}, path: '/vol1/music'}, {root: '   '}] : [])]) {
      c.state.libraryResponseCache.clear();
      c.fetch = async () => ({ok: true, status: 200, text: async () => JSON.stringify({[key]: [row], count: 1})});
      await assert.rejects(c.fetchLibraryResponse(url, '读取失败'), /响应格式异常/);
      assert.equal(c.state.libraryResponseCache.size, 0, 'invalid rows must not make retries reuse poisoned cache');
    }
    c.state.libraryResponseCache.clear();
    c.fetch = async () => ({ok: true, status: 200, text: async () => JSON.stringify({[key]: [], count: 0})});
    const result = await c.fetchLibraryResponse(url, '读取失败');
    assert.equal(result[key].length, 0, 'a documented empty collection remains valid');
    assert.equal(c.state.libraryResponseCache.size, 1);
    const row = key === 'items' ? {id: 'track-1'} : key === 'groups' ? {name: ''} : {path: '/vol1/music'};
    c.state.libraryResponseCache.clear();
    c.fetch = async () => ({ok: true, status: 200, text: async () => JSON.stringify({[key]: [row], count: 1})});
    assert.equal((await c.fetchLibraryResponse(url, '读取失败'))[key].length, 1, 'valid nonempty documents remain usable');
  }
  const nodes = Object.fromEntries(['libraryLoadError', 'libraryLoadErrorText', 'allCount', 'dsdCount', 'recentCount', 'serverPortValue', 'emptyText'].map(id => [id, {hidden: true, textContent: ''}]));
  Object.assign(c, {$: id => nodes[id], renderLibraryHealth() {}, libraryCount: x => x || 0, setTextContentIfChanged(node, value) {if (node) node.textContent = String(value);}, scanProgressText: () => ''});
  vm.runInContext(fn('updateLibraryStatusDecorations'), c);
  c.state.libraryStatus = {count: 0, message: '音乐库已就绪'};
  c.state.libraryLoadError = '登录已失效，请重新登录';
  c.updateLibraryStatusDecorations();
  assert.equal(nodes.libraryLoadError.hidden, false);
  assert.equal(nodes.libraryLoadErrorText.textContent, c.state.libraryLoadError);
  // A later status poll must not erase a failed list request.
  c.state.libraryStatus = {count: 42, message: '音乐库已就绪'};
  c.updateLibraryStatusDecorations();
  assert.equal(nodes.libraryLoadError.hidden, false);
  c.state.libraryLoadError = '';
  c.updateLibraryStatusDecorations();
  assert.equal(nodes.libraryLoadError.hidden, true);
  assert.match(app, /libraryLoadError = String\(error\?\.message/);
  assert.match(app, /retryLibraryLoadBtn"\)\.onclick = .*requestLibraryLoad/);
  console.log('Library startup failures, response contracts and recovery checks passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
