import io
import os
import time

import streamlit as st
import speech_recognition as sr
from dotenv import load_dotenv
from gtts import gTTS
from google import genai
from google.genai import types


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================
st.set_page_config(
    page_title="VoiceMate AI",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# 2. ENVIRONMENT + GEMINI CLIENT
# =========================================================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error(
        "Gemini API key not found. Add GEMINI_API_KEY=your_key "
        "to a .env file in the project folder, then restart Streamlit."
    )
    st.stop()

try:
    client = genai.Client(
        api_key=API_KEY,
        http_options=types.HttpOptions(timeout=60000),
    )
except Exception as exc:
    st.error(f"Could not initialize the Gemini client: {exc}")
    st.stop()

# Primary model first, followed by alternative supported models.
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.5-flash-lite",
]

# =========================================================
# 3. SESSION STATE
# =========================================================
defaults = {
    "messages": [],
    "pending_prompt": None,
    "last_audio_id": None,
    "last_failed_prompt": False,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# =========================================================
# 4. GEMINI + AUDIO HELPERS
# =========================================================
def build_gemini_history(messages):
    history = []
    for message in messages[-20:]:
        role = "user" if message["role"] == "user" else "model"
        history.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=message["content"])],
            )
        )
    return history


def is_temporary_api_error(exc):
    """Return True for errors that may succeed when retried."""
    error_text = str(exc).lower()
    return any(
        marker in error_text
        for marker in (
            "429", "500", "502", "503", "504",
            "resource_exhausted", "unavailable",
            "deadline", "timeout", "temporarily",
            "internal", "overloaded",
        )
    )


def generate_answer(messages):
    """
    Try each configured Gemini model.
    Temporary server/rate-limit errors get one short retry per model.
    """
    history = build_gemini_history(messages)
    last_error = None

    for model_name in MODELS:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=history,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    ),
                )

                answer = (response.text or "").strip()
                if answer:
                    return answer, model_name

                last_error = RuntimeError(
                    f"{model_name} returned an empty response."
                )
                break

            except Exception as exc:
                last_error = exc

                # Retry only errors likely to be temporary.
                if is_temporary_api_error(exc) and attempt == 0:
                    time.sleep(2)
                    continue

                # Try the next configured model.
                break

    return None, last_error


def make_speech(text):
    audio_buffer = io.BytesIO()
    gTTS(text=text, lang="en", slow=False).write_to_fp(audio_buffer)
    audio_buffer.seek(0)
    return audio_buffer.getvalue()


def recognize_audio(audio_bytes):
    recognizer = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
        audio = recognizer.record(source)
    return recognizer.recognize_google(audio, language="en-IN")


