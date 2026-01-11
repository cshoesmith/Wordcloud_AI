from openai import OpenAI
import os
import requests
import urllib.parse

from dotenv import load_dotenv

# Ensure env is loaded
load_dotenv()

def enrich_prompt(words: list[str], style: str) -> str:
    """Uses OpenAI to create a detailed visual description from the word list."""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("DEBUG: No OpenAI Key found, skipping enrichment.")
        return None

    try:
        client = OpenAI(api_key=openai_key)
        
        system_content = "You are a creative art director optimizing prompts for AI image generation. Create cohesive, visual scenes."
        
        joined_words = ", ".join(words)
        
        if style == "scarry":
            user_content = (
                f"Create a prompt for a chaotic, hyper-detailed Richard Scarry 'Busytown' style illustration of a German beer garden. "
                "The scene MUST be teeming with life: hundreds of anthropomorphic animals (foxes, pigs, cats) engaged in specific, busy activities found in a beer garden. "
                f"Integrate these specific words as labeled objects, shop signs, or vehicles in the scene: {joined_words}. "
                "Do not be abstract. Describe a 'Where's Waldo' level of density. "
                "Include details like a worm driving an apple car, a pig waiter dropping pretzels, and crowded tables. "
                "Use the provided words labels for the objects in the scene. "
                "The style is flat colors, detailed ink lines, children's book illustration."
            )
        else:
            user_content = (
                f"Create a detailed visual description for a Salvador Dali surrealist masterpiece painting. "
                f"The scene should incorporate these specific concepts/words conceptually or visually (melting clocks style, long legged elephants, floating objects): {joined_words}. "
                "Describe a dreamlike, artistic composition with deep shadows and vivid sky. "
                "The description should be a single paragraph, visually descriptive, suitable for an image generator. "
                "Keep it under 500 characters."
            )

        print("DEBUG: Calling OpenAI for prompt enrichment...")
        # Use gpt-4o for better detail text generation
        model = "gpt-4o"
        try:
             response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=300
            )
        except Exception as e:
            print(f"DEBUG: {model} failed ({e}), falling back to gpt-3.5-turbo")
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content}
                ],
                max_tokens=300
            )

        enriched = response.choices[0].message.content
        print(f"DEBUG: Enriched prompt: {enriched}")
        return enriched
        
    except Exception as e:
        print(f"DEBUG: OpenAI Enrichment failed: {e}")
        return None

def generate_image_from_prompt(prompt: str) -> str:
    """Generates image URL from a raw prompt string."""
    api_key = os.getenv("POLLINATIONS_API_KEY")
    encoded_prompt = urllib.parse.quote(prompt)
    
    import random
    seed = random.randint(0, 10000)
    
    # We switch back to the main image endpoint which is more compatible with direct URL embedding
    # and supports query parameters for configuration.
    base_url = "https://image.pollinations.ai/prompt"
    model = "flux" 
    
    params = f"?width=1024&height=1024&seed={seed}&nologo=true&model={model}"
    
    if api_key:
        # Some endpoints accept the key to bypass cache or limits, though standard usage is often free.
        # We add it just in case support is added or it helps with rate limits.
        # private=true might not work on the public endpoint but doesn't hurt.
        params += f"&private=true"
        
    image_url = f"{base_url}/{encoded_prompt}{params}"
    
    print(f"DEBUG: Generated URL (model={model}): {image_url}")
    return image_url

def generate_image(words: list[str], style: str = "dali") -> str:
    """
    Generates an image URL using Pollinations.ai Gen API with API Key.
    """
    api_key = os.getenv("POLLINATIONS_API_KEY")
    print(f"DEBUG: API Key loaded: {api_key[:5] if api_key else 'None'}... (Length: {len(api_key) if api_key else 0})")
    
    # Try to enrich the prompt first
    # We take slightly more words for the LLM to process
    rich_prompt = enrich_prompt(words[:30], style)
    
    if rich_prompt:
        prompt = rich_prompt
    else:
        # Fallback to simple template
        joined_words = ", ".join(words[:20]) # Limit to top 20
        
        if style == "scarry":
            prompt = (
                f"A busy, detailed, whimsical Richard Scarry style illustration of a large German beer garden. "
                f"The scene should incorporate these elements creatively: {joined_words}. "
                "Featuring anthropomorphic animals enjoying beer, sunny day, detailed line work, flat colors, children's book illustration style."
            )
        else:
            # Default to Dali
            prompt = (
                f"A surrealist masterpiece painting by Salvador Dali featuring these specific elements: {joined_words}. "
                "The scene should artfully blend beer culture, obscure venues, distinct tasting notes, and friends into a dreamlike landscape. "
                "High resolution, cinematic lighting, oil painting texture, vivid colors, deep shadows."
            )
    
    return generate_image_from_prompt(prompt)

    # OLD OPENAI CODE PRESERVED BELOW FOR REFERENCE
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = OpenAI(api_key=api_key)
    # ... (rest of old openai code)
    """
