const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const ui = path.resolve(__dirname, '../app/ui');
const app = fs.readFileSync(path.join(ui, 'app.js'), 'utf8').replace(/\r\n/g, '\n');
function source(name) {
  const match = app.match(new RegExp('^(?:async )?function ' + name + '\\([^]*?^}', 'm'));
  assert.ok(match, name + ' must be extractable');
  return match[0];
}

function harness(t, view, respond, configuredRoots = []) {
  const requests = [];
  const timers = new Set();
  const nodes = Object.fromEntries([
    'libraryLoadError', 'libraryLoadErrorText', 'retryLibraryLoadBtn', 'empty',
    'serverPortValue', 'allCount', 'dsdCount', 'recentCount', 'emptyText', 'searchInput',
  ].map(id => [id, { hidden: true, textContent: '', value: '' }]));
  const state = {
    view, page: 1, pageSize: 60, folderPage: 1, folderPageSize: 60,
    folderRoot: '', folderPath: '', groupName: '', sortKey: 'title', sortDir: 'asc',
    pageItems: [], items: [], groupRows: [], folderRows: [], folderRootRows: [],
    pageTotal: 0, libraryRequestSeq: 0, libraryLoading: false, libraryLoadError: '',
    libraryInteractionBlocked: false, libraryAbortController: null,
    libraryLoadPromise: null, libraryLoadKey: '', itemCache: new Map(), albumMetadata: new Map(),
    libraryResponseCache: new Map(), libraryResponseInflight: new Map(),
    libraryResponseActive: { value: 0 }, libraryResponseEpoch: 1,
    libraryStatus: { library_path: configuredRoots[0] || '', library_paths: configuredRoots },
  };
  let entries = 0;
  const c = {
    state, URLSearchParams, AbortController, TextEncoder, TextDecoder, Uint8Array,
    Map, Set, Promise, Error, TypeError, Number, String, Object, Array, Math,
    groupViews: { albums: 'album', artists: 'artist', composers: 'composer', genres: 'genre' },
    $: id => nodes[id], displayText: String, sortDirectionFactor: () => 1,
    scanProgressText: () => '', renderLibraryHealth() {}, currentItem: () => null,
    browseCursorForPage: () => '', rememberBrowsePageCursor() {},
    cancelReferencedItemHydrationSchedule() {}, cancelMetadataRowRender() {},
    cancelVisibleMetadataPrefetch() {}, cancelLibraryNavigationHoverDwell() {},
    scheduleReferencedItemHydration() {}, scheduleVisibleMetadataPrefetch() {},
    scheduleLibraryPageSnapshot() {}, refreshLibraryStatus() {},
    armLibraryInteractionHold() {
      // A cached malformed singleton used to recurse forever in microtasks,
      // starving even a real timeout. Bound entries so regressions fail promptly.
      if (++entries > 8) throw new Error('library worker entry budget exceeded: possible self-loop');
    },
    setTimeout(callback, ms) {
      const timer = setTimeout(() => { timers.delete(timer); callback(); }, ms);
      timers.add(timer);
      return timer;
    },
    clearTimeout(timer) { clearTimeout(timer); timers.delete(timer); },
    async fetch(url, init) {
      assert.notEqual(init?.signal?.aborted, true, 'a retry must own a live signal');
      const request = new URL(url, 'http://library.test/');
      requests.push(request);
      const body = respond(request);
      return { ok: true, status: 200, text: async () => JSON.stringify(body) };
    },
  };
  vm.createContext(c);
  t.after(() => {
    state.libraryAbortController?.abort();
    for (const timer of timers) clearTimeout(timer);
  });
  for (const file of [
    'response_json_loader.js', 'library_response_loader.js', 'library_render_policy.js',
    'library_load_key.js', 'creator_view_policy.js', 'library_query_params.js',
    'library_full_list_policy.js', 'library_metadata_merge_policy.js',
    'item_cache.js', 'lru_cache.js',
  ]) {
    vm.runInContext(fs.readFileSync(path.join(ui, file), 'utf8'), c, { filename: file });
  }
  state.itemCache = c.fnAudioItemCache(12000);
  state.libraryResponseCache = c.fnAudioLruCache(48);
  // Execute the real validation/cache/load chain and the real error DOM update.
  // Full list rendering and background metadata work are outside this test.
  c.render = () => c.updateLibraryStatusDecorations();
  for (const name of [
    'isCreatorView', 'currentCreatorName', 'isCreatorAllTracksView',
    'isPagedGroupListing', 'isPagedTrackListing', 'currentQueryText', 'libraryPageNumber',
    'libraryQueryParamsFor', 'folderNavigationUrls', 'libraryCount',
    'hasVisibleLibraryPresentation', 'configuredLibraryRoots', 'libraryLoadRequestKey',
    'fetchJsonChecked', 'validateLibraryResponse', 'fetchLibraryResponse',
    'cacheLibraryItems', 'mergeAuthoritativePageItems', 'setTextContentIfChanged',
    'updateLibraryStatusDecorations', 'loadPagedLibraryWorker', 'loadPagedLibrary',
    'requestLibraryLoad',
  ]) vm.runInContext(source(name), c, { filename: 'app.js:' + name });
  const retryBinding = app.match(/^\$\("retryLibraryLoadBtn"\)\.onclick = .*;$/m);
  assert.ok(retryBinding, 'the real retry button binding must exist');
  vm.runInContext(retryBinding[0], c);
  return { c, state, nodes, requests, entries: () => entries };
}

