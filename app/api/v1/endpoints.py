from fastapi import APIRouter
from app.api.v1 import dawn, thenews, dawn_rss

router = APIRouter()

router.include_router(dawn.router)
router.include_router(dawn_rss.router)
router.include_router(thenews.router)
