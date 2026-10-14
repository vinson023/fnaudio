(() => {
  function create(options = {}) {
    if (!options || typeof options !== "object") options = {};
    const doc = options.document || globalThis.document;
    const win = options.window || globalThis.window || globalThis;
    const getImageRoot = typeof options.getImageRoot === "function" ? options.getImageRoot : () => null;
    const getScrollRoot = typeof options.getScrollRoot === "function" ? options.getScrollRoot : () => null;
    let requestedConcurrency = 4;
    if (typeof options.maxConcurrent !== "boolean" && options.maxConcurrent != null) {
      try {
        const numeric = Number(options.maxConcurrent);
        if (Number.isFinite(numeric)) requestedConcurrency = numeric;
      } catch (_) { /* malformed configuration falls back to the default */ }
    }
    const maxConcurrent = Math.min(32, Math.max(1, Math.floor(requestedConcurrency) || 1));
    let initialPriorityCount = 8;
    if (options && options.initialPriorityCount != null) {
      try {
        const numeric = Number(options.initialPriorityCount);
        if (Number.isFinite(numeric)) initialPriorityCount = numeric;
      } catch (_) { /* malformed configuration falls back to the default */ }
    }
    initialPriorityCount = Math.min(32, Math.max(0, Math.floor(initialPriorityCount)));
    const maxQueued = 4096;
    const maxErrorRetries = 1;
    const onEvent = typeof options.onEvent === "function" ? options.onEvent : null;
    const emit = type => {
      try { onEvent?.(type); } catch (_) { /* diagnostics must not affect loading */ }
    };
    const scheduleRetry = (callback, delay) => {
      const timer = win && typeof win.setTimeout === "function"
        ? win.setTimeout
        : (typeof setTimeout === "function" ? setTimeout : null);
      if (timer) timer(callback, delay);
      else callback();
    };
    let generation = 0;

    const cancel = run => {
      if (!run || run.cancelled) return;
      run.cancelled = true;
      run.observer?.disconnect();
      run.queue.length = 0;
      for (const active of run.activeImages.values()) {
        if (!active || active.settled) continue;
        active.settled = true;
        active.cleanup?.();
      }
      run.activeImages.clear();
      run.inFlight = 0;
    };
    let activeRun = null;

    const hydrate = () => {
      const requestedImageRoot = getImageRoot();
      // Playback/metadata decorations can cause the keyed list to commit
      // again while cover requests are still in flight.  Keep the existing
      // observer/queue for the same root and only discover newly inserted
      // images; cancelling the run here made slow WebViews re-request covers
      // and briefly repaint rows with the fallback glyph.
      if (activeRun && !activeRun.cancelled
        && activeRun.imageRoot === requestedImageRoot
        && typeof activeRun.reconcile === "function") {
        return activeRun.reconcile();
      }
      cancel(activeRun);
      generation += 1;
      const run = {
        generation,
        cancelled: false,
        imageRoot: requestedImageRoot,
        observer: null,
        reconcile: null,
        queue: [],
        inFlight: 0,
        activeImages: new Map(),
        fallbackImages: null,
        fallbackIndex: 0,
        dropped: 0,
      };
      activeRun = run;
      const imageRoot = requestedImageRoot;
      const discoveredImages = imageRoot?.querySelectorAll ? imageRoot.querySelectorAll("img[data-cover-src]") : [];
      // The first screenful may deliberately ship with an eager `src` so the
      // browser can start fetching before this scheduler runs.  Those nodes
      // must not also enter the lazy queue: doing so reports a misleading
      // idle queue while eight browser requests are already in flight, and a
      // later incremental render can needlessly re-hydrate them.  Preserve
      // the declarative URL for keyed DOM comparison, then make the scheduler
      // own only images that it still has to start.
      const images = [];
      for (const image of Array.from(discoveredImages || [])) {
        const source = image?.dataset?.coverSrc;
        if (source && image?.hasAttribute?.("src")) {
          image.dataset.coverLoadedSrc = source;
          image.removeAttribute("data-cover-src");
          continue;
        }
        images.push(image);
      }
      const isActive = () => activeRun === run && !run.cancelled;
      const start = image => {
        if (!isActive()) return;
        const source = image?.dataset?.coverSrc;
        if (!source || image.hasAttribute("src")) return;
        run.inFlight += 1;
        emit("request");
        const active = { settled: false };
        run.activeImages.set(image, active);
        const finish = event => {
          if (active.settled) return;
          active.settled = true;
          active.cleanup?.();
          active.cleanup = null;
          run.activeImages.delete(image);
          run.inFlight = Math.max(0, run.inFlight - 1);
          if (!isActive()) return;
          if (event?.type === "load") {
            emit("load");
            image.removeAttribute?.("data-cover-retry-count");
            image.removeAttribute?.("hidden");
            image.hidden = false;
            if (image.style) image.style.visibility = "visible";
          } else if (event?.type === "error" && image.isConnected
            && source && Number(image.dataset?.coverRetryCount || 0) < maxErrorRetries) {
            emit("error");
            emit("retry");
            const retryCount = Number(image.dataset?.coverRetryCount || 0) + 1;
            image.dataset.coverRetryCount = String(retryCount);
            image.dataset.coverSrc = source;
            image.removeAttribute("src");
            image.hidden = false;
            if (image.style) image.style.visibility = "hidden";
            scheduleRetry(() => {
              if (!isActive() || !image.isConnected || image.dataset?.coverSrc !== source) return;
              image.dataset.coverQueued = "";
              enqueue(image, true);
            }, 450);
          } else if (event?.type === "error") {
            // Keep the row's music-glyph fallback visible after the bounded
            // retry is exhausted. Leaving a failed <img> displayed exposes
            // the browser's broken-image indicator for stale/missing artwork.
            image.hidden = true;
            if (image.style) image.style.visibility = "hidden";
            emit("error");
          }
          pump();
        };
        image.addEventListener("load", finish, { once: true });
        image.addEventListener("error", finish, { once: true });
        active.cleanup = () => {
          image.removeEventListener?.("load", finish);
          image.removeEventListener?.("error", finish);
        };
        // Keep the declarative source beside the browser-resolved `src`.  A
        // relative source becomes absolute after assignment, while keyed row
        // commits compare against freshly rendered relative markup. Retaining
        // this bounded string lets that comparison ignore scheduler-owned DOM
        // state without hiding a real cover URL change.
        image.dataset.coverLoadedSrc = source;
        // The row markup also has an inline error fallback for eager images.
        // Mark scheduler-owned lazy images so that fallback does not schedule
        // a second retry alongside this listener.
        image.dataset.coverSchedulerOwned = "1";
        image.src = source;
        image.removeAttribute("data-cover-src");
      };
      const pump = () => {
        if (!isActive()) return;
        while (run.inFlight < maxConcurrent && run.queue.length) {
          // Prefer visible/eager jobs over look-ahead work, but retain their
          // DOM enqueue order. The old unshift-based priority path reversed
          // a burst of visible rows (8,7,6...) and made covers appear to fill
          // from the bottom upward on slower WebViews.
          const priorityIndex = run.queue.findIndex(job => job.priority);
          const job = run.queue.splice(priorityIndex >= 0 ? priorityIndex : 0, 1)[0];
          if (job.generation !== run.generation || !job.image?.isConnected) continue;
          start(job.image);
        }
        while (run.inFlight < maxConcurrent && run.fallbackImages && run.fallbackIndex < run.fallbackImages.length) {
          enqueue(run.fallbackImages[run.fallbackIndex++], true);
        }
      };
      const enqueue = (image, priority = false) => {
        if (!isActive() || !image?.dataset?.coverSrc || image.dataset.coverQueued === String(run.generation)) return false;
        if (run.queue.length >= maxQueued && !priority) {
          run.dropped += 1;
          return false;
        }
        image.dataset.coverQueued = String(run.generation);
        const job = { image, generation: run.generation, priority: Boolean(priority) };
        // FIFO is intentional for both queue classes. `pump()` selects the
        // oldest priority entry before look-ahead work without reversing rows
        // that intersect in the same observer callback.
        run.queue.push(job);
        if (run.queue.length > maxQueued) {
          // Keep the same newest-normal-job eviction without relying on newer
          // array APIs that are absent from older Android WebViews.
          let normalIndex = -1;
          for (let index = run.queue.length - 1; index >= 0; index -= 1) {
            if (!run.queue[index].priority) {
              normalIndex = index;
              break;
            }
          }
          const evicted = normalIndex >= 0
            ? run.queue.splice(normalIndex, 1)[0]
            : run.queue.pop();
          // The evicted row still advertises data-cover-src, so its queue
          // marker has to go.  Leaving it set hides the image from every later
          // reconcile() and the observer already released it, which turns one
          // full queue into a cover that never loads again in this generation.
          if (evicted?.image) evicted.image.dataset.coverQueued = "";
          run.dropped += 1;
        }
        pump();
        return true;
      };
      run.reconcile = () => {
        if (!isActive()) return { generation: run.generation, queued: 0, inFlight: 0, dropped: run.dropped };
        // A keyed commit may detach an image while its network request is
        // still pending. Browsers do not guarantee a terminal event for a
        // detached image, so release that slot explicitly; the once-guarded
        // listener prevents a later stale load/error event from decrementing
        // the counter twice.
        for (const image of Array.from(run.activeImages.keys())) {
          if (image?.isConnected) continue;
          const active = run.activeImages.get(image);
          if (!active || active.settled) continue;
          active.settled = true;
          active.cleanup?.();
          active.cleanup = null;
          run.activeImages.delete(image);
          run.inFlight = Math.max(0, run.inFlight - 1);
        }
        const discovered = imageRoot?.querySelectorAll ? imageRoot.querySelectorAll("img[data-cover-src]") : [];
        const freshImages = [];
        for (const image of Array.from(discovered || [])) {
          const source = image?.dataset?.coverSrc;
          if (source && image?.hasAttribute?.("src")) {
            image.dataset.coverLoadedSrc = source;
            image.removeAttribute("data-cover-src");
            continue;
          }
          // The observer already owns every still-offscreen node from an
          // earlier pass. Without that marker each commit would re-classify
          // the whole offscreen tail as fresh and let its first burst jump the
          // queue, so an appended page kept warming covers the user never
          // reached.
          if (source
            && image.dataset.coverQueued !== String(run.generation)
            && image.dataset.coverObserved !== String(run.generation)) freshImages.push(image);
        }
        // Legacy WebViews use a bounded cursor instead of an observer. Keep
        // that cursor append-only so newly committed rows are discovered
        // without restarting already active loads.
        if (!run.observer && run.fallbackImages) {
          const known = new Set(run.fallbackImages);
          for (const image of freshImages) {
            if (!known.has(image)) run.fallbackImages.push(image);
          }
          pump();
          return { generation: run.generation, queued: run.queue.length, inFlight: run.inFlight, dropped: run.dropped };
        }
        const eagerCount = Math.min(initialPriorityCount, freshImages.length);
        for (let index = 0; index < freshImages.length; index += 1) {
          const image = freshImages[index];
          const priority = index < eagerCount;
          if (priority) {
            if (enqueue(image, true)) run.observer?.unobserve(image);
            continue;
          }
          // Offscreen artwork stays lazy: hand it to the observer instead of
          // the queue, mirroring the bounded burst of the first commit.
          image.dataset.coverObserved = String(run.generation);
          run.observer?.observe(image);
        }
        pump();
        return { generation: run.generation, queued: run.queue.length, inFlight: run.inFlight, dropped: run.dropped };
      };
      const Observer = win?.IntersectionObserver;
      if (typeof Observer !== "function") {
        // Legacy WebViews do not provide intersection events.  Keep the DOM
        // NodeList as a cursor rather than queueing every cover at once.
        run.fallbackImages = images;
        pump();
        return { generation: run.generation, queued: run.queue.length, inFlight: run.inFlight, dropped: run.dropped };
      }
      run.observer = new Observer(entries => {
        entries.forEach(entry => {
          if (!isActive()) return;
          if (!entry.isIntersecting) return;
          const root = entry.rootBounds;
          const bounds = entry.boundingClientRect;
          const visible = !root || (bounds.bottom >= root.top && bounds.top <= root.bottom);
          if (enqueue(entry.target, visible)) run.observer?.unobserve(entry.target);
        });
      }, { root: getScrollRoot(), rootMargin: "280px 0px" });
      // Start only the first few rows immediately. IntersectionObserver is
      // asynchronous on older WebViews, and waiting for its first callback
      // leaves the visible page blank for a frame or two. The bounded burst
      // preserves lazy loading for the rest of the library.
      const eagerCount = Math.min(initialPriorityCount, images.length);
      for (let index = 0; index < eagerCount; index += 1) {
        if (enqueue(images[index], true)) run.observer.unobserve(images[index]);
      }
      for (let index = eagerCount; index < images.length; index += 1) {
        images[index].dataset.coverObserved = String(run.generation);
        run.observer.observe(images[index]);
      }
      return { generation: run.generation, queued: run.queue.length, inFlight: run.inFlight, dropped: run.dropped };
    };
    return {
      hydrate,
      stop() {
        cancel(activeRun);
        generation += 1;
        activeRun = null;
      },
      snapshot() {
        return activeRun
          ? { generation: activeRun.generation, queued: activeRun.queue.length, inFlight: activeRun.inFlight, dropped: activeRun.dropped }
          : { generation, queued: 0, inFlight: 0, dropped: 0 };
      },
    };
  }

  globalThis.fnAudioCoverLoadScheduler = { create };
})();
