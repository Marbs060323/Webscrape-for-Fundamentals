# Starlink Data Usage Scraper

Scrapes **daily** and **monthly** data usage from the Starlink account page and exports to CSV with a web dashboard.

## Install

```bash
pip install -r requirements.txt
playwright install chromium
```

## Usage (Web App — Easiest)

Run the web server, then open the URL in your browser:

```bash
python app.py
```

**Open:** http://localhost:5000

**Steps:**
1. Click **"Scrape Starlink Data"** on the web page
2. A Chrome window opens — **log into your Starlink account**
3. The app **auto-detects** when usage data appears and extracts it
4. The dashboard updates automatically with real data

No terminal interaction needed — everything is controlled from the web page.

## Alternative (CLI)

If you prefer command-line:

```bash
python scraper.py --login
```

A browser opens. Log in, then press **ENTER** in the terminal when data is visible.

## Output

- `output/daily_usage.csv` — per-day download, upload, total (GB)
- `output/monthly_usage.csv` — monthly rollups

## Files

- `app.py` — Flask web app with one-click scraping and dashboard
- `scraper.py` — CLI scraper with interactive login
- `requirements.txt` — `playwright`, `flask`
