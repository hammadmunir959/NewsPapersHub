from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Any
from enum import Enum


from app.core.config import SUPPORTED_NEWSPAPERS, THENEWS_CITIES


NewspaperName = Enum(
    "NewspaperName", 
    {n.upper().replace("-", "_"): n for n in SUPPORTED_NEWSPAPERS}, 
    type=str
)

CityName = Enum(
    "CityName",
    {c.upper(): c for c in THENEWS_CITIES},
    type=str
)


class TaskState(str, Enum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    DOWNLOADING = "downloading"
    BUILDING_PDF = "building_pdf"
    COMPLETED = "completed"
    ERROR = "error"

class PaperSuccessResponse(BaseModel):
    newspaper: str
    date: str
    file_name: str
    path: str  # Renamed from saved_at
    pages: int
    size_mb: float

class TaskProgressResponse(BaseModel):
    id: str         # Renamed from task_id
    state: TaskState
    progress: int    # Renamed from percentage
    message: str
    result: Optional[Any] = None
    broadcast_status: Optional[str] = None
    broadcast_at: Optional[datetime] = None
    broadcast_error: Optional[str] = None

class SubscriberBase(BaseModel):
    phone_number: str
    full_name: Optional[str] = None
    is_active: int = 1

class SubscriberCreate(SubscriberBase):
    pass

class SubscriberUpdate(BaseModel):
    phone_number: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[int] = None

class SubscriberResponse(SubscriberBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MediaRequest(BaseModel):
    to: str
    media_path: str
    caption: Optional[str] = None

class BroadcastRequest(BaseModel):
    media_path: str
    text: Optional[str] = None  # Caption text; supports {name} placeholder
