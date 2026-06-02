"""
Cookie Export Helper
====================
Opens a visible browser window so you can log into Starlink manually.
After you log in, press Enter in the terminal to export cookies to cookies.json.

Usage:
    python export_cookies.py
    python scraper.py --cookies cookies.json
"""

from playwright.sync_api import sync_playwright
import json


def main():
    url = "https://starlink.com/account/signin"
    print("Opening browser. Log into your Starlink account, then press ENTER here to save cookies...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        input("Press ENTER after you are logged in...")

        # Export storage state (cookies + localStorage)
        storage = context.storage_state()
        with open("cookies.json", "w", encoding="utf-8") as f:
            json.dump(storage, f, indent=2)

        browser.close()

    print("Cookies saved to cookies.json")
    print("Now run: python scraper.py --cookies cookies.json")


if __name__ == "__main__":
    main()
