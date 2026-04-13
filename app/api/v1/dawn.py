from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from app.services.dawn_service import DawnService
from app.models.schemas import PaperSuccessResponse, PaperErrorResponse
from app.utils.date_utils import validate_date

router = APIRouter(prefix="/dawn")

@router.get("/{date_str}", response_model=PaperSuccessResponse)
async def get_dawn_paper(
    date_str: str = Path(..., description="Date in YYYY-MM-DD format")
):
    """Generate or retrieve Dawn newspaper PDF for a specific date."""
    try:
        validate_date(date_str)
        result = await DawnService.process(date_str)
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
