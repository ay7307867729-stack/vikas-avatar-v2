import urllib.request
import urllib.error
import json

url = "http://127.0.0.1:5000/chat"
data = json.dumps({"message": "test message"}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req) as resp:
        print(resp.status)
        print(resp.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(e.read().decode("utf-8"))
except Exception:
    import traceback
    traceback.print_exc()
