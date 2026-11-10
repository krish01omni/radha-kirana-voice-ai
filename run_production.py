import os
import sys
import re
import time
import subprocess
import threading
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv("d:/hack idea/voice_calling_agent/.env")

from generate_qr import generate_counter_standee

def start_server_and_tunnel():
    print("================================================================")
    print("  Starting Radha Voice AI Server + Free Cloudflare Public Tunnel")
    print("================================================================\n")

    # 1. Start FastAPI server via uvicorn in a separate thread
    def run_uvicorn():
        import uvicorn
        uvicorn.run("app:app", host="0.0.0.0", port=8000, log_level="warning")

    server_thread = threading.Thread(target=run_uvicorn, daemon=True)
    server_thread.start()
    print("[1/3] Local FastAPI server running on http://localhost:8000")
    time.sleep(2)

    # 2. Start Cloudflare Tunnel
    cloudflared_path = os.path.abspath("bin/cloudflared.exe")
    if not os.path.exists(cloudflared_path):
        print(f"[Warning] cloudflared.exe not found at {cloudflared_path}. Local only.")
        return

    print("[2/3] Launching Cloudflare Tunnel for 4G/5G mobile data access...")
    cmd = [cloudflared_path, "tunnel", "--url", "http://localhost:8000"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

    public_url = None
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    # Read output to capture the public URL
    start_time = time.time()
    for line in iter(proc.stdout.readline, ""):
        match = url_pattern.search(line)
        if match:
            public_url = match.group(0)
            break
        if time.time() - start_time > 20:
            break

    if public_url:
        print(f"\n================================================================")
        print(f"  [SUCCESS] PUBLIC HTTPS URL FOR MOBILE DATA (4G/5G):")
        print(f"  --> {public_url}")
        print(f"================================================================\n")
        
        # 3. Update the Counter QR Standee with this public URL!
        print("[3/3] Generating updated Counter QR Standee with Public HTTPS URL...")
        standee_file = generate_counter_standee(target_url=public_url)
        print(f"[Done] Standee ready: {standee_file}")
        print(f"\nNow customers on ANY mobile data (Jio / Airtel) can scan and call!")
    else:
        print("[Notice] Could not capture Cloudflare URL. Using local LAN IP.")
        generate_counter_standee()

    # Keep running
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    start_server_and_tunnel()
