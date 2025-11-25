from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from auth_client import auth_client
from typing import Optional


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Dependency to get current authenticated user"""
    token = credentials.credentials
    
    print(f"Attempting to verify token (length: {len(token)})")
    print(f"Auth base URL: {auth_client.base_url}")
    
    user_info = await auth_client.verify_token(token)
    if not user_info:
        print("Token verification failed - no user info returned")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials. Please check your token and ensure the auth service is accessible.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    print(f"User info received: {list(user_info.keys())}")
    
    # Extract user_id from user info
    # Handle nested structure: {"user": {"id": "..."}}
    user_obj = user_info.get("user") or user_info
    
    # Try multiple common field names
    user_id = (
        user_obj.get("user_id") or 
        user_obj.get("id") or 
        user_obj.get("sub") or
        user_obj.get("userId") or
        user_obj.get("_id") or
        user_obj.get("uid") or
        # Fallback to top-level if not nested
        user_info.get("user_id") or 
        user_info.get("id") or 
        user_info.get("sub") or
        user_info.get("userId") or
        user_info.get("_id") or
        user_info.get("uid")
    )
    
    if not user_id:
        print(f"User ID not found in response. Available keys: {list(user_info.keys())}")
        if "user" in user_info:
            print(f"User object keys: {list(user_info['user'].keys())}")
        print(f"Full response: {user_info}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User ID not found in token response. Available fields: {list(user_info.keys())}",
        )
    
    print(f"Successfully authenticated user: {user_id}")
    return {"user_id": str(user_id), "token": token, **user_info}

