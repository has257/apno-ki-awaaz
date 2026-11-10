
from app.services.gnani_service import GnaniService


gnani = GnaniService()

print("Testing Telugu TTS...")

audio = gnani.generate_speech(
    text="అమ్మ, మందులు వేసుకున్నావా?.",
    language="te-IN",
)

with open("test_reminder.wav", "wb") as file:
    file.write(audio)

print("TTS successful")
print("Audio bytes:", len(audio))
print("Saved: test_reminder.wav")
