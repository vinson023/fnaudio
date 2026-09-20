import ast
from pathlib import Path
import unittest


class TestDiscoveryContractTests(unittest.TestCase):
    def test_unittest_discovery_does_not_silently_skip_top_level_test_functions(self):
        """The offline gate uses unittest discovery, not pytest collection."""
        root = Path(__file__).resolve().parent
        skipped = []
        for path in root.glob("test_*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    skipped.append(path.name + ":" + node.name)
        self.assertEqual(
            skipped,
            [],
            "unittest discovery skips top-level pytest-style tests; put them on a unittest.TestCase",
        )


if __name__ == "__main__":
    unittest.main()
