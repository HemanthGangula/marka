#!/usr/bin/env python3
"""MD Viewer — lightweight Linux-native Markdown viewer and editor.

This script is the direct-execution entry point (python3 main.py).
When installed via pip, the 'mdviewer' console script calls
mdviewer.app:main() directly instead.
"""

import sys
import os

# Ensure the project root is in the path when run directly from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mdviewer.app import main

if __name__ == "__main__":
    main()
