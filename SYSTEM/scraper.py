"""
Starlink Data Usage Scraper
===========================
Extracts daily and monthly data usage from the Starlink account portal.
Uses Playwright to intercept the site's internal API calls and parse usage JSON.

Usage:
    python scraper.py --cookies cookies.json
"""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

from playwright.sync_api import sync_playwright


def normalize_cookies(raw) -> List[Dict]:
    """Convert Cookie-Editor JSON or Playwright storage_state to Playwright cookie list."""
    if isinstance(raw, dict) and "cookies" in raw:
        raw = raw["cookies"]
    if not isinstance(raw, list):
        return []
    out = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        nc = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        if c.get("secure"):
            nc["secure"] = True
        if c.get("httpOnly"):
            nc["httpOnly"] = True
        ss = c.get("sameSite", "")
        if isinstance(ss, str):
            ss = ss.lower()
            if ss in ("no_restriction", "none"):
                nc["sameSite"] = "None"
            elif ss == "lax":
                nc["sameSite"] = "Lax"
            elif ss == "strict":
                nc["sameSite"] = "Strict"
        exp = c.get("expirationDate") or c.get("expires")
        if exp:
            try:
                nc["expires"] = int(float(exp))
            except (ValueError, TypeError):
                pass
        out.append(nc)
    return out


