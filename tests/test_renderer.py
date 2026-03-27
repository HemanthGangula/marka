"""Unit tests for marka.renderer — MarkdownRenderer and sanitize_html.

These tests import only marka.renderer (and its pip dependencies:
markdown, pygments).  No GTK/GLib imports are needed, so the tests run
in any plain Python environment that has the pip requirements installed.

Run with:
    python3 -m unittest tests.test_renderer -v
"""

import sys
import os
import unittest

# Allow running from the repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marka.renderer import MarkdownRenderer, sanitize_html


class TestMarkdownRendererConvert(unittest.TestCase):
    """Tests for MarkdownRenderer.convert() — Markdown-to-HTML conversion."""

    def setUp(self):
        self.renderer = MarkdownRenderer()

    def _convert(self, md_text):
        """Convenience wrapper."""
        return self.renderer.convert(md_text)

    # ── Basic block elements ─────────────────────────────────────────────

    def test_heading_h1(self):
        html = self._convert("# Hello World")
        self.assertIn("<h1", html)
        self.assertIn("Hello World", html)

    def test_heading_h2(self):
        html = self._convert("## Section")
        self.assertIn("<h2", html)

    def test_heading_h3(self):
        html = self._convert("### Subsection")
        self.assertIn("<h3", html)

    def test_paragraph(self):
        html = self._convert("Simple paragraph text.")
        self.assertIn("<p>", html)
        self.assertIn("Simple paragraph text.", html)

    # ── Inline emphasis ──────────────────────────────────────────────────

    def test_bold_strong(self):
        html = self._convert("**bold text**")
        self.assertIn("<strong>", html)
        self.assertIn("bold text", html)

    def test_italic_em(self):
        html = self._convert("*italic text*")
        self.assertIn("<em>", html)

    def test_inline_code(self):
        html = self._convert("`inline code`")
        self.assertIn("<code>", html)
        self.assertIn("inline code", html)

    # ── Strikethrough (custom extension) ────────────────────────────────

    def test_strikethrough(self):
        html = self._convert("~~struck through~~")
        self.assertIn("<del>", html)
        self.assertIn("struck through", html)

    # ── Task list checkboxes (custom extension) ──────────────────────────

    def test_task_list_checked(self):
        html = self._convert("- [x] Done item")
        self.assertIn('type="checkbox"', html)
        self.assertIn('checked', html)

    def test_task_list_unchecked(self):
        html = self._convert("- [ ] Pending item")
        self.assertIn('type="checkbox"', html)

    def test_task_list_disabled(self):
        """Task list checkboxes must be disabled (read-only in preview)."""
        html = self._convert("- [x] Item")
        self.assertIn('disabled', html)

    # ── Fenced code blocks with syntax highlighting ──────────────────────

    def test_fenced_code_block_plain(self):
        md = "```\nsome code\n```"
        html = self._convert(md)
        self.assertIn("<code>", html)
        self.assertIn("some code", html)

    def test_fenced_code_block_with_language(self):
        md = "```python\nprint('hello')\n```"
        html = self._convert(md)
        # codehilite extension wraps highlighted code in a div with this class
        self.assertIn("codehilite", html)

    def test_fenced_code_block_css_class(self):
        """The codehilite CSS class must appear for language-tagged blocks."""
        md = "```javascript\nconsole.log('hi');\n```"
        html = self._convert(md)
        self.assertIn("codehilite", html)

    # ── Tables ───────────────────────────────────────────────────────────

    def test_table_basic(self):
        md = (
            "| Col A | Col B |\n"
            "|-------|-------|\n"
            "| val 1 | val 2 |\n"
        )
        html = self._convert(md)
        self.assertIn("<table>", html)
        self.assertIn("<th", html)
        self.assertIn("<td", html)
        self.assertIn("Col A", html)
        self.assertIn("val 1", html)

    # ── Links ────────────────────────────────────────────────────────────

    def test_link(self):
        html = self._convert("[Example](https://example.com)")
        self.assertIn('<a ', html)
        self.assertIn("https://example.com", html)
        self.assertIn("Example", html)

    # ── Images ───────────────────────────────────────────────────────────

    def test_image(self):
        html = self._convert("![Alt text](https://example.com/img.png)")
        self.assertIn("<img", html)

    # ── Blockquote ───────────────────────────────────────────────────────

    def test_blockquote(self):
        html = self._convert("> quoted text")
        self.assertIn("<blockquote>", html)

    # ── Horizontal rule ──────────────────────────────────────────────────

    def test_hr(self):
        html = self._convert("---")
        self.assertIn("<hr", html)

    # ── Reset between calls ──────────────────────────────────────────────

    def test_convert_is_idempotent(self):
        """Calling convert() twice with the same input must return the same output."""
        md = "# Title\n\nSome text."
        result1 = self._convert(md)
        result2 = self._convert(md)
        self.assertEqual(result1, result2)

    def test_empty_string(self):
        html = self._convert("")
        # Empty input should produce empty or whitespace-only output
        self.assertEqual(html.strip(), "")


