"""Main application window — MDViewerWindow."""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from mdviewer import APP_NAME, __version__
from mdviewer.editor import EditorPane
from mdviewer.preview import PreviewPane
from mdviewer.renderer import MarkdownRenderer
from mdviewer.status_bar import StatusBar
from mdviewer.file_manager import FileManager
from mdviewer.theme_manager import ThemeManager
from mdviewer import config as _cfg


class MDViewerWindow(Adw.ApplicationWindow):
    """Primary window for MD Viewer.

    Hosts the editor pane, preview pane, status bar, header bar, find bar,
    and all window-level actions.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load persisted settings before building UI
        self._settings = _cfg.load()

        w = self._settings.get("window_width", 1100)
        h = self._settings.get("window_height", 700)
        self.set_default_size(w, h)
        self.set_title(APP_NAME)

        # Core components
        self._renderer = MarkdownRenderer()
        self._editor = EditorPane()
        self._preview = PreviewPane()
        self._status_bar = StatusBar()
        self.file_manager = FileManager(self)
        self._theme_manager = ThemeManager(self._editor, self._preview)
        self._theme_manager.set_renderer(self._renderer)

        # View mode: "split", "editor", "preview"
        self._view_mode = "split"

        # Guard: True while load_content() is executing so content-changed
        # does not mark the document as modified during the initial text load.
        self._loading_content = False

        self._build_ui()
        self._connect_signals()

        # Defer last-file restore until AFTER present() so the WebView is
        # realized before load_html() is called.  Calling load_html() on an
        # unrealized WebKit widget triggers gtk_overlay_set_child assertions
        # inside WebKit's internal GTK overlay management.
        last = self._settings.get("last_file")
        if last:
            import os
            if os.path.isfile(last):
                GLib.idle_add(self._restore_last_file, last)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self):
        """Assemble the full window widget hierarchy — strictly bottom-up.

        Build order: leaf widgets → containers → window.
        This guarantees every widget has its children fully configured before
        it is attached to a parent, preventing gtk_overlay_set_child assertion
        failures that occur when a widget already has a parent at attach time.
        """
        # ── 1. Paned: give it children before attaching anywhere ──────────
        self._paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self._paned.set_wide_handle(True)
        self._paned.set_start_child(self._editor)
        self._paned.set_end_child(self._preview)
        self._paned.set_resize_start_child(True)
        self._paned.set_resize_end_child(True)

        # ── 2. Toast overlay: set child before attaching to toolbar_view ──
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(self._paned)

        # ── 3. Toolbar view: set content before attaching to window ───────
        toolbar_view = Adw.ToolbarView()
        toolbar_view.set_content(self._toast_overlay)
        toolbar_view.add_top_bar(self._build_header_bar())
        self._find_bar = self._build_find_bar()
        toolbar_view.add_top_bar(self._find_bar)
        toolbar_view.add_bottom_bar(self._status_bar)

        # ── 4. Window: attach fully-built tree last ────────────────────────
        self.set_content(toolbar_view)

        self.connect("realize", self._on_realize)

    def _build_header_bar(self):
        """Build the Adw.HeaderBar following GNOME HIG layout conventions."""
        header = Adw.HeaderBar()

        # Left side: New + Open (non-destructive navigation actions)
        new_btn = Gtk.Button(label="New")
        new_btn.set_action_name("app.new")
        new_btn.set_tooltip_text("New document (Ctrl+N)")
        new_btn.add_css_class("flat")

        open_btn = Gtk.Button(label="Open")
        open_btn.set_action_name("app.open")
        open_btn.set_tooltip_text("Open file (Ctrl+O)")
        open_btn.add_css_class("flat")

        header.pack_start(new_btn)
        header.pack_start(open_btn)

        # Center title
        self._title_widget = Adw.WindowTitle(title=APP_NAME, subtitle="")
        header.set_title_widget(self._title_widget)

        # Right side: menu button (packed first so it ends up rightmost)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_icon_name("open-menu-symbolic")
        menu_btn.set_tooltip_text("Main menu")
        menu_btn.add_css_class("flat")
        menu_btn.set_menu_model(self._build_menu())
        header.pack_end(menu_btn)

        # Segmented view-mode control (packed after menu so it sits left of it)
        view_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        view_box.add_css_class("linked")

        self._btn_editor = Gtk.ToggleButton()
        self._btn_editor.set_icon_name("document-edit-symbolic")
        self._btn_editor.set_tooltip_text("Editor only (Ctrl+E)")

        self._btn_split = Gtk.ToggleButton()
        self._btn_split.set_icon_name("view-dual-symbolic")
        self._btn_split.set_tooltip_text("Split view (Ctrl+Backslash)")
        self._btn_split.set_active(True)  # default mode

        self._btn_preview = Gtk.ToggleButton()
        self._btn_preview.set_icon_name("document-preview-symbolic")
        self._btn_preview.set_tooltip_text("Preview only (Ctrl+Shift+E)")

        # Link as a radio group: only one can be active at a time
        self._btn_editor.set_group(self._btn_split)
        self._btn_preview.set_group(self._btn_split)

        self._btn_editor.connect("toggled", self._on_mode_btn_toggled, "editor")
        self._btn_split.connect("toggled", self._on_mode_btn_toggled, "split")
        self._btn_preview.connect("toggled", self._on_mode_btn_toggled, "preview")

        view_box.append(self._btn_editor)
        view_box.append(self._btn_split)
        view_box.append(self._btn_preview)

        header.pack_end(view_box)

        return header

    def _build_find_bar(self):
        """Build a Gtk.SearchBar for find-in-document (Ctrl+F)."""
        search_bar = Gtk.SearchBar()
        search_bar.set_show_close_button(True)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_placeholder_text("Find in preview\u2026")
        self._search_entry.set_hexpand(True)
        self._search_entry.set_tooltip_text("Search text in the preview pane")

        search_bar.set_child(self._search_entry)
        search_bar.connect_entry(self._search_entry)

        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("activate", self._on_search_next)
        self._search_entry.connect("stop-search", self._on_search_stop)

        return search_bar

    def _build_menu(self):
        """Build the primary (hamburger) menu model."""
        menu = Gio.Menu()

        file_section = Gio.Menu()
        file_section.append("Save", "app.save")
        file_section.append("Save As\u2026", "app.save-as")
        file_section.append("Export as HTML\u2026", "app.export-html")
        menu.append_section(None, file_section)

        self._recent_menu = Gio.Menu()
        self._recent_menu.append("(no recent files)", None)
        menu.append_submenu("Recent Files", self._recent_menu)

        view_section = Gio.Menu()
        view_section.append("Editor Mode", "app.set-mode-editor")
        view_section.append("Split Mode", "app.set-mode-split")
        view_section.append("Preview Mode", "app.set-mode-preview")
        view_section.append("Find in Document", "app.find")
        view_section.append("Zoom In", "app.zoom-in")
        view_section.append("Zoom Out", "app.zoom-out")
        view_section.append("Reset Zoom", "app.zoom-reset")
        view_section.append("Print\u2026", "app.print")
        view_section.append("Toggle Word Wrap", "win.word-wrap")
        view_section.append("Toggle Line Numbers", "win.line-numbers")
        menu.append_section(None, view_section)

        app_section = Gio.Menu()
        app_section.append("About MD Viewer", "win.about")
        app_section.append("Quit", "app.quit")
        menu.append_section(None, app_section)

        return menu

    # ── Signals ───────────────────────────────────────────────────────────

    def _connect_signals(self):
        """Wire up all window-level signals and register window actions."""
        self._editor.connect("content-changed", self._on_content_changed)
        self._editor.connect("cursor-moved", self._on_cursor_moved)

        # Window-level stateful actions
        word_wrap = Gio.SimpleAction.new_stateful(
            "word-wrap", None, GLib.Variant.new_boolean(True)
        )
        word_wrap.connect("activate", self._on_word_wrap_toggle)
        self.add_action(word_wrap)

        line_nums = Gio.SimpleAction.new_stateful(
            "line-numbers", None, GLib.Variant.new_boolean(True)
        )
        line_nums.connect("activate", self._on_line_numbers_toggle)
        self.add_action(line_nums)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Ctrl+W closes the window
        close_action = Gio.SimpleAction.new("close", None)
        close_action.connect("activate", lambda a, p: self.request_close())
        self.add_action(close_action)
        self.get_application().set_accels_for_action("win.close", ["<Ctrl>w"])

        # Escape dismisses find bar
        key_ctl = Gtk.EventControllerKey()
        key_ctl.connect("key-pressed", self._on_key_pressed)
        self.add_controller(key_ctl)

        self.connect("close-request", self._on_close_request)

    def _on_realize(self, widget):
        width = self.get_width() or self._settings.get("window_width", 1100)
        saved_pos = self._settings.get("paned_position", -1)
        # Guard: reject positions that collapse either pane (>90 % or <10 % of width)
        if isinstance(saved_pos, int) and 0 < saved_pos < int(width * 0.9):
            self._paned.set_position(saved_pos)
        else:
            self._paned.set_position(width // 2)

    def _on_content_changed(self, editor):
        """Handle editor content changes: re-render preview and update title."""
        # Ignore signal fired while programmatically loading content
        if self._loading_content:
            return
        text = editor.get_text()
        html = self._renderer.convert(text)
        base_uri = self.file_manager.get_base_uri()
        self._preview.update_content(html, base_uri)
        self._status_bar.update_stats(text)
        self.file_manager.is_modified = True
        self._update_title(True)

    def _on_cursor_moved(self, editor, line, col):
        self._status_bar.update_cursor(line, col)

    def _on_mode_btn_toggled(self, btn, mode):
        """Handle a view-mode toggle button being pressed.

        GTK fires 'toggled' for both the button gaining active state *and* the
        one losing it.  We only act on the activation signal.
        """
        if not btn.get_active():
            return  # ignore de-activation of the previously active button
        self._view_mode = mode
        self._apply_view_mode()

    def _apply_view_mode(self):
        """Sync button highlight states and pane visibility to self._view_mode."""
        mode_map = {
            "editor":  self._btn_editor,
            "split":   self._btn_split,
            "preview": self._btn_preview,
        }
        for mode, btn in mode_map.items():
            # Block the toggled signal while we programmatically set active
            # state to avoid re-entrant calls to _on_mode_btn_toggled.
            btn.handler_block_by_func(self._on_mode_btn_toggled)
            btn.set_active(mode == self._view_mode)
            btn.handler_unblock_by_func(self._on_mode_btn_toggled)

        self._editor.set_visible(self._view_mode in ("split", "editor"))
        self._preview.set_visible(self._view_mode in ("split", "preview"))

    def _on_word_wrap_toggle(self, action, param):
        state = action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(not state))
        self._editor.set_word_wrap(not state)

    def _on_line_numbers_toggle(self, action, param):
        state = action.get_state().get_boolean()
        action.set_state(GLib.Variant.new_boolean(not state))
        self._editor.set_line_numbers(not state)

    def _on_about(self, action, param):
        from mdviewer.editor import HAS_SOURCE_VIEW
        sv_note = (
            "GtkSourceView 5 is active \u2014 full syntax highlighting enabled."
            if HAS_SOURCE_VIEW
            else "GtkSourceView 5 not found \u2014 using plain-text fallback highlighting.\n"
                 "Install gir1.2-gtksource-5 for the best editing experience."
        )
        about = Adw.AboutDialog()
        about.set_application_name(APP_NAME)
        about.set_version(__version__)
        about.set_comments(
            "A lightweight Markdown viewer and editor for Linux.\n\n" + sv_note
        )
        about.set_license_type(Gtk.License.MIT_X11)
        about.set_application_icon("text-editor")
        about.present(self)

    def _on_close_request(self, window):
        self._persist_state()
        if self.file_manager.is_modified:
            self.file_manager.check_unsaved_changes(callback=self.get_application().quit)
            return True  # suppress default close
        return False

    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Dismiss the find bar on Escape."""
        if keyval == 0xff1b:  # GDK_KEY_Escape
            if self._find_bar.get_search_mode():
                self._find_bar.set_search_mode(False)
                return True
        return False

    # ── Find in document ──────────────────────────────────────────────────

    def _on_search_changed(self, entry):
        """Forward search term to the preview pane's WebView find controller."""
        query = entry.get_text()
        self._preview.find_text(query)

    def _on_search_next(self, entry):
        """Advance to the next search result."""
        self._preview.find_next()

    def _on_search_stop(self, entry):
        """Close the find bar and clear highlights."""
        self._find_bar.set_search_mode(False)
        self._preview.find_text("")

    # ── Zoom ──────────────────────────────────────────────────────────────

    def preview_zoom(self, direction):
        """Adjust preview zoom level.

        direction: +1 to zoom in, -1 to zoom out, 0 to reset.
        """
        self._preview.adjust_zoom(direction)

    # ── Print ─────────────────────────────────────────────────────────────

    def print_preview(self):
        """Trigger WebKit print dialog for the current preview content."""
        self._preview.print_document(self)

    # ── Persistence ───────────────────────────────────────────────────────

    def _persist_state(self):
        """Save window geometry, paned position, and last open file."""
        width = self.get_width()
        height = self.get_height()
        paned_pos = self._paned.get_position()
        last_file = None
        if self.file_manager._current_file:
            last_file = self.file_manager._current_file.get_path()

        settings = dict(self._settings)
        if width > 0:
            settings["window_width"] = width
        if height > 0:
            settings["window_height"] = height
        if paned_pos > 0:
            settings["paned_position"] = paned_pos
        settings["last_file"] = last_file
        _cfg.save(settings)

    # ── Public API ────────────────────────────────────────────────────────

    def _restore_last_file(self, path):
        """Called via GLib.idle_add after present() so WebView is realized.

        Only opens the file if it carries a recognised markdown extension to
        prevent arbitrary file types (or path-injection values read from the
        config) from being loaded into the editor.
        """
        import os
        _MARKDOWN_EXTS = (".md", ".markdown", ".mdown", ".mkd", ".mkdn", ".txt")
        if not isinstance(path, str):
            return False
        if not path.lower().endswith(_MARKDOWN_EXTS):
            return False  # silently skip non-markdown paths
        if os.path.isfile(path):
            self.file_manager.load_gfile(Gio.File.new_for_path(path))
        return False  # do not repeat

    def open_file_from_gfile(self, gfile):
        """Open a Gio.File — called from do_open and drag-drop."""
        self.file_manager.load_gfile(gfile)

    def load_content(self, text, path=None):
        """Load text into the editor and trigger an initial preview render.

        The _loading_content guard ensures that the buffer's 'changed' signal
        (fired by set_text) does not trigger _on_content_changed and
        incorrectly mark the document as modified during the initial load.
        """
        self._loading_content = True
        try:
            self._editor.set_text(text)
        finally:
            self._loading_content = False

        self.file_manager.is_modified = False
        if path:
            self._title_widget.set_subtitle(path)
            self._status_bar.update_filename(path)
        else:
            self._title_widget.set_subtitle("")
            self._status_bar.update_filename(None)
        self._update_title(False)
        # Trigger initial preview render directly (not via content-changed signal)
        html = self._renderer.convert(text)
        base_uri = self.file_manager.get_base_uri()
        self._preview.update_content(html, base_uri)
        self._status_bar.update_stats(text)

    def _update_title(self, modified):
        filename = self.file_manager.get_display_name()
        prefix = "\u2022 " if modified else ""
        self._title_widget.set_title(f"{prefix}{filename}")

    def show_toast(self, message):
        """Show a non-blocking notification via Adw.ToastOverlay."""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    def update_recent_menu(self, recent_items):
        """Rebuild the Recent Files submenu from a list of (label, path) tuples."""
        self._recent_menu.remove_all()
        if not recent_items:
            self._recent_menu.append("(no recent files)", None)
            return
        for label, path in recent_items:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value(
                "win.open-path",
                GLib.Variant.new_string(path)
            )
            self._recent_menu.append_item(item)

    def toggle_find_bar(self):
        """Toggle the find bar visibility and focus the search entry."""
        mode = not self._find_bar.get_search_mode()
        self._find_bar.set_search_mode(mode)
        if mode:
            self._search_entry.grab_focus()

    def set_view_mode(self, mode):
        """Public API: switch to 'editor', 'split', or 'preview' mode.

        Called by app-level keyboard-shortcut actions defined in app.py.
        No-ops silently for unknown mode strings.
        """
        if mode not in ("editor", "split", "preview"):
            return
        self._view_mode = mode
        self._apply_view_mode()

    def request_close(self):
        """Initiate a graceful window close, honouring unsaved-changes check."""
        self.close()
