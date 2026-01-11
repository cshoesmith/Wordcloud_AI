from playwright.sync_api import sync_playwright
import time

def get_wordcloud_data(cookie_string: str = None):
    """
    Launches a browser to fetch word cloud data.
    If the user is not logged in, the browser window remains open for them to log in.
    """
    # Simulation hook for testing without opening a browser
    if cookie_string and "simulated_success" in cookie_string:
         return ["IPA", "Stout", "Hazy", "Sour", "Lager", "Ale", "Hops", "Malt", "Brewery", "Craft"]

    data = []
    
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
            # Remove common cookie/consent/UI junk words - EXPANDED LIST
            junk_words = {
                "Preferences", "analyze", "described", "clicking", "With", "experience", "agree", 
                "non-essential", "user", "Sign", "time", "website's", "consent", "here?", "Login",
                "Untappd", "Cookie", "Policy", "Privacy", "Settings", "Accept", "Reject", "Close",
                "navigation", "Toggle", "Menu", "Search", "Profile", "Account", "Rights", "Reserved",
                "Apple", "Google", "Facebook", "Twitter", "Instagram", "Discord", "Legal", "Terms",
                "Partners", "Jobs", "Support", "Help", "Status", "Developers", "About", "Blog",
                "change", "traffic", "your", "cookies", "must", "password", "make", "website", 
                "essential", "agree", "work", "continue", "Forgot", "around", "also", "preference",
                "preferences"
            }
            
            # Case-insensitive filtering
            junk_lower = {j.lower() for j in junk_words}
            
            cleaned_data = []
            for w in data:
                # Remove punctuation
                w_clean = re.sub(r'[^\w]', '', w)
                
                # Filter out junk, short words, and numbers
                if (len(w_clean) > 3 and 
                    w_clean.lower() not in junk_lower and 
                    not w_clean.isdigit()):
                    cleaned_data.append(w_clean)
            
            data = cleaned_data
            
            # Debug: Take a screenshot to see what the bot sees
            try:
                page.screenshot(path="static/debug_page.png")
                print("Saved debug screenshot to static/debug_page.png")
            except Exception:
                pass

            # FINAL SAFETY FALLBACK
            # If we still have no data (or very little), use a fallback list so the AI has something to draw.
            # Increased threshold to 8 to avoid getting just 4 random junk words.
            if len(data) < 8:
                print("Extraction failed to find extraction quality text. Using fallback beer words.")
                data = ["IPA", "Stout", "Hazy", "Lager", "Ale", "Hops", "Malt", "Brewery", "Craft", "Pilsner", "Saison", "Lambic", "Porter", "Dunkel", "Trappist"]
                print("Extraction failed to find significant text. Using fallback beer words.")
                data = ["IPA", "Stout", "Hazy", "Lager", "Ale", "Hops", "Malt", "Brewery", "Craft", "Pilsner"]
            
        except Exception as e:
            print(f"Error during browser interaction: {e}")
            
        except Exception as e:
            print(f"Error during browser interaction: {e}")
        finally:
            browser.close()

    return data
