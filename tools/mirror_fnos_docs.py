#!/usr/bin/env python3
"""Mirror the fnOS application developer documentation into references/.

The two documents this project keeps coming back to are the fnOS application
development guide (https://developer.fnnas.com/docs/...) and the open API
reference (https://developer.fnnas.com/api/...).  Both are Docusaurus sites, so
the readable text of a page lives inside one <article> element whose markup is
heavily decorated with hashed class names, per-token <span> highlighting, an
anchor marker that is a zero width space, a mobile "table of contents" button
and a breadcrumb nav.

An earlier one-off dump of the same pages was checked into the reference tree as
plain text and turned out to be lossy in five ways that all matter when the
snapshot is the authority for packaging work:

  * 43 NUL bytes: the converter used U+0000 as an inline-code sentinel and never
    stripped it, so words such as "可<00>删除" were corrupted invisibly;
  * 0 of 416 code fences kept their language, because the language only appears
    in a class attribute that the text dump threw away;
  * 46 HTML tables degraded into pipe-prefixed lines with no separator row, so
    they no longer render as tables anywhere;
  * 15 screenshots were dropped completely;
  * the mobile "page overview" button label leaked into the body of all 34 pages.

This tool replaces that dump.  It is deliberately dependency-free (stdlib only),
deterministic for a given fetch date, and split so that the HTML -> Markdown
conversion can be unit tested offline against inline fixtures: only crawl() and
write_snapshot() touch the network.

Usage:
    python tools/mirror_fnos_docs.py             # re-fetch and rewrite the snapshot
    python tools/mirror_fnos_docs.py --verify    # re-fetch and report drift, write nothing

The snapshot itself stays untracked, like the rest of references/, and it is not
hashed into SOURCE_MANIFEST.sha256, whose scope is src/ and android-client/.
"""

import argparse
import html
import json
import os
import posixpath
import re
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SITE = "https://developer.fnnas.com"
SEEDS = (
    "/docs/guide/",
    "/docs/core-concepts/framework/",
    "/docs/core-concepts/manifest/",
    "/docs/cli/fnpack/",
    "/api/overview/",
    "/api/calling/",
    "/api/authorization/user-access/",
    "/api/page/routing/",
)
# Docusaurus category pages hold no prose of their own, only a link list whose
# children are reachable from every other page through the sidebar.
INDEX_ONLY = "/docs/category/"
CONTENT_PREFIXES = ("/docs/", "/api/")
USER_AGENT = "fnAudio-doc-mirror/1.0 (local reference snapshot)"
DOCS_DIR = "docs"
API_DIR = "api"
ASSET_DIR = "assets"
# The vendor publishes these two files itself: an index and the whole corpus in
# one text file.  They are the fastest cross-check that the page list is
# complete, so they are copied byte for byte rather than converted.
LLMS_FILES = ("llms.txt", "llms-full.txt")
SKIP_TAGS = frozenset(("script", "style", "svg", "path", "nav", "button", "noscript", "iframe"))
VOID_TAGS = frozenset((
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
))
# U+200B is Docusaurus' heading anchor marker; the NUL range is defensive
# against the same class of sentinel leaking in from another converter.
INVISIBLE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u2060\ufeff]")
LANGUAGE_IN_CLASS = re.compile(r"(?:^|\s)language-([A-Za-z0-9+#._-]+)(?:\s|$)")


def strip_invisible(text):
    """Remove the characters that a browser shows as nothing but a grep does."""
    return INVISIBLE.sub("", text)


class Node(object):
    """A tiny DOM node: enough structure to render Markdown, no more."""

    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.parent = parent

    # -- attribute helpers -------------------------------------------------
    def get(self, name, default=""):
        value = self.attrs.get(name)
        return default if value is None else value

    @property
    def classes(self):
        return frozenset(token.lower() for token in self.get("class").split())

    def has_class(self, *needles):
        return any(needle in self.classes for needle in needles)

    def class_startswith(self, prefix):
        prefix = prefix.lower()
        return any(name.startswith(prefix) for name in self.classes)

    # -- traversal ---------------------------------------------------------
    def walk(self):
        for child in self.children:
            yield child
            for deeper in child.walk():
                yield deeper

    def find_all(self, tag):
        return [node for node in self.walk() if node.tag == tag]

    def first_descendant(self, predicate):
        for node in self.walk():
            if predicate(node):
                return node
        return None

    @property
    def is_text(self):
        return self.tag == "#text"


