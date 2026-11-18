// R587: the queue is the play order.
//
// Audio Station keeps two arrays (a source list plus a permutation).  fnAudio
// already keeps one list -- `state.queue` is both what the queue view draws and
// what the player walks -- so the equivalent of "shuffle is a permutation" is
// "turning shuffle on reorders the queue once and remembers the old order".
//
// That is what this module does, and it is why `nextIndex`/`previousIndex` no
// longer call `Math.random`: a coin flip per press cannot promise "one pass
// without repeats", cannot make "previous" return to the row you actually came
// from, and cannot keep the current row when shuffle is switched off.
//
// The same table lives in src/app/server/queue_order_policy.py; one test runs
// both against one table so the two copies cannot drift.
(() => {
  const MAX_ITEMS = 50000;
  const REPEAT_MODES = ["off", "all", "one"];

  function normalizeRepeat(repeat) {
    return REPEAT_MODES.includes(repeat) ? repeat : "off";
  }

  function usableIndex(index) {
    return Number.isInteger(index) ? index : -1;
  }

  function usableLength(length) {
    if (!Number.isInteger(length) || length < 0) return 0;
    return Math.min(length, MAX_ITEMS);
  }

  function nextIndex(index, length, repeat) {
    const size = usableLength(length);
    if (!size) return -1;
    const current = usableIndex(index);
    const mode = normalizeRepeat(repeat);
    if (mode === "one" && current >= 0) return current;
    // No current row (-1) starts at the first row, like a fresh queue.
    if (current < size - 1) return current + 1;
    return mode === "all" ? 0 : -1;
  }

  function previousIndex(index, length, repeat) {
    const size = usableLength(length);
    if (!size) return -1;
    const current = usableIndex(index);
    const mode = normalizeRepeat(repeat);
    if (mode === "one" && current >= 0) return current;
    if (current > 0) return current - 1;
    return mode === "all" ? size - 1 : -1;
  }

  function orderIds(items) {
    if (!Array.isArray(items)) return [];
    const ids = [];
    for (const item of items) {
      const id = String(item?.id || "");
      if (id) ids.push(id);
    }
    return ids;
  }

  // Fisher-Yates with the same guards as fnAudioShufflePolicy: a random source
  // that throws or returns NaN must reorder nothing rather than corrupt the list.
  function shuffled(values, random) {
    const items = values.slice();
    const source = typeof random === "function" ? random : Math.random;
    for (let index = items.length - 1; index > 0; index -= 1) {
      let sample = 0;
      try {
        sample = Number(source());
      } catch (_) {
        sample = 0;
      }
      if (!Number.isFinite(sample)) sample = 0;
      sample = Math.min(0.999999999, Math.max(0, sample));
      const swapIndex = Math.floor(sample * (index + 1));
      const held = items[index];
      items[index] = items[swapIndex];
      items[swapIndex] = held;
    }
    return items;
  }

  // Reorder so the playing row keeps its slot: the user hears no break, and the
  // "now playing" highlight does not jump to another part of the list.
  function shuffleQueue(items, index, random) {
    const source = Array.isArray(items) ? items.slice() : [];
    const cursor = usableIndex(index);
    const hasCurrent = cursor >= 0 && cursor < source.length;
    if (source.length < 2) return { items: source, index: hasCurrent ? cursor : -1 };
    const rest = [];
    for (let position = 0; position < source.length; position += 1) {
      if (hasCurrent && position === cursor) continue;
      rest.push(source[position]);
    }
    const mixed = shuffled(rest, random);
    if (!hasCurrent) return { items: mixed, index: -1 };
    const ordered = [];
    let taken = 0;
    for (let position = 0; position < source.length; position += 1) {
      if (position === cursor) ordered.push(source[cursor]);
      else {
        ordered.push(mixed[taken]);
        taken += 1;
      }
    }
    return { items: ordered, index: cursor };
  }

  // Put the remembered order back.  The row that is playing stays the row that
  // is playing -- only its position changes -- because "shuffle off" must not
  // switch songs.  Tracks added while shuffled were never in the remembered
  // order, so they keep their relative place at the end.
  function restoreQueue(items, index, originalIds) {
    const source = Array.isArray(items) ? items.slice() : [];
    const cursor = usableIndex(index);
    const currentId = cursor >= 0 && cursor < source.length ? String(source[cursor]?.id || "") : "";
    const byId = new Map();
    for (const item of source) {
      const id = String(item?.id || "");
      if (id && !byId.has(id)) byId.set(id, item);
    }
    const ordered = [];
    const seen = new Set();
    const remembered = Array.isArray(originalIds) ? originalIds : [];
    for (const raw of remembered) {
      const id = String(raw || "");
      const item = byId.get(id);
      if (!item || seen.has(id)) continue;
      ordered.push(item);
      seen.add(id);
    }
    for (const item of source) {
      const id = String(item?.id || "");
      if (!id || seen.has(id)) continue;
      ordered.push(item);
      seen.add(id);
    }
    let nextCursor = currentId ? ordered.findIndex(item => String(item?.id || "") === currentId) : -1;
    if (nextCursor < 0) nextCursor = ordered.length ? 0 : -1;
    return { items: ordered, index: nextCursor };
  }

  window.fnAudioQueueOrderPolicy = {
    MAX_ITEMS,
    REPEAT_MODES,
    nextIndex,
    previousIndex,
    orderIds,
    restoreQueue,
    shuffleQueue,
  };
})();
