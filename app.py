import streamlit as st
import os
import sys
import subprocess
import re
import io
import pandas as pd

# Set page config with high-quality theme settings
st.set_page_config(
    page_title="MakeMyTrip Scraper & Converter Suite",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply custom CSS for premium design aesthetics
st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1E3A8A;
            margin-bottom: 0.5rem;
        }
        .subheader {
            font-size: 1.1rem;
            color: #4B5563;
            margin-bottom: 2rem;
        }
        .stButton>button {
            background-color: #1E3A8A !important;
            color: white !important;
            border-radius: 6px !important;
            padding: 0.5rem 2rem !important;
            font-weight: 600 !important;
            border: none !important;
            transition: all 0.3s ease;
            width: 100%;
        }
        .stButton>button:hover {
            background-color: #3B82F6 !important;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }
        .card-container {
            background-color: #F3F4F6;
            padding: 1.5rem;
            border-radius: 8px;
            border-left: 5px solid #1E3A8A;
            margin-bottom: 1.5rem;
        }
        .metric-card {
            background-color: #EFF6FF;
            padding: 1rem;
            border-radius: 6px;
            border: 1px solid #BFDBFE;
            text-align: center;
        }
        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #1E3A8A;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #6B7280;
            text-transform: uppercase;
            font-weight: 600;
        }
    </style>
