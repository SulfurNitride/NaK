# NaK - Linux Modding Helper Makefile

.PHONY: all build clean install test help

# Default target
all: build

# Build the AppImage
build:
	@echo "Building NaK AppImage..."
	python3 build_appimage.py

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -f *.AppImage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Install dependencies
install-deps:
	@echo "Installing Python dependencies..."
	pip3 install -r requirements.txt

# Run tests (if any)
test:
	@echo "Running tests..."
	python3 -m pytest tests/ -v || echo "No tests found"

# Install appimagetool if not present
install-appimagetool:
	@echo "Installing appimagetool..."
	wget -O appimagetool-x86_64.AppImage https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
	chmod +x appimagetool-x86_64.AppImage
	sudo mv appimagetool-x86_64.AppImage /usr/local/bin/appimagetool

# Run the application in development mode
run:
	@echo "Running NaK in development mode..."
	python3 main.py

# Check dependencies
check-deps:
	@echo "Checking dependencies..."
	python3 main.py --check-deps

# Show version
version:
	@echo "NaK version:"
	python3 main.py --version

# Help
help:
	@echo "NaK - Linux Modding Helper Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  build              - Build the AppImage"
	@echo "  clean              - Clean build artifacts"
	@echo "  install-deps       - Install Python dependencies"
	@echo "  test               - Run tests"
	@echo "  install-appimagetool - Install appimagetool"
	@echo "  run                - Run in development mode"
	@echo "  check-deps         - Check dependencies"
	@echo "  version            - Show version"
	@echo "  help               - Show this help"
