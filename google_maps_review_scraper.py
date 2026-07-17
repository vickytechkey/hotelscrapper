import time
import json
import argparse
import os
import re
import sys
from datetime import datetime
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
        options.add_argument("--window-size=1280,1024")
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

def clean_text(text):
    if not text:
        return ""
    return text.strip().replace("\n", " ")

def parse_reviewer_stats(reviewer_info_text):
    """
    Parses strings like "Local Guide · 56 reviews · 19 photos" or "3 reviews"
    to extract the number of reviews.
    """
    if not reviewer_info_text:
        return 0
    # Search for something like "56 reviews" or "56 review" or just "56" in a simple "56 reviews" string
    match = re.search(r'([\d,]+)\s*reviews?', reviewer_info_text, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    
    # Try looking for a single number if it's just e.g. "3 reviews"
    parts = [p.strip() for p in reviewer_info_text.split("·")]
    for part in parts:
        if "review" in part.lower():
            num_match = re.search(r'[\d,]+', part)
            if num_match:
                return int(num_match.group(0).replace(",", ""))
    return 0

def extract_aspect_rating(review_element, aspect_name):
    """
    Extracts ratings for specific aspects like 'Service', 'Rooms', 'Location'
    which might appear as 'Service: 5/5' or 'Service: 5' or 'Rooms: 4/5'
    """
    text = review_element.text
    pattern = rf'{aspect_name}\s*:\s*(\d)(?:/5)?'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}/5"
    return "N/A"

def extract_trip_and_travel_type(review_element):
    """
    Extracts trip type and travel type from tags like 'Trip type: Holiday · Couple' or 'Travel type: Solo'.
    """
    text = review_element.text
    trip_type = "N/A"
    travel_type = "N/A"
    
    trip_match = re.search(r'Trip\s+type\s*:\s*([^:\n]+)', text, re.IGNORECASE)
    if trip_match:
        val = trip_match.group(1).strip()
        parts = [p.strip() for p in re.split(r'[·|•,-]', val)]
        if len(parts) >= 2:
            trip_type = parts[0]
            travel_type = parts[1]
        elif len(parts) == 1:
            trip_type = parts[0]
            
    return trip_type, travel_type

