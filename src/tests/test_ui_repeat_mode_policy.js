const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const source = fs.readFileSync(require('path').join(__dirname, '..', 'app', 'ui', 'repeat_mode_policy.js'), 'utf8');
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioRepeatModePolicy;

assert.strictEqual(policy.normalize('off'), 'off');
assert.strictEqual(policy.normalize('all'), 'all');
assert.strictEqual(policy.normalize('one'), 'one');
assert.strictEqual(policy.normalize('invalid'), 'off');
assert.strictEqual(policy.next('off'), 'all');
assert.strictEqual(policy.next('all'), 'one');
assert.strictEqual(policy.next('one'), 'off');
assert.strictEqual(policy.label('all'), '列表循环');
assert.strictEqual(policy.action('one'), '关闭循环播放');
assert.ok(policy.iconMarkup('off').includes('M17 2l4 4-4 4'));
assert.notStrictEqual(policy.iconMarkup('one'), policy.iconMarkup('off'));
console.log('Repeat mode policy regression checks passed.');
