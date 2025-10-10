#!/usr/bin/env python3
"""
Prontivus Backend Server Starter
Simple script to start the FastAPI backend server
"""

import sys
import os

# Add the parent directory to the path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Start the Uvicorn server"""
    import uvicorn
    
    # Get port from environment variable (for Render/production) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    
    # Check if running in production
    is_production = os.environ.get("APP_ENV", "development") == "production"
    
    print("\n" + "="*60)
    print("  Starting Prontivus Backend Server")
    print("="*60 + "\n")
    
    print(f"Environment: {'Production' if is_production else 'Development'}")
    print(f"Server will run on: http://0.0.0.0:{port}")
    print(f"Health Check: http://0.0.0.0:{port}/health")
    if not is_production:
        print(f"API Documentation: http://localhost:{port}/docs")
    print("\n" + "="*60)
    print("  Press CTRL+C to stop the server")
    print("="*60 + "\n")
    
    try:
        # Start Uvicorn server
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=not is_production,  # Only reload in development
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("  Server stopped by user")
        print("="*60 + "\n")
        sys.exit(0)
    except Exception as e:
        print(f"\nError starting server: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure you're in the backend directory")
        print("  2. Check if .env file exists")
        print("  3. Install dependencies: pip install -r requirements.txt")
        print("  4. Check if port 8000 is available\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
