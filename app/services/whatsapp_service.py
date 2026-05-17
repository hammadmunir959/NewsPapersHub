"""
WhatsApp delivery service using neonize.

neonize is a pure-Python WhatsApp library (bindings for the whatsmeow Go library).
Session is stored in NEONIZE_SESSION_PATH (default: neonize_session.sqlite3).

FIRST-TIME SETUP:
    Run `newshub-auth` or `python scripts/whatsapp_register.py` once to link your WhatsApp account.
    Scan the QR code with WhatsApp → Settings → Linked Devices → Link a Device.
    After that, all cron runs use the saved session automatically.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import select

from app.core.config import NEONIZE_SESSION_PATH, setup_logger
from app.core.database import AsyncSessionLocal
from app.models.database_models import Subscriber

logger = setup_logger(__name__)


# ── Neonize client factory ───────────────────────────────────────────────────

def _build_client():
    """Create a neonize NewClient using the configured session path."""
    from neonize.client import NewClient
    return NewClient(str(NEONIZE_SESSION_PATH))


from app.utils import normalize_jid


# ── Core send function (synchronous / blocking) ──────────────────────────────

def _send_document_sync(to: str, pdf_path: str, caption: str = "") -> bool:
    """
    Blocking: connect, send a PDF document to one number, disconnect.
    Intended to be called via asyncio.run_in_executor from async code.

    Args:
        to: Phone number string (e.g. '923001234567' or '+92 300 1234567')
        pdf_path: Absolute path to the PDF file to send.
        caption: Optional caption/text message accompanying the document.

    Returns:
        True on success, False on failure.
    """
    from neonize.client import NewClient
    from neonize.utils.jid import build_jid
    from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import (
        Message, DocumentMessage
    )
    from neonize.utils.enum import MediaType
    from neonize.events import ConnectedEv
    import threading

    path = Path(pdf_path)
    if not path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return False

    client = _build_client()
    jid = build_jid(normalize_jid(to))
    
    connected_event = threading.Event()
    
    @client.event(ConnectedEv)
    def on_connected(_c, _ev):
        connected_event.set()

    # neonize connect() blocks, so run it in a thread
    t = threading.Thread(target=client.connect, daemon=True)
    t.start()

    try:
        # Wait up to 15 seconds to connect
        if not connected_event.wait(timeout=15.0):
            logger.error(f"✗ Timeout connecting to WhatsApp for {to}")
            return False

        pdf_bytes = path.read_bytes()
        upload = client.upload(pdf_bytes, MediaType.MediaDocument)

        client.send_message(
            jid,
            Message(
                documentMessage=DocumentMessage(
                    URL=upload.url,
                    directPath=upload.DirectPath,
                    mediaKey=upload.MediaKey,
                    mimetype="application/pdf",
                    fileName=path.name,
                    caption=caption,
                    fileSHA256=upload.FileSHA256,
                    fileLength=upload.FileLength,
                    fileEncSHA256=upload.FileEncSHA256,
                )
            )
        )
        logger.info(f"✓ Sent to {to}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to send to {to}: {e}")
        return False
    finally:
        try:
            client.disconnect()
        except:
            pass


# ── Public async API ─────────────────────────────────────────────────────────

_whatsapp_lock = asyncio.Lock()

async def send_to_subscribers(pdf_path: str, caption: str = "") -> None:
    """
    Fetch all active subscribers from the database and broadcast the PDF.

    Used by:
      - The cron scheduler (automatic nightly delivery)
      - The /api/v1/whatsapp/broadcast REST endpoint (manual trigger)

    Args:
        pdf_path: Absolute path to the PDF file.
        caption:  Caption text. Supports {name} placeholder for personalization.
    """
    async with _whatsapp_lock:
        # Fetch active subscribers
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscriber.phone_number, Subscriber.full_name)
                .where(Subscriber.is_active == 1)
            )
            subscribers = result.all()

        if not subscribers:
            logger.warning("No active subscribers found. Skipping broadcast.")
            return

        logger.info(f"Broadcasting to {len(subscribers)} subscriber(s)...")
        loop = asyncio.get_running_loop()

        success_count = 0
        for phone, name in subscribers:
            personalized = caption.format(name=name or "there")
            success = await loop.run_in_executor(
                None, _send_document_sync, phone, pdf_path, personalized
            )
            if not success:
                logger.warning(f"Delivery failed for {phone} — continuing with next.")
            else:
                success_count += 1
            # Brief pause to respect WhatsApp rate limits
            await asyncio.sleep(2)

        logger.info("Broadcast complete.")
        if success_count == 0:
            raise RuntimeError("WhatsApp broadcast failed: No messages were delivered successfully.")


async def send_to_number(to: str, pdf_path: str, caption: str = "") -> bool:
    """
    Send a PDF to a single phone number.

    Used by the /api/v1/whatsapp/send-media REST endpoint.

    Args:
        to: Phone number string.
        pdf_path: Absolute path to the PDF file.
        caption: Optional caption text.

    Returns:
        True on success, False on failure.
    """
    async with _whatsapp_lock:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _send_document_sync, to, pdf_path, caption)
