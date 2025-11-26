from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import settings

# Lazy initialization - only create engine when needed
engine = None
SessionLocal = None

def get_engine():
    """Get or create the database engine"""
    global engine, SessionLocal
    if engine is None:
        # Ensure database URL uses postgresql:// (not postgres://)
        db_url = settings.database_url
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine

Base = declarative_base()


class FileUpload(Base):
    __tablename__ = "file_uploads"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    file_name = Column(String, nullable=False)
    project_name = Column(String, nullable=False)
    file_size_kb = Column(Float, nullable=False)
    upload_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    tags = Column(Text, nullable=True)  # JSON string of tags
    file_content = Column(Text, nullable=True)  # Store file content for retrieval
    file_search_store_name = Column(String, nullable=True)  # Store File Search Store name for queries


class UserStorage(Base):
    __tablename__ = "user_storage"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, nullable=False, index=True)
    total_storage_kb = Column(Float, default=0.0, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_db():
    """Get database session"""
    if SessionLocal is None:
        get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    
    # Run migration which handles both fresh DB and updates
    try:
        from migrate_db import migrate_database
        migrate_database()
    except Exception as e:
        print(f"Migration error: {e}")
        # Fallback: try to create tables directly
        try:
            Base.metadata.create_all(bind=engine)
            print("Created tables using fallback method")
        except Exception as fallback_error:
            print(f"Fallback also failed: {fallback_error}")
            raise

