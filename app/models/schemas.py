from pydantic import BaseModel
from typing import Optional
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


class PaperSuccessResponse(BaseModel):
    status: str = "success"
    message: str
    newspaper: str
    date: str
    file_name: str
    saved_at: str
    pages: int
    size_mb: float


class PaperErrorResponse(BaseModel):
    status: str = "error"
    error: str
    detail: Optional[str] = None

class TaskState(str, Enum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    DOWNLOADING = "downloading"
    BUILDING_PDF = "building_pdf"
    COMPLETED = "completed"
    ERROR = "error"

class TaskResponse(BaseModel):
    status: str = "started"
    message: str
    task_id: str

class TaskProgressResponse(BaseModel):
    task_id: str
    state: TaskState
    percentage: int
    message: str
    result: Optional[list] = None
