from fastapi import HTTPException
from sqlalchemy import select, delete
from typing import List, Optional

from app.core.database import AsyncSessionLocal
from app.models.database_models import Subscriber
from app.schemas.schemas import SubscriberCreate, SubscriberUpdate
from app.utils import normalize_jid

class SubscribersService:
    @staticmethod
    async def list_subscribers() -> List[Subscriber]:
        """List all subscribers."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Subscriber))
            return list(result.scalars().all())

    @staticmethod
    async def create_subscriber(subscriber: SubscriberCreate) -> Subscriber:
        """Create a new subscriber after normalizing their phone number."""
        clean_phone = normalize_jid(subscriber.phone_number)
        
        async with AsyncSessionLocal() as session:
            # Check if already exists
            existing = await session.execute(
                select(Subscriber).where(Subscriber.phone_number == clean_phone)
            )
            if existing.scalars().first():
                raise HTTPException(status_code=400, detail="Subscriber with this phone number already exists")
            
            sub_data = subscriber.model_dump()
            sub_data["phone_number"] = clean_phone
            
            db_subscriber = Subscriber(**sub_data)
            session.add(db_subscriber)
            await session.commit()
            await session.refresh(db_subscriber)
            return db_subscriber

    @staticmethod
    async def get_subscriber(subscriber_id: int) -> Subscriber:
        """Get a subscriber by ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.id == subscriber_id)
            )
            db_subscriber = result.scalars().first()
            if not db_subscriber:
                raise HTTPException(status_code=404, detail="Subscriber not found")
            return db_subscriber

    @staticmethod
    async def update_subscriber(subscriber_id: int, subscriber: SubscriberUpdate) -> Subscriber:
        """Update an existing subscriber and normalize phone number if provided."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.id == subscriber_id)
            )
            db_subscriber = result.scalars().first()
            if not db_subscriber:
                raise HTTPException(status_code=404, detail="Subscriber not found")
            
            update_data = subscriber.model_dump(exclude_unset=True)
            if "phone_number" in update_data:
                update_data["phone_number"] = normalize_jid(update_data["phone_number"])
                
            for key, value in update_data.items():
                setattr(db_subscriber, key, value)
            
            await session.commit()
            await session.refresh(db_subscriber)
            return db_subscriber

    @staticmethod
    async def delete_subscriber(subscriber_id: int) -> dict:
        """Delete a subscriber by ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Subscriber).where(Subscriber.id == subscriber_id)
            )
            db_subscriber = result.scalars().first()
            if not db_subscriber:
                raise HTTPException(status_code=404, detail="Subscriber not found")
            
            await session.delete(db_subscriber)
            await session.commit()
            return {"status": "success", "message": "Subscriber deleted"}
