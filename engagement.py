#!/usr/bin/env python3
"""
Main engagement bot for Astronomy of the Day Twitter account.

This bot runs at different times of the day with configurable intervals and:
1. Replies to replies on the user's tweets
2. Comments on reposts/retweets of the user's content
3. Manages scheduled engagement activities

Author: GitHub Copilot Assistant
"""

import tweepy
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Set
from decouple import config
import random
import json
from pathlib import Path

from logging_config import setup_bot_logging

# Setup enhanced logging
logger = setup_bot_logging(debug_mode=False)


# Helper function to parse comma-separated keywords
def parse_blacklist_keywords():
    """Parse blacklist keywords from environment variable."""
    keywords_str = config(
        "BLACKLIST_KEYWORDS", default="spam,bot,fake,scam,crypto,nft,buy now"
    )
    if isinstance(keywords_str, str):
        return [keyword.strip() for keyword in keywords_str.split(",")]
    return ["spam", "bot", "fake", "scam", "crypto", "nft", "buy now"]


# Configuration from environment variables
ENGAGEMENT_CONFIG = {
    "reply_interval_minutes": config(
        "REPLY_INTERVAL_MINUTES", default=16, cast=int
    ),  # Check for new replies
    "repost_interval_minutes": config(
        "REPOST_INTERVAL_MINUTES", default=45, cast=int
    ),  # Check for reposts
    "max_replies_per_check": config(
        "MAX_REPLIES_PER_CHECK", default=5, cast=int
    ),  # Maximum replies to send per check
    "max_repost_comments_per_check": config(
        "MAX_REPOST_COMMENTS_PER_CHECK", default=3, cast=int
    ),  # Maximum repost comments per check
    "tweets_cache_minutes": config(
        "TWEETS_CACHE_MINUTES", default=15, cast=int
    ),  # Cache tweets for 15 minutes to avoid rate limits
    "engagement_hours": {  # Active hours for engagement (24-hour format)
        "start": config(
            "ENGAGEMENT_START_HOUR", default=8, cast=int
        ),  # Start hour (24-hour format)
        "end": config(
            "ENGAGEMENT_END_HOUR", default=22, cast=int
        ),  # End hour (24-hour format)
    },
    "weekend_reduced_activity": config(
        "WEEKEND_REDUCED_ACTIVITY", default=True, cast=bool
    ),  # Reduce activity on weekends
    "blacklist_keywords": parse_blacklist_keywords(),  # Don't engage with tweets containing these
}

# File to track processed interactions
PROCESSED_FILE = Path("processed_interactions.json")