async function settles(operation) {
  let timer;
  try {
    return await Promise.race([
      operation,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error('library load did not settle (possible promise self-cycle)')), 1000);
      }),
    ]);
  } finally { clearTimeout(timer); }
}

function assertReleased(h) {
  assert.equal(h.state.libraryLoading, false);
  assert.equal(h.state.libraryInteractionBlocked, false);
  assert.equal(h.state.libraryAbortController, null);
  assert.equal(h.state.libraryLoadPromise, null);
  assert.equal(h.state.libraryLoadKey, '');
  assert.equal(h.state.libraryResponseInflight.size, 0);
  assert.equal(h.state.libraryResponseActive.value, 0);
}

const root = '/vol1/music';
const track = { id: 'track-1', title: 'Recovered track', root, folder: '', path: root + '/song.flac' };
function folderResponse(request, rootRow = { root, path: root, name: 'music' }) {
  if (request.pathname === '/api/library/roots') return { roots: [rootRow] };
  assert.equal(request.searchParams.get('root'), root, 'single-root navigation must preserve the selected root');
  assert.equal(request.searchParams.get('paged'), '1');
  if (request.pathname === '/api/library/folders') return { folders: [], count: 0, paged: true, limit: 60, offset: 0 };
  assert.equal(request.pathname, '/api/library');
  return { items: [track], count: 1, paged: true, limit: 60, offset: 0 };
}

for (const [label, view, field, row] of [
  ['root without a path', 'folders', 'roots', {}],
  ['null root', 'folders', 'roots', null],
  ['array root', 'folders', 'roots', []],
  ['blank root', 'folders', 'roots', { root: '   ' }],
  ['non-string root with valid path', 'folders', 'roots', { root: 17, path: root }],
  ['valid root with non-string path', 'folders', 'roots', { root, path: 17 }],
  ['null root with valid path', 'folders', 'roots', { root: null, path: root }],
  ['valid root with null path', 'folders', 'roots', { root, path: null }],
  ['null group', 'albums', 'groups', null],
  ['array group', 'albums', 'groups', []],
  ['group without a name', 'albums', 'groups', {}],
  ['non-string group name', 'albums', 'groups', { name: 17 }],
]) {
  test(label + ': real worker exposes failure, then retry fetches and recovers', async t => {
    let broken = true;
    const endpoint = field === 'roots' ? '/api/library/roots' : '/api/library/groups';
    const h = harness(t, view, request => {
      if (broken && request.pathname === endpoint) {
        return { [field]: [row], ...(field === 'roots' ? {} : { count: 1 }) };
      }
      if (field === 'roots') return folderResponse(request);
      assert.equal(request.pathname, '/api/library/groups');
      assert.equal(request.searchParams.get('paged'), '1');
      return { groups: [{ name: 'Recovered album', count: 1 }], count: 1, paged: true, limit: 60, offset: 0 };
    });
    await assert.rejects(settles(h.c.loadPagedLibrary(1, false)), /响应格式异常/);
    assertReleased(h);
    assert.equal(h.requests.length, 1, 'one malformed response must terminate this load');
    assert.equal(h.state.libraryResponseCache.size, 0, 'malformed rows must not poison retry cache');
    assert.equal(h.nodes.libraryLoadError.hidden, false, 'the worker must expose its error');
    assert.match(h.nodes.libraryLoadErrorText.textContent, /响应格式异常/);
    assert.equal(h.nodes.libraryLoadErrorText.textContent, h.state.libraryLoadError);

    // Exercise the actual button handler without refresh or manual cache clearing.
    broken = false;
    await settles(h.nodes.retryLibraryLoadBtn.onclick());
    assertReleased(h);
    assert.equal(h.state.libraryLoadError, '');
    assert.equal(h.nodes.libraryLoadError.hidden, true, 'successful retry must hide the old error');
    assert.equal(h.nodes.libraryLoadErrorText.textContent, '');
    assert.equal(h.requests.filter(request => request.pathname === endpoint).length, 2,
      'retry must fetch the repaired response from the network');
    assert.equal(h.state.pageTotal, 1);
    if (field === 'roots') {
      assert.equal(h.state.folderRoot, root);
      assert.equal(h.state.pageItems[0].id, 'track-1');
      assert.equal(h.requests.length, 4, 'failed roots + repaired roots + folders/tracks pair');
    } else {
      assert.equal(h.state.groupRows[0].name, 'Recovered album');
      assert.equal(h.requests.length, 2);
    }
  });
}

for (const [label, rootRow, configured] of [
  ['root-only response', { root, name: 'music' }, []],
  ['path-only response', { path: root, name: 'music' }, []],
  ['already configured root', { root, path: root, name: 'music' }, [root]],
]) {
  test(label + ': single-root navigation settles without a self-cycle', async t => {
    const h = harness(t, 'folders', request => folderResponse(request, rootRow), configured);
    await settles(h.c.loadPagedLibrary(1, false));
    assertReleased(h);
    assert.equal(h.entries(), 2, 'root selection must transition to the content worker exactly once');
    assert.equal(h.state.folderRoot, root);
    assert.equal(h.state.folderPath, '');
    assert.equal(h.state.pageItems[0].id, 'track-1');
    assert.equal(h.state.pageTotal, 1);
    assert.equal(h.nodes.libraryLoadError.hidden, true);
    assert.equal(h.state.libraryLoadError, '');
    assert.equal(h.requests.filter(request => request.pathname === '/api/library/roots').length,
      configured.length ? 0 : 1);
    assert.equal(h.requests.filter(request => request.pathname === '/api/library/folders').length, 1);
    assert.equal(h.requests.filter(request => request.pathname === '/api/library').length, 1);
  });
}
