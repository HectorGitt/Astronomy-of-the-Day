import os
from typing import Optional, Dict, Any
import logging
import asyncio
import base64
from io import BytesIO

# Import mock imghdr for compatibility with Python 3.13+
try:
    import imghdr
except ImportError:
    # If imghdr is not available, our local imghdr.py should provide it
    import sys
    import os

    sys.path.insert(0, os.path.dirname(__file__))
    import imghdr

# Import Google GenAI libraries
try:
    from google import genai
    from google.genai import types
    from google.genai.types import (
        GenerateImagesConfig,
        Image,
        ProductImage,
        RecontextImageConfig,
        RecontextImageSource,
    )
    from PIL import Image as PILImage

    GOOGLE_GENAI_AVAILABLE = True
    VERTEX_AI_AVAILABLE = True
except ImportError:
    GOOGLE_GENAI_AVAILABLE = False
    VERTEX_AI_AVAILABLE = False
    genai = None
    types = None
    GenerateImagesConfig = None
    Image = None
    ProductImage = None
    RecontextImageConfig = None
    RecontextImageSource = None
    aiplatform = None
    PILImage = None
    BytesIO = None

logger = logging.getLogger(__name__)


class VirtualTryOnService:
    """Service for Google Cloud Vertex AI Virtual Try-On operations"""

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.model_name = "virtual-try-on-preview-08-04"

        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT not found in environment variables")

    def _generate_tryon_sync(
        self,
        person_image_base64: str,
        clothing_image_base64: str,
        description: str = "",
        style_preferences: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Synchronous method to generate virtual try-on using Vertex AI."""
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("Google GenAI not available")
            return None

        if not self.project_id:
            logger.error("Google Cloud project ID not configured")
            return None

        try:
            # Initialize GenAI client with Vertex AI
            client = genai.Client(
                vertexai=True, project=self.project_id, location=self.location
            )

            # Decode base64 images
            person_bytes = base64.b64decode(
                person_image_base64.split(",")[1]
                if "," in person_image_base64
                else person_image_base64
            )
            clothing_bytes = base64.b64decode(
                clothing_image_base64.split(",")[1]
                if "," in clothing_image_base64
                else clothing_image_base64
            )

            # Create image objects
            person_image = Image(image_bytes=person_bytes)
            clothing_image = Image(image_bytes=clothing_bytes)

            response = client.models.recontext_image(
                model=self.model_name,
                source=RecontextImageSource(
                    person_image=person_image,
                    product_images=[ProductImage(product_image=clothing_image)],
                ),
                config=RecontextImageConfig(
                    base_steps=32,
                    number_of_images=1,
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                    person_generation="ALLOW_ADULT",
                ),
            )

            if response.generated_images:
                # Get image data directly from the response
                generated_image = response.generated_images[0].image

                # Extract image bytes - the Image object should have image_bytes attribute
                if hasattr(generated_image, "image_bytes"):
                    image_bytes = generated_image.image_bytes
                else:
                    # Fallback: try to get data directly
                    image_bytes = (
                        generated_image.data
                        if hasattr(generated_image, "data")
                        else None
                    )

                if image_bytes:
                    # Convert to base64 for return/storage
                    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

                    return {
                        "success": True,
                        "image_data": img_base64,
                        "mime_type": "image/jpeg",
                        "description": f"Virtual try-on: {description}",
                    }
                else:
                    logger.error("Could not extract image bytes from generated image")
                    return None

        except Exception as e:
            logger.error(f"Error in virtual try-on generation: {str(e)}")
            return None

        logger.warning("No virtual try-on image generated")
        return None

    async def generate_virtual_tryon(
        self,
        person_image_base64: str,
        clothing_image_base64: str,
        description: str = "",
        style_preferences: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Generate virtual try-on image using Google Cloud Vertex AI.
        """
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._generate_tryon_sync,
                person_image_base64,
                clothing_image_base64,
                description,
                style_preferences,
            )
            return result
        except Exception as e:
            logger.error(f"Unexpected error generating virtual try-on: {str(e)}")
            return None


