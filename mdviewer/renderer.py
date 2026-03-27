"""Markdown-to-HTML conversion engine.

Uses python-markdown with built-in extensions plus two small custom
extensions for strikethrough (~~text~~) and task-list checkboxes
(- [x] / - [ ]).  No additional pip packages required.
"""

import re
import xml.etree.ElementTree as etree
from html.parser import HTMLParser
from io import StringIO

import markdown
from markdown.inlinepatterns import InlineProcessor
from markdown.treeprocessors import Treeprocessor
from markdown.extensions import Extension
from pygments.formatters import HtmlFormatter


# ── Custom extension: ~~strikethrough~~ → <del> ─────────────────────────────

_STRIKE_RE = r"(~~)(.+?)~~"


class _StrikethroughInline(InlineProcessor):
    """Convert ~~text~~ to <del>text</del>."""

    def handleMatch(self, m, data):
        el = etree.Element("del")
        el.text = m.group(2)
        return el, m.start(0), m.end(0)


class StrikethroughExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            _StrikethroughInline(_STRIKE_RE, md), "strikethrough", 175
        )


# ── Custom extension: task-list checkboxes ───────────────────────────────────

_TASK_CHECKED = re.compile(r"^\[x\]\s*", re.IGNORECASE)
_TASK_UNCHECKED = re.compile(r"^\[ \]\s*")


class _TaskListProcessor(Treeprocessor):
    """Convert list items starting with [x] or [ ] into checkboxes."""

    def run(self, root):
        for ul in root.iter("ul"):
            has_task = False
            for li in ul:
                if li.tag != "li":
                    continue
                text = (li.text or "").lstrip()
                checked_m = _TASK_CHECKED.match(text)
                unchecked_m = _TASK_UNCHECKED.match(text)
                if checked_m or unchecked_m:
                    has_task = True
                    checkbox = etree.SubElement(li, "input")
                    checkbox.set("type", "checkbox")
                    checkbox.set("disabled", "disabled")
                    if checked_m:
                        checkbox.set("checked", "checked")
                        li.text = text[checked_m.end():]
                    else:
                        li.text = text[unchecked_m.end():]
                    # Move checkbox before the remaining text
                    checkbox.tail = li.text
                    li.text = ""
                    li.insert(0, checkbox)
                    li.set("class", "task-list-item")
            if has_task:
                ul.set("class", "task-list")


class TaskListExtension(Extension):
    def extendMarkdown(self, md):
        md.treeprocessors.register(
            _TaskListProcessor(md), "task_list", 100
        )


# ── HTML Sanitizer ────────────────────────────────────────────────────────────

# Tags whose entire subtree (tag + contents) should be removed.
_STRIP_TAGS = frozenset({
    "script", "style", "iframe", "object", "embed", "applet",
    "form", "button", "select", "textarea", "meta", "link",
    "base", "noscript", "template", "svg", "math",
})

# Tags that markdown legitimately produces and are safe to keep.
_ALLOWED_TAGS = frozenset({
    "p", "div",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li",
    "blockquote", "pre", "hr", "br",
    "table", "thead", "tbody", "tr", "th", "td",
    "dl", "dt", "dd",
    "details", "summary",
    "a", "em", "strong", "del", "ins", "mark", "kbd", "abbr", "span",
    "code", "b", "i", "s", "u", "q", "sup", "sub", "small",
    "img", "input",
})

# Self-closing tags that should not have a closing tag emitted.
_VOID_TAGS = frozenset({"br", "hr", "img", "input"})

