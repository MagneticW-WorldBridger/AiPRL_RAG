# RAG File Search Service

A FastAPI service that integrates with Google's Gemini File Search Tool for document search and retrieval.

## Features

- **File Upload**: Upload `.txt` files (max 100 MB) with automatic tagging for hybrid retrieval
- **Gemini File Search**: Query uploaded files using Google's File Search Tool
- **Authentication**: Integrates with existing auth microservice
- **PostgreSQL Database**: Stores file metadata and user storage information
- **User Isolation**: All operations are scoped to authenticated users

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
AUTH_BASE_URL=http://localhost:8000
DATABASE_URL=postgresql://user:password@host:port/dbname
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Database Setup

The application will automatically create the required tables on startup:
- `file_uploads`: Stores uploaded file metadata
- `user_storage`: Tracks total storage per user

### 4. Run the Application

**Option 1: Using Python module (recommended for Windows):**
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

**Option 2: Direct uvicorn command (if in PATH):**
```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

**Option 3: Using the built-in runner:**
```bash
python main.py
```

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: Available at `http://localhost:8001/docs`
  - Interactive API documentation
  - Try out endpoints directly from the browser
  - View request/response schemas
  
- **ReDoc**: Available at `http://localhost:8001/redoc`
  - Alternative documentation interface
  - Clean, readable format

- **OpenAPI Schema**: Available at `http://localhost:8001/openapi.json`
  - Raw OpenAPI 3.0 schema
  - Can be imported into API clients

## API Endpoints

All endpoints (except `/health`) require authentication via Bearer token.

### Upload File

```http
POST /upload
Content-Type: multipart/form-data
Authorization: Bearer <token>

file: <file.txt>
```

**Response:**
```json
{
  "message": "File uploaded successfully",
  "file_id": 1,
  "file_name": "document.txt",
  "project_name": "document",
  "size_kb": 45.2,
  "tags": ["keyword1", "keyword2"],
  "total_storage_kb": 45.2
}
```

### Process Prompt

```http
POST /prompt
Content-Type: application/json
Authorization: Bearer <token>

{
  "prompt": "What is the main topic?",
  "file_ids": [1, 2]  // Optional: empty array = all user's files
}
```

**Response:**
```json
{
  "response": "The main topic is..."
}
```

### Get User Files

```http
GET /files
Authorization: Bearer <token>
```

### Get User Storage

```http
GET /storage
Authorization: Bearer <token>
```

### Health Check

```http
GET /health
```

## Authentication

The service connects to an existing auth microservice. The auth service should have these endpoints:
- `POST /auth/signup`
- `POST /auth/signin`
- `GET /auth/me`
- `GET /auth/verify`
- `POST /auth/signout`

The service uses the `/auth/verify` endpoint to validate Bearer tokens.

## Database Schema

### file_uploads
- `id`: Primary key
- `user_id`: User identifier (from auth service)
- `file_name`: Original filename
- `project_name`: Extracted project name
- `file_size_kb`: File size in kilobytes
- `upload_time`: Upload timestamp
- `tags`: JSON array of extracted tags
- `file_content`: Full file content (for retrieval)
- `gemini_file_uri`: Gemini file URI (for File Search)

### user_storage
- `id`: Primary key
- `user_id`: User identifier (unique)
- `total_storage_kb`: Total storage used in KB
- `last_updated`: Last update timestamp

## Notes

- Only `.txt` files are accepted
- Maximum file size: 100 MB
- Files are automatically tagged for hybrid retrieval
- User storage is automatically updated on each upload
- All database operations are scoped to the authenticated user

