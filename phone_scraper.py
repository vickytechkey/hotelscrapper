import sys
import os
import json
import time
import re
import argparse
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

def clean_phone_number(raw_phone):
    if not raw_phone:
        return None
    # Remove unwanted leading/trailing whitespace
    phone = raw_phone.strip()
    # If starting with tel:, strip it
    if phone.lower().startswith("tel:"):
        phone = phone[4:]
    return phone

def scrape_google_phone(driver, hotel_name, location):
    query = f"{hotel_name} {location} phone number"
    url = f"https://www.google.com/search?q={re.sub(r'\s+', '+', query)}"
    print(f"Searching Google: {query}")
    
    try:
        driver.get(url)
        time.sleep(4) # Wait for page load and prevent search blocking
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. Search for tel links (href="tel:...")
        tel_links = soup.select('a[href^="tel:"]') or soup.select('a[href*="tel"]')
        for link in tel_links:
            href = link.get('href', '')
            match = re.search(r'tel:([\d\s\-\+\(\)]+)', href, re.IGNORECASE)
            if match:
                phone = clean_phone_number(match.group(1))
                if phone:
                    return phone
                    
        # 2. Search by class common to Google Knowledge Panel phone number (.Lrzca or .zVvyb or similar)
        phone_el = soup.select_one('.Lrzca') or soup.select_one('[class*="Lrzca"]') or soup.select_one('.zVvyb')
        if phone_el and phone_el.text:
            phone = clean_phone_number(phone_el.text)
            if phone:
                return phone
                
        # 3. Search visible text via Regex
        # Find any text matching "Phone: +91 422..." or "Phone: 0422..."
        page_text = soup.get_text()
        phone_patterns = [
            r'Phone\s*:\s*([\+\d\s\-\(\)]+)',
            r'Call\s*:\s*([\+\d\s\-\(\)]+)'
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for m in matches:
                # Clean up and validate matches
                cleaned = re.sub(r'[^\d\+\-\s\(\)]', '', m).strip()
                if len(cleaned) >= 7 and len(cleaned) <= 20:
                    return cleaned
                    
    except Exception as e:
        print(f"Error during Google search: {e}")
        
    return None

def init_chrome_driver(options, headless):
    import re
    try:
        return uc.Chrome(options=options, headless=headless)
    except Exception as e:
        err_msg = str(e)
        match = re.search(r"Current browser version is ([\d.]+)", err_msg)
        if match:
            version = match.group(1)
            major_version = int(version.split('.')[0])
            print(f"Detected Chrome version mismatch. Retrying with version_main={major_version}...")
            try:
                return uc.Chrome(options=options, headless=headless, version_main=major_version)
            except Exception as retry_err:
                print(f"Retry with version_main={major_version} failed: {retry_err}")
                raise retry_err
        raise e

def main():
    parser = argparse.ArgumentParser(description="Google Phone Number Scraper for Hotels")
    parser.add_argument("--input", type=str, required=True, help="Path to the JSON file")
    parser.add_argument("--limit", type=int, default=10, help="Max number of phone numbers to fetch")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: File {args.input} does not exist!")
        sys.exit(1)
        
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            hotels = json.load(f)
    except Exception as parse_err:
        print(f"Error reading JSON file: {parse_err}")
        sys.exit(1)
        
    print(f"Loaded {len(hotels)} hotels from {args.input}")
    
    # Filter hotels that don't have a phone number yet
    pending_hotels = [h for h in hotels if not h.get("Phone")]
    if not pending_hotels:
        print("All hotels already have phone numbers.")
        sys.exit(0)
        
    limit = min(args.limit, len(pending_hotels))
    print(f"Fetching phone numbers for {limit} hotels...")
    
    # Initialize undetected-chromedriver
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    
    driver = None
    try:
        driver = init_chrome_driver(options=options, headless=args.headless)
        
        fetched_count = 0
        for h in hotels:
            if fetched_count >= limit:
                break
                
            if not h.get("Phone"):
                name = h.get("Name", "")
                loc = h.get("Location", "")
                
                phone = scrape_google_phone(driver, name, loc)
                if phone:
                    h["Phone"] = phone
                    print(f"  └─ Success: Found phone '{phone}' for '{name}'")
                else:
                    h["Phone"] = "Not Found"
                    print(f"  └─ Failed: No phone number found for '{name}'")
                    
                # Incrementally save after each search to prevent data loss
                try:
                    with open(args.input, 'w', encoding='utf-8') as f:
                        json.dump(hotels, f, indent=4)
                    try:
                        os.chmod(args.input, 0o666)
                    except:
                        pass
                except Exception as save_err:
                    print(f"Warning: Failed to save progress to file: {save_err}")
                    
                fetched_count += 1
                # Sleep between searches to avoid Google block
                time.sleep(3)
                
    except Exception as driver_err:
        print(f"Driver initialization failed: {driver_err}")
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
                
    print("Finished fetching phone numbers!")

if __name__ == "__main__":
    main()