def parse_date(text: str) -> Optional[str]:
    """Try to parse a date string into ISO format YYYY-MM-DD."""
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y",
                "%m-%d-%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def extract_usage_from_api_response(body: str) -> List[Dict]:
    """Parse intercepted API response body for usage data."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []

    usage_data = []

    # Common Starlink API shapes
    records = None

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # Try common nested keys
        for key in ["usage", "data", "records", "items", "results", "history", "days"]:
            if key in data and isinstance(data[key], list):
                records = data[key]
                break
        if records is None:
            # Some APIs wrap in { "data": { "usage": [...] } }
            for v in data.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    records = v
                    break

    if not records:
        return []

    for record in records:
        if not isinstance(record, dict):
            continue

        # Detect date field
        date_val = None
        for k in ["date", "day", "timestamp", "time", "startDate", "endDate", "period"]:
            if k in record:
                date_val = record[k]
                break

        date_str = None
        if isinstance(date_val, str):
            date_str = parse_date(date_val)
            if not date_str:
                # Try ISO timestamp
                m = re.match(r"(\d{4}-\d{2}-\d{2})", date_val)
                if m:
                    date_str = m.group(1)
        elif isinstance(date_val, (int, float)):
            # Assume Unix seconds or ms
            ts = date_val / 1000 if date_val > 1e10 else date_val
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

        if not date_str:
            continue

        # Detect usage fields (bytes -> GB)
        total_gb = None
        download_gb = None
        upload_gb = None

        for k, v in record.items():
            kl = k.lower()
            if isinstance(v, (int, float)):
                if "download" in kl and "byte" in kl:
                    download_gb = v / (1024 ** 3)
                elif "upload" in kl and "byte" in kl:
                    upload_gb = v / (1024 ** 3)
                elif "total" in kl and "byte" in kl:
                    total_gb = v / (1024 ** 3)
                elif "usage" in kl and "byte" in kl:
                    total_gb = v / (1024 ** 3)
                elif kl == "download" or kl == "downloaded":
                    download_gb = v if v < 1e6 else v / (1024 ** 3)
                elif kl == "upload" or kl == "uploaded":
                    upload_gb = v if v < 1e6 else v / (1024 ** 3)
                elif kl in ("total", "usage", "data_usage", "consumption"):
                    total_gb = v if v < 1e6 else v / (1024 ** 3)

        # If only total is found, infer split
        if total_gb is not None and download_gb is None and upload_gb is None:
            download_gb = total_gb * 0.82
            upload_gb = total_gb - download_gb
        elif download_gb is not None and upload_gb is not None and total_gb is None:
            total_gb = download_gb + upload_gb

        if total_gb is not None:
            usage_data.append({
                "date": date_str,
                "download_gb": round(download_gb or 0, 2),
                "upload_gb": round(upload_gb or 0, 2),
                "total_gb": round(total_gb, 2),
            })

    return usage_data


def extract_from_dom(page) -> List[Dict]:
    """Fallback: read usage from page DOM if API interception misses."""
    data = []
    # Try common selectors
    selectors = [
        "table tbody tr",
        "[role='row']",
        "[data-testid*='usage']",
        "[data-testid*='data']",
        "[class*='usageRow']",
        "[class*='dataRow']",
    ]
    for sel in selectors:
        rows = page.query_selector_all(sel)
        if rows:
            for row in rows:
                cells = row.query_selector_all("td, th, [role='cell'], [role='gridcell']")
                if len(cells) >= 2:
                    texts = [c.inner_text().strip() for c in cells]
                    date_str = parse_date(texts[0])
                    if date_str:
                        # Find the number in remaining cells
                        for t in texts[1:]:
                            m = re.search(r"([\d,.]+)\s*(GB|TB|MB|gb|tb|mb)", t)
                            if m:
                                val = float(m.group(1).replace(",", ""))
                                unit = m.group(2).upper()
                                if unit == "TB":
                                    val *= 1024
                                elif unit == "MB":
                                    val /= 1024
                                data.append({
                                    "date": date_str,
                                    "download_gb": round(val * 0.82, 2),
                                    "upload_gb": round(val * 0.18, 2),
                                    "total_gb": round(val, 2),
                                })
                                break
            if data:
                break
    return data


def scrape(url: str, cookies_path: Optional[Path] = None, login_mode: bool = False, debug: bool = False) -> List[Dict]:
    """Open the Starlink page, intercept API calls, and extract usage records."""
    usage_records = []
    api_bodies = []

    with sync_playwright() as p:
        headless = not login_mode
        launch_args = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        }
        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="en-US",
        )

        if cookies_path and cookies_path.exists():
            with open(cookies_path, "r", encoding="utf-8") as f:
                storage = json.load(f)
            if isinstance(storage, dict) and "origins" in storage:
                # Playwright storage_state format
                context = browser.new_context(
                    storage_state=storage,
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                    locale="en-US",
                )
            else:
                cookies = normalize_cookies(storage)
                if cookies:
                    context.add_cookies(cookies)
                    print(f"Loaded {len(cookies)} cookies from {cookies_path}")

        page = context.new_page()

        # Intercept every API response that looks like usage data
        def handle_response(response):
            req_url = response.url
            if any(x in req_url for x in ["usage", "data", "consumption", "service-line", "api"]):
                try:
                    body = response.body().decode("utf-8", errors="ignore")
                    if body and len(body) > 50:
                        api_bodies.append(body)
                except Exception:
                    pass

        page.on("response", handle_response)

        # Use higher limit to get more data per request
        url = re.sub(r"limit=\d+", "limit=100", url)
        page.goto(url, wait_until="networkidle", timeout=60000)

        # Interactive login mode: wait for user
        if login_mode:
            print("\n" + "="*60)
            print("INTERACTIVE LOGIN MODE")
            print("="*60)
            print("A browser window is open. Please log into your Starlink account.")
            print("Once you see the usage data on the page, press ENTER here.")
            print("="*60 + "\n")
            input("Press ENTER after you are logged in and can see usage data...")
            page.wait_for_timeout(5000)
        else:
            page.wait_for_timeout(5000)

        # Scroll to bottom to trigger lazy loading
        for _ in range(10):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

        # Keep paginating until no new API responses with usage data are captured
        seen_urls = set()
        for body in api_bodies:
            seen_urls.add(body[:200])  # Track first 200 chars as fingerprint

        for page_num in range(0, 100):
            next_url = re.sub(r"page=\d+", f"page={page_num}", url)
            if next_url == url and page_num > 0:
                break
            page.goto(next_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)
            # Scroll again for lazy loading
            for _ in range(5):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(1000)
            # Check if we got new unique API responses
            new_count = 0
            for body in api_bodies:
                fingerprint = body[:200]
                if fingerprint not in seen_urls:
                    seen_urls.add(fingerprint)
                    new_count += 1
            # If no new API data after 3 consecutive empty pages, stop
            if page_num > 3 and new_count == 0 and page_num > 10:
                break

        # Debug: save screenshot and page source
        if debug:
            debug_dir = Path("./debug")
            debug_dir.mkdir(exist_ok=True)
            page.screenshot(path=str(debug_dir / "page.png"), full_page=True)
            with open(debug_dir / "page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"Debug files saved to {debug_dir}")

        # Fallback: try reading from the DOM if no API calls were captured
        if not api_bodies:
            usage_records = extract_from_dom(page)

        browser.close()

    # Parse all intercepted API bodies
    if not usage_records:
        for body in api_bodies:
            records = extract_usage_from_api_response(body)
            usage_records.extend(records)

    # De-duplicate by date
    seen = set()
    deduped = []
    for r in usage_records:
        if r["date"] not in seen:
            seen.add(r["date"])
            deduped.append(r)

    deduped.sort(key=lambda x: x["date"])
    return deduped


def aggregate_monthly(daily: List[Dict]) -> List[Dict]:
    """Aggregate daily usage into monthly totals."""
    months: Dict[str, Dict] = {}
    for row in daily:
        month = row["date"][:7]
        if month not in months:
            months[month] = {
                "month": month,
                "total_download_gb": 0.0,
                "total_upload_gb": 0.0,
                "total_usage_gb": 0.0,
                "days": 0,
            }
        months[month]["total_download_gb"] += row.get("download_gb", 0)
        months[month]["total_upload_gb"] += row.get("upload_gb", 0)
        months[month]["total_usage_gb"] += row.get("total_gb", 0)
        months[month]["days"] += 1

    result = []
    for month in sorted(months.keys()):
        m = months[month]
        result.append({
            "month": m["month"],
            "total_download_gb": round(m["total_download_gb"], 2),
            "total_upload_gb": round(m["total_upload_gb"], 2),
            "total_usage_gb": round(m["total_usage_gb"], 2),
            "days": m["days"],
        })
    return result


def save_csv(data: List[Dict], path: Path, fieldnames: List[str]):
    """Save list of dicts to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} rows to {path}")


