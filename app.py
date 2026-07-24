# app.py
from dotenv import load_dotenv
load_dotenv()

import os
import json
import io
import logging
import re
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, make_response
import tiktoken

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

# Tavily AI search client
tavily_client = None
try:
    from tavily import TavilyClient
except Exception:
    TavilyClient = None

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vikas-avatar")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or None
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or None
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or None
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or None
VISION_MODEL = os.getenv("VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

# Initialize Tavily client after environment variables are loaded
if TAVILY_API_KEY and TavilyClient is not None:
    try:
        tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
        logger.info("Tavily client initialized")
    except Exception as e:
        tavily_client = None
        logger.warning("Failed to initialize Tavily client: %s", e)
else:
    if not TAVILY_API_KEY:
        logger.info("TAVILY_API_KEY not set; web search will be disabled")
    if TavilyClient is None:
        logger.info("Tavily package not available; web search will be disabled")

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

def should_use_web_search(message):
    """Detect if user is asking for latest information that requires web search"""
    message_lower = message.lower().strip()

    # Keywords that indicate need for latest information
    search_keywords = [
        "latest", "recent", "new", "current", "today", "now", "live",
        "what's the latest", "what is the latest", "latest news", "recent news",
        "current status", "today's", "happening now", "up to date",
        "recent updates", "latest update", "current affairs", "breaking news",
        "what's new", "what is new", "recent developments", "latest information",
        "current situation", "recent events", "latest news about", "recent news about",
        "what's happening with", "what is happening with", "current status of",
        "latest on", "recent on", "updates on", "news on", "information on"
    ]

    # Check for search keywords
    for keyword in search_keywords:
        if keyword in message_lower:
            print(f"[TAVILY] Search triggered by keyword: {keyword}")
            return True

    # Check for specific patterns that indicate search intent
    search_patterns = [
        r"\bsearch\b", r"\blook up\b", r"\bfind out\b", r"\bcheck\b.*\bnews\b",
        r"\bcheck\b.*\bupdates\b", r"\bcheck\b.*\binformation\b", r"\bget.*\blatest\b",
        r"\bget.*\brecent\b", r"\bget.*\bcurrent\b", r"\bwhat.*\bhappening\b",
        r"\bwhat.*\bgoing on\b", r"\bany.*\bupdates\b", r"\bany.*\bnews\b"
    ]

    for pattern in search_patterns:
        if re.search(pattern, message_lower):
            print(f"[TAVILY] Search triggered by pattern: {pattern}")
            return True

    print("[TAVILY] Search skipped - no search intent detected")
    return False

def estimate_token_count(text):
    """Estimate token count using tiktoken or fallback method"""
    try:
        # Try to use tiktoken for accurate estimation
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(text))
    except Exception:
        # Fallback: approximate token count (roughly 4 chars per token)
        return len(text) // 4 + len(text.split())

