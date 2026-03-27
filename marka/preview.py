"""Markdown HTML preview pane backed by a WebKit.WebView.

Provides zoom, find-in-document, and print capabilities in addition to
live HTML rendering.
"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit


# ── CSS: GitHub-inspired design tokens ────────────────────────────────────────

_CSS_LIGHT = """
:root {
    --bg: #ffffff;
    --text: #24292f;
    --code-bg: #f6f8fa;
    --code-border: #d0d7de;
    --border: #d0d7de;
    --blockquote-border: #d0d7de;
    --blockquote-text: #57606a;
    --link: #0969da;
    --th-bg: #f6f8fa;
    --hr: #d0d7de;
    --ins-bg: #dafbe1;
    --del-bg: #ffebe9;
    --mark-bg: #fff8c5;
    --kbd-bg: #f6f8fa;
    --kbd-border: #d0d7de;
    --zoom: 1;
}
"""

_CSS_DARK = """
:root {
    --bg: #0d1117;
    --text: #e6edf3;
    --code-bg: #161b22;
    --code-border: #30363d;
    --border: #30363d;
    --blockquote-border: #3d444d;
    --blockquote-text: #9198a1;
    --link: #4493f8;
    --th-bg: #161b22;
    --hr: #21262d;
    --ins-bg: #1a4a27;
    --del-bg: #4a1a1a;
    --mark-bg: #4a3c00;
    --kbd-bg: #161b22;
    --kbd-border: #30363d;
    --zoom: 1;
}
"""

_CSS_BASE = """
* { box-sizing: border-box; }

html { font-size: calc(1rem * var(--zoom)); }

body {
    font-family: -apple-system, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
    font-size: 1rem;
    line-height: 1.6;
    color: var(--text);
    background: var(--bg);
    max-width: 860px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
}

h1, h2, h3, h4, h5, h6 {
    font-weight: 600;
    line-height: 1.25;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}
h1 { font-size: 2em;      border-bottom: 1px solid var(--hr); padding-bottom: 0.3em; }
h2 { font-size: 1.5em;   border-bottom: 1px solid var(--hr); padding-bottom: 0.3em; }
h3 { font-size: 1.25em; }
h4 { font-size: 1em; }
h5 { font-size: 0.875em; }
h6 { font-size: 0.85em;  color: var(--blockquote-text); }

p { margin-top: 0; margin-bottom: 1em; }

a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }

img { max-width: 100%; height: auto; }

/* ── Inline code ── */
code {
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", "Menlo", monospace;
    font-size: 0.875em;
    background: var(--code-bg);
    border: 1px solid var(--code-border);
    border-radius: 6px;
    padding: 0.2em 0.4em;
}

/* ── Code blocks ── */
pre {
    background: var(--code-bg);
    border: 1px solid var(--code-border);
    border-radius: 6px;
    padding: 1em 1.2em;
    overflow-x: auto;
    line-height: 1.45;
}
pre code {
    background: transparent;
    border: none;
    padding: 0;
    font-size: 0.875em;
}

/* ── Blockquote ── */
blockquote {
    border-left: 4px solid var(--blockquote-border);
    color: var(--blockquote-text);
    margin: 0 0 1em;
    padding: 0 1em;
}

/* ── Tables ── */
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 1em;
    overflow: auto;
}
th, td {
    border: 1px solid var(--border);
    padding: 6px 13px;
}
th {
    font-weight: 600;
    background: var(--th-bg);
}
tr:nth-child(even) { background: var(--code-bg); }

/* ── Horizontal rule ── */
hr {
    height: 1px;
    background: var(--hr);
    border: none;
    margin: 1.5em 0;
}

/* ── Lists ── */
ul, ol {
    padding-left: 2em;
    margin-bottom: 1em;
}
li { margin-bottom: 0.25em; }

/* ── Task lists (python-markdown extra) ── */
ul.task-list { list-style: none; padding-left: 0; }
li.task-list-item { padding-left: 1.6em; position: relative; }
li.task-list-item input[type=checkbox] {
    position: absolute;
    left: 0;
    top: 0.25em;
    accent-color: var(--link);
}

/* ── Definition lists (python-markdown extra) ── */
dl { margin-bottom: 1em; }
dt {
    font-weight: 600;
    margin-top: 0.75em;
}
dd {
    margin-left: 2em;
    margin-bottom: 0.25em;
    color: var(--blockquote-text);
}

/* ── Strikethrough ── */
del {
    background: var(--del-bg);
    text-decoration: line-through;
    border-radius: 3px;
    padding: 0 0.2em;
}

/* ── Inserted text ── */
ins {
    background: var(--ins-bg);
    text-decoration: none;
    border-radius: 3px;
    padding: 0 0.2em;
}

/* ── Highlighted text ── */
mark {
    background: var(--mark-bg);
    border-radius: 3px;
    padding: 0 0.2em;
}

/* ── Keyboard input ── */
kbd {
    font-family: "JetBrains Mono", "Fira Code", monospace;
    font-size: 0.85em;
    background: var(--kbd-bg);
    border: 1px solid var(--kbd-border);
    border-bottom-width: 3px;
    border-radius: 5px;
    padding: 0.15em 0.45em;
    white-space: nowrap;
}

/* ── Abbreviations ── */
abbr[title] {
    cursor: help;
    text-decoration: underline dotted;
}

