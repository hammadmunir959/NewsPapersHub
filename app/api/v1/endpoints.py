
from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from app.core.config import SUPPORTED_NEWSPAPERS
from app.services.newspaper_service import NewspaperService
from app.models.schemas import (
    PaperSuccessResponse, 
    PaperErrorResponse, 
    NewspaperName, 
    ScrapeMethod
)

router = APIRouter()


@router.get(
    "/get-paper/{newspaper}/{date_str}",
    response_model=PaperSuccessResponse,
    responses={
        400: {"model": PaperErrorResponse},
        404: {"model": PaperErrorResponse},
        500: {"model": PaperErrorResponse},
    },
)
async def get_paper(
    newspaper: NewspaperName = Path(..., description="Name of the newspaper"),
    date_str: str = Path(..., description="Date in YYYY-MM-DD format"),
    method: ScrapeMethod = Query(ScrapeMethod.EPAPER, description="Scrape method"),
):
    """
    Generate or retrieve a newspaper PDF.
    This is a synchronous endpoint that will block until the PDF is completely generated.
    """
    # 1. Validate Input
    if newspaper not in SUPPORTED_NEWSPAPERS:
        return JSONResponse(
            status_code=400,
            content=PaperErrorResponse(
                error="Unsupported newspaper",
                detail=f"Currently supported: {', '.join(SUPPORTED_NEWSPAPERS)}",
            ).model_dump(),
        )

    try:
        NewspaperService.validate_date(date_str)
    except ValueError as e:
        return JSONResponse(
            status_code=400,
            content=PaperErrorResponse(
                error="Invalid date", detail=str(e)
            ).model_dump(),
        )

    # 2. Process Newspaper
    try:
        result = await NewspaperService.process(newspaper, date_str, method)
        return result
    except ValueError as e:
         return JSONResponse(
            status_code=404,
            content=PaperErrorResponse(
                error="Not found", detail=str(e)
            ).model_dump(),
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=PaperErrorResponse(
                error="Internal server error", detail=str(e)
            ).model_dump(),
        )
