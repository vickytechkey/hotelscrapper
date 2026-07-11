import time
import json
import argparse
import os
import pandas as pd
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def scrape_hotel_detail(driver, detail_url):
    """Visits the hotel detail page and extracts deep information."""
    print(f"    -> Visiting detail page: {detail_url}")
    try:
        original_handle = driver.current_window_handle
        driver.execute_script("window.open('');")
        time.sleep(1.5)
        
        if len(driver.window_handles) > 1:
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(detail_url)
            time.sleep(3) # Wait for page load
            
            detail_html = driver.page_source
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            
            # Get detailed address
            addr_el = detail_soup.select_one('.address') or detail_soup.select_one('[class*="address"]') or detail_soup.select_one('.pc__location')
            detailed_address = addr_el.text.strip() if addr_el else None
            
            # Get amenities
            amenities_list = []
            amenity_elements = detail_soup.select('.ySdfs') or detail_soup.select('[class*="amenity"]') or detail_soup.select('.aeL1t')
            for ae in amenity_elements:
                txt = ae.text.strip()
                if txt and txt not in amenities_list:
                    amenities_list.append(txt)
            amenities = ", ".join(amenities_list) if amenities_list else None

            # Close the tab and switch back to list page tab
            driver.close()
            driver.switch_to.window(original_handle)
            return {"DetailedAddress": detailed_address, "Amenities": amenities}
        else:
            print("    -> Failed to open new tab/window (popup blocker active?). Skipping deep scrape.")
            return {}
    except Exception as e:
        print(f"    -> Error visiting detail page: {e}")
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(original_handle)
        except:
            pass
        return {}

def save_data_to_file(hotels_data, output_file):
    if not hotels_data:
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
            
    combined_data = existing_data + hotels_data
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

