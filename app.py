from dotenv import load_dotenv
load_dotenv()
import os
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq
import io
import requests
from datetime import datetime
from user_agents import parse
from flask import send_file

# Optional Google Cloud Text-to-Speech. If not installed or not configured,
# the /tts endpoint will return an error and the client will fall back to
# browser SpeechSynthesis.
try:
    from google.cloud import texttospeech
except Exception:
    texttospeech = None

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_notification(message):
    if not BOT_TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message
        }, timeout=10)
    except Exception as e:
        print("Telegram Error:", e)


# Simple CORS for local testing to avoid browser "Failed to fetch" when
# the page is served from a different host/port during development.
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


# Load AI memory
def load_memory():
    try:
        with open("memory.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {}


def save_memory(data):
    try:
        with open("memory.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Failed to save memory:", str(e))


memory = load_memory()
if "history" not in memory:
    memory["history"] = []

print("Loaded memory:", memory)


# Groq API connection
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("GROQ_API_KEY missing. /chat endpoint will not work until it is set.")
    client = None
else:
    client = Groq(
        api_key=api_key.strip()
    )


@app.route("/")
def home():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    browser = request.user_agent.browser or "Unknown"
    platform = request.user_agent.platform or "Unknown"
    time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    message = f"""
🔔 New Visitor

🌐 IP: {ip}
📱 Device: {platform}
🌍 Browser: {browser}
🕒 Time: {time}
"""

    try:
        country = "Unknown"
        state = "Unknown"
        city = "Unknown"

        res = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)

        if res.status_code == 200:
            data = res.json()
            country = data.get("country", "Unknown")
            state = data.get("regionName", "Unknown")
            city = data.get("city", "Unknown")

        message += f"""
🌍 Country: {country}
🏛️ State: {state}
🏙️ City: {city}
"""

    except Exception as e:
        print(e)

    send_telegram_notification(message)

    return render_template("index.html")


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'app': 'vikas-avtar'})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message")

    try:
        if client is None:
            return jsonify({
                "reply": "Error: GROQ_API_KEY missing. Please set the environment variable and restart the server."
            }), 500

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"""
Tum Vikas Yadav ho.
Tum B.Com student ho KUK se.
Tumhara goal hai financially strong banna, technology aur AI seekhna, aur apna AI project banana.
Tum 3D avatar, AI chat, voice input/output, aur website integration par kaam kar rahe ho.
Tumne Python, Flask, HTML, CSS, JavaScript, Three.js, Blender, GitHub, aur Render seekha hai.
Tum discipline, fitness, aur apni personal improvement par dhyan dete ho.
Tumne pehle baatein ki thi ki tum kabhi kabhi halwai helper ka kaam bhi karte ho.

Vikas ki memory:
{json.dumps(memory, ensure_ascii=False, indent=2)}

Agar user tumse pehle poochta hai "Tum kaun ho?", ek baar bolo "Main Vikas hoon." uske baad phir sirf seedha jawab do.
Baar-baar apna parichay mat do. Simple, chhota, Hindi mein reply do.
Yadi user seedha sawaal poochta hai, toh seedha jawab de.
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        reply = response.choices[0].message.content

        # Save user message and assistant reply to memory history
        if message:
            memory_entry = {
                "user": message,
                "assistant": reply
            }
            memory["history"].append(memory_entry)
            save_memory(memory)

        return jsonify({
            "reply": reply
        })


    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "reply": "Error: " + str(e)
        }), 500


@app.route('/tts', methods=['POST'])
def tts():
    data = request.json or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'no text provided'}), 400

    if texttospeech is None:
        return jsonify({'error': 'Text-to-Speech not configured on server'}), 500

    try:
        client = texttospeech.TextToSpeechClient()
        # Choose a natural Hindi female WaveNet voice.
        voice = texttospeech.VoiceSelectionParams(
            language_code='hi-IN',
            name='hi-IN-Wavenet-A',
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=1.02,
            pitch=2.0,
            sample_rate_hertz=24000,
            effects_profile_id=["headphone-class-device"]
        )

        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

        audio_bytes = response.audio_content
        return send_file(io.BytesIO(audio_bytes), mimetype='audio/wav', download_name='speech.wav')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    # Use PORT from environment (Render and other platforms set this).
    port = int(os.environ.get("PORT", 5000))
    # Allow disabling debug via FLASK_DEBUG env var
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)