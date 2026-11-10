import asyncio
import os
import sys
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("d:/hack idea/voice_calling_agent/.env")

from sheets_sync import SheetsSyncManager
from agent_core import InteractiveKiranaAgent

async def run_tests():
    print("=================================================================")
    print("  RUNNING COMPREHENSIVE RADHA V3.2 FLOW & ACCURACY AUDIT")
    print("=================================================================")
    
    sync = SheetsSyncManager("data/kirana_store.xlsx")
    agent = InteractiveKiranaAgent(sync_manager=sync)

    # -------------------------------------------------------------
    # TEST 1: Standard Home Delivery + Cash Flow
    # -------------------------------------------------------------
    print("\n--- TEST 1: Full Home Delivery + COD Flow ---")
    call_1 = "CALL_TEST_HOME_DELIVERY"
    
    # 1. Order Items
    reply, fin, ext = await agent.step(call_1, "Mujhe do packet maggi aur ek packet namak chahiye")
    print(f"User: 'Mujhe do packet maggi aur ek packet namak chahiye'")
    print(f"Radha: {reply}")
    assert not fin
    assert "maggi" in reply.lower() or "namak" in reply.lower() or "note" in reply.lower()

    # 2. Completion cue
    reply, fin, ext = await agent.step(call_1, "Bas itna hi")
    print(f"User: 'Bas itna hi'")
    print(f"Radha: {reply}")
    assert not fin
    assert ".0" not in reply, f"Decimal found in reply: {reply}"
    assert "Rs. 56" in reply, f"Expected Rs. 56, got: {reply}"

    # 3. Confirm bill
    reply, fin, ext = await agent.step(call_1, "Haan theek hai")
    print(f"User: 'Haan theek hai'")
    print(f"Radha: {reply}")
    assert "naam" in reply.lower()

    # 4. Give Name
    reply, fin, ext = await agent.step(call_1, "Mera naam Raj hai")
    print(f"User: 'Mera naam Raj hai'")
    print(f"Radha: {reply}")
    assert "delivery" in reply.lower() and "dukan" in reply.lower()

    # 5. Fulfillment preference
    reply, fin, ext = await agent.step(call_1, "Ghar par delivery chahiye")
    print(f"User: 'Ghar par delivery chahiye'")
    print(f"Radha: {reply}")
    assert "pata" in reply.lower() or "address" in reply.lower() or "flat" in reply.lower()

    # 6. Delivery address
    reply, fin, ext = await agent.step(call_1, "Flat 204 Green Valley building")
    print(f"User: 'Flat 204 Green Valley building'")
    print(f"Radha: {reply}")
    assert "payment" in reply.lower() or "cash" in reply.lower() or "upi" in reply.lower()

    # 7. Payment method
    reply, fin, ext = await agent.step(call_1, "Cash on delivery denge")
    print(f"User: 'Cash on delivery denge'")
    print(f"Radha: {reply}")
    assert fin is True
    assert ext is not None
    assert ".0" not in reply
    assert "30 minute" not in reply
    assert "Rs. 56" in reply

    # -------------------------------------------------------------
    # TEST 2: Store Pickup + Online UPI Flow (Skips Address!)
    # -------------------------------------------------------------
    print("\n--- TEST 2: Store Pickup + Online UPI Flow ---")
    call_2 = "CALL_TEST_STORE_PICKUP"
    
    reply, fin, ext = await agent.step(call_2, "2 kilo aata aur 1 kilo cheeni")
    print(f"User: '2 kilo aata aur 1 kilo cheeni'")
    print(f"Radha: {reply}")

    reply, fin, ext = await agent.step(call_2, "Bas itna hi samaan chahiye")
    print(f"User: 'Bas itna hi samaan chahiye'")
    print(f"Radha: {reply}")
    assert "Rs. 165" in reply
    assert ".0" not in reply

    reply, fin, ext = await agent.step(call_2, "Haan book kar dijiye")
    print(f"User: 'Haan book kar dijiye'")
    print(f"Radha: {reply}")
    assert "naam" in reply.lower()

    reply, fin, ext = await agent.step(call_2, "Mera naam Amit Sharma hai")
    print(f"User: 'Mera naam Amit Sharma hai'")
    print(f"Radha: {reply}")
    assert "delivery" in reply.lower() and "dukan" in reply.lower()

    # Choose Store Pickup
    reply, fin, ext = await agent.step(call_2, "Dukan se aakar le lenge")
    print(f"User: 'Dukan se aakar le lenge'")
    print(f"Radha: {reply}")
    # MUST SKIP ADDRESS and ask for payment!
    assert "pata" not in reply.lower()
    assert "payment" in reply.lower() or "cash" in reply.lower() or "upi" in reply.lower()

    # Pay online
    reply, fin, ext = await agent.step(call_2, "Online UPI se pay karenge")
    print(f"User: 'Online UPI se pay karenge'")
    print(f"Radha: {reply}")
    assert fin is True
    assert ext is not None
    assert ".0" not in reply
    assert "Rs. 165" in reply

    # -------------------------------------------------------------
    # TEST 3: Out-of-Stock Item Check
    # -------------------------------------------------------------
    print("\n--- TEST 3: Out-of-Stock Item Handling ---")
    call_3 = "CALL_TEST_OOS"
    reply, fin, ext = await agent.step(call_3, "Mujhe 2 kilo maida aur 1 packet tata salt chahiye")
    print(f"User: 'Mujhe 2 kilo maida aur 1 packet tata salt chahiye'")
    print(f"Radha: {reply}")
    assert "maida" in reply.lower()
    assert "uplabdh nahi" in reply.lower() or "not in stock" in reply.lower() or "maaf" in reply.lower()

    # -------------------------------------------------------------
    # TEST 4: Excel Logging Integrity Check
    # -------------------------------------------------------------
    print("\n--- TEST 4: Excel Sheet Logging Verification ---")
    row = sync.log_customer_order(call_1, ext)
    print(f"Logged Row Total: {row['Total Bill (₹)']} (Type: {type(row['Total Bill (₹)'])})")
    assert isinstance(row["Total Bill (₹)"], int)
    assert ".0" not in str(row["Total Bill (₹)"])
    print(f"Ordered Items String: {row['Ordered Items & Rates']}")
    assert ".0" not in row["Ordered Items & Rates"]

    print("\n=================================================================")
    print("  ALL 4 TEST SUITES PASSED WITH 100% SUCCESS!")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