/* ── Footnotes (python-markdown extra) ── */
.footnote {
    font-size: 0.85em;
    color: var(--blockquote-text);
    border-top: 1px solid var(--hr);
    margin-top: 2em;
    padding-top: 0.5em;
}
.footnote ol { padding-left: 1em; }
.footnote-backref { text-decoration: none; margin-left: 0.3em; }

/* ── Pygments syntax highlighting wrapper ── */
.codehilite { margin-bottom: 1em; }
.codehilite pre { margin: 0; }
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src file: data: http: https:; font-src 'none';">
<style>
{theme_vars}
{base_css}
{pygments_css}
</style>
</head>
<body>
{body}
</body>
</html>"""

# Zoom step in CSS rem units applied via --zoom custom property
_ZOOM_STEP = 0.1
_ZOOM_MIN = 0.5
_ZOOM_MAX = 3.0
_ZOOM_DEFAULT = 1.0


class PreviewPane(Gtk.Box):
    """Markdown HTML preview pane using WebKit.WebView.

    Supports live content updates, light/dark themes, find-in-document,
    zoom, and printing.
    """

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._is_dark = False
        self._current_html_body = ""
        self._pygments_css = ""
        self._base_uri = None
        self._zoom_level = _ZOOM_DEFAULT

        self._setup_webview()

    def _setup_webview(self):
        """Create and configure the WebKit.WebView with security hardening."""
        settings = WebKit.Settings()
        settings.set_enable_javascript(False)
        # Security: disallow file:// pages from reading arbitrary local paths.
        # Trade-off: local <img src="./image.png"> references will render as
        # broken images because WebKit cannot fetch same-directory file://
        # resources when this flag is False.  Relative image paths embedded in
        # markdown are therefore not displayed, which is the accepted
        # security/usability balance for this application.
        settings.set_allow_file_access_from_file_urls(False)
        settings.set_allow_universal_access_from_file_urls(False)
        settings.set_default_charset("utf-8")
        settings.set_enable_page_cache(False)

        self._webview = WebKit.WebView(settings=settings)
        self._webview.set_hexpand(True)
        self._webview.set_vexpand(True)

        # Find controller for Ctrl+F support
        self._find_controller = self._webview.get_find_controller()

        # Show a blank welcome page on startup
        self._webview.load_html(self._build_full_html(""), None)
        self.append(self._webview)

    def _zoom_css_override(self):
        """Return a tiny CSS snippet that overrides --zoom for the current level."""
        return f":root {{ --zoom: {self._zoom_level:.2f}; }}"

    def _build_full_html(self, body):
        """Assemble a complete HTML document from theme, base CSS, and body."""
        theme_vars = _CSS_DARK if self._is_dark else _CSS_LIGHT
        pygments = self._pygments_css or ""
        zoom_override = self._zoom_css_override()
        return _HTML_TEMPLATE.format(
            theme_vars=theme_vars + "\n" + zoom_override,
            base_css=_CSS_BASE,
            pygments_css=pygments,
            body=body,
        )

    # ── Public API ────────────────────────────────────────────────────────

    def update_content(self, html_body, base_uri=None):
        """Update the preview with new rendered HTML.

        Skips a WebView reload when both the body and base URI are unchanged
        to avoid unnecessary reflows on every debounce tick.
        """
        new_base = base_uri if base_uri else self._base_uri
        if html_body == self._current_html_body and new_base == self._base_uri:
            return
        self._current_html_body = html_body
        if base_uri:
            self._base_uri = base_uri
        full_html = self._build_full_html(html_body)
        self._webview.load_html(full_html, self._base_uri)

    def set_theme(self, is_dark, pygments_css=""):
        """Switch between light and dark themes and re-render current content."""
        self._is_dark = is_dark
        if pygments_css:
            self._pygments_css = pygments_css
        full_html = self._build_full_html(self._current_html_body)
        self._webview.load_html(full_html, self._base_uri)

    def set_pygments_css(self, css):
        """Set the Pygments syntax highlighting CSS string."""
        self._pygments_css = css

    def adjust_zoom(self, direction):
        """Change the preview zoom level.

        direction: +1 to zoom in, -1 to zoom out, 0 to reset to 100%.
        """
        if direction == 0:
            self._zoom_level = _ZOOM_DEFAULT
        elif direction > 0:
            self._zoom_level = min(_ZOOM_MAX, round(self._zoom_level + _ZOOM_STEP, 2))
        else:
            self._zoom_level = max(_ZOOM_MIN, round(self._zoom_level - _ZOOM_STEP, 2))
        # Re-render with new zoom
        full_html = self._build_full_html(self._current_html_body)
        self._webview.load_html(full_html, self._base_uri)

    def find_text(self, query):
        """Start or update a find-in-document search.

        Passing an empty string clears all highlights.
        """
        if not query:
            self._find_controller.search_finish()
            return
        options = (
            WebKit.FindOptions.CASE_INSENSITIVE
            | WebKit.FindOptions.WRAP_AROUND
        )
        self._find_controller.search(query, options, 200)

    def find_next(self):
        """Advance to the next search result."""
        self._find_controller.search_next()

    def find_previous(self):
        """Advance to the previous search result."""
        self._find_controller.search_previous()

    def print_document(self, parent_window=None):
        """Open the system print dialog for the current preview content."""
        print_op = WebKit.PrintOperation.new(self._webview)
        print_op.run_dialog(parent_window)
