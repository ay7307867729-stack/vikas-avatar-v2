# app.py
from dotenv import load_dotenv
load_dotenv()

import os
import json
import io
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, make_response

# Optional imports
try:
    from user_agents import parse as parse_ua
except Exception:
    parse_ua = None

try:
    from google.cloud import texttospeech
except Exception:
    texttospeech = None

# Groq client (import may raise if package missing)
try:
    from groq import Groq
except Exception:
    Groq = None

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vikas-avatar")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or None
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or None
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or None

# Initialize Groq client safely
client = None
if GROQ_API_KEY and Groq is not None:
    try:
        client = Groq(api_key=GROQ_API_KEY.strip())
        logger.info("GROQ client initialized")
    except Exception as e:
        logger.warning("Failed to initialize GROQ client: %s", e)
else:
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set; /chat will return an error")
    if Groq is None:
        logger.warning("groq package not available; /chat will return an error")

# Memory helpers
MEMORY_FILE = "memory.json"

def load_memory():
    try:
        if not os.path.exists(MEMORY_FILE):
            default = {"history": []}
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load memory: %s", e)
        return {"history": []}

def save_memory(data):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save memory: %s", e)

memory = load_memory()

# Telegram notification helper (optional)
def send_telegram_notification(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        logger.warning("Telegram Error: %s", e)

# Geo lookup helper (best-effort)
def lookup_geo(ip: str):
    if not ip:
        return {"country": "Unknown", "state": "Unknown", "city": "Unknown"}

    services = [
        {"url": f"https://ipwhois.app/json/{ip}", "map": {"country": "country", "state": "region", "city": "city"}, "success_key": "success"},
        {"url": f"https://ipinfo.io/{ip}/json", "map": {"country": "country", "state": "region", "city": "city"}, "success_key": None},
        {"url": f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city", "map": {"country": "country", "state": "regionName", "city": "city"}, "success_key": "status", "success_value": "success"},
    ]

    for svc in services:
        try:
            res = requests.get(svc["url"], timeout=4)
            data = res.json()
            sk = svc.get("success_key")
            if sk:
                sv = svc.get("success_value")
                if sv:
                    if data.get(sk) != sv:
                        continue
                else:
                    if not data.get(sk):
                        continue
            return {
                "country": data.get(svc["map"]["country"], "Unknown"),
                "state": data.get(svc["map"]["state"], "Unknown"),
                "city": data.get(svc["map"]["city"], "Unknown"),
            }
        except Exception:
            continue
    return {"country": "Unknown", "state": "Unknown", "city": "Unknown"}

# Simple CORS handling and OPTIONS support
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    return response

@app.route("/", methods=["GET", "OPTIONS"])
def home():
    if request.method == "OPTIONS":
        return make_response("", 204)

    ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or request.remote_addr
    if ip and "," in ip:
        ip = ip.split(",")[0].strip()

    ua_string = request.headers.get("User-Agent", "")
    if parse_ua:
        try:
            ua = parse_ua(ua_string)
            browser = ua.browser.family or "Unknown"
            device = ua.device.family or "Unknown"
            platform = ua.os.family or "Unknown"
        except Exception:
            browser = device = platform = "Unknown"
    else:
        browser = device = platform = "Unknown"

    time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    geo = lookup_geo(ip)

    message = (
        f"🔔 New Visitor\n\n"
        f"IP: {ip}\nDevice: {device}\nOS: {platform}\nBrowser: {browser}\nTime: {time}\n"
        f"Country: {geo['country']}\nState: {geo['state']}\nCity: {geo['city']}\n"
    )

    try:
        send_telegram_notification(message)
    except Exception:
        pass

    try:
        return render_template("index.html")
    except Exception:
        return "<h1>Vikas Avatar Backend</h1>", 200

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "vikas-avatar"})

# ---------------------------
# /chat route with system_prompt (Hindi) integrated
# ---------------------------
@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return make_response("", 204)

    data = request.get_json(silent=True) or {}
    message = data.get("message", "")
    if not isinstance(message, str):
        message = ""
    message = message.strip()

    if not message:
        return jsonify({"reply": "Error: No message provided"}), 400

    if client is None:
        return jsonify({"reply": "Error: GROQ_API_KEY missing or Groq client not available"}), 500

    try:
        # Trim memory for prompt safety
        memory.setdefault("history", [])
        if len(memory["history"]) > 10:
            memory["history"] = memory["history"][-10:]

        # Build runtime system prompt (Hindi) using the user's provided rules
        memory_json = json.dumps(memory, ensure_ascii=False, indent=2)

        system_prompt = (
            "Tum Vikas Yadav ke personal AI assistant ho.\n\n"
            "Neeche di gayi memory tumhari permanent memory hai.\n\n"
            f"{memory_json}\n\n"
            "Rules:\n\n"
            "1. Memory me jo likha hai wahi sach hai.\n"
            "2. Agar user Zainab, Special Person, Vikas, Goal, Skills ya memory me maujood kisi bhi cheez ke baare me pooche, to sirf memory ke hisaab se jawab do.\n"
            "3. Agar memory me information hai to apni training ya internet ki information bilkul mat use karo.\n"
            "4. Agar memory me information nahi hai to bolo:\n"
            '   "Mujhe iske baare me memory me koi jankari nahi mili."\n'
            "5. Hamesha Hindi me natural jawab do.\n"
            "6. Baar-baar apna introduction mat do.\n"
        )

        # Call the model
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
        )

        # Safely extract reply
        try:
            reply = response.choices[0].message.content
        except Exception:
            reply = getattr(response, "text", "") or "Error: Invalid response from model"

        # Save to memory and persist (keep memory file reasonably sized)
        memory.setdefault("history", []).append({"user": message, "assistant": reply})
        if len(memory["history"]) > 50:
            memory["history"] = memory["history"][-50:]
        save_memory(memory)

        return jsonify({"reply": reply})

    except Exception as e:
        logger.exception("Chat error")
        return jsonify({"reply": "Error: " + str(e)}), 500

# ---------------------------
# /tts route (optional)
# ---------------------------
@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400

    if texttospeech is None:
        return jsonify({"error": "Text-to-Speech not configured on server"}), 500

    try:
        tts_client = texttospeech.TextToSpeechClient()
        voice = texttospeech.VoiceSelectionParams(
            language_code="hi-IN",
            name="hi-IN-Neural2-B",
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            speaking_rate=1.02,
            pitch=2.0,
            sample_rate_hertz=24000
        )
        synthesis_input = texttospeech.SynthesisInput(text=text)
        response = tts_client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        audio_bytes = response.audio_content
        return send_file(io.BytesIO(audio_bytes), mimetype="audio/wav", download_name="speech.wav")
    except Exception as e:
        logger.exception("TTS error")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    logger.info("Starting app on port %s (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
