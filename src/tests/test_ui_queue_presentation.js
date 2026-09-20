const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const source = fs.readFileSync("app/ui/queue_presentation.js", "utf8");
const context = vm.createContext({ window: {} });
vm.runInContext(source, context);
const presentation = context.window.fnAudioQueuePresentation;

assert.equal(presentation.pageForQueueIndex(3, [{ queueIndex: 4 }, { queueIndex: 3 }], 1), 2);
assert.equal(presentation.pageForQueueIndex(99, [{ queueIndex: 4 }], 120), 1);
assert.equal(presentation.pageForQueueIndex({ valueOf() { throw new Error("must not coerce"); } }, [{ queueIndex: 4 }], 120), 1);
assert.equal(presentation.pageForQueueIndex(2, [{ queueIndex: 1 }, { queueIndex: 2 }], 1.9), 2);
const oversizedQueue = Array.from({ length: 50001 }, (_, index) => ({ queueIndex: index }));
assert.equal(presentation.pageForQueueIndex(50000, oversizedQueue, 120), 1);
assert.doesNotThrow(() => presentation.queuePresentationPlan(null));
assert.deepEqual(JSON.parse(JSON.stringify(presentation.queuePresentationPlan(null))), { changed: false, page: 1, requiresFullRender: false, shouldScrollCurrent: false });
assert.deepEqual(
  JSON.parse(JSON.stringify(presentation.queuePresentationPlan({ view: "queue", previousIndex: 1, currentIndex: 2, previousPage: 1, currentPage: 1 }))),
  { changed: true, page: 1, requiresFullRender: false, shouldScrollCurrent: true },
);
assert.deepEqual(
  JSON.parse(JSON.stringify(presentation.queuePresentationPlan({ view: "queue", previousIndex: 1, currentIndex: 120, previousPage: 1, currentPage: 2 }))),
  { changed: true, page: 2, requiresFullRender: true, shouldScrollCurrent: true },
);
assert.deepEqual(
  JSON.parse(JSON.stringify(presentation.queuePresentationPlan({ view: "all", previousIndex: 1, currentIndex: 2, previousPage: 1, currentPage: 1 }))),
  { changed: false, page: 1, requiresFullRender: false, shouldScrollCurrent: false },
);

console.log("Queue presentation regression checks passed.");
