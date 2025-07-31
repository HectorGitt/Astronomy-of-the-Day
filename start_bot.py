#!/usr/bin/env python3
"""
Quick start script for Engagement Bot only.
Equivalent to: python start_dashboard.py 2
"""

import subprocess
import sys


def main():
    """Start Engagement Bot only."""
    print("🤖 Quick Starting Engagement Bot...")
    print("Press Ctrl+C to stop")

    try:
        subprocess.run([sys.executable, "start_dashboard.py", "2"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Engagement Bot stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ start_dashboard.py not found!")
        print("Make sure you're running this from the correct directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
