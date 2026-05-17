#!/usr/bin/env python3
"""
Intelligent WhatsApp authentication helper for NewspapersHub.
Detects if running inside Docker or locally, and links the session seamlessly.

Usage:
    newshub-auth
    OR
    python scripts/whatsapp_register.py
"""

import os
import sys
import shutil
import subprocess

# Terminal Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def is_container_running(name: str) -> bool:
    """Check if a Docker container with the specified name is currently running."""
    if not shutil.which("docker"):
        return False
    try:
        output = subprocess.check_output(
            ["docker", "ps", "--filter", f"name={name}", "--format", "{{.Names}}"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        lines = [line.strip() for line in output.split("\n") if line.strip()]
        return name in lines
    except Exception:
        return False

def run_local_auth():
    """Execute the core Neonize client connection and pairing QR generator."""
    # Allow running from project root or scripts/ directory
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")))
    
    from app.core.config import NEONIZE_SESSION_PATH, setup_logger
    logger = setup_logger("whatsapp_register")
    
    from neonize.client import NewClient
    from neonize.events import ConnectedEv

    session_path = str(NEONIZE_SESSION_PATH)
    logger.info(f"Starting WhatsApp auth. Session will be saved to: {session_path}")

    if os.path.exists(session_path):
        logger.info("Existing session found. Connecting to verify...")
    else:
        logger.info("No session found. A QR code will appear — scan it with WhatsApp.")

    client = NewClient(session_path)

    @client.event(ConnectedEv)
    def on_connected(_client: NewClient, _event: ConnectedEv):
        logger.info("✓ Connected! WhatsApp session is active.")
        logger.info(f"Session saved to: {session_path}")
        logger.info("You can now press Ctrl+C to exit. The cron scheduler will use this session.")

    try:
        client.connect()
    except KeyboardInterrupt:
        logger.info("Auth script exited.")

def main():
    # Check if running inside the Docker container
    is_inside_docker = os.path.exists("/.dockerenv")
    
    if not is_inside_docker:
        project_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
        venv_python = os.path.join(project_dir, ".venv", "bin", "python3")
        if sys.executable != venv_python and os.path.exists(venv_python):
            os.execv(venv_python, [venv_python] + sys.argv)
            
    if is_inside_docker:
        # Directly run auth if we are already inside the container
        run_local_auth()
        return

    # If running on the host system, check if container is active
    container_name = "newspapershub_system"
    print(f"\n{BOLD}{CYAN}=== NewspapersHub WhatsApp Linker ==={RESET}")
    
    if is_container_running(container_name):
        print(f"{GREEN}✔ Detected running Docker container: '{container_name}'{RESET}")
        print(f"{CYAN}Initializing interactive container bridge for QR scan...{RESET}\n")
        try:
            # Attach to the running docker container and trigger auth script inside it
            subprocess.run([
                "docker", "exec", "-it", container_name, "uv", "run", "python", "scripts/whatsapp_register.py"
            ])
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Bridge closed by user.{RESET}")
    else:
        print(f"{YELLOW}⚠ Docker container '{container_name}' is not active.{RESET}")
        print(f"{CYAN}Initializing local environment linking...{RESET}\n")
        run_local_auth()

if __name__ == "__main__":
    main()