class EngagementBot:
    def __init__(self):
        """Initialize the engagement bot with Twitter API credentials."""
        logger.info("=== Initializing Engagement Bot ===")

        # Load Twitter API credentials
        self.consumer_key = config("CONSUMER_KEY")
        self.consumer_secret = config("CONSUMER_SECRET")
        self.access_token = config("ACCESS_TOKEN")
        self.access_token_secret = config("ACCESS_TOKEN_SECRET")
        self.bearer_token = config("BEARER_TOKEN")

        # Create API objects
        auth = tweepy.OAuthHandler(self.consumer_key, self.consumer_secret)
        auth.set_access_token(self.access_token, self.access_token_secret)

        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
        )
        self.api = tweepy.API(auth=auth, wait_on_rate_limit=True)

        # Get bot's user ID
        try:
            self.bot_user = self.client.get_me()
            if hasattr(self.bot_user, "data") and self.bot_user.data:
                self.bot_user_id = self.bot_user.data.id
                self.bot_username = self.bot_user.data.username
            else:
                # Fallback for different response format
                self.bot_user_id = self.bot_user.id
                self.bot_username = self.bot_user.username
            logger.info(
                f"Bot initialized for user: @{self.bot_username} (ID: {self.bot_user_id})"
            )
        except Exception as e:
            logger.error(f"Failed to get bot user info: {e}")
            raise

        # Load processed interactions
        self.processed_interactions = self.load_processed_interactions()

        # Initialize tweet cache to avoid rate limiting get_users_tweets()
        self.tweets_cache = {
            "data": None,
            "timestamp": None,
            "cache_duration_minutes": ENGAGEMENT_CONFIG["tweets_cache_minutes"],
        }

        # Log current configuration
        logger.info("=== Current Bot Configuration ===")
        logger.info(
            f"Reply check interval: {ENGAGEMENT_CONFIG['reply_interval_minutes']} minutes"
        )
        logger.info(
            f"Repost check interval: {ENGAGEMENT_CONFIG['repost_interval_minutes']} minutes"
        )
        logger.info(
            f"Max replies per check: {ENGAGEMENT_CONFIG['max_replies_per_check']}"
        )
        logger.info(
            f"Max repost comments per check: {ENGAGEMENT_CONFIG['max_repost_comments_per_check']}"
        )
        logger.info(
            f"Tweet cache duration: {ENGAGEMENT_CONFIG['tweets_cache_minutes']} minutes"
        )
        logger.info(
            f"Active hours: {ENGAGEMENT_CONFIG['engagement_hours']['start']}:00 - {ENGAGEMENT_CONFIG['engagement_hours']['end']}:00"
        )
        logger.info(
            f"Weekend reduced activity: {ENGAGEMENT_CONFIG['weekend_reduced_activity']}"
        )
        logger.info(
            f"Blacklisted keywords: {', '.join(ENGAGEMENT_CONFIG['blacklist_keywords'])}"
        )

        logger.info("=== Engagement Bot Initialization Complete ===")

    def load_processed_interactions(self) -> Dict[str, Set[str]]:
        """Load previously processed interactions from file."""
        if PROCESSED_FILE.exists():
            try:
                with open(PROCESSED_FILE, "r") as f:
                    data = json.load(f)
                    # Convert lists back to sets for faster lookup
                    return {
                        "replied_to": set(data.get("replied_to", [])),
                        "commented_reposts": set(data.get("commented_reposts", [])),
                    }
            except Exception as e:
                logger.error(f"Error loading processed interactions: {e}")

        return {"replied_to": set(), "commented_reposts": set()}

    def save_processed_interactions(self):
        """Save processed interactions to file."""
        try:
            data = {
                "replied_to": list(self.processed_interactions["replied_to"]),
                "commented_reposts": list(
                    self.processed_interactions["commented_reposts"]
                ),
            }
            with open(PROCESSED_FILE, "w") as f:
                json.dump(data, f, indent=2)
            logger.debug("Processed interactions saved successfully")
        except Exception as e:
            logger.error(f"Error saving processed interactions: {e}")

    def is_engagement_time(self) -> bool:
        """Check if current time is within engagement hours."""
        now = datetime.now()
        current_hour = now.hour

        # Check if within active hours
        start_hour = ENGAGEMENT_CONFIG["engagement_hours"]["start"]
        end_hour = ENGAGEMENT_CONFIG["engagement_hours"]["end"]

        if not (start_hour <= current_hour <= end_hour):
            logger.debug(f"Outside engagement hours ({start_hour}:00-{end_hour}:00)")
            return False

        # Check weekend reduced activity
        if (
            ENGAGEMENT_CONFIG["weekend_reduced_activity"] and now.weekday() >= 5
        ):  # Saturday=5, Sunday=6
            # Reduce weekend activity by 50%
            if random.random() < 0.5:
                logger.debug("Weekend reduced activity - skipping this cycle")
                return False

        return True

    def contains_blacklisted_keywords(self, text: str) -> bool:
        """Check if text contains any blacklisted keywords."""
        text_lower = text.lower()
        for keyword in ENGAGEMENT_CONFIG["blacklist_keywords"]:
            if keyword in text_lower:
                logger.debug(f"Blacklisted keyword '{keyword}' found in text")
                return True
        return False

    def generate_reply_message(self, original_tweet: str, reply_tweet: str) -> str:
        """Generate an engaging reply message using AI."""
        logger.debug("Generating AI reply message")

        # Fallback responses
        fallback_replies = [
            "Thanks for your interest in space exploration! 🚀",
            "Great observation! The universe never ceases to amaze ✨",
            "Appreciate your engagement with astronomy content! 🌟",
            "Fascinating perspective! Space science is full of wonders 🔭",
            "Thanks for sharing your thoughts on this cosmic wonder! 🌌",
        ]

        try:
            from openai import OpenAI

            openai_api_key = config("OPENAI_API_KEY", default="", cast=str)
            if not openai_api_key:
                logger.error("OpenAI API key not found")
                return random.choice(fallback_replies)

            openai_client = OpenAI(api_key=openai_api_key)

            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are the Astronomy of the Day Twitter bot. Generate friendly, educational replies to people who comment on astronomy posts. 

