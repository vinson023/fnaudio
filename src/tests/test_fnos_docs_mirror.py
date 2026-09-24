"""Structure guards for the local mirror of the fnOS developer documentation.

Two vendor documents decide how this application has to be packaged, which
privileges and resources it may declare, how its lifecycle scripts run and how
it calls the open API: the development guide under ``/docs`` and the open API
reference under ``/api``.  ``tools/mirror_fnos_docs.py`` keeps a readable copy
of both under ``references/fnos-developer-docs`` so those answers stay on disk
instead of in recollection.

The first copy was a hand-rolled text dump and it was quietly unusable: NUL
characters inside prose, not one code fence keeping its language, every HTML
table flattened into lines no Markdown renderer recognises, all screenshots
dropped, and the mobile table-of-contents button pasted into every page.  Each
of those failures gets a fixture below, because the mirror has to be re-run
whenever the vendor updates the site.
"""

import importlib.util
from pathlib import Path
import sys
import unittest


_MODULE_PATH = Path(__file__).resolve().parents[2] / "tools" / "mirror_fnos_docs.py"
_SPEC = importlib.util.spec_from_file_location("fnaudio_mirror_fnos_docs", _MODULE_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_ROOT = REPO_ROOT / "references" / "fnos-developer-docs"

# Written via chr() so this file holds no backtick-free ambiguity and, more
# importantly, so a fixture can tell an opening fence from prose.
FENCE = chr(96) * 3
TICK = chr(96)

TOC_LABEL = "本页总览"

REAL_PROSE = chr(0x771f) + chr(0x671b) + chr(0x6b63) + chr(0x6587)
ADMONITION_LABEL = "注意"

# The characters that made the previous snapshot unusable are exactly the ones
# an editor will not show.  Tab, line feed and carriage return stay legal:
# fenced source code legitimately contains tabs.
FORBIDDEN = set(range(0x00, 0x09)) | {0x0B, 0x0C} | set(range(0x0E, 0x20))
FORBIDDEN |= {0x7F, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF}


def forbidden_in(text):
    """Every forbidden code point present in ``text``, as numbers."""
    return sorted({ord(char) for char in text if ord(char) in FORBIDDEN})


def article(inner):
    """Wrap a fragment the way a Docusaurus page does.

    The real page puts a breadcrumb bar and a mobile table-of-contents control
    inside ``<article>`` before the document body, so the fixtures carry them
    too: whatever survives conversion has to have earned it.
    """
    return (
        "<article>"
        '<nav class="breadcrumbs theme-doc-breadcrumbs">'
        '<li class="breadcrumb__item">开放 API</li></nav>'
        '<div class="tocCollapsible_LhbJ theme-doc-toc-mobile tocMobile_RrSb">'
        '<button type="button" class="clean-btn tocCollapsibleButton_yYYT">'
        + TOC_LABEL
        + "</button></div>"
        '<div class="theme-doc-markdown markdown">'
        "<header><h1>调用方式</h1></header>"
        + inner
        + "</div></article>"
    )


PAGE_TITLE = "# " + chr(0x8c03) + chr(0x7528) + chr(0x65b9) + chr(0x5f0f)


def convert(inner):
    """Convert a fragment, minus the page title the wrapper itself carries.

    ``article()`` opens with a real ``<h1>`` because that is how the vendor
    starts a document, but a fixture still has to be compared against only the
    markup it supplied.  The title is pinned by HeadingTests instead.
    """
    markdown = _MODULE.html_to_markdown(article(inner))[0]
    lines = markdown.splitlines()
    assert lines and lines[0] == PAGE_TITLE, markdown
    return chr(10).join(lines[1:]) + chr(10)


class TableTests(unittest.TestCase):
    TABLE = (
        "<table><thead><tr><th>能力</th><th>需要声明的 Scope</th><th>说明</th></tr></thead>"
        "<tbody>"
        "<tr><td>应用共享授权管理</td><td><code>trim.file.sharedAccess</code></td>"
        "<td>让管理员为应用授权目录</td></tr>"
        "<tr><td>路径转换</td><td><code>trim.file.path</code></td>"
        "<td>把 /vol1/... 换成 | 展示给用户的路径</td></tr>"
        "</tbody></table>"
    )

    def setUp(self):
        self.markdown = convert(self.TABLE)
        self.lines = self.markdown.strip().splitlines()

    def test_a_flattened_table_is_not_a_table(self):
        """The old dump produced indented "| x" lines with no separator row."""
        self.assertEqual(len(_MODULE.SEPARATOR_ROW.findall(self.markdown)), 1)
        self.assertNotIn("<td", self.markdown)
        self.assertEqual(len(self.lines), 4, self.markdown)

    def test_header_cells_and_inline_code_survive(self):
        self.assertEqual(self.lines[0], "| 能力 | 需要声明的 Scope | 说明 |")
        self.assertIn("| " + TICK + "trim.file.sharedAccess" + TICK + " |", self.lines[2])

    def test_a_pipe_inside_a_cell_stays_escaped(self):
        self.assertIn("| 把 /vol1/... 换成 \\| 展示给用户的路径 |", self.lines[3])

    def test_no_dollar_sign_inline_code(self):
        """The previous converter wrapped code spans in $...$ instead of ticks."""
        self.assertNotIn("$trim", self.markdown)


class CodeBlockTests(unittest.TestCase):
    PRISM = (
        '<div class="language-json codeBlockContainer_dTth theme-code-block">'
        '<div class="codeBlockTitle_ZC3U">config/resource</div>'
        '<div class="codeBlockContent_A5Hs">'
        '<pre tabindex="0" class="prism-code language-json codeBlock_Q7DD thin-scrollbar">'
        '<code class="codeBlockLines_Lu7K">'
        '<span class="token-line" style="color:#393A34">'
        '<span class="token punctuation">{</span><br></span>'
        '<span class="token-line" style="color:#393A34"><span class="token plain">  </span>'
        '<span class="token property" style="color:#36acaa">&quot;name&quot;</span>'
        '<span class="token operator">:</span>'
        '<span class="token plain"> </span>'
        '<span class="token string" style="color:#e36209">"fnaudio"</span><br></span>'
        '<span class="token-line" style="color:#393A34">'
        '<span class="token punctuation">}</span><br></span>'
        "</code></pre></div></div>"
    )

    def test_fenced_source_keeps_its_language_and_file_name(self):
        """The caption sits on its own line, then the fence, as on the site."""
        markdown = convert(self.PRISM)
        self.assertEqual(
            markdown.strip().splitlines(),
            [
                "`config/resource`",
                "",
                FENCE + "json",
                "{",
                '  "name": "fnaudio"',
                "}",
                FENCE,
            ],
        )

    def test_the_prism_markup_itself_never_leaks(self):
        markdown = convert(self.PRISM)
        for fragment in ("prism-code", "token-line", "&quot;", "<br>"):
            self.assertNotIn(fragment, markdown)

    def test_a_second_language_is_tagged_too(self):
        markdown = convert(
            '<div class="language-bash"><pre class="prism-code language-bash">'
            "<code>fnpack build --name demo</code></pre></div>"
        )
        self.assertEqual(markdown.strip().splitlines(), [FENCE + "bash",
                                                        "fnpack build --name demo", FENCE])


class HeadingTests(unittest.TestCase):
    def test_the_anchor_link_at_the_end_of_a_heading_is_dropped(self):
        markdown = convert(
            '<h2 class="anchor anchorTargetStickyNavbar_ya9B" id="api-scope-定义">'
            "API Scope 定义"
            '<a href="#api-scope-定义" class="hash-link" aria-label="直接链接" '
            'title="直接链接" translate="no">' + chr(0x200B) + "</a></h2>"
            "<p>声明段。</p>"
        )
        self.assertEqual(markdown.strip().splitlines()[0], "## API Scope 定义")
        self.assertNotIn("](#", markdown)

    def test_the_page_heading_is_the_document_title(self):
        markdown = _MODULE.html_to_markdown(article("<p>正文</p>"))[0]
        self.assertEqual(markdown.splitlines()[0], PAGE_TITLE)

    def test_the_breadcrumb_bar_does_not_become_prose(self):
        markdown = convert("<p>正文</p>")
        self.assertNotIn("开放 API", markdown)


class ListTests(unittest.TestCase):
    def test_an_item_that_mixes_code_and_prose_stays_one_item(self):
        markdown = convert(
            "<ul>"
            "<li>前端 JS SDK：在 <code>window.fnos</code> 上打开授权页面、"
            "文件管理器，也可以读取 <code>platformConfig</code> 配置</li>"
            "<li>后端 API：需要 <code>Authorization</code> 头</li>"
            "</ul>"
        )
        self.assertEqual(
            markdown.strip().splitlines(),
            [
                "- 前端 JS SDK：在 " + TICK + "window.fnos" + TICK
                + " 上打开授权页面、文件管理器，也可以读取 "
                + TICK + "platformConfig" + TICK + " 配置",
                "- 后端 API：需要 " + TICK + "Authorization" + TICK + " 头",
            ],
        )

    def test_nested_lists_and_ordered_lists_keep_their_shape(self):
        markdown = convert(
            "<ol><li>第一步<ul><li>细节一</li><li>细节二</li></ul></li>"
            "<li>第二步</li></ol>"
        )
        self.assertEqual(
            markdown.strip().splitlines(),
            ["1. 第一步", "   - 细节一",
             "   - 细节二", "2. 第二步"],
        )


class AdmonitionTests(unittest.TestCase):
    WARNING = (
        '<div class="theme-admonition theme-admonition-warning alert alert--warning '
        'admonition_vtDI"><div class="admonitionHeading_pWpR">'
        '<span class="admonitionIcon_Kuo2"><svg viewBox="0 0 12 16">'
        '<path fill-rule="evenodd" d="M4 9h1v1H4z"/></svg></span>'
        + ADMONITION_LABEL
        + "</div>"
        '<div class="admonitionContent_IXtt"><p>只声明确实会用到的 Scope。</p>'
        "<p>必须在 " + TICK + "manifest" + TICK + " 中声明：</p>"
        '<div class="language-ini codeBlockContainer_x"><pre class="prism-code '
        'language-ini"><code class="codeBlockLines_y"><span class="token-line">'
        "micro_app=true<br></span></code></pre></div></div></div>"
    )

    def test_an_admonition_becomes_a_callout_that_keeps_its_content(self):
        markdown = convert(self.WARNING)
        lines = markdown.strip().splitlines()
        self.assertEqual(lines[0], "> **[!warning]** " + ADMONITION_LABEL)
        self.assertIn("只声明确实会用到的 Scope。", markdown)
        self.assertIn(TICK + "manifest" + TICK, markdown)
        self.assertIn("> " + FENCE + "ini", markdown)
        self.assertIn("> micro_app=true", markdown)

    def test_the_icon_svg_never_survives(self):
        markdown = convert(self.WARNING)
        for fragment in ("<svg", "viewBox", "fill-rule", "admonitionContent"):
            self.assertNotIn(fragment, markdown)


class InvisibleCharacterTests(unittest.TestCase):
    def test_control_and_zero_width_characters_are_stripped(self):
        markdown = convert(
            "<p>可" + chr(0x00) + "删除" + chr(0x00) + "配置</p>"
            "<p>阅读 " + chr(0x00) + chr(0x00) + "平台配置" + chr(0x00) + "章节</p>"
            "<p>零宽" + chr(0x200B) + "与 BOM" + chr(0xFEFF) + "结尾" + chr(0x2060) + "</p>"
        )
        self.assertEqual(forbidden_in(markdown), [], markdown.encode("unicode_escape"))
        self.assertIn("可删除配置", markdown)
        self.assertIn("阅读 平台配置章节", markdown)

    def test_the_mobile_table_of_contents_control_never_survives(self):
        markdown = convert("<p>正文</p>")
        self.assertNotIn(TOC_LABEL, markdown)
        self.assertNotIn(TOC_LABEL, _MODULE.render_readme([], "2026-01-01", []))


class ClassTokenTests(unittest.TestCase):
    """``has_class`` matches whole class names, never a substring of one.

    Every Docusaurus marker is looked up by class, so a matcher that degrades
    into a substring test would select the wrong element on the real page: a
    decorative wrapper whose name merely contains the document-body marker would
    become the document body, and the prose would be dropped without any error.
    """

    def test_a_class_that_merely_contains_the_marker_is_not_the_document_body(self):
        markup = (
            "<article>"
            '<div class="theme-doc-markdown-backup"><p>SENTINEL</p></div>'
            '<div class="theme-doc-markdown markdown"><p>' + REAL_PROSE + "</p></div>"
            "</article>"
        )
        markdown = _MODULE.html_to_markdown(markup)[0]
        self.assertIn(REAL_PROSE, markdown)
        self.assertNotIn("SENTINEL", markdown)

    def test_a_prefix_lookup_ignores_the_case_of_its_own_argument(self):
        # The vendor spells these classes in camelCase, so a caller is allowed to
        # repeat that spelling; matching has to work either way.
        root = _MODULE.parse_html('<div class="codeBlockTitle_aB"><p>x</p></div>')
        node = root.first_descendant(lambda n: n.tag == "div")
        self.assertTrue(node.class_startswith("codeBlockTitle"))
        self.assertTrue(node.class_startswith("CODEBLOCKTITLE"))
        self.assertTrue(node.class_startswith("codeblocktitle"))
        self.assertFalse(node.class_startswith("codeBlockContent"))


class PathRewriteTests(unittest.TestCase):
    def test_links_between_sections_point_at_local_markdown_files(self):
        from_docs = _MODULE.PageContext("/docs/core-concepts/environment-variables/")
        self.assertEqual(
            _MODULE.rewrite_href("/api/calling/", from_docs), "../api/api__calling.md"
        )
        self.assertEqual(
            _MODULE.rewrite_href("/api/calling/#scope", from_docs),
            "../api/api__calling.md#scope",
        )
        inside = _MODULE.PageContext("/docs/core-concepts/manifest/")
        self.assertEqual(
            _MODULE.rewrite_href("/docs/core-concepts/resource/", inside),
            "docs__core-concepts__resource.md",
        )

    def test_third_party_and_fragment_links_are_left_alone(self):
        inside = _MODULE.PageContext("/api/calling/")
        self.assertEqual(
            _MODULE.rewrite_href("https://www.npmjs.com/package/@trimjs/web-app", inside),
            "https://www.npmjs.com/package/@trimjs/web-app",
        )
        self.assertEqual(_MODULE.rewrite_href("#appendix", inside), "#appendix")
        self.assertEqual(_MODULE.rewrite_href("", inside), "")

    def test_site_paths_that_are_not_pages_point_back_at_the_origin(self):
        """An absolute path inside a local file would resolve to the drive root."""
        inside = _MODULE.PageContext("/docs/guide/")
        self.assertEqual(
            _MODULE.rewrite_href("/llms.txt", inside),
            _MODULE.SITE + "/llms.txt",
        )
        self.assertEqual(
            _MODULE.rewrite_href("/docs/category/核心概念/", inside),
            _MODULE.SITE + "/docs/category/" + "%E6%A0%B8%E5%BF%83%E6%A6%82%E5%BF%B5" + "/",
        )

    def test_category_indexes_are_not_content_pages(self):
        for path in ("/docs/category/其他/", "/img/logo.png", "", "/docs/guide/index.html"):
            self.assertFalse(_MODULE.is_content_page(path), path)
        for path in ("/docs/guide/", "/api/calling/", "/docs/core-concepts/manifest/"):
            self.assertTrue(_MODULE.is_content_page(path), path)

    def test_each_page_path_maps_to_exactly_one_local_file(self):
        self.assertEqual(_MODULE.page_filename("/api/calling/"), "api__calling.md")
        self.assertEqual(
            _MODULE.local_target("/docs/core-concepts/manifest/"),
            "docs/docs__core-concepts__manifest.md",
        )
        self.assertEqual(_MODULE.local_target("/api/page/ui/"), "api/api__page__ui.md")


class CountingTests(unittest.TestCase):
    def fenced(self, language, lines):
        return "\n".join([FENCE + language] + lines + [FENCE])

    def test_blocks_are_counted_not_fence_lines(self):
        body = "\n".join(
            [
                self.fenced("json", ["{", "}"]),
                "prose",
                self.fenced("bash", ["fnpack build"]),
                self.fenced("ini", ["micro_app=true"]),
            ]
        )
        self.assertEqual(_MODULE.count_code_blocks(body), (3, 3))
        self.assertEqual(_MODULE.count_code_blocks(self.fenced("", ["a", "b"])), (1, 0))
        self.assertEqual(_MODULE.count_code_blocks("no code here"), (0, 0))

    def test_the_separator_pattern_tolerates_padding_and_alignment(self):
        for row in (
            "| --- |",
            "| --- | --- |",
            "|:---|---:|",
            "| :--- | :---: | ---: |  ",
        ):
            self.assertIsNotNone(_MODULE.SEPARATOR_ROW.search(row), row)
        for text in ("---", "| --- ", "| a | --- |", "some | --- | text"):
            self.assertIsNone(_MODULE.SEPARATOR_ROW.search(text), text)

    def test_a_page_title_comes_from_the_heading_not_a_code_sample(self):
        body = "# Docker 应用案例\n\n" + self.fenced("html", ["<h1>Hello Docker</h1>"])
        self.assertEqual(_MODULE.title_of(body), "Docker 应用案例")
        self.assertEqual(_MODULE.title_of("no heading at all"), "")


@unittest.skipUnless(SNAPSHOT_ROOT.is_dir(), "the reference snapshot is not on disk")
class SnapshotTests(unittest.TestCase):
    """The on-disk mirror is the artifact a developer actually reads."""

    @classmethod
    def setUpClass(cls):
        cls.report = _MODULE.inspect_snapshot(str(SNAPSHOT_ROOT))

    def test_the_structural_report_is_clean(self):
        self.assertEqual(self.report["problems"], [], self.report["problems"])
        self.assertEqual(self.report["invisible_characters"], 0)
        self.assertGreaterEqual(self.report["pages"], 34)

    def test_every_code_fence_still_carries_its_language(self):
        self.assertGreater(self.report["fences"], 150)
        self.assertEqual(self.report["fences"], self.report["fences_with_language"])

    def test_tables_and_screenshots_are_still_there(self):
        self.assertGreaterEqual(self.report["tables"], 40)
        self.assertGreaterEqual(self.report["images"], 10)
        self.assertGreaterEqual(self.report["assets"], 10)

    def test_no_page_reveals_a_control_character_or_the_toc_widget(self):
        for path in (SNAPSHOT_ROOT / _MODULE.DOCS_DIR).glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(forbidden_in(text), [], path.name)
            self.assertNotIn(TOC_LABEL, text, path.name)

    def test_mirrored_images_are_real_image_files(self):
        signatures = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF8", b"RIFF")
        names = sorted((SNAPSHOT_ROOT / _MODULE.ASSET_DIR).glob("*"))
        self.assertTrue(names, "the snapshot lost its screenshots")
        for path in names:
            with path.open("rb") as handle:
                head = handle.read(12)
            self.assertTrue(head.startswith(signatures), path.name)
            self.assertGreater(path.stat().st_size, 1024, path.name)

    def test_the_vendor_machine_readable_index_matches_the_local_pages(self):
        """llms.txt is the vendor's own list of pages: it proves coverage."""
        listing = (SNAPSHOT_ROOT / "llms.txt").read_text(encoding="utf-8-sig")
        listed = set()
        for line in listing.splitlines():
            for piece in line.split("(")[1:]:
                url = piece.split(")")[0].strip()
                if url.startswith(_MODULE.SITE):
                    listed.add(url[len(_MODULE.SITE):])
        self.assertGreaterEqual(len(listed), 34)
        for path in sorted(listed):
            normalised = path if path.endswith("/") else path + "/"
            self.assertTrue(_MODULE.is_content_page(normalised), path)
            target = SNAPSHOT_ROOT / _MODULE.local_target(normalised)
            self.assertTrue(target.is_file(), str(target))
        self.assertEqual(len(listed), self.report["pages"])

    def test_the_vendor_full_export_is_mirrored_verbatim(self):
        full = SNAPSHOT_ROOT / "llms-full.txt"
        self.assertGreater(full.stat().st_size, 100_000)
        self.assertIn("trim.file.userAccess", full.read_text(encoding="utf-8-sig"))

    def test_the_index_lists_every_page_by_title(self):
        readme = (SNAPSHOT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("| - |", readme, "some page lost its title")
        for section in (_MODULE.DOCS_DIR, _MODULE.API_DIR):
            for path in (SNAPSHOT_ROOT / section).glob("*.md"):
                self.assertIn("](" + section + "/" + path.name + ")", readme, path.name)


if __name__ == "__main__":
    unittest.main()
