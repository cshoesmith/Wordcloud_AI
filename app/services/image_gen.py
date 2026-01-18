from openai import OpenAI
import os
import requests
import urllib.parse

from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

def enrich_prompt(data: any, style: str, theme: str = "Beer", venue_description: str = "") -> dict:
    """Uses OpenAI to create a detailed visual description from the word list/dict. Returns dict with 'visual_prompt' and 'reasoning'."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("DEBUG: No OpenAI Key found, skipping enrichment.")
        return None

    try:
        client = OpenAI(api_key=openai_key)
        
        # Prepare content based on input type
        if isinstance(data, dict):
            # Formatted string for the LLM
            input_text = "Categorized Keywords:\n"
            for category, items in data.items():
                if items:
                    input_text += f"- {category.upper()}: {', '.join(items)}\n"
            if venue_description:
                input_text += f"\nVENUE VIBE/THEME: {venue_description}\n"
        else:
            # Fallback for list
            input_text = f"Keywords: {', '.join(data)}"

        context_desc = "categorized beer and venue data" if isinstance(data, dict) else "list of words"

        system_content = (
            f"You are an expert AI Art Director and Data Storyteller. Your goal is to transform {context_desc} "
            "into a rich, cohesive visual narrative prompt for an image generator.\n\n"
            "PROCESS:\n"
            "1. ANALYZE: Review the keywords. Pay special attention to 'BEER_STYLES', 'BREWERIES', and 'VENUES'.\n"
            "2. THEME: If a VENUE VIBE is provided, use it as the core atmosphere (lighting, mood, setting).\n"
            "3. METAPHOR: Do NOT just list the words. Transform specific items into visual metaphors.\n"
            "   - A 'Stout' might become a river of dark velvet or an obsidian monolith.\n"
            "   - 'Stone Brewery' might appear as literal gargoyles or stone architecture.\n"
            "   - Friends' names can be subtle details (e.g., 'Chris' engraved on a mug, or a character named Chris).\n"
            "4. STORY: Develop a short visual scene where these elements coexist.\n"
            "5. PROMPT: Write a highly detailed image generation prompt based on this narrative in the requested style."
        )
        
        style_instructions = {
            "scarry": (
                "Style: Richard Scarry 'Busytown' Illustration (1970s Children's Book).\n"
                "Details: A chaotic, happy scene. "
                "Every beer style and brewery must be a physical shop, character, or vehicle. "
                "Draw a 'Where's Waldo' density. Flat colors, detailed ink lines."
            ),
            "dali": (
                "Style: Salvador Dali Surrealist Oil Painting.\n"
                "Details: A dreamscape. Venue descriptions become the warped landscape. "
                "Beer objects melt or float. High symbolism. "
                "Captures the subconscious feeling of the drinking session."
            ),
            "picasso": (
                "Style: Pablo Picasso Synthetic Cubism (1912).\n"
                "Details: Fragment and reassemble the venue and bottles. "
                "Use the venue vibe to dictate the color palette."
            ),
            "cyberpunk": (
                "Style: High-Fidelity Cyberpunk / Blade Runner Aesthetic.\n"
                "Details: A futuristic night market. The venue is a high-tech lounge. "
                "Breweries are neon corporate logos. "
                "High contrast, rain, steam, neon."
            ),
            "technology": (
                "Style: Abstract Future Technology / Data Visualization.\n"
                "Details: A visual representation of the data as a complex network. "
                "The venue is the server. Beers are data packets."
            )
        }
        
        # Default to Dali if style unknown
        specific_instruction = style_instructions.get(style, style_instructions["dali"])
        
        user_content = (
            f"INPUT DATA:\n{input_text}\n\n"
            f"Create the prompt applying this specific style guidance:\n{specific_instruction}"
        )

        print(f"DEBUG: Calling OpenAI for prompt enrichment (Style: {style})...")

        # Use gpt-4o for better detail text generation
        model = "gpt-4o"
        try:
             response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content + "\n\nCRITICAL: Output your response as valid JSON with two fields: 'visual_prompt' (the final image prompt) and 'reasoning' (a summary of your analysis, the categories found, and the story you created)."}
                ],
                max_tokens=800,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            print(f"DEBUG: {model} failed ({e}), falling back to gpt-3.5-turbo")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content + "\n\nCRITICAL: Output your response as valid JSON with two fields: 'visual_prompt' (the final image prompt) and 'reasoning' (a summary of your analysis, the categories found, and the story you created)."}
                ],
                max_tokens=800,
            )

        content = response.choices[0].message.content
        print(f"DEBUG: Enriched prompt raw: {content}")
        
        # Parse JSON
        import json
        try:
            data = json.loads(content)
            return data
        except json.JSONDecodeError:
            print("ERROR: Could not parse JSON from LLM, returning raw text as prompt.")
            return {"visual_prompt": content, "reasoning": "Could not extract reasoning."}
        
    except Exception as e:
        print(f"DEBUG: OpenAI Enrichment failed: {e}")
        return None

def generate_image_google(prompt: str) -> str:
    """
    Generates an image using Google's Gemini 3 Pro (Nano Banana Pro) model.
    """
    try:
        from google import genai
        from google.genai import types
        import uuid
        import io
        import base64
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY missing in environment")

        # Configure Client
        client = genai.Client(api_key=api_key)
        
        print(f"DEBUG: Calling Google Gemini 3 Pro (Nano Banana Pro)...")
        # print(f"DEBUG: Prompt: {prompt[:50]}...")
        
        # Use generate_content for Gemini 3 image generation
        # Allowing TEXT modality too because it's a "Thinking" model
        response = client.models.generate_content(
            model='gemini-3-pro-image-preview',
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE'], 
                image_config=types.ImageConfig(
                    aspect_ratio="1:1"
                )
            )
        )
        
        # Collect all images from the response
        found_images = []
        
        if response.parts:
            for part in response.parts:
                 if part.inline_data and part.inline_data.mime_type.startswith("image"):
                     found_images.append(part.inline_data.data)

        if found_images:
            # The docs say: "The last image within Thinking is also the final rendered image."
            # So we take the last one.
            final_image_data = found_images[-1]
            
            # Handle bytes vs base64 string
            if isinstance(final_image_data, str):
                try:
                    # Check if it's already a base64 string we can just use
                    # Logic: if it decodes successfully, it's b64.
                    image_bytes = base64.b64decode(final_image_data)
                    b64_string = final_image_data
                except Exception:
                    # It was a raw string? Convert to bytes then b64
                    image_bytes = final_image_data.encode() if hasattr(final_image_data, 'encode') else final_image_data
                    b64_string = base64.b64encode(image_bytes).decode('utf-8')
            else:
                # It is bytes
                b64_string = base64.b64encode(final_image_data).decode('utf-8')

            # Vercel Read-Only Fix: Return Data URI instead of saving to file
            print(f"DEBUG: Returning Google Image as Data URI (Length: {len(b64_string)})")
            return f"data:image/png;base64,{b64_string}"
        
        # If we got here, we had no images. Let's see if there was text output (error or refusal).
        text_content = " ".join([p.text for p in response.parts if p.text])
        if text_content:
             print(f"DEBUG: No images, but text received: {text_content[:200]}...")
             raise ValueError(f"Model returned text but no image: {text_content[:100]}...")
        
        raise ValueError("No content returned from Google API")

    except ImportError:
        error_msg = "'google-genai' package not installed."
        print(f"ERROR: {error_msg}")
        raise ImportError(error_msg)
    except Exception as e:
        print(f"ERROR: Google Generation failed: {e}")
        # Raise exception so it appears in the UI instead of generic 'failed'
        raise e

def generate_image_dalle(prompt: str) -> str:
    """
    Generates an image using OpenAI DALL-E 3.
    Saves it locally to static/generated/ and returns a local relative URL.
    """
    import uuid
    import base64
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OpenAI Key missing for DALL-E generation")
        return None

    try:
        client = OpenAI(api_key=api_key)
        
        print(f"DEBUG: Calling DALL-E 3 generation...")
        
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt[:3900], # DALL-E 3 char limit is 4000
            size="1024x1024",
            quality="standard",
            n=1,
        )

        image_url_temp = response.data[0].url
        
        # Download the image bytes
        img_data = requests.get(image_url_temp).content
        
        # Vercel Read-Only Fix: Return Data URI
        b64_string = base64.b64encode(img_data).decode('utf-8')
        
        print(f"DEBUG: Returning DALL-E Image as Data URI (Length: {len(b64_string)})")
        return f"data:image/png;base64,{b64_string}"

    except Exception as e:
        print(f"ERROR: DALL-E Generation failed: {e}")
        return None


def generate_image(data: any, style: str = 'dali') -> str:
    from app.services.beercloud import describe_venue
    
    venue_desc = ''
    if isinstance(data, dict):
        # Implement Logic to pick a venue and get description
        venues = data.get('venues', [])
        if venues:
            # Pick the first one or random? First is fine.
            venue_name = venues[0]
            print(f'DEBUG: Found venue: {venue_name}. Asking for description...')
            venue_desc = describe_venue(venue_name)
    
    # Step 1: Enrich Prompt
    enriched = enrich_prompt(data, style, venue_description=venue_desc)
    
    visual_prompt = ''
    if enriched and 'visual_prompt' in enriched:
        visual_prompt = enriched['visual_prompt']
    else:
        # Fallback if enrichment fails
        if isinstance(data, dict):
            # flatten
            flat = []
            for k,v in data.items():
                if isinstance(v, list): flat.extend(v)
            visual_prompt = f'A surreal artistic beer cloud featuring: {', '.join(flat[:20])}'
        else:
             visual_prompt = f'A surreal artistic beer cloud featuring: {', '.join(data[:20])}'

    # Step 2: Generate Image
    # Try Google First, then DALL-E
    try:
        return generate_image_google(visual_prompt)
    except Exception as e:
        print(f'DEBUG: Google Gen failed ({e}), trying DALL-E...')
        try:
             return generate_image_dalle(visual_prompt)
        except Exception as e2:
             print(f'ERROR: All image generation failed: {e2}')
             return None

