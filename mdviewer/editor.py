"""Markdown editor pane.

Uses GtkSourceView 5 when available, falling back to a plain Gtk.TextView
with manual regex-based syntax highlighting.
"""

import re
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib, GObject, Pango

# Try GtkSourceView 5 — optional dependency
try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource
    HAS_SOURCE_VIEW = True
except (ValueError, ImportError):
    HAS_SOURCE_VIEW = False

# Placeholder shown when the editor buffer is empty (no file open)
_EMPTY_PLACEHOLDER = (
    "Open a Markdown file (Ctrl+O) or start typing\u2026\n\n"
    "Tip: drag and drop a .md file onto this window to open it."
)


class EditorPane(Gtk.ScrolledWindow):
    """Markdown editor pane using GtkSourceView (with plain TextView fallback).

    Emits:
        content-changed: Debounced signal fired 300 ms after the last keystroke.
        cursor-moved(line, col): Fired on every cursor position change.
    """

    __gsignals__ = {
        "content-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "cursor-moved": (GObject.SignalFlags.RUN_LAST, None, (int, int)),
    }

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._preview_timer = None
        self._highlight_timer = None
        self._is_dark = False
        # Set to True while set_text() is running so _on_changed is a no-op
        self._loading = False

        if HAS_SOURCE_VIEW:
            self._setup_source_view()
        else:
            self._setup_text_view()

        self._setup_placeholder()

    # ── Setup ─────────────────────────────────────────────────────────────

    def _setup_source_view(self):
        """Configure a GtkSource.View with Markdown language and Adwaita scheme."""
        self._buffer = GtkSource.Buffer()
        self._view = GtkSource.View.new_with_buffer(self._buffer)

        lang_mgr = GtkSource.LanguageManager.get_default()
        lang = lang_mgr.get_language("markdown")
        if lang:
            self._buffer.set_language(lang)
        self._buffer.set_highlight_syntax(True)

        # StyleSchemeManager is a singleton — get_default() never duplicates it
        self._scheme_mgr = GtkSource.StyleSchemeManager.get_default()
        self._apply_source_scheme(False)

        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.set_show_line_numbers(True)
        self._view.set_auto_indent(True)
        self._view.set_tab_width(4)
        self._view.set_monospace(True)
        self._view.set_left_margin(8)
        self._view.set_right_margin(8)
        self._view.set_top_margin(8)
        self._view.set_bottom_margin(8)
        self._view.add_css_class("editor-view")

        # Do NOT call self.set_child(self._view) here.
        # _setup_placeholder() wraps the view in a Gtk.Overlay and then
        # calls self.set_child(overlay).  Setting the view's parent twice
        # (once here and once inside the overlay) triggers the
        # gtk_overlay_set_child assertion and breaks the editor widget.
        self._buffer.connect("changed", self._on_changed)
        self._buffer.connect("notify::cursor-position", self._on_cursor_notify)

    def _setup_text_view(self):
        """Configure a plain Gtk.TextView as a fallback when GtkSourceView is absent."""
        self._buffer = Gtk.TextBuffer()
        self._view = Gtk.TextView.new_with_buffer(self._buffer)
        self._view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._view.set_monospace(True)
        self._view.set_left_margin(8)
        self._view.set_right_margin(8)
        self._view.set_top_margin(8)
        self._view.set_bottom_margin(8)
        self._view.add_css_class("editor-view")

        self._setup_manual_tags()
        # Do NOT call self.set_child(self._view) here — see note in _setup_source_view.
        self._buffer.connect("changed", self._on_changed)
        self._buffer.connect("notify::cursor-position", self._on_cursor_notify)

    def _setup_placeholder(self):
        """Overlay a placeholder label visible only when the buffer is empty."""
        # Gtk.TextView exposes set_placeholder_text only via C; we use an
        # overlay-label approach that works with both GtkSourceView and plain
        # TextView without requiring GtkSourceView internals.
        self._placeholder = Gtk.Label(label=_EMPTY_PLACEHOLDER)
        self._placeholder.set_halign(Gtk.Align.START)
        self._placeholder.set_valign(Gtk.Align.START)
        self._placeholder.set_margin_start(12)
        self._placeholder.set_margin_top(12)
        self._placeholder.add_css_class("dim-label")
        self._placeholder.set_wrap(True)
        self._placeholder.set_xalign(0)
        # Accessible role: the label is purely decorative hint text
        self._placeholder.set_tooltip_text("Empty editor — open or create a file")

        overlay = Gtk.Overlay()
        overlay.set_child(self._view)
        overlay.add_overlay(self._placeholder)
        overlay.set_measure_overlay(self._placeholder, False)
        self.set_child(overlay)

        # Keep placeholder visibility in sync with buffer content
        self._buffer.connect("changed", self._update_placeholder_visibility)
        self._update_placeholder_visibility(self._buffer)

    def _update_placeholder_visibility(self, buf):
        """Show placeholder only when the buffer text is empty."""
        start, end = buf.get_bounds()
        empty = (buf.get_text(start, end, False) == "")
        self._placeholder.set_visible(empty)

    def _setup_manual_tags(self):
        """Create text tags for fallback syntax highlighting."""
        table = self._buffer.get_tag_table()

        def make_tag(name, **props):
            tag = Gtk.TextTag.new(name)
            for k, v in props.items():
                tag.set_property(k.replace("_", "-"), v)
            table.add(tag)

        make_tag("h1", weight=Pango.Weight.BOLD, scale=1.8)
        make_tag("h2", weight=Pango.Weight.BOLD, scale=1.5)
        make_tag("h3", weight=Pango.Weight.BOLD, scale=1.3)
        make_tag("h4", weight=Pango.Weight.BOLD, scale=1.1)
        make_tag("bold", weight=Pango.Weight.BOLD)
        make_tag("italic", style=Pango.Style.ITALIC)
        make_tag("code", family="monospace", background="#f0f0f0")
        make_tag("blockquote", foreground="#666666", style=Pango.Style.ITALIC)
        make_tag("link", foreground="#0066cc", underline=Pango.Underline.SINGLE)

    # ── Change handling (debounced) ───────────────────────────────────────

    def _on_changed(self, buf):
        if self._loading:
            return
        # Cancel any pending preview timer and restart it
        if self._preview_timer is not None:
            GLib.source_remove(self._preview_timer)
            self._preview_timer = None
        self._preview_timer = GLib.timeout_add(300, self._emit_content_changed)
        # Debounce manual syntax highlighting in fallback mode
        if not HAS_SOURCE_VIEW:
            if self._highlight_timer is not None:
                GLib.source_remove(self._highlight_timer)
                self._highlight_timer = None
            self._highlight_timer = GLib.timeout_add(300, self._run_manual_highlight)

    def _emit_content_changed(self):
        self._preview_timer = None
        self.emit("content-changed")
        return False  # do not repeat

    def _run_manual_highlight(self):
        self._highlight_timer = None
        self._apply_manual_highlighting()
        return False  # do not repeat

    def _on_cursor_notify(self, buf, param):
        line, col = self._get_cursor_position()
        self.emit("cursor-moved", line, col)

    def _get_cursor_position(self):
        mark = self._buffer.get_insert()
        it = self._buffer.get_iter_at_mark(mark)
        return it.get_line() + 1, it.get_line_offset() + 1

    # ── Manual syntax highlighting (fallback only) ────────────────────────

    def _apply_manual_highlighting(self):
        """Apply regex-based tag highlighting (used only in plain-TextView mode)."""
        buf = self._buffer
        start, end = buf.get_bounds()
        # Clear existing tags
        for tag_name in ["h1", "h2", "h3", "h4", "bold", "italic", "code", "blockquote", "link"]:
            tag = buf.get_tag_table().lookup(tag_name)
            if tag:
                buf.remove_tag(tag, start, end)

        text = buf.get_text(start, end, False)
        patterns = [
            (r"^#{4}\s+.*$",      "h4",         re.MULTILINE),
            (r"^#{3}\s+.*$",      "h3",         re.MULTILINE),
            (r"^#{2}\s+.*$",      "h2",         re.MULTILINE),
            (r"^#\s+.*$",         "h1",         re.MULTILINE),
            (r"\*\*[^*]+\*\*",    "bold",       0),
            (r"__[^_]+__",        "bold",       0),
            (r"\*[^*]+\*",        "italic",     0),
            (r"_[^_]+_",          "italic",     0),
            (r"`[^`]+`",          "code",       0),
            (r"^>.*$",            "blockquote", re.MULTILINE),
            (r"\[.+?\]\(.+?\)",   "link",       0),
        ]
        for pattern, tag_name, flags in patterns:
            for m in re.finditer(pattern, text, flags):
                s = buf.get_iter_at_offset(m.start())
                e = buf.get_iter_at_offset(m.end())
                buf.apply_tag_by_name(tag_name, s, e)

    # ── GtkSource theme ───────────────────────────────────────────────────

    def _apply_source_scheme(self, is_dark):
        """Switch between Adwaita and Adwaita-dark GtkSource style schemes."""
        if not HAS_SOURCE_VIEW:
            return
        scheme_name = "Adwaita-dark" if is_dark else "Adwaita"
        scheme = self._scheme_mgr.get_scheme(scheme_name)
        if scheme:
            self._buffer.set_style_scheme(scheme)

    # ── Public API ────────────────────────────────────────────────────────

    def get_text(self):
        """Return the full buffer contents as a string."""
        start, end = self._buffer.get_bounds()
        return self._buffer.get_text(start, end, False)

    def set_text(self, text):
        """Replace the entire buffer with *text*, suppressing change signals."""
        self._loading = True
        try:
            self._buffer.set_text(text)
            # Move cursor to beginning
            start = self._buffer.get_start_iter()
            self._buffer.place_cursor(start)
        finally:
            self._loading = False
        # Trigger a one-shot highlight pass after loading (fallback mode only)
        if not HAS_SOURCE_VIEW:
            self._apply_manual_highlighting()

    def set_word_wrap(self, enabled):
        """Enable or disable word-wrapping in the editor view."""
        mode = Gtk.WrapMode.WORD_CHAR if enabled else Gtk.WrapMode.NONE
        self._view.set_wrap_mode(mode)

    def set_line_numbers(self, enabled):
        """Show or hide line numbers (GtkSourceView only)."""
        if HAS_SOURCE_VIEW:
            self._view.set_show_line_numbers(enabled)

    def set_theme(self, is_dark):
        """Respond to a system light/dark theme change."""
        self._is_dark = is_dark
        self._apply_source_scheme(is_dark)
        if not HAS_SOURCE_VIEW:
            # Update code tag background for dark mode
            table = self._buffer.get_tag_table()
            code_tag = table.lookup("code")
            if code_tag:
                bg = "#2d2d2d" if is_dark else "#f0f0f0"
                code_tag.set_property("background", bg)

    def cleanup(self):
        """Cancel any pending debounce timers.

        Call this before the widget is destroyed to avoid firing signals
        on a deallocated object (GObject reference-cycle / use-after-free).
        """
        if self._preview_timer is not None:
            GLib.source_remove(self._preview_timer)
            self._preview_timer = None
        if self._highlight_timer is not None:
            GLib.source_remove(self._highlight_timer)
            self._highlight_timer = None

    @property
    def has_source_view(self):
        """True if GtkSourceView 5 is active."""
        return HAS_SOURCE_VIEW
