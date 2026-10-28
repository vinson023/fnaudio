"""Exercise Android's real stylesheet replacement with the local JDK, offline."""
import base64
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTIVITY = ROOT / 'android-client/app/src/main/java/com/fnaudio/client/ui/MainActivity.java'


class AndroidBundledStylesTests(unittest.TestCase):
    def test_every_extra_stylesheet_is_inlined_in_declared_order(self):
        html = (ROOT / 'src/app/ui/index.html').read_text(encoding='utf-8')
        names = re.findall(r'<link rel="stylesheet" href="([^?\"]+)', html)
        activity = ACTIVITY.read_text(encoding='utf-8')
        match = re.search(r'String\[\] additionalStyles = \{([^}]+)\}', activity)
        self.assertIsNotNone(match, 'Android must embed the additional styles, without fetching them from an older NAS')
        embedded = re.findall(r'"([^\"]+\.css)"', match[1])
        self.assertEqual(names, ['app.css'] + embedded)

    def test_real_java_replacement_keeps_css_order_and_literal_content(self):
        source = ACTIVITY.read_text(encoding='utf-8')
        marker = '    private static String inlineBundledStylesheet('
        self.assertIn(marker, source, 'Missing Android stylesheet inliner')
        method = source[source.index(marker):source.index('    private static String inlineBundledScript(', source.index(marker))]
        javac = shutil.which('javac')
        java = shutil.which('java')
        self.assertIsNotNone(javac, 'A local JDK is required for this regression')
        self.assertIsNotNone(java)
        html = (ROOT / 'src/app/ui/index.html').read_text(encoding='utf-8')
        # $ and backslashes are valid CSS content, but unsafe replacement strings
        # unless Matcher.quoteReplacement is used by the actual Java helper.
        tokens = ':root { --marker: "$1\\value"; }\n/* tokens */'
        theme = 'body { color: var(--ui-text); }\n/* theme */'
        harness = '''import java.util.Base64;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.regex.*;
public class StyleHarness {
METHOD
public static void main(String[] args) throws Exception {
String html = Files.readString(Path.of(args[0]), StandardCharsets.UTF_8);
for (int i=1; i<args.length; i+=2) {
html = inlineBundledStylesheet(html,args[i],new String(Base64.getDecoder().decode(args[i+1]),StandardCharsets.UTF_8));
}
System.out.print(Base64.getEncoder().encodeToString(html.getBytes(StandardCharsets.UTF_8)));
}
}'''.replace('METHOD', method)
        encoded = lambda value: base64.b64encode(value.encode('utf-8')).decode('ascii')
        with tempfile.TemporaryDirectory(prefix='fnaudio-style-java-') as folder:
            path = Path(folder) / 'StyleHarness.java'
            path.write_text(harness, encoding='utf-8')
            html_path = Path(folder) / 'index.html'
            html_path.write_text(html, encoding='utf-8')
            compile_result = subprocess.run([javac, '-encoding', 'UTF-8', str(path)], capture_output=True, timeout=30)
            if compile_result.returncode != 0:
                self.fail(compile_result.stderr.decode('utf-8', errors='replace'))
            result = subprocess.run([java, '-cp', folder, 'StyleHarness', str(html_path), 'design-tokens.css', encoded(tokens), 'fnos-theme.css', encoded(theme)], check=True, capture_output=True, timeout=30)
        result = base64.b64decode(result.stdout).decode('utf-8')
        self.assertIn(tokens, result)
        self.assertIn(theme, result)
        self.assertNotRegex(result, r'<link[^>]+href="(?:design-tokens|fnos-theme)\.css')
        self.assertLess(result.index('href="app.css'), result.index(tokens))
        self.assertLess(result.index(tokens), result.index(theme))
        self.assertIn('rel="icon"', result)
        self.assertIn('id="playBtn"', result)


if __name__ == '__main__':
    unittest.main()
