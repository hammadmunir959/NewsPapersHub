#!/usr/bin/env python3
"""
NewsPapersHub Backend Service Entry Point.

This script runs the FastAPI backend as a standalone service.
It is designed to be used either:
  - Directly: python service_entry.py
  - As a Snap daemon: snap run newspapershub.backend
  - Via systemd: systemctl --user start newspapershub-backend
"""

import os
import sys
import uvicorn

# Ensure the project root is on the Python path
if getattr(sys, 'frozen', False):
    # Running as a bundle (PyInstaller)
    PROJECT_ROOT = os.path.dirname(sys.executable)
    # The app source is in _MEIPASS
    sys.path.insert(0, sys._MEIPASS)
else:
    # Running as a script
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, PROJECT_ROOT)

# Load environment
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from app.main import app

SERVICE_HOST = "127.0.0.1"
SERVICE_PORT = 8765

if __name__ == "__main__":
    print(f"[NewsPapersHub] Starting backend on {SERVICE_HOST}:{SERVICE_PORT}")
    uvicorn.run(
        app,
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        log_level="info",
    )
