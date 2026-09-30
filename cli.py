#!/usr/bin/env python3
"""Root CLI entrypoint proxying to backend/cli.py"""
import sys
from pathlib import Path

# Insert backend directory
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from cli import main

if __name__ == "__main__":
    main()
