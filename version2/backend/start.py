#!/usr/bin/env python3
"""
DataSage AI Backend Startup Script
"""
import uvicorn
import os
import sys
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    
    print(f"Starting DataSage AI Backend...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"MongoDB URL: {os.getenv('MONGODB_URL', 'mongodb://localhost:27017')}")
    print(f"Database: {os.getenv('DATABASE_NAME', 'datasage_ai')}")
    
    # Start the server
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )



