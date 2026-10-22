const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('app/ui/app.js', 'utf8');
const match = app.match(/^async function refreshVisibleMetadataProjection\b[\s\S]*?^}/m);
assert.ok(match, 'metadata completion must refresh authoritative visible artwork');

async function run({ stale = false, unchanged = false, clearsThumbnail = false, failed = false } = {}) {
  const item = { id: 'wav1', title: 'Song', cover_url: 'cover/wav1?v=old', cover_thumbnail_url: '' };
  const queued = { ...item };
  if (clearsThumbnail) item.cover_thumbnail_url = 'cover-asset/obsolete?size=160';
  const state = { pageItems: [item], libraryRequestSeq: 3, libraryLoading: false,
    itemCache: new Map(), queue: [queued] };
  const calls = [];
  const context = { state, isPagedTrackListing: () => true,
    fetchLibraryItemsByIds: async ids => {
      assert.deepEqual(Array.from(ids), ['wav1']);
      if (failed) throw new Error('temporary proxy failure');
      if (stale) state.libraryRequestSeq++;
      return [unchanged ? { ...item } : { ...item, cover_url: 'metadata/artwork/new', cover_thumbnail_url: clearsThumbnail ? '' : 'cover-asset/new?size=160' }];
    }, invalidateTrackRowsMarkup: () => calls.push('invalidate'),
    scheduleMetadataRowRender: (id, fields) => calls.push([id, Array.from(fields)]),
    restoreLibraryNowPlaying: () => calls.push('now'),
  };
  vm.runInNewContext(match[0], context);
  const ok = await context.refreshVisibleMetadataProjection();
  if (stale || unchanged || failed) {
    assert.equal(item.cover_url, 'cover/wav1?v=old');
    assert.deepEqual(calls, []);
    if (failed) assert.equal(ok, false, 'failed projection must remain retryable');
  } else {
    assert.equal(item.cover_thumbnail_url, clearsThumbnail ? '' : 'cover-asset/new?size=160');
    assert.equal(queued.cover_thumbnail_url, item.cover_thumbnail_url);
    assert.equal(state.itemCache.get('wav1'), item);
    assert.ok(calls.some(call => Array.isArray(call) && call[0] === 'wav1'));
  }
}
async function testWholePage() {
  const items = Array.from({length: 120}, (_, i) => ({id: String(i), cover_url: 'old'}));
  let batches = 0;
  const context = { state: {pageItems: items, libraryRequestSeq: 1, queue: [], itemCache: new Map()},
    isPagedTrackListing: () => true,
    fetchLibraryItemsByIds: async ids => { batches++; assert.ok(ids.length <= 100); return ids.map(id => ({id, cover_url: 'new'})); },
    invalidateTrackRowsMarkup() {}, scheduleMetadataRowRender() {}, restoreLibraryNowPlaying() {} };
  vm.runInNewContext(match[0], context);
  assert.equal(await context.refreshVisibleMetadataProjection(), true);
  assert.equal(batches, 2);
  assert.ok(items.every(item => item.cover_url === 'new'), 'all 120 rows must recover');
}
async function testRevisionRetry() {
  const statusFunction = app.match(/^async function refreshLibraryStatus\b[\s\S]*?^}/m)[0];
  const state = { libraryStatusRequestToken: 0, metadataProjectionSignature: 'old', pageItems: [{}] };
  let attempts = 0;
  const context = { state, AbortController,
    fetch: async () => ({ok: true}),
    fnAudioResponseJsonLoader: {read: async ({request}) => ({response: await request, data: {scanning: false}})},
    metadataProjectionIsDue: () => true, fetchMetadataProjectionStatus: async () => ({}),
    metadataProjectionSignature: () => 'new', updateLibraryStatusDecorations() {},
    retryCurrentTrackMetadataAfterRecovery() {}, invalidateLibraryResponseCacheForMetadataRevision() {},
    refreshVisibleMetadataProjection: async () => ++attempts > 1,
    scheduleVisibleMetadataPrefetch() {},
  };
  vm.runInNewContext(statusFunction, context);
  await context.refreshLibraryStatus();
  assert.equal(state.metadataProjectionSignature, 'old', 'do not consume a failed revision refresh');
  await context.refreshLibraryStatus();
  assert.equal(attempts, 2);
  assert.equal(state.metadataProjectionSignature, 'new');
}
(async () => {
  await run();
  await run({ stale: true });
  await run({ unchanged: true });
  await run({ clearsThumbnail: true });
  await run({ failed: true });
  await testWholePage();
  await testRevisionRetry();
  assert.match(app, /await refreshVisibleMetadataProjection\(\)/, 'wire refresh to metadata revisions');
  console.log('Metadata artwork refresh checks passed.');
})().catch(error => { console.error(error); process.exitCode = 1; });