class TestSanitizeHtml(unittest.TestCase):
    """Tests for the sanitize_html() function — whitelist-based HTML sanitizer."""

    # ── Dangerous tags stripped ──────────────────────────────────────────

    def test_script_tag_stripped(self):
        result = sanitize_html("<script>alert(1)</script>")
        self.assertNotIn("<script", result)
        self.assertNotIn("alert(1)", result)

    def test_script_content_not_leaked(self):
        """Script tag content must be entirely consumed, not leaked as text."""
        result = sanitize_html("<script>stealData()</script>")
        self.assertNotIn("stealData", result)

    def test_style_tag_stripped(self):
        result = sanitize_html("<style>body { display:none }</style>")
        self.assertNotIn("<style", result)
        self.assertNotIn("display:none", result)

    def test_iframe_stripped(self):
        result = sanitize_html('<iframe src="https://evil.com"></iframe>')
        self.assertNotIn("<iframe", result)

    def test_iframe_content_stripped(self):
        result = sanitize_html("<iframe><b>text inside</b></iframe>")
        self.assertNotIn("text inside", result)

    def test_form_stripped(self):
        result = sanitize_html("<form action='/steal'><input type='text'></form>")
        self.assertNotIn("<form", result)

    # ── Event handler attributes stripped ────────────────────────────────

    def test_onclick_stripped(self):
        result = sanitize_html('<p onclick="evil()">text</p>')
        self.assertNotIn("onclick", result)
        # But the p tag and text content must survive
        self.assertIn("<p>", result)
        self.assertIn("text", result)

    def test_onload_stripped(self):
        result = sanitize_html('<img src="x.png" onload="steal()">')
        self.assertNotIn("onload", result)

    def test_onerror_stripped(self):
        result = sanitize_html('<img src="x.png" onerror="steal()">')
        self.assertNotIn("onerror", result)

    # ── Style attribute stripped ──────────────────────────────────────────

    def test_style_attr_stripped(self):
        result = sanitize_html('<p style="color:red">text</p>')
        self.assertNotIn('style=', result)
        self.assertIn("<p>", result)
        self.assertIn("text", result)

    # ── Dangerous href schemes blocked ───────────────────────────────────

    def test_javascript_href_blocked(self):
        result = sanitize_html('<a href="javascript:void(0)">click</a>')
        self.assertNotIn("javascript:", result)

    def test_vbscript_href_blocked(self):
        result = sanitize_html('<a href="vbscript:msgbox(1)">click</a>')
        self.assertNotIn("vbscript:", result)

    def test_https_href_preserved(self):
        result = sanitize_html('<a href="https://example.com">link</a>')
        self.assertIn('href="https://example.com"', result)
        self.assertIn("link", result)

    def test_relative_href_preserved(self):
        result = sanitize_html('<a href="#section">jump</a>')
        self.assertIn('href="#section"', result)

    # ── img src handling ──────────────────────────────────────────────────

    def test_data_image_src_preserved(self):
        result = sanitize_html('<img src="data:image/png;base64,abc123" alt="pic">')
        self.assertIn("data:image/png;base64,abc123", result)

    def test_data_text_html_src_blocked(self):
        """data:text/html is not a safe image source and must be blocked."""
        result = sanitize_html('<img src="data:text/html,<script>x</script>" alt="x">')
        self.assertNotIn("data:text/html", result)

    def test_javascript_src_blocked(self):
        result = sanitize_html('<img src="javascript:alert(1)" alt="x">')
        self.assertNotIn("javascript:", result)

    def test_https_img_src_preserved(self):
        result = sanitize_html('<img src="https://example.com/img.png" alt="x">')
        self.assertIn("https://example.com/img.png", result)

    # ── Input element handling ────────────────────────────────────────────

    def test_checkbox_input_preserved(self):
        result = sanitize_html('<input type="checkbox" disabled checked>')
        self.assertIn('<input', result)
        self.assertIn('type="checkbox"', result)

    def test_checkbox_disabled_attr(self):
        result = sanitize_html('<input type="checkbox" disabled>')
        self.assertIn('disabled', result)

    def test_text_input_stripped(self):
        """Non-checkbox input types must be stripped entirely."""
        result = sanitize_html('<input type="text" value="secret">')
        # type=text input should be dropped
        self.assertNotIn('type="text"', result)
        self.assertNotIn('value=', result)

    def test_hidden_input_stripped(self):
        result = sanitize_html('<input type="hidden" name="csrf" value="token">')
        self.assertNotIn('type="hidden"', result)
        self.assertNotIn('csrf', result)

    # ── Nested / complex cases ────────────────────────────────────────────

    def test_nested_script_content_not_leaked(self):
        """Content inside a nested script inside a div must not leak."""
        result = sanitize_html("<div><script><b>injected</b></script></div>")
        self.assertNotIn("injected", result)
        self.assertNotIn("<script", result)

    def test_script_with_allowed_sibling(self):
        """Allowed siblings of a script tag must survive."""
        result = sanitize_html("<div><script>bad()</script><p>good</p></div>")
        self.assertNotIn("bad()", result)
        self.assertIn("good", result)

    # ── Preserved classes (codehilite / task-list) ────────────────────────

    def test_codehilite_class_preserved(self):
        result = sanitize_html('<div class="codehilite"><pre>code</pre></div>')
        self.assertIn('class="codehilite"', result)

    def test_task_list_class_preserved(self):
        result = sanitize_html('<ul class="task-list"><li class="task-list-item">item</li></ul>')
        self.assertIn('class="task-list"', result)
        self.assertIn('class="task-list-item"', result)

    # ── Allowed tags preserved ────────────────────────────────────────────

    def test_paragraph_preserved(self):
        result = sanitize_html("<p>Hello world</p>")
        self.assertIn("<p>", result)
        self.assertIn("Hello world", result)
        self.assertIn("</p>", result)

    def test_strong_preserved(self):
        result = sanitize_html("<strong>bold</strong>")
        self.assertIn("<strong>", result)

    def test_em_preserved(self):
        result = sanitize_html("<em>italic</em>")
        self.assertIn("<em>", result)

    def test_del_preserved(self):
        result = sanitize_html("<del>struck</del>")
        self.assertIn("<del>", result)

    def test_code_preserved(self):
        result = sanitize_html("<code>snippet</code>")
        self.assertIn("<code>", result)

    def test_table_preserved(self):
        html = "<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>D</td></tr></tbody></table>"
        result = sanitize_html(html)
        self.assertIn("<table>", result)
        self.assertIn("<th>", result)
        self.assertIn("<td>", result)

    # ── Unknown / unrecognised tags ───────────────────────────────────────

    def test_unknown_tag_dropped_content_kept(self):
        """Unknown tags should be dropped but their text content preserved."""
        result = sanitize_html("<unknown>visible text</unknown>")
        self.assertNotIn("<unknown>", result)
        self.assertIn("visible text", result)

    # ── Empty / trivial inputs ────────────────────────────────────────────

    def test_empty_string(self):
        result = sanitize_html("")
        self.assertEqual(result, "")

    def test_plain_text_escaped(self):
        """Raw text with HTML special chars must be escaped."""
        result = sanitize_html("5 < 10 & 3 > 1")
        self.assertIn("&lt;", result)
        self.assertIn("&gt;", result)
        self.assertIn("&amp;", result)


if __name__ == "__main__":
    unittest.main()
