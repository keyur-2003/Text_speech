import streamlit as st
import google.generativeai as genai
import os
from gtts import gTTS
from pydub import AudioSegment
from pydub.generators import Sine
import base64
import speech_recognition as sr
import tempfile

# Set up Google API Key (Replace with your actual Gemini API key)

genai_api_key = st.secrets["GENAI_API_KEY"]
genai.configure(api_key=genai_api_key)
model = genai.GenerativeModel('gemini-2.0-flash')

# Function: Generate simple musical notation
def generate_musical_text(text):
    try:
        prompt = f"Based on the following text: '{text}', describe a very simple musical phrase (e.g., 'C4-quarter, G4-quarter, A4-half, tempo=100'). Keep it brief."
        response = model.generate_content(prompt)
        musical_text = response.text.strip()
        return musical_text
    except Exception as e:
        return f"Error generating musical text: {str(e)}"

# Function: Convert text to speech
def text_to_speech(text, language='en'):
    try:
        tts = gTTS(text=text, lang=language)
        tts.save("speech.mp3")
        audio = AudioSegment.from_mp3("speech.mp3")
        os.remove("speech.mp3")
        return audio
    except Exception as e:
        return f"Error during text-to-speech: {str(e)}"

# Function: Generate music from notes
def generate_sine_wave(musical_text, tempo=120):
    segments = []
    frequency_map = {
        "C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23,
        "G4": 392.00, "A4": 440.00, "B4": 493.88
    }
    duration_map = {"quarter": 0.5, "half": 1.0}

    if musical_text and not musical_text.startswith("Error"):
        notes = musical_text.split(',')
        for item in notes:
            item = item.strip()
            if "tempo=" in item:
                try:
                    tempo = int(item.split("=")[1])
                except ValueError:
                    st.warning(f"Invalid tempo in musical text: {item}")
                continue
            parts = item.split('-')
            if len(parts) == 2:
                note = parts[0].strip()
                duration_str = parts[1].strip()
                if note in frequency_map and duration_str in duration_map:
                    frequency = frequency_map[note]
                    duration_seconds = duration_map[duration_str]
                    duration_ms = int(duration_seconds * 1000 * (60 / tempo))
                    segment = Sine(freq=frequency).to_audio_segment(duration=duration_ms)
                    segments.append(segment)

    if segments:
        combined_audio = segments[0]
        for i in range(1, len(segments)):
            combined_audio = combined_audio.append(segments[i], crossfade=0)
        return combined_audio
    return AudioSegment.silent(duration=0)

# Function: Combine speech and music
def combine_audio(speech_audio, music_audio, music_volume_adjust=-20):
    if isinstance(speech_audio, str):
        return speech_audio
    if isinstance(music_audio, str):
        music_audio = AudioSegment.silent(duration=len(speech_audio))
    else:
        music_audio = music_audio + music_volume_adjust

    combined = speech_audio.overlay(music_audio)
    return combined.export(format="mp3").read()

# ✅ Updated: Convert speech (MP3/WAV) to text with proper conversion
def speech_to_text(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        # Convert to proper WAV format
        audio = AudioSegment.from_file(tmp_path)
        wav_path = tmp_path + ".wav"
        audio.export(wav_path, format="wav")

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
            return text

    except sr.UnknownValueError:
        return "Could not understand audio"
    except sr.RequestError as e:
        return f"Could not request results; {e}"
    except Exception as e:
        return f"Error: {str(e)}"

# --- Streamlit UI ---
st.title("🗣️ Text ↔ Speech with Optional AI Music 🎵")

tab1, tab2 = st.tabs(["🔊 Text to Speech", "🎙️ Speech to Text"])

# Tab 1: Text to Speech
with tab1:
    user_text = st.text_area("Enter your text here:")
    add_music = st.checkbox("Add simple background music?")

    if st.button("Generate Audio"):
        if user_text:
            with st.spinner("Generating speech..."):
                speech_audio = text_to_speech(user_text)

            if isinstance(speech_audio, AudioSegment):
                music_audio = AudioSegment.silent(duration=0)
                if add_music:
                    with st.spinner("Generating simple musical phrase..."):
                        musical_text = generate_musical_text(user_text)
                        st.info(f"Generated Musical Text: {musical_text}")
                        with st.spinner("Generating background music..."):
                            music_audio = generate_sine_wave(musical_text)

                with st.spinner("Combining audio..."):
                    final_audio_bytes = combine_audio(speech_audio, music_audio)

                if isinstance(final_audio_bytes, bytes):
                    st.audio(final_audio_bytes, format="audio/mp3")
                    b64 = base64.b64encode(final_audio_bytes).decode()
                    href = f'<a href="data:audio/mp3;base64,{b64}" download="spoken_music.mp3">📥 Download MP3</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error(final_audio_bytes)
            else:
                st.error(speech_audio)
        else:
            st.warning("Please enter some text.")

# Tab 2: Speech to Text
with tab2:
    uploaded_file = st.file_uploader("Upload an audio file (MP3 or WAV)", type=["mp3", "wav"])
    if uploaded_file and st.button("Convert to Text"):
        with st.spinner("Transcribing..."):
            text_result = speech_to_text(uploaded_file)
            st.success("Transcription Complete:")
            st.write(text_result)