# =========================================================
# 5. AESTHETIC UI THEME
# =========================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

    :root {
        --vm-bg: #0b1020;
        --vm-panel: rgba(20, 28, 49, 0.82);
        --vm-border: rgba(148, 163, 184, 0.16);
        --vm-text: #edf2ff;
        --vm-muted: #9aa8c4;
        --vm-purple: #8b7cff;
        --vm-cyan: #42d6c7;
    }

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(105, 86, 255, 0.18), transparent 30%),
            radial-gradient(circle at 95% 12%, rgba(40, 210, 190, 0.10), transparent 27%),
            linear-gradient(145deg, #090e1b 0%, #10182b 52%, #0b1020 100%);
        color: var(--vm-text);
    }

    [data-testid="stHeader"] {
        background: rgba(9, 14, 27, 0.72);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111a30 0%, #0d1426 100%);
        border-right: 1px solid var(--vm-border);
    }

    [data-testid="stSidebar"] * {
        color: #e7ecff;
    }

    .block-container {
        max-width: 1120px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }

    .brand-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 13px;
        margin: 0.3rem 0 0.2rem;
    }

    .brand-icon {
        width: 54px;
        height: 54px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 18px;
        font-size: 27px;
        background: linear-gradient(135deg, #7868ff, #3acfc4);
        box-shadow: 0 10px 35px rgba(110, 98, 255, 0.28);
    }

    .brand-title {
        font-family: 'Space Grotesk', sans-serif;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.05;
        font-weight: 700;
        letter-spacing: -1.8px;
        color: #f5f7ff;
    }

    .brand-title span {
        background: linear-gradient(90deg, #a99cff, #55e0d1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .brand-subtitle {
        text-align: center;
        color: #9eabc5;
        font-size: 1rem;
        margin: 0.65rem 0 1.6rem;
    }

    .hero-card {
        border: 1px solid rgba(151, 163, 255, 0.20);
        border-radius: 24px;
        padding: 25px 28px;
        background:
            linear-gradient(120deg, rgba(112, 94, 255, 0.16), rgba(48, 203, 190, 0.08)),
            rgba(17, 26, 46, 0.82);
        box-shadow: 0 18px 55px rgba(0, 0, 0, 0.18);
        margin-bottom: 1.35rem;
    }

    .hero-eyebrow {
        color: #8fe4dc;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-bottom: 8px;
    }

    .hero-heading {
        font-family: 'Space Grotesk', sans-serif;
        color: #f5f7ff;
        font-size: clamp(1.35rem, 2.5vw, 2rem);
        font-weight: 700;
        letter-spacing: -0.7px;
        margin-bottom: 7px;
    }

    .hero-copy {
        color: #aab6cf;
        font-size: 0.96rem;
        line-height: 1.6;
        max-width: 680px;
    }

    .section-heading {
        color: #f0f3ff;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.12rem;
        font-weight: 700;
        margin: 0.5rem 0 0.65rem;
    }

    .feature-card {
        min-height: 105px;
        border: 1px solid var(--vm-border);
        border-radius: 17px;
        padding: 15px 16px;
        background: rgba(19, 28, 48, 0.72);
    }

    .feature-icon {
        font-size: 1.35rem;
        margin-bottom: 7px;
    }

    .feature-title {
        color: #eef2ff;
        font-weight: 700;
        font-size: 0.9rem;
    }

    .feature-copy {
        color: #93a1bd;
        font-size: 0.78rem;
        margin-top: 3px;
    }

    .empty-state {
        border: 1px dashed rgba(154, 168, 196, 0.28);
        border-radius: 22px;
        padding: 32px 20px;
        text-align: center;
        background: rgba(18, 27, 47, 0.45);
        margin: 0.6rem 0 1.2rem;
    }

    .empty-icon {
        font-size: 2.4rem;
        margin-bottom: 8px;
    }

    .empty-title {
        color: #f0f3ff;
        font-size: 1.12rem;
        font-weight: 700;
    }

    .empty-copy {
        color: #9aa8c4;
        font-size: 0.9rem;
        margin-top: 6px;
    }

    .stButton > button {
        border-radius: 12px;
        border: 1px solid rgba(155, 146, 255, 0.35);
        background: linear-gradient(110deg, #7565f5, #4b9fbd);
        color: white;
        font-weight: 700;
        min-height: 42px;
        transition: all 0.2s ease;
    }

    .stButton > button:hover {
        border-color: #a99cff;
        color: white;
        transform: translateY(-1px);
        box-shadow: 0 8px 24px rgba(103, 91, 238, 0.22);
    }

    [data-testid="stAudioInput"] {
        border: 1px solid var(--vm-border);
        border-radius: 18px;
        padding: 16px;
        background: rgba(18, 27, 47, 0.72);
    }

    [data-testid="stChatMessage"] {
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 18px;
        background: rgba(18, 27, 47, 0.68);
        padding: 14px 16px;
        margin-bottom: 12px;
    }

    [data-testid="stChatInput"] {
        border: 1px solid rgba(139, 124, 255, 0.35);
        border-radius: 18px;
        background: rgba(17, 26, 46, 0.95);
    }

    [data-testid="stChatInput"] textarea {
        color: #f4f6ff;
    }

    [data-testid="stMarkdownContainer"] p {
        line-height: 1.65;
    }

    [data-testid="stAudio"] {
        border-radius: 14px;
    }

    hr {
        border-color: rgba(148, 163, 184, 0.13);
    }

    .footer {
        color: #71809e;
        text-align: center;
        font-size: 0.8rem;
        padding-top: 1rem;
    }

    @media (max-width: 700px) {
        .block-container { padding-top: 1.2rem; }
        .hero-card { padding: 20px; }
        .brand-icon { width: 46px; height: 46px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 6. SIDEBAR
# =========================================================
with st.sidebar:
    st.markdown(
        """
        <div style="display:flex;align-items:center;gap:10px;margin:8px 0 16px;">
            <div style="font-size:25px;">🎙️</div>
            <div>
                <div style="font-weight:800;font-size:1.15rem;">VoiceMate AI</div>
                <div style="font-size:.75rem;color:#91a0bd;">YOUR VOICE. YOUR AI.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("### ✨ What you can do")
    st.markdown(
        """
        - 🎤 **Talk naturally** — record your voice
        - 📝 **Live transcription** — convert speech to text
        - 🤖 **AI conversations** — powered by Gemini
        - 🔊 **Listen back** — hear AI responses
        - 💬 **Chat memory** — continue your conversation
        """
    )
    st.divider()

    st.markdown("### 📊 Your session")
    st.metric("Messages", len(st.session_state.messages))
    st.caption("Conversation context is kept for this active session.")

    if st.button("🧹  Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_prompt = None
        st.session_state.last_audio_id = None
        st.session_state.last_failed_prompt = False
        st.rerun()

    st.divider()
    st.caption("Built with Streamlit · Gemini AI · Python")


# =========================================================
# 7. HEADER + HERO
# =========================================================
st.markdown(
    """
    <div class="brand-row">
        <div class="brand-icon">🎙️</div>
        <div class="brand-title">VoiceMate <span>AI</span></div>
    </div>
    <div class="brand-subtitle">
        A smarter way to speak, ask, learn and listen.
    </div>
    <div class="hero-card">
        <div class="hero-eyebrow">YOUR PERSONAL AI ASSISTANT</div>
        <div class="hero-heading">Just say it. VoiceMate gets it.</div>
        <div class="hero-copy">
            Ask questions using your voice or type a message below.
            Get helpful AI responses and listen to them whenever you like.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Feature highlights
feature_cols = st.columns(4)
features = [
    ("🎤", "Voice input", "Speak in English (India)"),
    ("⚡", "Smart answers", "Gemini-powered responses"),
    ("🔊", "Voice playback", "Listen to the reply"),
    ("💬", "Chat memory", "Keep the conversation going"),
]
for col, (icon, title, copy) in zip(feature_cols, features):
    with col:
        st.markdown(
            f"""
            <div class="feature-card">
                <div class="feature-icon">{icon}</div>
                <div class="feature-title">{title}</div>
                <div class="feature-copy">{copy}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.write("")


# =========================================================
# 8. VOICE INPUT
# =========================================================
st.markdown('<div class="section-heading">🎧 Talk to VoiceMate</div>', unsafe_allow_html=True)
st.caption("Press the microphone button, record your question, and submit the recording.")

audio_data = st.audio_input("Record your message")

if audio_data is not None:
    audio_bytes = audio_data.getvalue()
    audio_id = hash(audio_bytes)

    if audio_id != st.session_state.last_audio_id:
        st.session_state.last_audio_id = audio_id
        try:
            with st.spinner("Listening carefully and converting your speech..."):
                voice_text = recognize_audio(audio_bytes)

            st.success("Your voice has been converted into text.")
            st.info(f"**You said:** {voice_text}")
            st.session_state.pending_prompt = voice_text

        except sr.UnknownValueError:
            st.error("I couldn't understand that recording. Please try speaking clearly.")
        except sr.RequestError as exc:
            st.error(f"Speech recognition service is unavailable: {exc}")
        except Exception as exc:
            st.error(f"Audio processing error: {exc}")


# =========================================================
# 9. CONVERSATION
# =========================================================
st.divider()
st.markdown('<div class="section-heading">💬 Your conversation</div>', unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown(
        """
        <div class="empty-state">
            <div class="empty-icon">💡</div>
            <div class="empty-title">Your conversation starts here</div>
            <div class="empty-copy">
                Try asking: “Explain artificial intelligence in simple words”
                or record a question using the microphone above.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# =========================================================
# 10. TEXT INPUT + PROMPT PROCESSING
# =========================================================
typed_prompt = st.chat_input("Message VoiceMate...")

prompt = None
is_retry = False

if typed_prompt and typed_prompt.strip():
    prompt = typed_prompt.strip()
    st.session_state.pending_prompt = None
elif st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt.strip()
    st.session_state.pending_prompt = None

# Retry the last failed request without duplicating its user message.
if st.session_state.last_failed_prompt:
    if st.button("🔄 Retry the last question"):
        is_retry = True

# =========================================================
# 11. GEMINI RESPONSE
# =========================================================
if prompt or is_retry:
    if prompt:
        st.session_state.messages.append(
            {"role": "user", "content": prompt}
        )
        st.session_state.last_failed_prompt = False

        with st.chat_message("user"):
            st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("VoiceMate is thinking..."):
            answer, result = generate_answer(st.session_state.messages)

        if answer:
            st.markdown(answer)
            st.caption(f"✦ Answered with {result}")

            st.session_state.messages.append(
                {"role": "assistant", "content": answer}
            )
            st.session_state.last_failed_prompt = False

            try:
                with st.spinner("Preparing your audio response..."):
                    speech_audio = make_speech(answer)
                st.markdown("**🔊 Listen to this response**")
                st.audio(speech_audio, format="audio/mp3")
            except Exception as exc:
                st.warning(
                    "The text response is ready, but audio could not be "
                    f"generated: {exc}"
                )

        else:
            st.session_state.last_failed_prompt = True
            st.warning(
                "Gemini is temporarily busy or the API quota may have "
                "been reached. Your question is kept in this conversation. "
                "Please wait a little and use the Retry button."
            )
            if result:
                with st.expander("Technical details"):
                    st.code(str(result))

# =========================================================
# 12. FOOTER
# =========================================================
st.markdown(
    """
    <div class="footer">
        🎙️ VoiceMate AI &nbsp;·&nbsp; Powered by Gemini
        <br>Made for conversations that feel natural.
    </div>
    """,
    unsafe_allow_html=True,
)
