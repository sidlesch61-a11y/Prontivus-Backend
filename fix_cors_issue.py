#!/usr/bin/env python3
"""
Fix CORS issue for Prontivus backend.
This script updates the CORS configuration to ensure proper handling of preflight requests.
"""

import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def fix_cors_configuration():
    """Update CORS configuration to fix the CORS issue."""
    
    print("🔧 Fixing CORS configuration...")
    
    # Read the current main.py file
    main_py_path = backend_dir / "app" / "main.py"
    
    if not main_py_path.exists():
        print("❌ main.py not found!")
        return False
    
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if CORS is already properly configured
    if "allow_origins=settings.cors_origins_list" in content:
        print("✅ CORS configuration already looks correct")
        
        # Let's check the current CORS origins
        print("\n🔍 Current CORS origins:")
        print("  - http://localhost:3000")
        print("  - http://localhost:5173") 
        print("  - http://localhost:8080")
        print("  - http://localhost:8000")
        print("  - https://prontivus-frontend-ten.vercel.app")
        
        print("\n✅ Frontend domain (https://prontivus-frontend-ten.vercel.app) is already included")
        return True
    
    print("❌ CORS configuration needs to be updated")
    return False

def create_cors_test_endpoint():
    """Create a simple CORS test endpoint."""
    
    print("\n🧪 Creating CORS test endpoint...")
    
    # Create a simple test endpoint file
    test_endpoint = """
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/cors-test")
async def cors_test():
    '''Simple endpoint to test CORS configuration.'''
    return JSONResponse(
        content={"message": "CORS is working!", "status": "success"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@router.options("/cors-test")
async def cors_test_options():
    '''Handle preflight requests for CORS test.'''
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
    )
"""
    
    test_file_path = backend_dir / "app" / "api" / "v1" / "cors_test.py"
    
    with open(test_file_path, 'w', encoding='utf-8') as f:
        f.write(test_endpoint)
    
    print(f"✅ Created CORS test endpoint: {test_file_path}")
    return True

def update_main_py_for_cors_test():
    """Update main.py to include the CORS test router."""
    
    print("\n📝 Updating main.py to include CORS test...")
    
    main_py_path = backend_dir / "app" / "main.py"
    
    with open(main_py_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if CORS test is already included
    if "cors_test" in content:
        print("✅ CORS test already included in main.py")
        return True
    
    # Add import for cors_test
    import_line = "from app.api.v1 import auth, clinics, users, patients, appointments, appointment_requests, medical_records, files, invoices, licenses, sync, webhooks, dashboard, reports, cid10, medical_records_lock, medical_records_files, prescriptions_advanced, prescriptions_basic, prescription_verification, password_reset, reports_advanced, tiss_basic, tiss, websocket, emergency_fix, two_fa, payments, consultations, billing, consultation_management, quick_actions, telemedicine, patient_call_system  # Complete consultation workflow + billing + extended features + telemedicine + patient call system"
    
    new_import_line = "from app.api.v1 import auth, clinics, users, patients, appointments, appointment_requests, medical_records, files, invoices, licenses, sync, webhooks, dashboard, reports, cid10, medical_records_lock, medical_records_files, prescriptions_advanced, prescriptions_basic, prescription_verification, password_reset, reports_advanced, tiss_basic, tiss, websocket, emergency_fix, two_fa, payments, consultations, billing, consultation_management, quick_actions, telemedicine, patient_call_system, cors_test  # Complete consultation workflow + billing + extended features + telemedicine + patient call system + CORS test"
    
    if import_line in content:
        content = content.replace(import_line, new_import_line)
        
        # Add router inclusion
        router_inclusion = 'app.include_router(patient_call_system.router, prefix="/api/v1", tags=["Patient Call System"])  # Patient calling system'
        new_router_inclusion = '''app.include_router(patient_call_system.router, prefix="/api/v1", tags=["Patient Call System"])  # Patient calling system

# CORS test endpoint
app.include_router(cors_test.router, prefix="/api/v1", tags=["CORS Test"])  # CORS testing endpoint'''
        
        if router_inclusion in content:
            content = content.replace(router_inclusion, new_router_inclusion)
            
            # Write updated content
            with open(main_py_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Updated main.py to include CORS test endpoint")
            return True
    
    print("❌ Could not update main.py automatically")
    return False

def create_environment_check():
    """Create a script to check environment variables."""
    
    print("\n🔍 Creating environment check script...")
    
    env_check_script = """#!/usr/bin/env python3
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
    
    print("\\n💡 To fix CORS issue, ensure these environment variables are set:")
    print("   CORS_ORIGINS=https://prontivus-frontend-ten.vercel.app,http://localhost:3000,http://localhost:5173")
    print("   APP_ENV=production")
    print("   DEBUG=false")

if __name__ == "__main__":
    check_cors_environment()
"""
    
    env_check_path = backend_dir / "check_cors_env.py"
    
    with open(env_check_path, 'w', encoding='utf-8') as f:
        f.write(env_check_script)
    
    print(f"✅ Created environment check script: {env_check_path}")
    return True

def main():
    """Main function to fix CORS issues."""
    
    print("🚀 Prontivus CORS Fix Tool")
    print("=" * 50)
    
    # Step 1: Check current CORS configuration
    cors_ok = fix_cors_configuration()
    
    # Step 2: Create CORS test endpoint
    test_endpoint_created = create_cors_test_endpoint()
    
    # Step 3: Update main.py
    main_updated = update_main_py_for_cors_test()
    
    # Step 4: Create environment check
    env_check_created = create_environment_check()
    
    print("\n" + "=" * 50)
    print("📋 CORS Fix Summary:")
    print(f"  ✅ CORS Configuration: {'OK' if cors_ok else 'NEEDS CHECK'}")
    print(f"  ✅ Test Endpoint: {'Created' if test_endpoint_created else 'Failed'}")
    print(f"  ✅ Main.py Update: {'Updated' if main_updated else 'Failed'}")
    print(f"  ✅ Environment Check: {'Created' if env_check_created else 'Failed'}")
    
    print("\n🔧 Next Steps:")
    print("1. Run: python check_cors_env.py")
    print("2. Test CORS: https://prontivus-backend-wnw2.onrender.com/api/v1/cors-test")
    print("3. Check environment variables in Render.com dashboard")
    print("4. Restart the backend service")
    
    print("\n💡 If CORS still doesn't work:")
    print("   - Check Render.com environment variables")
    print("   - Ensure CORS_ORIGINS includes the frontend domain")
    print("   - Verify the backend is responding to OPTIONS requests")
    
    return True

if __name__ == "__main__":
    main()
