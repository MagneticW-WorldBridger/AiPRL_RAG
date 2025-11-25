#!/usr/bin/env python3
"""Test script to verify configuration and dependencies"""
import os
import sys

# Set environment variables for testing
os.environ["AUTH_BASE_URL"] = "https://aiprlauth-production.up.railway.app"
os.environ["DATABASE_URL"] = "postgres://tsdbadmin:d2aovsc4w6z2rtjq@ceb6gweqsj.fqypwv4b4k.tsdb.cloud.timescale.com:36773/tsdb?sslmode=require"
os.environ["GEMINI_API_KEY"] = "AIzaSyByCLw3aXwulRHPKckkPxsHSmJYEpXQDc4"

print("Testing configuration...")
print("=" * 50)

try:
    from config import settings
    print(f"✓ Config loaded")
    print(f"  AUTH_BASE_URL: {settings.auth_base_url}")
    print(f"  DATABASE_URL: {'✓ Set' if settings.database_url else '✗ Missing'}")
    print(f"  GEMINI_API_KEY: {'✓ Set' if settings.gemini_api_key else '✗ Missing'}")
except Exception as e:
    print(f"✗ Config error: {e}")
    sys.exit(1)

print("\nTesting database connection...")
try:
    from database import get_engine, init_db
    engine = get_engine()
    print(f"✓ Database engine created")
    init_db()
    print(f"✓ Database initialized")
except Exception as e:
    print(f"✗ Database error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTesting Gemini client...")
try:
    from gemini_client import gemini_client
    print(f"✓ Gemini client initialized")
except Exception as e:
    print(f"✗ Gemini client error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\nTesting auth client...")
try:
    from auth_client import auth_client
    print(f"✓ Auth client initialized")
    print(f"  Auth base URL: {auth_client.base_url}")
except Exception as e:
    print(f"✗ Auth client error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 50)
print("✓ All tests passed! Configuration looks good.")
print("\nYou can now run: uvicorn main:app --host 0.0.0.0 --port 8000")

