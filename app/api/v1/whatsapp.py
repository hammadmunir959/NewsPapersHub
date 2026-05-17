from fastapi import APIRouter, BackgroundTasks
from app.schemas.schemas import MediaRequest, BroadcastRequest
from app.services import whatsapp_service

router = APIRouter()


@router.post("/send-media")
async def send_media(request: MediaRequest, background_tasks: BackgroundTasks):
    """
    Send a PDF (or any media file) with an optional caption to a specific WhatsApp number.
    """
    background_tasks.add_task(
        whatsapp_service.send_to_number,
        to=request.to,
        pdf_path=request.media_path,
        caption=request.caption or "",
    )
    return {"status": "queued", "message": f"Media delivery queued for {request.to}"}


@router.post("/broadcast")
async def broadcast_to_subscribers(request: BroadcastRequest, background_tasks: BackgroundTasks):
    """
    Broadcast a PDF to ALL active subscribers in the database.
    Supports {name} placeholder in the caption for personalization.
    """
    background_tasks.add_task(
        whatsapp_service.send_to_subscribers,
        pdf_path=request.media_path,
        caption=request.text or "",
    )
    return {"status": "queued", "message": "Broadcast queued for all active subscribers"}
