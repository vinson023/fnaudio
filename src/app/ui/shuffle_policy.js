(() => {
  const MAX_ITEMS = 50000;

  function shuffle(values, random = Math.random) {
    if (!Array.isArray(values)) return [];
    const items = values.slice(0, MAX_ITEMS);
    const nextRandom = typeof random === "function" ? random : Math.random;
    for (let index = items.length - 1; index > 0; index -= 1) {
      let sample = 0;
      try {
        sample = Number(nextRandom());
      } catch (_) {
        sample = 0;
      }
      if (!Number.isFinite(sample)) sample = 0;
      sample = Math.min(0.999999999, Math.max(0, sample));
      const swapIndex = Math.floor(sample * (index + 1));
      [items[index], items[swapIndex]] = [items[swapIndex], items[index]];
    }
    return items;
  }

  window.fnAudioShufflePolicy = { MAX_ITEMS, shuffle };
})();
