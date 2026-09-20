const fs = require('fs'); const path = require('path'); const vm = require('vm'); const assert = require('assert');
const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'ui', 'library_sort_options_policy.js'), 'utf8');
const context = { globalThis: {} }; vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioLibrarySortOptionsPolicy;
assert.strictEqual(JSON.stringify(policy.options('albums')), JSON.stringify([['album', '按专辑名']]));
assert.strictEqual(JSON.stringify(policy.options('albums', { hasGroupName: true })), JSON.stringify([['title','按标题'],['added','按加入时间'],['artist','按艺术家'],['album','按专辑'],['format','按格式'],['track_no','按歌曲序号']]));
assert.strictEqual(policy.defaultKey('albums', { albumDetail: true }), 'track_no');
assert.strictEqual(policy.defaultKey('folders', { folderPath: '/music' }), 'track_no');
console.log('Library sort options policy regression checks passed.');
