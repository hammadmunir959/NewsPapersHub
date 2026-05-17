#!/usr/bin/env python3
"""
CLI helper to view, parse, and render the latest NewspapersHub structured logs.

Usage:
    newshub-logs [count]
    e.g. newshub-logs 20
"""

import os
import sys
import json

# Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GRAY = "\033[90m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BLUE = "\033[34m"
CYAN = "\033[36m"

LEVEL_COLORS = {
    "info": GREEN,
    "warning": YELLOW,
    "error": RED,
    "critical": RED + BOLD,
    "debug": GRAY,
}

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, "logs", "newspapershub.log")

def get_last_n_lines(file_path: str, n: int) -> list[str]:
    """Read the last N lines of a file efficiently."""
    if not os.path.exists(file_path):
        return []
    
    with open(file_path, "r", encoding="utf-8") as f:
        # Simple and robust line reading
        lines = f.readlines()
        return lines[-n:]

def format_log_line(line: str) -> str:
    """Parse JSON log line and return a beautifully colored human-readable string."""
    line = line.strip()
    if not line:
        return ""
    
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Fallback for non-JSON lines
        return f"{GRAY}{line}{RESET}"

    # Extract standard fields
    timestamp = data.pop("timestamp", "unknown-time")
    level = data.pop("level", "info").lower()
    event = data.pop("event", "")
    logger_name = data.pop("logger", "app")

    # Determine level color
    lvl_color = LEVEL_COLORS.get(level, RESET)
    level_tag = f"{lvl_color}{level.upper():<7}{RESET}"
    
    # Format standard header
    header = f"{GRAY}{timestamp}{RESET} - {CYAN}{logger_name}{RESET} - [{level_tag}]"
    
    # Format extra context parameters
    context = ""
    if data:
        context_items = [f"{BLUE}{k}{RESET}={GRAY}{v}{RESET}" for k, v in data.items()]
        context = f" {GRAY}({RESET}{', '.join(context_items)}{GRAY}){RESET}"

    return f"{header} - {BOLD}{event}{RESET}{context}"

def main():
    # Parse count argument (default to 15)
    count = 15
    if len(sys.argv) > 1:
        try:
            count = int(sys.argv[1])
        except ValueError:
            pass

    if not os.path.exists(LOG_FILE_PATH):
        print(f"{YELLOW}No log file found at {LOG_FILE_PATH} yet. Start the application or run scripts to generate logs!{RESET}")
        return

    print(f"{BOLD}{CYAN}=== Showing Latest {count} Structured Logs ==={RESET}\n")
    
    lines = get_last_n_lines(LOG_FILE_PATH, count)
    for line in lines:
        formatted = format_log_line(line)
        if formatted:
            print(formatted)

if __name__ == "__main__":
    main()