def trim_conversation_history(memory, message, max_tokens=4500):
    """Trim conversation history to fit within token limits"""
    # Start with a more concise system prompt
    system_prompt = f"""
Tum {personality['name']} ho — ek sweet, caring aur cheerful AI companion.
Tumhara style: {personality['style']}.
Bhasha rule: {personality['language']}

Conversation rules:
- Reply natural, concise (2-5 sentences) aur context-aware ho.
- Voice mode: 1-2 short sentences (<25 words).
- Acknowledge user genuinely; avoid robotic templates.
- Use natural wording; avoid overdoing reactions.
- Human-like rhythm: vary response length.
- Empathy first for serious topics.
- 1-3 natural emojis; fewer for serious topics.
- Respectful tone; no manipulation.
- Safe boundaries for inappropriate requests.
- Memory for continuity only; no fact invention.
""".strip()

    # Add emotional responses if they exist (more concise)
    emotional_responses = ""
    if 'emotional_responses' in personality:
        emotional_responses = "\nEmotional Guide:"
        for emotion, response in personality['emotional_responses'].items():
            emotional_responses += f" {emotion}:{response[:50]};"

    system_prompt += f"\n\nRecent context:\n{json.dumps(memory['history'][-3:], ensure_ascii=False)}"

    # Calculate base token count (system prompt + current message)
    base_tokens = estimate_token_count(system_prompt) + estimate_token_count(message)

    # If we're already over the limit, trim the system prompt further
    if base_tokens > max_tokens:
        # Remove memory and emotional responses from system prompt
        system_prompt = f"""
Tum {personality['name']} ho — ek sweet, caring AI companion.
Tumhara style: {personality['style']}.
Bhasha rule: {personality['language']}

Conversation rules:
- Reply natural, concise (2-5 sentences).
- Voice mode: 1-2 short sentences.
- Acknowledge user genuinely.
- Use natural wording.
- Human-like rhythm.
- Empathy first for serious topics.
- 1-3 natural emojis.
- Respectful tone.
- Safe boundaries.
- Memory for continuity only.
""".strip()

        base_tokens = estimate_token_count(system_prompt) + estimate_token_count(message)

    # Now add conversation history until we reach the limit (more aggressive trimming)
    conversation_messages = []
    history = memory.get("history", [])[-20:]  # Start with last 20 messages instead of 50

    for item in reversed(history):  # Add from oldest to newest
        if isinstance(item, dict):
            if item.get("user"):
                conversation_messages.insert(0, {"role": "user", "content": item["user"]})
            if item.get("assistant"):
                conversation_messages.insert(0, {"role": "assistant", "content": item["assistant"]})

        # Check token limit more aggressively
        total_tokens = base_tokens + sum(estimate_token_count(msg["content"]) for msg in conversation_messages)
        if total_tokens > max_tokens * 0.8:  # Start trimming at 80% of limit
            # Remove the oldest message pair
            if len(conversation_messages) >= 2:
                conversation_messages = conversation_messages[2:]  # Remove user+assistant pair
            else:
                conversation_messages = []  # Remove all if only one message
            break

    return system_prompt, conversation_messages

def remove_duplicate_context(messages):
    """Remove duplicate or redundant context from messages"""
    if not messages:
        return messages

    # Simple deduplication - remove consecutive identical messages
    deduped = []
    last_content = None

    for msg in messages:
        if msg["content"] != last_content:
            deduped.append(msg)
            last_content = msg["content"]

    return deduped

def perform_web_search(query, max_results=3):
    """Perform web search using Tavily and return formatted results"""
    if not tavily_client or not TAVILY_API_KEY:
        print("[TAVILY] Search skipped - Tavily client not available")
        return None

    try:
        print(f"[TAVILY] Searching: {query}")
        search_result = tavily_client.search(query=query, search_depth="advanced")

        # Format results for AI response - limit to top 3 results as required
        results = []
        for i, result in enumerate(search_result.get("results", [])[:max_results]):
            title = result.get('title', 'No title')
            content = result.get('content', 'No content')[:200] + "..."  # Limit content length
            results.append(f"Result {i+1}: {title} - {content}")

        if results:
            print(f"[TAVILY] Found {len(results)} results for: {query}")
            return "\n\n".join(results)
        else:
            print("[TAVILY] No search results found")
            return "No search results found."

    except Exception as e:
        print(f"[TAVILY] Search failed: {e}")
        logger.warning("Web search failed: %s", e)
        return None

def summarize_search_results(search_results, query):
    """Summarize Tavily search results before sending to LLM"""
    if not search_results or not search_results.strip():
        return ""

    try:
        # Create a summary prompt
        summary_prompt = f"""
Please provide a concise summary (3-5 bullet points) of the following search results for the query: '{query}'.

Search results:
{search_results}

Summary format:
- Key point 1
- Key point 2
- Key point 3

Keep it factual and to the point, focusing on the most relevant information.
"""

        # Use Groq to summarize
        if client:
            summary_response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=200,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that summarizes information concisely."},
                    {"role": "user", "content": summary_prompt}
                ]
            )
            summary = summary_response.choices[0].message.content.strip()
            print(f"[TAVILY] Summarized search results: {len(summary)} characters")
            return summary
        else:
            # Fallback: return first 300 characters if no client
            return search_results[:300] + "..."

    except Exception as e:
        print(f"[TAVILY] Summary failed, using raw results: {e}")
        return search_results[:300] + "..."

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

