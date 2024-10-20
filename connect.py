import streamlit as st
import requests
import json
from google.cloud import speech_v1p1beta1 as speech
from pydub import AudioSegment
from google.cloud import texttospeech
import os
import subprocess
from moviepy.editor import VideoFileClip, AudioFileClip
from google.oauth2.service_account import Credentials
# from dotenv import load_dotenv



# Azure GPT-4o function
def get_gpt4o_correction(api_key, endpoint, transcription_text):
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }

    prompt = (
        "Please correct the grammatical mistakes in the following text without changing the original meaning or context: \n"
        f"{transcription_text}"
    )

    data = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150
    }

    response = requests.post(endpoint, headers=headers, json=data)

    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    else:
        return f"Error:{response.status_code}-{response.text}"

# Google Speech-to-Text function
def transcribe_audio(file_path):
    try:
        # Check if running on Render environment
        if os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_HOSTNAME"):
            # Load the JSON key from the environment variable
            google_creds = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
            print("Running on Render. Using provided Google credentials.")
            
            # Create credentials using the JSON content
            credentials = Credentials.from_service_account_info(google_creds)
            client = speech.SpeechClient(credentials=credentials)
        else:
            print("Not running on Render. Using default Google credentials.")
            client = speech.SpeechClient()  # Uses default application credentials

        audio = AudioSegment.from_file(file_path)
        audio = audio.set_channels(1)  # setting to mono

        mono_file_path = "mono_audio.wav"
        audio.export(mono_file_path, format="wav")

        # os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\AKS-VScode\credentials\video-audio-enhancement-61b6fb5e9a74.json"
        # client = speech.SpeechClient()

        with open(mono_file_path, "rb") as audio_file:
            content = audio_file.read()

        recognition_audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(language_code="en-US")

        response = client.recognize(config=config, audio=recognition_audio)
        transcription = " ".join([result.alternatives[0].transcript for result in response.results])

        os.remove(mono_file_path)
        return transcription

    except Exception as e:
        st.error(f"Error during transcription: {str(e)}")
        return ""

def generate_tts_audio(corrected_text, output_audio_path="corrected_audio.wav"):
    # Check if running on Render environment
    if os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        # Load the JSON key from the environment variable
        google_creds = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        print("Running on Render. Using provided Google credentials.")
        
        # Create credentials using the JSON content
        credentials = Credentials.from_service_account_info(google_creds)
        client = texttospeech.TextToSpeechClient(credentials=credentials)
    else:
        print("Not running on Render. Using default Google credentials.")
        client = texttospeech.TextToSpeechClient()  # Uses default application credentials

    
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name="en-US-Wavenet-C"
    )
    
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16
    )
    
    synthesis_input = texttospeech.SynthesisInput(text=corrected_text)

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    
    with open(output_audio_path, "wb") as out:
        out.write(response.audio_content)
    st.success(f"Corrected audio saved to {output_audio_path}")

def get_audio_duration(audio_path):
    audio = AudioFileClip(audio_path)
    duration = audio.duration  # Duration in seconds
    audio.close()
    # st.write(duration)
    return duration

# def adjust_audio_tempo(original_duration, corrected_audio_path, aligned_audio_path):
#     corrected_duration = get_audio_duration(corrected_audio_path)
#     tempo_ratio = original_duration / corrected_duration

#     command = [
#         "ffmpeg", "-i", corrected_audio_path,
#         "-filter:a", f"atempo={tempo_ratio:.2f}",
#         aligned_audio_path
#     ]
#     subprocess.run(command, check=True)
#     st.success(f"Aligned audio saved to {aligned_audio_path}")
def adjust_audio_tempo(original_duration, corrected_audio_path, aligned_audio_path):
    corrected_duration = get_audio_duration(corrected_audio_path)
    tempo_ratio = corrected_duration / original_duration  # Inverse ratio to slow down

    # Handle large tempo changes with multiple 'atempo' filters
    if 0.5 <= tempo_ratio <= 2.0:
        command = [
            "ffmpeg", "-i", corrected_audio_path,
            "-filter:a", f"atempo={tempo_ratio:.2f}",
            "-y", aligned_audio_path
        ]
    else:
        # Apply multiple atempo filters if ratio is outside 0.5 - 2.0 range
        filter_chain = []
        while tempo_ratio < 0.5 or tempo_ratio > 2.0:
            factor = min(max(tempo_ratio, 0.5), 2.0)  # Clamp between 0.5 and 2.0
            filter_chain.append(f"atempo={factor:.2f}")
            tempo_ratio /= factor  # Adjust for next iteration

        filter_string = ",".join(filter_chain)
        command = [
            "ffmpeg", "-i", corrected_audio_path,
            "-filter:a", filter_string,
            "-y", aligned_audio_path
        ]

    # Run the ffmpeg command
    subprocess.run(command, check=True)
    st.success(f"Aligned audio saved to {aligned_audio_path}")


