import re
import base64
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# No longer initializing EasyOCR to save memory/startup time
# reader = easyocr.Reader(['en']) 

def get_ocr_words(image_bytes: bytes) -> dict:
    """
    Extracts words from image bytes using GPT-4o Vision and categorizes them.
    Returns structured dict.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: No OpenAI Key found for Vision OCR.")
            return {}

        client = OpenAI(api_key=api_key)
        
        # Encode bytes to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        print("Calling GPT-4o Vision for text extraction and categorization...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a text extractor and classifier. Read the text from the image (menu, check-in, screenshot). "
                        "EXTRACT and CATEGORIZE the relevant entities into valid JSON.\n"
                        "Categories:\n"
                        "- 'beer_styles'\n"
                        "- 'breweries'\n"
                        "- 'venues' (Restaurant, Pub, Bar names)\n"
                        "- 'friends' (Usernames, People names)\n"
                        "- 'flavors' (Tasting notes)\n"
                        "- 'miscellaneous'\n"
                        "Ignore UI elements."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract and categorize the data from this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=600
        )

        content = response.choices[0].message.content
        print(f"GPT Vision Raw Output: {content}")
        
        import json
        try:
            data = json.loads(content)
            # Normalize keys
            expected_keys = ["beer_styles", "breweries", "venues", "friends", "flavors", "miscellaneous"]
            for k in expected_keys:
                if k not in data:
                    data[k] = []
            return data
        except json.JSONDecodeError:
            print("GPT returned invalid JSON. Falling back to simple list in miscellaneous.")
            return {"miscellaneous": [content], "beer_styles": [], "breweries": [], "venues": [], "friends": [], "flavors": []}

    except Exception as e:
        print(f"GPT Vision OCR Failed: {e}")
        return {}
