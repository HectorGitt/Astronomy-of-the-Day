from openai import OpenAI
from decouple import config
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin
import logging
import re

logger = logging.getLogger(__name__)

APOD_BASE_URL = "https://apod.nasa.gov/apod/"
APOD_PAGE_URL = APOD_BASE_URL + "astropix.html"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff")
# Iframes that are tracking/analytics, never APOD media
IFRAME_BLOCKLIST = ("googletagmanager.com", "google-analytics.com", "doubleclick.net")

client = OpenAI(api_key=config("OPENAI_API_KEY"))


def _is_tracker_or_blank(src):
    return (
        not src
        or not src.startswith(("http://", "https://", "//"))
        or any(host in src for host in IFRAME_BLOCKLIST)
    )


def scrape_apod():
    logger.info("Scraping APOD website as fallback...")
    try:
        response = requests.get(APOD_PAGE_URL, timeout=30)
        if response.status_code != 200:
            logger.error(f"Failed to fetch APOD website: {response.status_code}")
            return None, None, None

        # apod.nasa.gov now redirects to science.nasa.gov/apod/, so resolve
        # relative links against the final URL
        page_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")

        # science.nasa.gov wraps today's APOD in an embedded-post <article>; the rest
        # of the page is unrelated NASA news. Fall back to the whole page (old layout).
        container = soup.find("article", class_="smd-embed-post__article") or soup
        logger.info(
            "Using APOD article container"
            if container is not soup
            else "APOD article container not found, using whole page"
        )

        # Find media URL - check for video first, then images
        media_url = None

        # Check for video element
        video = container.find("video")
        if video:
            source = video.find("source")
            src = (source and source.get("src")) or video.get("src")
            if src:
                media_url = urljoin(page_url, src.strip())
                logger.info("Found video media")

        if not media_url:
            # New layout: image hosted under .../cds/apod/...
            img = container.find("img", src=lambda x: x and "/cds/apod/" in x)
            if img:
                media_url = urljoin(page_url, img["src"].strip())
                logger.info("Found APOD image")

        if not media_url:
            # Old layout: <a href="image/..."> (relative or absolute)
            img_link = container.find(
                "a",
                href=lambda x: x
                and (
                    x.strip().startswith("image/")
                    or ("/apod/image/" in x and x.strip().lower().endswith(IMAGE_EXTENSIONS))
                    or (x.startswith("ap") and x.endswith(".jpg"))
                ),
            )

            if img_link:
                media_url = urljoin(page_url, img_link["href"].strip())
                logger.info("Found image link")

        if not media_url:
            # Check for video iframe, skipping trackers (e.g. Google Tag Manager
            # <noscript> iframe) and placeholders like about:blank
            for iframe in container.find_all("iframe"):
                src = (iframe.get("src") or iframe.get("data-src") or "").strip()
                if iframe.find_parent("noscript") or _is_tracker_or_blank(src):
                    continue
                media_url = urljoin(page_url, src)
                logger.info(f"Found iframe media: {media_url}")
                break

        if not media_url and container is soup:
            # Old layout: generic img with src under image/
            img = soup.find("img", src=lambda x: x and x.strip().startswith("image/"))
            if img:
                media_url = urljoin(page_url, img["src"].strip())
                logger.info("Found img tag media")

        if not media_url:
            logger.error("Could not find media link in scraped HTML")
            return None, None, None

        # Explanation: text after "Explanation:" up to the footer notes
        explanation = ""
        text = " ".join(container.get_text(" ", strip=True).split())
        if "Explanation:" in text:
            explanation = text.split("Explanation:", 1)[1]
            for marker in ("APOD's email", "Tomorrow's picture", "Date "):
                explanation = explanation.split(marker, 1)[0]
            # Drop spaces left before punctuation where links were joined
            explanation = re.sub(r"\s+([.,;:!?)])", r"\1", explanation).strip()

        if not explanation:
            # Fallback: largest paragraph
            long_texts = [
                p.get_text(" ", strip=True)
                for p in container.find_all("p")
                if len(p.get_text(strip=True)) > 100
            ]
            if long_texts:
                explanation = max(long_texts, key=len)

        # Date: new layout has a "Date" table row, otherwise assume today
        apod_date = datetime.now()
        date_label = container.find("th", string=lambda x: x and x.strip() == "Date")
        date_cell = date_label and date_label.find_next_sibling("td")
        if date_cell:
            try:
                apod_date = datetime.strptime(date_cell.get_text(strip=True), "%B %d, %Y")
            except ValueError:
                logger.warning(f"Could not parse APOD date: {date_cell.get_text(strip=True)}")
        formatted_date = apod_date.strftime("%a, %b %d, %Y")

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

                        Do not start the caption with 'When'. Use diverse sentence structures.

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
