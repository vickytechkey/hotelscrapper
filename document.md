# MakeMyTrip Hotel Listing Scraper Documentation

This standalone, high-performance web scraper is written in Python using **Selenium** and **BeautifulSoup**. It is designed to navigate MakeMyTrip, bypass Cloudflare and other anti-bot protection mechanisms using `undetected-chromedriver`, scroll dynamically to load lazy-loaded elements, and export structured hotel datasets.

---

## Features

- **Anti-Bot Bypass**: Uses `undetected-chromedriver` to prevent issues like `net::ERR_HTTP2_PROTOCOL_ERROR` and general bot blocks.
- **Dynamic Infinite Scroll**: Automatically simulates user scrolling to load dynamic listing pages.
- **Batch Page Tracking**: Groups hotels into pagination segments (`PageNumber` 1, 2, 3...) based on their position in the infinite scroll.
- **Deep Scrape (Optional)**: Automatically spins up new tabs to visit each hotel's unique detail URL to scrape additional information (e.g. detailed address, comprehensive amenities) without resetting listing page scroll state.
- **Flexible Formats**: Export datasets in either structured **JSON** format or **CSV** based on your choice of output file extension.

---

## Prerequisites

The project requires **Python 3.12+** and is set up with a virtual environment (`venv`).

### Installation

1. Install dependencies in your virtual environment:
   ```bash
   ./venv/bin/pip install -r requirements.txt
   ```
2. Verify that **Google Chrome** is installed on your local host (as `undetected-chromedriver` automatically links with your local Chrome installation).

---

## Command Line Usage

Run the scraper using the python binary in the virtual environment.

```bash
./venv/bin/python makemytrip_scraper.py [arguments]
```

### Supported Arguments

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `--url` | String | Goa hotel listing URL | The MakeMyTrip listing search URL to scrape. |
| `--output` | String | `makemytrip_hotels.json` | File name for exported data. Use `.json` or `.csv`. |
| `--deep` | Flag | Disabled | Enables tab-switching to scrape individual hotel detail pages. |
| `--deep-limit` | Integer | `5` | Maximum number of hotel detail pages to visit if `--deep` is active. |
| `--scrolls` | Integer | `6` | Number of times to scroll down to trigger lazy loading. |

---

## Output Fields

The generated output (`JSON` or `CSV`) contains the following schema:

```json
[
    {
        "Name": "Ginger Goa, Candolim",
        "Location": "Candolim",
        "Address": "Candolim | 8 minutes walk to Candolim Beach",
        "Rating": "4.2",
        "Reviews": "(3485 Ratings)",
        "Price": "₹ 3,899",
        "Stars": "Four Stars",
        "PageNumber": 1,
        "Link": "https://www.makemytrip.com/hotels/hotel-details?hotelId=..."
    }
]
```

- **Name**: The hotel name.
- **Location**: Parsed city/area region name.
- **Address**: Text representation of the location/distance summary from listings.
- **Rating**: User rating value (e.g., `4.2`).
- **Reviews**: Total number of reviews and ratings.
- **Price**: Estimated base price per night.
- **Stars**: Star rating classification parsed from listing icons.
- **PageNumber**: Evaluated result page number index.
- **Link**: Deep link back to the MakeMyTrip detail/booking page.
- **DetailedAddress** *(only with `--deep`)*: Precise street address parsed from detail page.
- **Amenities** *(only with `--deep`)*: List of facilities parsed from detail page.

---

## Excel Conversion Script

To convert your saved JSON data to formatted Microsoft Excel (`.xlsx`) spreadsheets, you can use the helper utility [json_to_excel.py](file:///home/vignesh/github/hotelscrapping/json_to_excel.py).

```bash
./venv/bin/python json_to_excel.py [arguments]
```

### Arguments
- `--input`: Path to the source JSON file (defaults to `makemytrip_hotels.json`).
- `--output`: Path to save the converted Excel file (defaults to same name as input, replaced with `.xlsx`).

### Example
```bash
./venv/bin/python json_to_excel.py --input makemytrip_hotels.json --output makemytrip_hotels.xlsx
```

---

## Troubleshooting

### Timeouts or Blank Output
If MakeMyTrip presents a captcha challenge that slows down execution, increase the initial sleep timer inside `makemytrip_scraper.py` or run Chrome in headed mode by changing options inside the script:
```python
# Change headless=True to headless=False inside makemytrip_scraper.py
headless=False
```
This launches a visible browser where you can view progress or manually solve any verification checks.
