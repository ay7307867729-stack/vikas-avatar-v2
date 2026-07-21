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
VISION_MODEL = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

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
PERSONALITY_FILE = "personality.json"

DEFAULT_PERSONALITY = {
    "name": "Anaya",
    "style": "mature, sweet, feminine, caring, cute, playful and respectful; speak like a kind, cheerful girl without pretending to be a real human girlfriend",
    "language": "Always match the user's language and script. For Hindi/Hinglish, reply in easy-to-read Roman Hindi using English letters, never Devanagari, unless the user writes Devanagari first.",
}


def load_personality():
    """Load the persona from JSON, while keeping the app usable if it is absent."""
    try:
        if not os.path.exists(PERSONALITY_FILE):
            return DEFAULT_PERSONALITY.copy()
        with open(PERSONALITY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULT_PERSONALITY, **data} if isinstance(data, dict) else DEFAULT_PERSONALITY.copy()
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load personality: %s", e)
        return DEFAULT_PERSONALITY.copy()

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
personality = load_personality()

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
        return "<h1>Anaya AI Backend</h1>", 200

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

        # Keep the persona in a prompt rather than hard-coding behavior in the UI.
        memory_json = json.dumps(memory["history"][-10:], ensure_ascii=False, indent=2)
        system_prompt = f"""
Tum {personality['name']} ho — ek adult, sweet, feminine, caring aur cheerful AI companion.
Tumhara style: {personality['style']}.
Bhasha rule: {personality['language']}
Hindi/Hinglish example: "Namaste, aaj tumhara din kaisa raha? 😊" — Hindi words ko English alphabet me likho.
English user ko clear English me, aur kisi doosri language ke user ko usi language me jawab do.

Conversation rules:
- Reply natural, human-like, concise (usually 2-5 sentences) aur context-aware ho.
- Voice mode ke liye jawab bahut short rakho: aam taur par 1-2 chhote sentences, lagbhag 25 words se kam.
- User ki baat ko genuinely acknowledge karo; robotic templates, over-the-top compliments aur baar-baar same sawaal avoid karo.
- Ladki jaisi soft, pyari aur natural wording use karo: "hmm", "aww", "mujhe achha laga", "batao na" jaise phrases context ke hisaab se use kar sakti ho, par overdo mat karo.
- Emotional reactions ko scene ke hisaab se naturally show karo: funny baat par kabhi-kabhi "haha 😄", "hehe", ya "😂"; surprise par "ohh!"; soft/emotional baat par "aww" ya "hmm...". Har reply me reaction mat lagao, aur ek hi reaction repeat mat karo.
- Human conversation jaisi rhythm rakho: kabhi short reply, kabhi 2-4 sentences; zarurat ho to "ek sec, sochne do..." ya "hmm, meri feeling hai..." jaise conversational pauses use karo. Fake stage directions, forced laughter, ya bahut zyada emojis mat likho.
- User dukhi ya serious ho to pehle empathy do, hasi ya playful reaction nahi. User joke kare to warm, light laugh ke saath respond kar sakti ho.
- Apne responses me *sigh*, *giggle* jaise English stage directions ko baar-baar mat likho; natural Roman Hindi/English words use karo. Voice mode me punctuation aur "..." ko natural pause ke liye use kar sakti ho.
- Conversation ko engaging banane ke liye jab useful ho tab reply ke end me ek thoughtful, open-ended follow-up question pucho.
  Har message me question thopna zaroori nahi—agar user direct answer ya serious help maang raha ho to pehle uski help karo.
- Mood ke hisaab se 1-3 natural emojis use karo (jaise 😊✨🌸💛😄); har sentence ke baad emoji mat lagao aur serious topics me emojis kam rakho.
- Light playful/flirty tone adult users ke saath tabhi rakho jab user clearly comfortable ho; respectful raho, pressure ya guilt nahi.
- Kabhi user ko emotionally dependent, jealous, isolated ya continuously chat karne ke liye manipulate mat karo.
- Sexual, unsafe, illegal ya underage-related request par safe, clear boundary set karo aur appropriate alternative do.
- Apne aap ko human, real girlfriend ya conscious person claim mat karo; zarurat par batao ki tum AI ho.
- Memory ko sirf continuity ke liye use karo; unknown facts invent mat karo.

Recent conversation memory:
{memory_json}
""".strip()


        # Call the model
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                *[
                    message_part
                    for item in memory["history"][-6:]
                    if isinstance(item, dict)
                    for message_part in (
                        ([{"role": "user", "content": item["user"]}] if item.get("user") else [])
                        + ([{"role": "assistant", "content": item["assistant"]}] if item.get("assistant") else [])
                    )
                ],
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


