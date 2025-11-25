import httpx
from typing import Optional
from config import settings


class AuthClient:
    def __init__(self):
        self.base_url = settings.auth_base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def verify_token(self, token: str) -> Optional[dict]:
        """Verify token with auth service and get user info"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.client.post(
                f"{self.base_url}/auth/verify",
                headers=headers
            )
            
            # Log response for debugging
            print(f"Auth verify response status: {response.status_code}")
            print(f"Auth verify response: {response.text[:200]}")  # First 200 chars
            
            if response.status_code == 200:
                verify_result = response.json()
                # Check if token is valid
                is_valid = verify_result.get("valid") == "true" or verify_result.get("valid") == True
                
                if not is_valid:
                    print("Token validation returned false")
                    return None
                
                # If token is valid, get user info from /auth/me
                print("Token is valid, fetching user info from /auth/me...")
                user_info = await self.get_user_info(token)
                return user_info
            
            return None
        except httpx.RequestError as e:
            print(f"Auth verification request error: {e}")
            return None
        except Exception as e:
            print(f"Auth verification error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_user_info(self, token: str) -> Optional[dict]:
        """Get current user info from /auth/me"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.client.get(
                f"{self.base_url}/auth/me",
                headers=headers
            )
            
            # Log response for debugging
            print(f"Auth /me response status: {response.status_code}")
            print(f"Auth /me response: {response.text[:200]}")  # First 200 chars
            
            if response.status_code == 200:
                return response.json()
            return None
        except httpx.RequestError as e:
            print(f"Get user info request error: {e}")
            return None
        except Exception as e:
            print(f"Get user info error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def close(self):
        await self.client.aclose()


auth_client = AuthClient()

