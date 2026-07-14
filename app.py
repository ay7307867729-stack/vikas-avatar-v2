import os
import json
from flask import Flask, render_template, request, jsonify

from groq import Groq

app = Flask(__name__)
def load_memory():
    try:
        with open("memory.json", "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {}


memory = load_memory()

print(memory)


# Apni Groq API key yaha paste karo
import os

import os

client = Groq(
    api_key=os.environ.get("GROQ_API_KEY")
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
    print("ERROR:", e)
    return jsonify({
        "error": str(e)
    }), 500


if __name__ == "__main__":
    app.run(debug=True)