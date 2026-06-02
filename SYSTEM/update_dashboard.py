"""Update index.html with real data from CSV files."""
import csv
from pathlib import Path

OUTPUT_DIR = Path("./output")

def load_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

daily = load_csv(OUTPUT_DIR / "daily_usage.csv")
monthly = load_csv(OUTPUT_DIR / "monthly_usage.csv")

# Convert to JS array strings
daily_js = ",\n  ".join(
    f'{{date:"{r["date"]}",download_gb:{r["download_gb"]},upload_gb:{r["upload_gb"]},total_gb:{r["total_gb"]}}}'
    for r in daily
)

monthly_js = ",\n  ".join(
    f'{{month:"{r["month"]}",total_download_gb:{r["total_download_gb"]},total_upload_gb:{r["total_upload_gb"]},total_usage_gb:{r["total_usage_gb"]},days:{r["days"]}}}'
    for r in monthly
)

# Read existing HTML template
html_path = Path("c:/Users/ADMIN/OneDrive/Documents/SYSTEM/index.html")
with open(html_path, "r", encoding="utf-8") as f:
    html = f.read()

# Replace daily data array
import re
html = re.sub(
    r'const daily = \[.*?\];',
    f'const daily = [\n  {daily_js}\n];',
    html,
    flags=re.DOTALL
)

# Replace monthly data array
html = re.sub(
    r'const monthly = \[.*?\];',
    f'const monthly = [\n  {monthly_js}\n];',
    html,
    flags=re.DOTALL
)

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("index.html updated with real data!")
print(f"  Daily records: {len(daily)}")
print(f"  Monthly records: {len(monthly)}")
