import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import endpoints
from app.api.deps import get_api_key
from app.core.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

app = FastAPI(title="NewsPapersHub API", version="2.0.0")

@app.on_event("startup")
async def startup_event():
    await init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    endpoints.router, 
    prefix="/api/v1", 
    tags=["Newspapers"],
    dependencies=[Depends(get_api_key)]
)

@app.get("/health")
def health():
    return {"status": "ok"}
