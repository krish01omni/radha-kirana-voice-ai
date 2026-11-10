import os
import requests
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None

    def auto_detect_chat_id(self) -> Optional[str]:
        """Polls getUpdates to detect recent chat_id if not explicitly configured."""
        if not self.base_url:
            return None
        try:
            resp = requests.get(f"{self.base_url}/getUpdates", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                if results:
                    last_update = results[-1]
                    message = last_update.get("message") or last_update.get("channel_post") or {}
                    chat = message.get("chat", {})
                    found_id = str(chat.get("id"))
                    if found_id:
                        self.chat_id = found_id
                        return found_id
        except Exception as e:
            print(f"[Telegram Auto-Detect Error] {e}")
        return None

    def send_order_alert(self, order_data: Dict[str, Any]) -> bool:
        """Sends a rich formatted order receipt notification to Telegram."""
        if not self.base_url:
            print("[Telegram Notifier] No bot token configured.")
            return False

        if not self.chat_id:
            self.auto_detect_chat_id()

        if not self.chat_id:
            print("[Telegram Notifier] Cannot send alert: No chat_id found. Please send /start to your Telegram bot.")
            return False

        customer_name = order_data.get("Customer Name") or order_data.get("customer_name") or "Valued Customer"
        customer_contact = order_data.get("Customer Contact") or order_data.get("customer_contact") or "Web Phone"
        total_bill = order_data.get("Total Bill (₹)") or order_data.get("total_bill") or 0
        total_int = int(round(float(total_bill)))
        delivery_address = order_data.get("Delivery Address") or order_data.get("delivery_address") or "Store Pickup"
        payment_method = order_data.get("Payment Method") or order_data.get("payment_method") or "Cash on Delivery"
        call_id = order_data.get("Call ID") or order_data.get("call_id") or "ORDER"
        items_str = order_data.get("Ordered Items & Rates") or ""

        # Determine delivery mode
        addr_lower = delivery_address.lower()
        if "pickup" in addr_lower or "दुकान" in addr_lower or "counter" in addr_lower:
            delivery_mode = "Store Pickup"
        else:
            delivery_mode = "Home Delivery"

        # Format items neatly
        if not items_str and "items_ordered" in order_data:
            items_list = []
            for it in order_data["items_ordered"]:
                name = getattr(it, "item_name", it.get("item_name", "Item"))
                qty = getattr(it, "quantity", it.get("quantity", 1))
                unit = getattr(it, "unit", it.get("unit", "units"))
                sub = getattr(it, "subtotal", it.get("subtotal", 0))
                price = getattr(it, "unit_price", None)
                if price:
                    p_int = int(round(float(price)))
                    items_list.append(f"• {qty} × {unit} {name} (@₹{p_int} = ₹{int(round(float(sub)))})")
                else:
                    items_list.append(f"• {qty} {unit} {name} (₹{int(round(float(sub)))})")
            items_text = "\n".join(items_list)
        else:
            # Parse semicolon-separated string from sheets_sync
            clean_lines = []
            for part in items_str.split(";"):
                p = part.strip()
                if p:
                    # Clean up 'Rs.' to '₹' and ensure spacing
                    p = p.replace("Rs.", "₹").replace("Rs ", "₹")
                    clean_lines.append(f"• {p}")
            items_text = "\n".join(clean_lines) if clean_lines else "• General Order"

        msg = (
            f"🛒 *नया किराना ऑर्डर (New Order #{call_id})*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 *ग्राहक (Customer):* {customer_name}\n"
            f"📞 *संपर्क (Contact):* {customer_contact}\n"
            f"🛵 *डिलीवरी मोड:* {delivery_mode}\n"
            f"📍 *पता (Address):* {delivery_address}\n"
            f"💵 *पेमेंट:* {payment_method}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *सामान (Items):*\n"
            f"{items_text}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *कुल बिल (Total): ₹{total_int}*"
        )

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "Markdown"
            }
            res = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=6)
            if res.status_code == 200:
                print(f"[Telegram Notifier] Order alert sent to chat {self.chat_id}!")
                return True
            else:
                print(f"[Telegram Notifier Error {res.status_code}] {res.text}")
        except Exception as e:
            print(f"[Telegram Notifier Exception] {e}")

        return False
