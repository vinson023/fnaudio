const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "response_json_loader.js"), "utf8");
const context = {
  globalThis: {},
  Promise,
  Number,
  Math,
  Uint8Array,
  TextDecoder,
  TextEncoder,
  setTimeout,
  clearTimeout,
};
vm.runInNewContext(source, context);
const read = context.globalThis.fnAudioResponseJsonLoader.read;

const rejectionEvents = [];
const observeRejection = reason => { rejectionEvents.push(reason); };
process.on("unhandledRejection", observeRejection);
const tick = () => new Promise(resolve => setImmediate(resolve));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

(async () => {
  let resolveBody;
  const body = new Promise(resolve => { resolveBody = resolve; });
  let timedOut = false;
  await assert.rejects(
    read({
      request: Promise.resolve({ json: () => body }),
      timeoutMs: 10,
      onTimeout: () => { timedOut = true; },
      fallback: null,
    }),
    error => error?.name === "AbortError" && error?.code === "RESPONSE_BODY_TIMEOUT",
  );
  assert.equal(timedOut, true);
  resolveBody({ late: true });

  const result = await read({
    request: Promise.resolve({ json: async () => ({ ok: true }) }),
    timeoutMs: 100,
    fallback: {},
  });
  assert.deepEqual(result.data, { ok: true });

  let cancelled = false;
  const stream = {
    getReader() {
      return {
        async read() { return { done: false, value: new Uint8Array(32) }; },
        async cancel() { cancelled = true; },
        releaseLock() {},
      };
    },
  };
  const oversized = await read({
    request: Promise.resolve({ body: stream }),
    maxBytes: 16,
    fallback: { safe: true },
  });
  assert.deepEqual(oversized.data, { safe: true });
  assert.equal(cancelled, true);

  // A stream that is already errored rejects reader.cancel(). The timeout path
  // has nowhere to await it, so the rejection must be captured inside the loader.
  let stuckCancelCalls = 0;
  let releaseStuckRead;
  const stuckStream = {
    getReader() {
      return {
        read() {
          return new Promise(resolve => {
            releaseStuckRead = resolve;
          });
        },
        cancel() {
          stuckCancelCalls += 1;
          return Promise.reject(new Error("stream errored"));
        },
        releaseLock() {},
      };
    },
  };
  await assert.rejects(
    read({ request: Promise.resolve({ body: stuckStream }), timeoutMs: 5, fallback: null }),
    error => error?.name === "AbortError",
    "a body that never settles must still hit its deadline",
  );
  assert.equal(stuckCancelCalls, 1, "the deadline must cancel the reader exactly once");
  releaseStuckRead?.({ done: true });
  await tick();
  await tick();
  assert.deepEqual(rejectionEvents, [], "a rejected reader.cancel() must not escape as an unhandled rejection");

  // A deadline that fires while the oversize branch is awaiting its own cancel
  // must not cancel the same reader a second time.
  let slowCancelCalls = 0;
  const slowCancelStream = {
    getReader() {
      return {
        async read() {
          return { done: false, value: new Uint8Array(32) };
        },
        cancel() {
          slowCancelCalls += 1;
          return sleep(25);
        },
        releaseLock() {},
      };
    },
  };
  const raced = read({ request: Promise.resolve({ body: slowCancelStream }), maxBytes: 16, timeoutMs: 5, fallback: null });
  await assert.rejects(raced, error => error?.name === "AbortError");
  await sleep(80);
  assert.equal(slowCancelCalls, 1, "a superseded body task must reuse the pending cancellation");

  // A non-stream host must be bounded in bytes, not UTF-16 code units. Six CJK
  // characters are 18 code units but 30 bytes on top of the JSON punctuation.
  const cjkPayload = JSON.stringify({ title: "\u4e2d\u4e2d\u4e2d\u4e2d\u4e2d\u4e2d" });
  const cjkBytes = new TextEncoder().encode(cjkPayload).byteLength;
  assert.equal(cjkPayload.length < cjkBytes, true, "the fixture must be wider in bytes than in code units");
  const overByteBudget = await read({
    request: Promise.resolve({ text: async () => cjkPayload }),
    maxBytes: cjkPayload.length + 1,
    fallback: { rejected: true },
  });
  assert.deepEqual(overByteBudget.data, { rejected: true }, "a payload over the byte budget must not be parsed");
  const withinByteBudget = await read({
    request: Promise.resolve({ text: async () => cjkPayload }),
    maxBytes: cjkBytes,
    fallback: { rejected: true },
  });
  // Objects parsed inside the VM carry that realm's prototype, so compare the
  // decoded primitives rather than the object identity.
  assert.equal(withinByteBudget.data?.title, "\u4e2d".repeat(6), "an exact byte budget must still parse");
  assert.equal(Object.keys(withinByteBudget.data).length, 1);

  // The array buffer branch is preferred because its length is already exact.
  let textBranchCalls = 0;
  const encoded = new TextEncoder().encode(JSON.stringify({ ok: true }));
  const viaBuffer = await read({
    request: Promise.resolve({
      arrayBuffer: async () => encoded.buffer,
      text: async () => {
        textBranchCalls += 1;
        return "must not be read";
      },
    }),
    maxBytes: encoded.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(viaBuffer.data?.ok, true);
  assert.equal(textBranchCalls, 0, "the exact-byte branch must run before the string branch");
  const oversizedBuffer = await read({
    request: Promise.resolve({ arrayBuffer: async () => encoded.buffer }),
    maxBytes: encoded.byteLength - 1,
    fallback: { rejected: true },
  });
  assert.deepEqual(oversizedBuffer.data, { rejected: true });

  // A multibyte character split across two stream chunks must survive decoding.
  const split = new TextEncoder().encode(JSON.stringify({ title: "\u4e2d" }));
  const boundaryStream = {
    getReader() {
      let index = 0;
      return {
        async read() {
          if (index >= split.byteLength) return { done: true };
          const take = index === 0 ? split.byteLength - 1 : split.byteLength - index;
          const value = split.slice(index, index + take);
          index += take;
          return { done: false, value };
        },
        async cancel() {},
        releaseLock() {},
      };
    },
  };
  const acrossChunks = await read({
    request: Promise.resolve({ body: boundaryStream }),
    maxBytes: split.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(acrossChunks.data?.title, "\u4e2d", "chunk boundaries must not corrupt text");

  // The last-resort json() host cannot be measured before parsing, so it leans on
  // the declared length guard instead.
  let lastResortCalls = 0;
  const declaredTooLarge = await read({
    request: Promise.resolve({
      headers: { get: () => String(cjkBytes + 1) },
      json: async () => {
        lastResortCalls += 1;
        return {};
      },
    }),
    maxBytes: cjkBytes,
    fallback: { rejected: true },
  });
  assert.deepEqual(declaredTooLarge.data, { rejected: true });
  assert.equal(lastResortCalls, 0, "an oversized Content-Length must be rejected before the body is consumed");

  // A fetch shim that lives in another realm hands over a Uint8Array whose prototype
  // chain misses this realm's constructor. An instanceof test then answers the whole
  // page with the fallback, which looks like an empty list and no error at all, so the
  // chunk check has to read the internal slot. This context deliberately never
  // receives the host Uint8Array, so every view created below is foreign to it.
  const isolated = vm.createContext({
    globalThis: {},
    Promise,
    Number,
    Math,
    TextDecoder,
    TextEncoder,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(source, isolated);
  const readIsolated = isolated.globalThis.fnAudioResponseJsonLoader.read;
  const isForeignView = vm.runInContext("chunk => chunk instanceof Uint8Array", isolated);
  const foreignPayload = new TextEncoder().encode(JSON.stringify({ title: "\u4e2d\u6587" }));
  const foreignChunks = [foreignPayload.slice(0, 4), foreignPayload.slice(4)];
  assert.equal(isForeignView(foreignChunks[0]), false, "the fixture must really come from another realm");
  assert.equal(ArrayBuffer.isView(foreignChunks[0]), true, "the internal slot check is what survives realms");
  const streamOf = chunks => ({
    getReader() {
      let index = 0;
      return {
        async read() {
          if (index >= chunks.length) return { done: true };
          const value = chunks[index];
          index += 1;
          return { done: false, value };
        },
        async cancel() {},
        releaseLock() {},
      };
    },
  });
  const acrossRealms = await readIsolated({
    request: Promise.resolve({ body: streamOf(foreignChunks) }),
    maxBytes: foreignPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(acrossRealms.data?.title, "\u4e2d\u6587", "a foreign-realm chunk must still be read");
  const oversizedForeign = await readIsolated({
    request: Promise.resolve({ body: streamOf(foreignChunks) }),
    maxBytes: foreignPayload.byteLength - 1,
    fallback: { rejected: true },
  });
  assert.deepEqual(oversizedForeign.data, { rejected: true }, "the byte budget still applies across realms");

  // The view check has to keep accepting anything that carries the internal slot, and
  // keep refusing anything that does not. A host that hands over decoded text instead
  // of bytes must end up on the fallback, not on a rejected read: TextDecoder throws
  // for a plain string, and a thrown read is an error screen instead of an empty one.
  const dataViewPayload = new TextEncoder().encode(JSON.stringify({ view: "dataview" }));
  const dataViewChunks = [new DataView(dataViewPayload.buffer, dataViewPayload.byteOffset, dataViewPayload.byteLength)];
  const viaDataView = await readIsolated({
    request: Promise.resolve({ body: streamOf(dataViewChunks) }),
    maxBytes: dataViewPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(viaDataView.data?.view, "dataview", "a DataView chunk is a view and must be read");
  const notAView = await readIsolated({
    request: Promise.resolve({ body: streamOf(["already decoded text"]) }),
    maxBytes: dataViewPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.deepEqual(notAView.data, { rejected: true }, "a chunk that is not a byte view must fall back");

  // A host that answers a cancellation by failing the pending read, instead of
  // closing the stream, cannot change what the caller was told. The deadline already
  // rejected the race, and Promise.race subscribes to every input, so the late
  // rejection is delivered to nobody: it must not reach the unhandled-rejection
  // listener and must not turn into a second outcome. If this ever needs a guard in
  // the loader, it needs a test that says so, because there is none today.
  let rejectCancelledRead;
  const hostileStream = {
    getReader() {
      return {
        read() {
          return new Promise((_resolve, reject) => { rejectCancelledRead = reject; });
        },
        cancel() { return Promise.resolve(); },
        releaseLock() {},
      };
    },
  };
  await assert.rejects(
    read({ request: Promise.resolve({ body: hostileStream }), timeoutMs: 5, fallback: null }),
    error => error?.name === "AbortError",
    "a cancelled body that later fails must still report its deadline",
  );
  rejectCancelledRead(new Error("host rejected the cancelled read"));
  await sleep(20);
  assert.deepEqual(rejectionEvents, [], "a read rejected after the deadline must not escape as an unhandled rejection");

  // The opposite case: while the caller is still waiting, a failing body is a real
  // transport error and must not be quietly turned into a fallback page.
  const transportError = new Error("connection reset");
  await assert.rejects(
    read({
      request: Promise.resolve({
        body: {
          getReader() {
            return {
              read() { return Promise.reject(transportError); },
              cancel() { return Promise.resolve(); },
              releaseLock() {},
            };
          },
        },
      }),
      timeoutMs: 500,
      fallback: { rejected: true },
    }),
    error => error === transportError,
    "a body that fails while it is still wanted must reach the caller as an error",
  );

  // Measuring a buffered string costs a second full copy of the document, so it
  // only runs when three bytes per code unit could still overflow the budget. Both
  // sides of that boundary are checked here with the encoder call counted.
  let encoderCalls = 0;
  class CountingTextEncoder extends TextEncoder {
    constructor() {
      super();
      encoderCalls += 1;
    }
  }
  const measured = {
    globalThis: {},
    Promise,
    Number,
    Math,
    Uint8Array,
    TextDecoder,
    TextEncoder: CountingTextEncoder,
    setTimeout,
    clearTimeout,
  };
  vm.runInNewContext(source, measured);
  const readMeasured = measured.globalThis.fnAudioResponseJsonLoader.read;
  const asciiPayload = JSON.stringify({ title: "a".repeat(400) });
  assert.equal(new TextEncoder().encode(asciiPayload).byteLength, asciiPayload.length);
  const beforeSkipped = encoderCalls;
  const neverOverflows = await readMeasured({
    request: Promise.resolve({ text: async () => asciiPayload }),
    maxBytes: asciiPayload.length * 3,
    fallback: { rejected: true },
  });
  assert.equal(neverOverflows.data?.title?.length, 400, "a third-of-budget string cannot overflow it");
  assert.equal(encoderCalls, beforeSkipped, "a payload that provably fits must not be re-encoded to be measured");
  const beforeMeasured = encoderCalls;
  const oneByteTight = await readMeasured({
    request: Promise.resolve({ text: async () => asciiPayload }),
    maxBytes: asciiPayload.length * 3 - 1,
    fallback: { rejected: true },
  });
  assert.equal(oneByteTight.data?.title?.length, 400);
  assert.equal(encoderCalls, beforeMeasured + 1, "inside the band the exact byte count must still be taken");
  const cjkFits = await readMeasured({
    request: Promise.resolve({ text: async () => cjkPayload }),
    maxBytes: cjkBytes,
    fallback: { rejected: true },
  });
  assert.equal(cjkFits.data?.title, "\u4e2d".repeat(6), "the exact budget must still parse a wide payload");
  const cjkOver = await readMeasured({
    request: Promise.resolve({ text: async () => cjkPayload }),
    maxBytes: cjkBytes - 1,
    fallback: { rejected: true },
  });
  assert.deepEqual(cjkOver.data, { rejected: true }, "one byte over the exact budget must still be refused");
  assert.equal(encoderCalls, beforeMeasured + 3, "each banded payload is measured once");
  // The code unit count is also the cheap way out: once a string is already longer
  // than the entire budget the byte count cannot be smaller, and measuring it would
  // mean encoding megabytes that are going to be thrown away.
  const MAX_BYTES = 4 * 1024 * 1024;
  const beyondBudget = JSON.stringify({ title: "a".repeat(MAX_BYTES + 8) });
  assert.equal(beyondBudget.length > MAX_BYTES, true, "the fixture must exceed the largest allowed budget");
  const beforeEarlyExit = encoderCalls;
  const refusedWithoutMeasuring = await readMeasured({
    request: Promise.resolve({ text: async () => beyondBudget }),
    maxBytes: MAX_BYTES,
    fallback: { rejected: true },
  });
  assert.deepEqual(refusedWithoutMeasuring.data, { rejected: true });
  assert.equal(
    encoderCalls,
    beforeEarlyExit,
    "a string already longer than the whole budget must be refused without measuring it",
  );

  // Every fallback has to say which kind of nothing it is. The library list caches
  // whatever a request resolves to and paints it as authoritative, so an unreadable
  // body arriving as "no songs" is a visible data loss, while a host that really
  // answered without content must stay benign.
  const statusPayload = new TextEncoder().encode(JSON.stringify({ reported: "status" }));
  const reportedParsed = await read({
    request: Promise.resolve({ body: streamOf([statusPayload]) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(reportedParsed.bodyStatus, "parsed", (reportedParsed.bodyStatus || "") + " / parsed");
  assert.equal(reportedParsed.data?.reported, "status");
  const reportedOversize = await read({
    request: Promise.resolve({ body: streamOf([statusPayload]) }),
    maxBytes: statusPayload.byteLength - 1,
    fallback: { rejected: true },
  });
  assert.equal(reportedOversize.bodyStatus, "oversize");
  assert.deepEqual(reportedOversize.data, { rejected: true });
  const reportedEmpty = await read({
    request: Promise.resolve({ body: streamOf([]) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(reportedEmpty.bodyStatus, "empty", "a body with no bytes is no content, not a broken document");
  assert.deepEqual(reportedEmpty.data, { rejected: true });
  const reportedUndecodable = await read({
    request: Promise.resolve({ body: streamOf([new TextEncoder().encode("{ not json")]) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(reportedUndecodable.bodyStatus, "undecodable");
  const declaredOversize = await read({
    request: Promise.resolve({ headers: { get: () => String(statusPayload.byteLength + 1) } }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(declaredOversize.bodyStatus, "oversize", "the Content-Length guard reports the same status");
  const bufferParsed = await read({
    request: Promise.resolve({ arrayBuffer: async () => statusPayload.buffer }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(bufferParsed.bodyStatus, "parsed");
  const bufferEmpty = await read({
    request: Promise.resolve({ arrayBuffer: async () => new ArrayBuffer(0) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(bufferEmpty.bodyStatus, "empty");
  assert.equal(bufferEmpty.data?.rejected, true);
  const textParsed = await read({
    request: Promise.resolve({ text: async () => JSON.stringify({ viaText: true }) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(textParsed.bodyStatus, "parsed");
  assert.equal(
    (await read({
      request: Promise.resolve({ text: async () => "" }),
      maxBytes: statusPayload.byteLength,
      fallback: { rejected: true },
    })).bodyStatus,
    "empty",
    "a host that only offers text() must report no content the same way",
  );
  const unusableText = await read({
    request: Promise.resolve({ text: async () => 42 }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(unusableText.bodyStatus, "undecodable", "a body that is not a string stays unusable");
  const lastResortParsed = await read({
    request: Promise.resolve({ json: async () => ({ viaJson: true }) }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(lastResortParsed.bodyStatus, "parsed");
  const lastResortFailed = await read({
    request: Promise.resolve({ json: async () => { throw new Error("host parse failed"); } }),
    maxBytes: statusPayload.byteLength,
    fallback: { rejected: true },
  });
  assert.equal(
    lastResortFailed.bodyStatus,
    "undecodable",
    "a branch that never classified itself must not report success",
  );

  // The strict caller only asks one question about that status, so the answer has to
  // be exact: two usable values and everything else refused, including a status that
  // a future code path forgot to set.
  const usable = context.globalThis.fnAudioResponseJsonLoader.usableBody;
  assert.equal(typeof usable, "function", "the loader must export the usability decision");
  for (const status of ["parsed", "empty"]) {
    assert.equal(usable(status), true, status + " must stay usable");
  }
  for (const status of ["oversize", "undecodable", "cancelled", "", "garbage", undefined, null, 0, {}]) {
    assert.equal(usable(status), false, String(status) + " must not be usable");
  }


  // The document gate is deliberately stricter than the usability gate, because for a
  // document endpoint "no bytes" is not an answer about the world. It has to be exact
  // in the other direction too: a status the caller has never heard of is not a
  // document, and neither is the one a branch forgot to set.
  const parsedOnly = context.globalThis.fnAudioResponseJsonLoader.parsedBody;
  assert.equal(typeof parsedOnly, "function", "the loader must export the document decision");
  assert.equal(parsedOnly("parsed"), true, "a parsed body is the only document");
  for (const status of ["empty", "oversize", "undecodable", "cancelled", "", "garbage", undefined, null, 0, {}]) {
    assert.equal(parsedOnly(status), false, String(status) + " must not count as a document");
  }
  for (const status of ["parsed", "oversize", "undecodable", "cancelled"]) {
    assert.equal(usable(status), parsedOnly(status), status + " must mean the same thing to both gates");
  }
  assert.equal(usable("empty"), true, "a host that answered with no content stays benign for a fallback caller");
  assert.equal(parsedOnly("empty"), false, "the same no-content answer must not read as an empty document");

  // The verdicts above are only useful if real bodies really produce them, so drive
  // each of them through the reader rather than naming the status by hand.
  const documents = {
    parsed: await read({ request: Promise.resolve({ ok: true, status: 200, headers: { get: () => null },
      arrayBuffer: async () => new TextEncoder().encode("{\"targets\":[{\"id\":\"local\"}]}") }), fallback: {} }),
    empty: await read({ request: Promise.resolve({ ok: true, status: 200, headers: { get: () => null },
      arrayBuffer: async () => new Uint8Array(0) }), fallback: {} }),
    oversize: await read({ request: Promise.resolve({ ok: true, status: 200, headers: { get: () => String(9 * 1024 * 1024) },
      arrayBuffer: async () => new Uint8Array(0) }), fallback: {} }),
    broken: await read({ request: Promise.resolve({ ok: true, status: 200, headers: { get: () => null },
      arrayBuffer: async () => new TextEncoder().encode("<html>gateway</html>") }), fallback: {} }),
  };
  assert.equal(documents.parsed.bodyStatus, "parsed");
  assert.equal(documents.empty.bodyStatus, "empty");
  assert.equal(documents.oversize.bodyStatus, "oversize");
  assert.equal(documents.broken.bodyStatus, "undecodable", "a body that is not JSON must not claim a document");
  assert.equal(parsedOnly(documents.parsed.bodyStatus), true);
  for (const key of ["empty", "oversize", "broken"]) {
    assert.equal(parsedOnly(documents[key].bodyStatus), false, key + " must stay untrusted for a document caller");
  }
  // A status is only worth reading if it can never contradict the data beside it.
  // That contradiction is exactly what the fifth positional out-parameter used to
  // allow: a call site that forgot to thread the status box handed back the parsed
  // document while bodyStatus still said "undecodable", which the caller reads as a
  // broken response and paints over a good one. Comparing the two fields for every
  // transport shape kills that class directly, and it is only meaningful because the
  // shapes below contain both outcomes - a loader that always claimed "parsed" or
  // always returned the fallback would satisfy a status-only or data-only assertion
  // and must not satisfy this one.
  const agreementFallback = { rejected: true };
  const agreementShapes = {
    streamParsed: { body: streamOf([new TextEncoder().encode("{\"a\":1}")]) },
    streamOversize: { body: streamOf([new TextEncoder().encode("{\"a\":1}")]), maxBytes: 4 },
    streamEmpty: { body: streamOf([]) },
    streamBroken: { body: streamOf([new TextEncoder().encode("{ nope")]) },
    declaredOversize: { headers: { get: () => "999999" } },
    bufferParsed: { arrayBuffer: async () => new TextEncoder().encode("{\"b\":2}") },
    bufferEmpty: { arrayBuffer: async () => new Uint8Array(0) },
    textParsed: { text: async () => "{\"c\":3}" },
    textWrongType: { text: async () => 7 },
    jsonOnly: { json: async () => ({ d: 4 }) },
    jsonFailed: { json: async () => { throw new Error("host parse failed"); } },
    noResponse: undefined,
  };
  let trustedDocuments = 0;
  let refusedBodies = 0;
  for (const shape of Object.keys(agreementShapes)) {
    const options = { request: Promise.resolve(agreementShapes[shape]), fallback: agreementFallback };
    if (agreementShapes[shape] && agreementShapes[shape].maxBytes) options.maxBytes = agreementShapes[shape].maxBytes;
    else options.maxBytes = 4096;
    const outcome = await read(options);
    const trustworthy = parsedOnly(outcome.bodyStatus);
    assert.equal(
      trustworthy,
      outcome.data !== agreementFallback,
      shape + ": a document must never arrive with an unusable status and a refusal must never arrive as a document, got " + outcome.bodyStatus,
    );
    if (trustworthy) trustedDocuments += 1;
    else refusedBodies += 1;
  }
  assert.equal(trustedDocuments, 4, "the stream, arrayBuffer, text and json() paths must each be able to yield a document");
  assert.equal(refusedBodies, Object.keys(agreementShapes).length - 4, "every remaining shape must yield the fallback");

  // And the shape that made the contradiction possible has to stay gone, not merely
  // unused: the parameter list may not grow a fifth position again, and no status box
  // may be left behind to be forgotten.
  const parseHeader = /async function parseBoundedJson\(([^)]*)\)/.exec(source);
  assert.ok(parseHeader, "the bounded parse helper must remain the single place that reads a body");
  assert.equal(
    parseHeader[1].split(",").map(part => part.trim()).filter(Boolean).length,
    4,
    "response, fallback, maximum and setCancel - the result itself must not need a position",
  );
  assert.equal((source.match(/status\.value/g) || []).length, 0, "no out-parameter box may survive");
  assert.equal((source.match(/const status = \{ value:/g) || []).length, 0, "read() may not pre-seed a status box again");
  assert.equal((source.match(/parseBoundedJson\(/g) || []).length, 2, "the declaration plus the one call site in read()");

  if (rejectionEvents.length) process.off("unhandledRejection", observeRejection);
  if (rejectionEvents.length) throw rejectionEvents[0];
  console.log("Response JSON timeout regression checks passed.");
})().catch(error => { console.error(error); process.exitCode = 1; });
