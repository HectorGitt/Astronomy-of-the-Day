#!/usr/bin/env python3
"""
Outfit Generator Bot - Generates and posts AI fashion outfits to Twitter
Uses Gemini Flash 2.5 to create 4 random outfit images and posts them to Twitter
"""

import tweepy
from decouple import config
import asyncio
import random
import logging
import os
import base64
from io import BytesIO
from PIL import Image as PILImage
from google_genai import generate_outfit_image_from_text
import openai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/outfit_generator.log"),
        logging.StreamHandler(),
    ],
)

# Authenticate to Twitter
consumer_key = config("CONSUMER_KEY")
consumer_secret = config("CONSUMER_SECRET")
access_token = config("ACCESS_TOKEN")
access_token_secret = config("ACCESS_TOKEN_SECRET")
bearer_token = config("BEARER_TOKEN")

# Create API object
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
client = tweepy.Client(
    bearer_token, consumer_key, consumer_secret, access_token, access_token_secret
)
api = tweepy.API(auth=auth, wait_on_rate_limit=True)

# Initialize OpenAI client for prompt refinement
openai_client = openai.OpenAI(api_key=config("OPENAI_API_KEY"))

# Outfit generation settings
OUTFIT_STYLES = [
    "casual",
    "business casual",
    "formal",
    "streetwear",
    "bohemian",
    "minimalist",
    "vintage",
    "athleisure",
    "gothic",
    "preppy",
    "punk",
    "hipster",
    "retro",
    "modern",
    "elegant",
]

OUTFIT_OCCASIONS = [
    "office",
    "date night",
    "weekend casual",
    "party",
    "wedding",
    "beach day",
    "job interview",
    "coffee date",
    "concert",
    "brunch",
    "shopping",
    "travel",
    "gym",
    "home office",
    "dinner out",
]

OUTFIT_THEMES = [
    "colorful and vibrant",
    "monochromatic",
    "pastel tones",
    "bold patterns",
    "neutral palette",
    "metallic accents",
    "earth tones",
    "neon bright",
    "classic black and white",
    "seasonal colors",
    "cultural inspired",
    "futuristic",
    "vintage inspired",
    "sporty",
    "romantic",
]

GENDER_OPTIONS = ["unisex", "women", "men"]

tweet_status = False
tries = 0


async def refine_prompt_with_ai(basic_prompt, style, occasion, theme, gender):
    """Use OpenAI to refine and enhance the basic prompt for better outfit generation."""
    try:
        refinement_prompt = f"""
        You are a fashion expert AI. Take this basic outfit description and transform it into a detailed, professional prompt for AI image generation.

        Basic description: "{basic_prompt}"

        Style: {style}
        Occasion: {occasion}
        Theme: {theme}
        Gender: {gender}

        Create a highly detailed prompt that will generate a stunning fashion image. The prompt MUST include:

        1. A human model or person wearing the outfit (not just clothes on a hanger or flat lay)
        2. Specific details about the model's pose, expression, and setting
        3. Detailed clothing descriptions with fabrics, colors, and styling
        4. Professional photography elements (lighting, composition, etc.)
        5. Modern fashion context and contemporary appeal

        Make it vivid, specific, and optimized for AI image generation. Focus on creating a complete, wearable outfit that looks realistic and fashionable on a person.

        Return only the refined prompt, no additional text or explanations.
        """

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional fashion prompt engineer. Create detailed, vivid prompts for AI image generation.",
                },
                {"role": "user", "content": refinement_prompt},
            ],
            max_tokens=300,
            temperature=0.7,
        )

        refined_prompt = response.choices[0].message.content.strip()
        logging.info(f"Refined prompt for {style} outfit")
        return refined_prompt

    except Exception as e:
        logging.error(f"Failed to refine prompt with AI: {e}")
        # Return the original prompt if AI refinement fails
        return basic_prompt


def generate_random_prompts(count=4):
    """Generate random outfit prompts for AI generation."""
    prompts = []

    for i in range(count):
        style = random.choice(OUTFIT_STYLES)
        occasion = random.choice(OUTFIT_OCCASIONS)
        theme = random.choice(OUTFIT_THEMES)
        gender = random.choice(GENDER_OPTIONS)

        # Create a detailed prompt for the AI - ensure human model is included
        prompt = f"Create a stunning {style} outfit for a {occasion}. "
        prompt += f"Use {theme} color scheme. "
        prompt += f"Design for {gender} fashion. "
        prompt += "Make it fashionable, modern, and visually appealing. "
        prompt += (
            "Show the complete outfit on a human model with good lighting and styling. "
        )
        prompt += "The model should be posing naturally in an appropriate setting."

        prompts.append(
            {
                "prompt": prompt,
                "style": style,
                "occasion": occasion,
                "theme": theme,
                "gender": gender,
            }
        )

    return prompts


