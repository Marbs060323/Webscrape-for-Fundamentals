import time
import os
from selenium import webdriver

# Firefox Imports
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.firefox import GeckoDriverManager

# Chrome Imports
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from webdriver_manager.chrome import ChromeDriverManager

# Edge Imports
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# UPDATED: Added browser_type="firefox" as the 4th argument
def fetch_raw_data(profile_path, dashboard_url, api_url, browser_type="firefox"):
    driver = None
    
    try:
        # --- 1. SETUP THE CHOSEN BROWSER ---
        if browser_type == "firefox":
            print("Initializing Firefox...")
            options = FirefoxOptions()
            # Only apply the profile if it exists on this machine
            if os.path.exists(profile_path):
                options.add_argument("-profile")
                options.add_argument(profile_path)
            driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)

        elif browser_type == "chrome":
            print("Initializing Chrome...")
            options = ChromeOptions()
            # Note: Chrome doesn't use the Firefox profile path
            driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)

        elif browser_type == "edge":
            print("Initializing Microsoft Edge...")
            options = EdgeOptions()
            driver = webdriver.Edge(service=EdgeService(EdgeChromiumDriverManager().install()), options=options)

        driver.set_script_timeout(60)

        # --- 2. EXECUTE THE SCRAPE ---
        print(f"Opening Dashboard: {dashboard_url}")
        driver.get(dashboard_url)
        
        # Wait for dashboard to load (Wait up to 20 seconds)
        # Teacher will need to log in manually if they don't have your profile
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Subscription')]"))
            )
        except:
            print("⚠️ Dashboard not detected. Waiting 10s for manual login or page render...")
            time.sleep(10)

        # Use JS to fetch data from inside the authenticated session
        js_fetch = f"""
            var callback = arguments[arguments.length - 1];
            fetch('{api_url}')
                .then(r => r.text())
                .then(data => callback(data))
                .catch(e => callback('ERROR: ' + e));
        """
        print("Executing Internal API Fetch...")
        raw_json = driver.execute_async_script(js_fetch)
        return raw_json

    except Exception as e:
        print(f"Engine Error: {e}")
        return None
        
    finally:
        if driver:
            print("Closing browser...")
            driver.quit()