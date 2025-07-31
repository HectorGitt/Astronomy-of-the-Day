#!/usr/bin/env python3
"""
API Server for Astronomy of the Day Engagement Bot.

Provides REST API endpoints and web UI to view tweets, replies, and reposts.
"""

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import json
import tweepy
from datetime import datetime, timedelta
from pathlib import Path
from decouple import config
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
API_CONFIG = {
    "host": config("API_HOST", default="localhost"),
    "port": config("API_PORT", default=5000, cast=int),
    "debug": config("API_DEBUG", default=False, cast=bool),
}

# File paths
PROCESSED_FILE = Path("processed_interactions.json")
CACHE_FILE = Path("api_cache.json")


class TwitterAPI:
    def __init__(self):
        """Initialize Twitter API client."""
        self.client = tweepy.Client(
            bearer_token=config("BEARER_TOKEN"),
            consumer_key=config("CONSUMER_KEY"),
            consumer_secret=config("CONSUMER_SECRET"),
            access_token=config("ACCESS_TOKEN"),
            access_token_secret=config("ACCESS_TOKEN_SECRET"),
        )

        # Get bot user info
        try:
            self.bot_user = self.client.get_me()
            if hasattr(self.bot_user, "data") and self.bot_user.data:
                self.bot_user_id = self.bot_user.data.id
                self.bot_username = self.bot_user.data.username
            else:
                self.bot_user_id = self.bot_user.id
                self.bot_username = self.bot_user.username
            logger.info(f"API initialized for user: @{self.bot_username}")
        except Exception as e:
            logger.error(f"Failed to initialize Twitter API: {e}")
            raise

    def get_recent_tweets(self, hours: int = 24, max_results: int = 50) -> List[Dict]:
        """Get recent tweets from the bot."""
        try:
            tweets = self.client.get_users_tweets(
                id=self.bot_user_id,
                max_results=min(max_results, 100),
                tweet_fields=[
                    "created_at",
                    "public_metrics",
                    "conversation_id",
                    "author_id",
                ],
                expansions=["author_id"],
            )

            if not tweets.data:
                return []

            # Filter by time
            since_time = datetime.now() - timedelta(hours=hours)
            recent_tweets = []

            for tweet in tweets.data:
                if (
                    tweet.created_at
                    and tweet.created_at.replace(tzinfo=None) >= since_time
                ):
                    tweet_data = {
                        "id": tweet.id,
                        "text": tweet.text,
                        "created_at": tweet.created_at.isoformat()
                        if tweet.created_at
                        else None,
                        "conversation_id": tweet.conversation_id,
                        "public_metrics": {
                            "retweet_count": tweet.public_metrics.get(
                                "retweet_count", 0
                            ),
                            "like_count": tweet.public_metrics.get("like_count", 0),
                            "reply_count": tweet.public_metrics.get("reply_count", 0),
                            "quote_count": tweet.public_metrics.get("quote_count", 0),
                        }
                        if tweet.public_metrics
                        else {},
                        "url": f"https://twitter.com/{self.bot_username}/status/{tweet.id}",
                    }
                    recent_tweets.append(tweet_data)

            return recent_tweets

        except Exception as e:
            logger.error(f"Error fetching recent tweets: {e}")
            return []

    def get_replies_for_tweet(self, tweet_id: str, conversation_id: str) -> List[Dict]:
        """Get replies for a specific tweet."""
        try:
            query = f"conversation_id:{conversation_id} -from:{self.bot_username}"

            replies = self.client.search_recent_tweets(
                query=query,
                max_results=100,
                tweet_fields=[
                    "created_at",
                    "author_id",
                    "in_reply_to_user_id",
                    "public_metrics",
                ],
                expansions=["author_id"],
            )

            if not replies.data:
                return []

            # Create user lookup dict
            users_dict = {}
            if replies.includes and "users" in replies.includes:
                for user in replies.includes["users"]:
                    users_dict[user.id] = {
                        "username": user.username,
                        "name": user.name,
                        "profile_image_url": getattr(user, "profile_image_url", ""),
                    }

            reply_data = []
            for reply in replies.data:
                author_info = users_dict.get(
                    reply.author_id,
                    {
                        "username": "unknown",
                        "name": "Unknown User",
                        "profile_image_url": "",
                    },
                )

                reply_info = {
                    "id": reply.id,
                    "text": reply.text,
                    "created_at": reply.created_at.isoformat()
                    if reply.created_at
                    else None,
                    "author": author_info,
                    "public_metrics": {
                        "retweet_count": reply.public_metrics.get("retweet_count", 0),
                        "like_count": reply.public_metrics.get("like_count", 0),
                        "reply_count": reply.public_metrics.get("reply_count", 0),
                    }
                    if reply.public_metrics
                    else {},
                    "url": f"https://twitter.com/{author_info['username']}/status/{reply.id}",
                }
                reply_data.append(reply_info)

            return reply_data

        except Exception as e:
            logger.error(f"Error fetching replies for tweet {tweet_id}: {e}")
            return []

    def get_reposts_for_tweet(self, tweet_id: str) -> List[Dict]:
        """Get reposts/retweets for a specific tweet."""
        try:
            # Search for retweets and quote tweets
            query = f"url:{tweet_id} OR retweets_of:{self.bot_user_id}"

            reposts = self.client.search_recent_tweets(
                query=query,
                max_results=100,
                tweet_fields=[
                    "created_at",
                    "author_id",
                    "referenced_tweets",
                    "public_metrics",
                ],
                expansions=["author_id", "referenced_tweets.id"],
            )

            if not reposts.data:
                return []

            # Create user lookup dict
            users_dict = {}
            if reposts.includes and "users" in reposts.includes:
                for user in reposts.includes["users"]:
                    users_dict[user.id] = {
                        "username": user.username,
                        "name": user.name,
                        "profile_image_url": getattr(user, "profile_image_url", ""),
                    }

            repost_data = []
            for repost in reposts.data:
                # Skip bot's own reposts
                if repost.author_id == self.bot_user_id:
                    continue

                author_info = users_dict.get(
                    repost.author_id,
                    {
                        "username": "unknown",
                        "name": "Unknown User",
                        "profile_image_url": "",
                    },
                )

                repost_info = {
                    "id": repost.id,
                    "text": repost.text,
                    "created_at": repost.created_at.isoformat()
                    if repost.created_at
                    else None,
                    "author": author_info,
                    "is_retweet": bool(
                        repost.referenced_tweets
                        and any(
                            ref.type == "retweeted" for ref in repost.referenced_tweets
                        )
                    ),
                    "is_quote_tweet": bool(
                        repost.referenced_tweets
                        and any(
                            ref.type == "quoted" for ref in repost.referenced_tweets
                        )
                    ),
                    "public_metrics": {
                        "retweet_count": repost.public_metrics.get("retweet_count", 0),
                        "like_count": repost.public_metrics.get("like_count", 0),
                        "reply_count": repost.public_metrics.get("reply_count", 0),
                    }
                    if repost.public_metrics
                    else {},
                    "url": f"https://twitter.com/{author_info['username']}/status/{repost.id}",
                }
                repost_data.append(repost_info)

            return repost_data

        except Exception as e:
            logger.error(f"Error fetching reposts for tweet {tweet_id}: {e}")
            return []


