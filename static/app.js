let socket = null;
let audioContext = null;
let micSource = null;
let processorNode = null;
let audioStream = null;
let isCallActive = false;
let audioPlayer = new Audio();

// VAD State Machine
let pcmBuffer = [];
let isUserSpeaking = false;
let silenceFramesCount = 0;
const VAD_ENERGY_THRESHOLD = 0.016; // Energy threshold for active human voice
const SILENCE_FRAMES_TRIGGER = 7;   // ~1.79s continuous silence threshold (ensures natural pauses don't cut off customer)
const MIN_SPEECH_FRAMES = 2;        // At least ~500ms speech required before considering it a valid turn

const callBtn = document.getElementById("callBtn");
const btnIcon = document.getElementById("btnIcon");
const btnLabel = document.getElementById("btnLabel");
const callStatus = document.getElementById("callStatus");
const avatarRing = document.getElementById("avatarRing");
const waveformContainer = document.getElementById("waveformContainer");
const dialogScroll = document.getElementById("dialogScroll");
const receiptCard = document.getElementById("receiptCard");
const receiptId = document.getElementById("receiptId");
const receiptBody = document.getElementById("receiptBody");
const receiptTotal = document.getElementById("receiptTotal");
const receiptAddress = document.getElementById("receiptAddress");
const catalogModal = document.getElementById("catalogModal");
const viewCatalogBtn = document.getElementById("viewCatalogBtn");
const closeModalBtn = document.getElementById("closeModalBtn");
const catalogList = document.getElementById("catalogList");

callBtn.addEventListener("click", () => {
  if (!isCallActive) {
    startCall();
  } else {
    endCall();
  }
});

