"""Syntax guards for the shell scripts fnOS executes outside of Python.

Every file covered here is run by the app centre during install, start, stop,
upgrade or uninstall.  A parse error in one of them stays invisible to the
Python suite and to the packaged build: the app simply never comes up and the
only symptom on the NAS is a bare "error code 10330".  That is how
``persist_backend_port()`` reached HEAD -- an ``if`` whose condition carries a
here-document lost its ``then``, because the keyword has to follow the heredoc
terminator rather than the opening line.
"""

import pathlib
import re
import shutil
import subprocess
import unittest


SHELL_SCRIPTS = (
    "src/cmd/config_callback",
    "src/cmd/config_init",
    "src/cmd/install_callback",
    "src/cmd/install_init",
    "src/cmd/main",
    "src/cmd/uninstall_callback",
    "src/cmd/uninstall_init",
    "src/cmd/upgrade_callback",
    "src/cmd/upgrade_init",
    "src/app/ui/index.cgi",
)

# A compound header is only allowed to be followed by one of these words; the
# first reserved word seen after the header decides the verdict.
HEADER_KEYWORDS = {"if": "then", "elif": "then", "while": "do", "until": "do"}
STOP_WORDS = {
    "then", "else", "elif", "fi", "do", "done", "case", "esac",
    "for", "in", "select", "time", "{", "}", "function",
}

HEREDOC_RE = re.compile(r"<<(-?)[ \t]*([\'\"]?)([A-Za-z_][A-Za-z0-9_]*)")


def project_root():
    return pathlib.Path(__file__).resolve().parents[2]


def read_script(relative):
    return (project_root() / relative).read_text(encoding="utf-8").splitlines()


def scan_line(line):
    """Yield (index, char, in_quote) for a line, descending into command substitutions.

    A here-document marker such as the one in ``x="$(prog - "$(f)" <<'PY'")"``
    sits inside a double-quoted command substitution, so quoting has to restart
    inside ``$( )`` the way the shell actually does it.
    """
    stack = []
    quote = None
    depth = 0
    index = 0
    while index < len(line):
        char = line[index]
        if quote == "'":
            if char == "'":
                quote = None
            yield index, char, True
            index += 1
            continue
        if quote == '"':
            if char == "\\" and index + 1 < len(line):
                yield index, char, True
                yield index + 1, line[index + 1], True
                index += 2
                continue
            if char == '"':
                quote = None
            elif line.startswith("$(", index):
                stack.append((quote, depth))
                quote = None
                depth = 1
                yield index, char, False
                yield index + 1, line[index + 1], False
                index += 2
                continue
            yield index, char, True
            index += 1
            continue
        if depth:
            if char == "'" or char == '"':
                quote = char
                yield index, char, True
                index += 1
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    quote, depth = stack.pop()
            yield index, char, False
            index += 1
            continue
        if char in "'\"":
            quote = char
            yield index, char, True
            index += 1
            continue
        if char == "#" and (index == 0 or line[index - 1].isspace()):
            return
        if char == "<" and line.startswith("<<", index):
            match = HEREDOC_RE.match(line, index)
            if match:
                yield index, "<", False
                index = match.end() - 1
                yield index, "<", False
                index += 1
                continue
        yield index, char, False
        index += 1


def find_heredoc_openers(line):
    """Return (cut_index, dash, delimiter) for every ``<<WORD`` outside quotes."""
    found = []
    for index, char, quoted in scan_line(line):
        if quoted or char != "<" or not line.startswith("<<", index):
            continue
        match = HEREDOC_RE.match(line, index)
        if match:
            found.append((index, match.group(1) == "-", match.group(3)))
    return found


def strip_heredocs(lines):
    """Blank out here-document bodies; report how many opened and which never closed."""
    kept = []
    openers = 0
    pending = None
    for line in lines:
        if pending is not None:
            delimiter, dash = pending
            probe = line.strip() if dash else line.rstrip()
            if probe == delimiter:
                pending = None
            kept.append("")
            continue
        found = find_heredoc_openers(line)
        if found:
            cut, dash, delimiter = found[-1]
            kept.append(line[:cut])
            pending = (delimiter, dash)
            openers += 1
        else:
            kept.append(line)
    return kept, openers, pending


def tokenize(line):
    """Split one already-heredoc-stripped line into bare words."""
    words = []
    buffer = ""
    quote = None
    index = 0
    while index < len(line):
        char = line[index]
        if quote == "\'":
            if char == "\'":
                quote = None
            index += 1
            continue
        if quote == "\"":
            if char == "\\\\":
                index += 2
                continue
            if char == "\"":
                quote = None
            index += 1
            continue
        if char in "\'\"":
            quote = char
            index += 1
            continue
        if char == "#" and (not buffer or True) and (index == 0 or line[index - 1].isspace()):
            break
        if char.isspace() or char in ";|&()<>":
            if buffer:
                words.append(buffer)
                buffer = ""
            index += 1
            continue
        buffer += char
        index += 1
    if buffer:
        words.append(buffer)
    return words


class PackageShellScriptTests(unittest.TestCase):
    def test_every_covered_script_is_present_and_posix_sh(self):
        for relative in SHELL_SCRIPTS:
            lines = read_script(relative)
            self.assertTrue(lines, relative)
            self.assertTrue(lines[0].startswith("#!"), relative)
            self.assertIn("sh", lines[0], relative)

    def test_heredocs_are_all_closed(self):
        for relative in SHELL_SCRIPTS:
            _, openers, dangling = strip_heredocs(read_script(relative))
            self.assertIsNone(dangling, "%s leaves heredoc %r open" % (relative, dangling))

    def test_compound_headers_reach_their_body_keyword(self):
        for relative in SHELL_SCRIPTS:
            code, _, _ = strip_heredocs(read_script(relative))
            stream = []
            for number, line in enumerate(code, start=1):
                for word in tokenize(line):
                    stream.append((word, number))
            for position, (word, number) in enumerate(stream):
                if word not in HEADER_KEYWORDS:
                    continue
                wanted = HEADER_KEYWORDS[word]
                reached = None
                for follower, follower_line in stream[position + 1:]:
                    if follower in STOP_WORDS:
                        reached = (follower, follower_line)
                        break
                self.assertEqual(
                    reached,
                    (wanted, reached[1]) if reached else None,
                    "%s:%d `%s` never reaches %s (first reserved word after it: %r)"
                    % (relative, number, word, wanted, reached),
                )

    def find_shell(self):
        for name in ("bash", "sh"):
            found = shutil.which(name)
            if found:
                return found
        for candidate in (
            pathlib.Path(r"C:\Program Files\Git\bin\bash.exe"),
            pathlib.Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
        return None

    def test_scripts_parse_with_a_real_shell(self):
        shell = self.find_shell()
        if shell is None:
            self.skipTest("no POSIX shell on PATH, cannot run -n")
        root = project_root()
        for relative in SHELL_SCRIPTS:
            result = subprocess.run(
                [shell, "-n", str(root / relative)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                result.returncode,
                0,
                "%s fails to parse: %s" % (relative, (result.stderr or "").strip()[:400]),
            )


if __name__ == "__main__":
    unittest.main()
