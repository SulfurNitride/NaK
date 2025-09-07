#!/usr/bin/env python3
"""
NaK CLI - Simple command line interface for testing
"""
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
