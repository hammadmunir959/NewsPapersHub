from fastapi import APIRouter, HTTPException, Path
from typing import List

from app.services.dawn_service import DawnService
from app.models.schemas import PaperSuccessResponse
from app.utils.date_utils import validate_date

router = APIRouter(prefix="/dawn")


@router.get("/{date_str}", response_model=List[PaperSuccessResponse])
async def get_dawn_paper(
    date_str: str = Path(..., description="Date in YYYY-MM-DD format")
):
    """
    Retrieve Dawn newspaper PDF metadata for a given date.
    Uses the RSS-based generation pipeline.
    """
    try:
        validate_date(date_str)

        result = await DawnService.process(date_str)

        if not result:
            raise HTTPException(
                status_code=404,
                detail="No Dawn PDF found for the given date."
            )

        return result

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))