GUIDELINES:
✨ Be warm, welcoming, and encouraging
✨ Keep replies under 200 characters
✨ Share interesting space facts when relevant
✨ Ask thoughtful questions to encourage discussion
✨ Use 1-2 emojis maximum
✨ Be educational but not condescending
✨ Match the tone of the original reply

EXAMPLES:
- "Great question! The colors you see are actually different temperatures of gas - blue is hottest! 🔥"
- "Exactly! It's amazing how perspective changes everything in space photography ✨"
- "That's a wonderful observation! Have you ever tried stargazing in your area?"
""",
                    },
                    {
                        "role": "user",
                        "content": f"Original astronomy post: {original_tweet[:200]}\n\nUser's reply: {reply_tweet}\n\nGenerate a friendly, educational reply:",
                    },
                ],
                max_tokens=100,
                temperature=0.8,
            )

            reply = completion.choices[0].message.content.strip()
            logger.info(f"Generated reply: {reply}")
            return reply

        except Exception as e:
            logger.error(f"Error generating AI reply: {e}")
            # Fallback responses
            fallback_replies = [
                "Thanks for your interest in space exploration! 🚀",
                "Great observation! The universe never ceases to amaze ✨",
                "Appreciate your engagement with astronomy content! 🌟",
                "Fascinating perspective! Space science is full of wonders 🔭",
                "Thanks for sharing your thoughts on this cosmic wonder! 🌌",
            ]
            return random.choice(fallback_replies)

    def generate_repost_comment(self, original_tweet: str) -> str:
        """Generate a comment for reposts/retweets."""
        logger.debug("Generating repost comment")

        try:
            from openai import OpenAI

            openai_client = OpenAI(api_key=config("OPENAI_API_KEY"))

            completion = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are the Astronomy of the Day Twitter bot. Generate short, appreciative comments for people who repost your astronomy content.

GUIDELINES:
✨ Express genuine gratitude
✨ Keep under 150 characters
✨ Add a space fact or fun detail
✨ Use 1-2 emojis maximum
✨ Encourage space curiosity

EXAMPLES:
- "Thanks for sharing the cosmic wonder! 🌟 Did you know this nebula is 7,000 light-years away?"
- "Appreciate you spreading astronomy love! ✨ This image took 12 hours to capture!"
- "Thank you for the repost! 🚀 Fun fact: You can sometimes see this with binoculars!"
""",
                    },
                    {
                        "role": "user",
                        "content": f"Original astronomy post that was reposted: {original_tweet[:200]}\n\nGenerate a grateful comment with space fact:",
                    },
                ],
                max_tokens=80,
                temperature=0.8,
            )

            comment = completion.choices[0].message.content.strip()
            logger.info(f"Generated repost comment: {comment}")
            return comment

        except Exception as e:
            logger.error(f"Error generating repost comment: {e}")
            # Fallback comments
            fallback_comments = [
                "Thanks for sharing this cosmic beauty! 🌟",
                "Appreciate you spreading astronomy wonder! ✨",
                "Thank you for the repost! The universe is amazing 🚀",
                "Grateful for sharing space exploration content! 🔭",
                "Thanks for helping others discover cosmic wonders! 🌌",
            ]
            return random.choice(fallback_comments)

    def clear_tweets_cache(self):
        """Clear the tweets cache to force fresh API call."""
        logger.debug("Clearing tweets cache")
        self.tweets_cache["data"] = None
        self.tweets_cache["timestamp"] = None

    def is_cache_valid(self) -> bool:
        """Check if the tweets cache is still valid."""
        if self.tweets_cache["data"] is None or self.tweets_cache["timestamp"] is None:
            return False

        current_time = datetime.now()
        cache_age_seconds = (
            current_time - self.tweets_cache["timestamp"]
        ).total_seconds()
        cache_duration_seconds = self.tweets_cache["cache_duration_minutes"] * 60

        return cache_age_seconds < cache_duration_seconds

    def get_recent_bot_tweets(self, hours: int = 24) -> List[tweepy.Tweet]:
        """Get bot's recent tweets from the last N hours with caching to avoid rate limits."""
        logger.info(f"Fetching bot's tweets from last {hours} hours")

        current_time = datetime.now()

        # Check if we have valid cached data
        if self.is_cache_valid():
            logger.info(
                f"Using cached tweet data (valid for {self.tweets_cache['cache_duration_minutes']} minutes)"
            )
            cached_tweets = self.tweets_cache["data"]

            # Filter cached tweets within the requested time range
            since_time = current_time - timedelta(hours=hours)
            recent_tweets = []

            for tweet in cached_tweets:
                if (
                    tweet.created_at
                    and tweet.created_at.replace(tzinfo=None) >= since_time
                ):
                    recent_tweets.append(tweet)

            logger.info(f"Found {len(recent_tweets)} recent tweets from cache")
            return recent_tweets

        # Cache is invalid or doesn't exist, make API call
        logger.info("Cache expired or empty, making API call to get_users_tweets")

        try:
            # Calculate time threshold for API call (get more data to cache)
            since_time = current_time - timedelta(hours=hours)

            # Get user's recent tweets
            tweets = self.client.get_users_tweets(
                id=self.bot_user_id,
                max_results=100,  # Get more tweets to cache for longer
                tweet_fields=["created_at", "public_metrics", "conversation_id"],
            )

            if not tweets.data:
                logger.info("No recent tweets found")
                return []

            # Cache all retrieved tweets
            self.tweets_cache["data"] = tweets.data
            self.tweets_cache["timestamp"] = current_time
            logger.info(
                f"Cached {len(tweets.data)} tweets for {self.tweets_cache['cache_duration_minutes']} minutes"
            )

            # Filter tweets within requested time range
            recent_tweets = []
            for tweet in tweets.data:
                if (
                    tweet.created_at
                    and tweet.created_at.replace(tzinfo=None) >= since_time
                ):
                    recent_tweets.append(tweet)

            logger.info(f"Found {len(recent_tweets)} recent tweets from API call")
            return recent_tweets

        except Exception as e:
            logger.error(f"Error fetching recent bot tweets: {e}")

            # If API call fails but we have stale cache data, use it
            if self.tweets_cache["data"] is not None:
                logger.warning("API call failed, using stale cached data")
                cache_age_minutes = (
                    current_time - self.tweets_cache["timestamp"]
                ).total_seconds() / 60
                logger.warning(
                    f"Using cache that is {cache_age_minutes:.1f} minutes old"
                )

                # Filter stale cached tweets
                since_time = current_time - timedelta(hours=hours)
                recent_tweets = []

                for tweet in self.tweets_cache["data"]:
                    if (
                        tweet.created_at
                        and tweet.created_at.replace(tzinfo=None) >= since_time
                    ):
                        recent_tweets.append(tweet)

                return recent_tweets

            return []

    def process_replies(self):
        """Process and reply to replies on bot's tweets."""
        if not self.is_engagement_time():
            return

        logger.info("=== Processing Replies ===")

        try:
            recent_tweets = self.get_recent_bot_tweets(hours=24)
            reply_count = 0

            for tweet in recent_tweets:
                if reply_count >= ENGAGEMENT_CONFIG["max_replies_per_check"]:
                    logger.info("Reached maximum replies per check")
                    break

                # Search for replies to this tweet
                try:
                    # Use search to find replies (mentions that are replies to the conversation)
                    query = f"to:{self.bot_username} conversation_id:{tweet.conversation_id}"

                    replies = self.client.search_recent_tweets(
                        query=query,
                        max_results=10,
                        tweet_fields=["author_id", "created_at", "in_reply_to_user_id"],
                    )

                    if not replies.data:
                        continue

                    for reply in replies.data:
                        # Skip if already processed
                        if reply.id in self.processed_interactions["replied_to"]:
                            continue

                        # Skip if it's the bot's own tweet
                        if reply.author_id == self.bot_user_id:
                            continue

                        # Skip if contains blacklisted keywords
                        if self.contains_blacklisted_keywords(reply.text):
                            continue

                        # Generate and send reply
                        try:
                            reply_message = self.generate_reply_message(
                                tweet.text, reply.text
                            )

                            # Post the reply
                            response = self.client.create_tweet(
                                text=reply_message, in_reply_to_tweet_id=reply.id
                            )

                            logger.info(f"Replied to tweet {reply.id}: {reply_message}")

                            # Mark as processed
                            self.processed_interactions["replied_to"].add(reply.id)
                            reply_count += 1

                            # Add delay between replies
                            time.sleep(random.uniform(10, 30))

                        except Exception as e:
                            logger.error(f"Error replying to tweet {reply.id}: {e}")

                        if reply_count >= ENGAGEMENT_CONFIG["max_replies_per_check"]:
                            break

                except Exception as e:
                    logger.error(
                        f"Error searching for replies to tweet {tweet.id}: {e}"
                    )

            logger.info(f"Processed {reply_count} replies")
            self.save_processed_interactions()

        except Exception as e:
            logger.error(f"Error in process_replies: {e}")

    def process_reposts(self):
        """Process and comment on reposts of bot's content."""
        if not self.is_engagement_time():
            return

        logger.info("=== Processing Reposts ===")

        try:
            recent_tweets = self.get_recent_bot_tweets(hours=24)
            comment_count = 0

            for tweet in recent_tweets:
                if comment_count >= ENGAGEMENT_CONFIG["max_repost_comments_per_check"]:
                    logger.info("Reached maximum repost comments per check")
                    break

                # Search for retweets/quotes of this tweet
                try:
                    # Search for retweets and quote tweets
                    retweet_query = f"url:{tweet.id}"

                    reposts = self.client.search_recent_tweets(
                        query=retweet_query,
                        max_results=10,
                        tweet_fields=["author_id", "created_at", "referenced_tweets"],
                    )

                    if not reposts.data:
                        continue

                    for repost in reposts.data:
                        # Skip if already processed
                        if (
                            repost.id
                            in self.processed_interactions["commented_reposts"]
                        ):
                            continue

                        # Skip if it's the bot's own repost
                        if repost.author_id == self.bot_user_id:
                            continue

                        # Skip if contains blacklisted keywords
                        if self.contains_blacklisted_keywords(repost.text):
                            continue

                        # Generate and send comment
                        try:
                            comment_message = self.generate_repost_comment(tweet.text)

                            # Post the comment as a reply to the repost
                            response = self.client.create_tweet(
                                text=comment_message, in_reply_to_tweet_id=repost.id
                            )

                            logger.info(
                                f"Commented on repost {repost.id}: {comment_message}"
                            )

                            # Mark as processed
                            self.processed_interactions["commented_reposts"].add(
                                repost.id
                            )
                            comment_count += 1

                            # Add delay between comments
                            time.sleep(random.uniform(15, 45))

                        except Exception as e:
                            logger.error(f"Error commenting on repost {repost.id}: {e}")

                        if (
                            comment_count
                            >= ENGAGEMENT_CONFIG["max_repost_comments_per_check"]
                        ):
                            break

                except Exception as e:
                    logger.error(
                        f"Error searching for reposts of tweet {tweet.id}: {e}"
                    )

            logger.info(f"Processed {comment_count} repost comments")
            self.save_processed_interactions()

        except Exception as e:
            logger.error(f"Error in process_reposts: {e}")

    def cleanup_old_interactions(self):
        """Clean up old processed interactions to prevent memory bloat."""
        logger.debug("Cleaning up old processed interactions")

        # Keep only interactions from last 7 days worth of data
        # This is a simple implementation - in production you might want more sophisticated cleanup
        if len(self.processed_interactions["replied_to"]) > 1000:
            # Keep only the most recent 500
            recent_replies = list(self.processed_interactions["replied_to"])[-500:]
            self.processed_interactions["replied_to"] = set(recent_replies)

        if len(self.processed_interactions["commented_reposts"]) > 1000:
            # Keep only the most recent 500
            recent_comments = list(self.processed_interactions["commented_reposts"])[
                -500:
            ]
            self.processed_interactions["commented_reposts"] = set(recent_comments)

        self.save_processed_interactions()

    def run_engagement_cycle(self):
        """Run one complete engagement cycle."""
        logger.info("=== Starting Engagement Cycle ===")

        try:
            # Process replies first
            self.process_replies()

            # Wait a bit between different types of processing
            time.sleep(random.uniform(5, 15))

            # Process reposts
            self.process_reposts()

            # Cleanup old data occasionally
            if random.random() < 0.1:  # 10% chance
                self.cleanup_old_interactions()

            logger.info("=== Engagement Cycle Complete ===")

        except Exception as e:
            logger.error(f"Error in engagement cycle: {e}")

    def start_scheduler(self):
        """Start the scheduled engagement bot."""
        logger.info("=== Starting Engagement Bot Scheduler ===")

        # Schedule reply processing
        schedule.every(ENGAGEMENT_CONFIG["reply_interval_minutes"]).minutes.do(
            lambda: threading.Thread(target=self.process_replies, daemon=True).start()
        )

        # Schedule repost processing
        schedule.every(ENGAGEMENT_CONFIG["repost_interval_minutes"]).minutes.do(
            lambda: threading.Thread(target=self.process_reposts, daemon=True).start()
        )

        # Schedule daily cleanup
        schedule.every().day.at("02:00").do(self.cleanup_old_interactions)

        logger.info(f"Scheduler configured:")
        logger.info(
            f"  - Reply checks every {ENGAGEMENT_CONFIG['reply_interval_minutes']} minutes"
        )
        logger.info(
            f"  - Repost checks every {ENGAGEMENT_CONFIG['repost_interval_minutes']} minutes"
        )
        logger.info(
            f"  - Active hours: {ENGAGEMENT_CONFIG['engagement_hours']['start']}:00 - {ENGAGEMENT_CONFIG['engagement_hours']['end']}:00"
        )
        logger.info(
            f"  - Weekend reduced activity: {ENGAGEMENT_CONFIG['weekend_reduced_activity']}"
        )

        # Run initial cycle
        logger.info("Running initial engagement cycle...")
        threading.Thread(target=self.run_engagement_cycle, daemon=True).start()

        # Keep the scheduler running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute


def main():
    """Main function to start the engagement bot."""
    logger.info("=== Astronomy Engagement Bot Starting ===")

    try:
        bot = EngagementBot()
        bot.start_scheduler()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error in engagement bot: {e}")
        raise


if __name__ == "__main__":
    main()