# Initialize Twitter API
try:
    twitter_api = TwitterAPI()
except Exception as e:
    logger.error(f"Failed to initialize Twitter API: {e}")
    twitter_api = None


def load_processed_interactions() -> Dict:
    """Load processed interactions from file."""
    if PROCESSED_FILE.exists():
        try:
            with open(PROCESSED_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading processed interactions: {e}")
    return {"replied_to": [], "commented_reposts": []}


# API Routes
@app.route("/")
def index():
    """Serve the main UI."""
    return render_template("index.html")


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "twitter_api_available": twitter_api is not None,
        }
    )


@app.route("/api/stats")
def get_stats():
    """Get bot statistics."""
    processed = load_processed_interactions()

    stats = {
        "total_replies_processed": len(processed.get("replied_to", [])),
        "total_reposts_processed": len(processed.get("commented_reposts", [])),
        "bot_username": twitter_api.bot_username if twitter_api else "unknown",
        "last_updated": datetime.now().isoformat(),
    }

    return jsonify(stats)


@app.route("/api/tweets")
def get_tweets():
    """Get recent tweets with optional parameters."""
    if not twitter_api:
        return jsonify({"error": "Twitter API not available"}), 500

    hours = request.args.get("hours", 24, type=int)
    max_results = request.args.get("max_results", 50, type=int)

    tweets = twitter_api.get_recent_tweets(hours=hours, max_results=max_results)

    return jsonify(
        {
            "tweets": tweets,
            "count": len(tweets),
            "hours": hours,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/tweets/<tweet_id>/replies")
def get_tweet_replies(tweet_id: str):
    """Get replies for a specific tweet."""
    if not twitter_api:
        return jsonify({"error": "Twitter API not available"}), 500

    conversation_id = request.args.get("conversation_id", tweet_id)
    replies = twitter_api.get_replies_for_tweet(tweet_id, conversation_id)

    return jsonify(
        {
            "tweet_id": tweet_id,
            "replies": replies,
            "count": len(replies),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/tweets/<tweet_id>/reposts")
def get_tweet_reposts(tweet_id: str):
    """Get reposts for a specific tweet."""
    if not twitter_api:
        return jsonify({"error": "Twitter API not available"}), 500

    reposts = twitter_api.get_reposts_for_tweet(tweet_id)

    return jsonify(
        {
            "tweet_id": tweet_id,
            "reposts": reposts,
            "count": len(reposts),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/tweets/<tweet_id>/engagement")
def get_tweet_engagement(tweet_id: str):
    """Get complete engagement data for a tweet (replies + reposts)."""
    if not twitter_api:
        return jsonify({"error": "Twitter API not available"}), 500

    conversation_id = request.args.get("conversation_id", tweet_id)

    # Get replies and reposts concurrently
    replies = twitter_api.get_replies_for_tweet(tweet_id, conversation_id)
    reposts = twitter_api.get_reposts_for_tweet(tweet_id)

    # Check which have been processed
    processed = load_processed_interactions()
    processed_replies = set(processed.get("replied_to", []))
    processed_reposts = set(processed.get("commented_reposts", []))

    # Mark processed status
    for reply in replies:
        reply["bot_replied"] = reply["id"] in processed_replies

    for repost in reposts:
        repost["bot_commented"] = repost["id"] in processed_reposts

    return jsonify(
        {
            "tweet_id": tweet_id,
            "replies": {
                "data": replies,
                "count": len(replies),
                "processed_count": sum(1 for r in replies if r["bot_replied"]),
            },
            "reposts": {
                "data": reposts,
                "count": len(reposts),
                "processed_count": sum(1 for r in reposts if r["bot_commented"]),
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/processed")
def get_processed_interactions():
    """Get all processed interactions."""
    processed = load_processed_interactions()

    return jsonify(
        {
            "processed_interactions": processed,
            "stats": {
                "replied_to_count": len(processed.get("replied_to", [])),
                "commented_reposts_count": len(processed.get("commented_reposts", [])),
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/logs")
def get_logs():
    """Get recent log entries."""
    log_type = request.args.get("type", "main")  # main, errors, daily
    lines = request.args.get("lines", 100, type=int)

    log_files = {
        "main": "logs/astronomy_bot.log",
        "errors": "logs/astronomy_bot_errors.log",
        "daily": "logs/astronomy_bot_daily.log",
    }

    log_file = log_files.get(log_type, log_files["main"])

    try:
        if not Path(log_file).exists():
            return jsonify({"logs": [], "message": f"Log file {log_file} not found"})

        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if lines > 0 else all_lines

        # Parse log lines into structured data
        parsed_logs = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue

            # Try to parse the log format: timestamp - name - level - function:line - message
            parts = line.split(" - ", 4)
            if len(parts) >= 5:
                parsed_logs.append(
                    {
                        "timestamp": parts[0],
                        "logger": parts[1],
                        "level": parts[2],
                        "location": parts[3],
                        "message": parts[4],
                        "raw": line,
                    }
                )
            else:
                # Fallback for lines that don't match expected format
                parsed_logs.append(
                    {
                        "timestamp": "",
                        "logger": "",
                        "level": "INFO",
                        "location": "",
                        "message": line,
                        "raw": line,
                    }
                )

        return jsonify(
            {
                "logs": parsed_logs,
                "type": log_type,
                "file": log_file,
                "count": len(parsed_logs),
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {e}")
        return jsonify({"error": f"Failed to read log file: {str(e)}"}), 500


@app.route("/api/bot-responses")
def get_bot_responses():
    """Get recent bot responses with context."""
    max_results = request.args.get("max_results", 50, type=int)

    try:
        processed = load_processed_interactions()

        # Get recent responses from processed data
        responses = []

        # Add replied-to interactions
        for reply_id in processed.get("replied_to", []):
            responses.append(
                {
                    "id": reply_id,
                    "type": "reply",
                    "action": "Bot replied to tweet",
                    "timestamp": processed.get("replied_to_timestamps", {}).get(
                        reply_id
                    ),
                    "status": "completed",
                    "tweet_url": f"https://twitter.com/user/status/{reply_id}",
                }
            )

        # Add commented reposts
        for repost_id in processed.get("commented_reposts", []):
            responses.append(
                {
                    "id": repost_id,
                    "type": "repost_comment",
                    "action": "Bot commented on repost",
                    "timestamp": processed.get("commented_reposts_timestamps", {}).get(
                        repost_id
                    ),
                    "status": "completed",
                    "tweet_url": f"https://twitter.com/user/status/{repost_id}",
                }
            )

        # Sort by timestamp (most recent first)
        responses.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        # Limit results
        responses = responses[:max_results]

        return jsonify(
            {
                "responses": responses,
                "count": len(responses),
                "stats": {
                    "total_replies": len(processed.get("replied_to", [])),
                    "total_repost_comments": len(
                        processed.get("commented_reposts", [])
                    ),
                    "total_responses": len(processed.get("replied_to", []))
                    + len(processed.get("commented_reposts", [])),
                },
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting bot responses: {e}")
        return jsonify({"error": f"Failed to get bot responses: {str(e)}"}), 500


if __name__ == "__main__":
    logger.info(f"Starting API server on {API_CONFIG['host']}:{API_CONFIG['port']}")
    app.run(
        host=str(API_CONFIG["host"]),
        port=int(API_CONFIG["port"]),
        debug=bool(API_CONFIG["debug"]),
    )
