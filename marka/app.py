"""Marka application class — Adw.Application subclass and entry point."""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio

from marka import APP_ID


class MarkaApp(Adw.Application):
    """Top-level GApplication subclass.

    Builds all app-level actions and keyboard accelerators, then delegates
    to MarkaWindow for the actual UI.
    """

    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_OPEN,
        )
        self._window = None

    def do_startup(self):
        """Initialise actions and accelerators before the first window."""
        Adw.Application.do_startup(self)
        self._build_actions()

    def do_activate(self):
        """Present (or create) the main window."""
        if not self._window:
            from marka.window import MarkaWindow
            self._window = MarkaWindow(application=self)
        self._window.present()

    def do_open(self, files, n_files, hint):
        """Handle files passed on the command line or via D-Bus open."""
        self.do_activate()
        if files:
            self._window.open_file_from_gfile(files[0])

    def _build_actions(self):
        """Register all app-level Gio.SimpleAction objects with accelerators."""
        actions = [
            ("new",              self._on_new,              ["<Ctrl>n"]),
            ("open",             self._on_open,             ["<Ctrl>o"]),
            ("save",             self._on_save,             ["<Ctrl>s"]),
            ("save-as",          self._on_save_as,          ["<Ctrl><Shift>s"]),
            ("quit",             self._on_quit,             ["<Ctrl>q"]),
            # View / document actions (routed to window)
            ("find",             self._on_find,             ["<Ctrl>f"]),
            ("zoom-in",          self._on_zoom_in,          ["<Ctrl>equal", "<Ctrl>plus"]),
            ("zoom-out",         self._on_zoom_out,         ["<Ctrl>minus"]),
            ("zoom-reset",       self._on_zoom_reset,       ["<Ctrl>0"]),
            ("print",            self._on_print,            ["<Ctrl>p"]),
            ("export-html",      self._on_export_html,      []),
            # View-mode switching (segmented control keyboard shortcuts)
            ("set-mode-editor",  self._on_set_mode_editor,  ["<Ctrl>e"]),
            ("set-mode-split",   self._on_set_mode_split,   ["<Ctrl>backslash"]),
            ("set-mode-preview", self._on_set_mode_preview, ["<Ctrl><Shift>e"]),
        ]
        for name, callback, accels in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    # ── Action callbacks ───────────────────────────────────────────────────

    def _on_new(self, action, param):
        if self._window:
            self._window.file_manager.new_file()

    def _on_open(self, action, param):
        if self._window:
            self._window.file_manager.open_file_dialog()

    def _on_save(self, action, param):
        if self._window:
            self._window.file_manager.save_file()

    def _on_save_as(self, action, param):
        if self._window:
            self._window.file_manager.save_as_dialog()

    def _on_quit(self, action, param):
        if self._window:
            self._window.request_close()
        else:
            self.quit()

    def _on_find(self, action, param):
        if self._window:
            self._window.toggle_find_bar()

    def _on_zoom_in(self, action, param):
        if self._window:
            self._window.preview_zoom(+1)

    def _on_zoom_out(self, action, param):
        if self._window:
            self._window.preview_zoom(-1)

    def _on_zoom_reset(self, action, param):
        if self._window:
            self._window.preview_zoom(0)

    def _on_print(self, action, param):
        if self._window:
            self._window.print_preview()

    def _on_export_html(self, action, param):
        if self._window:
            self._window.file_manager.export_html()

    def _on_set_mode_editor(self, action, param):
        if self._window:
            self._window.set_view_mode("editor")

    def _on_set_mode_split(self, action, param):
        if self._window:
            self._window.set_view_mode("split")

    def _on_set_mode_preview(self, action, param):
        if self._window:
            self._window.set_view_mode("preview")


def main():
    """Console-scripts entry point (pip install)."""
    app = MarkaApp()
    sys.exit(app.run(sys.argv))