async def generate_refined_prompts(count=4):
    """Generate and refine random outfit prompts using AI."""
    logging.info("Generating and refining outfit prompts with AI...")

    # First generate basic prompts
    basic_prompts = generate_random_prompts(count)
    refined_prompts = []

    for i, prompt_data in enumerate(basic_prompts, 1):
        logging.info(f"Refining prompt {i}/{count} with AI...")

        # Refine the prompt using OpenAI
        refined_prompt = await refine_prompt_with_ai(
            prompt_data["prompt"],
            prompt_data["style"],
            prompt_data["occasion"],
            prompt_data["theme"],
            prompt_data["gender"],
        )

        refined_prompts.append(
            {
                "prompt": refined_prompt,
                "style": prompt_data["style"],
                "occasion": prompt_data["occasion"],
                "theme": prompt_data["theme"],
                "gender": prompt_data["gender"],
                "original_prompt": prompt_data["prompt"],
            }
        )

        # Small delay to avoid rate limits
        await asyncio.sleep(1)

    logging.info("All prompts refined with AI")
    return refined_prompts


async def generate_outfit_images(prompts):
    """Generate outfit images using Gemini Flash 2.5."""
    logging.info(f"Generating {len(prompts)} outfit images...")

    generated_outfits = []

    for i, prompt_data in enumerate(prompts, 1):
        logging.info(
            f"Generating outfit {i}/{len(prompts)}: {prompt_data['style']} for {prompt_data['occasion']}"
        )

        try:
            # Generate outfit using Gemini
            result = await generate_outfit_image_from_text(
                prompt=prompt_data["prompt"],
                style=prompt_data["style"],
                occasion=prompt_data["occasion"],
                gender=prompt_data["gender"],
            )

            if result and result["success"]:
                # Save image to file
                image_data = base64.b64decode(result["image_data"])
                image = PILImage.open(BytesIO(image_data))

                filename = f"outfit_{i}.png"
                image.save(filename, "PNG")

                generated_outfits.append(
                    {
                        "filename": filename,
                        "prompt_data": prompt_data,
                        "description": result.get("description", ""),
                        "image_data": result,
                    }
                )

                logging.info(f"Successfully generated outfit {i}")

            else:
                logging.error(f"Failed to generate outfit {i}")

        except Exception as e:
            logging.error(f"Error generating outfit {i}: {e}")
            continue

    return generated_outfits


def create_tweet_text(outfit_data, outfit_number, total_outfits):
    """Create engaging tweet text for the outfit."""
    style = outfit_data["prompt_data"]["style"]
    occasion = outfit_data["prompt_data"]["occasion"]
    theme = outfit_data["prompt_data"]["theme"]

    # Create more interesting and varied captions
    captions = [
        f"✨ Look {outfit_number}/{total_outfits}: This {style} masterpiece screams '{occasion}' vibes! The {theme} really elevates the whole look 💫 #FashionAI #OutfitGoals",
        f"🌟 Outfit {outfit_number} of {total_outfits}: When {style} meets {occasion} perfection! Loving how the {theme} brings everything together 👗 #AIOutfits #StyleInspo",
        f"💃 Creation {outfit_number}/{total_outfits}: {style.title()} elegance for your next {occasion}. The {theme} is giving major fashion chef vibes! ✨ #FashionTech #OutfitInspo",
        f"🎨 AI Magic {outfit_number}/{total_outfits}: {style} style that owns the {occasion} scene! The {theme} is absolutely *chef's kiss* 💋 #AIFashion #FashionForward",
        f"🔥 Outfit {outfit_number}/{total_outfits}: {style.title()} sophistication meets {occasion} charm. The {theme} is the secret ingredient! 🌈 #FashionAI #StyleCrush",
        f"💎 Look {outfit_number} of {total_outfits}: Pure {style} poetry for {occasion} moments. The {theme} makes it unforgettable! ✨ #AIOutfits #FashionArt",
        f"🌺 Creation {outfit_number}/{total_outfits}: {style} dreams come true for your {occasion}! The {theme} is pure magic ✨ #FashionTech #OutfitMagic",
        f"🎭 Outfit {outfit_number}/{total_outfits}: {style.title()} drama for {occasion} nights. The {theme} steals the show! 🎭 #AIFashion #StyleTheater",
    ]

    return random.choice(captions)


