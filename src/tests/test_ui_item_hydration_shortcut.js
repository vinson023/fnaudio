const assert = require("assert");
const fs = require("fs");
const path = require("path");

const source = fs.readFileSync(path.join(__dirname, "../app/ui/app.js"), "utf8");
assert.match(source, /const missing = orderedIds\.filter\(id => !state\.itemCache\.has\(id\)\);\s*if \(!missing\.length\) return orderedIds\.map\(itemById\)\.filter\(Boolean\);/);
console.log("Item hydration cache shortcut regression checks passed.");
