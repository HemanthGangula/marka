"""File I/O manager — new, open, save, save-as, export, recent files, drag-drop.

Provides a compatibility shim: Gtk.FileDialog (GTK >= 4.10) is preferred;
on GTK 4.6 (Ubuntu 22.04 LTS) we fall back to Gtk.FileChooserNative.
"""

import os
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

# GTK version detection — FileDialog requires 4.10
_gtk_major = Gtk.get_major_version()
_gtk_minor = Gtk.get_minor_version()
_HAS_FILE_DIALOG = (_gtk_major, _gtk_minor) >= (4, 10)


class FileManager:
    """Handles all file I/O: new, open, save, save-as, export, recent files, drag-drop."""

    MARKDOWN_MIMES = {"text/markdown", "text/x-markdown"}
    MARKDOWN_EXTS = (".md", ".markdown", ".mkd", ".mdown")

    def __init__(self, window):
        self._window = window
        self._current_file = None  # Gio.File or None
        self.is_modified = False

        self._recent_manager = Gtk.RecentManager.get_default()

        # Register open-path window action for recent-files menu
        open_path_action = Gio.SimpleAction.new(
            "open-path", GLib.VariantType.new("s")
        )
        open_path_action.connect("activate", self._on_open_path)
        self._window.add_action(open_path_action)

        self._setup_drag_drop()

    # ── Drag and drop ─────────────────────────────────────────────────────

    def _setup_drag_drop(self):
        """Register a drop target on the window for file drag-and-drop."""
        target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        target.connect("drop", self._on_drop)
        self._window.add_controller(target)

    def _on_drop(self, target, value, x, y):
        if isinstance(value, Gdk.FileList):
            files = list(value)
            if files:
                self.load_gfile(files[0])
        return True

    # ── New file ──────────────────────────────────────────────────────────

    def new_file(self):
        """Create a new empty document, prompting if there are unsaved changes."""
        if self.is_modified:
            self.check_unsaved_changes(callback=self._do_new)
        else:
            self._do_new()

    def _do_new(self):
        self._current_file = None
        self.is_modified = False
        self._window.load_content("", path=None)

    # ── Open file ─────────────────────────────────────────────────────────

    def open_file_dialog(self):
        """Open a file chooser dialog, prompting for unsaved changes first."""
        if self.is_modified:
            self.check_unsaved_changes(callback=self._show_open_dialog)
        else:
            self._show_open_dialog()

    def _show_open_dialog(self):
        if _HAS_FILE_DIALOG:
            self._show_open_dialog_modern()
        else:
            self._show_open_dialog_compat()

    def _show_open_dialog_modern(self):
        """Use Gtk.FileDialog (GTK >= 4.10)."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Open Markdown File")
        dialog.set_filters(self._make_filter_list())
        dialog.open(self._window, None, self._on_open_finish_modern)

    def _on_open_finish_modern(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
            self.load_gfile(gfile)
        except GLib.Error as e:
            if e.code != 2:  # 2 == user cancelled
                self._window.show_toast(f"Open error: {e.message}")

    def _show_open_dialog_compat(self):
        """Use Gtk.FileChooserNative (GTK < 4.10) as fallback."""
        dialog = Gtk.FileChooserNative.new(
            "Open Markdown File",
            self._window,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel",
        )
        md_filter = self._make_single_filter()
        dialog.add_filter(md_filter)
        dialog.connect("response", self._on_open_compat_response)
        dialog.show()

    def _on_open_compat_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                self.load_gfile(gfile)

    def load_gfile(self, gfile):
        """Load the content of a Gio.File into the editor."""
        if not gfile:
            return
        path = gfile.get_path()
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            self._window.show_toast(f"Could not open file: {e}")
            return

        self._current_file = gfile
        self.is_modified = False
        self._window.load_content(text, path=path)
        self._add_to_recent(gfile.get_uri())
        self._refresh_recent_menu()

    def _on_open_path(self, action, param):
        if param is None:
            return
        path = param.get_string()
        if path and os.path.isfile(path):
            self.load_gfile(Gio.File.new_for_path(path))
        else:
            self._window.show_toast("Recent file not found.")

    # ── Save ──────────────────────────────────────────────────────────────

    def save_file(self):
        """Save to the current file, or show Save As dialog if no file is set."""
        if self._current_file:
            self._write_to_file(self._current_file)
        else:
            self.save_as_dialog()

    def save_as_dialog(self):
        """Open a Save As dialog."""
        if _HAS_FILE_DIALOG:
            self._save_as_dialog_modern()
        else:
            self._save_as_dialog_compat()

    def _save_as_dialog_modern(self):
        """Save As using Gtk.FileDialog (GTK >= 4.10)."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Save Markdown File")
        dialog.set_filters(self._make_filter_list())
        if self._current_file:
            dialog.set_initial_file(self._current_file)
        else:
            dialog.set_initial_name("untitled.md")
        dialog.save(self._window, None, self._on_save_finish_modern)

    def _on_save_finish_modern(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            self._write_to_file(gfile)
            self._current_file = gfile
            path = gfile.get_path()
            self._window._title_widget.set_subtitle(path or "")
            self._window._status_bar.update_filename(path)
            self._window._update_title(False)
            self.is_modified = False
            self._add_to_recent(gfile.get_uri())
            self._refresh_recent_menu()
        except GLib.Error as e:
            if e.code != 2:
                self._window.show_toast(f"Save error: {e.message}")

    def _save_as_dialog_compat(self):
        """Save As using Gtk.FileChooserNative (GTK < 4.10)."""
        dialog = Gtk.FileChooserNative.new(
            "Save Markdown File",
            self._window,
            Gtk.FileChooserAction.SAVE,
            "_Save",
            "_Cancel",
        )
        if self._current_file:
            dialog.set_file(self._current_file)
        else:
            dialog.set_current_name("untitled.md")
        dialog.add_filter(self._make_single_filter())
        dialog.connect("response", self._on_save_compat_response)
        dialog.show()

    def _on_save_compat_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                self._write_to_file(gfile)
                self._current_file = gfile
                path = gfile.get_path()
                self._window._title_widget.set_subtitle(path or "")
                self._window._status_bar.update_filename(path)
                self._window._update_title(False)
                self.is_modified = False
                self._add_to_recent(gfile.get_uri())
                self._refresh_recent_menu()

    def _write_to_file(self, gfile):
        """Write the current editor buffer to *gfile*."""
        text = self._window._editor.get_text()
        path = gfile.get_path()
        if not path:
            self._window.show_toast("Save failed: could not determine file path.")
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.is_modified = False
            self._window._update_title(False)
            self._window.show_toast(f"Saved: {os.path.basename(path)}")
        except OSError as e:
            self._window.show_toast(f"Save failed: {e}")

    # ── Export to HTML ─────────────────────────────────────────────────────

    def export_html(self):
        """Export the current rendered preview as a standalone HTML file."""
        if _HAS_FILE_DIALOG:
            self._export_html_modern()
        else:
            self._export_html_compat()

    def _export_html_modern(self):
        """Export HTML using Gtk.FileDialog (GTK >= 4.10)."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Export as HTML")
        dialog.set_filters(self._make_html_filter_list())
        # Suggest a filename based on the current markdown file
        base = self._get_export_basename()
        dialog.set_initial_name(base)
        dialog.save(self._window, None, self._on_export_finish_modern)

    def _on_export_finish_modern(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
            self._write_html(gfile)
        except GLib.Error as e:
            if e.code != 2:
                self._window.show_toast(f"Export error: {e.message}")

    def _export_html_compat(self):
        """Export HTML using Gtk.FileChooserNative (GTK < 4.10)."""
        dialog = Gtk.FileChooserNative.new(
            "Export as HTML",
            self._window,
            Gtk.FileChooserAction.SAVE,
            "_Export",
            "_Cancel",
        )
        dialog.set_current_name(self._get_export_basename())
        html_filter = Gtk.FileFilter()
        html_filter.set_name("HTML Files")
        html_filter.add_mime_type("text/html")
        html_filter.add_pattern("*.html")
        dialog.add_filter(html_filter)
        dialog.connect("response", self._on_export_compat_response)
        dialog.show()

    def _on_export_compat_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dialog.get_file()
            if gfile:
                self._write_html(gfile)

    def _get_export_basename(self):
        """Return a suggested .html filename derived from the current .md path."""
        if self._current_file:
            path = self._current_file.get_path()
            if path:
                stem = os.path.splitext(os.path.basename(path))[0]
                return f"{stem}.html"
        return "export.html"

    def _write_html(self, gfile):
        """Write the fully-rendered HTML document to *gfile*."""
        path = gfile.get_path()
        if not path:
            self._window.show_toast("Export failed: could not determine file path.")
            return
        # Obtain the full HTML from the preview pane's current render
        preview = self._window._preview
        html = preview._build_full_html(preview._current_html_body)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            self._window.show_toast(f"Exported: {os.path.basename(path)}")
        except OSError as e:
            self._window.show_toast(f"Export failed: {e}")

    # ── Unsaved changes dialog ────────────────────────────────────────────

    def check_unsaved_changes(self, callback):
        """Show Save/Discard/Cancel dialog, then call *callback* on Discard or Save."""
        dialog = Adw.AlertDialog.new(
            "Save Changes?",
            "You have unsaved changes. Do you want to save them before continuing?"
        )
        dialog.add_response("cancel",  "Cancel")
        dialog.add_response("discard", "Discard")
        dialog.add_response("save",    "Save")
        dialog.set_response_appearance("discard", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_response_appearance("save",    Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_unsaved_response, callback)
        dialog.present(self._window)

    def _on_unsaved_response(self, dialog, response, callback):
        if response == "save":
            self.save_file()
            callback()
        elif response == "discard":
            callback()
        # "cancel" -> do nothing

    # ── Recent files ──────────────────────────────────────────────────────

    def _add_to_recent(self, uri):
        self._recent_manager.add_item(uri)

    def get_recent_items(self, limit=10):
        """Return up to *limit* (label, path) tuples for existing Markdown files.

        GLib.filename_from_uri returns a (path, hostname) tuple; index [0] is
        the local filesystem path.
        """
        items = []
        for item in self._recent_manager.get_items():
            uri = item.get_uri()
            if not uri or not uri.startswith("file://"):
                continue
            try:
                result = GLib.filename_from_uri(uri)
                path = result[0] if result else None
            except GLib.Error:
                path = None
            if not path or not os.path.isfile(path):
                continue
            ext = os.path.splitext(path)[1].lower()
            mime = item.get_mime_type() or ""
            if ext in self.MARKDOWN_EXTS or mime in self.MARKDOWN_MIMES:
                label = os.path.basename(path)
                items.append((label, path))
                if len(items) >= limit:
                    break
        return items

    def _refresh_recent_menu(self):
        recent = self.get_recent_items()
        self._window.update_recent_menu(recent)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _make_filter_list(self):
        """Build a Gio.ListStore of Gtk.FileFilter for Markdown files."""
        store = Gio.ListStore.new(Gtk.FileFilter)

        md_filter = Gtk.FileFilter()
        md_filter.set_name("Markdown Files")
        for ext in self.MARKDOWN_EXTS:
            md_filter.add_pattern(f"*{ext}")
        for mime in self.MARKDOWN_MIMES:
            md_filter.add_mime_type(mime)
        store.append(md_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        store.append(all_filter)

        return store

    def _make_single_filter(self):
        """Return a single Gtk.FileFilter for Markdown (used with FileChooserNative)."""
        md_filter = Gtk.FileFilter()
        md_filter.set_name("Markdown Files")
        for ext in self.MARKDOWN_EXTS:
            md_filter.add_pattern(f"*{ext}")
        for mime in self.MARKDOWN_MIMES:
            md_filter.add_mime_type(mime)
        return md_filter

    def _make_html_filter_list(self):
        """Build a Gio.ListStore of Gtk.FileFilter for HTML export."""
        store = Gio.ListStore.new(Gtk.FileFilter)

        html_filter = Gtk.FileFilter()
        html_filter.set_name("HTML Files")
        html_filter.add_mime_type("text/html")
        html_filter.add_pattern("*.html")
        store.append(html_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name("All Files")
        all_filter.add_pattern("*")
        store.append(all_filter)

        return store

    def get_base_uri(self):
        """Return base URI for the current file's directory (for relative image paths)."""
        if self._current_file:
            path = self._current_file.get_path()
            if path:
                directory = os.path.dirname(path)
                return GLib.filename_to_uri(directory)
        return None

    def get_display_name(self):
        """Return a short display name for the title bar."""
        if self._current_file:
            path = self._current_file.get_path()
            if path:
                return os.path.basename(path)
        return "Untitled"

    def mark_modified(self):
        """Programmatically mark the document as having unsaved changes."""
        self.is_modified = True
