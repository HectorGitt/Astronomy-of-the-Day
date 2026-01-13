from openai import OpenAI
from decouple import config
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

client = OpenAI(api_key=config("OPENAI_API_KEY"))


def scrape_apod():
    logger.info("Scraping APOD website as fallback...")
    try:
        response = requests.get("https://apod.nasa.gov/apod/astropix.html")
        if response.status_code != 200:
            logger.error(f"Failed to fetch APOD website: {response.status_code}")
            return None, None, None

        soup = BeautifulSoup(response.text, "html.parser")

        # Find media URL - check for video first, then images
        media_url = None

        # Check for video element
        video = soup.find("video")
        if video:
            source = video.find("source")
            if source and source.get("src"):
                media_url = "https://apod.nasa.gov/apod/" + source["src"]
                logger.info("Found video media")

        if not media_url:
            # Look for the image link: <a href="image/...">
            img_link = soup.find(
                "a",
                href=lambda x: x
                and (
                    x.startswith("image/")
                    or (x.startswith("ap") and x.endswith(".jpg"))
                ),
            )

            if img_link:
                # Check if it wraps an image to be sure, or just trust the href
                media_url = "https://apod.nasa.gov/apod/" + img_link["href"]
                logger.info("Found image link")

        if not media_url:
            # Check for video iframe
            iframe = soup.find("iframe")
            if iframe:
                media_url = iframe.get("src")
                logger.info("Found iframe media")

        if not media_url:
            # Try finding generic img with src starting with image/
            img = soup.find("img", src=lambda x: x and x.startswith("image/"))
            if img:
                media_url = "https://apod.nasa.gov/apod/" + img["src"]
                logger.info("Found img tag media")

        if not media_url:
            logger.error("Could not find media link in scraped HTML")
            return None, None, None

        # Find explanation
        # Look for <b> Explanation: </b>
        explanation_tag = soup.find("b", string=lambda x: x and "Explanation" in x)
        explanation = ""

        if explanation_tag:
            # Try to get the text after this tag from the parent
            parent_text = explanation_tag.parent.get_text()
            if "Explanation:" in parent_text:
                parts = parent_text.split("Explanation:", 1)
                if len(parts) > 1:
                    explanation = parts[1]
                    # Cleanup
                    if "Tomorrow's picture" in explanation:
                        explanation = explanation.split("Tomorrow's picture")[0]
                    explanation = explanation.strip()

        if not explanation:
            # Fallback: grab all text from all p tags and find largest
            ps = soup.find_all("p")
            texts = [p.get_text().strip() for p in ps]
            # Filter out short ones
            long_texts = [t for t in texts if len(t) > 100]
            if long_texts:
                explanation = max(long_texts, key=len)
                if "Explanation:" in explanation:
                    explanation = explanation.split("Explanation:", 1)[1].strip()

        # Date - usually implies today
        formatted_date = datetime.now().strftime("%a, %b %d, %Y")

        return explanation, media_url, formatted_date

    except Exception as e:
        logger.error(f"Error scraping APOD: {e}")
        return None, None, None


def get_message(context):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # The model identifier of the model to use
        messages=[
            {
                "role": "developer",
                "content": [
                    {
                        "type": "text",
                        "text": """Write one caption for a daily astronomy picture sourced from the NASA API.

                        The caption should be either funny, witty, or thought-provoking (choose one).

                        It must align with the theme of the image (galaxy, nebula, planet, star cluster, etc.).

                        Keep it under 200 characters, including spaces.

                        Use line breaks if it helps readability.

                        Do not use quotation marks in the caption.

                        Make sure it’s engaging and suitable for a Twitter/X audience.""",
                    }
                ],
            },
            {"role": "user", "content": context},
        ],
    )
    return completion.choices[0].message.content
