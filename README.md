# Marka

A lightweight, native Linux Markdown viewer and editor built with GTK4 and libadwaita.
Renders Markdown in real time with GitHub-style typography, syntax-highlighted code blocks
via Pygments, and automatic light/dark theme support.

```
[Editor pane]  |  [Live preview pane]
               |
# Hello World  |  <h1>Hello World</h1> (rendered)
               |
**bold** text  |  <b>bold</b> text (rendered)
```

## Features

- Live split-pane preview with GitHub-style CSS
- Syntax highlighting via GtkSourceView 5 (plain-text fallback included)
- Full CommonMark support: tables, task lists, footnotes, fenced code, strikethrough
- Find in document (Ctrl+F)
- Zoom preview (Ctrl+= / Ctrl+-)
- Print preview (Ctrl+P)
- Export rendered document to HTML
- Drag-and-drop file opening
- Recent files history
- Persistent window geometry and last-opened file across sessions
- Respects system light/dark theme via libadwaita

## Installation

### pip (recommended for developers)

```bash
pip install marka
marka
```

### Ubuntu / Debian (PPA)

```bash
sudo add-apt-repository ppa:hemanth/marka
sudo apt update
sudo apt install marka
```

### Flatpak

```bash
flatpak install flathub io.github.hemanth.Marka
flatpak run io.github.hemanth.Marka
```

### Snap

```bash
sudo snap install marka
marka
```

### Manual / from source

```bash
git clone https://github.com/hemanth/marka.git
cd marka

# Install system dependencies (Ubuntu 24.04 Noble)
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 \
                 gir1.2-webkit-6.0 gir1.2-gtksource-5

# Install Python dependencies
pip install -r requirements.txt

# Run directly
python3 main.py

# Or install via pip in editable mode
pip install -e .
marka
```

## System Requirements

| Component | Minimum |
|-----------|---------|
| Python | 3.10 or later |
| GTK | 4.6 or later (4.10 recommended) |
| libadwaita | 1.x |
| WebKitGTK | 6.0 |
| GtkSourceView | 5 (optional, for editor syntax highlighting) |
| OS | Linux (X11 or Wayland) |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New file |
| Ctrl+O | Open file |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save As |
| Ctrl+W | Close window |
| Ctrl+F | Find in preview |
| Ctrl+= | Zoom in preview |
| Ctrl+- | Zoom out preview |
| Ctrl+0 | Reset zoom |
| Ctrl+P | Print |
| Ctrl+Shift+E | Export to HTML |
| F11 | Toggle fullscreen |

## Running Tests

```bash
python3 -m unittest discover -s tests -v
```

## Contributing

Bug reports and pull requests are welcome at
https://github.com/hemanth/marka

Please open an issue before submitting large changes.

## License

MIT License. Copyright (c) 2026 Hemanth.
See the [LICENSE](LICENSE) file for full text.
