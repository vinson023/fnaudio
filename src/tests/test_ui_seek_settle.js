// R594: the seek rail must stop following the player for a moment after a seek.
//
// `commitSeek` dispatches the seek and clears `state.seeking` on the same tick, so
// every repaint path went back to trusting the player's position immediately.  The
// player needs a tick or two to actually move, so the rail was redrawn from the OLD
// position: the thumb snapped back to where it started and then jumped to where the
// finger left it -- one visible stutter per seek.
//
// Audio Station guards the same thing with a 200 ms window after the seek
// (`widget/MediaSeekBar.setProgress` + `getMIsWaitingForSeekCompleted`, which keys
// off `mLatestSeekTimeStamp`).  `seekPositionIsSettled()` is that window, and it is
// the single predicate all four repaint paths now ask.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const app = fs.readFileSync("app/ui/app.js", "utf8");
const css = fs.readFileSync("app/ui/app.css", "utf8");

function functionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for the seek-settle regression`);
  return match[0];
}

const predicateSource = functionSource("seekPositionIsSettled");

// A controllable clock: the window is 200 ms, and a real Date would make "just
// before" and "just after" depend on how long the test itself takes.
function build(state) {
  const clock = { now: 1000000 };
  class FakeDate extends Date {
    static now() { return clock.now; }
  }
  const context = { state, clock, Date: FakeDate, Number };
  vm.createContext(context);
  vm.runInContext(`${predicateSource}\nglobalThis.h = { settled: seekPositionIsSettled };`, context);
  return { ...context.h, clock };
}

// --- the predicate ---------------------------------------------------------

{
  // While the finger is down nothing the player says is worth painting.
  const env = build({ seeking: true, seekSettledAt: 0 });
  assert.equal(env.settled(), false, "a rail under the finger must not follow the player");
}

{
  // The seek went out this instant: the player is still reporting the old position.
  const env = build({ seeking: false, seekSettledAt: 1000000 });
  assert.equal(env.settled(), false, "the tick right after a seek must not be painted");
  env.clock.now = 1000150;
  assert.equal(env.settled(), false, "150 ms after the seek is still inside the window");
  env.clock.now = 1000201;
  assert.equal(env.settled(), true, "201 ms after the seek the rail follows again");
}

{
  // No seek has ever been sent.  This is the case a naive
  // `Date.now() - state.seekSettledAt > 200` gets wrong: undefined makes the
  // difference NaN, `NaN > 200` is false, and the rail would freeze forever.
  assert.equal(build({ seeking: false, seekSettledAt: 0 }).settled(), true, "a zero stamp means settled");
  assert.equal(build({ seeking: false }).settled(), true, "a missing stamp means settled");
  assert.equal(build({ seeking: false, seekSettledAt: "nonsense" }).settled(), true, "a non-numeric stamp means settled");
  assert.equal(build({ seeking: false, seekSettledAt: -5 }).settled(), true, "a negative stamp means settled");
}

{
  // Pure: four repaint paths call it per tick, so calling it twice in a row must
  // not consume the deadline and let the second call through.
  const env = build({ seeking: false, seekSettledAt: 1000000 });
  assert.equal(env.settled(), false);
  assert.equal(env.settled(), false, "the predicate must not consume its own window");
}

// --- the wiring ------------------------------------------------------------

{
  const commit = functionSource("commitSeek");
  assert.match(commit, /state\.seekSettledAt = Date\.now\(\);/, "commitSeek must record when the seek went out");
  assert.match(commit, /state\.seeking = false;[\s\S]{0,240}state\.seekSettledAt = Date\.now\(\);/, "the stamp is set on the same path that clears `seeking`");
  // The stamp has to survive the early return for "no duration", or a seek on a
  // track whose duration is not known yet would leave the window unarmed.
  assert.ok(
    commit.indexOf("if (!duration) return;") < commit.indexOf("state.seekSettledAt = Date.now();"),
    "the stamp belongs after the duration guard, not before it",
  );
}

{
  // Every place that repaints the rail has to ask the predicate.  Four sites used to
  // spell the condition out as `!state.seeking`, which is exactly the copy that made
  // the second state impossible to add in one place.
  const bare = app.match(/!state\.seeking/g) || [];
  assert.deepEqual(bare, [], "no repaint path may test `!state.seeking` directly any more");
  // Six call sites: the native status snapshot, the remote tick (its `seconds`
  // gate and its write), the renderer tick (same two), and the audio timeupdate.
  const uses = app.match(/seekPositionIsSettled\(\)/g) || [];
  assert.equal(uses.length, 7, `one definition plus six repaint paths must ask the predicate, found ${uses.length}`);
  assert.equal((app.match(/if \(seekPositionIsSettled\(\)\) \{/g) || []).length, 3, "three of the sites gate a block, not a single write");
}

// --- the hit area ----------------------------------------------------------

{
  // The input is the hit area, the track is what you see.  8px around a 4px rail
  // was a 2:1 ratio; the phone row is 38px now, which is the whole row, so it
  // costs no layout change at all.
  // Anchored on the phone-only declarations (`appearance:none`), not on the media
  // query: the base sheet has a `.progress input` rule too, and a lazy scan from
  // the first `@media(max-width:760px)` finds that one first.
  const phoneSeek = css.match(/\.progress input\{([^}]*-webkit-appearance:none[^}]*)\}/);
  assert.ok(phoneSeek, "the phone seek rule must stay findable");
  const height = /height:(\d+)px/.exec(phoneSeek[1]);
  assert.ok(height, "the phone seek input must declare its height");
  assert.ok(Number(height[1]) >= 38, `the phone seek hit area must be at least the 38px row, got ${height[1]}px`);
  assert.match(css, /\.progress input::-webkit-slider-runnable-track\{height:4px/, "the visible rail stays 4px");

  // The row it lives in has to be that tall too, and the footer height is the thing
  // that may not move.
  const rows = css.match(/grid-template-rows:(\d+)px (\d+)px (\d+)px!important;height:(\d+)px/);
  assert.ok(rows, "the phone footer keeps three explicit rows and its height");
  const [first, second, third, total] = rows.slice(1).map(Number);
  assert.ok(second >= 38, `the progress row must hold the 38px input, got ${second}px`);
  assert.equal(first + second + third + 2 * 2, total, "the rows plus the two 2px gaps must still add up to the footer height");
}

console.log("Seek settle window regression checks passed.");
