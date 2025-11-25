from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status, Body
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
from datetime import datetime

from database import get_db, FileUpload, UserStorage, init_db
from auth_dependency import get_current_user
from gemini_client import gemini_client
from file_utils import extract_tags_from_text, tags_to_json
from pydantic import BaseModel, Field

app = FastAPI(
    title="RAG File Search Service",
    description="""
    A FastAPI service that integrates with Google's Gemini File Search Tool for document search and retrieval.
    
    ## Features
    
    * **File Upload**: Upload `.txt` files (max 100 MB) with automatic tagging
    * **Gemini File Search**: Query uploaded files using Google's File Search Tool
    * **Authentication**: Integrates with existing auth microservice
    * **User Isolation**: All operations are scoped to authenticated users
    
    ## Authentication
    
    All endpoints (except `/health`) require Bearer token authentication.
    Include the token in the Authorization header: `Bearer <your-token>`
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
    },
    tags_metadata=[
        {
            "name": "Files",
            "description": "Operations for uploading and managing files.",
        },
        {
            "name": "Search",
            "description": "Operations for searching and querying uploaded files using Gemini File Search.",
        },
        {
            "name": "Storage",
            "description": "Operations for viewing storage information.",
        },
        {
            "name": "Health",
            "description": "Health check endpoint.",
        },
    ],
)

# Configure CORS for development
# For production, replace with specific origins
from config import settings
import re

# Check if we're in development (you can set this via env var)
is_development = os.getenv("ENVIRONMENT", "development").lower() == "development"

if is_development:
    # In development, allow all localhost origins
    # This uses a regex pattern to match any localhost port
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],  # Allow all methods (GET, POST, PUT, DELETE, etc.)
        allow_headers=["*"],  # Allow all headers
    )
else:
    # In production, specify exact origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            # Add your production frontend URLs here
            "https://yourdomain.com",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()


# Pydantic models
class PromptRequest(BaseModel):
    prompt: str = Field(
        ...,
        description="The search query or prompt to process using Gemini File Search. Will search all user's uploaded files.",
        example="What is the main topic discussed in the documents?"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "What are the key findings in the research documents?"
            }
        }


class PromptResponse(BaseModel):
    response: str = Field(
        ...,
        description="The response from Gemini File Search based on the prompt and uploaded files",
        example="Based on the uploaded documents, the key findings are..."
    )


class FileUploadResponse(BaseModel):
    message: str = Field(..., description="Success message")
    file_id: int = Field(..., description="ID of the uploaded file")
    file_name: str = Field(..., description="Name of the uploaded file")
    project_name: str = Field(..., description="Project name extracted from filename")
    size_kb: float = Field(..., description="File size in kilobytes")
    tags: List[str] = Field(..., description="Extracted tags for hybrid retrieval")
    total_storage_kb: float = Field(..., description="User's total storage usage in KB")


class FileInfo(BaseModel):
    id: int
    file_name: str
    project_name: str
    size_kb: float
    upload_time: str
    tags: List[str]


class FilesListResponse(BaseModel):
    files: List[FileInfo]


class StorageInfo(BaseModel):
    user_id: str
    total_storage_kb: float
    last_updated: Optional[str] = None


# File upload endpoint
@app.post(
    "/upload",
    response_model=FileUploadResponse,
    tags=["Files"],
    summary="Upload a text file",
    description="""
    Upload a `.txt` file to the service. The file will be:
    - Validated (must be .txt, max 100 MB)
    - Uploaded to Gemini File Search
    - Tagged automatically for hybrid retrieval
    - Stored in the database with metadata
    
    The user's total storage will be updated automatically.
    """,
    responses={
        200: {
            "description": "File uploaded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "File uploaded successfully",
                        "file_id": 1,
                        "file_name": "document.txt",
                        "project_name": "document",
                        "size_kb": 45.2,
                        "tags": ["keyword1", "keyword2", "keyword3"],
                        "total_storage_kb": 45.2
                    }
                }
            }
        },
        400: {"description": "Invalid file type or size exceeded"},
        401: {"description": "Unauthorized - Invalid or missing token"},
        500: {"description": "Internal server error"}
    }
)
async def upload_file(
    file: UploadFile = File(..., description="The .txt file to upload (max 100 MB)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a .txt file and process it with Gemini File Search.
    
    - **file**: Must be a .txt file, maximum size 100 MB
    - Returns file metadata including extracted tags and updated storage info
    """
    
    # Check file extension
    if not file.filename.endswith('.txt'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt files are allowed"
        )
    
    # Read file content
    content = await file.read()
    file_size_bytes = len(content)
    file_size_kb = file_size_bytes / 1024.0
    
    # Check max file size (100 MB = 102400 KB)
    max_size_kb = 102400
    if file_size_kb > max_size_kb:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum of {max_size_kb} KB (100 MB)"
        )
    
    # Decode content
    try:
        file_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8 encoded text"
        )
    
    user_id = current_user["user_id"]
    
    try:
        # Check if user already has a file with a store (reuse the same store for all user's files)
        existing_file = db.query(FileUpload).filter(
            FileUpload.user_id == user_id,
            FileUpload.file_search_store_name.isnot(None)
        ).first()
        
        existing_store_name = existing_file.file_search_store_name if existing_file else None
        
        # Get or create a File Search Store for this user
        file_search_store_name = gemini_client.get_or_create_file_search_store(
            user_id, 
            existing_store_name
        )
        
        # Upload file to Gemini File Search Store
        uploaded_store_name = gemini_client.upload_file(
            file_content, 
            file.filename, 
            file_search_store_name
        )
        if not uploaded_store_name:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload file to Gemini File Search Store"
            )
        
        # Extract project name from filename
        project_name = file.filename.rsplit('.', 1)[0]  # Remove .txt extension
        
        # Extract tags for hybrid retrieval
        tags = extract_tags_from_text(file_content)
        tags_json = tags_to_json(tags)
        
        # Save to database
        db_file = FileUpload(
            user_id=user_id,
            file_name=file.filename,
            project_name=project_name,
            file_size_kb=file_size_kb,
            upload_time=datetime.utcnow(),
            tags=tags_json,
            file_content=file_content,  # Store content for retrieval
            file_search_store_name=uploaded_store_name  # Store File Search Store name
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        # Update user's total storage
        user_storage = db.query(UserStorage).filter(UserStorage.user_id == user_id).first()
        if not user_storage:
            user_storage = UserStorage(
                user_id=user_id,
                total_storage_kb=file_size_kb
            )
            db.add(user_storage)
        else:
            user_storage.total_storage_kb += file_size_kb
            user_storage.last_updated = datetime.utcnow()
        
        db.commit()
        
        return {
            "message": "File uploaded successfully",
            "file_id": db_file.id,
            "file_name": file.filename,
            "project_name": project_name,
            "size_kb": file_size_kb,
            "tags": tags,
            "total_storage_kb": user_storage.total_storage_kb
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing file: {str(e)}"
        )


# Prompt endpoint
@app.post(
    "/prompt",
    response_model=PromptResponse,
    tags=["Search"],
    summary="Query uploaded files using Gemini File Search",
    description="""
    Process a prompt/question using Google's Gemini File Search tool.
    
    The service will:
    - Search through ALL of the user's uploaded files
    - Use Gemini File Search to find relevant information
    - Return a response based on the content of all uploaded files
    
    All files uploaded by the authenticated user will be included in the search.
    """,
    responses={
        200: {
            "description": "Successfully processed prompt",
            "content": {
                "application/json": {
                    "example": {
                        "response": "Based on the uploaded documents, the main topic is..."
                    }
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing token"},
        404: {"description": "No files found for this user"},
        500: {"description": "Error processing prompt with Gemini"}
    }
)
async def process_prompt(
    request: PromptRequest = Body(..., description="The prompt request with query. Will search all user's files."),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process a prompt using Gemini File Search tool with ALL user's files.
    
    - **prompt**: The question or query to search for
    - Returns a response generated by Gemini based on all uploaded files
    """
    
    user_id = current_user["user_id"]
    
    # Get ALL user's files - always search all files
    files = db.query(FileUpload).filter(FileUpload.user_id == user_id).all()
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No files found for this user. Please upload files first."
        )
    
    try:
        # Get or create the user's File Search Store
        # All files from the same user should be in the same store
        existing_file = db.query(FileUpload).filter(
            FileUpload.user_id == user_id,
            FileUpload.file_search_store_name.isnot(None)
        ).first()
        
        existing_store_name = existing_file.file_search_store_name if existing_file else None
        
        # Get or create the store for this user
        file_search_store_name = gemini_client.get_or_create_file_search_store(
            user_id, 
            existing_store_name
        )
        
        # Ensure all user's files are in the store
        # Check if any files are missing from the store
        files_missing_from_store = [
            f for f in files 
            if not f.file_search_store_name or f.file_search_store_name != file_search_store_name
        ]
        
        # Upload any missing files to the store
        for file in files_missing_from_store:
            print(f"Uploading missing file {file.file_name} to store...")
            uploaded_store = gemini_client.upload_file(
                file.file_content, 
                file.file_name, 
                file_search_store_name
            )
            if uploaded_store:
                # Update database with the store name
                file.file_search_store_name = uploaded_store
                db.commit()
        
        # Use the user's File Search Store for the query
        # All files should be in this single store
        file_search_store_names = [file_search_store_name]
        
        print(f"Searching in store: {file_search_store_name} with {len(files)} files")
        
        if not file_search_store_names:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to prepare files for search"
            )
        
        # Use Gemini File Search to get response
        try:
            response_text = gemini_client.search_and_respond(
                request.prompt, 
                list(file_search_store_names)
            )
        except Exception as gemini_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing prompt with Gemini: {str(gemini_error)}"
            )
        
        return PromptResponse(response=response_text)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing prompt: {str(e)}"
        )


# Health check endpoint
@app.get(
    "/health",
    tags=["Health"],
    summary="Health check",
    description="Check if the service is running and healthy. No authentication required.",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {"status": "healthy"}
                }
            }
        }
    }
)
async def health_check():
    """Health check endpoint - returns service status"""
    from config import settings
    return {
        "status": "healthy",
        "auth_base_url": settings.auth_base_url,
        "database_configured": bool(settings.database_url),
        "gemini_configured": bool(settings.gemini_api_key)
    }


# Debug endpoint to test auth (remove in production)
@app.get(
    "/debug/auth-test",
    tags=["Health"],
    summary="Test authentication (debug)",
    description="Test endpoint to debug authentication issues. Requires Bearer token.",
    responses={
        200: {"description": "Authentication successful"},
        401: {"description": "Authentication failed"}
    }
)
async def debug_auth_test(
    current_user: dict = Depends(get_current_user)
):
    """Debug endpoint to test authentication"""
    return {
        "message": "Authentication successful",
        "user_id": current_user.get("user_id"),
        "available_fields": list(current_user.keys())
    }


# Get user's files
@app.get(
    "/files",
    response_model=FilesListResponse,
    tags=["Files"],
    summary="Get all user's files",
    description="Retrieve a list of all files uploaded by the authenticated user.",
    responses={
        200: {
            "description": "List of user's files",
            "content": {
                "application/json": {
                    "example": {
                        "files": [
                            {
                                "id": 1,
                                "file_name": "document.txt",
                                "project_name": "document",
                                "size_kb": 45.2,
                                "upload_time": "2024-01-15T10:30:00",
                                "tags": ["keyword1", "keyword2"]
                            }
                        ]
                    }
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing token"}
    }
)
async def get_user_files(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all files uploaded by the current user.
    
    Returns a list of files with metadata including:
    - File ID, name, and size
    - Upload timestamp
    - Extracted tags
    """
    user_id = current_user["user_id"]
    
    files = db.query(FileUpload).filter(FileUpload.user_id == user_id).all()
    
    from file_utils import json_to_tags
    
    return {
        "files": [
            {
                "id": f.id,
                "file_name": f.file_name,
                "project_name": f.project_name,
                "size_kb": f.file_size_kb,
                "upload_time": f.upload_time.isoformat(),
                "tags": json_to_tags(f.tags)
            }
            for f in files
        ]
    }


# Get user storage info
@app.get(
    "/storage",
    response_model=StorageInfo,
    tags=["Storage"],
    summary="Get user storage information",
    description="Get the current user's total storage usage and last update timestamp.",
    responses={
        200: {
            "description": "User storage information",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "total_storage_kb": 1024.5,
                        "last_updated": "2024-01-15T10:30:00"
                    }
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing token"}
    }
)
async def get_user_storage(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user's storage information.
    
    Returns:
    - Total storage used in KB
    - Last update timestamp
    """
    user_id = current_user["user_id"]
    
    user_storage = db.query(UserStorage).filter(UserStorage.user_id == user_id).first()
    
    if not user_storage:
        return {
            "user_id": user_id,
            "total_storage_kb": 0.0,
            "last_updated": None
        }
    
    return {
        "user_id": user_id,
        "total_storage_kb": user_storage.total_storage_kb,
        "last_updated": user_storage.last_updated.isoformat() if user_storage.last_updated else None
    }


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="RAG File Search Service",
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