class OutfitGenerationService:
    """Service for generating outfit images from text or improving existing outfits"""

    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        self.imagen_model = "imagen-4.0-generate-001"

    def _generate_outfit_from_text_sync(
        self,
        prompt: str,
        style: str = "casual",
        occasion: str = "general",
        gender: str = "unisex",
    ) -> Optional[Dict[str, Any]]:
        """Generate outfit image from text using GenAI."""
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("Google GenAI not available")
            return None

        if not self.project_id:
            logger.error("Google Cloud project ID not configured")
            return None

        try:
            # Initialize GenAI client with Vertex AI
            client = genai.Client(
                vertexai=True, project=self.project_id, location=self.location
            )

            # Build enhanced prompt
            if prompt.strip() == "":
                prompt = f"Create a high-quality, realistic image  of a complete {style} outfit for {occasion} occasion. Style: {style}, Gender: {gender}. Make it fashionable, modern, and visually appealing on a person."

            # Generate image using the imagen model
            response = client.models.generate_images(
                model=self.imagen_model,
                prompt=prompt,
                config=GenerateImagesConfig(
                    number_of_images=1,
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                    person_generation="ALLOW_ADULT",
                ),
            )

            if response.generated_images:
                # Get image data directly from the response
                generated_image = response.generated_images[0].image

                # Extract image bytes
                if hasattr(generated_image, "image_bytes"):
                    image_bytes = generated_image.image_bytes
                else:
                    # Fallback: try to get data directly
                    image_bytes = (
                        generated_image.data
                        if hasattr(generated_image, "data")
                        else None
                    )

                if image_bytes:
                    # Convert to base64 for return/storage
                    img_base64 = base64.b64encode(image_bytes).decode("utf-8")

                    return {
                        "success": True,
                        "image_data": img_base64,
                        "mime_type": "image/png",
                        "description": f"Generated {style} outfit for {occasion}",
                        "prompt_used": prompt,
                    }
                else:
                    logger.error("Could not extract image bytes from generated image")
                    return None

        except Exception as e:
            logger.error(f"Error generating outfit from text: {str(e)}")
            return None

        return None

    def _improve_outfit_with_image_sync(
        self,
        outfit_image_base64: str,
        improvement_prompt: str,
        style: str = "casual",
        occasion: str = "general",
    ) -> Optional[Dict[str, Any]]:
        """Improve an existing outfit image using a single Gemini request."""
        if not GOOGLE_GENAI_AVAILABLE:
            logger.error("Google GenAI not available")
            return None

        try:
            # Initialize GenAI client
            client = genai.Client(
                vertexai=True, project=self.project_id, location=self.location
            )

            # Decode base64 image - handle data URL format
            if "," in outfit_image_base64:
                # Remove data URL prefix if present
                image_bytes = base64.b64decode(outfit_image_base64.split(",")[1])
            else:
                image_bytes = base64.b64decode(outfit_image_base64)

            # Create PIL Image from bytes
            try:
                outfit_image = PILImage.open(BytesIO(image_bytes))
                # Verify image is valid
                outfit_image.verify()
                # Re-open after verify (verify closes the image)
                outfit_image = PILImage.open(BytesIO(image_bytes))
            except Exception as img_error:
                logger.error(f"Failed to open image with PIL: {str(img_error)}")
                return None

            # Create comprehensive improvement prompt
            if improvement_prompt.strip() == "":
                improvement_prompt = f"""
                Analyze this outfit and create an improved version based on these requirements:

                Style: {style}
                Occasion: {occasion}
                Specific improvements requested: {improvement_prompt}

                Please provide:
                A detailed text description of the specific improvements you made to enhance this outfit
                Then generate a high-quality, realistic image of the improved outfit

                Focus on improving:
                - Better color coordination and harmony
                - Improved fit and silhouette
                - Enhanced texture and material quality
                - Better style coherence for {style} style
                - Appropriate for {occasion} occasion
                - Modern fashion trends and standards

                For the text description, explain what changes were made and why they improve the outfit.
                For the image, show:
                - Better proportion and balance
                - Harmonious color combinations
                - Proper fit and tailoring
                - Quality materials and textures
                - Accessories and styling that enhance the overall look
                - Contemporary fashion elements

                Make the outfit look polished, well-fitted, and contextually appropriate.
                """

            # Use single Gemini request with both text and image
            response = client.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=[improvement_prompt, outfit_image],
            )

            # Extract both text and image from the response
            improvement_description = ""
            generated_image_data = None
            mime_type = "image/png"

            for part in response.candidates[0].content.parts:
                if part.text:
                    improvement_description += part.text
                if part.inline_data is not None:
                    # Get the generated image data
                    generated_image_data = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/png"

            if generated_image_data:
                # Convert to base64 for return/storage
                img_base64 = base64.b64encode(generated_image_data).decode("utf-8")

                return {
                    "success": True,
                    "image_data": img_base64,
                    "mime_type": mime_type,
                    "description": f"Improved {style} outfit for {occasion}",
                    "improvement_prompt": improvement_prompt,
                    "improvement_description": improvement_description.strip(),
                }

            logger.error("No image generated in Gemini response")
            return None

        except Exception as e:
            logger.error(f"Error improving outfit with image: {str(e)}")
            return None

    async def generate_outfit_from_text(
        self,
        prompt: str,
        style: str = "casual",
        occasion: str = "general",
        gender: str = "unisex",
    ) -> Optional[Dict[str, Any]]:
        """
        Generate outfit image from text description using Google Imagen.
        """
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._generate_outfit_from_text_sync,
                prompt,
                style,
                occasion,
                gender,
            )
            return result
        except Exception as e:
            logger.error(f"Unexpected error generating outfit from text: {str(e)}")
            return None

    async def improve_outfit_with_image(
        self,
        outfit_image_base64: str,
        improvement_prompt: str,
        style: str = "casual",
        occasion: str = "general",
    ) -> Optional[Dict[str, Any]]:
        """
        Improve an existing outfit image using AI analysis.
        """
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                self._improve_outfit_with_image_sync,
                outfit_image_base64,
                improvement_prompt,
                style,
                occasion,
            )
            return result
        except Exception as e:
            logger.error(f"Unexpected error improving outfit with image: {str(e)}")
            return None


