"""
Generate realistic daily data from the real monthly totals we extracted.
This replaces sample data with real monthly data + estimated daily distribution.
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path

# Real monthly totals extracted from browser console
MONTHLY_TOTALS = {
    "2024-11": 482,
    "2024-12": 482,
    "2025-01": 547,
    "2025-02": 218,
    "2025-03": 91,
    "2025-04": 451,
    "2025-05": 459,
    "2025-06": 359,
}

def days_in_month(year, month):
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    return (next_month - datetime(year, month, 1)).days

def generate_daily_data():
    """Generate realistic daily usage with some variation (not flat)."""
    import random
    random.seed(42)  # Reproducible
    
    daily = []
    for month_str, total_gb in MONTHLY_TOTALS.items():
        year, month = int(month_str[:4]), int(month_str[5:7])
        num_days = days_in_month(year, month)
        
        # Generate random weights that sum to total
        weights = [random.uniform(0.5, 2.0) for _ in range(num_days)]
        total_weight = sum(weights)
        
        for day in range(1, num_days + 1):
            date = datetime(year, month, day)
            weight = weights[day - 1]
            day_total = round((weight / total_weight) * total_gb, 2)
            download = round(day_total * 0.82, 2)
            upload = round(day_total - download, 2)
            daily.append({
                "date": date.strftime("%Y-%m-%d"),
                "download_gb": download,
                "upload_gb": upload,
                "total_gb": day_total
            })
    
    return daily

def generate_monthly_data():
    """Generate monthly aggregation from totals."""
    monthly = []
    for month_str, total_gb in MONTHLY_TOTALS.items():
        year, month = int(month_str[:4]), int(month_str[5:7])
        num_days = days_in_month(year, month)
        download = round(total_gb * 0.82, 2)
        upload = round(total_gb - download, 2)
        monthly.append({
            "month": month_str,
            "total_download_gb": download,
            "total_upload_gb": upload,
            "total_usage_gb": total_gb,
            "days": num_days
        })
    return monthly

def save_csv(data, path, fieldnames):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Saved {len(data)} rows to {path}")

if __name__ == "__main__":
    OUTPUT_DIR = Path("./output")
    
    daily = generate_daily_data()
    monthly = generate_monthly_data()
    
    save_csv(daily, OUTPUT_DIR / "daily_usage.csv", ["date", "download_gb", "upload_gb", "total_gb"])
    save_csv(monthly, OUTPUT_DIR / "monthly_usage.csv", ["month", "total_download_gb", "total_upload_gb", "total_usage_gb", "days"])
    
    print("\n=== REAL DATA SUMMARY ===")
    print("Monthly totals extracted from Starlink website:")
    for m in monthly:
        print(f"  {m['month']}: {m['total_usage_gb']} GB ({m['days']} days)")
    print(f"\nTotal daily records: {len(daily)}")
    print("NOTE: Daily values are estimated distributions based on real monthly totals.")
