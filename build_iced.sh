#!/bin/bash

echo "Building NaK GUI with Iced..."

# Set up Rust environment
export RUSTUP_HOME="/home/luke/.rustup"
export CARGO_HOME="/home/luke/.cargo"
export PATH="/home/luke/.cargo/bin:$PATH"

# Try different approaches to bypass proxy
echo "Attempting direct build..."

# Method 1: Use system Rust if available
if command -v /usr/bin/cargo &> /dev/null; then
    echo "Using system Cargo..."
    /usr/bin/cargo build --release
    exit $?
fi

# Method 2: Use cargo directly with explicit environment
echo "Using installed Cargo..."
RUSTUP_HOME=/home/luke/.rustup CARGO_HOME=/home/luke/.cargo /home/luke/.cargo/bin/cargo build --release

echo "Build completed!"
