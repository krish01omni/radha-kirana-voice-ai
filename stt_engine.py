import os
import wave
import torch
import numpy as np
from faster_whisper import WhisperModel

# Common Whisper hallucinations on silence, background hiss, or breaths
HALLUCINATION_BLACKLIST = {
    "main sun rahi hoon",
    "main sun raha hoon",
    "main sun rahi hun",
    "main sun raha hun",
    "thank you for watching",
    "subtitles by",
    "thank you",
    "thanks",
    "dhanyawad",
    "shukriya",
    "you",
    "bye",
    "...",
    "subtitles",
    "amara.org",
    "subscribe",
    "watching"
}

# Regional Indian, Hinglish, and Bhojpuri vocabulary priming prompt
INITIAL_PROMPT = (
    "Namaste, mujhe 2 packet doodh, 1 kilo atta, 2 kilo cheeni, maggi, tata namak, sarson tel, urad daal chahiye. "
    "Mera naam Raj hai. Rajesh, Suresh, Ramesh, Amit, Rahul, Priya, Pooja. "
    "Hum Raj Colony, Gandhi Nagar, Flat number 302, Room number 104, gali number, sector mein rehte hain. "
    "Bas itna hi samaan chahiye, bhejwa dijiye. Total bill kitna hua? Haan poora order hai, book kar do."
)

class LocalWhisperSTT:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(LocalWhisperSTT, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_size: str = "small"):
        if getattr(self, "_initialized", False):
            return
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"[LocalWhisperSTT] Initializing Faster-Whisper '{model_size}' on {device.upper()} ({compute_type})...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._initialized = True
        print(f"[LocalWhisperSTT] Faster-Whisper '{model_size}' ready for real-time transcription!")

    def transcribe_pcm(self, pcm_bytes: bytes, sample_rate: int = 16000) -> str:
        """
        Transcribes raw 16-bit 16kHz PCM audio bytes directly in memory.
        Zero disk I/O, zero FFmpeg subprocess overhead.
        """
        if not pcm_bytes or len(pcm_bytes) < 3200:  # Minimum 200ms audio required
            return ""

        try:
            # 1. Convert raw bytes to float32 NumPy array normalized to [-1.0, 1.0]
            audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32768.0

            # 2. Check energy to filter out dead silence or microphone hiss
            rms = np.sqrt(np.mean(audio_float32**2))
            if rms < 0.008:
                return ""

            # 3. Direct in-memory transcription with beam search & prompt priming
            segments, _ = self.model.transcribe(
                audio_float32,
                language="hi",
                initial_prompt=INITIAL_PROMPT,
                beam_size=3,
                best_of=3,
                temperature=0.0,
                condition_on_previous_text=False,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400)
            )

            text_chunks = [s.text.strip() for s in segments if s.text.strip()]
            full_text = " ".join(text_chunks).strip()

            # 4. Anti-hallucination filter
            lower_clean = full_text.lower().replace(".", "").replace(",", "").strip()
            if lower_clean in HALLUCINATION_BLACKLIST:
                return ""

            return full_text
        except Exception as e:
            print(f"[Whisper PCM Transcribe Error] {e}")
            return ""

    def transcribe(self, audio_path: str, language: str = "hi") -> str:
        """Transcribes audio from a WAV file on disk."""
        if not os.path.exists(audio_path):
            return ""
        try:
            segments, _ = self.model.transcribe(
                audio_path,
                language=language,
                initial_prompt=INITIAL_PROMPT,
                beam_size=3,
                best_of=3,
                temperature=0.0,
                vad_filter=True
            )
            return " ".join([s.text.strip() for s in segments if s.text.strip()]).strip()
        except Exception as e:
            print(f"[Whisper File Transcribe Error] {e}")
            return ""

    def save_wav(self, pcm_bytes: bytes, output_path: str, sample_rate: int = 16000):
        """Saves accumulated PCM bytes into a standard 16kHz Mono WAV file."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with wave.open(output_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_bytes)
