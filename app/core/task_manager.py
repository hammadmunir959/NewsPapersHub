import asyncio
import json
import logging
from typing import Dict, Any, Callable, Coroutine
import inspect

import inspect
from typing import Dict, Any, Callable
from app.models.schemas import TaskState

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self):
        # Maps task_id to its current status dict
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def register(self, task_id: str):
        """Register a new task and initialize its status."""
        self.tasks[task_id] = {
            "task_id": task_id,
            "state": TaskState.PENDING,
            "percentage": 0,
            "message": "Task queued.",
            "result": None
        }

    async def publish(self, task_id: str, state: TaskState, percentage: int, message: str, result=None):
        """Update the current state of the task."""
        if task_id in self.tasks:
            self.tasks[task_id].update({
                "state": state,
                "percentage": percentage,
                "message": message
            })
            if result is not None:
                self.tasks[task_id]["result"] = result
            logger.debug(f"[Task {task_id}] Updated: {percentage}% - {state.value} - {message}")

    def get_status(self, task_id: str) -> Dict[str, Any]:
        """Return instantly the latest status of the task."""
        return self.tasks.get(task_id)
        
    def cleanup(self, task_id: str):
        """Remove task data from memory. Could be called after it's retrieved as completed."""
        self.tasks.pop(task_id, None)

    async def run_and_track_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Wrapper to execute the background task safely and publish terminal events."""
        try:
            await self.publish(task_id, TaskState.DISCOVERING, 5, "Task has been picked up by background worker.")
            
            if inspect.iscoroutinefunction(func):
                result = await func(*args, task_id=task_id, **kwargs)
            else:
                import asyncio
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(None, lambda: func(*args, task_id=task_id, **kwargs))
            
            # Extract models to dict if necessary
            if isinstance(result, list):
                result_dict = [r.dict() if hasattr(r, 'dict') else r for r in result]
            elif hasattr(result, 'dict'):
                result_dict = result.dict()
            else:
                result_dict = result

            await self.publish(task_id, TaskState.COMPLETED, 100, "Task finished successfully.", result_dict)
        except Exception as e:
            logger.exception(f"Background task {task_id} failed with error: {e}")
            await self.publish(task_id, TaskState.ERROR, 0, str(e))

# Global instance
task_manager = TaskManager()
