import os
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class StatusBar(Gtk.ActionBar):
    """Bottom status bar showing cursor position, filename, and word/char count."""

    def __init__(self):
        super().__init__()

        self._cursor_label = Gtk.Label(label="Ln 1, Col 1")
        self._cursor_label.add_css_class("dim-label")
        self._cursor_label.set_margin_start(4)
        self._cursor_label.set_margin_end(8)

        self._file_label = Gtk.Label(label="Untitled")
        self._file_label.add_css_class("dim-label")

        self._stats_label = Gtk.Label(label="0 words · 0 chars")
        self._stats_label.add_css_class("dim-label")
        self._stats_label.set_margin_start(8)
        self._stats_label.set_margin_end(4)

        self.pack_start(self._cursor_label)
        self.set_center_widget(self._file_label)
        self.pack_end(self._stats_label)

    def update_cursor(self, line, col):
        self._cursor_label.set_text(f"Ln {line}, Col {col}")

    def update_stats(self, text):
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        self._stats_label.set_text(f"{words} words · {chars} chars")

    def update_filename(self, path):
        if path:
            self._file_label.set_text(os.path.basename(path))
        else:
            self._file_label.set_text("Untitled")