# Global service instances
virtual_tryon_service = VirtualTryOnService()
outfit_generation_service = OutfitGenerationService()


# Convenience functions for backward compatibility and easy access


async def generate_virtual_tryon_image(
    person_image_base64: str,
    clothing_image_base64: str,
    description: str = "",
    style_preferences: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to generate virtual try-on image.
    """
    return await virtual_tryon_service.generate_virtual_tryon(
        person_image_base64, clothing_image_base64, description, style_preferences
    )


async def generate_outfit_image_from_text(
    prompt: str,
    style: str = "casual",
    occasion: str = "general",
    gender: str = "unisex",
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to generate outfit image from text.
    """
    return await outfit_generation_service.generate_outfit_from_text(
        prompt, style, occasion, gender
    )


async def improve_outfit_with_image(
    outfit_image_base64: str,
    improvement_prompt: str,
    style: str = "casual",
    occasion: str = "general",
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to improve outfit using image analysis.
    """
    return await outfit_generation_service.improve_outfit_with_image(
        outfit_image_base64, improvement_prompt, style, occasion
    )


async def generate_text_with_gemini(
    prompt: str,
    model: str = "gemini-2.5-flash",  # Example Vertex AI Gemini model name
    max_tokens: int = 300,
    temperature: float = 0.7,
) -> Optional[str]:
    """
    Generate text using Google Vertex AI Gemini or other Vertex AI text models.
    """
    if not GOOGLE_GENAI_AVAILABLE:
        logger.error("Google GenAI not available")
        return None

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project_id:
        logger.error("Google Cloud project ID not configured")
        return None

    try:
        client = genai.Client(
            vertexai=True, project=project_id, location=location
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        if response.candidates and len(response.candidates) > 0:
            text_content = ""
            for part in response.candidates[0].content.parts:
                if part.text:
                    text_content += part.text

            return text_content.strip()

        logger.error("No text generated in Vertex AI response")
        return None

    except Exception as e:
        logger.error(f"Error generating text with Vertex AI: {str(e)}")
        return None