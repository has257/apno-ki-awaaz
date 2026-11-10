
import os

from app.config import settings
from transformers import pipeline


os.environ["GNANI_API_KEY"] = settings.gnani_api_key

print("Initializing Gnani TTS...")

tts = pipeline(
    "text-to-speech",
    model="gnani/gnani",
    trust_remote_code=True,
)

print("Generating Telugu audio...")

result = tts(
    "నమస్కారం. మీ మందులు వేసుకునే సమయం అయింది.",
    voice=settings.gnani_tts_voice,
    model="timbre-v2.5",
    language="te-IN",
    tts_mode="rest",
    sample_rate=22050,
    container="wav",
    encoding="linear_pcm",
)

audio = result["audio"]

with open("test_reminder.wav", "wb") as file:
    file.write(audio)

print("Audio generated successfully!")
print("Saved to: test_reminder.wav")
print("Audio size:", len(audio), "bytes")
