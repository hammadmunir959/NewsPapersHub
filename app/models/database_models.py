from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON
from app.core.database import Base
from app.models.schemas import TaskState

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
