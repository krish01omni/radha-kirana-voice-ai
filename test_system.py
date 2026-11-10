import os
import asyncio
from sheets_sync import SheetsSyncManager
from tts_engine import LocalEdgeTTS
from agent_core import InteractiveKiranaAgent, KiranaItem, KiranaCallExtraction

async def run_tests():
    print("\n--- 1. Testing SheetsSyncManager & Read-Only Catalog ---")
    sync = SheetsSyncManager("data/kirana_store.xlsx")
    catalog = sync.get_price_catalog()
    print(f"Catalog loaded successfully with {len(catalog)} items.")
    for item_key in ["atta (aashirvaad)", "sugar (cheeni)", "amul taaza milk"]:
        if item_key in catalog:
            item = catalog[item_key]
            print(f"  * {item['raw_name']}: Rs. {item['price']} per {item['unit']}")

    print("\n--- 2. Testing Edge-TTS Speech Synthesis ---")
    tts = LocalEdgeTTS("hi-IN-SwaraNeural")
    test_phrase = "Namaste! Shree Ganesh Kirana Store mein aapka swagat hai."
    audio_bytes = await tts.synthesize_to_bytes(test_phrase)
    print(f"Audio synthesized successfully! Byte size: {len(audio_bytes)} bytes.")
    assert len(audio_bytes) > 1000, "Audio output too small"

    print("\n--- 3. Testing Order Logging to Excel (Option A) ---")
    dummy_order = KiranaCallExtraction(
        customer_name="Ramesh Kumar",
        customer_contact="9876543210",
        items_ordered=[
            KiranaItem(item_name="Atta (Aashirvaad)", quantity=5, unit="kg", unit_price=60, subtotal=300),
            KiranaItem(item_name="Sugar (Cheeni)", quantity=2, unit="kg", unit_price=45, subtotal=90)
        ],
        total_calculated_bill=390.0,
        special_instructions=["Deliver before 12 PM", "Call before coming"],
        delivery_address="Flat 302, Shanti Heights",
        payment_method="Cash on Delivery",
        executive_summary="Ramesh ordered 5kg atta and 2kg sugar for Flat 302."
    )
    logged = sync.log_customer_order("CALL_TEST_001", dummy_order, "recordings/test.wav")
    print(f"Order logged: Total Rs. {logged['Total Bill (₹)']} for {logged['Customer Name']}")
    assert logged["Total Bill (₹)"] == 390.0, "Total calculation mismatch"

    print("\n==========================================")
    print("  ALL CORE SYSTEM TESTS PASSED SUCCESSFULLY! ")
    print("==========================================\n")

if __name__ == "__main__":
    asyncio.run(run_tests())
