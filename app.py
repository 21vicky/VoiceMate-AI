import streamlit as st
import speech_recognition as sr
import google.genai as genai
from google.genai import types
from gtts import gTTS
from dotenv import load_dotenv
import os
import io


# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="VoiceMate AI",
    page_icon="🎙️",
    layout="wide"
)


# ==========================================
# 2. LOAD ENVIRONMENT VARIABLES
# ==========================================

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("Gemini API Key not found. Check your .env file.")
    st.stop()


# ==========================================
# 3. GEMINI CONFIGURATION
# ==========================================

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(timeout=30000)
)

MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash"
]


# ==========================================
# 4. SESSION STATE
# ==========================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

if "last_audio_id" not in st.session_state:
    st.session_state.last_audio_id = None


# ==========================================
# 5. CUSTOM UI
# ==========================================

st.markdown("""
<style>

.main-title {
    text-align: center;
    font-size: 42px;
    font-weight: bold;
    color: #6C63FF;
}

.subtitle {
    text-align: center;
    color: gray;
    font-size: 17px;
    margin-bottom: 30px;
}

.stButton > button {
    border-radius: 10px;
    font-weight: bold;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# 6. HEADER
# ==========================================

st.markdown(
    '<div class="main-title">🎙️ VoiceMate AI</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Your Personal AI Voice Assistant'
    '</div>',
    unsafe_allow_html=True
)


# ==========================================
# 7. SIDEBAR
# ==========================================

with st.sidebar:

    st.title("🎙️ VoiceMate AI")

    st.write("Your intelligent AI-powered voice assistant.")

    st.divider()

    st.subheader("✨ Features")

    st.write("🎤 Voice Recognition")
    st.write("📝 Speech-to-Text")
    st.write("🤖 Gemini AI Responses")
    st.write("🔊 Text-to-Speech")
    st.write("💬 Conversation Memory")

    st.divider()

    if st.button("🧹 Clear Chat", use_container_width=True):

        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.session_state.last_audio_id = None

        st.rerun()

    st.caption("Built with Python, Streamlit & Gemini AI")


# ==========================================
# 8. VOICE INPUT
# ==========================================

st.subheader("🎤 Speak to VoiceMate AI")

audio_data = st.audio_input("Record your voice")

if audio_data is not None:

    audio_id = hash(audio_data.getvalue())

    if audio_id != st.session_state.last_audio_id:

        st.session_state.last_audio_id = audio_id

        try:

            recognizer = sr.Recognizer()

            with sr.AudioFile(
                io.BytesIO(audio_data.getvalue())
            ) as source:

                audio = recognizer.record(source)

            with st.spinner("Converting speech into text..."):

                voice_text = recognizer.recognize_google(
                    audio,
                    language="en-IN"
                )

            st.success("Speech recognized successfully!")

            st.write("**You said:**", voice_text)

            st.session_state.pending_prompt = voice_text

        except sr.UnknownValueError:

            st.error("Sorry, I couldn't understand your voice.")

        except sr.RequestError:

            st.error("Speech recognition service is unavailable.")

        except Exception as e:

            st.error(f"Voice Recognition Error: {e}")


# ==========================================
# 9. DISPLAY CHAT HISTORY
# ==========================================

st.divider()

st.subheader("💬 Conversation")

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# ==========================================
# 10. TEXT INPUT
# ==========================================

typed_prompt = st.chat_input(
    "Type your question here..."
)


# ==========================================
# 11. PROCESS USER PROMPT
# ==========================================

prompt = None

if typed_prompt:

    prompt = typed_prompt

    # Typed input takes priority over pending voice input.
    st.session_state.pending_prompt = None

elif st.session_state.pending_prompt:

    prompt = st.session_state.pending_prompt

    st.session_state.pending_prompt = None


# ==========================================
# 12. GEMINI AI RESPONSE
# ==========================================

if prompt:

    # Save user message

    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    with st.chat_message("user"):

        st.markdown(prompt)

    with st.chat_message("assistant"):

        answer = None

        # ==================================
        # BUILD CONVERSATION HISTORY
        # ==================================

        chat_history = []

        for message in st.session_state.messages:

            role = (
                "user"
                if message["role"] == "user"
                else "model"
            )

            chat_history.append({
                "role": role,
                "parts": [
                    {"text": message["content"]}
                ]
            })

        # ==================================
        # GEMINI MODEL FALLBACK
        # ==================================

        for model in MODELS:

            try:

                with st.spinner(
                    f"VoiceMate AI is thinking... ({model})"
                ):

                    response = client.models.generate_content(
                        model=model,
                        contents=chat_history
                    )

                    answer = response.text

                if answer:
                    st.success(
                        f"Connected successfully using {model}!"
                    )
                    break

            except Exception as e:

                st.warning(f"{model} is unavailable.")

                st.code(str(e))

        # ==================================
        # DISPLAY AI RESPONSE
        # ==================================

        if answer:

            st.markdown(answer)

            # ==================================
            # TEXT-TO-SPEECH
            # ==================================

            st.divider()

            st.subheader("🔊 Listen to the Answer")

            try:

                with st.spinner("Generating voice..."):

                    tts = gTTS(
                        text=answer,
                        lang="en",
                        slow=False
                    )

                    audio_fp = io.BytesIO()

                    tts.write_to_fp(audio_fp)

                    audio_fp.seek(0)

                st.audio(
                    audio_fp,
                    format="audio/mp3"
                )

            except Exception as e:

                st.warning(f"Text-to-Speech Error: {e}")

            # Save assistant response

            st.session_state.messages.append({
                "role": "assistant",
                "content": answer
            })

        else:

            st.error(
                "All Gemini models are currently unavailable. "
                "Please try again later."
            )


# ==========================================
# 13. FOOTER
# ==========================================

st.divider()

st.markdown(
    "<center>🚀 VoiceMate AI | Powered by Gemini AI</center>",
    unsafe_allow_html=True
)