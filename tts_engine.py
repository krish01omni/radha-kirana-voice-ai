import os
import asyncio
import edge_tts

class LocalEdgeTTS:
    def __init__(self, voice: str = "hi-IN-SwaraNeural"):
        self.voice = voice

    async def synthesize_to_bytes(self, text: str, voice: str = None) -> bytes:
        """Synthesizes text into MP3/WAV audio bytes using Microsoft Edge Neural TTS."""
        selected_voice = voice or self.voice
        communicate = edge_tts.Communicate(text, selected_voice)
        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])
        return bytes(audio_data)

    def synthesize_sync(self, text: str, voice: str = None) -> bytes:
        """Synchronous wrapper for synthesize_to_bytes."""
        return asyncio.run(self.synthesize_to_bytes(text, voice))