def scrape_google_travel(driver, args):
    scraped_reviews = []
    try:
        print(f"Loading Google Travel URL: {args.url}")
        driver.get(args.url)
        time.sleep(10)
        
        # Bypass Cookie Consent if needed
        try:
            consent_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Accept all') or contains(., 'Agree') or contains(., 'Accept') or contains(., 'consent') or @aria-label='Accept all']")
            for btn in consent_buttons:
                if btn.is_displayed():
                    print(f"Clicking consent button: {btn.text}")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(5)
                    break
        except Exception as consent_err:
            pass
            
        # Click "All reviews" and select "Google" to focus only on Google reviews
        try:
            all_btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'All reviews')]")
            if all_btns:
                driver.execute_script("arguments[0].click();", all_btns[0])
                time.sleep(2)
                dropdown_items = driver.find_elements(By.XPATH, "//*[text()='Google']")
                for item in dropdown_items:
                    if item.tag_name == "span":
                        driver.execute_script("arguments[0].click();", item)
                        time.sleep(3)
                        break
        except Exception as e:
            print(f"Note: Error selecting Google reviews filter: {e}")

        # Smooth scrolling body to load reviews
        last_count = 0
        no_change_count = 0
        scroll_iteration = 0
        
        # Smooth scroll helper function
        def smooth_scroll(target_y):
            current_y = driver.execute_script("return window.pageYOffset;")
            step = 100
            if current_y < target_y:
                for y in range(int(current_y), int(target_y), step):
                    driver.execute_script(f"window.scrollTo(0, {y});")
                    time.sleep(0.05)
            driver.execute_script(f"window.scrollTo(0, {target_y});")

        while True:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            review_cards = soup.select("div.Svr5cf.bKhjM")
            current_count = len(review_cards)
            print(f"Loaded {current_count} Google Travel reviews (Target: {args.limit})...")
            
            if current_count >= args.limit or (current_count > 0 and current_count == last_count):
                no_change_count += 1
                if no_change_count >= 5:
                    print("No new reviews loaded. Stopping scroll.")
                    break
            else:
                no_change_count = 0
                
            last_count = current_count
            
            # Click any "Read more" buttons to expand review text
            try:
                read_more_buttons = driver.find_elements(By.XPATH, "//button[@aria-label='Read more' or contains(@class, 'iigpze') or contains(@class, 'ksBjEc')]")
                for btn in read_more_buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass
                
            scroll_iteration += 1
            h = driver.execute_script("return document.body.scrollHeight;")
            print(f"Scrolling page (Iteration {scroll_iteration}) to {h}...")
            smooth_scroll(h)
            time.sleep(3.5)

        # Extraction phase
        soup = BeautifulSoup(driver.page_source, "html.parser")
        review_cards = soup.select("div.Svr5cf.bKhjM")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for idx, card in enumerate(review_cards):
            if len(scraped_reviews) >= args.limit:
                break
                
            try:
                name_el = card.select_one("a.DHIhE") or card.select_one(".DHIhE")
                name = name_el.text.strip() if name_el else "N/A"
                
                date_el = card.select_one(".iUtr1")
                review_provided = date_el.text.strip() if date_el else "N/A"
                
                score_el = card.select_one(".GDWaad")
                star_rating = score_el.text.strip() if score_el else "N/A"
                if "/5" not in star_rating and star_rating != "N/A":
                    star_rating = f"{star_rating}/5"
                
                # Check for trip details
                trip_el = card.select_one(".ThUm5b")
                trip_text = trip_el.text.strip() if trip_el else "N/A"
                trip_type = "N/A"
                travel_type = "N/A"
                if trip_text != "N/A":
                    parts = [p.strip() for p in re.split(r'[·|•,❘❘-]', trip_text)]
                    if len(parts) >= 2:
                        trip_type = parts[0]
                        travel_type = parts[1]
                    elif len(parts) == 1:
                        trip_type = parts[0]
                
                text_el = card.select_one(".kVathc")
                review_text = text_el.text.strip() if text_el else ""
                # Clean up "Read more" or other texts if they exist in review text
                if review_text.endswith("Read more"):
                    review_text = review_text[:-9].strip()
                
                scraped_reviews.append({
                    "name_of_person": name,
                    "number_of_reviews": 0,
                    "todays_date": today_str,
                    "when_did_the_review_provided": review_provided,
                    "star_rating": star_rating,
                    "review_text": review_text,
                    "number_of_reviews_provided_earlier": 0,
                    "trip_type": trip_type,
                    "travel_type": travel_type,
                    "tags": trip_text,
                    "service": "N/A",
                    "rooms": "N/A",
                    "hotel_highlights": "N/A",
                    "hotel_name": args.hotel_name,
                    "location": args.location,
                    "pincode": args.pincode,
                    "address": args.address
                })
            except Exception as item_err:
                print(f"Error parsing review card index {idx}: {item_err}")
                
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(scraped_reviews, f, indent=4)
        print(f"Successfully scraped {len(scraped_reviews)} reviews and saved to {args.output}")

    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Google Maps / Travel Reviews Scraper")
    parser.add_argument("--url", type=str, required=True, help="Google Maps / Travel reviews URL")
    parser.add_argument("--hotel-name", type=str, required=True, help="Hotel name")
    parser.add_argument("--location", type=str, required=True, help="Hotel location")
    parser.add_argument("--pincode", type=str, required=True, help="Hotel pincode")
    parser.add_argument("--address", type=str, required=True, help="Hotel address")
    parser.add_argument("--output", type=str, required=True, help="Path to output JSON file")
    parser.add_argument("--limit", type=int, default=50, help="Target number of reviews to scrape")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print("Initializing Google Chrome Driver...")
    driver = init_chrome_driver(headless=args.headless)
    
    if "google.com/travel" in args.url or "google.co.in/travel" in args.url:
        scrape_google_travel(driver, args)
        return

    scraped_reviews = []
    
    try:
        print(f"Loading URL: {args.url}")
        driver.get(args.url)
        time.sleep(8)
        
        # Bypass Cookie Consent or general Google popups
        try:
            consent_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Accept all') or contains(., 'Agree') or contains(., 'Accept') or contains(., 'consent') or @aria-label='Accept all']")
            for btn in consent_buttons:
                if btn.is_displayed():
                    print(f"Clicking consent/bypass button: {btn.text or btn.get_attribute('aria-label')}")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(5)
                    break
        except Exception as consent_err:
            print(f"No consent button found or error clicking it: {consent_err}")
            
        # Check if the Reviews tab needs to be clicked (if we are not already on the reviews page)
        try:
            # We want to find the review trigger *inside* the place card of the active place.
            # Locate h1 (hotel name) first, then find the reviews button or rating close to it.
            print("Locating active place card via h1...")
            # We can use JS to click the correct trigger inside the place card.
            clicked = driver.execute_script("""
                let h1 = document.querySelector('h1');
                if (h1) {
                    let card = h1.closest('div[role="main"]') || h1.parentElement;
                    // Look for stars, review count, or "Reviews" tab button inside the card
                    let trigger = card.querySelector('div.F7nice, span[aria-label*="stars"], span[aria-label*="reviews"], button[aria-label*="Reviews"]');
                    if (trigger) {
                        trigger.click();
                        return true;
                    }
                }
                return false;
            """)
            if clicked:
                print("Clicked review trigger inside the active place card.")
                time.sleep(5)
            else:
                print("Could not find trigger inside active place card. Falling back to generic buttons...")
                reviews_buttons = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Reviews') or contains(., 'Reviews') or contains(., 'reviews')]")
                for btn in reviews_buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(5)
                        break
        except Exception as click_err:
            print(f"Note: Error finding or clicking reviews button: {click_err}")

        print("Locating scrollable reviews container...")
        scrollable_div = None
        
        # We find the scrollable container starting from a review card (since review cards only exist inside the reviews panel)
        try:
            scrollable_div = driver.execute_script("""
                let firstReview = document.querySelector('div.jftiEf, div[class*="jftiCc"], div[data-review-id]');
                if (firstReview) {
                    let parent = firstReview.parentElement;
                    while (parent) {
                        let style = window.getComputedStyle(parent);
                        if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && parent.scrollHeight > parent.clientHeight) {
                            return parent;
                        }
                        parent = parent.parentElement;
                    }
                }
                // Fallback to role="feed" if no reviews visible yet
                return document.querySelector('div[role="feed"]');
            """)
            if scrollable_div:
                print("Successfully located reviews scrollable container.")
        except Exception as js_err:
            print(f"JS scrollable container detection error: {js_err}")
                
        last_count = 0
        no_change_count = 0
        scroll_iteration = 0
        
        while len(scraped_reviews) < args.limit:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            review_cards = soup.select('div.jftiEf') or soup.select('div[class*="jftiCc"]') or soup.select('div[data-review-id]')
            current_count = len(review_cards)
            print(f"Loaded {current_count} review elements in DOM (Target: {args.limit})...")
            
            if current_count == 0:
                # Save screenshot to debug
                screenshot_path = os.path.join(os.path.dirname(args.output) or ".", "debug_screenshot.png")
                driver.save_screenshot(screenshot_path)
                print(f"Saved debug screenshot to {screenshot_path}")
                
            if current_count >= args.limit or (current_count > 0 and current_count == last_count):
                no_change_count += 1
                if no_change_count >= 5:
                    print("No new reviews loaded after multiple scrolls. Stopping scroll.")
                    break
            else:
                no_change_count = 0
                
            last_count = current_count
            
            try:
                more_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label*='See more'], button.w8nwZe")
                for btn in more_buttons:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass
                
            scroll_iteration += 1
            print(f"Scrolling review container (Iteration {scroll_iteration})...")
            if scrollable_div:
                driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", scrollable_div)
            else:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
            time.sleep(2.5)

        print("Extracting final review data details...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        review_cards = soup.select('div.jftiEf') or soup.select('div[class*="jftiCc"]') or soup.select('div[data-review-id]')
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for idx, card in enumerate(review_cards):
            if len(scraped_reviews) >= args.limit:
                break
                
            try:
                name_el = card.select_one('.d4r55') or card.select_one('[class*="d4r55"]') or card.select_one('.TSqpS')
                name = clean_text(name_el.text) if name_el else "N/A"
                
                reviewer_info_el = card.select_one('.Rfn1Y') or card.select_one('[class*="Rfn1Y"]') or card.select_one('.755wfc')
                info_text = reviewer_info_el.text if reviewer_info_el else ""
                reviews_count = parse_reviewer_stats(info_text)
                
                todays_date = today_str
                
                date_el = card.select_one('.rsqaWe') or card.select_one('[class*="rsqaWe"]') or card.select_one('.xPCZGe')
                review_provided = clean_text(date_el.text) if date_el else "N/A"
                
                star_el = card.select_one('span[aria-label*="star"]') or card.select_one('div[aria-label*="star"]')
                star_rating = "N/A"
                if star_el:
                    aria_lbl = star_el.get('aria-label', '')
                    match = re.search(r'(\d+)\s*stars?', aria_lbl, re.IGNORECASE)
                    if match:
                        star_rating = f"{match.group(1)}/5"
                    else:
                        match_single = re.search(r'(\d)', aria_lbl)
                        if match_single:
                            star_rating = f"{match_single.group(1)}/5"
                
                text_el = card.select_one('.wiI7pd') or card.select_one('[class*="wiI7pd"]') or card.select_one('.MyEned')
                review_text = clean_text(text_el.text) if text_el else ""
                
                trip_type, travel_type = extract_trip_and_travel_type(card)
                tags = "N/A"
                if trip_type != "N/A" and travel_type != "N/A":
                    tags = f"{trip_type} | {travel_type}"
                elif trip_type != "N/A":
                    tags = trip_type
                
                service_rating = extract_aspect_rating(card, "Service")
                rooms_rating = extract_aspect_rating(card, "Rooms")
                
                highlights = "N/A"
                highlights_el = card.select_one('.x3G5fe') or card.select_one('[class*="x3G5fe"]')
                if highlights_el:
                    highlights = clean_text(highlights_el.text)
                
                review_record = {
                    "name_of_person": name,
                    "number_of_reviews": reviews_count,
                    "todays_date": todays_date,
                    "when_did_the_review_provided": review_provided,
                    "star_rating": star_rating,
                    "review_text": review_text,
                    "number_of_reviews_provided_earlier": reviews_count,
                    "trip_type": trip_type,
                    "travel_type": travel_type,
                    "tags": tags,
                    "service": service_rating,
                    "rooms": rooms_rating,
                    "hotel_highlights": highlights,
                    "hotel_name": args.hotel_name,
                    "location": args.location,
                    "pincode": args.pincode,
                    "address": args.address
                }
                
                scraped_reviews.append(review_record)
                
            except Exception as item_err:
                print(f"Error parsing review card index {idx}: {item_err}")
                
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(scraped_reviews, f, indent=4)
        print(f"Successfully scraped {len(scraped_reviews)} reviews and saved to {args.output}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