async function startCall() {
  try {
    callStatus.textContent = "Connecting to Radha...";
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    // Initialize Web Audio Context at standard 16kHz
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    audioContext = new AudioCtxClass({ sampleRate: 16000 });
    await audioContext.resume();

    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/ws/call`;
    socket = new WebSocket(wsUrl);
    socket.binaryType = "arraybuffer";

    socket.onopen = () => {
      isCallActive = true;
      updateUIForActiveCall();
      startAudioCapture();
    };

    socket.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      handleServerMessage(data);
    };

    socket.onclose = () => {
      if (isCallActive) {
        endCall();
      }
    };

    socket.onerror = (err) => {
      console.error("[WebSocket Error]", err);
      callStatus.textContent = "Connection error. Retrying...";
    };

  } catch (err) {
    console.error("[Mic Error]", err);
    callStatus.textContent = "Microphone access denied.";
    alert("Please allow microphone access to talk to Radha.");
  }
}

let ambientNoiseFloor = 0.010;
let consecutiveSpeechFrames = 0;

function startAudioCapture() {
  micSource = audioContext.createMediaStreamSource(audioStream);

  // 1. High-Pass Filter: Strips sub-bass, 50Hz/60Hz AC hum, motor rumbling (<140Hz)
  const highpassFilter = audioContext.createBiquadFilter();
  highpassFilter.type = "highpass";
  highpassFilter.frequency.setValueAtTime(140, audioContext.currentTime);
  highpassFilter.Q.setValueAtTime(0.7, audioContext.currentTime);

  // 2. Low-Pass Filter: Strips high-frequency whine, inverter hiss (>3600Hz)
  const lowpassFilter = audioContext.createBiquadFilter();
  lowpassFilter.type = "lowpass";
  lowpassFilter.frequency.setValueAtTime(3600, audioContext.currentTime);
  lowpassFilter.Q.setValueAtTime(0.7, audioContext.currentTime);

  // 3. Human Voice Clarity Peaking Filter: Boosts vocal formant range (1500Hz)
  const voiceBoostFilter = audioContext.createBiquadFilter();
  voiceBoostFilter.type = "peaking";
  voiceBoostFilter.frequency.setValueAtTime(1500, audioContext.currentTime);
  voiceBoostFilter.gain.setValueAtTime(3.5, audioContext.currentTime);
  voiceBoostFilter.Q.setValueAtTime(1.0, audioContext.currentTime);

  // Buffer size 4096 samples at 16kHz = ~256ms per audio frame
  processorNode = audioContext.createScriptProcessor(4096, 1, 1);

  processorNode.onaudioprocess = (e) => {
    if (!isCallActive) return;

    const inputData = e.inputBuffer.getChannelData(0);
    
    // 1. Calculate Root Mean Square (RMS) energy of filtered voice frame
    let sumSquares = 0.0;
    for (let i = 0; i < inputData.length; i++) {
      sumSquares += inputData[i] * inputData[i];
    }
    const rms = Math.sqrt(sumSquares / inputData.length);

    // Dynamic Noise Floor Tracking:
    // If not actively speaking, adapt to continuous background machine noise
    if (!isUserSpeaking) {
      if (rms < ambientNoiseFloor * 1.8) {
        ambientNoiseFloor = ambientNoiseFloor * 0.94 + rms * 0.06;
      }
    }

    // Dynamic Speech Threshold:
    // Human voice speaking close to the mic is significantly above background machine noise
    const dynamicSpeechThreshold = Math.max(0.026, ambientNoiseFloor * 2.3);

    // 2. Convert 32-bit float [-1.0, 1.0] to 16-bit signed PCM
    const pcm16 = new Int16Array(inputData.length);
    for (let i = 0; i < inputData.length; i++) {
      const s = Math.max(-1, Math.min(1, inputData[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // 3. Voice Activity Detection (VAD) with Barge-In Protection
    const isVoiceDetected = rms > dynamicSpeechThreshold;

    if (isVoiceDetected) {
      consecutiveSpeechFrames++;

      // If Radha is currently speaking, require at least 2 consecutive speech frames
      // to prevent momentary background machine spikes from interrupting her
      const canBargeIn = audioPlayer.paused || consecutiveSpeechFrames >= 2;

      if (!isUserSpeaking && canBargeIn) {
        isUserSpeaking = true;
        callStatus.textContent = "Listening to you...";
        waveformContainer.classList.add("active");
        
        // Anti-interruption: Mute Radha only on sustained user speech
        if (!audioPlayer.paused) {
          audioPlayer.pause();
          audioPlayer.currentTime = 0;
        }
      }

      if (isUserSpeaking) {
        silenceFramesCount = 0;
        pcmBuffer.push(pcm16);
      }

    } else {
      consecutiveSpeechFrames = 0;
      if (isUserSpeaking) {
        pcmBuffer.push(pcm16);
        silenceFramesCount++;

        // When silence persists for ~1.79s, customer has completed their turn
        if (silenceFramesCount >= SILENCE_FRAMES_TRIGGER) {
          if (pcmBuffer.length >= MIN_SPEECH_FRAMES) {
            commitSpeechUtterance();
          } else {
            // Discard momentary noise bursts
            pcmBuffer = [];
            isUserSpeaking = false;
            silenceFramesCount = 0;
          }
        }
      }
    }
  };

  // Connect Filter Pipeline: Mic -> HighPass -> LowPass -> VoiceBoost -> Processor -> Destination
  micSource.connect(highpassFilter);
  highpassFilter.connect(lowpassFilter);
  lowpassFilter.connect(voiceBoostFilter);
  voiceBoostFilter.connect(processorNode);
  processorNode.connect(audioContext.destination);
}

function commitSpeechUtterance() {
  if (pcmBuffer.length === 0 || !socket || socket.readyState !== WebSocket.OPEN) return;

  callStatus.textContent = "Radha processing...";
  waveformContainer.classList.remove("active");

  // Merge PCM chunks into a single ArrayBuffer
  let totalSamples = 0;
  for (let i = 0; i < pcmBuffer.length; i++) {
    totalSamples += pcmBuffer[i].length;
  }

  const mergedPcm = new Int16Array(totalSamples);
  let offset = 0;
  for (let i = 0; i < pcmBuffer.length; i++) {
    mergedPcm.set(pcmBuffer[i], offset);
    offset += pcmBuffer[i].length;
  }

  // Send pure 16kHz PCM bytes to server (zero WebM headers, zero corruption!)
  socket.send(mergedPcm.buffer);

  // Reset turn state
  pcmBuffer = [];
  isUserSpeaking = false;
  silenceFramesCount = 0;
}

function endCall() {
  isCallActive = false;
  if (processorNode) {
    processorNode.disconnect();
    processorNode = null;
  }
  if (micSource) {
    micSource.disconnect();
    micSource = null;
  }
  if (audioContext && audioContext.state !== "closed") {
    audioContext.close();
  }
  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop());
  }
  if (!audioPlayer.paused) {
    audioPlayer.pause();
  }
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type: "hangup" }));
    socket.close();
  }
  updateUIForIdleCall();
}

function updateUIForActiveCall() {
  callBtn.className = "call-btn active";
  btnIcon.textContent = "🛑";
  btnLabel.textContent = "End Call";
  callStatus.textContent = "Call connected • Speak your order in Hindi/English";
  avatarRing.classList.add("active");
}

function updateUIForIdleCall() {
  callBtn.className = "call-btn idle";
  btnIcon.textContent = "📞";
  btnLabel.textContent = "Call Radha";
  callStatus.textContent = "Call ended • Thank you!";
  avatarRing.classList.remove("active");
  waveformContainer.classList.remove("active");
}

function handleServerMessage(data) {
  if (data.type === "agent_reply" || data.type === "greeting") {
    callStatus.textContent = "Radha speaking...";
    addMessage("assistant", data.text);
    if (data.audio_base64) {
      playAudio(data.audio_base64, data.audio_mime || "audio/mp3", Boolean(data.auto_end_call));
    }
  } else if (data.type === "user_transcript") {
    addMessage("user", data.text);
  } else if (data.type === "order_receipt") {
    renderReceipt(data.order);
    callStatus.textContent = "Order Confirmed! Receipt generated.";
  } else if (data.type === "status") {
    callStatus.textContent = data.text;
  }
}

function addMessage(sender, text) {
  if (!text) return;
  const bubble = document.createElement("div");
  bubble.className = `msg-bubble ${sender}`;
  bubble.textContent = text;
  dialogScroll.appendChild(bubble);
  dialogScroll.scrollTop = dialogScroll.scrollHeight;
}

function playAudio(base64Data, mimeType = "audio/mp3", autoEnd = false) {
  audioPlayer.src = `data:${mimeType};base64,${base64Data}`;
  audioPlayer.play().then(() => {
    audioPlayer.onended = () => {
      if (autoEnd) {
        callStatus.textContent = "Order complete • Disconnecting...";
        setTimeout(() => {
          endCall();
        }, 900);
        return;
      }
      if (isCallActive) {
        callStatus.textContent = "Listening to you...";
      }
    };
  }).catch(e => {
    console.warn("Auto-play blocked:", e);
    if (autoEnd) {
      setTimeout(() => {
        endCall();
      }, 1500);
    }
  });
}

function renderReceipt(order) {
  if (!order) return;
  receiptCard.classList.remove("hidden");
  receiptId.textContent = `#${order.call_id || "ORD-001"}`;
  
  const totalVal = Math.round(Number(order.total_calculated_bill || order.total_bill || 0));
  receiptTotal.textContent = `₹${totalVal}`;

  const customerName = order.customer_name || "Valued Customer";
  const address = order.delivery_address || "Store Pickup";
  receiptAddress.innerHTML = `<strong>Customer:</strong> ${customerName}<br><strong>Delivery:</strong> ${address}`;

  receiptBody.innerHTML = "";
  const items = order.items_ordered || [];
  if (items.length === 0) {
    receiptBody.innerHTML = `<p style="color: #94A3B8;">Inquiry recorded.</p>`;
    return;
  }

  items.forEach(it => {
    const row = document.createElement("div");
    row.className = "receipt-item";
    const sub = it.subtotal ? `₹${Math.round(Number(it.subtotal))}` : "";
    const qty = (typeof it.quantity === "number" && Number.isInteger(it.quantity)) ? it.quantity : Math.round(it.quantity);
    row.innerHTML = `<span>${qty} ${it.unit} ${it.item_name}</span><strong>${sub}</strong>`;
    receiptBody.appendChild(row);
  });
}

// Catalog modal
viewCatalogBtn.addEventListener("click", async () => {
  catalogModal.classList.remove("hidden");
  try {
    const res = await fetch("/api/catalog");
    const catalog = await res.json();
    catalogList.innerHTML = "";
    for (const key in catalog) {
      const it = catalog[key];
      const row = document.createElement("div");
      row.className = "catalog-item-row";
      row.innerHTML = `<span>${it.raw_name} (${it.unit})</span><strong>₹${it.price}</strong>`;
      catalogList.appendChild(row);
    }
  } catch (err) {
    catalogList.innerHTML = "<p>Error loading catalog</p>";
  }
});

closeModalBtn.addEventListener("click", () => {
  catalogModal.classList.add("hidden");
});
