"""
Migration script to add file_search_store_name column to file_uploads table
Run this once to update your existing database schema.
"""
from sqlalchemy import text
from database import get_engine
from config import settings

def migrate_database():
    """Add file_search_store_name column if it doesn't exist"""
    # Ensure engine is created
    db_engine = get_engine()
    
    try:
        with db_engine.connect() as conn:
            # Check if column exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='file_uploads' 
                AND column_name='file_search_store_name'
            """)
            result = conn.execute(check_query)
            
            if result.fetchone() is None:
                # Column doesn't exist, add it
                print("Adding file_search_store_name column to file_uploads table...")
                alter_query = text("""
                    ALTER TABLE file_uploads 
                    ADD COLUMN file_search_store_name VARCHAR
                """)
                conn.execute(alter_query)
                conn.commit()
                print("Successfully added file_search_store_name column")
            else:
                print("Column file_search_store_name already exists")
            
            # Also check if we need to drop the old gemini_file_uri column if it exists
            check_old_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='file_uploads' 
                AND column_name='gemini_file_uri'
            """)
            old_result = conn.execute(check_old_query)
            
            if old_result.fetchone() is not None:
                print("Removing old gemini_file_uri column...")
                drop_query = text("""
                    ALTER TABLE file_uploads 
                    DROP COLUMN gemini_file_uri
                """)
                conn.execute(drop_query)
                conn.commit()
                print("Successfully removed old gemini_file_uri column")
            else:
                print("No old gemini_file_uri column to remove")
                
    except Exception as e:
        print(f"Error during migration: {e}")
        raise

if __name__ == "__main__":
    print("Running database migration...")
    migrate_database()
    print("Migration complete!")

