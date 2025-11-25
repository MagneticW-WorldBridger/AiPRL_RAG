from google import genai
from google.genai import types
from typing import List, Optional
from config import settings
import tempfile
import os
import time


class GeminiFileSearchClient:
    def __init__(self):
        # Initialize the Gemini client with API key
        self.client = genai.Client(api_key=settings.gemini_api_key)
    
    def get_or_create_file_search_store(self, user_id: str, existing_store_name: Optional[str] = None) -> str:
        """Get or create a File Search Store for a user"""
        try:
            # If we have an existing store name, return it
            if existing_store_name:
                return existing_store_name
            
            # Create a new store for this user
            store_display_name = f"user_{user_id}_store"
            file_search_store = self.client.file_search_stores.create(
                config={'display_name': store_display_name}
            )
            
            return file_search_store.name
        except Exception as e:
            print(f"Error creating file search store: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def upload_file(self, file_content: str, file_name: str, file_search_store_name: str) -> Optional[str]:
        """Upload file to Gemini File Search Store and return document name"""
        try:
            # Create a temporary file to upload
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name
            
            try:
                print(f"Uploading file {file_name} to store {file_search_store_name}...")
                
                # Upload and import a file into the File Search store
                operation = self.client.file_search_stores.upload_to_file_search_store(
                    file=tmp_path,
                    file_search_store_name=file_search_store_name,
                    config={
                        'display_name': file_name,
                    }
                )
                
                print(f"Upload operation started. Operation type: {type(operation)}")
                
                # Handle different operation return types
                # It could be a string (operation name), an object, or None
                if operation is None:
                    print("Operation returned None, assuming synchronous completion")
                    return file_search_store_name
                
                # If operation is a string, it's the operation name
                if isinstance(operation, str):
                    operation_name = operation
                    print(f"Operation is a string (name): {operation_name}")
                # If operation is an object, get its name
                elif hasattr(operation, 'name'):
                    operation_name = operation.name
                    print(f"Operation is an object with name: {operation_name}")
                else:
                    print(f"Operation type: {type(operation)}, attributes: {[attr for attr in dir(operation) if not attr.startswith('_')]}")
                    # Try to get operation name from the object
                    operation_name = str(operation)
                    print(f"Using operation as string: {operation_name}")
                
                # Get the operation object to check status
                # operations.get() expects a string (operation name), not an object
                try:
                    operation_obj = self.client.operations.get(operation_name)
                    print(f"Retrieved operation object. Type: {type(operation_obj)}")
                except Exception as e:
                    print(f"Error getting operation object: {e}")
                    import traceback
                    traceback.print_exc()
                    # If we can't get the operation, assume it completed synchronously
                    return file_search_store_name
                
                # Wait until import is complete with timeout
                max_wait_time = 300  # 5 minutes max wait
                wait_time = 0
                check_interval = 2  # Check every 2 seconds
                
                # Check if operation has a 'done' attribute
                if not hasattr(operation_obj, 'done'):
                    print("Operation object doesn't have 'done' attribute. Checking for completion status...")
                    # Check other possible status attributes
                    if hasattr(operation_obj, 'response'):
                        print("Operation has response, assuming completed")
                        return file_search_store_name
                    else:
                        print("No done attribute found, assuming synchronous operation")
                        return file_search_store_name
                
                while not operation_obj.done:
                    if wait_time >= max_wait_time:
                        print(f"File upload operation timed out after {max_wait_time} seconds")
                        return None
                    
                    time.sleep(check_interval)
                    wait_time += check_interval
                    
                    try:
                        # Refresh operation status using the operation name (string)
                        operation_obj = self.client.operations.get(operation_name)
                        print(f"Operation status: done={operation_obj.done}, wait_time={wait_time}s")
                        
                        # Check if operation failed
                        if hasattr(operation_obj, 'error') and operation_obj.error:
                            print(f"Operation error detected: {operation_obj.error}")
                            return None
                            
                    except Exception as e:
                        print(f"Error checking operation status: {e}")
                        import traceback
                        traceback.print_exc()
                        # If we can't check status, assume it might have completed
                        # But log the error
                        if wait_time > 60:  # If we've waited more than a minute, give up
                            return None
                
                print(f"File upload operation completed after {wait_time} seconds")
                
                # Check for errors in final operation object
                if hasattr(operation_obj, 'error') and operation_obj.error:
                    print(f"File upload operation failed: {operation_obj.error}")
                    return None
                
                # Operation completed successfully
                return file_search_store_name
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        except Exception as e:
            print(f"Error uploading file to Gemini: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def search_and_respond(self, prompt: str, file_search_store_names: List[str]) -> str:
        """Use Gemini with File Search tool to respond to prompt"""
        try:
            # Generate content using File Search
            print(f"Searching for {file_search_store_names} in Gemini...")
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[
                        types.Tool(
                            file_search=types.FileSearch(
                                file_search_store_names=file_search_store_names
                            )
                        )
                    ]
                )
            )
            
            return response.text
        except Exception as e:
            print(f"Error in Gemini search: {e}")
            import traceback
            traceback.print_exc()
            raise Exception(f"Error processing prompt with Gemini: {str(e)}")


gemini_client = GeminiFileSearchClient()

