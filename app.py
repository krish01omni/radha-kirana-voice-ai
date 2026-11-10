import os
import io
import sys
import json
import base64
import asyncio
import datetime
from typing import Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Safe UTF-8 reconfiguration for Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def safe_print(*args, **kwargs):
    """Crash-proof print for Windows terminals to eliminate charmap UnicodeEncodeErrors."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            safe_args = [str(a).encode(encoding, errors="replace").decode(encoding) for a in args]
            print(*safe_args, **kwargs)
        except Exception:
            pass
    except Exception:
        pass

load_dotenv("d:/hack idea/voice_calling_agent/.env")

from sheets_sync import SheetsSyncManager
from gnani_engine import UnifiedAudioEngine
from agent_core import InteractiveKiranaAgent, KiranaCallExtraction

app = FastAPI(title="Radha V3 - Kirana AI Voice Counter", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.abspath("d:/hack idea/voice_calling_agent/static")
RECORDINGS_DIR = os.path.abspath("d:/hack idea/voice_calling_agent/recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Singletons
sync_manager = SheetsSyncManager(excel_path="data/kirana_store.xlsx")
audio_engine = UnifiedAudioEngine(mode=os.getenv("AUDIO_MODE", "GNANI"))
kirana_agent = InteractiveKiranaAgent(sync_manager=sync_manager)

# Concurrency & DoS Guards
MAX_CONCURRENT_CALLS = 15
active_connections_lock = asyncio.Lock()
active_calls_count = 0
MAX_TURN_PCM_BYTES = 4 * 1024 * 1024  # Max 4MB PCM per turn (~2 minutes)

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/catalog")
async def get_catalog():
    return JSONResponse(content=sync_manager.get_price_catalog())

@app.get("/api/standee")
async def get_standee():
    from generate_qr import generate_counter_standee
    standee_path = generate_counter_standee()
    return FileResponse(standee_path)

@app.websocket("/ws/call")
async def websocket_call_endpoint(websocket: WebSocket):
    global active_calls_count
    
    async with active_connections_lock:
        if active_calls_count >= MAX_CONCURRENT_CALLS:
            await websocket.close(code=1008, reason="Server busy. Please try calling again in a moment.")
            return
        active_calls_count += 1

    await websocket.accept()
    clean_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    call_id = f"CALL_{clean_timestamp}"
    safe_print(f"\n[Call Connected] New caller: {call_id} (Active: {active_calls_count})")

    session = kirana_agent.get_or_create_session(call_id)
    full_call_pcm = bytearray()
    call_wav_path = os.path.join(RECORDINGS_DIR, f"{call_id}.wav")
    order_logged = False

    # 1. Send Radha's Welcome Greeting Immediately
    greeting_text = "Namaste! Shree Ganesh Kirana Store mein aapka swagat hai. Main Radha bol rahi hoon. Kahiye, aapko kya samaan chahiye?"
    try:
        greeting_audio = await audio_engine.synthesize_speech(greeting_text)
        greeting_b64 = base64.b64encode(greeting_audio).decode("utf-8")
        greeting_mime = "audio/wav" if greeting_audio.startswith(b"RIFF") else "audio/mp3"
        await websocket.send_json({
            "type": "greeting",
            "text": greeting_text,
            "audio_base64": greeting_b64,
            "audio_mime": greeting_mime
        })
        session.dialog_history.append(f"Radha: {greeting_text}")
    except Exception as e:
        safe_print(f"[Greeting Audio Error] {e}")

    try:
        while True:
            message = await websocket.receive()
            
            # Client text control message
            if "text" in message:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "hangup":
                        safe_print(f"[{call_id}] Client initiated hangup.")
                        break
                except Exception:
                    pass

            # Binary raw 16kHz PCM audio turn from VAD
            elif "bytes" in message:
                pcm_chunk = message["bytes"]
                if len(pcm_chunk) > MAX_TURN_PCM_BYTES:
                    safe_print(f"[{call_id} Warning] Oversized turn dropped.")
                    continue

                full_call_pcm.extend(pcm_chunk)

                # Transcribe pure PCM directly in memory (Gnani prisma-v3.0 or Faster-Whisper small fallback)
                user_text = audio_engine.transcribe_pcm(pcm_chunk)
                
                # Check for valid speech (filtered against silence and hallucinations)
                if user_text and len(user_text.strip()) >= 2:
                    safe_print(f"[{call_id}] Customer: \"{user_text}\"")
                    await websocket.send_json({
                        "type": "user_transcript",
                        "text": user_text
                    })

                    # 2. Process turn through state machine
                    reply_text, is_finalized, final_extraction = await kirana_agent.step(call_id, user_text)
                    safe_print(f"[{call_id}] Radha ({session.state}): \"{reply_text}\"")

                    # 3. Synthesize speech and stream audio back to customer
                    reply_audio = await audio_engine.synthesize_speech(reply_text)
                    reply_b64 = base64.b64encode(reply_audio).decode("utf-8")
                    reply_mime = "audio/wav" if reply_audio.startswith(b"RIFF") else "audio/mp3"
                    await websocket.send_json({
                        "type": "agent_reply",
                        "text": reply_text,
                        "audio_base64": reply_b64,
                        "audio_mime": reply_mime,
                        "state": session.state,
                        "cart_count": len(session.cart),
                        "auto_end_call": is_finalized
                    })

                    # 4. If order just reached FINALIZED, emit receipt and write to Excel immediately!
                    if is_finalized and final_extraction and not order_logged:
                        logged_row = sync_manager.log_customer_order(call_id, final_extraction, call_wav_path)
                        order_logged = True
                        safe_print(f"[{call_id}] Confirmed Order logged: Rs. {logged_row.get('Total Bill (₹)')} | {logged_row.get('Customer Name')} | {logged_row.get('Delivery Address')}")
                        
                        await websocket.send_json({
                            "type": "order_receipt",
                            "order": {
                                "call_id": call_id,
                                "customer_name": logged_row["Customer Name"],
                                "total_bill": int(round(logged_row["Total Bill (₹)"])),
                                "delivery_address": logged_row["Delivery Address"],
                                "items_ordered": [
                                    {
                                        "item_name": item.item_name,
                                        "quantity": int(item.quantity) if item.quantity.is_integer() else item.quantity,
                                        "unit": item.unit,
                                        "subtotal": int(round(item.subtotal))
                                    }
                                    for item in final_extraction.items_ordered
                                ]
                            }
                        })

    except WebSocketDisconnect:
        safe_print(f"[{call_id}] Customer disconnected.")
    except Exception as e:
        safe_print(f"[{call_id} Error] {e}")

    finally:
        async with active_connections_lock:
            active_calls_count = max(0, active_calls_count - 1)

        # 1. Save master call recording WAV if audio was received
        if len(full_call_pcm) > 3200:
            audio_engine.local_stt.save_wav(bytes(full_call_pcm), call_wav_path)
            safe_print(f"[{call_id}] Saved clean audio recording: {call_wav_path}")

        # 2. If call ended before finalization, but customer had ordered items, save partial order
        if not order_logged and session.cart:
            final_extraction = session.to_extraction()
            logged_row = sync_manager.log_customer_order(call_id, final_extraction, call_wav_path)
            safe_print(f"[{call_id}] Preserved partial order in Excel: Rs. {logged_row.get('Total Bill (₹)')} | {logged_row.get('Customer Name')}")
            try:
                await websocket.send_json({
                    "type": "order_receipt",
                    "order": {
                        "call_id": call_id,
                        "customer_name": logged_row["Customer Name"],
                        "total_bill": logged_row["Total Bill (₹)"],
                        "delivery_address": logged_row["Delivery Address"],
                        "items_ordered": [
                            {
                                "item_name": item.item_name,
                                "quantity": item.quantity,
                                "unit": item.unit,
                                "subtotal": item.subtotal
                            }
                            for item in final_extraction.items_ordered
                        ]
                    }
                })
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    safe_print(f"\n=======================================================")
    safe_print(f"  Radha V3 - Enterprise Kirana Voice AI Server")
    safe_print(f"  Running on: http://{host}:{port}")
    safe_print(f"=======================================================\n")
    uvicorn.run("app:app", host=host, port=port, reload=False)
