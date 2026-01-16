import os
import json
import requests
import threading
import time
from fastapi import FastAPI, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="Zone B - Secure Gateway")

# --- KONFIGURATION & SECURITY ---
# SESSION_SECRET in Render Environment setzen!
SECRET_KEY = os.environ.get("SESSION_SECRET", "gold-standard-key-321")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")

ZONE_C_URL = os.environ.get("ZONE_C_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
MY_OWN_URL = os.environ.get("MY_OWN_URL")

# --- HELPER FUNKTIONEN ---
def get_users():
    """Lädt User aus Render Environment Variable USERS_JSON"""
    users_raw = os.environ.get("USERS_JSON", '{"admin": "gold2024"}')
    try:
        return json.loads(users_raw)
    except:
        return {"admin": "error_check_env"}

def is_authenticated(request: Request):
    return request.session.get("user") is not None

# --- KEEP ALIVE LOGIK ---
def keep_alive():
    """Verhindert den Sleep-Mode von Zone B und Zone C"""
    while True:
        try:
            if ZONE_C_URL:
                requests.get(f"{ZONE_C_URL}/health", timeout=10)
            if MY_OWN_URL:
                requests.get(MY_OWN_URL, timeout=10)
        except:
            pass
        time.sleep(600) # Alle 10 Minuten

threading.Thread(target=keep_alive, daemon=True).start()

# --- ROUTEN ---

@app.get("/")
async def index(request: Request):
    # Wenn nicht eingeloggt -> Zeige Login Screen
    if not is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    
    # Wenn eingeloggt -> Zeige Dashboard
    events = [
        "Own Ico", "Collect NFTs", "Token Buyback Mechanism", 
        "Jeremy Palmer", "Akatzuki", "Aniverse", "Bloxverse", 
        "5000 lvl Crypto World", "Max lvl Own Ico Business",
        "kauf19.99", "kauf49.99", "Purchase IAP"
    ]
    return templates.TemplateResponse("index.html", {"request": request, "events": events})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    users = get_users()
    if username in users and users[username] == password:
        request.session["user"] = username
        # Nach Login zur Hauptseite umleiten
        return RedirectResponse(url="/", status_code=303)
    
    # Bei Fehler zurück zum Login mit Meldung
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": "Zugriff verweigert: Falsche Daten."
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.post("/api/send")
async def proxy_send(
    request: Request,
    platform: str = Form(...),
    device_id: str = Form(...),
    event_name: str = Form(...)
):
    # Sicherheitscheck für API Aufrufe
    if not is_authenticated(request):
        return JSONResponse({"success": False, "message": "Sitzung abgelaufen."}, status_code=401)

    if not ZONE_C_URL or not INTERNAL_API_KEY:
        return {"success": False, "message": "Konfigurationsfehler in Zone B."}

    try:
        # Weiterleitung an Zone C
        response = requests.post(
            f"{ZONE_C_URL}/api/internal-execute",
            data={
                "platform": platform,
                "device_id": device_id,
                "event_name": event_name
            },
            headers={"x-api-key": INTERNAL_API_KEY},
            timeout=35
        )
        
        if response.status_code == 200:
            return {"success": True, "message": response.json().get("filtered_message")}
        else:
            return {"success": False, "message": f"Zone C Fehler (Status {response.status_code})"}

    except Exception as e:
        return {"success": False, "message": "Verbindung zu Zone C konnte nicht hergestellt werden."}