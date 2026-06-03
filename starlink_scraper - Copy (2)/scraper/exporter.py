import json
import pandas as pd
import os
from datetime import datetime, timedelta

def process_data(raw_json):
    all_rows = []
    try:
        if raw_json is None:
            raise ValueError("No data returned from the API fetch")

        if not isinstance(raw_json, str):
            raw_json = str(raw_json)

        raw_json = raw_json.strip()
        if not raw_json:
            raise ValueError("Empty response returned from the API fetch")

        if raw_json.startswith("ERROR:"):
            raise ValueError(raw_json)

        if raw_json.startswith("<"):
            raise ValueError("Received HTML instead of JSON. The session may not be authenticated.")

        data = json.loads(raw_json)
        start_from = datetime(2025, 11, 1)
        
        # Helper to find the billing cycles anywhere in the JSON
        billing_cycles = []
        def find_keys(obj):
            nonlocal billing_cycles
            if isinstance(obj, dict):
                if 'billingCyclesAnnotated' in obj:
                    billing_cycles = obj['billingCyclesAnnotated']
                    return
                for v in obj.values(): find_keys(v)
            elif isinstance(obj, list):
                for i in obj: find_keys(i)

        find_keys(data)

        for cycle in billing_cycles:
            start_date = datetime.strptime(cycle['startDate'].split('T')[0], "%Y-%m-%d")
            if start_date < start_from:
                continue
            
            for i, day in enumerate(cycle.get('dailyData', [])):
                current_date = start_date + timedelta(days=i)
                if isinstance(day, list):
                    usage = day[0] if day else 0
                elif isinstance(day, dict):
                    usage = next(iter(day.values()), 0)
                else:
                    usage = day

                all_rows.append({
                    "Date": f"{current_date.month}/{current_date.day}/{current_date.year}",
                    "Data Usage (GB)": round(float(usage), 2)
                })

        # Save to CSV
        os.makedirs('output', exist_ok=True)
        df = pd.DataFrame(all_rows)
        df.to_csv('output/starlink_usage.csv', index=False)
        return all_rows
    except Exception as e:
        print(f"Export Error: {e}")
        return None