import time
import json
import argparse
import os
import re
import sys
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def init_chrome_driver(headless=True):
    try:
        uc.Chrome.__del__ = lambda self: None
    except:
        pass
        
    def get_options():
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-extensions")
        return options
        
    try:
        driver = uc.Chrome(options=get_options(), headless=headless)
        return driver
    except Exception as e:
        err_msg = str(e)
        match = re.search(r"Current browser version is ([\d.]+)", err_msg)
        if match:
            version = match.group(1)
            major_version = int(version.split('.')[0])
            print(f"Detected Chrome version mismatch. Retrying with version_main={major_version}...")
            return uc.Chrome(options=get_options(), headless=headless, version_main=major_version)
        raise e

def clean_value(val):
    if not val or val == "N/A":
        return "N/A"
    # Remove specific Google Maps icon unicode characters
    val = re.sub(r'^[\s]+', '', val)
    # Remove other leading/trailing non-alphanumeric icons if any
    val = val.strip(' \n\t\r')
    return val

def clean_timing(val):
    val = clean_value(val)
    if not val or val == "N/A":
        return "N/A"
    # Remove clock/icon character
    val = re.sub(r'^[\s]+', '', val)
    # Remove "See more hours", "See weekly hours" and arrow characters
    val = val.replace("See more hours", "").replace("See weekly hours", "")
    val = re.sub(r'[]+', '', val)
    return val.strip()

