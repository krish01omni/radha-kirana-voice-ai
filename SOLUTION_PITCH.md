# Radha (राधा) — Voice-First AI Counter for Indian Retail

### 1. Project Title
**Radha (राधा)** — Zero-Hardware Voice AI Ordering Counter for India's 12 Million Kirana Stores.

---

### 2. The Problem You Are Solving
Between 6 PM and 9 PM, every neighborhood kirana store in India turns chaotic. Customers jostle at the counter, WhatsApp pings with unorganized voice notes, and phone calls interrupt every billing calculation. The shopkeeper juggles a calculator in one hand, packs groceries with the other, and scribbles delivery addresses on loose scrap paper.

By closing time:
* Paper slips get lost or stained, leading to missed sales and customer disputes.
* Item rates get miscalculated in the evening rush.
* Delivery boys take the wrong bag to the wrong house.
* Big quick-commerce apps charge steep commissions (15–25%) and demand complex POS software that local retailers neither want nor can afford.

---

### 3. Who Will Use It?
* **Local Kirana Shopkeepers & Small Retailers**: Neighborhood grocery stores, dairy counters, and mom-and-pop shops who want automated order-taking without buying computers, tablets, or barcode scanners. They control inventory and prices directly from a basic Google Sheet on their existing phone.
* **Everyday Customers & Neighborhood Shoppers**: Everyday shoppers (especially homemakers and elders) who find typing on complex apps frustrating. They simply point their phone camera at a printed counter QR standee, speak naturally in everyday Hindi or Hinglish, and get their groceries delivered or packed for quick pickup.

---

### 4. What Radha Does (The Solution)
Radha turns any retail counter into an automated voice ordering desk with **zero hardware cost**:
1. **Scan-to-Call**: Customer scans a physical laminated QR standee. It launches an instant web call in their browser without downloading any mobile app.
2. **Speaks Like a Shopkeeper**: Radha greets the customer, listens clearly through background shop noise, notes down items, and quotes the bill in clean, whole rupees (₹600, never ₹600.0).
3. **Smart Retail Follow-ups**: Clarifies Home Delivery vs. Store Pickup, captures customer name and flat/room number, and checks payment mode (Cash vs. UPI).
4. **Auto-Disconnect & Instant Alerts**: The call auto-disconnects on confirmation. The itemized order logs instantly into the shopkeeper's Google Sheet and fires an instant receipt card to their Telegram bot.

---

### 5. The Gnani AI Models & APIs You Use
Radha is powered by Gnani.ai's state-of-the-art Indic Voice Infrastructure:

* **Gnani `prisma-v3.0` Indic Speech-to-Text (STT) API (`/stt/v3`)**:
  * Transcribes streaming 16kHz PCM voice turns in real-time.
  * Native understanding of Indian accents, vernacular grocery units (*"ek pao cheeni"*, *"aadha kilo atta"*, *"do packet doodh"*), and multilingual code-switching between Hindi, English, and regional dialects.
  * Robust against loud background retail noise (refrigerator compressors, mixer grinders, ceiling fans, and street traffic).
* **Gnani `timbre-v2.5` Indic Text-to-Speech (TTS) API (`/api/v1/tts/inference`)**:
  * Synthesizes natural, humanized Hindi voice responses using the **`Nalini`** voice persona (`hi-IN`).
  * Delivers a polite, conversational tone that customers trust like a real neighborhood store assistant.

---

### 6. The Real-World Impact
Zero new devices, zero commission cuts, and zero app fatigue. India's kirana shops already have community trust and 10-minute delivery speed—Radha gives them hands-free voice automation with nothing more than a sheet of paper on the counter.
