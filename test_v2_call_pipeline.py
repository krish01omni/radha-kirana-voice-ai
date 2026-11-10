import asyncio
import os
import sys
import openpyxl
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv("d:/hack idea/voice_calling_agent/.env")

from sheets_sync import SheetsSyncManager
from agent_core import InteractiveKiranaAgent

async def test_full_conversational_state_machine():
    print("\n=======================================================")
    print("  SIMULATION TEST: Radha V2 Conversational State Machine")
    print("=======================================================\n")

    sync_mgr = SheetsSyncManager(excel_path="data/kirana_store.xlsx")
    agent = InteractiveKiranaAgent(sync_manager=sync_mgr)
    call_id = "CALL_SIM_VERIFY_999"

    session = agent.get_or_create_session(call_id)

    # -----------------------------------------------------------
    # TURN 1: Customer orders items
    # -----------------------------------------------------------
    t1_text = "mujhe 1 kilo atta aur 2 packet doodh chahiye"
    print(f"\n[TURN 1] Customer: \"{t1_text}\"")
    r1, fin1, ext1 = await agent.step(call_id, t1_text)
    print(f"[TURN 1] Radha ({session.state}): \"{r1}\"")
    
    assert session.state == "ORDERING", f"Expected state ORDERING, got {session.state}"
    assert not fin1, "Order should NOT be finalized on first items"
    assert "Rs." not in r1 or "kul bill" not in r1.lower(), "Radha should NOT quote grand total bill yet"
    assert "address" not in r1.lower(), "Radha should NOT ask for address yet"
    print("✓ Turn 1 Passed: Items added to cart, no premature total or address prompt.")

    # -----------------------------------------------------------
    # TURN 2: Customer orders another item
    # -----------------------------------------------------------
    t2_text = "2 kilo cheeni bhi jod do"
    print(f"\n[TURN 2] Customer: \"{t2_text}\"")
    r2, fin2, ext2 = await agent.step(call_id, t2_text)
    print(f"[TURN 2] Radha ({session.state}): \"{r2}\"")
    
    assert session.state == "ORDERING", f"Expected state ORDERING, got {session.state}"
    assert len(session.cart) >= 2, f"Expected at least 2 items in cart, got {len(session.cart)}"
    print("✓ Turn 2 Passed: Additional item added, state remains ORDERING.")

    # -----------------------------------------------------------
    # TURN 3: Customer signals completion
    # -----------------------------------------------------------
    t3_text = "Nahi, bas itna hi bhejwa dijiye. Total bill kitna hua?"
    print(f"\n[TURN 3] Customer: \"{t3_text}\"")
    r3, fin3, ext3 = await agent.step(call_id, t3_text)
    print(f"[TURN 3] Radha ({session.state}): \"{r3}\"")
    
    assert session.state == "CONFIRM_ORDER", f"Expected state CONFIRM_ORDER, got {session.state}"
    assert "Rs." in r3 or "bill" in r3.lower(), "Radha MUST quote the total bill now"
    assert "poora order" in r3.lower() or "pura order" in r3.lower(), "Radha MUST ask if this is the full order"
    print("✓ Turn 3 Passed: Order completion recognized, total bill quoted, asking for confirmation.")

    # -----------------------------------------------------------
    # TURN 4: Customer confirms order is complete
    # -----------------------------------------------------------
    t4_text = "Haan, yahi poora order hai, book kar do."
    print(f"\n[TURN 4] Customer: \"{t4_text}\"")
    r4, fin4, ext4 = await agent.step(call_id, t4_text)
    print(f"[TURN 4] Radha ({session.state}): \"{r4}\"")
    
    assert session.state == "COLLECT_LEAD", f"Expected state COLLECT_LEAD, got {session.state}"
    assert "naam" in r4.lower() and "address" in r4.lower(), "Radha MUST ask for customer name and address"
    print("✓ Turn 4 Passed: Customer confirmed order, Radha asks for Name & Address.")

    # -----------------------------------------------------------
    # TURN 5: Customer provides name & address
    # -----------------------------------------------------------
    t5_text = "Mera naam Raj hai. Hum Raj Colony ke room number 302 me rehte hain."
    print(f"\n[TURN 5] Customer: \"{t5_text}\"")
    r5, fin5, ext5 = await agent.step(call_id, t5_text)
    print(f"[TURN 5] Radha ({session.state}): \"{r5}\"")
    
    assert session.state == "FINALIZED", f"Expected state FINALIZED, got {session.state}"
    assert fin5 is True, "Turn 5 must return is_finalized=True"
    assert ext5 is not None, "Turn 5 must return final_extraction"
    assert ext5.total_calculated_bill > 0, f"Expected total bill > 0, got {ext5.total_calculated_bill}"
    assert "Raj" in ext5.customer_name or "Raj" in session.customer_name, "Customer name must be extracted"
    print(f"✓ Turn 5 Passed: Customer details captured. Total: Rs. {ext5.total_calculated_bill}, Name: {ext5.customer_name}, Address: {ext5.delivery_address}")

    # -----------------------------------------------------------
    # LOG TO EXCEL & VERIFY
    # -----------------------------------------------------------
    row = sync_mgr.log_customer_order(call_id, ext5, "recordings/sim_test.wav")
    print(f"\n[Excel Logged]: {row}")
    assert row["Total Bill (₹)"] > 0, "Excel row total bill must be > 0"
    assert row["Customer Name"] != "Customer", "Customer name should not be generic 'Customer'"
    assert "Raj" in row["Customer Name"], "Customer name must contain 'Raj'"
    print("✓ Excel verification passed cleanly!")

if __name__ == "__main__":
    asyncio.run(test_full_conversational_state_machine())
