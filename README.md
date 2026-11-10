# Radha (राधा) - Enterprise Kirana Voice AI Calling Counter 🛒🎙️

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![WebRTC / WebSocket](https://img.shields.io/badge/Audio-16kHz%20PCM%20WebSocket-orange.svg)](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
[![Gnani.ai](https://img.shields.io/badge/STT%2FTTS-Gnani.ai%20Indic-purple.svg)](https://vachana.ai/)
[![Google Gemini](https://img.shields.io/badge/LLM-Gemini%20Flash%20Lite-4285F4.svg?logo=google)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Radha** is a production-grade, zero-hardware Indian Kirana Voice AI Assistant designed for retail grocery stores, mom-and-pop shops, and neighborhood markets. 

Customers scan a physical QR code standee on the store counter using any standard smartphone camera (no mobile app installation required), launching a mobile browser phone that allows them to speak their grocery order in natural **Hindi, Hinglish, or regional dialects**. Radha listens, acknowledges items in real-time, calculates whole-rupee bills, verifies order completeness, inquires whether the customer wants home delivery or store pickup, collects contact details, and logs confirmed orders directly into the shop owner's Excel spreadsheet and Google Sheets.

---

## Key Capabilities & Engineering Highlights

### 1. Zero-Hardware Scan-to-Call Counter Standee
* Store owners do not need expensive kiosks, touchscreens, or dedicated tablets.
* A high-resolution, printable counter standee (`static/kirana_qr_standee.png`) is placed on the front desk.
* Customers point their phone camera at the QR code, instantly opening the mobile audio dialer in Safari or Chrome over standard 4G/5G mobile data or Wi-Fi.

### 2. Machine Noise & Counter Rumbling Rejection Engine
Kirana shops and street counters frequently have loud background noise—grinders, mixer machines, refrigerator compressors, fan drone, and traffic horns. Radha incorporates a **3-stage Web Audio Biquad Hardware Filter** combined with **Adaptive Noise Floor Tracking**:
* **140 Hz High-Pass Filter**: Completely eliminates low-frequency electrical hum (50Hz/60Hz), refrigeration compressors, and fan rumbling.
* **3600 Hz Low-Pass Filter**: Strips out high-frequency motor whine, inverter static, and metallic clatter.
* **1500 Hz Vocal Formant Peaking Filter (+3.5 dB)**: Amplifies human voice frequencies directly into the microphone.
* **Adaptive Noise Floor VAD**: Dynamically measures ambient noise ($\text{Threshold} = \max(0.026, \text{NoiseFloor} \times 2.3)$), preventing constant machinery hum from triggering false speech detections.
* **Barge-in Protection**: Prevents random noise spikes from interrupting Radha mid-sentence.

### 3. Strict 7-Stage Conversational State Machine
Radha enforces a deterministic, loop-free order workflow:
1. **Initial Greeting**: Warm retail welcome (*"Namaste! Radha Kirana Store mein aapka swagat hai. Kahiye, aaj kya samaan chahiye?"*).
2. **Item Acknowledgment & Out-of-Stock Filter**: Adds valid items to cart; politely informs customers if an unlisted item (e.g., *Maida*, *Besan*) is unavailable.
3. **Bill Confirmation (Zero Decimals)**: When the customer signals completion (*"बस इतना ही"*, *"हो गया"*), quotes the grand total in whole rupees (e.g., `₹56`, `₹319`, never `₹56.0`).
4. **Customer Name Collection**: Captures customer name (*"Kripya apna shubh naam bata dijiye?"*). Bypasses automatically if already stated.
5. **Mandatory Delivery vs. Store Pickup**: Removes arbitrary delivery time assumptions. Asks:
   > *"क्या आपको यह ऑर्डर होम डिलीवरी चाहिए, या आप दुकान से आकर ले जाएंगे?"*
6. **Conditional Address Capture**: If **Home Delivery** is chosen, captures flat/room/building address. If **Store Pickup** is chosen, skips address collection entirely.
7. **Payment Mode Inquiry**: Clarifies Cash (Cash on Delivery / counter cash) vs Online UPI/QR code payment.
8. **Automated Call Termination**: Immediately after Radha plays the closing confirmation (*"Dhanyawaad [Name] ji! Aapka ₹[Total] ka order confirm ho gaya hai. Shukriya!"*), the call cleanly and automatically disconnects.

### 4. Shopkeeper-Controlled Two-Tab Excel Management
* **`Price_Catalog` Tab**: Read-only for AI. The store owner sets prices and stock status. If the owner updates Atta from ₹60 to ₹65, Radha immediately quotes ₹65 on the very next phone call.
* **`Orders_Log` Tab**: Append-only log recording timestamp, customer name, phone/call ID, itemized rates, whole-rupee total bill, delivery address/pickup status, payment method, and audio recording link.
* **Formula Injection Guard (CWE-1236)**: Sanitizes user inputs to prevent malicious `=CMD|' /C ...` formula injection attacks.

### 5. Dual-Mode Speech Pipeline
* **`GNANI` Mode (Production)**: Uses Gnani.ai's `prisma-v3.0` Indic speech-to-text API and `timbre-v2.5` (`Nalini`) natural Indic text-to-speech.
* **`DEV` Mode (100% Free / Zero API Cost)**: Operates locally using CUDA-accelerated Faster-Whisper (`small`) and Microsoft Edge Neural TTS (`hi-IN-SwaraNeural`).

---

## Project Structure

```
voice_calling_agent/
├── .env.example              # Safe environment variable configuration template
├── .gitignore                # Production ignore rules (blocks credentials and recordings)
├── requirements.txt          # Python dependencies
├── LICENSE                   # MIT Open Source License
├── README.md                 # System documentation & setup guide
├── app.py                    # FastAPI server & WebSocket 16kHz PCM streaming hub
├── agent_core.py             # 7-stage state machine & Google Gemini intent extractor
├── sheets_sync.py            # Thread-safe Excel (openpyxl) & Google Sheets sync engine
├── gnani_engine.py           # Unified Indic audio driver (Gnani.ai + Edge/Whisper fallback)
├── stt_engine.py             # Local CUDA Faster-Whisper transcription fallback
├── tts_engine.py             # Local Microsoft Edge Neural TTS fallback
├── generate_qr.py            # Retail QR Code Counter Standee generator
├── test_all_flows.py         # Full test suite verifying delivery, pickup & math flows
├── static/
│   ├── index.html            # Mobile web dialer interface
│   ├── app.js                # Web Audio Biquad filters, adaptive VAD & receipt view
│   ├── style.css             # Responsive retail mobile theme
│   └── kirana_qr_standee.png # Generated counter standee ready for printing
└── data/
    └── kirana_store.xlsx     # Auto-generated 2-tab master workbook
```

---

## Step-by-Step Setup Guide

### 1. Prerequisites
* **Operating System**: Windows 10/11, macOS, or Linux.
* **Python**: Version 3.10 or higher.
* **Microphone & Internet**: Required for phone testing.

### 2. Clone Repository & Setup Environment
```bash
git clone https://github.com/krish01omni/radha-kirana-voice-ai.git
cd radha-kirana-voice-ai

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 3. Configure Credentials (`.env`)
Copy the template file to `.env`:
```bash
cp .env.example .env
```
Edit `.env` with your preferred editor and supply your API keys:
```env
# Google Gemini API Key (Required for conversational intelligence)
# Obtain free from: https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# Speech Pipeline: Set 'GNANI' for production Indic voice or 'DEV' for local free fallback
AUDIO_MODE=GNANI

# Gnani.ai API Key (Required when AUDIO_MODE=GNANI)
# Obtain from: https://vachana.ai/
GNANI_API_KEY=your_gnani_vachana_api_key_here

# Voice persona (Gnani: 'Nalini', Edge-TTS: 'hi-IN-SwaraNeural')
DEFAULT_VOICE=Nalini

# Network binding
HOST=0.0.0.0
PORT=8000
```

---

## Excel Sheet Setup & Customization

The master Excel workbook `data/kirana_store.xlsx` is automatically created on first boot if it does not already exist. It contains two pre-configured sheets:

### Tab 1: `Price_Catalog`
Store owners can open this file in Excel, LibreOffice, or Google Sheets to configure their inventory:

| Item Name | Unit | Price (₹) | In Stock |
| :--- | :--- | :--- | :--- |
| Atta (Aashirvaad) | 1 kg | 60 | Yes |
| Sugar (Cheeni) | 1 kg | 45 | Yes |
| Amul Taaza Milk | 500 ml | 27 | Yes |
| Tata Salt | 1 kg | 28 | Yes |
| Maggi 2-Minute Noodles | 1 packet | 14 | Yes |
| Fortune Sunflower Oil | 1 litre | 145 | Yes |
| Basmati Rice | 1 kg | 90 | Yes |
| Taj Mahal Tea | 250 g | 110 | Yes |
| Toor Dal | 1 kg | 160 | Yes |
| Surf Excel Detergent | 1 kg | 135 | Yes |

* **Real-time Price Updates**: Change any price in the table, save the file, and Radha will quote the updated rate immediately without server restart.
* **Unit Normalization Engine**: If a customer requests *"2 litres milk"* for an item listed as `500 ml @ ₹27`, Radha automatically calculates $4 \times 27 = ₹108$.

### Tab 2: `Orders_Log`
Confirmed orders are appended automatically under thread-safe file locking:

| Timestamp | Call ID | Customer Name | Customer Contact | Ordered Items & Rates | Total Bill (₹) | Delivery Address | Special Instructions | Payment Method | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-10 12:23:13 | CALL_20261110_122313 | Raj | Web Phone | 1 kg Atta (@Rs.60 = Rs.60); 2 packet Maggi (@Rs.14 = Rs.28) | 88 | Room 201 Building 4 | Fulfillment: DELIVERY | Cash on Delivery | PENDING |

---

## Printable Counter Standee & QR Code Generation

To generate the counter standee with your custom public server URL:

```bash
python generate_qr.py --url "https://your-domain-or-tunnel-url.com"
```

This creates a print-ready image at `static/kirana_qr_standee.png`:
* Features Radha's branding, clear Hindi instructions (*"QR कोड स्कैन करें और बोलकर किराना सामान ऑर्डर करें"*).
* Print this sheet and place it on your billing counter or storefront.

---

## Running the Server & Enabling Mobile 4G/5G Access

### Local Execution
```bash
python app.py
```
The server will bind to `http://0.0.0.0:8000`.

### Public Phone Access over 4G/5G (Cloudflare Tunnel)
To allow customers to scan the counter standee from their own cellular mobile data outside the local Wi-Fi network, expose the local port using Cloudflare Tunnel (free, zero port-forwarding):

```bash
# Download cloudflared from https://github.com/cloudflare/cloudflared/releases
cloudflared tunnel --url http://localhost:8000
```
Cloudflare will output a public HTTPS address (e.g., `https://random-subdomain.trycloudflare.com`). Run `generate_qr.py` with that URL, and any smartphone on mobile data can call Radha immediately.

---

## Automated Verification Suite

Run the full end-to-end regression test suite to verify all dialogue stages, zero-decimal bill formatting, and Excel synchronization:

```bash
python test_all_flows.py
```

Expected verification output:
```
=================================================================
  RUNNING COMPREHENSIVE RADHA V3.2 FLOW & ACCURACY AUDIT
=================================================================
--- TEST 1: Full Home Delivery + COD Flow ---
User: 'Mujhe do packet maggi aur ek packet namak chahiye'
Radha: Ji, 2 packet Maggi 2-Minute Noodles, 1 kg Tata Salt note kar liya hai. Aur kuch chahiye ji?
User: 'Bas itna hi'
Radha: Aapka kul bill Rs. 56 hua hai. Kya aapka poora order yahi hai ya kuch aur jodna hai?
User: 'Haan theek hai'
Radha: Bahut badhiya! Kripya apna shubh naam bata dijiye?
User: 'Mera naam Raj hai'
Radha: Ji Raj! Kya aapko ye order home delivery chahiye, ya aap dukan se aakar le jayenge?
...
=================================================================
  ALL 4 TEST SUITES PASSED WITH 100% SUCCESS!
=================================================================
```

---

## Security & Privacy Assurance

* **Zero Hardcoded Secrets**: All private API keys and tokens are loaded strictly via environment variables.
* **Git Cleanliness**: `.gitignore` strictly protects `.env`, customer audio recordings (`recordings/`), and customer order spreadsheets (`data/*.xlsx`).
* **Prompt Injection Defense**: Customer utterances are sanitized through boundary stripping before passing to Gemini LLM.
* **CWE-1236 Spreadsheet Security**: Leading characters (`=`, `+`, `-`, `@`) in customer names or addresses are escaped with single quotes to prevent spreadsheet formula execution exploits.

---

## Contributing & License

Contributions are welcome! Please submit issues or pull requests to improve Indic dialect handling or additional POS integrations.

Distributed under the **MIT License**. See `LICENSE` for details.
