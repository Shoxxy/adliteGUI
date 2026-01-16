import os
import requests
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

ZONE_C_URL = os.environ.get("ZONE_C_URL")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")

@app.get("/")
async def index(request: Request):
    events = ["Own Ico", "Collect NFTs", "Token Buyback Mechanism", "Jeremy Palmer", "Akatzuki", "Aniverse", "Bloxverse", "5000 lvl Crypto World", "Max lvl Own Ico Business", "kauf19.99", "kauf49.99", "Purchase IAP"]
    return templates.TemplateResponse("index.html", {"request": request, "events": events})

@app.post("/api/send")
async def proxy_send(platform: str = Form(...), device_id: str = Form(...), event_name: str = Form(...)):
    try:
        # Request an Zone C
        resp = requests.post(
            f"{ZONE_C_URL}/api/internal-execute",
            data={"platform": platform, "device_id": device_id, "event_name": event_name},
            headers={"x-api-key": INTERNAL_API_KEY},
            timeout=20
        )
        
        # Zone B reicht einfach nur die gefilterte Nachricht weiter
        data = resp.json()
        return {"success": True, "message": data.get("filtered_message", "Unbekannte Antwort.")}

    except:
        return {"success": False, "message": "Zone C nicht erreichbar."}