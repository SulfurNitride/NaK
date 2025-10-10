#!/bin/bash
# Test Flet UI locally before building AppImage

echo "Testing Flet UI locally..."
echo "============================================"
echo ""

# Try to find the right Python (prefer 3.14t if available)
if command -v python3.14t &> /dev/null; then
    PYTHON=python3.14t
elif command -v python3.14 &> /dev/null; then
    PYTHON=python3.14
else
    PYTHON=python3
fi

echo "Using: $PYTHON ($(${PYTHON} --version))"

# Check if flet is installed
if ! $PYTHON -c "import flet" 2>/dev/null; then
    echo "Installing flet..."
    $PYTHON -m pip install --user flet
fi

echo ""
echo "Starting Flet app..."
echo "Press Ctrl+C to stop"
echo ""

$PYTHON nak-flet/main.py