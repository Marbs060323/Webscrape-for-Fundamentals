"""Shift all dates in CSVs and index.html by +1 year."""

import csv
import re
from pathlib import Path

OUTPUT_DIR = Path("./output")

# Shift monthly CSV
monthly = []
with open(OUTPUT_DIR / "monthly_usage.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        year, mon = r["month"].split("-")
        r["month"] = f"{int(year)+1}-{mon}"
        monthly.append(r)

with open(OUTPUT_DIR / "monthly_usage.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["month","total_download_gb","total_upload_gb","total_usage_gb","days"])
    writer.writeheader()
    writer.writerows(monthly)

# Shift daily CSV
daily = []
with open(OUTPUT_DIR / "daily_usage.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for r in reader:
        parts = r["date"].split("-")
        parts[0] = str(int(parts[0]) + 1)
        r["date"] = "-".join(parts)
        daily.append(r)

with open(OUTPUT_DIR / "daily_usage.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["date","download_gb","upload_gb","total_gb"])
    writer.writeheader()
    writer.writerows(daily)

# Update index.html
html_path = Path("c:/Users/ADMIN/OneDrive/Documents/SYSTEM/index.html")
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Replace 2024- with 2025- and 2025- with 2026-
# Do 2024 first, then 2025, to avoid double-shifting
html = html.replace("2024-", "TEMP_")
html = html.replace("2025-", "2026-")
html = html.replace("TEMP_", "2025-")

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Dates shifted by +1 year!")
print("Monthly:", [m["month"] for m in monthly])
print("Daily range:", daily[0]["date"], "to", daily[-1]["date"])
