import time
import json
import argparse
import os
import re
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

def save_data_to_file(hotels_data, output_file):
    if not hotels_data:
        return
    existing_data = []
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
        except Exception:
            existing_data = []
            
    # Combine and deduplicate by Name
    seen_names = {item["Name"].lower() for item in existing_data}
    new_items = []
    for item in hotels_data:
        if item["Name"].lower() not in seen_names:
            new_items.append(item)
            seen_names.add(item["Name"].lower())
            
    combined_data = existing_data + new_items
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=4)
    try:
        os.chmod(output_file, 0o666)
    except Exception:
        pass

def parse_zomato_cards(html, output_file, url_city=""):
    soup = BeautifulSoup(html, 'html.parser')
    
    # Select card anchors. Usually cards are links containing /info and have an h4 inside them.
    cards = soup.select('a[href*="/info"]')
    if not cards:
        # Fallback to general search for anchors
        cards = [a for a in soup.find_all('a') if a.find('h4')]

    hotels_data = []
    new_added = 0
    
    for card in cards:
        try:
            name_el = card.find('h4')
            if not name_el:
                continue
            name = name_el.text.strip()
            if not name:
                continue
            
            # Find rating: typically a div next to or near h4
            rating = "N/A"
            rating_el = card.select_one('h4 + div') or card.select_one('div[class*="rating"]') or card.select_one('div[class*="Rating"]')
            if rating_el:
                rating = rating_el.text.strip()
                if rating.endswith("star-fill"):
                    rating = rating[:-9].strip()
            else:
                # Look for a small div containing numbers like 4.1, 4.3, or "New"
                for div in card.find_all('div'):
                    text = div.text.strip()
                    if text.endswith("star-fill"):
                        text = text[:-9].strip()
                    if re.match(r'^\d\.\d$', text) or text == "New":
                        rating = text
                        break

            # Find Area and Location
            area = "N/A"
            location = url_city.capitalize() if url_city else "N/A"
            
            # Attempt 1: Target paragraph element in the structure
            target_p = card.select_one('div:last-child > div:first-child > p:first-child')
            p_text = target_p.text.strip() if target_p else ""
            
            if not p_text or ',' not in p_text:
                # Attempt 2: Search for any paragraph or div inside the card that contains a comma and matches location patterns
                for p in card.find_all(['p', 'div']):
                    txt = p.text.strip()
                    if ',' in txt and len(txt) < 100:
                        p_text = txt
                        break
            
            if p_text and ',' in p_text:
                parts = [part.strip() for part in p_text.split(',')]
                if len(parts) >= 2:
                    area = parts[0]
                    location = parts[1]
                elif len(parts) == 1:
                    area = parts[0]
            elif p_text:
                area = p_text

            hotel_item = {
                "Name": name,
                "Rating": rating,
                "Area": area,
                "Location": location,
                "Link": "https://www.zomato.com" + card.get('href') if card.get('href') and not card.get('href').startswith('http') else card.get('href', '')
            }
            
            hotels_data.append(hotel_item)
            new_added += 1
        except Exception as e:
            print(f"Error parsing card: {e}")
            
    if hotels_data:
        save_data_to_file(hotels_data, output_file)
        print(f"Incremental save: {len(hotels_data)} hotels saved to {output_file}.")
        
    return new_added

def init_chrome_driver(options, headless):
    try:
        uc.Chrome.__del__ = lambda self: None
    except:
        pass
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

def scrape_zomato(url, output_file, scrolls=20, headless=False):
    print(f"Starting Zomato Scraper: {url}")
    
    # Extract city from URL path if possible
    url_city = ""
    path_match = re.search(r'zomato\.com/([^/]+)', url)
    if path_match:
        url_city = path_match.group(1)

    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    
    driver = init_chrome_driver(options=options, headless=headless)
    
    try:
        driver.get(url)
        print("Page loaded. Waiting 10 seconds for initial elements...")
        time.sleep(10)
        
        scroll_pause_time = 3.0
        no_change_count = 0
        last_body_height = driver.execute_script("return document.body.scrollHeight;")
        
        for i in range(scrolls):
            print(f"Scrolling page ({i+1}/{scrolls})...")
            # Scroll down slowly in increments of 300 pixels
            last_height = driver.execute_script("return window.pageYOffset;")
            target_height = driver.execute_script("return document.body.scrollHeight;")
            while last_height < target_height:
                last_height += 300
                driver.execute_script(f"window.scrollTo(0, {last_height});")
                time.sleep(0.25)
                target_height = driver.execute_script("return document.body.scrollHeight;")
            time.sleep(scroll_pause_time)
            
            try:
                current_html = driver.page_source
                count = parse_zomato_cards(current_html, output_file, url_city=url_city)
                print(f"Parsed {count} hotel cards at scroll iteration {i+1}...")
            except Exception as inner_e:
                print(f"Warning during scroll parsing: {inner_e}")
            
            # Check if page body height has changed
            new_body_height = driver.execute_script("return document.body.scrollHeight;")
            if new_body_height == last_body_height:
                # Nudge up and down to trigger potential lazy loading
                driver.execute_script("window.scrollBy(0, -300);")
                time.sleep(1.0)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time)
                new_body_height = driver.execute_script("return document.body.scrollHeight;")
                
                if new_body_height == last_body_height:
                    no_change_count += 1
                    print(f"No height change detected (attempt {no_change_count}/3)...")
                    if no_change_count >= 3:
                        print("Reached the end of the page / bottom of listings.")
                        break
                else:
                    no_change_count = 0
            else:
                no_change_count = 0
            
            last_body_height = new_body_height
                
        # Final parsing pass
        final_html = driver.page_source
        print(f"Page title: {driver.title}")
        if "Access Denied" in driver.title or "Cloudflare" in driver.title or "security" in driver.title.lower():
            print("Warning: Access denied or Cloudflare block detected!")
        
        final_count = parse_zomato_cards(final_html, output_file, url_city=url_city)
        if final_count == 0:
            print(f"HTML Snippet (first 1000 chars): {final_html[:1000]}")
        print(f"Completed! Final card parse found {final_count} hotels.")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zomato Dine Out Scraper")
    parser.add_argument("--url", required=True, help="Zomato Dine Out URL to scrape")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--scrolls", type=int, default=20, help="Number of times to scroll down")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    args = parser.parse_args()
    
    scrape_zomato(args.url, args.output, args.scrolls, args.headless)
