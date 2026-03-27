.PHONY: run venv install uninstall clean deps

PYTHON      := python3
VENV_DIR    := venv
VENV_PYTHON := $(VENV_DIR)/bin/python

## Run the app directly (no venv needed if system deps are present)
run:
	$(PYTHON) main.py

## Run with a specific file
run-file:
	$(PYTHON) main.py $(FILE)

## Create venv with system site-packages (required for PyGObject)
venv:
	$(PYTHON) -m venv $(VENV_DIR) --system-site-packages
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install Markdown pygments
	@echo "Venv ready. Activate with: source $(VENV_DIR)/bin/activate"
	@echo "Then run: python main.py"

## Install system dependencies (Ubuntu/Debian)
deps:
	sudo apt install -y \
		python3-gi \
		gir1.2-gtk-4.0 \
		gir1.2-adw-1 \
		gir1.2-webkit-6.0 \
		gir1.2-gtksource-5
	pip3 install --user Markdown pygments

## Install to ~/.local
install:
	bash install.sh

## Remove installation
uninstall:
	rm -rf $$HOME/.local/share/marka
	rm -f  $$HOME/.local/bin/marka
	rm -f  $$HOME/.local/share/applications/marka.desktop
	update-desktop-database $$HOME/.local/share/applications 2>/dev/null || true
	@echo "Marka uninstalled."

## Remove .pyc files and __pycache__
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

## Show help
help:
	@echo "Marka — Makefile targets:"
	@echo "  make run        Run the app"
	@echo "  make venv       Create Python venv"
	@echo "  make deps       Install system dependencies (Ubuntu)"
	@echo "  make install    Install to ~/.local"
	@echo "  make uninstall  Remove installation"
	@echo "  make clean      Remove build artifacts"
