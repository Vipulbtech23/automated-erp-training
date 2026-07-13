import json
import hashlib
import streamlit as st


def speak(
    text,
    label="🔊 Play Voice",
    rate=1.0,
    pitch=1.0,
    volume=1.0,
    key=None,
):
    """
    Browser Text-to-Speech for Streamlit.

    Works on:
    - Local Streamlit
    - Streamlit Cloud
    - Admin dashboard
    - Student dashboard

    Notes:
    - `key` is accepted for compatibility with dashboard calls.
    - `st.components.v1.html()` does NOT support a key argument,
      so key is used only to generate unique HTML element IDs.
    """

    if text is None:
        return

    clean_text = str(text).strip()

    if not clean_text:
        return

    safe_text = json.dumps(clean_text)
    safe_label = json.dumps(str(label))

    if key is None:
        unique_id = hashlib.md5(
            clean_text.encode("utf-8")
        ).hexdigest()[:12]
    else:
        unique_id = hashlib.md5(
            str(key).encode("utf-8")
        ).hexdigest()[:12]

    play_id = f"play_{unique_id}"
    stop_id = f"stop_{unique_id}"
    status_id = f"status_{unique_id}"

    try:
        speech_rate = float(rate)
    except (TypeError, ValueError):
        speech_rate = 1.0

    try:
        speech_pitch = float(pitch)
    except (TypeError, ValueError):
        speech_pitch = 1.0

    try:
        speech_volume = float(volume)
    except (TypeError, ValueError):
        speech_volume = 1.0

    speech_rate = max(0.1, min(speech_rate, 10.0))
    speech_pitch = max(0.0, min(speech_pitch, 2.0))
    speech_volume = max(0.0, min(speech_volume, 1.0))

    component_html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">

        <style>
            * {{
                box-sizing: border-box;
                font-family: Arial, Helvetica, sans-serif;
            }}

            body {{
                margin: 0;
                padding: 4px;
                background: transparent;
            }}

            .speech-box {{
                width: 100%;
                display: flex;
                align-items: center;
                gap: 9px;
                flex-wrap: wrap;
            }}

            button {{
                border: none;
                padding: 10px 16px;
                border-radius: 10px;
                cursor: pointer;
                font-size: 13px;
                font-weight: 700;
                transition:
                    transform 0.2s ease,
                    box-shadow 0.2s ease,
                    opacity 0.2s ease;
            }}

            button:hover {{
                transform: translateY(-1px);
            }}

            button:disabled {{
                cursor: not-allowed;
                opacity: 0.65;
                transform: none;
            }}

            .play-button {{
                color: white;
                background: linear-gradient(
                    135deg,
                    #0077cc,
                    #00a5c8
                );
                box-shadow:
                    0 7px 16px rgba(0, 119, 204, 0.25);
            }}

            .stop-button {{
                color: #8b1e1e;
                background: #ffe8e8;
                border: 1px solid #ffcaca;
            }}

            .speech-status {{
                min-width: 90px;
                color: #60758a;
                font-size: 12px;
            }}
        </style>
    </head>

    <body>
        <div class="speech-box">

            <button
                id="{play_id}"
                class="play-button"
                type="button"
            ></button>

            <button
                id="{stop_id}"
                class="stop-button"
                type="button"
            >
                ⏹ Stop
            </button>

            <span
                id="{status_id}"
                class="speech-status"
            >
                Ready
            </span>

        </div>

        <script>
            const speechText = {safe_text};
            const buttonLabel = {safe_label};

            const playButton =
                document.getElementById("{play_id}");

            const stopButton =
                document.getElementById("{stop_id}");

            const statusText =
                document.getElementById("{status_id}");

            playButton.textContent = buttonLabel;

            function getPreferredVoice() {{
                const voices =
                    window.speechSynthesis.getVoices();

                if (!voices || voices.length === 0) {{
                    return null;
                }}

                return (
                    voices.find(
                        voice => voice.lang === "en-IN"
                    )
                    ||
                    voices.find(
                        voice => voice.lang === "hi-IN"
                    )
                    ||
                    voices.find(
                        voice =>
                            voice.lang &&
                            voice.lang.startsWith("en")
                    )
                    ||
                    voices[0]
                );
            }}

            function playSpeech() {{
                if (!("speechSynthesis" in window)) {{
                    statusText.textContent =
                        "Not supported";

                    return;
                }}

                window.speechSynthesis.cancel();

                const speechMessage =
                    new SpeechSynthesisUtterance(
                        speechText
                    );

                speechMessage.rate = {speech_rate};
                speechMessage.pitch = {speech_pitch};
                speechMessage.volume = {speech_volume};
                speechMessage.lang = "en-IN";

                const selectedVoice =
                    getPreferredVoice();

                if (selectedVoice) {{
                    speechMessage.voice =
                        selectedVoice;
                }}

                speechMessage.onstart = () => {{
                    statusText.textContent =
                        "Speaking...";

                    playButton.disabled = true;
                }};

                speechMessage.onend = () => {{
                    statusText.textContent =
                        "Completed";

                    playButton.disabled = false;
                }};

                speechMessage.onerror = (event) => {{
                    console.error(
                        "Speech error:",
                        event
                    );

                    statusText.textContent =
                        "Speech error";

                    playButton.disabled = false;
                }};

                window.speechSynthesis.speak(
                    speechMessage
                );
            }}

            playButton.addEventListener(
                "click",
                playSpeech
            );

            stopButton.addEventListener(
                "click",
                () => {{
                    if (
                        "speechSynthesis"
                        in window
                    ) {{
                        window.speechSynthesis.cancel();
                    }}

                    statusText.textContent =
                        "Stopped";

                    playButton.disabled = false;
                }}
            );

            if (
                "speechSynthesis"
                in window
            ) {{
                window.speechSynthesis.onvoiceschanged =
                    getPreferredVoice;
            }}
        </script>
    </body>
    </html>
    """

    # IMPORTANT:
    # st.components.v1.html() does not accept a key argument.
    st.components.v1.html(
        component_html,
        height=68,
        scrolling=False
    )