"""Every script the page declares must be inlined by the Android client.

The Android app loads the same `index.html` the server serves, but it loads it
through `loadDataWithBaseURL` with an inlined document: each `<script src>` is
replaced by the file's bytes so a phone can open the player while the NAS is
still on an older UI build.  A module that `index.html` gains but
`MainActivity` does not know about stays a `<script src>` in that document, and
WebView then either fetches it over the network (wrong version) or fails on it
(missing function, blank screen).

That silent gap is what this file guards: the declared list, the two halves of
the Java list (the ten explicit replacements and `additionalScripts`), and the
real Java inlining run, which must leave no external script behind.
"""
import base64
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / 'src/app/ui/index.html'
UI = ROOT / 'src/app/ui'
ACTIVITY = ROOT / 'android-client/app/src/main/java/com/fnaudio/client/ui/MainActivity.java'


def declared_scripts():
    """Script names in the order `index.html` loads them."""
    html = INDEX.read_text(encoding='utf-8')
    return re.findall(r'<script\s+src="([^?"]+)', html)


def inline_plan(source):
    """The two lists `MainActivity` inlines from, as (explicit, additional)."""
    # The Java source spells the pattern `src=\"name\\.js"` inside a string
    # literal, so the name sits between one backslash and two.
    explicit = [name + '.js' for name in
                re.findall(r'src=\\?"([A-Za-z0-9_]+)\\\\.js', source)]
    block = re.search(r'String\[\] additionalScripts = \{([^}]+)\}', source)
    if block is None:
        return explicit, []
    return explicit, re.findall(r'"([^"]+\.js)"', block.group(1))


class AndroidBundledScriptsTests(unittest.TestCase):
    def test_every_declared_script_has_an_inline_path(self):
        declared = declared_scripts()
        self.assertGreater(len(declared), 50, 'index.html must declare the whole policy set')
        explicit, additional = inline_plan(ACTIVITY.read_text(encoding='utf-8'))
        self.assertTrue(explicit, 'Android must keep its explicit replacements for the first scripts')
        self.assertTrue(additional, 'Android must keep the additionalScripts list')

        handled = set(explicit) | set(additional)
        missing = [name for name in declared if name not in handled]
        self.assertEqual(missing, [], 'Android would leave these scripts as network fetches')
        orphaned = [name for name in additional if name not in declared]
        self.assertEqual(orphaned, [], 'Android inlines scripts the page no longer declares')
        duplicates = sorted({name for name in additional if additional.count(name) > 1})
        self.assertEqual(duplicates, [], 'a doubled entry inlines the same module twice')

    def test_both_halves_keep_the_document_order(self):
        # The explicit replacements are matched by name, not by position, so only
        # the additional list has to stay aligned with the page: a module that
        # reads a global installed later would break, and the page would not.
        declared = declared_scripts()
        explicit, additional = inline_plan(ACTIVITY.read_text(encoding='utf-8'))
        expected = [name for name in declared if name not in set(explicit)]
        self.assertEqual(additional, expected, 'Android must inline the remaining scripts in page order')

    def test_real_java_inlining_leaves_no_external_script(self):
        source = ACTIVITY.read_text(encoding='utf-8')
        marker = '    private static String inlineBundledScript('
        self.assertIn(marker, source, 'Missing Android script inliner')
        method = source[source.index(marker):source.index('\n    }', source.index(marker)) + len('\n    }')]
        javac = shutil.which('javac')
        java = shutil.which('java')
        self.assertIsNotNone(javac, 'A local JDK is required for this regression')
        self.assertIsNotNone(java)

        declared = declared_scripts()
        harness = '''import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Base64;
import java.util.List;
import java.util.regex.*;
public class ScriptHarness {
METHOD
public static void main(String[] args) throws Exception {
String html = Files.readString(Path.of(args[0]), StandardCharsets.UTF_8);
Path ui = Path.of(args[1]);
List<String> names = Files.readAllLines(Path.of(args[2]), StandardCharsets.UTF_8);
for (String name : names) {
String body = Files.readString(ui.resolve(name), StandardCharsets.UTF_8);
html = inlineBundledScript(html, name, body + "\\n/*MARK:" + name + "*/\\n");
}
System.out.print(Base64.getEncoder().encodeToString(html.getBytes(StandardCharsets.UTF_8)));
}
}'''.replace('METHOD', method)

        with tempfile.TemporaryDirectory(prefix='fnaudio-script-java-') as folder:
            path = Path(folder) / 'ScriptHarness.java'
            path.write_text(harness, encoding='utf-8')
            names_path = Path(folder) / 'names.txt'
            names_path.write_text('\n'.join(declared), encoding='utf-8')
            compiled = subprocess.run([javac, '-encoding', 'UTF-8', str(path)], capture_output=True, timeout=120)
            self.assertEqual(compiled.returncode, 0, compiled.stderr.decode('utf-8', 'replace'))
            run = subprocess.run(
                [java, '-cp', folder, 'ScriptHarness', str(INDEX), str(UI), str(names_path)],
                capture_output=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stderr.decode('utf-8', 'replace'))
            inlined = base64.b64decode(run.stdout).decode('utf-8')

        leftovers = re.findall(r'<script\s+src="([^"]+)"', inlined)
        self.assertEqual(leftovers, [], 'the Android document must not fetch any script')
        for name in declared:
            self.assertIn('/*MARK:%s*/' % name, inlined, 'Android dropped %s' % name)


if __name__ == "__main__":
    unittest.main()
