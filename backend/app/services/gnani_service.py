
import json
from pathlib import Path

import requests
from gnani.stt import GnaniSTTClient

from app.config import settings


class GnaniTTSRequestError(RuntimeError):
    def __init__(
        self,
        *,
        status_code: int,
        provider_message: str,
        content_type: str | None,
    ) -> None:
        super().__init__("Gnani cloned TTS returned a non-success status")
        self.status_code = status_code
        self.provider_message = provider_message
        self.content_type = content_type


class GnaniService:

    TTS_API_URL = "https://api.vachana.ai/api/v1/tts/inference"

    def __init__(self):
        self.api_key = settings.gnani_api_key

        if not self.api_key:
            raise ValueError("GNANI_API_KEY is not configured")

        # Existing STT client remains unchanged
        self.stt_client = GnaniSTTClient(
            api_key=self.api_key
        )

        # Load the cloned voice embedding once
        embedding_path = (
            Path(__file__).resolve().parents[2]
            / "voice_embedding.json"
        )

        if not embedding_path.exists():
            raise FileNotFoundError(
                f"Voice embedding not found: {embedding_path}"
            )

        with embedding_path.open("r", encoding="utf-8") as file:
            self.speaker_embedding = json.load(file)

        self.tts_speed = 1.00

    def generate_speech(
        self,
        text: str,
        voice: str | None = None,
        language: str | None = None,
    ) -> bytes:

        if not text or not text.strip():
            raise ValueError("Speech text cannot be empty")

        if language and language != "te-IN":
            raise ValueError(
                "The configured cloned voice is currently intended for Telugu."
            )

        headers = {
            "X-API-Key-ID": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model": "vachana-vc-v1",
            "speaker_embedding": self.speaker_embedding,
            "speed": self.tts_speed,
            "audio_config": {
                "sample_rate": 22050,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }

        response = requests.post(
            self.TTS_API_URL,
            headers=headers,
            json=payload,
            timeout=120,
        )

        if response.status_code != 200:
            raise GnaniTTSRequestError(
                status_code=response.status_code,
                provider_message=response.text,
                content_type=response.headers.get("Content-Type"),
            )

        return response.content

    def transcribe_audio(
        self,
        audio_path: str,
        language: str = "te-IN",
    ) -> str:

        result = self.stt_client.transcribe(
            audio_path,
            language_code=language,
        )

        return result["transcript"]
