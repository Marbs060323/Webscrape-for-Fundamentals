import os
from flask import Flask, render_template, jsonify, send_file
from dotenv import load_dotenv
from scraper.engine import fetch_raw_data
from scraper.exporter import process_data

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# These must match your .env file keys
PROFILE = os.getenv("STARLINK_PROFILE_PATH", r"C:\Users\yusof\AppData\Roaming\Mozilla\Firefox\Profiles\fqm7f8q7.StarlinkScraper")
BROWSER = os.getenv("STARLINK_BROWSER", "firefox")
DASHBOARD = "https://starlink.com/account/service-line/AST-2293597-46342-54?selectedDevice=ut01000000-00000000-0060d786&page=0&limit=5"
API_URL = "https://starlink.com/api/telemetryagg/v1/data-usage/account/ACC-2735603-74738-20/service-line/AST-2293597-46342-54/annotated"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scrape')
def scrape_without_browser():
    # FIXED: The order must be (profile, dashboard, api, browser)
    # Your engine.py expects: fetch_raw_data(profile_path, dashboard_url, api_url, browser_type)
    raw = None
    try:
        raw = fetch_raw_data(PROFILE, DASHBOARD, API_URL, BROWSER)
    except Exception as e:
        print(f"Scrape Failed: {e}")

    # Fallback to demo mode if live fails (Important for teacher)
    if not raw or "authenticated_user_required" in raw:
        print("Using local backup JSON...")
        if os.path.exists('output/data_usage.json'):
            with open('output/data_usage.json', 'r') as f:
                raw = f.read()
        else:
            return jsonify({"status": "error", "message": "Auth failed and no backup data found."}), 401

    clean_data = process_data(raw)
    if not clean_data:
        return jsonify({
            "status": "error",
            "message": "Scrape returned no usable JSON. Check login/profile path or the Starlink API response."
        }), 500

    return jsonify({"status": "success", "data": clean_data})

@app.route('/download')
def download():
    path = os.path.join('output', 'starlink_usage.csv')
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "CSV File not found", 404

if __name__ == '__main__':
    app.run(debug=True)