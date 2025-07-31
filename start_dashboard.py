#!/usr/bin/env python3
"""
Startup script for the Astronomy Bot API Dashboard.

Run this script to start both the engagement bot and the API server.

Usage:
    python start_dashboard.py                    # Interactive mode
    python start_dashboard.py 1                  # API Server only
    python start_dashboard.py 2                  # Engagement Bot only
    python start_dashboard.py 3                  # Both services
    python start_dashboard.py --api              # API Server only (alias)
    python start_dashboard.py --bot              # Engagement Bot only (alias)
    python start_dashboard.py --both             # Both services (alias)
"""

import subprocess
import sys
import time
import threading
import argparse
from pathlib import Path


def start_api_server():
    """Start the API server."""
    print("🚀 Starting API Server...")
    try:
        subprocess.run([sys.executable, "api_server.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 API Server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ API Server error: {e}")


def start_engagement_bot():
    """Start the engagement bot."""
    print("🤖 Starting Engagement Bot...")
    try:
        subprocess.run([sys.executable, "engagement.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Engagement Bot stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Engagement Bot error: {e}")


def check_env_file():
    """Check if .env file exists."""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  Warning: .env file not found!")
        print("Please copy .env.example to .env and configure your API keys.")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            sys.exit(1)


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import flask
        import tweepy
        import openai

        print("✅ All dependencies found")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Astronomy Bot Dashboard Startup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_dashboard.py           # Interactive mode
  python start_dashboard.py 1         # API Server only
  python start_dashboard.py 2         # Engagement Bot only  
  python start_dashboard.py 3         # Both services
  python start_dashboard.py --api     # API Server only
  python start_dashboard.py --bot     # Engagement Bot only
  python start_dashboard.py --both    # Both services
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "choice",
        nargs="?",
        choices=["1", "2", "3", "4"],
        help="Startup mode: 1=API only, 2=Bot only, 3=Both, 4=Exit",
    )
    group.add_argument("--api", action="store_true", help="Start API Server only")
    group.add_argument("--bot", action="store_true", help="Start Engagement Bot only")
    group.add_argument("--both", action="store_true", help="Start both services")

    return parser.parse_args()


def get_startup_choice():
    """Get the startup choice from arguments or interactive input."""
    args = parse_arguments()

    # Convert named arguments to numeric choices
    if args.api:
        return "1"
    elif args.bot:
        return "2"
    elif args.both:
        return "3"
    elif args.choice:
        return args.choice
    else:
        # Interactive mode
        return None


def run_startup_mode(choice: str):
    """Run the selected startup mode."""
    if choice == "1":
        print("\n🚀 Starting API Server only...")
        print("Dashboard will be available at: http://localhost:5000")
        print("Press Ctrl+C to stop")
        start_api_server()

    elif choice == "2":
        print("\n🤖 Starting Engagement Bot only...")
        print("Press Ctrl+C to stop")
        start_engagement_bot()

    elif choice == "3":
        print("\n🚀 Starting both API Server and Engagement Bot...")
        print("Dashboard will be available at: http://localhost:5000")
        print("Press Ctrl+C to stop both services")

        # Start API server in a separate thread
        api_thread = threading.Thread(target=start_api_server, daemon=True)
        api_thread.start()

        # Give API server time to start
        time.sleep(2)

        # Start engagement bot in main thread
        try:
            start_engagement_bot()
        except KeyboardInterrupt:
            print("\n🛑 Shutting down all services...")

    elif choice == "4":
        print("👋 Goodbye!")
        sys.exit(0)

    else:
        print("❌ Invalid choice. Please try again.")
        return False

    return True


def main():
    """Main startup function."""
    print("=" * 50)
    print("🌌 Astronomy Bot Dashboard Startup")
    print("=" * 50)

    # Check environment and dependencies
    # check_env_file()
    check_dependencies()

    # Get startup choice from args or interactive input
    choice = get_startup_choice()

    if choice:
        # Non-interactive mode
        run_startup_mode(choice)
    else:
        # Interactive mode
        while True:
            print("\nChoose startup mode:")
            print("1. API Server only (Dashboard UI)")
            print("2. Engagement Bot only")
            print("3. Both API Server and Engagement Bot")
            print("4. Exit")

            choice = input("\nEnter your choice (1-4): ").strip()

            if run_startup_mode(choice):
                break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Startup error: {e}")
        sys.exit(1)
