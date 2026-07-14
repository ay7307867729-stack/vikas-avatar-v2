import os
import json
from flask import Flask, render_template, request, jsonify
from groq import Groq

app = Flask(__name__)


# Load AI memory
def load_memory():
    try:
        with open("memory.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {}


memory = load_memory()

print(memory)


# Groq API connection
api_key = os.environ.get("GROQ_API_KEY")

if not api_key:
    print("GROQ_API_KEY missing")

client = Groq(
    api_key=api_key.strip()
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message")

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": f"""
Tum Vikas ke personal AI assistant ho.

Vikas ki memory:
{memory}

Hindi me friendly reply do.
"""
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        reply = response.choices[0].message.content

        return jsonify({
            "reply": reply
        })


    except Exception as e:
        import traceback
        traceback.print_exc()

        return jsonify({
            "reply": "Error: " + str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)