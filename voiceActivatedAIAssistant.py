# YOU GOTTA pip install pyaudio google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client openai python-dateutil numpy pyttsx3
import pyaudio
import wave
import re
from datetime import datetime, timedelta
from dateutil import parser
import speech_recognition as sr
from google.oauth2 import service_account
from googleapiclient.discovery import build
import openai
import numpy as np
import sys
import pyttsx3

# Initialize Google Calendar API credentials
calendar_credentials = service_account.Credentials.from_service_account_file('path_to_your_google_credentials.json')
calendar_service = build('calendar', 'v3', credentials=calendar_credentials)

# Initialize OpenAI API
openai.api_key = 'your_openai_api_key'

# Audio recording parameters
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
RECORD_SECONDS = 10
SILENCE_THRESHOLD = 2  # seconds of silence to stop recording

# Initialize PyAudio
p = pyaudio.PyAudio()

def record_audio():
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("Recording...")

    frames = []
    silent_frames = 0
    recording = True

    while recording:
        data = stream.read(CHUNK)
        frames.append(data)

        # Detect silence
        if is_silent(data):
            silent_frames += 1
            if silent_frames > SILENCE_THRESHOLD * (RATE / CHUNK):
                recording = False
        else:
            silent_frames = 0

    stream.stop_stream()
    stream.close()
    
    audio_filename = "output.wav"
    wf = wave.open(audio_filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print("Finished recording.")
    return audio_filename


def is_silent(data):
    audio_data = np.frombuffer(data, dtype=np.int16)
    return np.max(np.abs(audio_data)) < 2000

def transcribe_audio(audio_filename):
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_filename) as source:
        audio = recognizer.record(source)
    try:
        text = recognizer.recognize_sphinx(audio)
        print("Transcription: " + text)
    except sr.UnknownValueError:
        print("Sphinx could not understand the audio")
        text = ""
    except sr.RequestError as e:
        print("Sphinx error; {0}".format(e))
        text = ""

    return text

def parse_command(text):
    if "calendar" in text or "event" in text or "reminder" in text:
        return "calendar"
    else:
        return "chatgpt"

def add_to_calendar(text):
    # Extract title
    title_match = re.search(r"(set|schedule|create|add)\s+(an?\s+)?(event|reminder|meeting|appointment)?\s*(.*?)(on|at|for|from)?\s", text, re.IGNORECASE)
    title = title_match.group(4).strip() if title_match else "Untitled Event"

    # Extract datetime
    date_time_match = re.search(r"(on|at|for|from)\s+(.*)", text, re.IGNORECASE)
    date_time_text = date_time_match.group(2).strip() if date_time_match else None

    # Parse date and time using dateutil
    try:
        if date_time_text:
            start_time = parser.parse(date_time_text, fuzzy=True)
        else:
            start_time = datetime.now() + timedelta(days=1)  # Default to tomorrow
    except ValueError:
        start_time = datetime.now() + timedelta(days=1)  # Default to tomorrow

    # Default event duration of 1 hour
    end_time = start_time + timedelta(hours=1)

    event = {
        'summary': title,
        'start': {'dateTime': start_time.isoformat(), 'timeZone': 'America/Los_Angeles'},
        'end': {'dateTime': end_time.isoformat(), 'timeZone': 'America/Los_Angeles'},
        'reminders': {'useDefault': True},
    }
    #logic that handles user confirmation
    
    event_result = calendar_service.events().insert(calendarId='primary', body=event).execute()
    try:
        confirmation_text = f"event_result '{event['summary']}' is scheduled on {event['start']['dateTime']}. Confirm?"
        speak_text(confirmation_text)
        audio_filename2 = record_audio()
        text2 = transcribe_audio(audio_filename2)
        print("You said:", text2)
        if "no" in text2 or "wrong" in text2 or "nope" in text2 or "nah" in text2:
            speak_text("Ok, let's try again. Tell me the details of your event")
            audio_filename3 = record_audio()
            text3 = transcribe_audio(audio_filename3)
            add_to_calendar(text3)
        else:
            return event_result
    except ValueError:
        return event_result

def chatgpt_response(text):
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=text,
        max_tokens=150
    )
    return response.choices[0].text.strip()

def speak_text(text):
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()

def main():
    try:
        audio_filename = record_audio()
        text = transcribe_audio(audio_filename)
        print("You said:", text)

        command = parse_command(text)
        if command == "calendar":
            add_to_calendar(text)
        
        else:
            response = chatgpt_response(text)
            speak_text(response)
    except KeyboardInterrupt:
        sys.quit()
if __name__ == "__main__":
    main()