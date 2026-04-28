import logging
import uuid
from typing import Optional, Any, Callable, Dict, Set
from sqlalchemy import delete, select
import asyncio

from app.core.database import AsyncSessionLocal
from app.models.database_models import TaskRecord
from app.models.schemas import TaskState

logger = logging.getLogger(__name__)

class TaskEventBus:
    """Manages real-time subscriptions for task updates using asyncio.Queues."""
    def __init__(self):
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if task_id not in self.subscribers:
            self.subscribers[task_id] = set()
        self.subscribers[task_id].add(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue):
        if task_id in self.subscribers:
            self.subscribers[task_id].discard(queue)
            if not self.subscribers[task_id]:
                del self.subscribers[task_id]

    async def notify(self, task_id: str, data: dict):
        if task_id in self.subscribers:
            # Create a copy of the set to avoid issues if set changes during iteration
            for queue in list(self.subscribers[task_id]):
                await queue.put(data)

class TaskManagerService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.bus = TaskEventBus()

    async def get_task(self, newspaper: str, date: str, city: Optional[str] = None) -> Optional[TaskRecord]:
        async with self.session_factory() as session:
            stmt = select(TaskRecord).where(
                TaskRecord.newspaper == newspaper,
                TaskRecord.date == date,
                TaskRecord.city == city
            )
            result = await session.execute(stmt)
            return result.scalars().first()

    async def create_task(self, newspaper: str, date: str, city: Optional[str] = None) -> TaskRecord:
        task_id = str(uuid.uuid4())
        task = TaskRecord(
            id=task_id,
            newspaper=newspaper,
            date=date,
            city=city,
            state=TaskState.PENDING,
            percentage=0,
            message="Task initialized."
        )
        async with self.session_factory() as session:
            session.add(task)
            await session.commit()
            await session.refresh(task)
        return task

    async def cleanup_task(self, task_id: str):
        async with self.session_factory() as session:
            await session.execute(delete(TaskRecord).where(TaskRecord.id == task_id))
            await session.commit()

    async def publish(self, task_id: str, state: Optional[TaskState] = None, 
                      percentage: Optional[int] = None, message: Optional[str] = None, 
                      result: Optional[Any] = None):
        """Update the current state of the task in DB (matches old task_manager API)."""
        async with self.session_factory() as session:
            stmt = select(TaskRecord).where(TaskRecord.id == task_id)
            db_result = await session.execute(stmt)
            task = db_result.scalars().first()
            if task:
                if state: task.state = state
                if percentage is not None: task.percentage = percentage
                if message: task.message = message
                if result is not None:
                    # Convert Pydantic models to dict for JSON serialization
                    if hasattr(result, "model_dump"):
                        task.result = result.model_dump()
                    elif isinstance(result, list):
                        task.result = [r.model_dump() if hasattr(r, "model_dump") else r for r in result]
                    else:
                        task.result = result
                await session.commit()
                
                # Broadcast update to SSE subscribers
                await self.bus.notify(task_id, {
                    "id": task_id,
                    "state": task.state,
                    "progress": task.percentage,
                    "message": task.message,
                    "result": task.result
                })

    async def run_in_background(self, task_id: str, func: Callable, *args, **kwargs):
        """Wrapper to run a service method and update DB state."""
        try:
            await self.publish(task_id, state=TaskState.DISCOVERING, percentage=5, message="Processing started...")
            result = await func(*args, **kwargs, task_id=task_id)
            await self.publish(task_id, state=TaskState.COMPLETED, percentage=100, message="Success!", result=result)
        except Exception as e:
            logger.exception(f"Task {task_id} failed: {e}")
            await self.publish(task_id, state=TaskState.ERROR, percentage=0, message=str(e))

# Global Instance
task_service = TaskManagerService(AsyncSessionLocal)
task_manager = task_service  # For backward compatibility