def parse_hotels_from_html(html, existing_names, hotels_data, output_file, driver=None, deep_scrape=False, deep_limit=0, deep_scraped_count=None):
    soup = BeautifulSoup(html, 'html.parser')
    cards = soup.select('.hotelTileDt') or soup.select('.listingRowOuter') or soup.select('.listingRow')
    if not cards:
        cards = soup.select('.hotelCard') or soup.select('[class*="hotelCard"]')
    
    if deep_scraped_count is None:
        deep_scraped_count = [0]
        
    new_added = 0
    for idx, card in enumerate(cards):
        try:
            name_el = card.select_one('span.wordBreak') or card.select_one('p.font20') or card.select_one('[id*="detpg_hotel_name"]')
            if not name_el:
                continue
            name = name_el.text.strip()
            if not name or len(name) < 2:
                continue
            
            if name in existing_names:
                continue
                
            link_el = card.select_one('a')
            link = link_el.get('href') if link_el else ""
            if link and not link.startswith('http'):
                if link.startswith('//'):
                    link = "https:" + link
                else:
                    link = "https://www.makemytrip.com" + link

            address_el = card.select_one('.addrContainer') or card.select_one('.pc__locationPerNew') or card.select_one('[class*="address"]')
            address = address_el.text.strip() if address_el else "N/A"

            rating_el = card.select_one('.rating') or card.select_one('[id*="detpg_user_rating"]') or card.select_one('[class*="rating"]')
            rating = rating_el.text.strip() if rating_el else "N/A"

            reviews_el = card.select_one('p.font14.darkGreyText') or card.select_one('[class*="ratingCount"]')
            reviews_count = reviews_el.text.strip() if reviews_el else "N/A"

            price_el = card.select_one('p.priceText') or card.select_one('[class*="price"]') or card.select_one('[class*="actualPrice"]')
            price = price_el.text.strip() if price_el else "N/A"

            stars = "N/A"
            stars_el = card.select_one('.rating_fill')
            if stars_el:
                classes = stars_el.get('class', [])
                for cls in classes:
                    if 'rating' in cls and cls != 'rating_fill':
                        stars = cls.replace('rating', '') + ' Stars'

            page_number = (len(existing_names) // 10) + 1

            hotel_item = {
                "Name": name,
                "Location": address.split('|')[0].strip() if '|' in address else address,
                "Address": address,
                "Rating": rating,
                "Reviews": reviews_count,
                "Price": price,
                "Stars": stars,
                "PageNumber": page_number,
                "Link": link
            }

            if deep_scrape and link and driver and deep_scraped_count[0] < deep_limit:
                details = scrape_hotel_detail(driver, link)
                if details.get("DetailedAddress"):
                    hotel_item["DetailedAddress"] = details["DetailedAddress"]
                if details.get("Amenities"):
                    hotel_item["Amenities"] = details["Amenities"]
                deep_scraped_count[0] += 1

            hotels_data.append(hotel_item)
            existing_names.add(name)
            new_added += 1

            # Save and clear memory immediately for each single hotel (for each scrap memory)
            save_data_to_file(hotels_data, output_file)
            print(f"Incremental save: 1 new hotel ({name}) saved to {output_file}. Clearing memory...")
            hotels_data.clear()

        except Exception as parse_err:
            pass
            
    if len(hotels_data) > 0:
        save_data_to_file(hotels_data, output_file)
        hotels_data.clear()
    return new_added

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

def scrape_makemytrip(url, output_file, deep_scrape=False, deep_limit=10, scrolls=6, headless=False):
    temp_file = output_file + ".tmp"
    print(f"Starting undetected-chromedriver to scrape: {url} (headless={headless})")
    
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2
    })
    driver = init_chrome_driver(options=options, headless=headless)
    hotels_data = []
    existing_names = set()
    deep_scraped_count = [0]
    
    try:
        driver.get(url)
        print("Page loaded. Waiting 10 seconds for initial elements...")
        time.sleep(10)
        
        # Verify page content to prevent scrolling on error page
        try:
            if "ERR_HTTP2_PROTOCOL_ERROR" in driver.page_source:
                print("Error: Chrome failed to load the page (ERR_HTTP2_PROTOCOL_ERROR).")
                print("This is common in headless mode. Try running in headful (default) mode.")
                return
        except:
            pass
        
        scroll_pause_time = 3.0
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        # Scroll loop to load multiple pages
        try:
            no_change_count = 0
            for i in range(scrolls):
                print(f"Scrolling page ({i+1}/{scrolls})...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(scroll_pause_time)
                
                # Periodically parse the current page to avoid data loss if tab crashes
                try:
                    current_html = driver.page_source
                    new_count = parse_hotels_from_html(current_html, existing_names, hotels_data, temp_file, deep_scraped_count=deep_scraped_count)
                    if new_count > 0:
                        print(f"Parsed {new_count} new hotels (Total: {len(existing_names)}) during scrolling...")
                except Exception as inner_e:
                    print(f"Warning: Failed to parse intermediate page source (could mean page crashed or loading): {inner_e}")
                
                # Prune older DOM elements to prevent memory leaks and tab crashes
                try:
                    prune_js = """
                    var cards = document.querySelectorAll('.hotelTileDt, .listingRowOuter, .listingRow, .hotelCard, [class*="hotelCard"]');
                    if (cards.length > 25) {
                        for (var i = 0; i < cards.length - 25; i++) {
                            if (cards[i].innerHTML !== "") {
                                var height = cards[i].offsetHeight;
                                if (height > 0) {
                                    cards[i].style.height = height + 'px';
                                }
                                cards[i].innerHTML = "";
                            }
                        }
                    }
                    """
                    driver.execute_script(prune_js)
                except Exception as prune_e:
                    print(f"Warning: Failed to prune DOM: {prune_e}")
                
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    # Try nudging up and down to trigger lazy loading
                    driver.execute_script("window.scrollBy(0, -300);")
                    time.sleep(1.0)
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(scroll_pause_time)
                    new_height = driver.execute_script("return document.body.scrollHeight")
                    
                    if new_height == last_height:
                        no_change_count += 1
                        print(f"No height change detected (attempt {no_change_count}/3)...")
                        if no_change_count >= 3:
                            print("Reached the end of the page / bottom of listings.")
                            break
                    else:
                        no_change_count = 0
                else:
                    no_change_count = 0
                
                last_height = new_height
        except KeyboardInterrupt:
            print("\n[Interrupt] Scrolling stopped by user. Parsing and saving currently loaded hotels...")
        except Exception as scroll_e:
            print(f"\n[Warning] Scrolling interrupted: {scroll_e}. Proceeding to save already parsed hotels.")
 
        print("Finished scrolling. Parsing any remaining/unparsed HTML content...")
        try:
            html = driver.page_source
            parse_hotels_from_html(html, existing_names, hotels_data, temp_file, driver, deep_scrape, deep_limit, deep_scraped_count=deep_scraped_count)
        except Exception as final_parse_err:
            print(f"Warning during final parse: {final_parse_err}. Handled safely using previously saved data.")

        if os.path.exists(temp_file):
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(temp_file, output_file)
                try:
                    os.chmod(output_file, 0o666)
                except Exception:
                    pass
                print(f"Successfully scraped {len(existing_names)} hotels and saved to {output_file}!")
            except Exception as rename_err:
                print(f"Error finalizing output file: {rename_err}")
        else:
            print("No hotel data could be parsed.")

    except Exception as e:
        print(f"Error during execution: {e}")
        if os.path.exists(temp_file):
            try:
                if os.path.exists(output_file):
                    os.remove(output_file)
                os.rename(temp_file, output_file)
                try:
                    os.chmod(output_file, 0o666)
                except Exception:
                    pass
                print(f"Recovered intermediate backup data and saved to {output_file}")
            except Exception as recover_err:
                print(f"Failed to recover backup temp file: {recover_err}")
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MakeMyTrip Hotel Listing Scraper")
    parser.add_argument(
        "--url", 
        type=str, 
        default="https://www.makemytrip.com/hotels/hotel-listing/?checkin=07212026&checkout=07222026&city=CTGOI&country=IN&locusId=CTGOI&locusType=city&roomStayQualifier=2e0e&rsc=1e2e0e&searchText=Goa",
        help="MakeMyTrip hotel listing URL to scrape"
    )
    parser.add_argument(
        "--output", 
        type=str, 
        default="makemytrip_hotels.json",
        help="Output filename (ends in .json or .csv)"
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Visit each hotel detail page for extra info"
    )
    parser.add_argument(
        "--deep-limit",
        type=int,
        default=5,
        help="Max number of hotel detail pages to scrape if deep option is enabled"
    )
    parser.add_argument(
        "--scrolls",
        type=int,
        default=1000,
        help="Number of scroll iterations to load multiple pages of listings (default 1000 to scroll to the end)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run scraper in headless mode"
    )
    args = parser.parse_args()
    scrape_makemytrip(args.url, args.output, args.deep, args.deep_limit, args.scrolls, headless=args.headless)