class _TreeBuilder(HTMLParser):
    """Tolerant enough for Docusaurus output; unmatched end tags are ignored."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#document")
        self.stack = [self.root]

    def _attach(self, node):
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        node = Node(tag, attrs)
        self._attach(node)
        if tag not in VOID_TAGS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._attach(Node(tag.lower(), attrs))

    def handle_endtag(self, tag):
        tag = tag.lower()
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                return
        # Stray closing tag: the enclosing structure is already correct.

    def handle_data(self, data):
        if data:
            self._attach(Node("#text", {"data": data}))


def parse_html(markup):
    builder = _TreeBuilder()
    builder.feed(markup)
    builder.close()
    return builder.root


class PageContext(object):
    """Where the page being rendered came from, plus the assets it pulled in."""

    def __init__(self, path):
        self.path = path if path.endswith("/") else path + "/"
        self.assets = {}

    @property
    def output_dir(self):
        target = local_target(self.path)
        return target.rsplit("/", 1)[0]


def collapse(text):
    return re.sub(r"[ \t\r\n]+", " ", strip_invisible(text)).strip()


def plain_text(node):
    """Concatenate every text descendant without inserting spaces, like a lexer."""
    if node.tag == "#text":
        return strip_invisible(node.get("data"))
    if node.tag in SKIP_TAGS:
        return ""
    if node.tag == "br":
        return "\n"
    return "".join(plain_text(child) for child in node.children)


def language_of(node):
    for candidate in (node,) + tuple(node.walk()):
        match = LANGUAGE_IN_CLASS.search(candidate.get("class"))
        if match:
            return match.group(1).lower()
    return ""


def fence_for(code):
    longest = max([len(run) for run in re.findall(r"`+", code)] or [0])
    return "`" * max(3, longest + 1)


def code_text(pre):
    """Recover source lines from Prism markup, which puts one line per span."""
    token_lines = [node for node in pre.walk() if node.tag == "span" and node.has_class("token-line")]
    if token_lines:
        return "\n".join(plain_text(line).rstrip("\n") for line in token_lines)
    return plain_text(pre).strip("\n")


def rewrite_href(href, ctx):
    """Point links at the local Markdown files; leave third-party URLs alone."""
    href = (href or "").strip()
    if not href or href.startswith(("#", "mailto:", "javascript:", "data:")):
        return href
    parsed = urllib.parse.urlsplit(href)
    fragment = ("#" + parsed.fragment) if parsed.fragment else ""
    path = parsed.path
    if parsed.scheme in ("http", "https"):
        site_host = urllib.parse.urlsplit(SITE).netloc.lower()
        if parsed.netloc.lower() != site_host:
            return href
    if not path.startswith("/"):
        path = posixpath.normpath(posixpath.join(posixpath.dirname(ctx.path), path))
    if is_content_page(path):
        target = local_target(path)
        return posixpath.relpath(target, ctx.output_dir) + fragment
    if parsed.scheme not in ("http", "https"):
        # /llms.txt and friends: kept, but pointed back at the origin, because an
        # absolute path inside a local file would resolve to the drive root.
        return SITE + urllib.parse.quote(path) + fragment
    return href


def is_content_page(path):
    if not path.startswith(CONTENT_PREFIXES) or path.startswith(INDEX_ONLY):
        return False
    last = posixpath.basename(path.rstrip("/"))
    return bool(last) and "." not in last


def page_filename(path):
    return path.strip("/").replace("/", "__") + ".md"


def local_target(path):
    section = DOCS_DIR if path.startswith("/docs/") else API_DIR
    return "%s/%s" % (section, page_filename(path))


def image_reference(node, ctx):
    src = (node.get("src") or "").strip()
    if not src or src.startswith("data:"):
        return ""
    absolute = src if re.match(r"^[a-z]+://", src, re.I) else urllib.parse.urljoin(SITE + ctx.path, src)
    if not absolute.startswith(SITE + "/"):
        # Third-party hosts are mirrored too: the point of a snapshot is that it
        # still reads the same once the vendor takes the images down.
        pass
    name = posixpath.basename(urllib.parse.urlsplit(absolute).path)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name) or "image"
    ctx.assets[absolute] = name
    alt = collapse(node.get("alt"))
    return "![%s](%s)" % (alt, posixpath.relpath(ASSET_DIR + "/" + name, ctx.output_dir))


def render_inline(node, ctx, br=" "):
    tag = node.tag
    if tag == "#text":
        return strip_invisible(node.get("data"))
    if tag in SKIP_TAGS:
        return ""
    if tag == "br":
        return br
    if tag == "code":
        body = collapse(plain_text(node))
        return "`%s`" % body if body else ""
    if tag == "img":
        return image_reference(node, ctx)
    if tag == "a":
        if node.has_class("hash-link"):
            # Docusaurus appends a "#" permalink to every heading; it is not prose.
            return ""
        inner = collapse("".join(render_inline(child, ctx, br=" ") for child in node.children))
        href = rewrite_href(node.get("href"), ctx)
        label = inner or href
        if not label:
            return ""
        return "[%s](%s)" % (label, href) if href else label
    inner = "".join(render_inline(child, ctx, br) for child in node.children)
    if tag in ("strong", "b"):
        return "**%s**" % inner.strip() if inner.strip() else ""
    if tag in ("em", "i"):
        return "*%s*" % inner.strip() if inner.strip() else ""
    if tag in ("del", "s", "strike"):
        return "~~%s~~" % inner.strip() if inner.strip() else ""
    return inner


def _quote(block):
    return "\n".join(("> " + line).rstrip() for line in block.split("\n"))


def _indent(block, spaces):
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in block.split("\n"))


def render_table(node, ctx):
    grid = []
    for row in node.find_all("tr"):
        cells = [child for child in row.children if child.tag in ("td", "th")]
        if not cells:
            continue
        grid.append([_cell(child, ctx) for child in cells])
    if not grid:
        return []
    width = max(len(row) for row in grid)
    for row in grid:
        while len(row) < width:
            row.append("")
    lines = ["| " + " | ".join(grid[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in grid[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return ["\n".join(lines)]


def _cell(node, ctx):
    text = render_inline(node, ctx, br="<br>")
    text = re.sub(r"<br>\s*", "<br>", text)
    text = re.sub(r"\s*\n\s*", "<br>", text.strip())
    text = text.replace("\\|", "|").replace("|", "\\|")
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text


def render_list(node, ctx, depth=0):
    ordered = node.tag == "ol"
    lines = []
    index = 1
    for item in [child for child in node.children if child.tag == "li"]:
        marker = ("%d. " % index) if ordered else "- "
        index += 1
        pad = " " * len(marker)
        chunks = []
        children = []
        for child in item.children:
            if child.tag in ("ul", "ol"):
                chunks.append(_indent("\n".join(render_list(child, ctx, depth + 1)), len(marker)))
            else:
                children.append(child)
        # An <li> mixes inline runs (<code>, <a>, text) with block children
        # (<p>, <div>, another <pre>).  Runs join with nothing, blocks break.
        segments = []
        run = []
        for child in children:
            if child.tag in ("p", "div", "pre", "blockquote", "table"):
                if run:
                    segments.append("".join(run).strip())
                    run = []
                pieces = render_block(child, ctx) if child.tag != "p" else [render_inline(child, ctx, br="\n").strip()]
                segments.extend(piece for piece in pieces if piece.strip())
            else:
                run.append(render_inline(child, ctx, br="\n"))
        if run:
            segments.append("".join(run).strip())
        body = "\n".join(re.sub(r"\n{2,}", "\n", piece).strip() for piece in segments if piece.strip())
        if body:
            first, _, rest = body.partition("\n")
            lines.append(marker + first)
            for extra in ([rest] if rest else []):
                block_lines = [pad + line if line.strip() else "" for line in extra.split("\n")]
                lines.extend(block_lines)
        else:
            lines.append(marker.rstrip())
        lines.extend(chunks)
    return lines


def render_admonition(node, ctx):
    kind = "note"
    for name in sorted(node.classes):
        if name.startswith("theme-admonition-"):
            kind = name.split("-", 2)[-1]
    heading = node.first_descendant(lambda n: n.tag == "div" and n.class_startswith("admonitionheading"))
    label = collapse(plain_text(heading)) if heading is not None else ""
    content = node.first_descendant(lambda n: n.tag == "div" and n.class_startswith("admonitioncontent"))
    blocks = render_children(list(content.children) if content is not None else [], ctx)
    title = "> **[!%s]** %s" % (kind, label) if label else "> **[!%s]**" % kind
    out = [title]
    for block in blocks:
        out.append(">")
        out.append(_quote(block))
    return ["\n".join(out)]


def render_block(node, ctx):
    tag = node.tag
    if tag == "#text":
        text = collapse(node.get("data"))
        return [text] if text else []
    if tag in SKIP_TAGS:
        return []
    if tag in ("header", "main", "section", "figure"):
        return render_children(node.children, ctx)
    if tag == "div":
        classes = node.classes
        if any(name.startswith("tocollapsible") for name in classes):
            return []
        if any(name.startswith("theme-admonition") or name.startswith("alert--") for name in classes):
            if any(name.startswith("theme-admonition") for name in classes):
                return render_admonition(node, ctx)
            return []
        if node.first_descendant(lambda n: n.tag == "pre") is not None:
            return render_code_block(node, ctx)
        if any(name.startswith("codeblock") or name.startswith("language-") for name in classes):
            return render_code_block(node, ctx)
        if any(name.startswith("mdxcodeblock") for name in classes):
            return render_code_block(node, ctx)
        blocks = render_children(node.children, ctx)
        if blocks:
            return blocks
        inline = collapse(render_inline(node, ctx))
        return [inline] if inline else []
    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        title = collapse(render_inline(node, ctx))
        return ["%s %s" % ("#" * int(tag[1]), title)] if title else []
    if tag == "p":
        text = render_inline(node, ctx, br="\n").strip()
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return [text] if text.strip() else []
    if tag == "blockquote":
        inner = render_children(node.children, ctx)
        return [_quote("\n\n".join(inner))] if inner else []
    if tag in ("ul", "ol"):
        return ["\n".join(render_list(node, ctx))]
    if tag == "table":
        return render_table(node, ctx)
    if tag == "pre":
        return render_code_block(node, ctx)
    if tag == "hr":
        return ["---"]
    if tag == "img":
        ref = image_reference(node, ctx)
        return [ref] if ref else []
    if tag == "details":
        summary = node.first_descendant(lambda n: n.tag == "summary")
        out = []
        if summary is not None:
            label = collapse(render_inline(summary, ctx))
            if label:
                out.append("**%s**" % label)
        body = [child for child in node.children if child.tag != "summary"]
        out.extend(render_children(body, ctx))
        return out
    if tag == "br":
        return []
    inline = collapse(render_inline(node, ctx))
    return [inline] if inline else []


def render_code_block(node, ctx):
    pre = node if node.tag == "pre" else node.first_descendant(lambda n: n.tag == "pre")
    if pre is None:
        return []
    code = code_text(pre)
    if not code.strip():
        return []
    language = language_of(node) or language_of(pre)
    title = node.first_descendant(lambda n: n.tag == "div" and n.class_startswith("codeblocktitle"))
    label = collapse(plain_text(title)) if title is not None else ""
    fence = fence_for(code)
    block = "%s%s\n%s\n%s" % (fence, language, code, fence)
    return (["`%s`" % label, block] if label else [block])


def render_children(nodes, ctx):
    out = []
    for child in list(nodes):
        out.extend(render_block(child, ctx))
    return out


def article_html(page_html):
    match = re.search(r"<article\b.*?</article>", page_html, re.S)
    if not match:
        raise ValueError("page has no <article> element")
    return match.group(0)


def html_to_markdown(markup, page_path="/docs/"):
    """Convert one Docusaurus <article> (or a bare fragment) into Markdown."""
    ctx = PageContext(page_path)
    root = parse_html(markup)
    article = root.first_descendant(lambda n: n.tag == "article")
    scope = article if article is not None else root
    body = scope.first_descendant(lambda n: n.tag == "div" and n.has_class("theme-doc-markdown"))
    if body is None:
        body = scope
    blocks = render_children(body.children, ctx)
    deduped = []
    for block in blocks:
        block = block.rstrip()
        if not block:
            continue
        if block == "本页总览":
            # The mobile table-of-contents control, not documentation.
            continue
        deduped.append(block)
    return "\n\n".join(deduped).strip() + "\n", ctx


def fetch(url, timeout=30):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_text(url, cache=None):
    if cache is not None and url in cache:
        return cache[url]
    body = fetch(url).decode("utf-8", "replace")
    if cache is not None:
        cache[url] = body
    return body


def discover_pages(fetch_html=fetch_text, cache=None):
    """Breadth-first walk of the sidebar links, restricted to the two documents."""
    seen = set()
    pending = list(SEEDS)
    pages = []
    while pending:
        path = pending.pop(0)
        if path in seen:
            continue
        seen.add(path)
        try:
            markup = fetch_html(SITE + path, cache)
        except Exception as error:  # network failure must not invent a page
            sys.stderr.write("fetch failed %s: %s\n" % (path, error))
            continue
        for href in re.findall(r'href="(/[^"#?]+)"', markup):
            if not href.startswith(CONTENT_PREFIXES):
                continue
            if href.startswith(INDEX_ONLY):
                continue
            if not href.endswith("/"):
                href = href + "/" if "." not in posixpath.basename(href) else href
            if href not in seen:
                pending.append(href)
        if path.startswith(INDEX_ONLY):
            continue
        if is_content_page(path):
            pages.append(path)
    return sorted(set(pages))


def title_of(markdown_body):
    """Take the page heading out of the converted Markdown, not the raw HTML.

    Reading <h1> from the source markup was wrong in both directions: the real
    page title never survived as a raw <h1>, while the HTML listing inside a
    sample page's code fence did, so a code snippet masqueraded as the title of
    that page and every other page came out untitled.
    """
    match = re.search("^# +(.+?)[ \t]*$", markdown_body, re.M)
    return collapse(match.group(1)) if match else ""


def front_matter(url, fetched, heading):
    lines = ["---", "source: %s" % url, "fetched: %s" % fetched]
    if heading:
        lines.append('title: "%s"' % heading.replace('"', "'"))
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def section_of(path):
    return DOCS_DIR if path.startswith("/docs/") else API_DIR


def render_readme(entries, fetched, asset_names):
    header = [
        "# fnOS 应用开放平台文档快照",
        "",
        "来源：%s （开发文档 /docs 与开放 API /api 全站抓取）" % SITE,
        "抓取日期：%s" % fetched,
        "",
        "用途：fnAudio 打包、manifest 字段、生命周期脚本、privilege/resource 配置、",
        "CGI 入口与开放 API 接入的权威依据，避免依赖记忆或过期快照。",
        "",
        "> 注意：这是外部文档的只读快照，不参与 fpk 打包，也不进入 SOURCE_MANIFEST.sha256。",
        "> 需要更新时运行 `python tools/mirror_fnos_docs.py` 重新抓取，不要手工改写正文；",
        "> 抓取后用 `python tools/mirror_fnos_docs.py --verify` 复核本地与站点是否一致。",
        "",
    ]
    blocks = []
    for heading, section in (("\u5f00\u53d1\u6587\u6863 (/docs)", DOCS_DIR), ("\u5f00\u653e API (/api)", API_DIR)):
        rows = ["", "## %s" % heading, "", "| 文档 | 文件 | 来源 |", "| --- | --- | --- |"]
        chosen = [entry for entry in entries if entry["section"] == section]
        for entry in sorted(chosen, key=lambda item: item["path"]):
            rows.append("| %s | [%s](%s/%s) | %s |" % (entry["title"] or "-", entry["file"], section, entry["file"], entry["url"]))
        blocks.append("\n".join(rows))
    assets = ["", "## 截图", "", "`%s/` 共 %d 张，站点原文以图片承载的界面示例。" % (ASSET_DIR, len(asset_names)), ""]
    return "\n".join(header + blocks + assets)


def build_pages(pages, fetch_html=fetch_text, fetched="1970-01-01", cache=None):
    """Fetch and convert every page; returns markdown bodies plus asset URLs seen."""
    entries = []
    asset_urls = {}
    for path in pages:
        url = SITE + path
        try:
            markup = fetch_html(url, cache)
        except Exception as error:
            sys.stderr.write("fetch failed %s: %s\n" % (url, error))
            continue
        body, ctx = html_to_markdown(article_html(markup), path)
        filename = page_filename(path)
        entries.append({
            "path": path,
            "url": url,
            "section": section_of(path),
            "file": filename,
            "title": title_of(body),
            "markdown": front_matter(url, fetched, title_of(body)) + body,
        })
        for source, name in ctx.assets.items():
            asset_urls[source] = name
    return entries, asset_urls


def write_snapshot(out_root, entries, asset_urls, fetched, downloader=None):
    """Write the markdown tree and mirror the images it references."""
    downloader = downloader or (lambda url: fetch(url, timeout=60))
    written = []
    for entry in entries:
        target = os.path.join(out_root, entry["section"], entry["file"])
        ensure_dir(os.path.dirname(target))
        write_text(target, entry["markdown"])
        written.append(target)
    asset_dir = os.path.join(out_root, ASSET_DIR)
    ensure_dir(asset_dir)
    for source, name in sorted(asset_urls.items()):
        target = os.path.join(asset_dir, name)
        if os.path.exists(target):
            continue
        try:
            payload = downloader(source)
        except Exception as error:
            sys.stderr.write("asset failed %s: %s\n" % (source, error))
            continue
        with open(target, "wb") as handle:
            handle.write(payload)
        written.append(target)
    for name in LLMS_FILES:
        target = os.path.join(out_root, name)
        try:
            payload = downloader(SITE + "/" + name)
        except Exception as error:
            sys.stderr.write("export failed %s: %s\n" % (name, error))
            continue
        with open(target, "wb") as handle:
            handle.write(payload)
        written.append(target)
    readme = os.path.join(out_root, "README.md")
    write_text(readme, render_readme(entries, fetched, sorted(asset_urls.values())))
    written.append(readme)
    report = os.path.join(out_root, "MIRROR_REPORT.json")
    write_text(report, json.dumps({
        "site": SITE,
        "fetched": fetched,
        "pages": [{"path": e["path"], "file": "%s/%s" % (e["section"], e["file"]), "title": e["title"]} for e in entries],
        "assets": sorted(asset_urls.values()),
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    written.append(report)
    return written


def ensure_dir(path):
    if path and not os.path.isdir(path):
        os.makedirs(path)


def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def local_pages(out_root):
    found = {}
    for section in (DOCS_DIR, API_DIR):
        directory = os.path.join(out_root, section)
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(directory, name)
            head = read_text(path)[:400]
            match = re.search(r"^source:\s*(\S+)", head, re.M)
            found[(match.group(1) if match else name)] = path
    return found


FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def strip_front_matter(text):
    return FRONT_MATTER.sub("", text, count=1)


def count_code_blocks(body):
    """Count fenced blocks, not fence lines: an opener and a closer look alike."""
    inside = False
    blocks = 0
    tagged = 0
    for match in FENCE.finditer(body):
        if inside:
            inside = False
            continue
        blocks += 1
        if match.group(1):
            tagged += 1
        inside = True
    return blocks, tagged


INTERNAL_LINK = re.compile(r"\]\(([^)\s]+\.md)(#[^)\s]*)?\)")
IMAGE_LINK = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```([A-Za-z0-9+#._-]*)[^\S\n]*$", re.M)
SEPARATOR_ROW = re.compile(r"^\|([ \t]*:?-{3,}:?[ \t]*\|)+[ \t]*$", re.M)


def inspect_snapshot(out_root):
    """Read-only structural report on a snapshot, so a stale or corrupt dump shows up."""
    report = {
        "root": out_root,
        "pages": 0,
        "fences": 0,
        "fences_with_language": 0,
        "tables": 0,
        "images": 0,
        "assets": 0,
        "invisible_characters": 0,
        "problems": [],
    }
    pages = local_pages(out_root)
    report["pages"] = len(pages)
    if not pages:
        report["problems"].append("no mirrored pages found under %s" % out_root)
        return report
    for url, path in sorted(pages.items()):
        name = os.path.relpath(path, out_root).replace("\\", "/")
        body = read_text(path)
        if not url.startswith(SITE):
            report["problems"].append("%s: missing or malformed source front matter" % name)
        report["invisible_characters"] += len(INVISIBLE.findall(body))
        blocks, tagged = count_code_blocks(body)
        report["fences"] += blocks
        report["fences_with_language"] += tagged
        report["tables"] += len(SEPARATOR_ROW.findall(body))
        code_body = strip_front_matter(body)
        for match in INTERNAL_LINK.finditer(code_body):
            target = match.group(1)
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target.replace("/", os.sep)))
            if not os.path.isfile(resolved):
                report["problems"].append("%s: link target does not exist: %s" % (name, target))
        for match in IMAGE_LINK.finditer(code_body):
            target = match.group(1)
            report["images"] += 1
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target.replace("/", os.sep)))
            if not os.path.isfile(resolved):
                report["problems"].append("%s: image target does not exist: %s" % (name, target))
    for name in LLMS_FILES:
        target = os.path.join(out_root, name)
        if not os.path.isfile(target) or os.path.getsize(target) == 0:
            report["problems"].append("vendor export missing or empty: %s" % name)
    asset_dir = os.path.join(out_root, ASSET_DIR)
    if os.path.isdir(asset_dir):
        report["assets"] = len([n for n in os.listdir(asset_dir) if not n.startswith(".")])
    if report["fences"] and report["fences_with_language"] != report["fences"]:
        report["problems"].append("some code fences lost their language tag")
    if report["pages"] and report["images"] == 0:
        report["problems"].append("no screenshots referenced, which means the image tags were dropped")
    return report


def verify_snapshot(out_root, fetch_html=fetch_text, cache=None):
    """Compare the local snapshot with a fresh conversion of the live pages."""
    pages = discover_pages(fetch_html, cache)
    entries, _assets = build_pages(pages, fetch_html, _snapshot_date(out_root), cache)
    problems = []
    local = local_pages(out_root)
    for entry in entries:
        target = os.path.join(out_root, entry["section"], entry["file"])
        if not os.path.isfile(target):
            problems.append("missing locally: %s" % entry["path"])
            continue
        stored = strip_front_matter(read_text(target))
        fresh = strip_front_matter(entry["markdown"])
        if stored.strip() != fresh.strip():
            problems.append("body differs from the site: %s" % entry["path"])
    for url in sorted(local):
        if url.startswith(SITE) and url[len(SITE):] not in pages:
            problems.append("local page has no counterpart on the site: %s" % url)
    return problems


def _snapshot_date(out_root):
    readme = os.path.join(out_root, "README.md")
    if os.path.isfile(readme):
        match = re.search(r"抓取日期：\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", read_text(readme))
        if match:
            return match.group(1)
    for url, path in sorted(local_pages(out_root).items()):
        match = re.search(r"^fetched:\s*(\S+)", read_text(path)[:400], re.M)
        if match:
            return match.group(1)
    return "1970-01-01"


def default_out_root():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "references", "fnos-developer-docs")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mirror the fnOS developer and open API documentation.")
    parser.add_argument("--out", default=None, help="snapshot directory (default: references/fnos-developer-docs)")
    parser.add_argument("--date", default=None, help="value written into the fetched: front matter")
    parser.add_argument("--verify", action="store_true", help="re-fetch and report drift without writing")
    parser.add_argument("--report", action="store_true", help="inspect the local snapshot only; no network")
    arguments = parser.parse_args(argv)
    out_root = arguments.out or default_out_root()

    if arguments.report:
        report = inspect_snapshot(out_root)
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        for problem in report["problems"]:
            sys.stderr.write("PROBLEM %s\n" % problem)
        return 1 if report["problems"] else 0

    import datetime

    fetched = arguments.date or datetime.date.today().isoformat()
    cache = {}
    if arguments.verify:
        problems = verify_snapshot(out_root, fetch_text, cache)
        for problem in problems:
            sys.stderr.write("DRIFT %s\n" % problem)
        print("pages=%d drift=%d" % (len(local_pages(out_root)), len(problems)))
        return 1 if problems else 0

    pages = discover_pages(fetch_text, cache)
    entries, assets = build_pages(pages, fetch_text, fetched, cache)
    written = write_snapshot(out_root, entries, assets, fetched)
    report = inspect_snapshot(out_root)
    print(json.dumps({"pages": report["pages"], "assets": report["assets"],
                      "fences": report["fences"], "fences_with_language": report["fences_with_language"],
                      "tables": report["tables"], "images": report["images"],
                      "invisible_characters": report["invisible_characters"],
                      "written": len(written), "problems": report["problems"]}, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["problems"] else 0


if __name__ == "__main__":
    sys.exit(main())
