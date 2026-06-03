# Webscrape-for-Fundamentals

# Starlink Usage Scraper

A small Flask app that scrapes Starlink daily usage history and exports a CSV.

## Quick start

1. Create and activate a Python virtual environment (Windows example):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. (Optional) Create a `.env` file to override defaults (see `app.py` for keys):

- `STARLINK_PROFILE_PATH` — browser profile path
- `STARLINK_BROWSER` — `firefox` or `chrome`

4. Run the app:

```powershell
python app.py
```

5. Open the UI: http://127.0.0.1:5000/

## Usage

- Click **Start Scraper** to fetch usage history from the server-side scraper (`/scrape`).
- When finished, click **Download CSV** to get `output/starlink_usage.csv` (`/download`).

The UI was updated to a minimalist design; functionality and endpoints remain unchanged.

## Troubleshooting

- If scraping fails due to authentication, the app will attempt to use `output/data_usage.json` as a fallback.
- Check `app.py` config values and ensure the browser profile path is correct.

## License
MIT-style — use at your own risk.