# GitHub Actions Setup

This directory contains GitHub Actions workflows for automatically building the NaK AppImage.

## Quick Start

1. **Push your code to GitHub**
2. **Go to Actions tab** - The build will run automatically
3. **Download the AppImage** from the workflow artifacts

## What Happens Automatically

- ✅ **Every push**: Builds AppImage on Ubuntu 20.04
- ✅ **Every release**: Builds and attaches AppImage to the release
- ✅ **Manual trigger**: Can trigger builds anytime

## Why Use GitHub Actions?

Building on GitHub Actions (Ubuntu 20.04) gives you an AppImage that works on:
- Ubuntu 20.04 and newer
- Debian 11 and newer  
- Fedora 32 and newer
- Most modern Linux distros

Building on your local machine (glibc 2.42) would only work on very recent systems.

## Files

- `workflows/build-appimage.yml` - The build workflow
- `BUILDING.md` - Detailed build instructions

## See Also

Read [BUILDING.md](BUILDING.md) for:
- How to build locally
- Compatibility information
- Troubleshooting
- Development workflow

