import os
import re
import sys
import time
import json
import pydantic
from typing import List, Optional, Dict, Any, Tuple
from google import genai
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("d:/hack idea/voice_calling_agent/.env")

class KiranaItem(pydantic.BaseModel):
    item_name: str = pydantic.Field(description="Standardized grocery item name")
    quantity: float = pydantic.Field(default=1.0, description="Numeric quantity in catalog units")
    unit: str = pydantic.Field(default="units", description="Unit of measurement: kg, packets, litres, grams, pieces")
    unit_price: float = pydantic.Field(default=0.0, description="Catalog unit price in INR")
    subtotal: float = pydantic.Field(default=0.0, description="Line item total in INR (quantity * unit_price)")
    brand_preference: Optional[str] = pydantic.Field(default=None, description="Specific brand")

class KiranaCallExtraction(pydantic.BaseModel):
    customer_name: str = pydantic.Field(default="Valued Customer", description="Customer's identified name")
    customer_contact: str = pydantic.Field(default="Web Phone", description="Phone number or contact identifier")
    items_ordered: List[KiranaItem] = pydantic.Field(default_factory=list, description="List of items ordered")
    total_calculated_bill: float = pydantic.Field(default=0.0, description="Grand total bill in INR")
    special_instructions: List[str] = pydantic.Field(default_factory=list, description="Delivery instructions")
    fulfillment_type: str = pydantic.Field(default="DELIVERY", description="DELIVERY or PICKUP")
    delivery_address: str = pydantic.Field(default="Store Pickup", description="Delivery address or room number")
    payment_method: str = pydantic.Field(default="Cash on Delivery", description="Payment mode")
    executive_summary: str = pydantic.Field(default="Kirana voice order", description="Clean 1-2 sentence order summary")

class KiranaSession:
    """Maintains active state per call across the 7 structured stages to eliminate loops."""
    def __init__(self, call_id: str, sync_manager: Any):
        self.call_id = call_id
        self.sync_manager = sync_manager
        # States: ORDERING -> CONFIRM_ORDER -> COLLECT_NAME -> COLLECT_FULFILLMENT -> COLLECT_ADDRESS -> COLLECT_PAYMENT -> FINALIZED
        self.state = "ORDERING"
        self.cart: Dict[str, KiranaItem] = {}  # canonical item_name -> KiranaItem
        self.customer_name: Optional[str] = None
        self.customer_contact: Optional[str] = None
        self.fulfillment_type: Optional[str] = None  # "DELIVERY" or "PICKUP"
        self.delivery_address: Optional[str] = None
        self.payment_method: Optional[str] = None   # "Cash on Delivery", "Store Cash", "Online UPI"
        self.dialog_history: List[str] = []
        self.total_bill: float = 0.0

    def recalculate_total(self) -> float:
        total = 0.0
        for item in self.cart.values():
            total += float(item.subtotal)
        self.total_bill = round(total, 2)
        return self.total_bill

    def to_extraction(self) -> KiranaCallExtraction:
        self.recalculate_total()
        items = list(self.cart.values())
        name = self.customer_name or "Valued Customer"
        f_type = self.fulfillment_type or ("PICKUP" if "pickup" in (self.delivery_address or "").lower() else "DELIVERY")
        address = self.delivery_address or ("Store Pickup" if f_type == "PICKUP" else "Neighborhood Delivery")
        contact = self.customer_contact or "Web Phone"
        pay_mode = self.payment_method or ("Cash on Delivery" if f_type == "DELIVERY" else "Store Cash")
        total_int = int(round(self.total_bill))
        
        item_summary = ", ".join([f"{int(it.quantity) if it.quantity.is_integer() else it.quantity} {it.unit} {it.item_name}" for it in items])
        summary = f"Order for {name}: {item_summary}. Total Rs. {total_int} ({f_type}). Payment: {pay_mode}."
        
        return KiranaCallExtraction(
            customer_name=name,
            customer_contact=contact,
            items_ordered=items,
            total_calculated_bill=float(total_int),
            special_instructions=[f"Fulfillment: {f_type}"],
            fulfillment_type=f_type,
            delivery_address=address,
            payment_method=pay_mode,
            executive_summary=summary
        )

