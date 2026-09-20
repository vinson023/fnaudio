import ast
from collections import defaultdict
from pathlib import Path
import unittest


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
MOJIBAKE_FRAGMENTS = (
    "閺堫",
    "鏈",
    "娌℃",
    "绯荤",
    "涓嶆",
    "娴嬭",
    "鏃犳",
    "杈撳",
    "璁惧",
    "闊抽",
)


def source_trees():
    for path in APP_ROOT.rglob("*.py"):
        yield path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def nested_blocks(node):
    for field in ("body", "orelse", "finalbody"):
        block = getattr(node, field, None)
        if isinstance(block, list):
            yield field, block
    if isinstance(node, ast.Try):
        for index, handler in enumerate(node.handlers):
            yield "handler[%d]" % index, handler.body
    if isinstance(node, ast.Match):
        for index, case in enumerate(node.cases):
            yield "case[%d]" % index, case.body


class SourceHygieneTests(unittest.TestCase):
    def test_metadata_service_keeps_provider_limits_single_sourced(self):
        path = APP_ROOT / "server" / "metadata_service.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assignments = defaultdict(list)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {
                        "MAX_PROVIDER_RESPONSE_BYTES",
                        "MAX_PROVIDER_LYRICS_BYTES",
                    }:
                        assignments[target.id].append(node.lineno)
        self.assertEqual(assignments, {})

    def test_todo_checklist_entries_are_unique(self):
        todo_path = Path(__file__).resolve().parents[2] / "TODO.md"
        lines = [line.strip() for line in todo_path.read_text(encoding="utf-8").splitlines()]
        entries = [line for line in lines if line.startswith("- [")]
        duplicates = [line for line, count in __import__("collections").Counter(entries).items() if count > 1]
        self.assertEqual(duplicates, [])

    def test_hygiene_scope_covers_all_packaged_python(self):
        paths = {path.relative_to(APP_ROOT).as_posix() for path, _tree in source_trees()}
        self.assertIn("server/server.py", paths)
        self.assertIn("ui/cgi_proxy.py", paths)

    def test_python_strings_do_not_contain_known_mojibake(self):
        failures = []
        for path, tree in source_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                matches = [part for part in MOJIBAKE_FRAGMENTS if part in node.value]
                if matches:
                    failures.append("%s:%s %r" % (path, node.lineno, matches))
        self.assertEqual(failures, [])

    def test_python_scopes_do_not_redefine_names(self):
        failures = []
        for path, tree in source_trees():
            scopes = [(tree, "module")]
            scopes.extend((node, "class %s" % node.name) for node in ast.walk(tree) if isinstance(node, ast.ClassDef))
            for scope, label in scopes:
                definitions = defaultdict(list)
                for node in scope.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        definitions[node.name].append(node.lineno)
                for name, lines in definitions.items():
                    if len(lines) > 1:
                        failures.append("%s:%s duplicate %s at %s" % (path, label, name, lines))
        self.assertEqual(failures, [])

    def test_literal_dicts_do_not_repeat_keys(self):
        failures = []
        for path, tree in source_trees():
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                keys = defaultdict(list)
                for key in node.keys:
                    if isinstance(key, ast.Constant) and isinstance(key.value, (str, int, float, bytes)):
                        keys[(type(key.value).__name__, key.value)].append(key.lineno)
                for key, lines in keys.items():
                    if len(lines) > 1:
                        failures.append("%s duplicate key %r at %s" % (path, key, lines))
        self.assertEqual(failures, [])

    def test_blocks_do_not_continue_after_unconditional_terminators(self):
        failures = []

        def visit(node, path):
            for field, block in nested_blocks(node):
                terminated_at = None
                for statement in block:
                    if terminated_at is not None:
                        failures.append(
                            "%s:%s follows terminator at %s in %s.%s"
                            % (path, statement.lineno, terminated_at, type(node).__name__, field)
                        )
                    if isinstance(statement, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                        terminated_at = statement.lineno
                    visit(statement, path)

        for path, tree in source_trees():
            visit(tree, path)
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
