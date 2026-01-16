import os
import requests
import threading
import time
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- KONFIGURATION ---
ZONE_C_URL = os.environ.get("ZONE_C_URL", "https://adlite-1.onrender.com").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
MY_OWN_URL = os.environ.get("MY_OWN_URL") # Die URL von Zone B selbst

# --- KEEP-ALIVE FUNKTION ---
def keep_alive():
    """Pingt Zone C und sich selbst alle 10 Minuten an, um den Sleep-Mode zu verhindern."""
    while True:
        try:
            # Ping Zone C
            requests.get(f"{ZONE_C_URL}/health", timeout=10)
            # Ping sich selbst (Zone B)
            if MY_OWN_URL:
                requests.get(MY_OWN_URL, timeout=10)
            print("Keep-Alive Ping gesendet.")
        except Exception as e:
            print(f"Keep-Alive Fehler: {e}")
        time.sleep(600) # 10 Minuten

# Starte den Ping-Thread beim Booten
threading.Thread(target=keep_alive, daemon=True).start()

# --- ROUTES ---

@app.get("/")
async def index(request: Request):
    # Die Liste der Events (identisch mit deiner data_android.json)
    events = [
        "Own Ico", "Collect NFTs", "Token Buyback Mechanism", 
        "Jeremy Palmer", "Akatzuki", "Aniverse", "Bloxverse", 
        "5000 lvl Crypto World", "Max lvl Own Ico Business",
        "kauf19.99", "kauf49.99", "Purchase IAP"
    ]
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "events": events
    })

@app.post("/api/send")
async def proxy_send(
    platform: str = Form(...),
    device_id: str = Form(...),
    event_name: str = Form(...)
):
    if not INTERNAL_API_KEY:
        return {"success": False, "message": "API-Key fehlt in Zone B."}

    try:
        # Request an Zone C senden
        response = requests.post(
            f"{ZONE_C_URL}/api/internal-execute",
            data={
                "platform": platform,
                "device_id": device_id,
                "event_name": event_name
            },
            headers={"x-api-key": INTERNAL_API_KEY},
            timeout=30 # Hoher Timeout für Cold-Starts
        )
        
        if response.status_code == 200:
            # Übernehme die gefilterte Nachricht direkt von Zone C
            data = response.json()
            return {"success": True, "message": data.get("filtered_message")}
        else:
            return {"success": False, "message": f"Zone C meldet Fehler: {response.status_code}"}

    except Exception as e:
        return {"success": False, "message": "Zone C momentan nicht erreichbar."}