# Allowed attributes per tag (lowercase tag name → set of allowed attr names).
_ALLOWED_ATTRS = {
    "a":       frozenset({"href", "title", "class", "id", "name"}),
    "img":     frozenset({"src", "alt", "title", "width", "height", "class"}),
    "input":   frozenset({"type", "disabled", "checked", "class"}),
    "abbr":    frozenset({"title"}),
    "th":      frozenset({"align", "colspan", "rowspan", "scope"}),
    "td":      frozenset({"align", "colspan", "rowspan", "scope"}),
    "ol":      frozenset({"start", "type"}),
    "code":    frozenset({"class", "id"}),
    "span":    frozenset({"class", "id"}),
    "li":      frozenset({"class", "id"}),
    "ul":      frozenset({"class", "id"}),
    "div":     frozenset({"class", "id"}),
    "p":       frozenset({"class", "id"}),
    "pre":     frozenset({"class", "id"}),
    "table":   frozenset({"class", "id"}),
    "h1":      frozenset({"id"}),
    "h2":      frozenset({"id"}),
    "h3":      frozenset({"id"}),
    "h4":      frozenset({"id"}),
    "h5":      frozenset({"id"}),
    "h6":      frozenset({"id"}),
    "details": frozenset({"open"}),
}
_DEFAULT_ALLOWED_ATTRS = frozenset({"class", "id"})

# Schemes blocked in href (a) and src (img) attributes.
_BLOCKED_URL_SCHEMES = re.compile(
    r"^\s*(javascript|vbscript|data)\s*:", re.IGNORECASE
)
# Allowed schemes for <a href>.
# Note: "//" (protocol-relative) is intentionally excluded — it would be
# resolved relative to the WebKit base URI (file://) and could reach
# arbitrary hosts.  Use explicit https:// instead.
_HREF_ALLOWED = re.compile(
    r"^\s*(https?://|#|/(?!/)|\.\.?/)", re.IGNORECASE
)
# data: URIs allowed for <img src> — only image subtypes.
_DATA_IMAGE = re.compile(r"^\s*data:image/", re.IGNORECASE)


def _is_safe_href(url):
    """Return True if url is safe for use in <a href>."""
    if _BLOCKED_URL_SCHEMES.match(url):
        return False
    # Block file: scheme in hrefs
    if re.match(r"^\s*file:", url, re.IGNORECASE):
        return False
    return True


def _is_safe_img_src(url):
    """Return True if url is safe for use in <img src>."""
    # Allow data:image/ URIs
    if _DATA_IMAGE.match(url):
        return True
    # Allow http/https/file and relative paths
    if re.match(r"^\s*(https?://|file://|/|\.\.?/)", url, re.IGNORECASE):
        return True
    # Block javascript:, vbscript:, data: (non-image)
    if _BLOCKED_URL_SCHEMES.match(url):
        return False
    # Allow plain relative paths (no scheme)
    if not re.match(r"^\s*[a-zA-Z][a-zA-Z0-9+\-.]*:", url):
        return True
    return False


def _sanitize_attrs(tag, attrs):
    """Filter and sanitize the attribute list for a given tag.

    Returns a list of (name, value) pairs that are safe to emit.
    """
    allowed = _ALLOWED_ATTRS.get(tag, _DEFAULT_ALLOWED_ATTRS)
    result = []
    for name, value in attrs:
        name_lower = name.lower()
        # Strip all event handlers (on*)
        if name_lower.startswith("on"):
            continue
        # Strip style attributes universally
        if name_lower == "style":
            continue
        if name_lower not in allowed:
            continue
        # Special URL sanitization
        if tag == "a" and name_lower == "href":
            if value is None or not _is_safe_href(value):
                continue
        if tag == "img" and name_lower == "src":
            if value is None or not _is_safe_img_src(value):
                continue
        # For <input>, only allow if type==checkbox
        if tag == "input" and name_lower == "type":
            if (value or "").lower() != "checkbox":
                # Drop the entire input element's non-checkbox types
                # by returning empty — handled at tag level below
                return None  # signal: skip this input element
        result.append((name_lower, value))
    return result