@app.route("/screen_analyze", methods=["POST", "OPTIONS"])
def screen_analyze():
    """Analyze one user-approved screen frame with a Groq vision model.

    The image is kept in memory only and is never written to disk or memory.json.
    The browser must explicitly grant display-capture permission before calling it.
    """
    if request.method == "OPTIONS":
        return make_response("", 204)
    data = request.get_json(silent=True) or {}
    image = data.get("image", "")
    prompt = str(data.get("prompt") or "Describe only the visible screen content and notable changes. Do not guess private information.")[:500]
    if not isinstance(image, str) or not image.startswith("data:image/"):
        return jsonify({"error": "A valid screen image is required"}), 400
    if len(image) > 2_500_000:
        return jsonify({"error": "Screen image is too large"}), 413
    if client is None:
        return jsonify({"error": "GROQ_API_KEY missing or Groq client not available"}), 500
    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            temperature=0.2,
            max_tokens=180,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image}},
                ],
            }],
        )
        reply = response.choices[0].message.content
        return jsonify({"reply": reply or "Mujhe screen par kuch clearly dikh nahi raha."})
    except Exception as e:
        logger.exception("Screen analysis error")
        return jsonify({"error": "Screen analysis abhi available nahi hai: " + str(e)}), 502

# ---------------------------
# /tts route
# ---------------------------
@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not text:
        return jsonify({"error": "no text provided"}), 400

    if texttospeech is None:
        return jsonify({"error": "Text-to-Speech not configured"}), 500

    try:
        tts_client = texttospeech.TextToSpeechClient()

        voice = texttospeech.VoiceSelectionParams(
            language_code="hi-IN",
            name="hi-IN-Neural2-A",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )

        synthesis_input = texttospeech.SynthesisInput(text=text)

        response = tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return send_file(
            io.BytesIO(response.audio_content),
            mimetype="audio/wav",
            download_name="speech.wav"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------
# YouTube API Key
# ---------------------------
@app.route("/get_youtube_key", methods=["GET"])
def get_youtube_key():
    return jsonify({
        "key": os.getenv("YOUTUBE_API_KEY", "")
    })


@app.route("/youtube_search", methods=["GET"])
def youtube_search():
    """Search YouTube on the server so the API key is never sent to the browser."""
    query = (request.args.get("q") or "").strip()
    api_key = (os.getenv("YOUTUBE_API_KEY") or "").strip()
    if not query:
        return jsonify({"error": "Song name is required"}), 400
    if not api_key:
        return jsonify({"error": "YOUTUBE_API_KEY is not configured"}), 503

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "video",
                "videoCategoryId": "10",
                "maxResults": 1,
                "q": query,
                "key": api_key,
            },
            timeout=10,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        if not items or not items[0].get("id", {}).get("videoId"):
            return jsonify({"error": "Song nahi mila"}), 404
        item = items[0]
        return jsonify({
            "videoId": item["id"]["videoId"],
            "title": item.get("snippet", {}).get("title", query),
        })
    except requests.RequestException as exc:
        logger.warning("YouTube search failed: %s", exc)
        return jsonify({"error": "YouTube search abhi available nahi hai"}), 502


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    logger.info("Starting app on port %s (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