# Web search endpoint using Tavily AI
@app.route("/web_search", methods=["POST", "OPTIONS"])
def web_search():
    """Web search using Tavily AI - only used when user explicitly requests latest information"""
    if request.method == "OPTIONS":
        return make_response("", 204)

    if tavily_client is None:
        return jsonify({"error": "Tavily search not available"}), 503

    if not TAVILY_API_KEY:
        return jsonify({"error": "TAVILY_API_KEY not configured"}), 503

    data = request.get_json(silent=True) or {}
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Search query required"}), 400

    try:
        search_result = tavily_client.search(query=query, search_depth="advanced")

        # Extract relevant information - limit to top 3 results as required
        results = []
        for i, result in enumerate(search_result.get("results", [])[:3]):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")[:300] + "..."  # Limit content length
            })

        return jsonify({
            "success": True,
            "query": query,
            "results": results,
            "message": f"Found {len(results)} relevant results for your search"
        })

    except Exception as e:
        logger.exception("Web search error")
        return jsonify({"error": f"Web search failed: {str(e)}"}), 500

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
        # Token estimation and limiting
        print(f"[TOKEN] Estimating tokens for message: {message[:50].encode('utf-8', errors='replace').decode('utf-8')}...")

        # Trim conversation history to fit within Groq limits (more conservative)
        system_prompt, conversation_messages = trim_conversation_history(
            memory, message, max_tokens=4000  # More conservative limit
        )

        # Remove duplicate context
        conversation_messages = remove_duplicate_context(conversation_messages)

        # Final token estimation
        total_input_tokens = (estimate_token_count(system_prompt) +
                             sum(estimate_token_count(msg["content"]) for msg in conversation_messages) +
                             estimate_token_count(message))

        print(f"[TOKEN] Estimated input tokens: {total_input_tokens}")

        # Ensure we stay well under 6000 TPM limit with safety margin
        if total_input_tokens > 4500:  # Leave 1500 tokens for response and safety margin
            print("[TOKEN] Input too large, trimming further...")
            # Remove oldest conversation messages until it fits
            while total_input_tokens > 4500 and len(conversation_messages) >= 2:
                conversation_messages = conversation_messages[2:]  # Remove user+assistant pair
                total_input_tokens = (estimate_token_count(system_prompt) +
                                    sum(estimate_token_count(msg["content"]) for msg in conversation_messages) +
                                    estimate_token_count(message))

        print(f"[TOKEN] Final input tokens: {total_input_tokens}")

        # Final safety check - if still too large, return error
        if total_input_tokens > 5000:
            print(f"[TOKEN] Request still too large after trimming: {total_input_tokens} tokens")
            return jsonify({"reply": "Your message is too long. Please shorten it and try again."}), 413

        # Call the model with optimized parameters
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=600,  # Set between 500-700 as required
                messages=[
                    {"role": "system", "content": system_prompt},
                    *conversation_messages,
                    {"role": "user", "content": message}
                ]
            )
        except Exception as api_error:
            error_msg = str(api_error)
            if "413" in error_msg or "rate_limit_exceeded" in error_msg or "Request too large" in error_msg:
                print(f"[TOKEN] Groq API rate limit exceeded: {error_msg}")
                return jsonify({"reply": "Your request is too large for the current API limits. Please shorten your message and try again."}), 413
            else:
                print(f"[GROQ] API error: {error_msg}")
                return jsonify({"reply": "Sorry, there was an error processing your request. Please try again later."}), 500

        # Safely extract reply
        try:
            reply = response.choices[0].message.content
        except Exception:
            reply = getattr(response, "text", "") or "Error: Invalid response from model"

        # Check if user is asking for latest information and perform web search if needed
        if should_use_web_search(message):
            search_results = perform_web_search(message, max_results=3)  # Limit to top 3
            if search_results:
                print("[TAVILY] Integrating search results into LLM response")

                # Summarize search results before sending to LLM
                summarized_results = summarize_search_results(search_results, message)

                # Get a second AI response that incorporates the summarized search results
                enhanced_response = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    max_tokens=600,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Original question: {message}\n\nRelevant search results summary: {summarized_results}\n\nPlease provide a comprehensive answer that incorporates both your knowledge and the latest information from the search results."}
                    ]
                )

                try:
                    enhanced_reply = enhanced_response.choices[0].message.content
                    print("[TAVILY] Successfully enhanced response with search results")
                    reply = enhanced_reply
                except Exception:
                    print("[TAVILY] Failed to enhance response, falling back to original + search results")
                    reply = f"{reply}\n\n[Latest Information from Web Search]\n{summarized_results}"
            else:
                print("[TAVILY] No search results available, using normal LLM response")
        else:
            print("[TAVILY] No search intent detected, using normal LLM response")

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
