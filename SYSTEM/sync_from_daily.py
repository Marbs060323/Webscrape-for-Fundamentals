"""Recalculate monthly totals from the trimmed daily CSV and update index.html."""
import csv
import re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

SYSTEM = Path("c:/Users/ADMIN/OneDrive/Documents/SYSTEM")
out = SYSTEM / "output"

# Load daily data
daily = []
with open(out / "daily_usage.csv", "r", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        daily.append(r)

# Calculate monthly totals from daily
monthly_data = defaultdict(lambda: {"download": 0.0, "upload": 0.0, "total": 0.0, "days": 0})
for r in daily:
    date = datetime.strptime(r["date"], "%Y-%m-%d")
    month_key = date.strftime("%Y-%m")
    monthly_data[month_key]["download"] += float(r["download_gb"])
    monthly_data[month_key]["upload"] += float(r["upload_gb"])
    monthly_data[month_key]["total"] += float(r["total_gb"])
    monthly_data[month_key]["days"] += 1

monthly = []
for month in sorted(monthly_data.keys()):
    d = monthly_data[month]
    monthly.append({
        "month": month,
        "total_download_gb": round(d["download"], 2),
        "total_upload_gb": round(d["upload"], 2),
        "total_usage_gb": round(d["total"], 2),
        "days": d["days"]
    })

# Save monthly CSV
with open(out / "monthly_usage.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["month","total_download_gb","total_upload_gb","total_usage_gb","days"])
    w.writeheader()
    w.writerows(monthly)

# Update index.html
html_path = SYSTEM / "index.html"
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

daily_js = ",\n  ".join(
    f'{{date:"{r["date"]}",download_gb:{r["download_gb"]},upload_gb:{r["upload_gb"]},total_gb:{r["total_gb"]}}}'
    for r in daily
)
monthly_js = ",\n  ".join(
    f'{{month:"{r["month"]}",total_download_gb:{r["total_download_gb"]},total_upload_gb:{r["total_upload_gb"]},total_usage_gb:{r["total_usage_gb"]},days:{r["days"]}}}'
    for r in monthly
)

html = re.sub(r'const daily = \[.*?\];', f'const daily = [\n  {daily_js}\n];', html, flags=re.DOTALL)
html = re.sub(r'const monthly = \[.*?\];', f'const monthly = [\n  {monthly_js}\n];', html, flags=re.DOTALL)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Synced from daily data!")
for m in monthly:
    print(f"  {m['month']}: {m['total_usage_gb']} GB ({m['days']} days)")
print(f"Daily records: {len(daily)}")
