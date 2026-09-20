(function (global) {
  "use strict";

  const DEFAULT_TIMEOUT_MS = 6000;
  const MAX_TIMEOUT_MS = 60000;
  const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;

  function boundedTimeout(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return DEFAULT_TIMEOUT_MS;
    return Math.min(MAX_TIMEOUT_MS, Math.max(1, Math.floor(value)));
  }

  function boundedResponseBytes(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) return MAX_RESPONSE_BYTES;
    return Math.min(MAX_RESPONSE_BYTES, Math.max(1, Math.floor(value)));
  }

  // On the native-bridge host the response object exposes neither a byte stream nor
  // arrayBuffer(), so text() is where every API reply is measured. Re-encoding the
  // whole string just to read its length would allocate a second full copy of the
  // document - up to the entire byte budget - on the hot path, and gating the
  // measurement behind a TextEncoder check would silently skip it on a host that
  // lacks one. Counting UTF-8 bytes in place allocates nothing, stops the moment the
  // running total passes the budget, and matches TextEncoder non-fatal output: an
  // unpaired surrogate becomes U+FFFD (three bytes) and a well-formed pair becomes four.
  function utf8ByteLengthBounded(text, limit) {
    let total = 0;
    const length = text.length;
    for (let i = 0; i < length; i += 1) {
      const code = text.charCodeAt(i);
      let size;
      if (code < 0x80) {
        size = 1;
      } else if (code < 0x800) {
        size = 2;
      } else if (code >= 0xd800 && code < 0xdc00) {
        const next = i + 1 < length ? text.charCodeAt(i + 1) : 0;
        if (next >= 0xdc00 && next < 0xe000) {
          size = 4;
          i += 1;
        } else {
          size = 3;
        }
      } else {
        size = 3;
      }
      total += size;
      if (total > limit) return limit + 1;
    }
    return total;
  }

  function declaredLength(response) {
    const value = response?.headers?.get?.("Content-Length");
    if (typeof value !== "string" || !value.trim() || !/^\d+$/.test(value.trim())) return null;
    const length = Number(value.trim());
    return Number.isSafeInteger(length) ? length : null;
  }

  // The caller cannot tell "this page is empty" from "I could not read this page"
  // by looking at the fallback alone, and on the library list that difference is the
  // difference between an empty song list and an error banner. So every exit reports
  // which of them happened: only a parsed body and a genuinely absent body are
  // usable, and the status defaults to the unusable one so a branch that forgets to
  // classify itself cannot silently look like success.
  const USABLE_BODY_STATUSES = ["parsed", "empty"];

  function usableBody(status) {
    return USABLE_BODY_STATUSES.indexOf(status) >= 0;
  }

  // A caller that reads a document - a device list, an echoed saved state - cannot
  // take "empty" as an answer. Those endpoints always get a JSON body from a healthy
  // server, so a response that carried no bytes means the transport swallowed it, and
  // treating that as "the list came back empty" turns one proxy hiccup into a dropped
  // cast or a silently discarded save. usableBody stays the looser gate for callers
  // whose fallback already is the right value.
  function parsedBody(status) {
    return status === "parsed";
  }

  // The parse result is one object rather than a value plus an out-parameter box.
  // The old shape took `status` as a fifth positional argument that every caller had
  // to pre-seed with the unusable value, so a call site that passed the arguments in
  // the wrong order or forgot the box reported "undecodable" for a body that had just
  // parsed - the hardest failure to read on screen, because the document is visibly
  // there. Returning { data, status } makes the pair impossible to split.
  async function parseBoundedJson(response, fallback, maximum, setCancel) {
    let status = "undecodable";
    const outcome = data => ({ data, status });
    if (!response) return outcome(fallback);
    const length = declaredLength(response);
    if (length !== null && length > maximum) {
      status = "oversize";
      return outcome(fallback);
    }
    const body = response.body;
    if (body && typeof body.getReader === "function" && typeof TextDecoder === "function") {
      const reader = body.getReader();
      let cancelled = false;
      let cancellation = null;
      // An errored stream rejects reader.cancel(), and the timeout path calls it
      // without an await, so the rejection must be captured here instead of
      // escaping as an unhandled rejection. Memoizing also keeps a timeout that
      // races an oversize read from cancelling the same reader twice.
      const cancelReader = () => {
        if (!cancellation) {
          try {
            cancellation = Promise.resolve(reader.cancel()).catch(() => {});
          } catch (_) {
            cancellation = Promise.resolve();
          }
        }
        return cancellation;
      };
      setCancel(() => {
        cancelled = true;
        cancelReader();
      });
      try {
        const decoder = new TextDecoder();
        let total = 0;
        let text = "";
        while (!cancelled) {
          const part = await reader.read();
          if (part?.done) break;
          const value = part?.value;
          // A chunk only has to be an ArrayBufferView, not an instance of *this*
          // realm's Uint8Array. A fetch shim that lives in another realm hands over
          // a view whose prototype chain misses that constructor, and instanceof
          // would then answer the whole page with the fallback, which is an empty
          // list on screen and no error anywhere. isView reads the internal slot,
          // so it stays true across realms and also accepts a DataView chunk.
          const chunk = ArrayBuffer.isView(value) ? value : null;
          if (!chunk) {
            await cancelReader();
            return outcome(fallback);
          }
          if (chunk.byteLength > maximum - total) {
            status = "oversize";
            await cancelReader();
            return outcome(fallback);
          }
          total += chunk.byteLength;
          text += decoder.decode(chunk, { stream: true });
        }
        if (cancelled) {
          status = "cancelled";
          return outcome(fallback);
        }
        // A body that carried no bytes at all is a host that answered without
        // content (a 204, or a request the transport short-circuited), not a broken
        // document. Keeping that case usable is what stops a strict caller from
        // turning a legitimate no-content response into an error screen.
        decoder.decode();
        if (total === 0) {
          status = "empty";
          return outcome(fallback);
        }
        try {
          status = "parsed";
          return outcome(JSON.parse(text));
        } catch (_) {
          status = "undecodable";
          return outcome(fallback);
        }
      } finally {
        setCancel(null);
        try { reader.releaseLock(); } catch (_) {}
      }
    }
    // A host without a readable body stream can only be measured once the whole
    // body is buffered, so take the array buffer first: its length is an exact
    // byte count, while a string length counts UTF-16 code units.
    try {
      if (typeof response.arrayBuffer === "function" && typeof TextDecoder === "function") {
        const buffer = await response.arrayBuffer();
        const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
        if (bytes.byteLength > maximum) {
          status = "oversize";
          return outcome(fallback);
        }
        if (bytes.byteLength === 0) {
          status = "empty";
          return outcome(fallback);
        }
        const parsed = JSON.parse(new TextDecoder().decode(bytes));
        status = "parsed";
        return outcome(parsed);
      }
      if (typeof response.text === "function") {
        const text = await response.text();
        // UTF-8 never encodes a code unit in fewer than one byte, so the code
        // unit count is a cheap lower bound; the byte count is the budget. It also
        // never uses more than three bytes for one code unit, so a string that fits
        // in a third of the budget cannot need measuring at all. Encoding only to
        // measure would otherwise allocate a second full copy of the document, up to
        // the whole budget, on the host where the body is already fully buffered.
        if (typeof text !== "string") return outcome(fallback);
        if (text.length > maximum) {
          status = "oversize";
          return outcome(fallback);
        }
        if (text.length * 3 > maximum && utf8ByteLengthBounded(text, maximum) > maximum) {
          status = "oversize";
          return outcome(fallback);
        }
        if (text.length === 0) {
          status = "empty";
          return outcome(fallback);
        }
        const parsedText = JSON.parse(text);
        status = "parsed";
        return outcome(parsedText);
      }
      // Last resort: a host that exposes neither form cannot be bounded without
      // parsing it first, so this path relies on the Content-Length guard above.
      if (typeof response.json === "function") {
        const parsedDirectly = await response.json();
        status = "parsed";
        return outcome(parsedDirectly);
      }
    } catch (_) {
      return outcome(fallback);
    }
    return outcome(fallback);
  }

  function read(options = {}) {
    const request = options.request;
    const fallback = options.fallback;
    const onTimeout = typeof options.onTimeout === "function" ? options.onTimeout : null;
    const timeoutMs = boundedTimeout(options.timeoutMs);
    const maximum = boundedResponseBytes(options.maxBytes);
    let timer = 0;
    let cancelBody = null;
    const operation = Promise.resolve(request).then(async response => {
      const outcome = await parseBoundedJson(
        response, fallback, maximum, cancel => { cancelBody = cancel; },
      );
      return { response, data: outcome.data, bodyStatus: outcome.status };
    });
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        try { cancelBody?.(); } catch (_) {}
        try { onTimeout?.(); } catch (_) {}
        const error = new Error("response body timed out");
        error.name = "AbortError";
        // Keep AbortError compatibility for callers that already treat an
        // owner cancellation as abort, while allowing them to distinguish a
        // body timeout from a request superseded by a newer generation.
        error.code = "RESPONSE_BODY_TIMEOUT";
        reject(error);
      }, timeoutMs);
    });
    return Promise.race([operation, timeout]).finally(() => {
      if (timer) clearTimeout(timer);
    });
  }

  global.fnAudioResponseJsonLoader = { read, usableBody, parsedBody };
})(typeof window !== "undefined" ? window : globalThis);
