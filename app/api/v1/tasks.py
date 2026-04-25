from fastapi import APIRouter, HTTPException
from app.core.task_manager import task_manager
from app.models.schemas import TaskProgressResponse

router = APIRouter(prefix="/tasks")

@router.get("/progress/{task_id}", response_model=TaskProgressResponse)
async def get_task_progress(task_id: str):
    """
    Returns the current status and percentage of the background task instantly.
    """
    status = task_manager.get_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return status