def extract_pincode(address):
    if not address or address == "N/A":
        return "N/A"
    
    cleaned_addr = clean_value(address)
    # Indian Pincode: 6 digits, optionally separated by a space
    india_match = re.search(r'\b\d{3}\s?\d{3}\b', cleaned_addr)
    if india_match:
        return india_match.group(0).replace(" ", "")
        
    # Standard 5-digit zip code (US, etc.)
    us_match = re.search(r'\b\d{5}(?:-\d{4})?\b', cleaned_addr)
    if us_match:
        return us_match.group(0)
        
    # UK Postcode pattern
    uk_match = re.search(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', cleaned_addr, re.IGNORECASE)
    if uk_match:
        return uk_match.group(0).upper()
        
    return "N/A"

def save_data_to_file(data, output_file):
    if not data:
        return
    existing_data = []
    if os.path.exists(output_file):
        try:
            if '.json' in output_file:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            else:
                existing_data = pd.read_csv(output_file).to_dict(orient='records')
        except Exception:
            existing_data = []
            
    # Deduplicate by Name
    seen_names = {item["Name"].lower() for item in existing_data}
    new_items = []
    for item in data:
        if item["Name"].lower() not in seen_names:
            new_items.append(item)
            seen_names.add(item["Name"].lower())
            
    combined_data = existing_data + new_items
    if '.json' in output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, indent=4)
    else:
        df = pd.DataFrame(combined_data)
        df.to_csv(output_file, index=False)
        
    try:
        os.chmod(output_file, 0o666)
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser(description="Google Maps Search Scraper")
    parser.add_argument("--url", type=str, required=True, help="Google Maps search URL")
    parser.add_argument("--output", type=str, required=True, help="Path to output JSON/CSV file")
    parser.add_argument("--scrolls", type=int, default=5, help="Number of scroll iterations to load results")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()
    
    # Ensure results folder exists
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    print("Initializing Google Chrome Driver...")
    driver = init_chrome_driver(headless=args.headless)
    
    try:
        print(f"Loading search URL: {args.url}")
        driver.get(args.url)
        time.sleep(5)
        
        feed_selector = "div[role='feed']"
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, feed_selector))
            )
            feed = driver.find_element(By.CSS_SELECTOR, feed_selector)
        except Exception:
            print("Warning: Could not find results feed. Continuing without scroll...")
            feed = None
            
        if feed:
            last_height = driver.execute_script("return arguments[0].scrollHeight", feed)
            for i in range(args.scrolls):
                print(f"Scrolling page ({i+1}/{args.scrolls})...")
                driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", feed)
                time.sleep(2.5)
                
                new_height = driver.execute_script("return arguments[0].scrollHeight", feed)
                if new_height == last_height:
                    # Give it a second chance with extra wait to handle lazy-loading delays
                    time.sleep(2.0)
                    driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", feed)
                    new_height = driver.execute_script("return arguments[0].scrollHeight", feed)
                    if new_height == last_height:
                        print("Reached the end of the list (no height change detected).")
                        break
                last_height = new_height
                
        # Parse place links
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        place_links = []
        anchors = soup.select('a[href*="/maps/place/"]')
        for a in anchors:
            href = a.get('href', '')
            name = a.get('aria-label') or a.text.strip()
            if href and name and href not in [x['href'] for x in place_links]:
                place_links.append({'name': name, 'href': href})
                
        total_links = len(place_links)
        print(f"Total: {total_links} places found in list.")
        
        scraped_data = []
        for idx, item in enumerate(place_links):
            print(f"Scraping place ({idx+1}/{total_links}): {item['name']}")
            try:
                driver.get(item['href'])
                time.sleep(4.5) # Wait for page load
                
                detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Extract Name
                name_el = detail_soup.select_one('h1')
                name = name_el.text.strip() if name_el else item['name']
                
                # Extract Address
                address_el = (
                    detail_soup.select_one('button[data-item-id="address"]') or 
                    detail_soup.select_one('button[aria-label*="Address:"]') or
                    detail_soup.select_one('[aria-label^="Address:"]')
                )
                address = "N/A"
                if address_el:
                    address = address_el.text.strip()
                    if address.startswith("Address: "):
                        address = address[9:]
                address = clean_value(address)
                
                # Extract Pincode
                pincode = extract_pincode(address)
                
                # Extract Phone
                phone_el = (
                    detail_soup.select_one('button[data-item-id^="phone:tel:"]') or 
                    detail_soup.select_one('button[aria-label*="Phone:"]') or
                    detail_soup.select_one('[aria-label^="Phone:"]')
                )
                phone = "N/A"
                if phone_el:
                    phone = phone_el.text.strip()
                    if phone.startswith("Phone: "):
                        phone = phone[7:]
                phone = clean_value(phone)
                
                # Extract Business Timing / Hours
                hours_el = (
                    detail_soup.select_one('button[data-item-id="oh"]') or
                    detail_soup.select_one('div[data-item-id="oh"]') or
                    detail_soup.select_one('[aria-label*="Hours"]') or
                    detail_soup.select_one('[aria-label*="Open"]') or
                    detail_soup.select_one('[class*="t39uWc"]')
                )
                timing = "N/A"
                if hours_el:
                    timing = hours_el.text.strip()
                    if timing.startswith("Hours: "):
                        timing = timing[7:]
                    if not timing and hours_el.get('aria-label'):
                        timing = hours_el.get('aria-label').strip()
                timing = clean_timing(timing)
                
                # Extract Rating and Reviews
                rating = "N/A"
                reviews_count = "N/A"
                rating_container = detail_soup.select_one('div.F7nice') or detail_soup.select_one('[class*="F7nice"]')
                if rating_container:
                    rating_span = rating_container.select_one('span')
                    if rating_span:
                        rating = rating_span.text.strip()
                    # Check for reviews count (usually enclosed in parentheses)
                    for span in rating_container.find_all('span'):
                        txt = span.text.strip()
                        if '(' in txt and ')' in txt:
                            reviews_count = txt.replace('(', '').replace(')', '').strip()
                            break
                        # Also check if it contains digit or comma and is not the rating
                        elif txt and txt != rating and re.match(r'^[\d,]+$', txt):
                            reviews_count = txt.replace(',', '')
                            break
                            
                # Fallback for rating/reviews if not found
                if rating == "N/A":
                    star_el = detail_soup.select_one('span[aria-label*="stars"]')
                    if star_el:
                        label = star_el.get('aria-label', '')
                        match = re.search(r'(\d\.\d|\d)', label)
                        if match:
                            rating = match.group(1)
                            
                if reviews_count == "N/A":
                    reviews_el = detail_soup.select_one('[aria-label*="reviews"]') or detail_soup.select_one('[aria-label*="Reviews"]')
                    if reviews_el:
                        lbl = reviews_el.get('aria-label', '')
                        match = re.search(r'([\d,]+)\s*reviews', lbl, re.IGNORECASE)
                        if match:
                            reviews_count = match.group(1).replace(',', '')
                
                # Extract Location/Area from Address
                location = "N/A"
                if address != "N/A":
                    parts = [p.strip() for p in address.split(',')]
                    if len(parts) >= 3:
                        location = parts[-3]
                    elif len(parts) >= 2:
                        location = parts[-2]
                        
                ranking = idx + 1
                page_number = (idx // 10) + 1
                        
                place_record = {
                    "Name": name,
                    "Location": location,
                    "Address": address,
                    "Pincode": pincode,
                    "Phone": phone,
                    "Business Timing": timing,
                    "Rating": rating,
                    "Reviews": reviews_count,
                    "Ranking": ranking,
                    "PageNumber": page_number,
                    "Link": item['href']
                }
                
                scraped_data.append(place_record)
                
                # Incremental save to file
                save_data_to_file([place_record], args.output)
                print(f"Incremental save: 1 new hotel scraped and saved to {args.output}")
                
            except Exception as e:
                print(f"Error scraping details for {item['name']}: {e}")
                
        print(f"Scraping process complete. Output saved to {args.output}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
