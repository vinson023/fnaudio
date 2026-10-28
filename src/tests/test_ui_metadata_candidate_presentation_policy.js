const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/metadata_candidate_presentation_policy.js", "utf8");
const context = { globalThis: {} };
vm.runInNewContext(source, context);
const policy = context.globalThis.fnAudioMetadataCandidatePresentationPolicy;
assert.equal(typeof policy.selectDisplayCandidate, "function");
assert.equal(typeof policy.selectDisplayArtwork, "function");
assert.equal(typeof policy.confidencePercent, "function");
const sparseBest = { title: "Song", artist: "Artist", confidence: 0.99 };
const complete = { title: "Song", artist: "Artist", album: "Album", image_url: "https://example.test/a.jpg", confidence: 0.72 };
assert.equal(policy.selectDisplayCandidate(sparseBest, [complete]), complete, "display should prefer a complete cover/album candidate over sparse best");
assert.equal(policy.selectDisplayCandidate({}, []), null, "empty projections should remain distinguishable from a candidate");
assert.equal(policy.selectDisplayCandidate(null, [{ title: "Song", confidence: "bad" }]).title, "Song");
const hostile = new Proxy({ title: "Hostile" }, { get() { throw new Error("unexpected coercion"); } });
assert.doesNotThrow(() => policy.selectDisplayCandidate(hostile, [complete]), "hostile provider fields must not break display selection");
assert.equal(policy.selectDisplayCandidate({ title: "Low", confidence: "0.7" }, [{ title: "High", confidence: "0.8" }]).title, "High");
const hostileKeys = new Proxy({ title: "Hostile keys" }, { ownKeys() { throw new Error("unexpected ownKeys"); } });
assert.doesNotThrow(() => policy.selectDisplayCandidate(hostileKeys, [complete]));
assert.equal(policy.selectDisplayCandidate({}, [{ confidence: 0 }]), null, "Candidates without display data must remain absent");
assert.equal(policy.selectDisplayArtwork({ title: "Local", image_url: "" }, [{ title: "Remote", image_url: "https://example.test/remote.jpg" }]), "https://example.test/remote.jpg", "Artwork should be projected independently from the selected metadata candidate");
assert.equal(policy.selectDisplayArtwork({}, [], "https://example.test/fallback.jpg"), "https://example.test/fallback.jpg");
assert.equal(policy.confidencePercent(Infinity), "0%", "non-finite confidence must not leak into the UI");
assert.equal(policy.confidencePercent(2), "100%", "confidence display must be capped at 100%");
assert.equal(policy.confidencePercent("0.375"), "38%");
console.log("Metadata candidate presentation policy checks passed.");

const NL = String.fromCharCode(10);
const app = fs.readFileSync("app/ui/app.js", "utf8");
const index = fs.readFileSync("app/ui/index.html", "utf8");

