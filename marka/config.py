"""Window state persistence — reads/writes $XDG_CONFIG_HOME/marka/settings.json.

Uses GLib.get_user_config_dir() so the path honours XDG_CONFIG_HOME rather
than hard-coding ~/.config.
"""

import json
import os

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

_CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "marka")
_CONFIG_FILE = os.path.join(_CONFIG_DIR, "settings.json")

_DEFAULTS = {
    "window_width": 1100,
    "window_height": 700,
    "window_x": -1,
    "window_y": -1,
    "paned_position": -1,
    "last_file": None,
}


def load() -> dict:
    """Return persisted settings merged with defaults.

    Returns a dict with all keys from _DEFAULTS, overridden by any values
    found in the on-disk JSON file.  Falls back to defaults silently on any
    I/O or parse error.
    """
    settings = dict(_DEFAULTS)
    if os.path.isfile(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                settings.update(data)
                # Type-validate individual keys to prevent malformed config
                # values from being used as file paths or window dimensions.

                # last_file must be a str or None
                lf = settings.get("last_file")
                if lf is not None and not isinstance(lf, str):
                    settings["last_file"] = None

                # window_width / window_height must be int, clamped 400–4000
                for dim in ("window_width", "window_height"):
                    val = settings.get(dim)
                    if not isinstance(val, int):
                        settings[dim] = _DEFAULTS[dim]
                    else:
                        settings[dim] = max(400, min(4000, val))

                # paned_position must be a positive int; 0 means "use default"
                pp = settings.get("paned_position")
                if not isinstance(pp, int) or pp <= 0:
                    settings["paned_position"] = 0

        except (OSError, json.JSONDecodeError):
            pass  # silently fall back to defaults
    return settings


def save(settings: dict) -> None:
    """Persist *settings* dict to disk, ignoring I/O errors."""
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump(settings, fh, indent=2)
    except OSError:
        pass
