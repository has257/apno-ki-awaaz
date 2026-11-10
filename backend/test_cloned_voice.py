
import json
import requests
from pathlib import Path
from app.config import settings

API_URL = "https://api.vachana.ai/api/v1/tts/inference"

# Load your saved speaker embedding
with open("voice_embedding.json", "r", encoding="utf-8") as file:
    speaker_embedding = json.load(file)


payload = {
    "text": "అమ్మా... సాయంత్రం మందులు వేసుకోవడం మర్చిపోకు. కొంచెం నీళ్లు కూడా తాగు.",
    "model": "vachana-vc-v1",
    "speaker_embedding": speaker_embedding,
    "speed": 0.90,
    "audio_config": {
        "sample_rate": 22050,
        "num_channels": 1,
        "sample_width": 2,
        "encoding": "linear_pcm",
        "container": "wav"
    }
}

headers = {
    "X-API-Key-ID": settings.gnani_api_key,
    "Content-Type": "application/json"
}

print("Generating speech using your cloned voice...")

response = requests.post(
    API_URL,
    headers=headers,
    json=payload,
    timeout=120
)

if response.status_code != 200:
    print("API Error:", response.status_code)
    print(response.text)
    response.raise_for_status()

output_file = Path("cloned_voice_test.wav")
output_file.write_bytes(response.content)

print("Success! Your cloned voice audio is ready.")
print(f"Saved to: {output_file}")
