
from app.services.gnani_service import GnaniService

gnani = GnaniService()

print("Testing Telugu STT...")

transcript = gnani.transcribe_audio(
    audio_path="Sample_test_clean.wav",
    language="te-IN",
)

print("STT successful!")
print("Recognized text:", transcript)
