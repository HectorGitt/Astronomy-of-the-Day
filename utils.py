from openai import OpenAI
from decouple import config

client = OpenAI(api_key=config("OPENAI_API_KEY"))


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
