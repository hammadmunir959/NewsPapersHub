from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from typing import List, Optional
import uuid
from app.services.thenews_service import TheNewsService
from app.models.schemas import PaperSuccessResponse, CityName, TaskResponse
from app.utils.date_utils import validate_date
from app.core.task_manager import task_manager

router = APIRouter(prefix="/thenews")

@router.get("/{date_str}", response_model=TaskResponse)
async def download_thenews_paper(
    background_tasks: BackgroundTasks,
    date_str: str = Path(..., description="Date in YYYY-MM-DD format"),
    cities: Optional[List[CityName]] = Query(
        None, 
        description="List of cities to download PDFs for.",
        alias="city"
    )
):
    """Start generation of The News newspaper PDF for a specific date and city/cities in background."""
    try:
        validate_date(date_str)
        # Convert enum to string list
        city_list = [c.value for c in cities] if cities else None
        
        task_id = str(uuid.uuid4())
        task_manager.register(task_id)

        background_tasks.add_task(
            task_manager.run_and_track_task,
            task_id,
            TheNewsService.process,
            date_str=date_str,
            cities=city_list
        )
        
        return TaskResponse(
            status="started",
            message=f"PDF generation task started for {date_str}.",
            task_id=task_id
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
