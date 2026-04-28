import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from app.services.dawn_service import DawnService
from app.services.thenews_service import TheNewsService
from app.models.schemas import TaskProgressResponse, CityName, TaskState
from app.utils.date_utils import validate_date
from app.services.task_manager_service import task_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stream/{task_id}")
async def stream_task_progress(task_id: str):
    """
    Stream real-time task progress updates via Server-Sent Events (SSE).
    """
    async def event_generator():
        queue = task_service.bus.subscribe(task_id)
        try:
            while True:
                # Wait for next update from the bus
                data = await queue.get()
                yield f"data: {json.dumps(data)}\n\n"
                
                # Stop streaming if task is in a terminal state
                if data["state"] in [TaskState.COMPLETED, TaskState.ERROR]:
                    break
        finally:
            task_service.bus.unsubscribe(task_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/dawn/{date_str}", response_model=TaskProgressResponse)
async def get_dawn_paper(
    background_tasks: BackgroundTasks,
    date_str: str = Path(..., description="Date in YYYY-MM-DD format")
):
    """
    Get Dawn newspaper PDF generation status for a given date.
    Triggers generation if not exists or if previous attempt failed.
    """
    validate_date(date_str)
    
    task = await task_service.get_task("dawn", date_str)
    
    # Retry if failed: cleanup and restart
    if task and task.state == TaskState.ERROR:
        logger.info(f"Re-attempting failed Dawn task for {date_str}")
        await task_service.cleanup_task(task.id)
        task = None
        
    if not task:
        task = await task_service.create_task("dawn", date_str)
        background_tasks.add_task(
            task_service.run_in_background,
            task.id,
            DawnService().process,
            date_str=date_str
        )
    
    return TaskProgressResponse(
        id=task.id,
        state=task.state,
        progress=task.percentage,
        message=task.message,
        result=task.result
    )

@router.get("/thenews/{date_str}", response_model=TaskProgressResponse)
async def get_thenews_paper(
    background_tasks: BackgroundTasks,
    date_str: str = Path(..., description="Date in YYYY-MM-DD format"),
    cities: Optional[List[CityName]] = Query(None, alias="city")
):
    """
    Get The News newspaper PDF generation status for a given date/cities.
    Triggers generation if not exists or if previous attempt failed.
    """
    validate_date(date_str)
    city_list = [c.value for c in cities] if cities else None
    city_str = ",".join(sorted(city_list)) if city_list else "all"
    
    task = await task_service.get_task("thenews", date_str, city_str)
    
    if task and task.state == TaskState.ERROR:
        logger.info(f"Re-attempting failed The News task for {date_str} ({city_str})")
        await task_service.cleanup_task(task.id)
        task = None
        
    if not task:
        task = await task_service.create_task("thenews", date_str, city_str)
        background_tasks.add_task(
            task_service.run_in_background,
            task.id,
            TheNewsService.process,
            date_str=date_str,
            cities=city_list
        )
        
    return TaskProgressResponse(
        id=task.id,
        state=task.state,
        progress=task.percentage,
        message=task.message,
        result=task.result
    )