""", unsafe_allow_html=True)

# App Title
st.markdown("<div class='main-header'>🏨 MakeMyTrip Hotels Scraper Suite</div>", unsafe_allow_html=True)
st.markdown("<div class='subheader'>Scrape hotel details dynamically by location name and convert datasets to Excel.</div>", unsafe_allow_html=True)

# Sidebar Navigation
page = st.sidebar.radio(
    "Select a Tool",
    ["🏨 Hotel Listing Scraper", "📊 JSON to Excel Converter"]
)

# Common City Codes Mapping
CITIES_MAP = {
    "chennai": "CTMAA",
    "goa": "CTGOI",
    "mumbai": "CTBOM",
    "delhi": "CTDEL",
    "bangalore": "CTBLR",
    "bengaluru": "CTBLR",
    "hyderabad": "CTHYD",
    "kolkata": "CTCCU",
    "pune": "CTPNQ",
    "jaipur": "CTJAI",
    "kochi": "CTCOK",
    "ooty": "CTOOT",
    "agra": "CTAGR",
    "ahmedabad": "CTAMD",
    "amritsar": "CTATQ",
    "chandigarh": "CTIXC",
    "coimbatore": "CTCJB",
    "dehradun": "CTDED",
    "gurgaon": "CTGGN",
    "noida": "CTNOD",
    "guwahati": "CTGAU",
    "indore": "CTIDR",
    "jodhpur": "CTJDH",
    "lucknow": "CTLKO",
    "madurai": "CTIXM",
    "mangalore": "CTIXE",
    "mysore": "CTMYQ",
    "nagpur": "CTNAG",
    "patna": "CTPAT",
    "pondicherry": "CTPNY",
    "raipur": "CTRPR",
    "ranchi": "CTIXR",
    "shimla": "CTSLM",
    "surat": "CTSTV",
    "trichy": "CTTRZ",
    "trivandrum": "CTTRV",
    "udaipur": "CTUDR",
    "vadodara": "CTBDQ",
    "varanasi": "CTVNS",
    "vijayawada": "CTVGA",
    "vizag": "CTVTZ",
    "visakhapatnam": "CTVTZ"
}

# Ensure results folder exists
os.makedirs("results", exist_ok=True)

if page == "🏨 Hotel Listing Scraper":
    st.header("MakeMyTrip Hotel Listing Scraper")
    
    st.markdown(
        """
        <div class='card-container'>
            <strong>Instructions:</strong> Enter a location name (e.g. Chennai, Goa). The system will automatically build the search query and save incremental outputs inside the <code>results/</code> directory.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Inputs
    location = st.text_input("Enter Location Name (e.g., Chennai, Goa)", value="Goa")
    
    # Clean location name
    loc_clean = location.strip().lower()
    city_code = CITIES_MAP.get(loc_clean)
    if not city_code:
        # Fallback helper: CT + first 3 letters of location name in uppercase
        safe_prefix = re.sub(r'[^a-zA-Z]', '', loc_clean)[:3].upper()
        city_code = f"CT{safe_prefix}" if len(safe_prefix) >= 3 else "CTGOI"
        
    # Dynamically build URL
    constructed_url = f"https://www.makemytrip.com/hotels/hotel-listing/?checkin=07212026&checkout=07222026&city={city_code}&country=IN&locusId={city_code}&locusType=city&roomStayQualifier=2e0e&rsc=1e2e0e&searchText={location}"
    
    # Allow advanced users to review/editconstructed URL
    with st.expander("Advanced: Edit constructed URL & parameters"):
        url = st.text_area("Constructed MakeMyTrip URL", value=constructed_url, height=100)
    
    col1, col2 = st.columns(2)
    with col1:
        output_filename = f"{re.sub(r'[^a-zA-Z0-9_]', '', location.strip().lower())}_hotels.json"
        output_file = st.text_input("Output File Path", value=os.path.join("results", output_filename))
        scrolls = st.number_input("Scroll Iterations (Depth)", min_value=1, max_value=5000, value=6, step=1)
        
    with col2:
        headless = st.checkbox("Run Headless Browser (Invisible)", value=True, help="Uncheck this if you want to see the browser running or need to solve a CAPTCHA.")
        deep_scrape = st.checkbox("Deep Scrape (Scrape Address & Amenities)", value=False)
        
        deep_limit = 5
        if deep_scrape:
            deep_limit = st.number_input("Deep Scrape Limit", min_value=1, max_value=500, value=5)

    if st.button("🚀 Start Scraping"):
        if not location:
            st.error("Please enter a location name.")
        elif not output_file:
            st.error("Please specify a target JSON file path.")
        else:
            st.info("Scraping started. Initializing browser & parameters...")
            
            # Placeholders for metrics
            m_col1, m_col2, m_col3 = st.columns(3)
            with m_col1:
                scroll_metric = st.empty()
            with m_col2:
                hotels_metric = st.empty()
            with m_col3:
                saves_metric = st.empty()
                
            scroll_progress = st.progress(0.0)
            
            # Initialize metrics values
            scroll_metric.markdown(f"<div class='metric-card'><div class='metric-value'>0 / {scrolls}</div><div class='metric-label'>Scroll Progress</div></div>", unsafe_allow_html=True)
            hotels_metric.markdown("<div class='metric-card'><div class='metric-value'>0</div><div class='metric-label'>Hotels Found</div></div>", unsafe_allow_html=True)
            saves_metric.markdown("<div class='metric-card'><div class='metric-value'>0</div><div class='metric-label'>Saved to File</div></div>", unsafe_allow_html=True)
            
            # Build command list
            cmd = [
                sys.executable, "makemytrip_scraper.py",
                "--url", url,
                "--output", output_file,
                "--scrolls", str(scrolls)
            ]
            if headless:
                cmd.append("--headless")
            else:
                if sys.platform.startswith('linux'):
                    import shutil
                    if shutil.which("xvfb-run"):
                        cmd = ["xvfb-run", "--server-args=-screen 0 1024x768x24"] + cmd
            if deep_scrape:
                cmd.append("--deep")
                cmd.append("--deep-limit")
                cmd.append(str(deep_limit))
                
            # Log container
            log_header = st.subheader("Real-Time Execution Logs")
            log_box = st.empty()
            
            # Start subprocess
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                
                log_text = ""
                total_saved = 0
                total_hotels = 0
                
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    
                    log_text += line
                    # Limit log box text to prevent slowdown
                    log_box.code(log_text[-5000:])
                    
                    # Regex parsing for progress updates
                    # Scrolling page (3/6)...
                    scroll_match = re.search(r"Scrolling page \((\d+)/(\d+)\)", line)
                    if scroll_match:
                        curr = int(scroll_match.group(1))
                        tot = int(scroll_match.group(2))
                        pct = min(max(curr / tot, 0.0), 1.0)
                        scroll_progress.progress(pct)
                        scroll_metric.markdown(f"<div class='metric-card'><div class='metric-value'>{curr} / {tot}</div><div class='metric-label'>Scroll Progress</div></div>", unsafe_allow_html=True)
                        
                    # Parsed 10 new hotels (Total: 25) during scrolling...
                    hotels_match = re.search(r"Total:\s*(\d+)", line)
                    if hotels_match:
                        total_hotels = int(hotels_match.group(1))
                        hotels_metric.markdown(f"<div class='metric-card'><div class='metric-value'>{total_hotels}</div><div class='metric-label'>Hotels Found</div></div>", unsafe_allow_html=True)
                        
                    # Incremental save: 1 new hotel (...) saved to ...
                    save_match = re.search(r"Incremental save: (\d+) new hotel", line)
                    if save_match:
                        total_saved += int(save_match.group(1))
                        saves_metric.markdown(f"<div class='metric-card'><div class='metric-value'>{total_saved}</div><div class='metric-label'>Saved to File</div></div>", unsafe_allow_html=True)
                
                process.wait()
                
                if process.returncode == 0:
                    st.success(f"Scraping completed successfully! Output file: `{output_file}`")
                    
                    # Preview results
                    if os.path.exists(output_file):
                        try:
                            df = pd.read_json(output_file)
                            st.dataframe(df)
                        except Exception as parse_ex:
                            st.warning(f"Unable to show file preview: {parse_ex}")
                else:
                    st.error(f"Scraper process terminated with exit code {process.returncode}")
                    
            except Exception as e:
                st.error(f"Failed to start scraper subprocess: {e}")

