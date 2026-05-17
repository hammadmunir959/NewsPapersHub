from typing import List
from fastapi import APIRouter
from app.schemas.schemas import SubscriberCreate, SubscriberUpdate, SubscriberResponse
from app.services.subscribers_service import SubscribersService

router = APIRouter()

@router.get("/", response_model=List[SubscriberResponse])
async def list_subscribers():
    return await SubscribersService.list_subscribers()

@router.post("/", response_model=SubscriberResponse)
async def create_subscriber(subscriber: SubscriberCreate):
    return await SubscribersService.create_subscriber(subscriber)

@router.get("/{subscriber_id}", response_model=SubscriberResponse)
async def get_subscriber(subscriber_id: int):
    return await SubscribersService.get_subscriber(subscriber_id)

@router.put("/{subscriber_id}", response_model=SubscriberResponse)
async def update_subscriber(subscriber_id: int, subscriber: SubscriberUpdate):
    return await SubscribersService.update_subscriber(subscriber_id, subscriber)

@router.delete("/{subscriber_id}")
async def delete_subscriber(subscriber_id: int):
    return await SubscribersService.delete_subscriber(subscriber_id)
