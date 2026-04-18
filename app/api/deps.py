from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.core import config

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def get_api_key(api_key: str = Security(api_key_header)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    
    # Handle "Bearer <key>" format if used, or just raw key
    token = api_key
    if api_key.startswith("Bearer "):
        token = api_key.replace("Bearer ", "", 1)
        
    if token != config.APP_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return token
