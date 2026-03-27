#!/usr/bin/env bash
# Marka install script — installs to ~/.local for the current user.
# Idempotent: safe to re-run on an existing installation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Honour XDG base-dir spec; fall back to standard defaults.
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"

INSTALL_DIR="$XDG_DATA_HOME/marka"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$XDG_DATA_HOME/applications"
METAINFO_DIR="$XDG_DATA_HOME/metainfo"
ICONS_DIR="$XDG_DATA_HOME/icons/hicolor/scalable/apps"

echo "=== Marka Installer ==="
echo ""

# ── Check / install system dependencies ──────────────────────────────────────
check_dep() {
    python3 -c "import gi; gi.require_version('$1', '$2'); from gi.repository import $1" 2>/dev/null
}

echo "Checking system dependencies..."

if ! check_dep Gtk 4.0; then
    echo "ERROR: GTK4 (python3-gi + gir1.2-gtk-4.0) not found."
    echo "  Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0"
    exit 1
fi

if ! check_dep Adw 1; then
    echo "ERROR: libadwaita (gir1.2-adw-1) not found."
    echo "  Ubuntu: sudo apt install gir1.2-adw-1"
    exit 1
fi

if ! check_dep WebKit 6.0; then
    echo "ERROR: WebKitGTK (gir1.2-webkit-6.0) not found."
    echo "  Ubuntu: sudo apt install gir1.2-webkit-6.0"
    exit 1
fi

if ! check_dep GtkSource 5; then
    echo "NOTE: GtkSourceView 5 not found — syntax highlighting will use fallback."
    echo "  Install for best experience: sudo apt install gir1.2-gtksource-5"
    echo ""
fi

# ── Check python-markdown and pygments ───────────────────────────────────────
missing_py_deps=()
python3 -c "import markdown" 2>/dev/null || missing_py_deps+=("Markdown")
python3 -c "import pygments" 2>/dev/null || missing_py_deps+=("pygments")

if [[ ${#missing_py_deps[@]} -gt 0 ]]; then
    echo "Installing Python dependencies: ${missing_py_deps[*]} ..."
    pip3 install --user "${missing_py_deps[@]}"
fi

# ── Copy application files (idempotent) ───────────────────────────────────────
echo "Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
# Use cp -a to preserve timestamps; overwrite existing files without deleting
# the directory first so an already-running instance is not disrupted.
cp -a "$SCRIPT_DIR/main.py" "$INSTALL_DIR/"
cp -a "$SCRIPT_DIR/marka" "$INSTALL_DIR/"

# ── Create launcher script ────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/marka" << LAUNCHER
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/main.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/marka"

# ── Install .desktop file ─────────────────────────────────────────────────────
mkdir -p "$APPS_DIR"
if [[ -f "$SCRIPT_DIR/marka.desktop" ]]; then
    sed "s|/opt/marka|$INSTALL_DIR|g" "$SCRIPT_DIR/marka.desktop" \
        > "$APPS_DIR/io.github.HemanthGangula.Marka.desktop"
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
else
    echo "WARNING: marka.desktop not found — skipping desktop entry."
fi

# ── Install AppStream metainfo ────────────────────────────────────────────────
if [[ -f "$SCRIPT_DIR/data/io.github.HemanthGangula.Marka.metainfo.xml" ]]; then
    mkdir -p "$METAINFO_DIR"
    cp "$SCRIPT_DIR/data/io.github.HemanthGangula.Marka.metainfo.xml" \
       "$METAINFO_DIR/io.github.HemanthGangula.Marka.metainfo.xml"
    echo "AppStream metainfo installed to $METAINFO_DIR"
else
    echo "NOTE: data/io.github.HemanthGangula.Marka.metainfo.xml not found — skipping metainfo."
fi

# ── Register MIME type ────────────────────────────────────────────────────────
xdg-mime default io.github.HemanthGangula.Marka.desktop text/markdown 2>/dev/null || true
xdg-mime default io.github.HemanthGangula.Marka.desktop text/x-markdown 2>/dev/null || true

echo ""
echo "=== Installation complete! ==="
echo ""
echo "Run from terminal:  marka [file.md]"
echo "Or find 'Marka' in your application launcher."
echo ""
echo "To uninstall:  make uninstall"
