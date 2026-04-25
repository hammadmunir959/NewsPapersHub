from fastapi import APIRouter
from app.api.v1 import dawn, thenews, tasks

router = APIRouter()

router.include_router(dawn.router)
router.include_router(thenews.router)
router.include_router(tasks.router)