async def post_outfits_to_twitter(outfits):
    """Post generated outfits to Twitter."""
    global tweet_status, tries

    if not outfits:
        logging.error("No outfits to post!")
        return False

    try:
        # Create a thread of tweets
        thread_tweets = []

        # Intro tweet
        intro_text = "🎨 AI Fashion Showcase! 🤖 Generated 4 unique outfits with GPT-4 refined prompts ✨\n\nEach look is worn by stunning models in perfect settings! 👇 #AIFashion #FashionAI #AIOutfits"
        intro_tweet = client.create_tweet(text=intro_text)
        thread_tweets.append(intro_tweet)

        logging.info("Posted intro tweet")

        # Post each outfit as a reply in the thread
        for i, outfit in enumerate(outfits, 1):
            try:
                # Upload media
                media = api.media_upload(outfit["filename"])
                logging.info(f"Uploaded outfit {i} media to Twitter")

                # Create tweet text
                tweet_text = create_tweet_text(outfit, i, len(outfits))

                # Post as reply to previous tweet
                reply_tweet = client.create_tweet(
                    text=tweet_text,
                    media_ids=[media.media_id],
                    in_reply_to_tweet_id=thread_tweets[-1].data["id"],
                )

                thread_tweets.append(reply_tweet)
                logging.info(f"Posted outfit {i} tweet")

                # Small delay between tweets to avoid rate limits
                await asyncio.sleep(2)

            except Exception as e:
                logging.error(f"Failed to post outfit {i}: {e}")
                continue

        # Outro tweet
        outro_text = "🤖 All outfits generated by Gemini Flash 2.5 AI with GPT-4 prompt refinement! Each look features real models in stunning settings 💃\n\nWhich outfit would you rock? 💭\n\n#GeminiAI #GPT4 #FashionTech #AIArt #OutfitInspo"
        client.create_tweet(
            text=outro_text, in_reply_to_tweet_id=thread_tweets[-1].data["id"]
        )

        logging.info("Posted outro tweet")
        tweet_status = True

        return True

    except Exception as e:
        logging.error(f"Failed to post outfits to Twitter: {e}")
        return False

    finally:
        # Clean up image files
        for outfit in outfits:
            try:
                if os.path.exists(outfit["filename"]):
                    os.remove(outfit["filename"])
                    logging.info(f"Cleaned up {outfit['filename']}")
            except Exception as e:
                logging.warning(f"Failed to clean up {outfit['filename']}: {e}")


async def main():
    """Main function to generate and post outfits."""
    global tries, tweet_status

    logging.info("Starting Outfit Generator Bot")
    logging.info("Using AI for outfit generation")

    while tries < 3 and not tweet_status:
        tries += 1
        logging.info(f"Attempt {tries} to generate and post outfits")

        try:
            # Generate and refine random prompts with AI
            prompts = await generate_refined_prompts(4)
            logging.info("Generated and refined 4 outfit prompts with AI")

            # Generate outfit images
            outfits = await generate_outfit_images(prompts)

            if not outfits:
                logging.error("No outfits were successfully generated")
                if tries < 3:
                    logging.info("Retrying in 5 minutes...")
                    await asyncio.sleep(300)
                continue

            logging.info(f"Successfully generated {len(outfits)} outfits")

            # Post to Twitter
            success = await post_outfits_to_twitter(outfits)

            if success:
                logging.info("Successfully posted all outfits to Twitter!")
                tweet_status = True
            else:
                logging.error("❌ Failed to post outfits to Twitter")
                if tries < 3:
                    logging.info("Retrying in 5 minutes...")
                    await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"❌ Error in attempt {tries}: {e}")
            if tries < 3:
                logging.info("Retrying in 5 minutes...")
                await asyncio.sleep(300)

    if tweet_status:
        logging.info("Outfit generation and posting completed successfully!")
    else:
        logging.error("💥 Failed to generate and post outfits after 3 attempts")


if __name__ == "__main__":
    asyncio.run(main())
