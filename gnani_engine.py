import os
import io
import wave
import requests
from typing import Optional
from stt_engine import LocalWhisperSTT
from tts_engine import LocalEdgeTTS

class UnifiedAudioEngine:
    def __init__(self, mode: str = "DEV", gnani_api_key: Optional[str] = None):
        self.mode = mode or os.getenv("AUDIO_MODE", "DEV")
        self.gnani_api_key = gnani_api_key or os.getenv("GNANI_API_KEY", "")
        self.base_url = "https://api.vachana.ai"
        
        # Local free engines (0 credit burn)
        self.local_stt = LocalWhisperSTT(model_size="small")
        self.local_tts = LocalEdgeTTS(voice=os.getenv("DEFAULT_VOICE", "hi-IN-SwaraNeural"))

    def transcribe_pcm(self, pcm_bytes: bytes) -> str:
        """
        Transcribes raw 16kHz PCM audio bytes.
        In GNANI mode: sends in-memory WAV to Gnani prisma-v3.0.
        In DEV mode: uses local CUDA Faster-Whisper small.
        """
        if self.mode == "GNANI" and self.gnani_api_key:
            try:
                # Wrap PCM into an in-memory WAV buffer
                wav_io = io.BytesIO()
                with wave.open(wav_io, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(pcm_bytes)
                wav_io.seek(0)

                headers = {"X-API-Key-ID": self.gnani_api_key}
                files = {"audio_file": ("turn.wav", wav_io, "audio/wav")}
                data = {"language_code": "indic-auto", "model": "prisma-v3.0"}
                resp = requests.post(f"{self.base_url}/stt/v3", headers=headers, files=files, data=data, timeout=8)
                if resp.status_code == 200:
                    t = resp.json().get("transcript", "")
                    return t.strip() if t else ""
                print(f"[Gnani STT Status {resp.status_code}] Falling back to local Faster-Whisper.")
            except Exception as e:
                print(f"[Gnani STT Error] {e}")

        # Local Faster-Whisper small on CUDA (Fallback on API failure)
        return self.local_stt.transcribe_pcm(pcm_bytes)

    def transcribe_audio(self, audio_file_path: str, lang: str = "indic-auto") -> str:
        """Transcribes audio file on disk."""
        if self.mode == "GNANI" and self.gnani_api_key:
            try:
                headers = {"X-API-Key-ID": self.gnani_api_key}
                with open(audio_file_path, "rb") as f:
                    files = {"audio_file": (os.path.basename(audio_file_path), f, "audio/wav")}
                    data = {"language_code": lang, "model": "prisma-v3.0"}
                    resp = requests.post(f"{self.base_url}/stt/v3", headers=headers, files=files, data=data, timeout=12)
                    if resp.status_code == 200:
                        transcript = resp.json().get("transcript", "")
                        if transcript:
                            return transcript
                    print(f"[Gnani STT Status {resp.status_code}] Falling back to local whisper.")
            except Exception as e:
                print(f"[Gnani STT Error] {e}")

        # Local Faster-Whisper (CUDA)
        return self.local_stt.transcribe(audio_file_path, language="hi" if lang == "hi-IN" else None)

    async def synthesize_speech(self, text: str, voice: str = "Nalini", lang: str = "hi-IN") -> bytes:
        """
        Synthesizes text into audio bytes.
        In GNANI mode: calls Gnani timbre-v2.5 endpoint.
        In DEV mode: uses local Edge-TTS (hi-IN-SwaraNeural).
        """
        if self.mode == "GNANI" and self.gnani_api_key:
            try:
                headers = {
                    "X-API-Key-ID": self.gnani_api_key,
                    "Content-Type": "application/json"
                }
                payload = {
                    "text": text,
                    "voice": voice,
                    "model": "timbre-v2.5",
                    "language": lang,
                    "speed": 1,
                    "audio_config": {
                        "encoding": "linear_pcm",
                        "container": "wav",
                        "num_channels": 1,
                        "sample_rate": 24000,
                        "sample_width": 2
                    }
                }
                resp = requests.post(f"{self.base_url}/api/v1/tts/inference", headers=headers, json=payload, timeout=10)
                if resp.status_code == 200 and resp.content:
                    return resp.content
                print(f"[Gnani TTS Status {resp.status_code}] Falling back to Edge-TTS.")
            except Exception as e:
                print(f"[Gnani TTS Error] {e}")

        # Local Edge-TTS (Free)
        return await self.local_tts.synthesize_to_bytes(text)
