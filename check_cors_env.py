#!/usr/bin/env python3
'''
Check environment variables for CORS configuration.
'''

import os

def check_cors_environment():
    print("🔍 Checking CORS environment variables...")
    
    # Check CORS_ORIGINS
    cors_origins = os.getenv("CORS_ORIGINS", "")
    print(f"CORS_ORIGINS: {cors_origins}")
    
    if "prontivus-frontend-ten.vercel.app" in cors_origins:
        print("✅ Frontend domain found in CORS_ORIGINS")
    else:
        print("❌ Frontend domain NOT found in CORS_ORIGINS")
        print("   Add: https://prontivus-frontend-ten.vercel.app")
    
    # Check if we're in production
    app_env = os.getenv("APP_ENV", "development")
    print(f"APP_ENV: {app_env}")
    
    # Check debug mode
    debug = os.getenv("DEBUG", "false")
    print(f"DEBUG: {debug}")
    
    print("\n💡 To fix CORS issue, ensure these environment variables are set:")
    print("   CORS_ORIGINS=https://prontivus-frontend-ten.vercel.app,http://localhost:3000,http://localhost:5173")
    print("   APP_ENV=production")
    print("   DEBUG=false")

if __name__ == "__main__":
    check_cors_environment()