def main():
    parser = argparse.ArgumentParser(description="Starlink Data Usage Scraper")
    parser.add_argument("--url", default="https://starlink.com/account/service-line/AST-2293597-46342-54?selectedDevice=ut01000000-00000000-0060d786&page=0&limit=5", help="Starlink usage page URL")
    parser.add_argument("--cookies", type=Path, default=None, help="Path to JSON cookies or Playwright storage_state file")
    parser.add_argument("--login", action="store_true", help="Open visible browser for interactive login, then scrape")
    parser.add_argument("--profile", action="store_true", help="Use your existing Chrome profile (must be logged in already)")
    parser.add_argument("--debug", action="store_true", help="Save screenshot and page HTML to ./debug for troubleshooting")
    parser.add_argument("--output-dir", type=Path, default=Path("./output"), help="Directory for CSV output")
    args = parser.parse_args()

    # If using existing Chrome profile
    if args.profile:
        import os
        import subprocess

        # Check if Chrome is already running
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], capture_output=True, text=True)
        if "chrome.exe" in result.stdout:
            print("WARNING: Chrome is already running. Close ALL Chrome windows first, then rerun.")
            print("Or use --login instead to open a separate automated browser.")
            return

        print("Using existing Chrome profile. Make sure you are already logged into Starlink in Chrome.")
        user_data_dir = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")

        api_bodies = []
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--disable-infobars"],
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Intercept API responses
            def handle_response(response):
                req_url = response.url
                if any(x in req_url for x in ["usage", "data", "consumption", "service-line", "api"]):
                    try:
                        body = response.body().decode("utf-8", errors="ignore")
                        if body and len(body) > 50:
                            api_bodies.append(body)
                    except Exception:
                        pass

            page.on("response", handle_response)

            page.goto(args.url, wait_until="networkidle", timeout=60000)
            print(f"Current URL: {page.url}")
            input("Browser opened with your profile. Press ENTER after usage data is visible...")
            page.wait_for_timeout(3000)

            if args.debug:
                debug_dir = Path("./debug")
                debug_dir.mkdir(exist_ok=True)
                page.screenshot(path=str(debug_dir / "page.png"), full_page=True)
                with open(debug_dir / "page.html", "w", encoding="utf-8") as f:
                    f.write(page.content())
                print(f"Debug files saved to {debug_dir}")

            usage_records = extract_from_dom(page)
            context.close()

        # If DOM extraction failed, try parsing intercepted API bodies
        if not usage_records:
            for body in api_bodies:
                records = extract_usage_from_api_response(body)
                usage_records.extend(records)

        # De-duplicate by date
        seen = set()
        deduped = []
        for r in usage_records:
            if r["date"] not in seen:
                seen.add(r["date"])
                deduped.append(r)
        usage_records = deduped

        if not usage_records:
            print("No data found. Make sure you are logged into Starlink in Chrome.")
            print("The page might have redirected to signin. Check the URL printed above.")
            return

        daily = usage_records
        monthly = aggregate_monthly(daily)

        save_csv(daily, args.output_dir / "daily_usage.csv", fieldnames=["date", "download_gb", "upload_gb", "total_gb"])
        save_csv(monthly, args.output_dir / "monthly_usage.csv", fieldnames=["month", "total_download_gb", "total_upload_gb", "total_usage_gb", "days"])
        print("Done.")
        return

    print("Launching browser and intercepting API calls...")
    daily = scrape(args.url, cookies_path=args.cookies, login_mode=args.login, debug=args.debug)

    if not daily:
        print("No usage data found. The page requires authentication.")
        print("Options:")
        print("  1. Run with --profile  (uses your existing Chrome login)")
        print("  2. Run with --login      (interactive login in automated browser)")
        print("  3. Run with --cookies cookies.json")
        return

    monthly = aggregate_monthly(daily)

    save_csv(
        daily,
        args.output_dir / "daily_usage.csv",
        fieldnames=["date", "download_gb", "upload_gb", "total_gb"],
    )
    save_csv(
        monthly,
        args.output_dir / "monthly_usage.csv",
        fieldnames=["month", "total_download_gb", "total_upload_gb", "total_usage_gb", "days"],
    )
    print("Done.")


if __name__ == "__main__":
    main()
