import re
import base64
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# No longer initializing EasyOCR to save memory/startup time
# reader = easyocr.Reader(['en']) 

def get_ocr_words(image_bytes: bytes) -> list[str]:
    """
    Extracts words from image bytes using GPT-4o Vision.
    Encodes image to Base64 and asks GPT to read the content words.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: No OpenAI Key found for Vision OCR.")
            return []

        client = OpenAI(api_key=api_key)
        
        # Encode bytes to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        print("Calling GPT-4o Vision for text extraction...")
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are a text extractor. Your job is to look at a word cloud or screenshot and extract the meaningful content words. Ignore standard UI elements (wifi, battery, time, settings, menus, 'untappd', 'beer', 'brewery' headers). Output ONLY a comma-separated list of the distinct, interesting words found (like beer names, brewery names, styles, flavors). Do not output full sentences."
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the beer names, brewery names, and tasting notes from this image. Ignore interface text."},
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
            max_tokens=300
        )

        content = response.choices[0].message.content
        print(f"GPT Vision Raw Output: {content}")
        
        # Basic cleanup of the response string into a list
        cleaned_str = re.sub(r'[^\w\s,]', '', content) # Remove unexpected special chars but keep commas
        words = [w.strip() for w in cleaned_str.split(',') if len(w.strip()) > 2]
        
        # Remove common duplicates or junk that might have slipped through
        # (GPT is usually good, but a second pass helps)
        junk_words = {"untappd", "settings", "profile", "beer", "brewery", "image", "extracted", "text"}
        final_words = [w for w in words if w.lower() not in junk_words]
        
        print(f"GPT Found {len(final_words)} words: {final_words[:10]}...")
        return final_words

    except Exception as e:
        print(f"GPT Vision OCR Failed: {e}")
        return []