assert.match(index, /id="metadataCandidateDialog"/, "metadata completion must have its own dialog");
assert.match(index, /id="metadataCandidateSearchForm"/, "manual metadata search must have a dedicated form");
assert.match(index, /id="metadataCandidateSearchInput"/, "manual search needs a visible query input");
assert.match(index, /id="metadataCandidateSearchResults"/, "manual search needs a result container");
assert.match(app, /function openMetadataCandidateDialog\(/, "candidate flow must open the dedicated dialog");
assert.match(app, /api\/metadata\/track\/search/, "manual search must use the track-scoped search endpoint");
assert.match(app, /function renderMetadataCandidateSearchResults\(/, "manual results need a dedicated renderer");

function appFunctionSource(name) {
  const match = app.match(new RegExp("^(?:async )?function " + name + "\\b[\\s\\S]*?^}", "m"));
  assert.ok(match, `function ${name} must stay extractable for executable UI regressions`);
  return match[0];
}

// External-share password sampling remains live and independent of candidate polling.
const SHARE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
const SHARE_ALPHABET_LENGTH = 57;
// Math.floor(256 / 57) * 57: the widest prefix of the byte range that divides
// evenly into the alphabet.  Anything from here up must be discarded.
const UNBIASED_BYTE_LIMIT = 228;

function passwordHarness(script) {
  const draws = [];
  let cursor = 0;
  const context = {
    draws,
    String, Number, Math, Array, Error,
    Uint8Array: class {
      constructor(length) {
        const cells = new Array(length).fill(0);
        return new Proxy(cells, {
          get(target, key) {
            if (key === "byteLength") return target.length;
            return Reflect.get(target, key);
          },
        });
      }
    },
    crypto: {
      getRandomValues(target) {
        draws.push(target.length);
        for (let index = 0; index < target.length; index += 1) {
          target[index] = script[Math.min(cursor, script.length - 1)];
          cursor += 1;
        }
        return target;
      },
    },
  };
  vm.createContext(context);
  vm.runInContext([
    appFunctionSource("generateExternalSharePassword"),
    "globalThis.__target = generateExternalSharePassword;",
  ].join(NL), context);
  return { context, generate: () => context.__target(), draws };
}

// The oracle restates the specification rather than the implementation: walk
// the scripted bytes in order, keep only the ones below the bound, and map
// each survivor onto the alphabet.
function expectedPassword(script) {
  const characters = [];
  for (let index = 0; index < script.length && characters.length < 10; index += 1) {
    if (script[index] < UNBIASED_BYTE_LIMIT) {
      characters.push(SHARE_ALPHABET[script[index] % SHARE_ALPHABET_LENGTH]);
    }
  }
  assert.equal(characters.length, 10, "fixture bug: this script cannot fill ten characters");
  return characters.join("");
}

(async () => {
  // 1. Positive control: a buffer that is entirely inside the unbiased range
  //    costs one draw and maps one-for-one, so fixture and alphabet line up.
  const inRange = [0, 1, 2, 3, 4, 5, 6, 7, 8, 54];
  const clean = passwordHarness(inRange);
  assert.equal(clean.generate(), expectedPassword(inRange),
    "an in-range byte must select its own character");
  assert.equal(clean.draws.length, 1, "and a full buffer of accepted bytes costs exactly one draw");

  // 2. The biased tail must be refused, not folded.  Bytes 228..255 are what
  //    256 % 57 leaves over; here they are spread across the buffer so that
  //    completing the password costs a second read.
  const biased = [228, 0, 255, 1, 227, 2, 250, 3, 229, 4, 5, 6, 7, 8, 9, 240, 10, 11, 12, 13];
  const produced = passwordHarness(biased).generate();
  assert.equal(produced, expectedPassword(biased),
    "every rejected byte has to be replaced by a further draw, in order");
  const costly = passwordHarness(biased);
  costly.generate();
  assert.ok(costly.draws.length > 1, "which costs more than the single naive read");

  // 3. Nothing may leak outside the alphabet, whatever the generator returns
  //    -- including a whole first buffer that sits in the rejected tail.
  for (const script of [
    [56, 56, 56, 56, 56, 56, 56, 56, 56, 56],
    [255, 254, 253, 252, 251, 250, 249, 248, 247, 246, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  ]) {
    const probe = passwordHarness(script);
    const value = probe.generate();
    assert.equal(value.length, 10);
    assert.ok([...value].every(character => SHARE_ALPHABET.includes(character)),
      "the password stays inside its own alphabet: " + value);
  }

  // 3b. The buffer is read ten bytes at a time, so a batch can end with nine
  //     accepted bytes and a rejected one.  Only an outer loop that keeps going
  //     until ten characters are really in hand survives that; one that stops at
  //     "nine or more" hands back a short password.
  const straddle = [0, 1, 2, 3, 4, 5, 6, 7, 8, 255, 254, 9, 10, 11, 12, 13, 14, 15, 16, 17];
  const crossed = passwordHarness(straddle);
  assert.equal(crossed.generate(), expectedPassword(straddle),
    "a first buffer that fills only nine characters has to be followed up");
  assert.equal(crossed.draws.length, 2, "which is measurable as a second read");

  // 4. Wiring: the bound the measurement above relies on is stated in the
  //    source in terms of the byte range, not as a guessed magic number.
  assert.match(appFunctionSource("generateExternalSharePassword"), /256/,
    "the rejection bound has to be derived from the byte range");
})().then(() => {
  console.log("External share password sampling checks passed.");
}).catch(error => {
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
});

