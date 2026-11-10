
import json
import requests

from pathlib import Path
from app.config import settings

API_URL = "https://api.vachana.ai/api/v1/tts/voice-clone/embeddings"

audio_path = Path("Sample_test_fixed.wav")

if not audio_path.exists():
    raise FileNotFoundError(f"Recording not found: {audio_path}")

headers = {
    "X-API-Key-ID": settings.gnani_api_key
}

print("Generating your voice embedding...")

with audio_path.open("rb") as audio:
    response = requests.post(
        API_URL,
        headers=headers,
        files={
            "audio_file": (
                audio_path.name,
                audio,
                "audio/wav"
            )
        },
        timeout=120
    )

response.raise_for_status()
result = response.json()

if not result.get("success"):
    raise RuntimeError(f"Gnani API error: {result}")

embedding = result["data"]["voice_clone_embedding"]

output_path = Path("voice_embedding.json")
output_path.write_text(
    json.dumps(embedding),
    encoding="utf-8"
)

print("Voice embedding generated successfully!")
print(f"Saved locally to: {output_path}")
print("Embedding shape:", embedding["shape"])
print("Embedding dtype:", embedding["dtype"])
