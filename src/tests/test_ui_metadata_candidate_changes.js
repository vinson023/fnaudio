// R495: the candidate dialog promises, in words, that confirming only fills
// blanks and replaces values the scanner guessed from the file name -- a real
// tag is never touched.  That promise is three branches in one function, and it
// is the only thing standing between "补全" and "覆盖用户标签", so the branches are
// pinned here rather than inferred from the right-hand preview column.
//
// The tables are lifted out of app.js instead of being copied: a second copy of
// the placeholder list would drift from the one the server's PLACEHOLDER_NAMES
// mirrors, and the test would keep passing while the shipped code changed.

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");

const app = fs.readFileSync(path.join(__dirname, "..", "app", "ui", "app.js"), "utf8");

function tables() {
  const fields = app.match(/const METADATA_CANDIDATE_FIELDS = \[[\s\S]*?\];/);
  const placeholders = app.match(/const METADATA_CANDIDATE_PLACEHOLDERS = new Set\(\[[\s\S]*?\]\);/);
  assert.ok(fields, "the candidate field table must stay extractable");
  assert.ok(placeholders, "the placeholder set must stay extractable");
  return `${fields[0]}\n${placeholders[0]}\n`;
}

function sandbox() {
  const context = { String, Number, Math, Set, Array, Object };
  const code = names => names
    .map(name => {
      const match = app.match(new RegExp(`^function ${name}\\b[\\s\\S]*?^}`, "m"));
      assert.ok(match, `missing candidate change helper: ${name}`);
      return match[0];
    })
    .join("\n");
  vm.createContext(context);
  vm.runInContext(
    tables() + code(["metadataCandidateFieldChange", "metadataCandidateChanges"]),
    context,
  );
  return context;
}

const ctx = sandbox();
const change = (item, candidate, field) => ctx.metadataCandidateFieldChange(item, candidate, field);
// Values built inside the sandbox carry that realm's prototypes, so they are
// copied into plain objects before comparison; the shape is what is under test,
// not which Object constructor produced it.  Array.from matters as much as the
// spread: Array.prototype.map on a sandbox array would build its result in the
// sandbox realm and fail the same way.
const plain = value => (value === null ? null : { ...value });
const plainChanges = (item, candidate) => Array.from(
  ctx.metadataCandidateChanges(item, candidate),
  entry => ({ field: entry.field, state: entry.state, label: entry.label, current: entry.current, next: entry.next }),
);

test("a candidate with nothing to say about a field is not a change at all", () => {
  // Absent, empty and whitespace-only all mean "the provider did not answer for
  // this field".  Listing them would put rows in the preview that confirm would
  // silently skip.
  for (const value of [undefined, null, "", "   "]) {
    assert.equal(change({ title: "Old" }, { title: value }, "title"), null, JSON.stringify(value));
  }
  assert.equal(change({ title: "Old" }, null, "title"), null);
});

test("an empty or placeholder current value is a fill", () => {
  assert.deepEqual(plain(change({ album: "" }, { album: "叶惠美" }, "album")), {
    state: "fill", current: "", next: "叶惠美",
  });
  assert.equal(change({}, { album: "叶惠美" }, "album").state, "fill");
  // The placeholders mirror the service's PLACEHOLDER_NAMES: a scanner that gave
  // up writes one of these, and the row is still a blank for our purposes.
  for (const placeholder of ["未分类", "未知专辑", "未知歌手", "unknown album"]) {
    assert.equal(
      change({ album: placeholder }, { album: "叶惠美" }, "album").state,
      "fill",
      placeholder,
    );
  }
});

test("identical text is kept whatever its source, and that check runs first", () => {
  // Same value, different case, is not a change worth showing -- and the case
  // where the current value *is* a placeholder has to land here too, because the
  // candidate itself is unchanged.  Filling a field with what it already says
  // would make the preview lie about the write.
  const same = [
    [{ title: "双截棍" }, { title: "双截棍" }],
    [{ artist: "周杰伦" }, { artist: "周杰伦" }],
    [{ artist: "Jay Chou" }, { artist: "jay chou" }],
    [{ album: " 未分类 " }, { album: "未分类" }],
  ];
  for (const [item, candidate] of same) {
    const field = Object.keys(candidate)[0];
    assert.equal(change(item, candidate, field).state, "keep", JSON.stringify(candidate));
  }
});

