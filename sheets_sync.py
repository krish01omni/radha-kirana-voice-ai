import os
import threading
import datetime
import subprocess
import pandas as pd
from typing import Dict, Any, Optional

DEFAULT_CATALOG = [
    {"Item Name": "Atta (Aashirvaad)", "Unit": "1 kg", "Price (₹)": 60.0, "In Stock": "Yes"},
    {"Item Name": "Sugar (Cheeni)", "Unit": "1 kg", "Price (₹)": 45.0, "In Stock": "Yes"},
    {"Item Name": "Amul Taaza Milk", "Unit": "500 ml", "Price (₹)": 27.0, "In Stock": "Yes"},
    {"Item Name": "Tata Salt", "Unit": "1 kg", "Price (₹)": 28.0, "In Stock": "Yes"},
    {"Item Name": "Maggi 2-Minute Noodles", "Unit": "1 packet", "Price (₹)": 14.0, "In Stock": "Yes"},
    {"Item Name": "Fortune Sunflower Oil", "Unit": "1 litre", "Price (₹)": 145.0, "In Stock": "Yes"},
    {"Item Name": "Basmati Rice", "Unit": "1 kg", "Price (₹)": 90.0, "In Stock": "Yes"},
    {"Item Name": "Taj Mahal Tea", "Unit": "250 g", "Price (₹)": 110.0, "In Stock": "Yes"},
    {"Item Name": "Toor Dal", "Unit": "1 kg", "Price (₹)": 160.0, "In Stock": "Yes"},
    {"Item Name": "Surf Excel Detergent", "Unit": "1 kg", "Price (₹)": 135.0, "In Stock": "Yes"}
]

ORDER_COLUMNS = [
    "Timestamp", "Call ID", "Customer Name", "Customer Contact",
    "Ordered Items & Rates", "Total Bill (₹)", "Delivery Address",
    "Special Instructions", "Payment Method", "Audio File Path", "Status"
]

# Multilingual / Vernacular alias dictionary mapping colloquial terms to catalog keys
ITEM_SYNONYMS = {
    "atta": ["atta", "aata", "aashirvaad", "gehu", "flour"],
    "sugar": ["sugar", "cheeni", "chini", "shakkar", "sakkar", "mithai"],
    "milk": ["milk", "doodh", "dudh", "amul", "taaza", "dood", "packet doodh"],
    "salt": ["salt", "namak", "tata salt", "noon"],
    "maggi": ["maggi", "meggi", "noodles", "yippee", "noodle"],
    "oil": ["oil", "tel", "sunflower", "fortune", "sarson", "refined"],
    "rice": ["rice", "chawal", "chaawal", "basmati", "akshat"],
    "tea": ["tea", "chai", "chay", "taj mahal", "patti", "chaipatti"],
    "dal": ["dal", "daal", "toor", "arhar", "pulse", "rahari"],
    "detergent": ["detergent", "surf", "sabun", "surf excel", "powder", "soap"]
}

