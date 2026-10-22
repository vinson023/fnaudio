const fs = require('fs'); const path = require('path'); const vm = require('vm'); const assert = require('assert');
const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'ui', 'host_privacy_policy.js'), 'utf8');
const context = { globalThis: {} }; vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioHostPrivacyPolicy;
for (const host of ['localhost', '127.0.0.1', '::1', 'nas.local', '10.1.2.3', '172.16.0.1', '192.168.100.2', '169.254.1.1', 'fc00::1', 'fd12:3456::1', 'fe80::1']) assert.strictEqual(policy.isPrivateHost(host), true);
for (const host of ['172.15.0.1', '172.32.0.1', '192.167.1.1', '198.51.100.2', '8.8.8.8', '2001:4860:4860::8888', '999.1.1.1']) assert.strictEqual(policy.isPrivateHost(host), false);
assert.strictEqual(policy.isPrivateHost({}), false);
console.log('Host privacy policy regression checks passed.');
