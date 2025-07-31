#!/usr/bin/env python3
"""
Quick start script for API Server only.
Equivalent to: python start_dashboard.py 1
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Start API Server only."""
    print("🚀 Quick Starting API Server...")
    print("Dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop")

    try:
        subprocess.run([sys.executable, "start_dashboard.py", "1"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 API Server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ start_dashboard.py not found!")
        print("Make sure you're running this from the correct directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
