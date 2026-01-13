import tweepy
from decouple import config
import requests
from datetime import datetime
import os
import time
import textwrap
import logging
from utils import get_message, scrape_apod

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Authenticate to Twitter
consumer_key = config("CONSUMER_KEY")
consumer_secret = config("CONSUMER_SECRET")
access_token = config("ACCESS_TOKEN")
access_token_secret = config("ACCESS_TOKEN_SECRET")
bearer_token = config("BEARER_TOKEN")
nasa_api_key = config("NASA_API_KEY")

# Create API object
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
client = tweepy.Client(
    bearer_token, consumer_key, consumer_secret, access_token, access_token_secret
)
api = tweepy.API(auth=auth, wait_on_rate_limit=True)

tweet_status = False
api_status = False
tries = 0
image_status = False


def chunkstring(string, length):
    return textwrap.shorten(string, length, placeholder="...")


def tweet_parser():
    logging.info("Fetching Astronomy Picture of the Day from NASA API")
    response = requests.get(
        f"https://api.nasa.gov/planetary/apod?api_key={nasa_api_key}"
    )
    if response.status_code == 200:
        global api_status
        api_status = True
        logging.info("Successfully fetched data from NASA API")

        data = response.json()
        date_str = data.get("date")
        date_object = datetime.strptime(date_str, "%Y-%m-%d").date()
        media_url = data.get("url")

        # If API returns no URL, try scraping
        if not media_url:
            logging.info("NASA API returned no media URL. Attempting scrape...")
            try:
                # We mainly want the media URL from scrape if API failed to give one
                _, scraped_url, _ = scrape_apod()
                if scraped_url:
                    media_url = scraped_url
                    logging.info(f"Retrieved media URL from scrape: {media_url}")
            except Exception as e:
                logging.error(f"Failed to scrape for missing URL: {e}")

        return (
            data.get("explanation"),
            media_url,
            date_object.strftime("%a, %b %d, %Y"),
        )
    else:
        logging.error(f"Failed to fetch data from NASA API: {response.status_code}")

        logging.info("Attempting fallback scrape...")
        explanation, media_url, formatted_date = scrape_apod()
        if explanation and media_url:
            api_status = True
            return explanation, media_url, formatted_date

        return None, None, None


