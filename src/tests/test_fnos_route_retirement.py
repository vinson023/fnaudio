"""R118: the always-false fnOS route group is retired, so pin what "retired" means.

TODO L84 named seven ``if False and`` route blocks around the fnOS accessible-folder
endpoints (three in ``app/server/server.py``, four in ``app/ui/cgi_proxy.py``) and
offered two ways out: close the feature for real, or replace the false literal with a
configuration switch. The forensic reason for choosing the first is inside the deleted
blocks themselves: they called ``get_shared_accessible_folders`` and
``del_shared_accessible_folder``, and neither name was ever imported -- line
106 of the committed HEAD version of ``server.py`` pulled only ``FnosApiError``
and ``call_trim_api`` out of
``fnos_api``, and ``call_trim_api`` had no other user in the file. A configuration
switch would not have enabled a feature, it would have converted every request into a
NameError.

The assertions are deliberately two-sided. Half of them fail if the dead code comes
back; the other half fail if the deletion reached too far, because the live TRIM token
chain, the service-port lookup and the local configuration route all pass through the
same two files.

This file is excluded from its own forbidden-name scan: naming a forbidden literal is
unavoidable when the test is the record of the deletion. The exclusion is asserted to
cover exactly this one file, so the scan cannot be quietly widened later.
"""

import ast
from pathlib import Path
import os
import re
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER = REPO_ROOT / "src" / "app" / "server" / "server.py"
CGI_PROXY = REPO_ROOT / "src" / "app" / "ui" / "cgi_proxy.py"
FIXTURE = REPO_ROOT / "tools" / "ui_e2e_fixture.py"
LIBRARY = REPO_ROOT / "src" / "app" / "server" / "library.py"
FNOS_ENTRY = REPO_ROOT / "src" / "app" / "server" / "fnos_api.py"
FNOS_TEST = REPO_ROOT / "src" / "tests" / "test_fnos_api.py"

DEAD_FUNCTIONS = (
    "trim_request",
    "read_config_payload",
    "merge_paths",
    "send_local_config_update",
    "response_code",
    "json_object_or_empty",
)
DEAD_CONSTANTS = (
    "MAX_CONFIG_RESPONSE_BYTES",
    "MAX_TRIM_GATEWAY_RESPONSE_BYTES",
    "MAX_MERGED_LIBRARY_PATHS",
    "MAX_MERGED_LIBRARY_PATH_CHARS",
)
DEAD_ENDPOINT_STRINGS = ("/api/fnos", "shared-folders", "auth-debug", "trim.file.")
THIS_FILE = Path(__file__).resolve()


def text(path):
    return path.read_text(encoding="utf-8")


def source_files():
    """Every packaged/verified Python source, minus caches and vendored trees."""
    roots = [REPO_ROOT / "src" / "app", REPO_ROOT / "src" / "tests", REPO_ROOT / "tools"]
    for root in roots:
        if root.is_file():
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                name
                for name in dirnames
                if name not in {"__pycache__", "runtime", "apk-analysis", "node_modules", "build"}
            ]
            if root.name == "tools" and Path(dirpath) != root:
                # tools has only top-level scripts under review; the rest is tooling
                # payload (SDK caches, virtualenvs) that no round is expected to audit.
                dirnames[:] = []
            for filename in sorted(filenames):
                if filename.endswith(".py"):
                    yield Path(dirpath) / filename


def scanned_sources():
    return [path for path in source_files() if path.resolve() != THIS_FILE]


def find_forbidden(names, paths):
    offenders = []
    for path in paths:
        body = text(path)
        for name in names:
            pattern = re.compile(r"\b%s\b" % re.escape(name))
            for number, line in enumerate(body.splitlines(), 1):
                if pattern.search(line):
                    offenders.append(
                        "%s:%s names %s" % (path.relative_to(REPO_ROOT).as_posix(), number, name)
                    )
                    break
    return offenders