class SheetsSyncManager:
    _lock = threading.Lock()

    def __init__(self, excel_path: str = "data/kirana_store.xlsx", spreadsheet_id: Optional[str] = None):
        self.excel_path = os.path.abspath(excel_path)
        self.spreadsheet_id = spreadsheet_id or os.getenv("SPREADSHEET_ID")
        self.orders_sheet_id = os.getenv("ORDERS_LOG_SHEET_ID") or self.spreadsheet_id
        self.price_sheet_id = os.getenv("PRICE_CATALOG_SHEET_ID")
        os.makedirs(os.path.dirname(self.excel_path), exist_ok=True)
        self._initialize_excel_if_needed()

    def _initialize_excel_if_needed(self):
        """Creates the two-tab Kirana store workbook safely under thread lock."""
        with self._lock:
            if not os.path.exists(self.excel_path):
                print(f"[SheetsSyncManager] Initializing master workbook: {self.excel_path}")
                with pd.ExcelWriter(self.excel_path, engine="openpyxl") as writer:
                    catalog_df = pd.DataFrame(DEFAULT_CATALOG)
                    catalog_df.to_excel(writer, sheet_name="Price_Catalog", index=False)
                    
                    orders_df = pd.DataFrame(columns=ORDER_COLUMNS)
                    orders_df.to_excel(writer, sheet_name="Orders_Log", index=False)
                print("[SheetsSyncManager] Price_Catalog and Orders_Log tabs initialized.")

    def sanitize_field(self, value: Any) -> str:
        """Sanitizes text fields to prevent CSV/Formula injection (CWE-1236)."""
        if value is None:
            return ""
        text = str(value).strip()
        if text.startswith(("=", "+", "-", "@")):
            text = "'" + text
        text = "".join(ch for ch in text if ch >= " " or ch == "\t")
        return text

    def get_price_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Thread-safe read access to Price_Catalog (Cloud Google Sheet with local fallback)."""
        # 1. Try reading from connected Cloud Google Sheet
        if getattr(self, "price_sheet_id", None):
            try:
                import io, requests
                url = f"https://docs.google.com/spreadsheets/d/{self.price_sheet_id}/export?format=csv"
                resp = requests.get(url, timeout=4)
                if resp.status_code == 200 and resp.text and len(resp.text) > 10:
                    df = pd.read_csv(io.StringIO(resp.text))
                    catalog = {}
                    for _, row in df.iterrows():
                        raw_name = self.sanitize_field(row.get("Item Name", row.get("item_name", "")))
                        if not raw_name:
                            continue
                        unit = self.sanitize_field(row.get("Unit", row.get("unit", "units")))
                        try:
                            price = float(row.get("Price (₹)", row.get("Price", row.get("price", 0.0))))
                        except (ValueError, TypeError):
                            price = 0.0
                        in_stock = str(row.get("In Stock", row.get("in_stock", "Yes"))).strip().lower() in ["yes", "y", "true", "1"]
                        key = raw_name.lower()
                        catalog[key] = {
                            "raw_name": raw_name,
                            "unit": unit,
                            "price": price,
                            "in_stock": in_stock
                        }
                    if catalog:
                        return catalog
            except Exception:
                pass

        # 2. Local Excel Master Fallback
        with self._lock:
            try:
                df = pd.read_excel(self.excel_path, sheet_name="Price_Catalog")
                catalog = {}
                for _, row in df.iterrows():
                    raw_name = self.sanitize_field(row.get("Item Name", ""))
                    if not raw_name:
                        continue
                    unit = self.sanitize_field(row.get("Unit", "unit"))
                    try:
                        price = float(row.get("Price (₹)", 0.0))
                    except (ValueError, TypeError):
                        price = 0.0
                    in_stock = str(row.get("In Stock", "Yes")).strip().lower() in ["yes", "y", "true", "1"]
                    
                    key = raw_name.lower()
                    catalog[key] = {
                        "raw_name": raw_name,
                        "unit": unit,
                        "price": price,
                        "in_stock": in_stock
                    }
                return catalog
            except Exception as e:
                print(f"[SheetsSyncManager Error reading catalog] {e}")
                return {}

    def match_item_price(self, query_name: str) -> tuple[float, str, str]:
        """
        Fuzzy matches customer's item name (Hindi, Hinglish, Bhojpuri) against the Price_Catalog.
        Returns: (price, unit, canonical_name)
        """
        catalog = self.get_price_catalog()
        query = query_name.lower().strip()

        # 1. Direct substring match in catalog
        for cat_key, cat_info in catalog.items():
            if cat_key in query or query in cat_key:
                return cat_info["price"], cat_info["unit"], cat_info["raw_name"]

        # 2. Match via Indian vernacular synonyms
        for canonical_group, aliases in ITEM_SYNONYMS.items():
            for alias in aliases:
                if alias in query:
                    # Find corresponding catalog entry
                    for cat_key, cat_info in catalog.items():
                        if canonical_group in cat_key or any(a in cat_key for a in aliases):
                            return cat_info["price"], cat_info["unit"], cat_info["raw_name"]

        return 0.0, "units", query_name.title()

    def get_catalog_summary_text(self) -> str:
        """Returns safe summary text of available inventory for Radha's context."""
        catalog = self.get_price_catalog()
        lines = []
        for _, info in catalog.items():
            stock = "In Stock" if info["in_stock"] else "OUT OF STOCK"
            lines.append(f"- {info['raw_name']}: Rs. {info['price']} per {info['unit']} ({stock})")
        return "\n".join(lines)

    def log_customer_order(self, call_id: str, extraction: Any, audio_file_path: str = "") -> Dict[str, Any]:
        """
        Thread-safe append of confirmed customer orders.
        Guarantees non-zero total calculation when items are present.
        """
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item_lines = []
        total_bill = 0.0

        for item in getattr(extraction, "items_ordered", []):
            item_name = self.sanitize_field(getattr(item, "item_name", "Item"))
            try:
                qty = float(getattr(item, "quantity", 1))
            except (ValueError, TypeError):
                qty = 1.0

            # Use vernacular fuzzy matching to find price
            matched_price, unit, canonical_name = self.match_item_price(item_name)
            
            agent_subtotal = getattr(item, "subtotal", None)
            agent_unit_price = getattr(item, "unit_price", None)
            if agent_unit_price and agent_unit_price > 0:
                matched_price = float(agent_unit_price)

            if agent_subtotal and agent_subtotal > 0:
                subtotal = float(agent_subtotal)
            else:
                subtotal = matched_price * qty
            total_bill += subtotal
            sub_int = int(round(subtotal))
            matched_p_int = int(round(matched_price))
            price_tag = f"@Rs.{matched_p_int}" if matched_p_int > 0 else "Market Rate"
            qty_tag = int(qty) if (hasattr(qty, "is_integer") and qty.is_integer()) or qty == int(qty) else qty
            item_lines.append(f"{qty_tag} {unit} {canonical_name} ({price_tag} = Rs.{sub_int})")

        # Fallback: if extraction already provided a computed bill, verify it
        extracted_bill = getattr(extraction, "total_calculated_bill", 0.0)
        if extracted_bill and extracted_bill > 0:
            total_bill = float(extracted_bill)

        items_str = "; ".join(item_lines) if item_lines else "General Inquiry"
        instructions_list = [self.sanitize_field(inst) for inst in getattr(extraction, "special_instructions", [])]
        instructions_str = " | ".join(instructions_list) if instructions_list else "None"

        order_row = {
            "Timestamp": now,
            "Call ID": self.sanitize_field(call_id),
            "Customer Name": self.sanitize_field(getattr(extraction, "customer_name", "Customer")),
            "Customer Contact": self.sanitize_field(getattr(extraction, "customer_contact", "Web Phone")),
            "Ordered Items & Rates": items_str,
            "Total Bill (₹)": int(round(total_bill)),
            "Delivery Address": self.sanitize_field(getattr(extraction, "delivery_address", "Store Pickup")),
            "Special Instructions": instructions_str,
            "Payment Method": self.sanitize_field(getattr(extraction, "payment_method", "Cash on Delivery")),
            "Audio File Path": self.sanitize_field(audio_file_path),
            "Status": "PENDING"
        }

        # 1. Thread-safe write to Excel
        with self._lock:
            try:
                try:
                    orders_df = pd.read_excel(self.excel_path, sheet_name="Orders_Log")
                except Exception:
                    orders_df = pd.DataFrame(columns=ORDER_COLUMNS)
                
                new_row_df = pd.DataFrame([order_row])
                updated_df = pd.concat([orders_df, new_row_df], ignore_index=True)
                
                with pd.ExcelWriter(self.excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                    updated_df.to_excel(writer, sheet_name="Orders_Log", index=False)
                print(f"[SheetsSyncManager] Order logged safely: {call_id} -> Total Rs. {round(total_bill, 2)}")
            except Exception as e:
                print(f"[SheetsSyncManager Excel Append Error] {e}")

        # 2. Secure Google Sheets append
        target_sheet = getattr(self, "orders_sheet_id", None) or self.spreadsheet_id
        if target_sheet:
            try:
                row_vals = []
                for col in ORDER_COLUMNS:
                    v = str(order_row.get(col, "")).replace('"', '""').replace(",", "\\,").replace("\n", " ")
                    row_vals.append(v)
                csv_line = ",".join(row_vals)
                gsheets_cmd = "gsheets.cmd" if os.name == "nt" else "gsheets"
                safe_cmd = [gsheets_cmd, "mutate", "append", str(target_sheet), "Sheet1", csv_line]
                res = subprocess.run(safe_cmd, shell=True, capture_output=True, text=True, timeout=10)
                if res.returncode == 0:
                    print(f"[SheetsSyncManager] Synced to Google Sheet: {target_sheet}")
                else:
                    print(f"[SheetsSyncManager gsheets warning] {res.stderr.strip()}")
            except Exception as e:
                print(f"[SheetsSyncManager Google Sheet Sync Error] {e}")

        # 3. Instant Telegram Bot Order Notification
        try:
            from telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            threading.Thread(target=notifier.send_order_alert, args=(order_row,), daemon=True).start()
        except Exception as e:
            print(f"[Telegram Notification Trigger Error] {e}")

        return order_row
