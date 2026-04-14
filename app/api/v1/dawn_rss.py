from fastapi import APIRouter, HTTPException, Path
from app.services.dawn_rss_service import DawnRSSService
from app.models.schemas import PaperSuccessResponse
from app.utils.date_utils import validate_date

router = APIRouter(prefix="/dawn/rss")

@router.get("/{date_str}", response_model=PaperSuccessResponse)
async def get_dawn_rss_edition(
    date_str: str = Path(..., description="Date in YYYY-MM-DD format")
):
    """Generate Dawn newspaper PDF from RSS feeds for a specific date."""
    try:
        validate_date(date_str)
        result = await DawnRSSService.process(date_str)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
