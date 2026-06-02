"""
Starlink Web Scraper App
========================
Run: python app.py
Open: http://localhost:5000

Click "Scrape Starlink Data" → browser opens → log in → data auto-extracts.
"""

import csv
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import List, Dict, Optional

from flask import Flask, jsonify, render_template_string, request
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Global state for the active scraping session
scraping_state = {
    "status": "idle",  # idle | waiting_login | extracting | done | error
    "message": "",
    "browser_open": False,
    "daily": [],
    "monthly": [],
}

STARLINK_URL = "https://starlink.com/account/service-line/AST-2293597-46342-54?selectedDevice=ut01000000-00000000-0060d786&page=0&limit=5"
OUTPUT_DIR = Path("./output")


def load_csv(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def parse_date(text: str) -> Optional[str]:
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
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []

    usage_data = []
    records = None

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        for key in ["usage", "data", "records", "items", "results", "history", "days"]:
            if key in data and isinstance(data[key], list):
                records = data[key]
                break
        if records is None:
            for v in data.values():
                if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                    records = v
                    break

    if not records:
        return []

    for record in records:
        if not isinstance(record, dict):
            continue

        date_val = None
        for k in ["date", "day", "timestamp", "time", "startDate", "endDate", "period"]:
            if k in record:
                date_val = record[k]
                break

        date_str = None
        if isinstance(date_val, str):
            date_str = parse_date(date_val)
            if not date_str:
                m = re.match(r"(\d{4}-\d{2}-\d{2})", date_val)
                if m:
                    date_str = m.group(1)
        elif isinstance(date_val, (int, float)):
            ts = date_val / 1000 if date_val > 1e10 else date_val
            date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

        if not date_str:
            continue

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
                elif kl in ("download", "downloaded"):
                    download_gb = v if v < 1e6 else v / (1024 ** 3)
                elif kl in ("upload", "uploaded"):
                    upload_gb = v if v < 1e6 else v / (1024 ** 3)
                elif kl in ("total", "usage", "data_usage", "consumption"):
                    total_gb = v if v < 1e6 else v / (1024 ** 3)

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
    data = []
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


def aggregate_monthly(daily: List[Dict]) -> List[Dict]:
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
        months[month]["total_download_gb"] += float(row.get("download_gb", 0))
        months[month]["total_upload_gb"] += float(row.get("upload_gb", 0))
        months[month]["total_usage_gb"] += float(row.get("total_gb", 0))
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


def run_scraper_task():
    """Background thread: open browser, wait for login, extract data."""
    global scraping_state

    scraping_state["status"] = "waiting_login"
    scraping_state["message"] = "Browser opened. Please log into Starlink. Data will auto-extract when ready..."
    scraping_state["browser_open"] = True

    usage_records = []
    api_bodies = []
    browser = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                locale="en-US",
            )
            page = context.new_page()

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
            url = re.sub(r"limit=\d+", "limit=100", STARLINK_URL)
            page.goto(url, wait_until="networkidle", timeout=60000)

            # Auto-detect: wait up to 5 minutes for login + data load
            max_wait = 300  # seconds
            poll_interval = 3
            elapsed = 0
            found_data = False

            while elapsed < max_wait:
                current_url = page.url
                # Check if we're on a usage page (not signin)
                if "signin" in current_url or "login" in current_url:
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    scraping_state["message"] = f"Waiting for login... ({elapsed}s elapsed)"
                    continue

                # Scroll to bottom to trigger lazy loading
                for _ in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1)

                # Try extracting from DOM
                dom_data = extract_from_dom(page)
                if dom_data:
                    usage_records = dom_data
                    found_data = True
                    break

                # Try parsing any intercepted API bodies
                if api_bodies:
                    for body in api_bodies[:]:
                        records = extract_usage_from_api_response(body)
                        if records:
                            usage_records.extend(records)
                    if usage_records:
                        found_data = True
                        break
                    api_bodies.clear()  # Clear so we don't re-parse same bodies

                time.sleep(poll_interval)
                elapsed += poll_interval
                scraping_state["message"] = f"Looking for usage data on page... ({elapsed}s elapsed)"

            # If found data, keep paginating for more historical data
            if found_data:
                scraping_state["message"] = "Found data. Fetching more historical pages..."
                seen_urls = set()
                for body in api_bodies:
                    seen_urls.add(body[:200])

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
                    if page_num > 3 and new_count == 0 and page_num > 10:
                        break

            if not found_data:
                # One final attempt from DOM
                usage_records = extract_from_dom(page)

            browser.close()
            browser = None

    except Exception as e:
        scraping_state["status"] = "error"
        scraping_state["message"] = f"Error: {str(e)}"
        if browser:
            browser.close()
        return

    # De-duplicate
    seen = set()
    deduped = []
    for r in usage_records:
        if r["date"] not in seen:
            seen.add(r["date"])
            deduped.append(r)
    deduped.sort(key=lambda x: x["date"])

    if not deduped:
        scraping_state["status"] = "error"
        scraping_state["message"] = "No usage data found. Make sure you logged in successfully."
        return

    # Save
    monthly = aggregate_monthly(deduped)
    save_csv(deduped, OUTPUT_DIR / "daily_usage.csv", ["date", "download_gb", "upload_gb", "total_gb"])
    save_csv(monthly, OUTPUT_DIR / "monthly_usage.csv", ["month", "total_download_gb", "total_upload_gb", "total_usage_gb", "days"])

    scraping_state["status"] = "done"
    scraping_state["message"] = f"Success! Extracted {len(deduped)} daily records."
    scraping_state["daily"] = deduped
    scraping_state["monthly"] = monthly
    scraping_state["browser_open"] = False