elif page == "📊 JSON to Excel Converter":
    st.header("JSON to Excel Converter")
    
    st.markdown(
        """
        <div class='card-container'>
            <strong>Instructions:</strong> Convert your scraped JSON dataset into a clean, auto-formatted Microsoft Excel (.xlsx) file.
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Automatically scan results folder for JSON files
    json_files = []
    if os.path.exists("results"):
        json_files = [os.path.join("results", f) for f in os.listdir("results") if f.endswith(".json")]
        
    input_file = st.selectbox("Select JSON File", options=json_files if json_files else ["No JSON files found in results/"])
    custom_input = st.text_input("Or enter custom JSON File Path", value="" if json_files else "results/goa_hotels.json")
    
    target_input = custom_input if custom_input else input_file
    
    output_excel = st.text_input("Output Excel File Path (Optional)", value="")
    
    if st.button("📊 Convert File"):
        if not target_input or "No JSON files" in target_input:
            st.error("Please specify a valid input JSON file path.")
        elif not os.path.exists(target_input):
            st.error(f"Input file `{target_input}` does not exist!")
        else:
            if not output_excel:
                base_name, _ = os.path.splitext(target_input)
                output_excel = base_name + ".csv"
                
            with st.spinner("Converting..."):
                try:
                    # Import and execute converter function
                    from json_to_excel import convert_json_to_excel
                    
                    convert_json_to_excel(target_input, output_excel)
                    
                    st.success(f"Successfully converted! Excel file saved at: `{output_excel}`")
                    
                    # Offer download option
                    if os.path.exists(output_excel):
                        with open(output_excel, "rb") as f:
                            file_bytes = f.read()
                            st.download_button(
                                  label="📥 Download Excel File",
                                  data=file_bytes,
                                  file_name=os.path.basename(output_excel),
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                except Exception as ex:
                    st.error(f"An error occurred during conversion: {ex}")