class _HtmlSanitizer(HTMLParser):
    """Whitelist-based HTML sanitizer using Python's built-in html.parser.

    Strips dangerous tags and attributes from markdown-generated HTML.
    Operates as a streaming parser, emitting safe HTML to an internal buffer.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._out = StringIO()
        # Stack of tags currently being stripped (tag + all its descendants)
        self._strip_depth = 0
        # Track whether current <input> should be skipped
        self._skip_input = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        # If we are inside a stripped subtree, ignore everything
        if self._strip_depth > 0:
            if tag not in _VOID_TAGS:
                self._strip_depth += 1
            return

        # Tags that should be stripped entirely (including their contents)
        if tag in _STRIP_TAGS:
            if tag not in _VOID_TAGS:
                self._strip_depth += 1
            return

        # Unknown tags: drop but do NOT strip contents
        if tag not in _ALLOWED_TAGS:
            return

        # Sanitize attributes
        if tag == "input":
            # Check if type is checkbox; _sanitize_attrs returns None if not
            safe_attrs = _sanitize_attrs(tag, attrs)
            if safe_attrs is None:
                # Non-checkbox input — skip the tag entirely (it's void)
                return
        else:
            safe_attrs = _sanitize_attrs(tag, attrs)
            if safe_attrs is None:
                return

        # Emit the sanitized tag
        attr_str = ""
        for name, value in safe_attrs:
            if value is None:
                attr_str += f" {name}"
            else:
                escaped = value.replace("&", "&amp;").replace('"', "&quot;")
                attr_str += f' {name}="{escaped}"'

        if tag in _VOID_TAGS:
            self._out.write(f"<{tag}{attr_str}>")
        else:
            self._out.write(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag):
        tag = tag.lower()

        if self._strip_depth > 0:
            if tag not in _VOID_TAGS:
                # Guard: never let _strip_depth drop below 1 on a close tag
                # that was NOT a _STRIP_TAG opener.  Mismatched close tags for
                # *allowed* tags (e.g. "</div>" inside "<script>…</script>")
                # would otherwise prematurely reset _strip_depth to 0 and allow
                # content that follows inside the stripped subtree to leak.
                if tag in _STRIP_TAGS:
                    self._strip_depth -= 1
                elif self._strip_depth > 1:
                    # Non-strip tag closed inside stripped subtree; was opened
                    # while inside (handle_starttag incremented depth for it).
                    self._strip_depth -= 1
                # else: spurious close tag for an allowed tag whose open was
                # OUTSIDE the stripped region — do NOT decrement.
            return

        # Void tags never have end tags
        if tag in _VOID_TAGS:
            return

        if tag in _STRIP_TAGS:
            return

        if tag not in _ALLOWED_TAGS:
            return

        self._out.write(f"</{tag}>")

    def handle_data(self, data):
        if self._strip_depth > 0:
            return
        # Escape any raw text that could be misinterpreted
        self._out.write(
            data.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
        )

    def handle_entityref(self, name):
        if self._strip_depth > 0:
            return
        self._out.write(f"&{name};")

    def handle_charref(self, name):
        if self._strip_depth > 0:
            return
        self._out.write(f"&#{name};")

    def get_output(self):
        return self._out.getvalue()


def sanitize_html(html: str) -> str:
    """Sanitize markdown-generated HTML using a whitelist-based HTMLParser.

    Removes dangerous tags (script, iframe, style, etc.) and attributes
    (event handlers, style, unsafe URLs) while preserving all content that
    python-markdown legitimately produces.
    """
    parser = _HtmlSanitizer()
    parser.feed(html)
    parser.close()
    return parser.get_output()


# ── Renderer ─────────────────────────────────────────────────────────────────

class MarkdownRenderer:
    """Converts Markdown text to HTML with syntax highlighting."""

    def __init__(self):
        self._md = markdown.Markdown(
            extensions=[
                "extra",              # tables, fenced code, footnotes, abbr, attr_list, def_list
                "codehilite",         # pygments syntax highlighting
                "toc",                # table of contents anchors
                "nl2br",              # newline → <br>
                "sane_lists",         # better list handling
                "smarty",             # typographic quotes, dashes, ellipses
                StrikethroughExtension(),
                TaskListExtension(),
            ],
            extension_configs={
                "codehilite": {
                    "guess_lang": False,
                    "css_class": "codehilite",
                    "linenums": False,
                },
                "toc": {
                    "permalink": False,
                },
            },
        )

    def convert(self, text):
        """Convert markdown text to sanitized HTML body content."""
        self._md.reset()
        raw_html = self._md.convert(text)
        return sanitize_html(raw_html)

    def get_pygments_css(self, dark=False):
        """Return pygments CSS for the chosen theme."""
        style = "monokai" if dark else "friendly"
        return HtmlFormatter(style=style).get_style_defs(".codehilite")
