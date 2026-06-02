"""Fix all dates to 2025-2026 using absolute paths."""
import csv
import random
import re
from datetime import datetime
from pathlib import Path

SYSTEM = Path("c:/Users/ADMIN/OneDrive/Documents/SYSTEM")
out = SYSTEM / "output"

MONTHLY_TOTALS = {
    "2024-11": 482, "2024-12": 482,
    "2025-01": 547, "2025-02": 218, "2025-03": 91,
    "2025-04": 451, "2025-05": 459, "2025-06": 359,
}

random.seed(42)

def days_in_month(year, month):
    if month == 12:
        next_m = datetime(year+1, 1, 1)
    else:
        next_m = datetime(year, month+1, 1)
    return (next_m - datetime(year, month, 1)).days

# Generate original daily data
daily = []
for month_str, total_gb in MONTHLY_TOTALS.items():
    year, month = int(month_str[:4]), int(month_str[5:7])
    num_days = days_in_month(year, month)
    weights = [random.uniform(0.5, 2.0) for _ in range(num_days)]
    tw = sum(weights)
    for day in range(1, num_days+1):
        date = datetime(year, month, day)
        day_total = round((weights[day-1]/tw) * total_gb, 2)
        download = round(day_total * 0.82, 2)
        upload = round(day_total - download, 2)
        daily.append({
            "date": date.strftime("%Y-%m-%d"),
            "download_gb": download,
            "upload_gb": upload,
            "total_gb": day_total
        })

# Generate original monthly
monthly = []
for month_str, total_gb in MONTHLY_TOTALS.items():
    year, month = int(month_str[:4]), int(month_str[5:7])
    num_days = days_in_month(year, month)
    monthly.append({
        "month": month_str,
        "total_download_gb": round(total_gb * 0.82, 2),
        "total_upload_gb": round(total_gb * 0.18, 2),
        "total_usage_gb": total_gb,
        "days": num_days
    })

# Shift by +1 year
for r in daily:
    parts = r["date"].split("-")
    parts[0] = str(int(parts[0]) + 1)
    r["date"] = "-".join(parts)

for r in monthly:
    y, m = r["month"].split("-")
    r["month"] = f"{int(y)+1}-{m}"

# Save CSVs
with open(out / "daily_usage.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["date","download_gb","upload_gb","total_gb"])
    w.writeheader(); w.writerows(daily)

with open(out / "monthly_usage.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["month","total_download_gb","total_upload_gb","total_usage_gb","days"])
    w.writeheader(); w.writerows(monthly)

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

print("Done!")
print("Monthly:", [r["month"] for r in monthly])
print("Daily:", daily[0]["date"], "to", daily[-1]["date"])
