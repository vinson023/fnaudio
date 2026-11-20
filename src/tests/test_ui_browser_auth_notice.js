// 会话失效时的提示必须「说得出下一步」，而且只响一次。
//
// 背景：fnOS 的短令牌几分钟就过期。飞牛 app 的 WebView 里没有 FnAudioNative 桥，
// 宿主 SDK 也明确拒绝续期（trim-web-app.js: "refreshToken is not supported on
// mobile platform"），页面重载拿回来的还是同一个 fnos-token。所以 401 之后唯一
// 诚实的做法是把「重新打开 fnAudio」说出来，而不是让按钮看着像死的、或者用
// 「请检查与 NAS 的连接」把人带偏。
const fs = require("fs");
const path = require("path");
const assert = require("assert").strict;
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8").replace(/\r\n/g, "\n");

const start = source.indexOf("let browserAuthFailureNoticedAt = 0;");
const end = source.indexOf("function apiFetch(", start);
assert.ok(start > 0 && end > start, "the auth notice helper must stay a standalone block ahead of apiFetch");
const block = source.slice(start, end);

function harness({ bridge = false, now = 1000 } = {}) {
  const notices = [];
  const clock = { value: now };
  const context = {
    window: bridge ? { FnAudioNative: { refreshSession() {} } } : {},
    showAppError: message => { notices.push(String(message)); },
    Date: { now: () => clock.value },
  };
  vm.createContext(context);
  vm.runInContext(`${block}\nthis.noteBrowserAuthFailure = noteBrowserAuthFailure; this.browserAuthFailedRecently = browserAuthFailedRecently;`, context);
  return { context, notices, now: clock };
}

// 1) 没有桥 + 401：说一次，而且要说清怎么恢复。
{
  const h = harness();
  const response = { status: 401 };
  assert.equal(h.context.noteBrowserAuthFailure(response), response, "the response must be handed back untouched");
  assert.equal(h.notices.length, 1, "a 401 without a bridge must be reported");
  assert.match(h.notices[0], /重新打开 fnAudio/, "the notice must name the one action that actually works");
  assert.doesNotMatch(h.notices[0], /检查与 NAS 的连接/, "blaming the NAS connection sends the user the wrong way");
}

// 2) 一串 401（列表 + 封面 + 队列保存同时到）只响一次。
{
  const h = harness();
  for (let i = 0; i < 5; i += 1) h.context.noteBrowserAuthFailure({ status: 401 });
  assert.equal(h.notices.length, 1, "a burst of 401s must not stack banners");
}

// 3) 一分钟后再失效，还要能再提醒一次。
{
  const h = harness();
  h.context.noteBrowserAuthFailure({ status: 401 });
  h.now.value += 61000;
  h.context.noteBrowserAuthFailure({ status: 401 });
  assert.equal(h.notices.length, 2, "a later expiry must be reported again");
}

// 4) 有原生桥时不插话：那条路径自己会续期，失败了也有自己的文案。
{
  const h = harness({ bridge: true });
  h.context.noteBrowserAuthFailure({ status: 401 });
  assert.equal(h.notices.length, 0, "the native path owns its own failure reporting");
}

// 5) 非 401 一律不插话。
{
  const h = harness();
  for (const status of [200, 403, 500, 0]) h.context.noteBrowserAuthFailure({ status });
  h.context.noteBrowserAuthFailure(null);
  h.context.noteBrowserAuthFailure(undefined);
  assert.equal(h.notices.length, 0, "only 401 means the session is gone");
}

// 6) 四个运输键在同一时刻要认得「刚才是会话失效」，别拿通用文案盖掉那句可执行的。
{
  const h = harness();
  assert.equal(h.context.browserAuthFailedRecently(), false, "nothing has failed yet");
  h.context.noteBrowserAuthFailure({ status: 401 });
  assert.equal(h.context.browserAuthFailedRecently(), true, "a fresh 401 must be visible to the transport callers");
  h.now.value += 4000;
  assert.equal(h.context.browserAuthFailedRecently(), false, "the window must lapse so a real network failure still speaks");
}

// 7) 源码层面：浏览器路径的每个出口都要过这道关，四个运输键都要让位。
for (const marker of [
  "return browserFetch(input, init).then(noteBrowserAuthFailure);",
]) {
  assert.ok(source.includes(marker), `every browser fetch exit must pass through the auth notice: ${marker}`);
}
assert.equal(
  (source.match(/return browserFetch\(input, init\);/g) || []).length,
  0,
  "no browser fetch exit may bypass the auth notice",
);
for (const caller of ["上一曲", "下一曲", "循环模式", "随机播放"]) {
  const pattern = new RegExp(`browserAuthFailedRecently\\(\\)\\) showAppError\\("[^"]*${caller}`);
  assert.match(source, pattern, `the ${caller} failure message must defer to the session notice`);
}

console.log("Browser auth notice checks passed.");
