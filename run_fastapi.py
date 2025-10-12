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

    # Get port from environment variable (for cloud deployments)
    port = int(os.getenv("PORT", 8000))

    # Run the server
    uvicorn.run(
        "fastapi_scheduler:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
