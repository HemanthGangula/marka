"""Unit tests for config load/save round-trip logic.

These tests exercise the JSON serialisation, defaults merging, and type
validation logic from marka/config.py WITHOUT importing GLib/GTK.
We achieve this by monkey-patching the module-level constants
(_CONFIG_DIR, _CONFIG_FILE) after bypassing the gi import via a thin
mock, so the test suite runs in a headless environment with no display.

Run with:
    python3 -m unittest tests.test_config -v
"""

import sys
import os
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Bootstrap: provide a minimal stub for the 'gi' import chain so that
# marka.config can be imported without a live GTK session.
# ---------------------------------------------------------------------------

# Build a mock gi module tree that satisfies:
#   import gi
#   gi.require_version("GLib", "2.0")
#   from gi.repository import GLib
#   GLib.get_user_config_dir()

_fake_glib = MagicMock()
_fake_glib.get_user_config_dir.return_value = "/tmp/_marka_test_config_dir"

_fake_repository = MagicMock()
_fake_repository.GLib = _fake_glib

_fake_gi = MagicMock()
_fake_gi.repository = _fake_repository

# Inject the stubs before importing the module under test.
sys.modules.setdefault("gi", _fake_gi)
sys.modules.setdefault("gi.repository", _fake_repository)

# Allow running from repo root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import marka.config as config_module  # noqa: E402 — must come after mocks


