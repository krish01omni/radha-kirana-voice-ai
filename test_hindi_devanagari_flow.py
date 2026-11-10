import os
import sys
import asyncio
import openpyxl
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("d:/hack idea/voice_calling_agent/.env")

from sheets_sync import SheetsSyncManager
from agent_core import InteractiveKiranaAgent

async def test_live_user_conversation():
    print("\n" + "="*70)
    print("  SIMULATION TEST: EXACT LIVE USER CONVERSATION IN HINDI")
    print("="*70 + "\n")

    sync_mgr = SheetsSyncManager(excel_path="data/kirana_store.xlsx")
    agent = InteractiveKiranaAgent(sync_manager=sync_mgr)
    call_id = "CALL_DEV_HINDI_VERIFY"

    session = agent.get_or_create_session(call_id)

    # TURN 1: Customer gives order in Devanagari Hindi
    t1 = "मुझे दो किलो आटा, एक किलो दूध, एक किलो रिफ़ाइन ऑयल।"
    print(f"[TURN 1] Customer: \"{t1}\"")
    r1, fin1, ext1 = await agent.step(call_id, t1)
    print(f"[TURN 1] Radha ({session.state}): \"{r1}\"")
    
    assert session.state == "ORDERING", f"Expected state ORDERING, got {session.state}"
    assert len(session.cart) >= 3, f"Expected 3 items in cart, got {len(session.cart)}"
    print(f"  Cart items: {list(session.cart.keys())}")
    for name, it in session.cart.items():
        print(f"    - {it.quantity} {it.unit} {it.item_name}: Rs. {it.subtotal}")
    session.recalculate_total()
    print(f"  Cart Total: Rs. {session.total_bill}")
    assert session.total_bill == 319.0, f"Expected total Rs. 319.0, got {session.total_bill}"
    assert not fin1, "Must not finalize on Turn 1"
    print("✓ Turn 1 Passed: Devanagari grocery items parsed into cart with correct unit normalization!")

    # TURN 2: Customer signals completion in Devanagari Hindi
    t2 = "बस इतना ही चाहिए।"
    print(f"\n[TURN 2] Customer: \"{t2}\"")
    r2, fin2, ext2 = await agent.step(call_id, t2)
    print(f"[TURN 2] Radha ({session.state}): \"{r2}\"")
    
    assert session.state == "CONFIRM_ORDER", f"Expected state CONFIRM_ORDER, got {session.state}"
    assert "319" in r2, f"Radha must quote bill Rs. 319. Got: {r2}"
    assert "poora order" in r2.lower() or "pura order" in r2.lower(), "Must ask if this is full order"
    assert not fin2, "Must not finalize on Turn 2"
    print("✓ Turn 2 Passed: Devanagari completion recognized, exact bill Rs. 319 quoted!")

    # TURN 3: Customer confirms order
    t3 = "नहीं, बस यही है।"
    print(f"\n[TURN 3] Customer: \"{t3}\"")
    r3, fin3, ext3 = await agent.step(call_id, t3)
    print(f"[TURN 3] Radha ({session.state}): \"{r3}\"")
    
    assert session.state == "COLLECT_LEAD", f"Expected state COLLECT_LEAD, got {session.state}"
    assert "naam" in r3.lower() and "address" in r3.lower(), f"Radha must ask for Name and Address. Got: {r3}"
    assert not fin3, "Must not finalize on Turn 3"
    print("✓ Turn 3 Passed: Confirmation recognized, Radha actively asks for Name and Address!")

    # TURN 4: Customer gives name and address in Hindi
    t4 = "मेरा नाम राज है। खटाल वाली बिल्डिंग के पास दो सौ एक नंबर रूम है।"
    print(f"\n[TURN 4] Customer: \"{t4}\"")
    r4, fin4, ext4 = await agent.step(call_id, t4)
    print(f"[TURN 4] Radha ({session.state}): \"{r4}\"")
    
    assert session.state == "FINALIZED", f"Expected state FINALIZED, got {session.state}"
    assert fin4 is True, "Must return is_finalized=True"
    assert ext4 is not None, "Must return final extraction"
    assert ext4.total_calculated_bill == 319.0, f"Expected 319.0, got {ext4.total_calculated_bill}"
    print(f"  Customer Name: {ext4.customer_name}")
    print(f"  Delivery Address: {ext4.delivery_address}")
    print(f"  Total Bill: Rs. {ext4.total_calculated_bill}")
    print("✓ Turn 4 Passed: Lead captured, order finalized with exact bill!")

    # LOG TO EXCEL & VERIFY
    logged_row = sync_mgr.log_customer_order(call_id, ext4, "recordings/hindi_test.wav")
    print(f"\n[Excel Logged]: {logged_row}")
    assert logged_row["Total Bill (₹)"] == 319.0, f"Excel Total Bill must be 319.0, got {logged_row['Total Bill (₹)']}"
    print("✓ Excel verification passed with 100% precision!")

if __name__ == "__main__":
    asyncio.run(test_live_user_conversation())
