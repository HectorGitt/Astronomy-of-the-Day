from openai import OpenAI

client = OpenAI()

def get_message(context):
    completion = client.chat.completions.create(
        model="gpt-4o-mini",  # The model identifier of the model to use
        messages=[
            {"role": "developer", "content": [
                {
                    "type": "text",
                    "text": "Write a  funny, witty, or thought-provoking caption for a daily astronomy picture using the NASA API. The caption should align with the image's theme, be engaging for a Twitter audience, and fit within 200 characters, including spaces. Use line breaks if needed for readability. Avoid using quotation marks in the captions."
                }
            ]},
            {
                "role": "user",
                "content": context
            }
        ]
    )
    return completion.choices[0].message.content