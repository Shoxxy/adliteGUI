import os
import json
import requests
import threading
import time
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# --- 1. APP INITIALISIERUNG (Muss vor den Routen stehen!) ---
app = FastAPI(title="SuStoolz Lite Beta")

# Session Middleware für den Login-Schutz
# In Render 'SESSION_SECRET' als Environment Variable setzen!
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get("SESSION_SECRET", "super-secret-gold-key-999")
)

# Template Verzeichnis (Stelle sicher, dass der Ordner 'templates' existiert!)
templates = Jinja2Templates(directory="templates")

# --- 2. KONFIGURATION ---
ZONE_C_URL = os.environ.get("ZONE_C_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
MY_OWN_URL = os.environ.get("MY_OWN_URL")

# --- 3. HILFSFUNKTIONEN ---
def get_users():
    """Lädt die User-Daten aus der USERS_JSON Umgebungsvariable"""
    users_raw = os.environ.get("USERS_JSON", '{"admin": "gold2026"}')
    try:
        return json.loads(users_raw)
    except:
        return {"admin": "error_check_env"}

def is_authenticated(request: Request):
    return request.session.get("user") is not None

# --- 4. KEEP-ALIVE SYSTEM ---
def keep_alive():
    """Verhindert das Einschlafen der Instanzen (alle 10 Min)"""
    while True:
        try:
            if ZONE_C_URL:
                requests.get(f"{ZONE_C_URL}/health", timeout=10)
            if MY_OWN_URL:
                requests.get(MY_OWN_URL, timeout=10)
        except:
            pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# --- 5. ROUTEN ---

@app.get("/")
async def index(request: Request):
    # Authentifizierungs-Check
    if not is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    
    # App-Konfiguration von Zone C abrufen
    app_config = {}
    if ZONE_C_URL and INTERNAL_API_KEY:
        try:
            resp = requests.get(
                f"{ZONE_C_URL}/api/get-apps", 
                headers={"x-api-key": INTERNAL_API_KEY}, 
                timeout=10
            )
            if resp.status_code == 200:
                app_config = resp.json()
        except Exception as e:
            print(f"Fehler beim Abruf der Apps: {e}")

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "app_config": app_config
    })

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    users = get_users()
    if username in users and users[username] == password:
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": "ZUGRIFF VERWEIGERT: UNGÜLTIGE CREDENTIALS"
    })

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.post("/api/send")
async def proxy_send(
    request: Request,
    app_name: str = Form(...),
    platform: str = Form(...),
    device_id: str = Form(...),
    event_name: str = Form(...)
):
    if not is_authenticated(request):
        return JSONResponse({"success": False, "message": "SESSION EXPIRED"}, status_code=401)

    try:
        response = requests.post(
            f"{ZONE_C_URL}/api/internal-execute",
            data={
                "app_name": app_name,
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
            return {"success": False, "message": f"ZONE C ERROR: {response.status_code}"}

    except Exception as e:
        return {"success": False, "message": "UPLINK TO ZONE C FAILED"}

# Start für lokales Testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)