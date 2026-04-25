from fastapi import APIRouter, HTTPException, Path, BackgroundTasks
from typing import List
import uuid

from app.services.dawn_service import DawnService
from app.models.schemas import PaperSuccessResponse, TaskResponse
from app.utils.date_utils import validate_date
from app.core.task_manager import task_manager

router = APIRouter(prefix="/dawn")


@router.get("/{date_str}", response_model=TaskResponse)
async def get_dawn_paper(
    background_tasks: BackgroundTasks,
    date_str: str = Path(..., description="Date in YYYY-MM-DD format")
):
    """
    Start Dawn newspaper PDF generation for a given date.
    Returns a task task_id that can be streamed for status.
    """
    try:
        validate_date(date_str)

        task_id = str(uuid.uuid4())
        task_manager.register(task_id)
        
        background_tasks.add_task(
            task_manager.run_and_track_task,
            task_id,
            DawnService.process,
            date_str=date_str
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