@app.route("/")
def index():
    daily = load_csv(OUTPUT_DIR / "daily_usage.csv")
    monthly = load_csv(OUTPUT_DIR / "monthly_usage.csv")

    return render_template_string(HTML_TEMPLATE,
                                  daily=daily,
                                  monthly=monthly,
                                  status=scraping_state["status"],
                                  message=scraping_state["message"])


@app.route("/scrape", methods=["POST"])
def scrape_endpoint():
    if scraping_state["status"] in ("waiting_login", "extracting"):
        return jsonify({"ok": False, "message": "Scraping already in progress."})

    scraping_state["status"] = "waiting_login"
    scraping_state["message"] = "Starting browser..."
    scraping_state["browser_open"] = False

    t = Thread(target=run_scraper_task, daemon=True)
    t.start()

    return jsonify({"ok": True, "message": "Browser opened. Please log into Starlink."})


@app.route("/status")
def status_endpoint():
    return jsonify({
        "status": scraping_state["status"],
        "message": scraping_state["message"],
        "browser_open": scraping_state["browser_open"],
    })


@app.route("/data")
def data_endpoint():
    daily = load_csv(OUTPUT_DIR / "daily_usage.csv")
    monthly = load_csv(OUTPUT_DIR / "monthly_usage.csv")
    return jsonify({"daily": daily, "monthly": monthly})


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Starlink Data Usage</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0b0d17;
    color: #e2e8f0;
    padding: 2rem 1rem;
    max-width: 1100px;
    margin: 0 auto;
  }
  h1 { color: #fff; margin-bottom: 0.5rem; font-size: 1.8rem; }
  .subtitle { color: #94a3b8; margin-bottom: 1.5rem; font-size: 0.95rem; }
  .btn {
    display: inline-block;
    background: #3b82f6;
    color: #fff;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 8px;
    font-size: 1rem;
    cursor: pointer;
    margin-bottom: 1.5rem;
  }
  .btn:hover { background: #2563eb; }
  .btn:disabled { background: #475569; cursor: not-allowed; }
  .status {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1.5rem;
    color: #cbd5e1;
  }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }
  .card {
    background: #1e293b;
    border-radius: 12px;
    padding: 1.25rem;
    border: 1px solid #334155;
  }
  .card h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; margin-bottom: 0.5rem; }
  .card .value { font-size: 1.6rem; font-weight: 700; color: #fff; }
  .card .unit { font-size: 0.85rem; color: #64748b; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 2rem; }
  th, td { padding: 0.65rem 0.75rem; text-align: left; font-size: 0.9rem; }
  th { background: #1e293b; color: #cbd5e1; font-weight: 600; border-bottom: 2px solid #334155; }
  td { border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #1e293b; }
  .section-title { font-size: 1.2rem; color: #fff; margin: 2rem 0 1rem; }
  .bar { height: 6px; background: #334155; border-radius: 3px; overflow: hidden; margin-top: 4px; }
  .bar-fill { height: 100%; background: #3b82f6; border-radius: 3px; }
</style>
</head>
<body>
<h1>Starlink Data Usage</h1>
<p class="subtitle">Scraped from https://starlink.com/account/service-line/AST-2293597-46342-54</p>

<button class="btn" id="scrape-btn" onclick="startScrape()">Scrape Starlink Data</button>

<div class="status" id="status-box" style="display:none;"></div>

<div id="summary-cards" class="cards"></div>

<h2 class="section-title">Monthly Totals</h2>
<table id="monthly-table">
  <thead><tr><th>Month</th><th>Download (GB)</th><th>Upload (GB)</th><th>Total (GB)</th><th>Days</th><th>Avg/Day</th></tr></thead>
  <tbody></tbody>
</table>

<h2 class="section-title">Daily Usage</h2>
<table id="daily-table">
  <thead><tr><th>Date</th><th>Download (GB)</th><th>Upload (GB)</th><th>Total (GB)</th><th>Relative</th></tr></thead>
  <tbody></tbody>
</table>

<script>
const dailyData = {{ daily | tojson }};
const monthlyData = {{ monthly | tojson }};

function formatNum(n) {
  return parseFloat(n).toLocaleString('en-US', {maximumFractionDigits:2});
}

function render() {
  if (!dailyData.length) {
    document.getElementById('summary-cards').innerHTML = '<div class="card"><h3>No Data</h3><div class="value">--</div><div class="unit">Click the button above to scrape</div></div>';
    document.querySelector('#monthly-table tbody').innerHTML = '';
    document.querySelector('#daily-table tbody').innerHTML = '';
    return;
  }

  const totalGB = dailyData.reduce((s,r) => s + parseFloat(r.total_gb || 0), 0);
  const avgGB = totalGB / dailyData.length;
  const maxDay = dailyData.reduce((a,b) => parseFloat(a.total_gb) > parseFloat(b.total_gb) ? a : b);

  document.getElementById('summary-cards').innerHTML = `
    <div class="card"><h3>Total Usage</h3><div class="value">${formatNum(totalGB)}</div><div class="unit">GB</div></div>
    <div class="card"><h3>Daily Average</h3><div class="value">${formatNum(avgGB)}</div><div class="unit">GB / day</div></div>
    <div class="card"><h3>Highest Day</h3><div class="value">${formatNum(maxDay.total_gb)}</div><div class="unit">GB on ${maxDay.date}</div></div>
    <div class="card"><h3>Days Tracked</h3><div class="value">${dailyData.length}</div><div class="unit">days</div></div>
  `;

  document.querySelector('#monthly-table tbody').innerHTML = monthlyData.map(r => {
    const avg = parseFloat(r.total_usage_gb) / parseInt(r.days);
    return `<tr><td>${r.month}</td><td>${formatNum(r.total_download_gb)}</td><td>${formatNum(r.total_upload_gb)}</td><td><strong>${formatNum(r.total_usage_gb)}</strong></td><td>${r.days}</td><td>${formatNum(avg)}</td></tr>`;
  }).join('');

  const maxDaily = Math.max(...dailyData.map(r => parseFloat(r.total_gb || 0)));
  document.querySelector('#daily-table tbody').innerHTML = dailyData.map(r => {
    const pct = (parseFloat(r.total_gb) / maxDaily) * 100;
    return `<tr><td>${r.date}</td><td>${formatNum(r.download_gb)}</td><td>${formatNum(r.upload_gb)}</td><td><strong>${formatNum(r.total_gb)}</strong></td><td><div class="bar"><div class="bar-fill" style="width:${pct}%"></div></div></td></tr>`;
  }).join('');
}

async function startScrape() {
  const btn = document.getElementById('scrape-btn');
  const status = document.getElementById('status-box');
  btn.disabled = true;
  status.style.display = 'block';
  status.textContent = 'Opening browser... Please wait.';

  const res = await fetch('/scrape', {method: 'POST'});
  const data = await res.json();
  status.textContent = data.message;

  if (data.ok) {
    pollStatus();
  } else {
    btn.disabled = false;
  }
}

async function pollStatus() {
  const btn = document.getElementById('scrape-btn');
  const status = document.getElementById('status-box');

  const interval = setInterval(async () => {
    const res = await fetch('/status');
    const s = await res.json();
    status.textContent = s.message;

    if (s.status === 'done') {
      clearInterval(interval);
      btn.disabled = false;
      // Refresh page to load new data
      location.reload();
    } else if (s.status === 'error') {
      clearInterval(interval);
      btn.disabled = false;
    }
  }, 3000);
}

render();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 60)
    print("Starlink Web Scraper App")
    print("=" * 60)
    print("Open your browser and go to: http://localhost:5000")
    print("Press Ctrl+C to stop the server.")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