class TestConfigRoundTrip(unittest.TestCase):
    """Tests for config.save() / config.load() round-trip behaviour."""

    def setUp(self):
        # Use a fresh temporary directory for each test so tests are isolated.
        self._tmpdir = tempfile.mkdtemp()
        self._config_file = os.path.join(self._tmpdir, "settings.json")
        # Patch the module-level constants to point at our temp directory.
        self._dir_patcher = patch.object(config_module, "_CONFIG_DIR", self._tmpdir)
        self._file_patcher = patch.object(config_module, "_CONFIG_FILE", self._config_file)
        self._dir_patcher.start()
        self._file_patcher.start()

    def tearDown(self):
        self._file_patcher.stop()
        self._dir_patcher.stop()
        # Clean up temp files.
        if os.path.isfile(self._config_file):
            os.unlink(self._config_file)
        os.rmdir(self._tmpdir)

    # ── Happy-path round-trip ────────────────────────────────────────────

    def test_save_and_load_round_trip(self):
        """Values saved must be returned unchanged on the next load()."""
        data = {
            "window_width": 1200,
            "window_height": 800,
            "window_x": 100,
            "window_y": 50,
            "paned_position": 500,
            "last_file": "/home/user/notes.md",
        }
        config_module.save(data)
        loaded = config_module.load()
        self.assertEqual(loaded["window_width"], 1200)
        self.assertEqual(loaded["window_height"], 800)
        self.assertEqual(loaded["window_x"], 100)
        self.assertEqual(loaded["window_y"], 50)
        self.assertEqual(loaded["paned_position"], 500)
        self.assertEqual(loaded["last_file"], "/home/user/notes.md")

    def test_save_creates_file(self):
        config_module.save({"window_width": 900})
        self.assertTrue(os.path.isfile(self._config_file))

    def test_save_writes_valid_json(self):
        config_module.save({"window_width": 1024, "last_file": None})
        with open(self._config_file, "r", encoding="utf-8") as fh:
            parsed = json.load(fh)
        self.assertEqual(parsed["window_width"], 1024)
        self.assertIsNone(parsed["last_file"])

    # ── Defaults returned when no file ───────────────────────────────────

    def test_load_returns_defaults_when_no_file(self):
        # No file has been saved yet.
        result = config_module.load()
        defaults = dict(config_module._DEFAULTS)
        for key, value in defaults.items():
            self.assertIn(key, result)
            self.assertEqual(result[key], value,
                             msg=f"Default for '{key}' mismatch")

    def test_load_merges_partial_config_with_defaults(self):
        """A config with only some keys must still return all default keys."""
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_width": 1920}, fh)
        result = config_module.load()
        # Saved key is present.
        self.assertEqual(result["window_width"], 1920)
        # Default keys not in file are filled in.
        self.assertIn("window_height", result)
        self.assertEqual(result["window_height"], config_module._DEFAULTS["window_height"])

    # ── Corrupt / invalid JSON ────────────────────────────────────────────

    def test_corrupt_json_returns_defaults(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            fh.write("{ this is not json }")
        result = config_module.load()
        defaults = dict(config_module._DEFAULTS)
        for key, value in defaults.items():
            self.assertEqual(result[key], value,
                             msg=f"Key '{key}' should be default after corrupt JSON")

    def test_truncated_json_returns_defaults(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            fh.write('{"window_width": 1')  # truncated
        result = config_module.load()
        self.assertEqual(result["window_width"], config_module._DEFAULTS["window_width"])

    def test_json_array_instead_of_object_returns_defaults(self):
        """Top-level JSON array (not a dict) must trigger fallback to defaults."""
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump([1, 2, 3], fh)
        result = config_module.load()
        self.assertEqual(result["window_width"], config_module._DEFAULTS["window_width"])

    # ── Type validation / coercion ────────────────────────────────────────

    def test_last_file_non_string_coerced_to_none(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"last_file": 12345}, fh)
        result = config_module.load()
        self.assertIsNone(result["last_file"])

    def test_last_file_list_coerced_to_none(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"last_file": ["/path/file.md"]}, fh)
        result = config_module.load()
        self.assertIsNone(result["last_file"])

    def test_window_width_string_replaced_with_default(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_width": "1200px"}, fh)
        result = config_module.load()
        self.assertEqual(result["window_width"], config_module._DEFAULTS["window_width"])

    def test_window_width_float_replaced_with_default(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_width": 1200.5}, fh)
        result = config_module.load()
        # JSON numbers without decimal are int in Python; 1200.5 is float
        # The validator checks isinstance(val, int) — float should be replaced.
        self.assertEqual(result["window_width"], config_module._DEFAULTS["window_width"])

    def test_window_width_clamped_minimum(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_width": 100}, fh)  # below 400 minimum
        result = config_module.load()
        self.assertEqual(result["window_width"], 400)

    def test_window_width_clamped_maximum(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_width": 9999}, fh)  # above 4000 maximum
        result = config_module.load()
        self.assertEqual(result["window_width"], 4000)

    def test_window_height_clamped(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"window_height": 50}, fh)  # below 400 minimum
        result = config_module.load()
        self.assertEqual(result["window_height"], 400)

    def test_paned_position_zero_normalised(self):
        """paned_position of 0 must be normalised to 0 (the 'use default' sentinel)."""
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"paned_position": 0}, fh)
        result = config_module.load()
        self.assertEqual(result["paned_position"], 0)

    def test_paned_position_negative_normalised(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"paned_position": -100}, fh)
        result = config_module.load()
        self.assertEqual(result["paned_position"], 0)

    def test_paned_position_string_normalised(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"paned_position": "500"}, fh)
        result = config_module.load()
        self.assertEqual(result["paned_position"], 0)

    def test_paned_position_valid_preserved(self):
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"paned_position": 450}, fh)
        result = config_module.load()
        self.assertEqual(result["paned_position"], 450)

    # ── Save is tolerant of OS errors ────────────────────────────────────

    def test_save_does_not_raise_on_unwritable_path(self):
        """config.save() must swallow OSError rather than propagate it."""
        with patch.object(config_module, "_CONFIG_FILE", "/root/no_permission/settings.json"):
            with patch.object(config_module, "_CONFIG_DIR", "/root/no_permission"):
                # Should not raise.
                try:
                    config_module.save({"window_width": 800})
                except OSError:
                    self.fail("config.save() raised OSError unexpectedly")

    # ── Extra keys in config file are passed through ──────────────────────

    def test_unknown_keys_passed_through(self):
        """Extra keys in the config file must not be silently discarded."""
        with open(self._config_file, "w", encoding="utf-8") as fh:
            json.dump({"future_feature": True, "window_width": 1000}, fh)
        result = config_module.load()
        # Known key merged correctly.
        self.assertEqual(result["window_width"], 1000)
        # Unknown key also present (update() does not filter unknown keys).
        self.assertIn("future_feature", result)


if __name__ == "__main__":
    unittest.main()
