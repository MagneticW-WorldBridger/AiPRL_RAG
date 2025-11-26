"""
Migration script for database schema
Handles both fresh database setup and migrations for existing databases.
"""
from sqlalchemy import text, inspect
from database import get_engine, Base, FileUpload, UserStorage
from config import settings

def check_table_exists(conn, table_name):
    """Check if a table exists in the database"""
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()

def migrate_database():
    """Run database migrations"""
    # Ensure engine is created
    db_engine = get_engine()
    
    try:
        with db_engine.begin() as conn:  # Use begin() for automatic transaction management
            # Check if tables exist
            file_uploads_exists = check_table_exists(conn, 'file_uploads')
            user_storage_exists = check_table_exists(conn, 'user_storage')
            
            if not file_uploads_exists or not user_storage_exists:
                print("Fresh database detected. Creating all tables...")
                # Create all tables from scratch
                Base.metadata.create_all(bind=db_engine)
                print("✓ Successfully created all tables")
                return
            
            print("Existing database detected. Checking for schema updates...")
            
            # Check if file_uploads table exists and has the required columns
            if file_uploads_exists:
                inspector = inspect(conn)
                columns = [col['name'] for col in inspector.get_columns('file_uploads')]
                
                # Check if file_search_store_name column exists
                if 'file_search_store_name' not in columns:
                    print("Adding file_search_store_name column to file_uploads table...")
                    alter_query = text("""
                        ALTER TABLE file_uploads 
                        ADD COLUMN file_search_store_name VARCHAR
                    """)
                    conn.execute(alter_query)
                    print("✓ Successfully added file_search_store_name column")
                else:
                    print("✓ Column file_search_store_name already exists")
                
                # Check if old gemini_file_uri column exists and remove it
                if 'gemini_file_uri' in columns:
                    print("Removing old gemini_file_uri column...")
                    drop_query = text("""
                        ALTER TABLE file_uploads 
                        DROP COLUMN gemini_file_uri
                    """)
                    conn.execute(drop_query)
                    print("✓ Successfully removed old gemini_file_uri column")
                else:
                    print("✓ No old gemini_file_uri column to remove")
            
            # Ensure user_storage table exists
            if not user_storage_exists:
                print("Creating user_storage table...")
                UserStorage.__table__.create(bind=db_engine, checkfirst=True)
                print("✓ Successfully created user_storage table")
            else:
                print("✓ user_storage table already exists")
                
    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    print("Running database migration...")
    print(f"Database URL: {settings.database_url[:20]}..." if len(settings.database_url) > 20 else f"Database URL: {settings.database_url}")
    migrate_database()
    print("Migration complete!")

