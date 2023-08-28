import streamlit as st
import assemblyai as aai
from io import BytesIO
import requests
import tempfile
from moviepy.editor import *
from pydub import AudioSegment
import yt_dlp
import numpy as np
import threading

assemblyai_api_key = st.secrets['assemblyai_api_key']
aai.settings.api_key = assemblyai_api_key

st.title("University Lecture Q&A Chat App")

input_type = st.selectbox("Select input type", ["Video", "Audio", "YouTube"])

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

if "recording" not in st.session_state:
    st.session_state.recording = False

uploaded_file = st.file_uploader("Upload your file", type=['mp4', 'mp3', 'wav'])

audio_data = None
transcript = None

def extract_audio_from_video(video_file):
    with tempfile.NamedTemporaryFile(suffix=".mp4") as temp_video_file:
        temp_video_file.write(video_file.read())
        temp_video_file.flush()
        video = VideoFileClip(temp_video_file.name)
        audio = video.audio

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio_file:
        temp_audio_file_name = temp_audio_file.name
        audio.write_audiofile(temp_audio_file_name, codec='mp3')

    with open(temp_audio_file_name, 'rb') as temp_audio_file:
        audio_data = BytesIO(temp_audio_file.read())

    os.remove(temp_audio_file_name)
    audio_data.seek(0)
    return audio_data


def upload_file_to_assemblyai(file_data):
    response = requests.post(
        'https://api.assemblyai.com/v2/upload',
        headers={'authorization': assemblyai_api_key},
        files={'file': file_data}
    )
    return response.json()['upload_url']

def process_audio_with_lemur(transcript, questions):
    lemurs_response = transcript.lemur.question(questions)
    return lemurs_response

def download_youtube_audio(youtube_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': 'temp_audio.%(ext)s',
    }

    with st.spinner("Processing YouTube video..."):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])

    with open('temp_audio.mp3', 'rb') as audio_file:
        audio_data = BytesIO(audio_file.read())

    os.remove('temp_audio.mp3')
    audio_data.seek(0)
    return audio_data


if not st.session_state.get("transcript"):
    st.session_state.transcript = None

if uploaded_file:
    if (input_type == "Video" and uploaded_file.type == "video/mp4") or (input_type == "Audio" and (uploaded_file.type == "audio/mpeg" or uploaded_file.type == "audio/x-wav")):
        if not st.session_state.transcript:
            st.write("File uploaded successfully!")

            if input_type == "Video":
                video_data = BytesIO(uploaded_file.getvalue())  # Convert UploadedFile to BytesIO
                video_data.seek(0)
                audio_data = extract_audio_from_video(video_data)
                audio_data.seek(0)
            else:
                audio_data = BytesIO(uploaded_file.getvalue())
                audio_data.seek(0)

            if audio_data:
                st.write("Transcription in progress...")
                audio_url = upload_file_to_assemblyai(audio_data)
                transcriber = aai.Transcriber()
                st.session_state.transcript = transcriber.transcribe(audio_url)
                st.write("Transcription complete, Q/A ready")
    else:
        st.write("Please upload only the selected file type")


if input_type == "YouTube":
    youtube_url = st.text_input("Enter YouTube video URL")
    if youtube_url:
        if not st.session_state.get("audio_data"):
            st.session_state.audio_data = download_youtube_audio(youtube_url)
            st.session_state.audio_data.seek(0)
        audio_data = st.session_state.audio_data

        if not st.session_state.get("transcript"):
            st.write("Transcription in progress...")
            audio_url = upload_file_to_assemblyai(audio_data)
            transcriber = aai.Transcriber()
            st.session_state.transcript = transcriber.transcribe(audio_url)
            st.write("Transcription complete, Q/A ready")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("What would you like to ask your upload?")

if user_input:
    # Add the user's question to the list of messages
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Fetch the response from Lemur
    lemurs_questions = [aai.LemurQuestion(question=msg["content"]) for msg in st.session_state.messages if msg["role"] == "user"]
    
    if lemurs_questions and st.session_state.transcript:  # Change this line
        lemurs_response = st.session_state.transcript.lemur.question(lemurs_questions)
        lemurs_answer = lemurs_response.response[-1].answer

        # Add the Lemur's answer to the list of messages
        st.session_state.messages.append({"role": "bot", "content": lemurs_answer})

# Display all the messages in the chat component
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.button("Reset"):
    st.session_state.transcript = None
    st.session_state.messages = []
    st.session_state.uploaded_file = None
    st.experimental_rerun()
    
