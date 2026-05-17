"""
Newspaper delivery scheduler.

Runs as a standalone process (via supervisord or systemd).
Every SCHEDULER_INTERVAL_MIN minutes it checks whether the current hour falls
inside the configured delivery window (SCHEDULER_WINDOW_START–SCHEDULER_WINDOW_END).

If inside the window and today's Dawn hasn't been delivered yet:
  1. Generate the PDF by calling DawnService directly (no HTTP round-trip).
  2. Broadcast the PDF to all active subscribers via neonize.
  3. Mark the task as delivered so subsequent checks in the same day skip it.

Configuration (set in .env or environment):
    SCHEDULER_WINDOW_START  — delivery window start hour, 24h (default: 19 → 7 PM)
    SCHEDULER_WINDOW_END    — delivery window end hour, 24h  (default: 24 → midnight)
    SCHEDULER_INTERVAL_MIN  — check frequency in minutes     (default: 30)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, List


from app.core.config import (
    SCHEDULER_WINDOW_START,
    SCHEDULER_WINDOW_END,
    SCHEDULER_INTERVAL_MIN,
    setup_logger,
)
from app.services.dawn_service import DawnService
from app.services.whatsapp_service import send_to_subscribers
from app.services.task_manager_service import task_service
from app.schemas.schemas import TaskState
from app.utils.user_utils import get_dynamic_greeting

logger = setup_logger(__name__)


async def _is_already_delivered(date_str: str) -> bool:
    """Return True if today's Dawn was already successfully sent via WhatsApp."""
    task = await task_service.get_task("dawn", date_str)
    if task and task.state == TaskState.COMPLETED:
        result = task.result or {}
        return result.get("whatsapp_sent", False)
    return False


async def run_dawn_delivery(date_str: str) -> None:
    """
    Full pipeline for one day's Dawn edition:
      1. Check cache / previous delivery status.
      2. Generate PDF via DawnService (uses disk cache if already built).
      3. Broadcast to all active DB subscribers.
      4. Mark delivered in the task record.
    """
    logger.info(f"=== Dawn delivery run: {date_str} ===")

    # 1. Skip if already delivered today
    if await _is_already_delivered(date_str):
        logger.info(f"Dawn for {date_str} already delivered. Skipping.")
        return

    # 2. Get or create a task record
    task = await task_service.get_task("dawn", date_str)
    if task and task.state == TaskState.ERROR:
        logger.info("Previous task errored — cleaning up and retrying.")
        await task_service.cleanup_task(task.id)
        task = None
    if not task:
        task = await task_service.create_task("dawn", date_str)

    # 3. Generate the PDF (DawnService uses disk cache if already built)
    try:
        response = await DawnService().process(date_str, task_id=task.id)
        pdf_path = response.path
        logger.info(f"PDF ready: {pdf_path} ({response.size_mb} MB)")
    except Exception as e:
        logger.error(f"Dawn generation failed: {e}")
        await task_service.publish(task.id, state=TaskState.ERROR, message=str(e))
        return

    # 4. Broadcast to all subscribers
    greeting = get_dynamic_greeting()
    caption = (
        f"📰 {greeting} {{name}}!\n"
        f"Your Dawn newspaper for {date_str} is here. Enjoy your read!\n\n"
        " _This is an automated message_\n"
        "⚡ _Powered by NewsPapersHub_"
    )
    try:
        await send_to_subscribers(pdf_path=pdf_path, caption=caption)
    except Exception as e:
        logger.error(f"WhatsApp broadcast failed: {e}")
        await task_service.publish(
            task.id,
            broadcast_status="failed",
            broadcast_at=datetime.now(),
            broadcast_error=str(e)
        )
        return

    # 5. Mark as delivered — store flag in existing result JSON
    delivered_result = response.model_dump()
    delivered_result["whatsapp_sent"] = True
    await task_service.publish(
        task.id,
        state=TaskState.COMPLETED,
        percentage=100,
        message="Dawn PDF generated and delivered to all subscribers.",
        result=delivered_result,
        broadcast_status="success",
        broadcast_at=datetime.now()
    )
    logger.info(f"=== Dawn delivery complete for {date_str} ===")