def constant_false_tests(path):
    tree = ast.parse(text(path), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if isinstance(test, ast.Constant) and test.value is False:
            found.append(node.lineno)
        elif isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
            if any(
                isinstance(value, ast.Constant) and value.value is False
                for value in test.values
            ):
                found.append(node.lineno)
    return found


class FnOsRouteRetirementTests(unittest.TestCase):
    def test_the_scan_excludes_only_this_record_of_the_deletion(self):
        self.assertNotIn(THIS_FILE, scanned_sources())
        self.assertGreaterEqual(len(scanned_sources()), 200)
        for path in (SERVER, CGI_PROXY, FIXTURE, LIBRARY):
            self.assertIn(path, scanned_sources())

    def test_no_constant_false_guard_is_left_in_the_http_entry_points(self):
        offenders = []
        for path in (SERVER, CGI_PROXY, FIXTURE):
            offenders.extend("%s:%s" % (path.name, line) for line in constant_false_tests(path))
            if "if False and" in text(path):
                offenders.append("%s: literal guard text" % path.name)
        self.assertEqual(offenders, [])

    def test_the_fnos_endpoint_strings_are_gone_from_the_http_sources(self):
        self.assertEqual(find_forbidden(DEAD_ENDPOINT_STRINGS, [SERVER, CGI_PROXY, FIXTURE]), [])

    def test_the_functions_only_the_deleted_blocks_called_are_gone_everywhere(self):
        self.assertEqual(find_forbidden(DEAD_FUNCTIONS, scanned_sources()), [])

    def test_the_limits_only_the_deleted_blocks_read_are_gone_everywhere(self):
        self.assertEqual(find_forbidden(DEAD_CONSTANTS, scanned_sources()), [])

    def test_the_dead_entry_point_and_its_test_module_are_not_in_the_tree(self):
        self.assertFalse(FNOS_ENTRY.exists())
        self.assertFalse(FNOS_TEST.exists())
        self.assertEqual(find_forbidden(("fnos_api",), scanned_sources()), [])

    def test_the_server_stops_importing_the_path_merging_helpers_and_the_library_keeps_them(self):
        for name in ("normalize_library_paths", "merge_library_paths"):
            self.assertEqual(find_forbidden((name,), [SERVER]), [])
            self.assertTrue(re.search(r"\b%s\b" % name, text(LIBRARY)), name)

    def test_cgi_proxy_dropped_socket_but_kept_the_live_authentication_chain(self):
        proxy = text(CGI_PROXY)
        self.assertEqual(find_forbidden(("socket",), [CGI_PROXY]), [])
        for live in (
            "def trim_token(",
            "def normalize_trim_token(",
            "MAX_TRIM_TOKEN_CHARS",
            "def service_port(",
            "def local_service_ready(",
            "def wait_for_service(",
            "def write_service_unavailable(",
            "def main(",
        ):
            self.assertIn(live, proxy)
        self.assertIn("fnos-token", proxy)

    def test_the_routes_that_survived_are_still_wired_in_the_same_order(self):
        server_body = text(SERVER)
        for live in (
            'if path == "/api/health":',
            'if parsed.path == "/api/config/library":',
            'if path == "/api/playback/targets":',
            'return self.send_json({"error": "not found"}, 404)',
            "def serve_static(self, path, query=None, head_only=False):",
        ):
            self.assertIn(live, server_body)
        fixture_body = text(FIXTURE)
        self.assertIn('if path == "/api/config/library":', fixture_body)
        self.assertIn('if path.startswith("/api/"):', fixture_body)

    def test_the_retirement_test_module_is_itself_under_gate_control(self):
        manifest = REPO_ROOT / "SOURCE_MANIFEST.sha256"
        relative = "src/tests/test_fnos_route_retirement.py"
        listed = {
            line.split("  ", 1)[1]
            for line in text(manifest).splitlines()
            if "  " in line
        }
        self.assertIn(relative, listed)
        self.assertNotIn("src/app/server/fnos_api.py", listed)
        self.assertNotIn("src/tests/test_fnos_api.py", listed)


if __name__ == "__main__":
    unittest.main()
