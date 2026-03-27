import gi

gi.require_version("Adw", "1")
from gi.repository import Adw


class ThemeManager:
    """Keeps editor and preview in sync with the system dark/light theme."""

    def __init__(self, editor, preview):
        self._editor = editor
        self._preview = preview
        self._renderer = None  # set later via set_renderer()

        self._style_manager = Adw.StyleManager.get_default()
        self._style_manager.connect("notify::dark", self._on_dark_changed)

        # Apply initial theme
        self._apply(self._style_manager.get_dark())

    def set_renderer(self, renderer):
        self._renderer = renderer
        # Reapply so preview gets correct pygments CSS
        self._apply(self._style_manager.get_dark())

    def _on_dark_changed(self, style_manager, _param):
        self._apply(style_manager.get_dark())

    def _apply(self, is_dark):
        self._editor.set_theme(is_dark)
        pygments_css = ""
        if self._renderer:
            pygments_css = self._renderer.get_pygments_css(is_dark)
        self._preview.set_theme(is_dark, pygments_css)

    @property
    def is_dark(self):
        return self._style_manager.get_dark()