async def execute_delivery_pipeline(date_str: str, papers: Optional[list[str]] = None) -> None:
    """
    Manually trigger the delivery pipeline for a specific date and set of papers.
    """
    logger.info(f"Manual pipeline execution triggered for date={date_str}, papers={papers}")
    target_papers = papers or ["dawn"]
    
    tasks = []
    if "dawn" in target_papers:
        tasks.append(run_dawn_delivery(date_str))
    if "thenews" in target_papers:
        # Import dynamically to avoid potential circular dependencies
        from app.services.thenews_service import TheNewsService
        
        async def run_thenews_delivery_task():
            logger.info(f"=== The News delivery run: {date_str} ===")
            task = await task_service.get_task("thenews", date_str)
            if task and task.state == TaskState.ERROR:
                logger.info("Previous task errored — cleaning up and retrying.")
                await task_service.cleanup_task(task.id)
                task = None
            if not task:
                task = await task_service.create_task("thenews", date_str)
            
            try:
                responses = await TheNewsService.process(date_str, task_id=task.id)
                for response in responses:
                    greeting = get_dynamic_greeting()
                    caption = (
                        f"📰 {greeting} {{name}}!\n"
                        f"Your The News newspaper for {date_str} is here. Enjoy your read!\n\n"
                        " _This is an automated message_\n"
                        "⚡ _Powered by NewsPapersHub_"
                    )
                    await send_to_subscribers(pdf_path=response.path, caption=caption)
                
                if responses:
                    await task_service.publish(
                        task.id,
                        state=TaskState.COMPLETED,
                        percentage=100,
                        message="The News PDFs generated and delivered to all subscribers.",
                        result=[r.model_dump() for r in responses],
                        broadcast_status="success",
                        broadcast_at=datetime.now()
                    )
            except Exception as e:
                logger.error(f"The News delivery failed: {e}")
                await task_service.publish(
                    task.id, 
                    state=TaskState.ERROR, 
                    message=str(e),
                    broadcast_status="failed",
                    broadcast_at=datetime.now(),
                    broadcast_error=str(e)
                )
                
        tasks.append(run_thenews_delivery_task())
        
    if tasks:
        await asyncio.gather(*tasks)


async def scheduler_loop() -> None:
    """
    Pure-async cron loop.
    Checks every SCHEDULER_INTERVAL_MIN minutes whether we're inside the
    delivery window, then triggers the Dawn delivery pipeline once per day.
    """
    logger.info(
        f"Scheduler started — window: {SCHEDULER_WINDOW_START:02d}:00 – "
        f"{'00:00 (midnight)' if SCHEDULER_WINDOW_END >= 24 else f'{SCHEDULER_WINDOW_END:02d}:00'}, "
        f"check interval: every {SCHEDULER_INTERVAL_MIN} min"
    )

    while True:
        now = datetime.now()
        hour = now.hour

        # Handle midnight boundary: treat hour 0 as 24 for comparison
        effective_hour = hour if hour != 0 else 24

        in_window = SCHEDULER_WINDOW_START <= effective_hour < SCHEDULER_WINDOW_END

        if in_window:
            logger.debug(f"Inside delivery window (hour={hour}). Checking delivery status...")
            date_str = now.strftime("%Y-%m-%d")
            await run_dawn_delivery(date_str)
        else:
            logger.debug(
                f"Outside delivery window (hour={hour}, "
                f"window={SCHEDULER_WINDOW_START}–{SCHEDULER_WINDOW_END}). Sleeping."
            )

        await asyncio.sleep(SCHEDULER_INTERVAL_MIN * 60)


if __name__ == "__main__":
    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
