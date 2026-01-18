try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

import time
import re
import os
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_untappd_friends_words(access_token: str) -> dict:
    """
    Fetches recent check-ins from the user's friends feed via Untappd API 
    and extracts relevant words, categorized.
    """
    print("DEBUG: Fetching Untappd friends feed...")
    try:
        # Endpoint for User's Friend Activity Feed: /v4/checkin/recent
        # Note: This endpoint might return global or friends depending on params, 
        # but for authenticated users, /v4/checkin/recent usually gives the friend feed by default or via param.
        # Let's try the standard activity feed.
        url = "https://api.untappd.com/v4/checkin/recent" 
        params = {"access_token": access_token, "limit": 50}
        
        response = requests.get(url, params=params)
        if response.status_code != 200:
            print(f"Error fetching Untappd data: {response.text}")
            return []
            
        data = response.json()
        items = data.get("response", {}).get("checkins", {}).get("items", [])
        
        words = []
        for item in items:
            beer = item.get("beer", {})
            brewery = item.get("brewery", {})
            venue = item.get("venue", {})
            
            # Extract Beer Name
            if beer.get("beer_name"):
                words.append(beer["beer_name"])
            
            # Extract Style
            if beer.get("beer_style"):
                words.append(beer["beer_style"])
                
            # Extract Brewery
            if brewery.get("brewery_name"):
                words.append(brewery["brewery_name"])
                
            # Extract Location (City/Venue)
            if venue:
                 if venue.get("venue_name"):
                     words.append(venue["venue_name"])
                 if venue.get("location", {}).get("venue_city"):
                     words.append(venue["location"]["venue_city"])

        # Shuffle and Clean
        print(f"DEBUG: Found {len(words)} raw terms from Untappd.")
        return clean_words_with_llm(words)

    except Exception as e:
        print(f"Error in get_untappd_friends_words: {e}")
        return []

def clean_words_with_llm(raw_words: list[str]) -> dict:
    """
    Uses OpenAI to clean the scraped word list and categorize it.
    Returns a dict with keys: 'beer_styles', 'breweries', 'venues', 'friends', 'flavors', 'miscellaneous'.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    # If no key or no words, return basic structure with raw words in 'miscellaneous'
    if not openai_key or not raw_words:
        return {
            "beer_styles": [],
            "breweries": [],
            "venues": [],
            "friends": [],
            "flavors": [],
            "miscellaneous": raw_words
        }

    try:
        client = OpenAI(api_key=openai_key)
        
        # Deduplicate and limit to save tokens
        unique_words = list(set(raw_words))
        if len(unique_words) > 200:
            unique_words = unique_words[:200]
            
        joined_words = ", ".join(unique_words)
        print(f"DEBUG: Asking LLM to clean and categorize {len(unique_words)} words...")

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data cleaner for a beer attributes word cloud. "
                        "Input: A raw list of strings scraped from a website or menu. "
                        "Task: CLEAN the words (fix typos, remove UI junk) and CATEGORIZE them into a JSON structure. "
                        "Categories:\n"
                        "- 'beer_styles': (e.g., IPA, Stout, Lager, Gose)\n"
                        "- 'breweries': (e.g., Stone, Guinness, Other Half)\n"
                        "- 'venues': (e.g., The Pub, McSorleys, Beer Garden)\n"
                        "- 'friends': (Names of people if apparent, e.g., Chris, Dave. If ambiguous, put in misc)\n"
                        "- 'flavors': (e.g., Hoppy, Malty, Citrus, Dank)\n"
                        "- 'miscellaneous': (Anything else valid but not fitting above)\n"
                        "\n"
                        "Rules:\n"
                        "1. FIX partial/corrupted words.\n"
                        "2. REMOVE all UI elements (Settings, Login, Cookies, Privacy, Menu, 'Analyze').\n"
                        "3. REMOVE generic/stop words (Beer, Drink, Pour, View, Full) unless they are specific flavors.\n"
                        "4. Output valid JSON only."
                    )
                },
                {
                    "role": "user",
                    "content": f"Process this list: {joined_words}"
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=800
        )
        
        cleaned_text = response.choices[0].message.content
        import json
        data = json.loads(cleaned_text)
        
        # Ensure all keys exist
        keys = ["beer_styles", "breweries", "venues", "friends", "flavors", "miscellaneous"]
        for k in keys:
            if k not in data:
                data[k] = []
                
        print(f"DEBUG: LLM categorization complete.")
        return data

    except Exception as e:
        print(f"Warning: LLM cleaning failed ({e}). Returning raw list in 'miscellaneous'.")
        return {
            "beer_styles": [],
            "breweries": [],
            "venues": [],
            "friends": [],
            "flavors": [],
            "miscellaneous": raw_words
        }

def describe_venue(venue_name: str) -> str:
    """
    Asks LLM to describe the vibe/theme of a venue based on its name.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or not venue_name:
        return ""
        
    try:
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a creative writer. Given a venue name, imagine its atmosphere, decor, and vibe. Describe it in 2-3 evocative sentences suitable for an art prompt (e.g. lighting, materials, crowd, mood)."},
                {"role": "user", "content": f"Describe the venue: {venue_name}"}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception:
        return ""


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
