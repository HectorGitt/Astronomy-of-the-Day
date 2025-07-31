#!/usr/bin/env python3
"""
Production deployment script for both services.
Equivalent to: python start_dashboard.py 3
"""

import subprocess
import sys


def main():
    """Start both API Server and Engagement Bot."""
    print("🚀 Production Deployment Starting...")
    print("Starting both API Server and Engagement Bot")
    print("Dashboard will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop all services")

    try:
        subprocess.run([sys.executable, "start_dashboard.py", "3"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 All services stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ start_dashboard.py not found!")
        print("Make sure you're running this from the correct directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
