import os
import sys
import subprocess
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sheet_id = "1GNGMQxc-Bh1BwgfTMnwxTijiymwmXBNCcqLJE22tO18"
excel_path = "d:/hack idea/voice_calling_agent/data/kirana_store.xlsx"

df = pd.read_excel(excel_path, sheet_name="Orders_Log")

cols = [
    "Timestamp", "Call ID", "Customer Name", "Customer Contact",
    "Ordered Items & Rates", "Total Bill (₹)", "Delivery Address",
    "Special Instructions", "Payment Method", "Audio File Path", "Status"
]

print(f"Reading orders from {excel_path}...")
rows_to_append = []
for idx, row in df.iterrows():
    name = str(row.get("Customer Name", "")).strip()
    bill = row.get("Total Bill (₹)", 0)
    items = str(row.get("Ordered Items & Rates", ""))
    if bill > 0 or (name and name != "Customer" and name != "nan"):
        row_vals = []
        for c in cols:
            val = str(row.get(c, "")).replace("nan", "").replace('"', '""').replace(",", "\\,").replace("\n", " ").strip()
            row_vals.append(val)
        rows_to_append.append(",".join(row_vals))

print(f"Appending {len(rows_to_append)} confirmed orders to Google Sheet {sheet_id}...")
gsheets_bin = "gsheets.cmd" if os.name == "nt" else "gsheets"
for r in rows_to_append:
    cmd = [gsheets_bin, "mutate", "append", sheet_id, "Sheet1", r]
    res = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if res.returncode == 0:
        print(f"[OK] Appended: {r[:70]}...")
    else:
        print(f"[ERROR] {res.stderr.strip()}")

print("\nSUCCESS: All existing orders successfully synced to Google Sheet!")
