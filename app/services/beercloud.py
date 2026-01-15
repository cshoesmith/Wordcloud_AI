try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

import time
import re
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def clean_words_with_llm(raw_words: list[str]) -> list[str]:
    """
    Uses OpenAI to clean the scraped word list: fixing typos, removing UI junk,
    and ensuring only relevant beer-related terms remain.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or not raw_words:
        return raw_words

    try:
        client = OpenAI(api_key=openai_key)
        
        # Deduplicate and limit to save tokens
        unique_words = list(set(raw_words))
        # If we have too many, just take the top 150 to avoid massive context
        if len(unique_words) > 150:
            unique_words = unique_words[:150]
            
        joined_words = ", ".join(unique_words)
        print(f"DEBUG: Asking LLM to clean {len(unique_words)} words...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data cleaner for a beer attributes word cloud. "
                        "Input: A raw list of strings scraped from a website. "
                        "Task: Return a clean, comma-separated list of ONLY relevant beer descriptors (flavors, styles, ingredients) and brewery names. "
                        "Rules:\n"
                        "1. FIX partial/corrupted words (e.g., 'Strawb...' -> 'Strawberry', 'Haz...' -> 'Hazy').\n"
                        "2. REMOVE all UI elements (Settings, Login, Cookies, Privacy, Menu, 'Analyze').\n"
                        "3. REMOVE generic/stop words (Beer, Drink, Pour, View, Full).\n"
                        "4. KEEP specialized terms (DIPA, Gose, Brett, Citra, Mosaic).\n"
                        "5. Output ONLY the comma-separated list, nothing else."
                    )
                },
                {
                    "role": "user",
                    "content": f"Clean this list: {joined_words}"
                }
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        cleaned_text = response.choices[0].message.content
        # robust splitting
        cleaned_list = [w.strip() for w in cleaned_text.split(',') if len(w.strip()) > 2]
        
        print(f"DEBUG: LLM cleaned list size: {len(cleaned_list)}")
        return cleaned_list

    except Exception as e:
        print(f"Warning: LLM cleaning failed ({e}). Returning original list.")
        return raw_words

def get_wordcloud_data(cookie_string: str = None):
    """
    Launches a browser to fetch word cloud data.
    If the user is not logged in, the browser window remains open for them to log in.
    """
    # Simulation hook for testing without opening a browser
    if cookie_string and "simulated_success" in cookie_string:
         return ["IPA", "Stout", "Hazy", "Sour", "Lager", "Ale", "Hops", "Malt", "Brewery", "Craft"]

    data = []
    
    if sync_playwright is None:
        print("WARNING: Playwright not installed. Scraping disabled.")
        return []

    with sync_playwright() as p:
        # Launch browser with headless=False so the user can interact if needed
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # If a cookie string was manually provided, try to add it (optional fallback)
        if cookie_string and "sb_session" in cookie_string: # Assuming sb_session or similar
            # Logic to parse and add cookies would go here, but usually it's cleaner to just let the user login
            pass

        page = context.new_page()
        
        print("Navigating to BeerCloud...")
        try:
            page.goto("https://beercloud.wardy.au/")
            
            # Check if we need to login. 
            print("Checking login status...")
            
            # Wait loop: Wait for "Login with Untappd" to disappear
            start_time = time.time()
            logged_in = False
            
            while time.time() - start_time < 120:
                # Check for common login indicator
                try:
                    # Using a broad selector for the login button/link we saw earlier
                    if page.get_by_text("Login with Untappd").count() > 0 and page.get_by_text("Login with Untappd").is_visible():
                         # print("Waiting for login...", end='\r') # Avoid spamming stdout in this environment
                         page.wait_for_timeout(3000)
                    else:
                        print("Login button not visible. Assuming logged in!")
                        logged_in = True
                        break
                except Exception as e:
                    print(f"Error checking login state: {e}")
                    page.wait_for_timeout(3000)

            if logged_in:
                # Wait for the word cloud to render
                print("Waiting for word cloud to render...")
                page.wait_for_timeout(8000)  # Give it a good 8 seconds
                
                print("Extracting words...")
                try:
                    # Strategy 1: SVG text elements (common for D3/word clouds)
                    svg_texts = page.locator("svg text").all_inner_texts()
                    if len(svg_texts) > 5:
                        data = svg_texts
                        print(f"Found {len(data)} words in SVG.")
                    else:
                        print("SVG strategy insufficient.")

                    # Strategy 1.5: Spans/Divs commonly used for word clouds
                    # If SVG didn't work, try capturing spans (often used for HTML clouds)
                    if not data:
                         span_texts = page.locator("span").all_inner_texts()
                         candidates = [s for s in span_texts if len(s) > 3]
                         if len(candidates) > 5:
                             data = list(set(candidates))
                             print(f"Found {len(data)} words in spans.")

                    # Strategy 2: just body text fallback
                    if not data:
                        body_text = page.evaluate("document.body.innerText")
                        # Simple cleanup: words > 3 chars
                        words = [w.strip() for w in body_text.split() if len(w.strip()) > 3]
                        data = list(set(words))
                        print(f"Found {len(data)} words in body.")
                        
                except Exception as ex:
                    print(f"Extraction error: {ex}")
            else:
                print("Timed out waiting for login.")
            # FILTERING & CLEANUP
            # Use LLM to clean up the scraped data (Fixes corrupted words and removes UI junk)
            if data:
                print("Refining extracted words with LLM...")
                data = clean_words_with_llm(data)
            
            # Debug: Take a screenshot to see what the bot sees
            try:
                page.screenshot(path="static/debug_page.png")
                print("Saved debug screenshot to static/debug_page.png")
            except Exception:
                pass

            # FINAL SAFETY FALLBACK
            # If we still have no data (or very little), use a fallback list so the AI has something to draw.
            if len(data) < 5:
                print("Extraction failed to find sufficient quality text. Using fallback beer words.")
                data = ["IPA", "Stout", "Hazy", "Lager", "Ale", "Hops", "Malt", "Brewery", "Craft", "Pilsner", "Saison", "Lambic"]
            
        except Exception as e:
            print(f"Error during browser interaction: {e}")
            
        except Exception as e:
            print(f"Error during browser interaction: {e}")
        finally:
            browser.close()

    return data
