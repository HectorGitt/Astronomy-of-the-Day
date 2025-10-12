#!/usr/bin/env python3
"""
Run script for FastAPI Outfit Scheduler Server
"""

import os
import sys
import uvicorn
from pathlib import Path

# Add current directory to Python path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def main():
    """Start the FastAPI server"""
    print("🚀 Starting FastAPI Outfit Scheduler Server...")

    # Get port from environment variable (Cloud Run sets PORT, default to 8080)
    port = int(os.getenv("PORT", "8080"))
    print(f"📡 Listening on port {port}")
    print(f"🌐 Environment PORT variable: {os.getenv('PORT', 'not set')}")

    # Ensure we're binding to 0.0.0.0 for container environments
    host = "0.0.0.0"
    print(f"🏠 Binding to host: {host}")

    # Run the server
    uvicorn.run(
        "fastapi_scheduler:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True,
        server_header=False,  # Don't expose server info
        date_header=False,  # Don't expose date
    )


if __name__ == "__main__":
    main()
