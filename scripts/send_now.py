"""
Instantly generate and broadcast the newspapers (both Dawn and The News) to all active subscribers.

This script bypasses the 7 PM scheduler logic and forces an immediate
PDF generation and WhatsApp broadcast.

Usage:
    uv run python scripts/send_now.py           # Sends today's edition
    uv run python scripts/send_now.py 2026-05-16 # Sends a specific date
"""

import sys
import asyncio
import os
from datetime import datetime

# Allow running from project root or scripts/ directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import setup_logger
from app.services.scheduler_service import execute_delivery_pipeline

logger = setup_logger("send_now")


async def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    logger.info(f"=== INSTANT MANUAL DELIVERY: {date_str} for both newspapers ===")

    try:
        await execute_delivery_pipeline(date_str, ["dawn", "thenews"])
        logger.info("=== INSTANT DELIVERY PROCESS FINISHED ===")
    except Exception as e:
        logger.error(f"Instant manual delivery failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
