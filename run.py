import tweepy
from decouple import config
import requests
from datetime import datetime
import os
import time
import textwrap

# Authenticate to Twitter

""" dotenv.load_dotenv()
# Load environment variables with dotenv
consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")
bearer_token = os.getenv("BEARER_TOKEN")
 """
#import config from .env file
consumer_key = config('CONSUMER_KEY')
consumer_secret = config('CONSUMER_SECRET')
access_token = config('ACCESS_TOKEN')
access_token_secret = config('ACCESS_TOKEN_SECRET')
bearer_token = config('BEARER_TOKEN')
nasa_api_key = config('NASA_API_KEY')

# Create API object
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
client = tweepy.Client(bearer_token, consumer_key, consumer_secret, access_token, access_token_secret,)
api = tweepy.API(auth=auth, wait_on_rate_limit=True)

#fetch aod from nasa api
#https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY

tweet_status = False
api_status = False
tries = 0
#set image status to false
image_status = False


def chunkstring(string, length):
    return textwrap.shorten(string, length, placeholder='...')

def tweet_parser():
    response = requests.get(f"https://api.nasa.gov/planetary/apod?api_key={nasa_api_key}")
    date_str = response.json().get("date")
    date_object = datetime.strptime(date_str, '%Y-%m-%d').date()
    tweet_text = f'{date_object.strftime("%a, %b %d, %Y")}\n- {response.json().get("title")}\n{chunkstring(response.json().get("explanation"), 170)}'
    media_url = response.json().get("url")
    if response.status_code == 200:
        global api_status
        api_status = True
    return tweet_text, media_url, date_object


def tweet():
    try:
        global tries
        global image_status
        tries += 1
        tweet_text, media_url, date_obj = tweet_parser()
        if api_status is False:
            return
        request = requests.get(media_url, stream=True)
        if request.status_code == 200:
            if media_url.endswith('.jpg'):    
                with open('aiod.jpg', 'wb') as image:
                    for chunk in request:
                        image.write(chunk)
                image_status = True
                media = api.media_upload("aiod.jpg")
            else:
                print("No image found")
        else:
            return
        
        more_string = f'\nRead more at https://apod.nasa.gov/apod/ap{date_obj.strftime("%y%m%d")}.html'
        if image_status:
            tweet_text += more_string
            client.create_tweet(text=tweet_text, media_ids=[media.media_id])
        else:
            if "youtube" in media_url:
                media_url = "https://youtu.be/" + media_url.split("/")[-1]
            tweet_text = chunkstring(tweet_text, 220) + "\n" + media_url + more_string
            client.create_tweet(text=tweet_text)
            

        global tweet_status
        tweet_status = True
        if image_status:
            os.remove("aiod.jpg")
        print("Tweeted", datetime.now())
    except Exception as e:
        print(e)
        print("Tweet failed", datetime.now())

def tweet_handler():
    while True:
        if tries > 0 and tweet_status is False:
            print('Trying again, waiting 1 hour')
            time.sleep(3600)
        if tweet_status:
            break
        else:
            tweet()
            
        
if __name__ == "__main__":
        tweet_handler()

