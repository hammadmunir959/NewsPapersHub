from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON
from app.core.database import Base
from app.schemas.schemas import TaskState

class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    newspaper = Column(String, nullable=False)
    date = Column(String, nullable=False)
    city = Column(String, nullable=True)
    state = Column(String, default=TaskState.PENDING)
    percentage = Column(Integer, default=0)
    message = Column(String, default="")
    result = Column(JSON, nullable=True)
    broadcast_status = Column(String, default="pending")
    broadcast_at = Column(DateTime, nullable=True)
    broadcast_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Subscriber(Base):
    __tablename__ = "subscribers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
