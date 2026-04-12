from pydantic import BaseModel
from typing import Optional
from enum import Enum
from app.core.config import SUPPORTED_NEWSPAPERS, SUPPORTED_METHODS


# Dynamically create Enums from config
# This ensures thatSwagger UI dropdowns stay in sync with our supported list
ScrapeMethod = Enum(
    "ScrapeMethod", 
    {m.upper().replace("-", "_"): m for m in SUPPORTED_METHODS}, 
    type=str
)

NewspaperName = Enum(
    "NewspaperName", 
    {n.upper().replace("-", "_"): n for n in SUPPORTED_NEWSPAPERS}, 
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
