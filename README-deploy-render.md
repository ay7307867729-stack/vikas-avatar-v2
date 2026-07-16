Deploy to Render (step-by-step)

Overview
- This repo contains a Flask app (`app.py`) and `requirements.txt`.
- Render can deploy this as a Web Service using Gunicorn.

Preconditions
- Create a Git repository (GitHub/GitLab) and push this project.

Recommended start command
- Render sets the `$PORT` env var — the app reads it.
- If you need Google Cloud TTS, store the service account JSON in a Render secret named `GOOGLE_SA_JSON` and the Groq API key in `GROQ_API_KEY`.

Start command (Render -> Web Service -> "Start Command"):

```bash
# Create a temporary key file from secret and export path, then start gunicorn
bash -lc 'if [ -n "$GOOGLE_SA_JSON" ]; then echo "$GOOGLE_SA_JSON" > /tmp/key.json && export GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json; fi; gunicorn app:app -w 4 -b 0.0.0.0:$PORT'
```

Notes:
- This writes the service-account JSON to `/tmp/key.json` at runtime (ephemeral). It's more secure than committing a file.
- If you don't use server TTS, you can skip setting `GOOGLE_SA_JSON` and the app will fall back to browser TTS.

Render web service setup
1. Go to https://dashboard.render.com and create a new Web Service.
2. Connect your Git repository.
3. Branch: `main` (or whichever branch you pushed).
4. Build Command: leave empty (Render will run `pip install -r requirements.txt` by default) or set:
   ```bash
   pip install -r requirements.txt
   ```
5. Start Command: paste the `bash -lc '...'` command from above.
6. Environment:
   - Add `GROQ_API_KEY` (your Groq key) as an environment variable.
   - Optionally add `GOOGLE_SA_JSON` (the full JSON text of your Google service account) as a secret.
   - Optionally set `FLASK_DEBUG` to `false`.

Troubleshooting
- Logs: Use Render dashboard logs if the service fails to boot.
- Port issues: Render sets `$PORT` automatically — the app uses it.
- Static files: Flask serves `static/` by default.
- If `/tts` returns errors about credentials, confirm `GOOGLE_SA_JSON` is set and valid.

Security tip
- Do NOT commit your service-account JSON to the repo. Use Render's secret env vars.

Optional: Render `render.yaml`
- If you prefer Infrastructure as Code, you can create a `render.yaml` describing the service. The minimal approach above works well for quick deploys.
