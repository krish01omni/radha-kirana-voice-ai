import os
import sys
import json
from dotenv import load_dotenv
from google import genai

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("d:/hack idea/voice_calling_agent/.env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

catalog_summary = """- Atta (Aashirvaad): Rs. 60 per 1 kg (In Stock)
- Sugar (Cheeni): Rs. 45 per 1 kg (In Stock)
- Amul Taaza Milk: Rs. 27 per 500 ml (In Stock)
- Tata Salt: Rs. 28 per 1 kg (In Stock)
- Maggi 2-Minute Noodles: Rs. 14 per 1 packet (In Stock)
- Fortune Sunflower Oil: Rs. 145 per 1 litre (In Stock)
- Basmati Rice: Rs. 90 per 1 kg (In Stock)
- Taj Mahal Tea: Rs. 110 per 250 g (In Stock)
- Toor Dal: Rs. 160 per 1 kg (In Stock)
- Surf Excel Detergent: Rs. 135 per 1 kg (In Stock)"""

test_utterances = [
    "बस इतना ही चाहिए।",
    "नहीं, बस यही है।",
    "मेरा नाम राज है। खटाल वाली बिल्डिंग के पास दो सौ एक नंबर रूम है।"
]

for utt in test_utterances:
    prompt = f"""You are a Kirana Store AI Order Extractor.
Catalog:
{catalog_summary}

Customer Speech: "{utt}"

Output strict JSON:
{{
  "items": [],
  "out_of_stock": [],
  "is_completion_signal": true/false (true if customer says 'bas itna hi', 'ho gaya', 'nahi bas yahi hai', 'itna hi bhej do', 'aur kuch nahi'),
  "is_confirmation": true/false (true if customer confirms order or says 'haan', 'theek hai', 'book kar do', 'yahi hai'),
  "customer_name": "extracted name or null",
  "delivery_address": "extracted delivery address or null"
}}
"""
    res = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
        config={"response_mime_type": "application/json", "temperature": 0.1}
    )
    print(f"\n--- Utterance: {utt} ---")
    print(res.text)
