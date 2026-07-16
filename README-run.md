Run and troubleshoot the local Flask server (Windows)

1) Install dependencies
Open PowerShell and run:

```powershell
cd "c:\Users\hp\OneDrive\Desktop\vikas avtar"
python -m pip install -r requirements.txt
```

2) Run the server

```powershell
python app.py
```

You should see a line like:

Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)

3) Open in Chrome
- Use the exact URL: http://127.0.0.1:5000/ or http://localhost:5000/
- Don't open the HTML file directly via `file://` — that breaks XHR/fetch calls.

4) Quick health check
- In PowerShell run:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing
```

- Expected JSON: { "status": "ok", "app": "vikas-avtar" }

5) Common issues
- "Address already in use" on port 5000: run `netstat -ano | findstr :5000` and kill the PID with `taskkill /PID <pid> /F`.
- Windows Firewall prompts: allow access for Python when prompted.
- Chrome shows CORS/Failed to fetch: ensure you opened via http://localhost:5000 and not via file://. The app adds permissive CORS headers for local dev.

6) If the page is blank or Three.js errors in Console:
- Open DevTools (Ctrl+Shift+I) → Console / Network. Copy any red error messages and share them.

7) If `/tts` fails:
- The server will return an error if Google credentials are not configured; client falls back to browser TTS.
- To enable server TTS, set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to a service account JSON path.

If you want, I can now:
- Walk you through running these commands step-by-step, or
- Inspect Chrome console logs if you paste them here, or
- Attempt to start a local dev server from here (I can only provide commands).