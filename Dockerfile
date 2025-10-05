# Use Ubuntu 20.04 for older glibc (2.31) for maximum compatibility
FROM ubuntu:20.04

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install basic build dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    git \
    build-essential \
    python3 \
    python3-pip \
    python3-dev \
    file \
    pkg-config \
    libgtk-3-0 \
    libgtk-3-dev \
    libwebkit2gtk-4.0-37 \
    libwebkit2gtk-4.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 (LTS) for frontend builds
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Install PyInstaller
RUN pip3 install pyinstaller requests pillow psutil py7zr vdf

# Install Go 1.23 (required for Wails)
RUN wget https://go.dev/dl/go1.23.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf go1.23.0.linux-amd64.tar.gz && \
    rm go1.23.0.linux-amd64.tar.gz

ENV PATH="/usr/local/go/bin:/root/go/bin:${PATH}"
ENV GOPATH="/root/go"

# Install Wails
RUN go install github.com/wailsapp/wails/v2/cmd/wails@latest

# Set CPU compatibility for Go builds
ENV GOAMD64=v1

# Set working directory
WORKDIR /workspace

# Default command
CMD ["/bin/bash"]