test("only a value the scanner guessed may be replaced", () => {
  // The whole safety of the feature rests on this: a value whose source is the
  // tag came from the user (or from a previous confirmed write) and is not ours
  // to overwrite, while a value inferred from the file name is.
  assert.equal(
    change({ album: "周杰伦 - 叶惠美", metadata_source: { album: "filename" } }, { album: "叶惠美" }, "album").state,
    "replace",
  );
  assert.equal(
    change({ album: "周杰伦 - 叶惠美" }, { album: "叶惠美" }, "album").state,
    "replace",
    "an item with no source map at all is not a tag",
  );
  assert.deepEqual(
    plain(change({ album: "旧专辑", metadata_source: { album: "tag" } }, { album: "叶惠美" }, "album")),
    { state: "keep", current: "旧专辑", next: "叶惠美" },
    "a real tag is kept even when the candidate disagrees",
  );
});

test("the preview counts writes, not rows", () => {
  const item = {
    title: "", artist: "周杰伦", album: "周杰伦 - 叶惠美",
    metadata_source: { artist: "tag", album: "filename" },
  };
  const candidate = { title: "双截棍", artist: "周杰伦", album: "叶惠美", date: "2003" };
  const changes = plainChanges(item, candidate);
  const byField = Object.fromEntries(changes.map(entry => [entry.field, entry.state]));
  assert.deepEqual(byField, { title: "fill", artist: "keep", album: "replace", date: "fill" });
  // Every row carries its human label; the preview must not print raw field names.
  for (const entry of changes) {
    assert.ok(entry.label && entry.label !== entry.field, JSON.stringify(entry));
  }
  // No candidate means no rows at all.  A candidate with no track behind it is
  // the dialog's defensive case: every field the provider answered reads as a
  // fill, which is what the row would say if the track had an empty tag.
  assert.equal(plainChanges(item, null).length, 0);
  assert.deepEqual(
    plainChanges(null, candidate).map(entry => entry.state),
    ["fill", "fill", "fill", "fill"],
  );
});

test("artwork is a two-state row of its own, because it is not a tag value", () => {
  // Cover artwork has no text value to compare, so it cannot go through the field
  // table: it is either already present or it will be downloaded.
  const missing = plainChanges({}, { image_url: "http://x/cover.jpg" });
  assert.deepEqual(missing.map(entry => [entry.field, entry.state]), [["artwork", "fill"]]);

  const present = plainChanges({ metadata_artwork_id: "abc" }, { image_url: "http://x/cover.jpg" });
  assert.deepEqual(present.map(entry => [entry.field, entry.state]), [["artwork", "keep"]]);

  assert.deepEqual(
    plainChanges({}, { title: "x" }).filter(entry => entry.field === "artwork"),
    [],
    "no image means no artwork row",
  );
});

test("the shipped renderer and button derive from these states, not from their own copy", () => {
  // A second classification would let the preview disagree with what is written.
  const preview = app.match(/^function renderMetadataCandidatePreview\b[\s\S]*?^}/m);
  assert.ok(preview, "missing renderMetadataCandidatePreview");
  assert.match(preview[0], /is-\$\{change\.state\}/, "each row is classed by the state it was given");
  assert.match(preview[0], /state === "keep"/, "kept rows are drawn differently from writes");
  assert.match(preview[0], /state === "replace" && change\.current/, "only a replacement shows the old value");

  const sync = app.match(/^function syncMetadataCandidateSelection\b[\s\S]*?^}/m);
  assert.ok(sync, "missing syncMetadataCandidateSelection");
  assert.match(sync[0], /renderMetadataCandidatePreview\(/, "the preview is refreshed on selection");
  assert.match(sync[0], /writing \? `确认并写入 \$\{writing\} 项` : "确认匹配"/,
    "the button must state how many fields will be written");
});
