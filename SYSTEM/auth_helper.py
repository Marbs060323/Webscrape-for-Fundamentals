"""
Auth Helper for Starlink Scraper
================================
This script opens a visible Chromium browser so you can log into your
Starlink account manually. Once logged in, it exports the session storage
state to 'auth_state.json', which can be passed to scraper.py via --auth.

Usage:
    python auth_helper.py
"""

from playwright.sync_api import sync_playwright


def main():
    url = input("Enter Starlink login URL (default: https://starlink.com/account/signin): ").strip()
    if not url:
        url = "https://starlink.com/account/signin"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        input("Log in to your Starlink account in the browser window, then press ENTER here to save session...")

        context.storage_state(path="auth_state.json")
        browser.close()

    print("Session saved to auth_state.json")
    print("Run: python scraper.py --auth auth_state.json")


if __name__ == "__main__":
    main()
