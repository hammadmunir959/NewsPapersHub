from fastapi import APIRouter, HTTPException, Path, Query
from typing import List, Optional
from app.services.thenews_service import TheNewsService
from app.models.schemas import PaperSuccessResponse, CityName
from app.utils.date_utils import validate_date

router = APIRouter(prefix="/thenews")

@router.get("/{date_str}", response_model=List[PaperSuccessResponse])
async def download_thenews_paper(
    date_str: str = Path(..., description="Date in YYYY-MM-DD format"),
    cities: Optional[List[CityName]] = Query(
        None, 
        description="List of cities to download PDFs for.",
        alias="city"
    )
):
    """Download The News newspaper PDF for a specific date and city/cities."""
    try:
        validate_date(date_str)
        # Convert enum to string list
        city_list = [c.value for c in cities] if cities else None
        
        result = await TheNewsService.process(date_str, city_list)
        if not result:
             raise HTTPException(status_code=404, detail="No PDFs found for the given date and cities.")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