def replace_audio_in_video(video_file_path, aligned_audio_file_path, output_video_file_path):
    if not os.path.isfile(video_file_path):
        raise FileNotFoundError(f"Video file not found: {video_file_path}")
    if not os.path.isfile(aligned_audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {aligned_audio_file_path}")
    command = [
        "ffmpeg", "-i", video_file_path, "-i", aligned_audio_file_path,
        "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
        output_video_file_path
    ]
    subprocess.run(command, check=True)
    st.success(f"New video with corrected audio saved to {output_video_file_path}")
    return output_video_file_path

def check_ffmpeg_installed():
    try:
        # run command to get FFmpeg version
        result=subprocess.run(['ffmpeg','-version'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)

        # if the command was successful ,return True
        if result.returncode==0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False

def main():
    st.title("AI-Powered Video Audio Correction")

    # Check if FFmpeg is installed
    if not check_ffmpeg_installed():
        st.error("FFmpeg is not installed or not found in your environment. Please install FFmpeg to use this application.")
        return  # Exit the main function if FFmpeg is not available
    else:
        st.write("installed")

     # Azure openAI connection details
    azure_openai_key = "22ec84421ec24230a3638d1b51e3a7dc"
    azure_openai_endpoint = "https://internshala.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-08-01-preview"



    if "transcription" not in st.session_state:
        st.session_state.transcription = ""
    if "corrected_text" not in st.session_state:
        st.session_state.corrected_text = ""
    if "final_video_path" not in st.session_state:
        st.session_state.final_video_path=None

    uploaded_file = st.file_uploader("Upload a video file", type=["mp4"])

    if uploaded_file is not None:
        file_path = "uploaded_file.mp4"

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if st.button("Transcribe Audio"):
            with st.spinner("Transcribing audio..."):
                st.session_state.transcription = transcribe_audio(file_path)

            if st.session_state.transcription.strip() == "":
                st.error("Transcription failed!")
            else:
                st.write("Initial transcription:", st.session_state.transcription)
        

        if st.session_state.transcription:
            if st.button("Correct Transcription with GPT-4o"):
                with st.spinner("Correcting transcription..."):
                    st.session_state.corrected_text = get_gpt4o_correction(
                        azure_openai_key, azure_openai_endpoint, st.session_state.transcription
                    )
                st.write("Initial transcription:", st.session_state.transcription)
                st.write("Corrected Transcription:", st.session_state.corrected_text)

            if st.session_state.corrected_text:
                if st.button("Replace Audio in Video"):
                    with st.spinner("Generating audio and replacing in video..."):
                        # Step 1: Generate corrected audio
                        st.write("error")
                        generate_tts_audio(st.session_state.corrected_text, "corrected_audio.wav")

                        # Step 2: Get the original audio duration
                        original_duration = get_audio_duration(file_path)

                        # Step 3: Adjust TTS audio tempo
                        adjust_audio_tempo(original_duration, "corrected_audio.wav", "aligned_audio.wav")

                        # Step 4: Replace audio in original video
                        st.session_state.final_video_path=replace_audio_in_video(file_path, "aligned_audio.wav", "final_video.mp4")

                        if st.session_state.final_video_path:
                            with open(st.session_state.final_video_path,"rb") as video_file:
                                st.download_button(
                                    label="Download Updated Video",
                                    data=video_file,
                                    file_name="SynchronizedAI_Video.mp4",
                                    mime="video/mp4"
                                )

if __name__ == "__main__":
    main()
