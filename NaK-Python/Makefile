.PHONY: install run build clean appimage help

# Default target
all: help

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	pip3 install -r requirements.txt

# Run the application
run: install
	@echo "Starting NaK - Linux Modding Helper..."
	python3 main.py

# Build the application (create executable)
build: install
	@echo "Building NaK application..."
	@echo "Note: This is a Python application, no compilation needed."
	@echo "Use 'make run' to start the application."

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -f *.AppImage
	rm -rf __pycache__/
	rm -rf src/__pycache__/
	rm -rf src/*/__pycache__/
	rm -rf src/*/*/__pycache__/
	@echo "Clean complete"

# Build AppImage
appimage: install
	@echo "Building AppImage package..."
	python3 build_appimage.py

# Install system-wide (optional)
install-system: install
	@echo "Installing system-wide..."
	sudo cp main.py /usr/local/bin/nak
	sudo chmod +x /usr/local/bin/nak
	@echo "NaK installed to /usr/local/bin/nak"

# Uninstall system-wide
uninstall-system:
	@echo "Uninstalling system-wide..."
	sudo rm -f /usr/local/bin/nak
	@echo "NaK uninstalled from system"

# Show help
help:
	@echo "NaK - Linux Modding Helper (Python Version)"
	@echo ""
	@echo "Available targets:"
	@echo "  install         - Install Python dependencies"
	@echo "  run            - Run the application"
	@echo "  build          - Build the application (no compilation needed)"
	@echo "  clean          - Clean build artifacts"
	@echo "  appimage       - Build AppImage package"
	@echo "  install-system - Install system-wide (optional)"
	@echo "  uninstall-system - Uninstall system-wide"
	@echo "  help           - Show this help message"
	@echo ""
	@echo "Examples:"
	@echo "  make install   # Install dependencies"
	@echo "  make run       # Run the application"
	@echo "  make appimage  # Build AppImage package"
