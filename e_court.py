import argparse
import json
import os
import time
from datetime import date, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

ECOURTS_URL = "https://services.ecourts.gov.in/ecourtindia_v6/"
OUTPUT_DIR = "scraper_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def initialize_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_experimental_option("prefs", {
        "download.default_directory": os.path.join(os.getcwd(), OUTPUT_DIR),
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True
    })
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    driver.set_page_load_timeout(30)
    print("-> WebDriver initialized.")
    return driver

# CRITICAL FIX: Changed default values to a more stable option for initial selection
def select_court_details(driver, state_name="ANDHRA PRADESH", district_name="CHITTOOR", court_complex="TIRUPATI"):
    driver.get(f"{ECOURTS_URL}?p=cause_list/")

    try:
        time.sleep(2) 
        wait = WebDriverWait(driver, 15)
        
        # 1. Select State
        state_dropdown = wait.until(EC.visibility_of_element_located((By.ID, "state_code")))
        Select(state_dropdown).select_by_visible_text(state_name) 
        time.sleep(2)

        # 2. Select District
        district_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "district_code")))
        Select(district_dropdown).select_by_visible_text(district_name)
        time.sleep(2)
        
        # 3. Select Court Complex
        court_dropdown = wait.until(EC.element_to_be_clickable((By.ID, "court_complex_code")))
        Select(court_dropdown).select_by_visible_text(court_complex)
        time.sleep(1) 

        print("-> Court details selected successfully.")
        return True
    except Exception as e:
        print(f"ERROR: Could not select court details using visible text: {e}")
        return False

def check_case_listing(driver, search_type, case_input, listing_date):
    print(f"\n--- Checking Case Listing for {case_input} on {listing_date} ---")

    try:
        wait = WebDriverWait(driver, 15)
        
        cause_list_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Cause List by Court/Judge')]"))
        )
        cause_list_link.click()
        
        date_input = wait.until(EC.visibility_of_element_located((By.ID, 'from_date_cal')))

        js_date_set = f"arguments[0].value = '{listing_date}'"
        driver.execute_script(js_date_set, date_input)
        
        time.sleep(2) 

        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')

        if case_input in page_source:
            print(f"\n✅ Case {case_input} is listed on {listing_date}!")
            
            print("   - Serial Number: [Requires complex table parsing, assumed N/A for this console output]")
            print("   - Court Name: [Requires complex table parsing, assumed N/A for this console output]")
            
            print("\n   - Case PDF Download: NOT IMPLEMENTED (Requires specific link near the case number in the HTML table).")
            
            result = {
                "case_input": case_input,
                "date": listing_date,
                "is_listed": True,
                "details": "Details are visible on the cause list page.",
            }
            return result
        else:
            print(f"❌ Case {case_input} is NOT listed on {listing_date}.")
            return {"case_input": case_input, "date": listing_date, "is_listed": False}

    except Exception as e:
        print(f"An error occurred while checking the case listing: {e}")
        return {"case_input": case_input, "date": listing_date, "error": str(e)}


def download_cause_list(driver, listing_date):
    print(f"\n--- Downloading Entire Cause List for {listing_date} ---")

    try:
        driver.get(f"{ECOURTS_URL}?p=cause_list/")
        if not select_court_details(driver):
            return {"date": listing_date, "status": "Failed court selection (See console error above)"}

        wait = WebDriverWait(driver, 15)
        
        cause_list_link = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Cause List by Court/Judge')]"))
        )
        cause_list_link.click()
        
        date_input = wait.until(EC.visibility_of_element_located((By.ID, 'from_date_cal')))

        js_date_set = f"arguments[0].value = '{listing_date}'"
        driver.execute_script(js_date_set, date_input)
        
        time.sleep(2) 
        
        pdf_links = driver.find_elements(By.XPATH, "//a[contains(translate(text(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'PDF')] | //a[contains(@href, '.pdf')]")
        
        if pdf_links:
            pdf_link = pdf_links[0]
            print(f"   -> Attempting to click PDF link: {pdf_link.get_attribute('href')}")
            pdf_link.click()
            
            time.sleep(10) 
            
            downloaded_files = os.listdir(OUTPUT_DIR)
            print(f"   ✅ Download initiated. Check the '{OUTPUT_DIR}' folder.")
            return {"date": listing_date, "status": "Download Initiated", "output_dir": OUTPUT_DIR}
        else:
            print("   ❌ Could not find a general PDF download link on the page.")
            return {"date": listing_date, "status": "No PDF link found"}
        
    except Exception as e:
        print(f"An error occurred during cause list download: {e}")
        return {"date": listing_date, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(
        description="eCourts Scraper: Check case listing or download the daily cause list.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    case_group = parser.add_argument_group('Case Check (Requirements 1, 2, 3, 4)')
    case_group.add_argument(
        '--check-case', 
        nargs=3, 
        metavar=('<TYPE/CNR>', '<NUMBER>', '<YEAR>'),
        help='Check a specific case. Input: (Case Type/CNR) (Number) (Year). E.g., --check-case CNR N/A N/A or --check-case CA 123 2023'
    )
    case_group.add_argument(
        '--today', 
        action='store_true', 
        help='Check case listing for TODAY.'
    )
    case_group.add_argument(
        '--tomorrow', 
        action='store_true', 
        help='Check case listing for TOMORROW.'
    )
    
    parser.add_argument(
        '--causelist-today', 
        action='store_true', 
        help='Download the entire cause list for TODAY (Requirement 5).'
    )
    
    args = parser.parse_args()
    
    driver = initialize_driver()
    
    today_dt = date.today().strftime("%d-%m-%Y")
    tomorrow_dt = (date.today() + timedelta(days=1)).strftime("%d-%m-%Y")
    
    final_output = {}

    try:
        
        if args.check_case:
            if args.tomorrow:
                target_date = tomorrow_dt
            elif args.today or not (args.today or args.tomorrow):
                target_date = today_dt
            else:
                print("ERROR: Must specify --today or --tomorrow for case check.")
                return

            case_type, case_number, case_year = args.check_case
            case_input = f"{case_type}/{case_number}/{case_year}"
            
            if select_court_details(driver):
                result = check_case_listing(driver, case_type, case_input, target_date)
                final_output['case_check'] = result
                print(f"\n--- Console Output (Requirements 3) ---")
                print(json.dumps(result, indent=4))
                
                output_filename = os.path.join(OUTPUT_DIR, f"case_check_result_{target_date}.json")
                with open(output_filename, 'w') as f:
                    json.dump(result, f, indent=4)
                print(f"\n-> Results saved to {output_filename}")
            else:
                print("\nSCRIPT ABORTED: Court details selection failed. Check the detailed ERROR message above.")

        if args.causelist_today:
            result = download_cause_list(driver, today_dt) 
            final_output['causelist_download'] = result
            
            output_filename = os.path.join(OUTPUT_DIR, f"causelist_download_summary_{today_dt}.json")
            with open(output_filename, 'w') as f:
                json.dump(result, f, indent=4)
            print(f"\n-> Download summary saved to {output_filename}")


        if not (args.check_case or args.causelist_today):
            print("\nNo task specified. Use --check-case or --causelist-today.")


    finally:
        driver.quit()
        print("\n-> WebDriver closed. Script finished.")

if __name__ == "__main__":
    main()