class InteractiveKiranaAgent:
    def __init__(self, api_key: Optional[str] = None, sync_manager: Any = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.sync_manager = sync_manager
        self.primary_model = "gemini-flash-lite-latest"
        self.fallback_model = "gemini-3.5-flash-lite"
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.sessions: Dict[str, KiranaSession] = {}

    def get_or_create_session(self, call_id: str) -> KiranaSession:
        if call_id not in self.sessions:
            self.sessions[call_id] = KiranaSession(call_id, self.sync_manager)
        return self.sessions[call_id]

    def _sanitize_input(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r'<\/?(?:system|instruction|user_utterance|guardrail)[^>]*>', '', text, flags=re.IGNORECASE)
        return cleaned.strip()[:600]

    def _get_catalog_context(self) -> str:
        if self.sync_manager:
            return self.sync_manager.get_catalog_summary_text()
        return "- Atta (Aashirvaad): Rs. 60 per 1 kg\n- Sugar (Cheeni): Rs. 45 per 1 kg\n- Amul Taaza Milk: Rs. 27 per 500 ml\n- Tata Salt: Rs. 28 per 1 kg\n- Maggi: Rs. 14 per 1 packet"

    def _analyze_turn_with_gemini(self, text: str, session: KiranaSession) -> Dict[str, Any]:
        """
        Multilingual (Devanagari + Romanized) Turn Analyzer using Gemini.
        Extracts items, out-of-stock items, completion cues, confirmation cues, name, fulfillment, address, and payment.
        """
        if not self.client:
            return self._analyze_turn_locally(text, session)

        catalog_text = self._get_catalog_context()
        prompt = f"""You are an expert Indian Kirana Store Voice AI order extractor.
Reference Price Catalog:
{catalog_text}

Cart so far has {len(session.cart)} items. Current state is '{session.state}'.
Customer Speech (Hindi/Hinglish/Bhojpuri/English): "{text}"

Extract the customer's intent, items, and contact preferences into strict JSON:
{{
  "items": [
    {{"catalog_item": "Exact catalog item name", "quantity": 1.0, "unit": "kg/packet/litre", "unit_price": 60.0, "subtotal": 60.0}}
  ],
  "out_of_stock": ["item names that customer requested but are not in catalog or out of stock"],
  "is_completion_signal": true/false (true if customer says 'bas itna hi', 'ho gaya', 'nahi bas yahi hai', 'itna bhej do', 'aur kuch nahi', 'बस इतना', 'इतना ही', 'यही है', 'नहीं बस', 'हो गया', 'नहीं'),
  "is_confirmation": true/false (true if customer confirms order or details, e.g. 'haan', 'theek hai', 'book kar do', 'yahi hai', 'हाँ', 'हां', 'ठीक है', 'बुक कर दो', 'भेज दीजिए'),
  "customer_name": "extracted customer name or null",
  "fulfillment_type": "DELIVERY" / "PICKUP" / null (ONLY extract if customer is explicitly choosing delivery or pickup, e.g. 'home delivery chahiye' -> DELIVERY, 'dukan se lenge' -> PICKUP),
  "delivery_address": "extracted delivery address/room/building/locality or null",
  "payment_method": "CASH" / "ONLINE" / null (CASH if cash on delivery, dukan par denge, cash; ONLINE if upi, qr code, online, gpay, phonepe)
}}

Unit Normalization Rules:
- For Amul Taaza Milk (500 ml @ Rs. 27): If customer asked for 1 litre/kilo, quantity = 2.0 packets (subtotal: Rs. 54.0). If 2 litres/kilo, quantity = 4.0 packets (subtotal: Rs. 108.0).
- If customer gives their name (e.g. 'मेरा नाम राज है' / 'Mera naam Raj hai'), extract customer_name = 'Raj'.
- If customer gives delivery address (e.g. 'खटाल वाली बिल्डिंग के पास 201 नंबर रूम'), extract delivery_address.
"""
        for model in [self.primary_model, self.fallback_model]:
            try:
                res = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "temperature": 0.1
                    }
                )
                if res and res.text:
                    parsed = json.loads(res.text.strip())
                    return parsed
            except Exception as e:
                print(f"[Gemini Analyzer Error on {model}] {e}")
                continue

        # Fallback to local dual-script parser
        return self._analyze_turn_locally(text, session)

    def _analyze_turn_locally(self, text: str, session: KiranaSession) -> Dict[str, Any]:
        """Dual-script (Devanagari + Romanized) local fallback parser."""
        t = text.lower()
        items = []
        out_of_stock = []

        catalog = self.sync_manager.get_price_catalog() if self.sync_manager else {}
        entries = catalog.values() if isinstance(catalog, dict) else catalog

        # Keyword mapping for Devanagari and Latin
        item_keywords = {
            "Atta (Aashirvaad)": ["atta", "aata", "aashirvaad", "आटा", "आशीर्वाद"],
            "Sugar (Cheeni)": ["cheeni", "chini", "shakar", "sugar", "चीनी", "शक्कर"],
            "Amul Taaza Milk": ["doodh", "dudh", "milk", "amul", "दूध", "अमुल"],
            "Tata Salt": ["namak", "salt", "tata namak", "नमक", "टाटा नमक"],
            "Maggi 2-Minute Noodles": ["maggi", "noodles", "मैगी", "नूडल्स"],
            "Fortune Sunflower Oil": ["tel", "oil", "sunflower", "refined", "fortune", "तेल", "रिफ़ाइन", "रिफाइन", "फॉर्च्यून"],
            "Basmati Rice": ["chawal", "rice", "basmati", "चावल", "बासमती"],
            "Taj Mahal Tea": ["chai", "tea", "taj mahal", "चाय", "ताज़ महल"],
            "Toor Dal": ["daal", "dal", "toor", "दाल", "तूर"],
            "Surf Excel Detergent": ["surf", "surf excel", "detergent", "सर्फ", "डिटर्जेंट"]
        }

        for entry in entries:
            raw_name = entry.get("raw_name") or entry.get("item_name")
            price = float(entry.get("price", 0.0))
            cat_unit = entry.get("unit", "units")
            kws = item_keywords.get(raw_name, [raw_name.lower()])

            matched = any(kw in t for kw in kws)
            if matched:
                qty_m = re.search(r'(\d+(?:\.\d+)?)\s*(kilo|kg|packet|pkt|litre|l|किलो|लीटर|पैकेट)?', t)
                raw_qty = float(qty_m.group(1)) if qty_m else 1.0
                
                final_qty = raw_qty
                final_sub = price * raw_qty
                unit_desc = cat_unit

                if "500 ml" in cat_unit.lower() and ("kilo" in t or "litre" in t or "किलो" in t or "लीटर" in t):
                    final_qty = raw_qty * 2.0
                    final_sub = final_qty * price
                    unit_desc = "packet"

                items.append({
                    "catalog_item": raw_name,
                    "quantity": final_qty,
                    "unit": unit_desc,
                    "unit_price": price,
                    "subtotal": final_sub
                })

        # Out-of-stock unlisted checks
        unlisted = ["maida", "suji", "rawa", "besan", "paneer", "dahi", "ghee", "मैदा", "सूजी", "बेसन", "पनीर", "दही"]
        for un in unlisted:
            if un in t:
                out_of_stock.append(un.title())

        # Completion signal detection
        completion_cues = [
            "bas itna", "itna hi", "itna bhej", "ho gaya", "aur kuch nahi", "kuch nahi",
            "nahi bas", "total bill", "kitna hua", "book kar", "pura order", "नहीं", "बस इतना",
            "इतना ही", "हो गया", "और कुछ नहीं", "कुछ नहीं", "नहीं बस", "टोटल बिल", "कितना हुआ",
            "बस यही", "यही है"
        ]
        is_comp = any(c in t for c in completion_cues)

        # Confirmation signal detection
        confirm_cues = ["haan", "theek hai", "book kar do", "yahi hai", "हाँ", "हां", "ठीक है", "बुक कर दो", "यही है", "sahi hai"]
        is_conf = any(c in t for c in confirm_cues)

        # Name detection
        name_m = re.search(r'(?:mera naam|naam|मेरा नाम|नाम)\s+([a-zA-Z\u0900-\u097F]+)', t)
        c_name = name_m.group(1).title() if name_m else None

        # Fulfillment detection (explicit only)
        pickup_kws = ["dukan se", "store se", "pickup", "aa kar", "aakar", "le lenge", "le jaunga", "दुकान से", "आकर ले लेंगे", "पिकअप"]
        delivery_kws = ["home delivery", "ghar par", "ghar pe", "delivery chahiye", "डिलीवरी चाहिए", "घर पर"]
        
        f_type = None
        if any(pk in t for pk in pickup_kws):
            f_type = "PICKUP"
        elif any(dk in t for dk in delivery_kws):
            f_type = "DELIVERY"

        # Address detection
        addr_m = re.search(r'([a-zA-Z\u0900-\u097F\s\d]+(?:colony|nagar|gali|vihar|sector|room|building|पास|बिल्डिंग|रूम|कमरा|नंबर)[^,\.\n]*)', t)
        c_addr = addr_m.group(0).strip() if addr_m else None

        # Payment detection
        cash_kws = ["cash", "cod", "rokda", "cash on delivery", "dukan par cash", "नकद", "कैश", "हाथ में"]
        online_kws = ["online", "upi", "gpay", "phonepe", "paytm", "qr", "qr code", "ऑनलाइन", "यूपीआई", "गूगल पे"]
        
        pay_mode = None
        if any(ck in t for ck in cash_kws):
            pay_mode = "CASH"
        elif any(ok in t for ok in online_kws):
            pay_mode = "ONLINE"

        return {
            "items": items,
            "out_of_stock": out_of_stock,
            "is_completion_signal": is_comp,
            "is_confirmation": is_conf,
            "customer_name": c_name,
            "fulfillment_type": f_type,
            "delivery_address": c_addr,
            "payment_method": pay_mode
        }

    async def step(self, call_id: str, utterance: str) -> Tuple[str, bool, Optional[KiranaCallExtraction]]:
        """
        Processes one customer utterance through the state machine.
        Returns: (Radha_reply, is_finalized, final_order_or_none)
        """
        session = self.get_or_create_session(call_id)
        safe_utterance = self._sanitize_input(utterance)
        session.dialog_history.append(f"Customer: {safe_utterance}")

        if not safe_utterance or len(safe_utterance) < 2:
            return "Kahiye ji, aapko kya samaan chahiye?", False, None

        # Analyze turn with Gemini (with dual-script fallback)
        analysis = self._analyze_turn_with_gemini(safe_utterance, session)
        
        # 1. Update Cart with newly detected items
        new_item_descriptions = []
        for it in analysis.get("items", []):
            cat_name = it.get("catalog_item")
            if cat_name:
                k_item = KiranaItem(
                    item_name=cat_name,
                    quantity=float(it.get("quantity", 1.0)),
                    unit=it.get("unit", "units"),
                    unit_price=float(it.get("unit_price", 0.0)),
                    subtotal=float(it.get("subtotal", 0.0))
                )
                session.cart[cat_name] = k_item
                qty_display = int(k_item.quantity) if k_item.quantity.is_integer() else k_item.quantity
                new_item_descriptions.append(f"{qty_display} {k_item.unit} {cat_name}")

        # 2. Update Lead Details if detected in utterance
        if analysis.get("customer_name") and not session.customer_name:
            session.customer_name = str(analysis["customer_name"]).strip().title()

        # ONLY update fulfillment if in COLLECT_FULFILLMENT or explicit customer statement
        if analysis.get("fulfillment_type") and (session.state == "COLLECT_FULFILLMENT" or not session.fulfillment_type):
            session.fulfillment_type = analysis["fulfillment_type"]

        if analysis.get("delivery_address") and not session.delivery_address:
            session.delivery_address = str(analysis["delivery_address"]).strip()

        if analysis.get("payment_method") and not session.payment_method:
            session.payment_method = "Cash on Delivery" if analysis["payment_method"] == "CASH" else "Online UPI / QR"

        is_completion = bool(analysis.get("is_completion_signal"))
        is_confirmation = bool(analysis.get("is_confirmation"))
        out_of_stock = analysis.get("out_of_stock", [])

        # ==========================================================
        # STATE 1: ORDERING (Customer dictating grocery items)
        # ==========================================================
        if session.state == "ORDERING":
            # If customer signaled completion & cart has items -> quote whole rupee bill!
            if (is_completion or is_confirmation) and len(session.cart) > 0:
                session.state = "CONFIRM_ORDER"
                total_int = int(round(session.recalculate_total()))
                reply = f"Aapka kul bill Rs. {total_int} hua hai. Kya aapka poora order yahi hai ya kuch aur jodna hai?"
                session.dialog_history.append(f"Radha: {reply}")
                return reply, False, None

            # Customer is giving items
            oos_text = ""
            if out_of_stock:
                oos_items_str = ", ".join(out_of_stock)
                oos_text = f"Maaf kariyega, {oos_items_str} abhi uplabdh nahi hai. "

            if new_item_descriptions:
                items_str = ", ".join(new_item_descriptions)
                reply = f"{oos_text}Ji, {items_str} note kar liya hai. Aur kuch chahiye ji?"
            elif out_of_stock:
                reply = f"{oos_text}Aapko iske alawa aur kya samaan chahiye ji?"
            else:
                reply = "Ji, maine note kar liya. Aur kya samaan chahiye ji?"

            session.dialog_history.append(f"Radha: {reply}")
            return reply, False, None

        # ==========================================================
        # STATE 2: CONFIRM_ORDER (Verifying bill & completeness)
        # ==========================================================
        elif session.state == "CONFIRM_ORDER":
            # If customer confirms order completeness ("Haan", "Theek hai", "Yahi hai")
            if is_confirmation or is_completion:
                if not session.customer_name:
                    session.state = "COLLECT_NAME"
                    reply = "Bahut badhiya! Kripya apna shubh naam bata dijiye?"
                    session.dialog_history.append(f"Radha: {reply}")
                    return reply, False, None
                else:
                    # Name is known, MANDATORY Question 5: Delivery vs Pickup!
                    session.state = "COLLECT_FULFILLMENT"
                    reply = f"Ji {session.customer_name}! Kya aapko ye order home delivery chahiye, ya aap dukan se aakar le jayenge?"
                    session.dialog_history.append(f"Radha: {reply}")
                    return reply, False, None

            # If customer added more items instead
            if new_item_descriptions:
                session.state = "ORDERING"
                items_str = ", ".join(new_item_descriptions)
                reply = f"Ji, {items_str} bhi jod diya. Aur kuch chahiye ji?"
                session.dialog_history.append(f"Radha: {reply}")
                return reply, False, None

            reply = "Ji, bataiye kya ye aapka poora order hai, ya kuch aur bhi jodna hai?"
            session.dialog_history.append(f"Radha: {reply}")
            return reply, False, None

        # ==========================================================
        # STATE 3: COLLECT_NAME (Capturing customer Name)
        # ==========================================================
        elif session.state == "COLLECT_NAME":
            if session.customer_name:
                # Name is captured! ALWAYS ask Question 5: Delivery vs Pickup!
                session.state = "COLLECT_FULFILLMENT"
                reply = f"Ji {session.customer_name}! Kya aapko ye order home delivery chahiye, ya aap dukan se aakar le jayenge?"
                session.dialog_history.append(f"Radha: {reply}")
                return reply, False, None

            reply = "Kripya apna shubh naam bata dijiye ji?"
            session.dialog_history.append(f"Radha: {reply}")
            return reply, False, None

        # ==========================================================
        # STATE 4: COLLECT_FULFILLMENT (Delivery vs Store Pickup)
        # ==========================================================
        elif session.state == "COLLECT_FULFILLMENT":
            t = safe_utterance.lower()
            pickup_kws = ["dukan", "store", "pickup", "aa kar", "aakar", "le lenge", "le jaunga", "दुकान", "आकर", "पिकअप", "ले लेंगे"]
            delivery_kws = ["delivery", "deliver", "ghar", "bhej", "pahuncha", "डिलीवरी", "डिलीवर", "घर", "भेज"]

            is_pickup = any(kw in t for kw in pickup_kws) or analysis.get("fulfillment_type") == "PICKUP"
            is_delivery = any(kw in t for kw in delivery_kws) or analysis.get("fulfillment_type") == "DELIVERY"

            if is_pickup:
                session.fulfillment_type = "PICKUP"
                session.delivery_address = "Store Pickup"
                session.state = "COLLECT_PAYMENT"
                reply = "Theek hai ji, dukan se pickup note kar liya hai. Aap payment kaise karenge — dukan par cash, ya online UPI se?"
                session.dialog_history.append(f"Radha: {reply}")
                return reply, False, None

            elif is_delivery:
                session.fulfillment_type = "DELIVERY"
                if session.delivery_address and session.delivery_address != "Store Pickup":
                    session.state = "COLLECT_PAYMENT"
                    reply = "Delivery address note ho gaya hai. Aap payment kaise karenge — Cash on delivery, ya online UPI se?"
                    session.dialog_history.append(f"Radha: {reply}")
                    return reply, False, None
                else:
                    session.state = "COLLECT_ADDRESS"
                    reply = "Kripya apna delivery pata, flat number ya room number bata dijiye?"
                    session.dialog_history.append(f"Radha: {reply}")
                    return reply, False, None

            # If customer's response was ambiguous, repeat Question 5 clearly!
            reply = "Bataiye ji, kya aapko ye order home delivery chahiye ya aap dukan se aakar le jayenge?"
            session.dialog_history.append(f"Radha: {reply}")
            return reply, False, None

        # ==========================================================
        # STATE 5: COLLECT_ADDRESS (Delivery address if needed)
        # ==========================================================
        elif session.state == "COLLECT_ADDRESS":
            if session.delivery_address and session.delivery_address != "Store Pickup":
                session.state = "COLLECT_PAYMENT"
                reply = "Pata note kar liya hai. Aap payment kaise karenge — Cash on delivery, ya online UPI se?"
                session.dialog_history.append(f"Radha: {reply}")
                return reply, False, None

            reply = "Kripya apna delivery flat number, room number ya gali ka pata bata dijiye taaki saman pahunchaya ja sake."
            session.dialog_history.append(f"Radha: {reply}")
            return reply, False, None

        # ==========================================================
        # STATE 6: COLLECT_PAYMENT (Cash vs Online UPI)
        # ==========================================================
        elif session.state == "COLLECT_PAYMENT":
            pay_text = safe_utterance.lower()
            if any(kw in pay_text for kw in ["online", "upi", "qr", "gpay", "phonepe", "गूगल", "ऑनलाइन", "यूपीआई"]):
                session.payment_method = "Online UPI / QR"
            else:
                session.payment_method = "Cash on Delivery" if session.fulfillment_type == "DELIVERY" else "Store Cash"

            session.state = "FINALIZED"
            total_int = int(round(session.recalculate_total()))
            name = session.customer_name or "Ji"
            reply = f"Dhanyawaad {name}! Aapka Rs. {total_int} ka order confirm ho gaya hai. Shukriya!"
            session.dialog_history.append(f"Radha: {reply}")
            return reply, True, session.to_extraction()

        # ==========================================================
        # STATE 7: FINALIZED (Order already booked)
        # ==========================================================
        else:
            total_int = int(round(session.recalculate_total()))
            reply = f"Aapka Rs. {total_int} ka order pehle hi confirm ho chuka hai ji. Shukriya!"
            return reply, True, session.to_extraction()

    async def extract_final_order(self, call_id: str, full_dialog: str) -> KiranaCallExtraction:
        """Extracts structured order details for the session."""
        session = self.get_or_create_session(call_id)
        return session.to_extraction()
