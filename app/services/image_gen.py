from openai import OpenAI
import os
import requests
import urllib.parse

from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

def enrich_prompt(words: list[str], style: str, theme: str = "Beer") -> dict:
    """Uses OpenAI to create a detailed visual description from the word list. Returns dict with 'visual_prompt' and 'reasoning'."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("DEBUG: No OpenAI Key found, skipping enrichment.")
        return None

    try:
        client = OpenAI(api_key=openai_key)
        
        if theme.lower() == "beer":
            context_desc = "ocr from beer menus/history"
            entity_class = "Beer Names (Stouts, IPAs), Venues (Pubs, Breweries), Locations (Cities, Countries), and Styles/Flavors"
            expand_ex = "'Guinness' -> dark, velvet, Irish harp; 'IPA' -> hops, green vines, bitterness"
            item_name_ref = "beer/venue name"
            item_coll_ref = "beer names"
            experience_ref = "beer experience"
        else:
            context_desc = f"list items related to the theme section: '{theme}'"
            entity_class = f"Key Entities, Categories, and Descriptors relevant to the theme '{theme}'"
            expand_ex = f"items related to '{theme}' -> visual metaphors"
            item_name_ref = f"'{theme}' item name"
            item_coll_ref = f"'{theme}' items"
            experience_ref = f"'{theme}' experience"

        system_content = (
            f"You are an expert AI Art Director and Data Storyteller. Your goal is to transform a list of raw text ({context_desc}) "
            "into a rich, cohesive visual narrative. \n"
            "PROCESS:\n"
            f"1. ANALYZE: Identify every entity in the list. Classify them into: {entity_class}.\n"
            f"2. EXPAND: For each key entity, imagine its visual essence (e.g., {expand_ex}).\n"
            "3. NARRATE: Develop a short visual story or scene where all these expanded elements coexist naturally.\n"
            "4. PROMPT: Write a highly detailed image generation prompt based on this narrative in the requested style."
        )
        
        joined_words = ", ".join(words)
        
        style_instructions = {
            "scarry": (
                "Style: Richard Scarry 'Busytown' Illustration (1970s Children's Book).\n"
                "Details: A chaotic, happy scene teeming with anthropomorphic animals (pigs in lederhosen, cat waiters). "
                f"Every {item_name_ref} must be a physical object or shop sign in the scene. "
                "Draw a 'Where's Waldo' density. Flat colors, detailed ink lines."
            ),
            "dali": (
                "Style: Salvador Dali Surrealist Oil Painting.\n"
                "Details: A dreamscape where time and matter are fluid. Transform the {item_coll_ref} into surreal objects "
                "(e.g., a clock made of foam, a burning giraffe made of hops). "
                "Long shadows, vast horizons, double images. Captures the subconscious feeling of the drinking session."
            ),
            "picasso": (
                "Style: Pablo Picasso Synthetic Cubism (1912).\n"
                "Details: Fragment and reassemble the {experience_ref}. Show the bottles, glasses, and pub atmosphere from multiple angles simultaneously. "
                "Use geometric shapes, collage-like textures, and a muted but rich color palette (ochre, grey, blue). "
                "Abstract the text into graphical elements within the composition."
            ),
            "cyberpunk": (
                "Style: High-Fidelity Cyberpunk / Blade Runner Aesthetic.\n"
                "Details: A futuristic night market in Neo-Tokyo. The {item_coll_ref} are glowing neon holograms and advertisements reflected in rain-slicked streets. "
                "Cybernetic patrons sipping glowing liquids. High contrast, blue and pink, chromatic aberration, steam, grime, and high-tech."
            ),
            "technology": (
                "Style: Abstract Future Technology / Data Visualization.\n"
                "Details: A visual representation of the {experience_ref} as a complex digital network. "
                "Circuit board pathways made of gold liquid. Nodes representing beers pulsing with light. "
                "Clean, white, silver, and blue color scheme. 3D render, Octane render, 8k resolution."
            )
        }
        
        # Default to Dali if style unknown
        specific_instruction = style_instructions.get(style, style_instructions["dali"])
        
        user_content = (
            f"Input Words ({theme}): {joined_words}.\n\n"
            f"Execute the Multi-stage process. Categories -> Expansions -> Story.\n"
            f"Finally, generate the prompt applying this specific style guidance:\n{specific_instruction}"
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

