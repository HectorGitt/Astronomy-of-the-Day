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
        if media_url:
            request = requests.get(media_url, stream=True)
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
                if media_url.endswith(img_formats):
                    with open("aiod.jpg", "wb") as image:
                        total_length = int(request.headers.get("content-length"))
                        downloaded = 0
                        for chunk in request.iter_content(chunk_size=1024):
                            if chunk:
                                image.write(chunk)
                                downloaded += len(chunk)
                                done = int(50 * downloaded / total_length)
                                logging.info(
                                    f"Download progress: [{'=' * done}{' ' * (50 - done)}] {done * 2}%"
                                )
                    image_status = True
                    media = api.media_upload("aiod.jpg")
                    logging.info("Image downloaded and uploaded to Twitter")
                else:
                    logging.info("No image found in the media URL")
                    logging.info("No image found in the media URL")
            else:
                logging.error(f"Failed to download media: {request.status_code}")
                return
        if image_status:
            response = client.create_tweet(text=caption, media_ids=[media.media_id])
            logging.info(f"Tweeted with image. Caption: {caption}")
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
            logging.info(f"Tweeted without image. Caption: {caption}")
            if hasattr(response, "data") and response.data:
                logging.info(f"Tweet ID: {response.data.get('id')}")

        global tweet_status
        tweet_status = True
        if image_status:
            os.remove("aiod.jpg")
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