def tweet():
    try:
        global tries
        global image_status
        tries += 1
        logging.info(f"Attempt number {tries} to tweet")
        image_text, media_url, date_obj = tweet_parser()
        if not api_status:
            logging.warning("API status is False, skipping tweet")
            return

        caption = get_message(str(date_obj) + " " + image_text)
        media_uploaded = False
        media_id = None

        if media_url:
            logging.info(f"Processing media URL: {media_url}")
            request = requests.get(media_url, stream=True)
            logging.info(f"Media URL status code: {request.status_code}")

            if request.status_code == 200:
                logging.info("Successfully connected to media from URL")
                img_formats = (
                    ".jpg",
                    ".png",
                    ".jpeg",
                    ".gif",
                    ".bmp",
                    ".tiff",
                    ".webp",
                )
                video_formats = (
                    ".mp4",
                    ".mov",
                    ".avi",
                    ".m4v",
                    ".webm",
                )

                if media_url.endswith(img_formats):
                    # Handle image
                    with open("aiod.jpg", "wb") as image:
                        total_length = int(request.headers.get("content-length", 0))
                        downloaded = 0
                        for chunk in request.iter_content(chunk_size=1024):
                            if chunk:
                                image.write(chunk)
                                downloaded += len(chunk)
                                if total_length > 0:
                                    done = int(50 * downloaded / total_length)
                                    logging.info(
                                        f"Download progress: [{'=' * done}{' ' * (50 - done)}] {done * 2}%"
                                    )
                    image_status = True
                    media = api.media_upload("aiod.jpg")
                    media_id = media.media_id
                    media_uploaded = True
                    logging.info("Image downloaded and uploaded to Twitter")

                elif media_url.endswith(video_formats):
                    # Handle video
                    with open("aiod.mp4", "wb") as video:
                        total_length = int(request.headers.get("content-length", 0))
                        downloaded = 0
                        for chunk in request.iter_content(chunk_size=1024):
                            if chunk:
                                video.write(chunk)
                                downloaded += len(chunk)
                                if total_length > 0:
                                    done = int(50 * downloaded / total_length)
                                    logging.info(
                                        f"Video download progress: [{'=' * done}{' ' * (50 - done)}] {done * 2}%"
                                    )
                    media = api.media_upload("aiod.mp4", media_category="tweet_video")
                    media_id = media.media_id
                    media_uploaded = True
                    logging.info("Video downloaded and uploaded to Twitter")

                else:
                    logging.info(f"Unsupported media format extension: {media_url}")
                    # Try to detect video by content-type or if it ends with nothing typical
                    content_type = request.headers.get("Content-Type", "").lower()
                    logging.info(f"Media content-type: {content_type}")

                    if "video" in content_type:
                        # Fallback video handling
                        file_ext = ".mp4"  # Default
                        if "webm" in content_type:
                            file_ext = ".webm"
                        elif "quicktime" in content_type:
                            file_ext = ".mov"

                        filename = f"aiod{file_ext}"

                        with open(filename, "wb") as video:
                            total_length = int(request.headers.get("content-length", 0))
                            downloaded = 0
                            for chunk in request.iter_content(chunk_size=1024):
                                if chunk:
                                    video.write(chunk)
                                    downloaded += len(chunk)
                                    if total_length > 0:
                                        done = int(50 * downloaded / total_length)
                                        logging.info(
                                            f"Fallback video download progress: [{'=' * done}{' ' * (50 - done)}] {done * 2}%"
                                        )

                        try:
                            media = api.media_upload(
                                filename, media_category="tweet_video"
                            )
                            media_id = media.media_id
                            media_uploaded = True
                            logging.info(
                                "Video downloaded (fallback) and uploaded to Twitter"
                            )
                        except Exception as e:
                            logging.error(f"Failed to upload video: {e}")
                    else:
                        logging.info("Posting tweet with media URL instead")
            else:
                logging.error(f"Failed to download media: {request.status_code}")
                return
        if media_uploaded and media_id:
            response = client.create_tweet(text=caption, media_ids=[media_id])
            logging.info(f"Tweeted with media. Caption: {caption}")
            if hasattr(response, "data") and response.data:
                logging.info(f"Tweet ID: {response.data.get('id')}")
        elif media_url:
            if "youtube" in media_url:
                media_url = "https://youtu.be/" + media_url.split("/")[-1]
            caption = chunkstring(caption, 210) + "\n" + media_url
            response = client.create_tweet(text=caption)
            logging.info(f"Tweeted with media URL. Content: {caption}")
            if hasattr(response, "data") and response.data:
                logging.info(f"Tweet ID: {response.data.get('id')}")
        else:
            response = client.create_tweet(text=caption)
            logging.info(f"Tweeted without media. Caption: {caption}")
            if hasattr(response, "data") and response.data:
                logging.info(f"Tweet ID: {response.data.get('id')}")

        global tweet_status
        tweet_status = True

        # Clean up downloaded files
        for filename in ["aiod.jpg", "aiod.mp4", "aiod.webm", "aiod.mov"]:
            if os.path.exists(filename):
                os.remove(filename)
                logging.info(f"Cleaned up {filename}")

        logging.info("Tweeted successfully at %s", datetime.now())
    except Exception as e:
        logging.error(f"Tweet failed: {e}")
        logging.error("Tweet failed at %s", datetime.now())


def tweet_handler():
    while True:
        if tries >= 3 and not tweet_status:
            logging.error("Failed to tweet after 3 attempts")
            break
        if tries > 0 and not tweet_status:
            logging.info("Trying again, waiting 1 hour")
            time.sleep(3600)
        if tweet_status:
            break
        else:
            tweet()


if __name__ == "__main__":
    tweet_handler()
