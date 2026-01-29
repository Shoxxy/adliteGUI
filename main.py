import os
import requests
import json
from datetime import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles 
from starlette.middleware.sessions import SessionMiddleware

# --- KONFIGURATION ---
app = FastAPI(title="SuStoolz Zone B GUI")

# Secret Key für Sessions (in Produktion unbedingt ändern!)
SECRET_KEY = os.environ.get("SESSION_SECRET", "super-secret-gui-key-999")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Ordner-Pfade definieren
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Statische Dateien mounten (CSS, Banner, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- ZONE C UPLINK CONFIG ---
# Hierhin sendet die GUI ihre Befehle. Zone C ist der "Motor".
ZONE_C_URL = os.environ.get("ZONE_C_URL", "http://localhost:8000").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "secure-key-123")

# Benutzer-Datenbank (einfaches JSON Format)
# Format env: '{"admin":"password", "user2":"secret"}'
USERS_JSON = os.environ.get("USERS_JSON", '{"admin":"password"}')
try:
    USERS = json.loads(USERS_JSON)
except json.JSONDecodeError:
    print("CRITICAL: USERS_JSON could not be parsed. Defaulting to admin:password")
    USERS = {"admin": "password"}

# --- HILFSFUNKTIONEN ---

def check_auth(request: Request):
    """Prüft, ob der User eingeloggt ist."""
    return request.session.get("user")

# --- ROUTEN ---

@app.get("/")
async def index(request: Request):
    """Haupt-Dashboard: Lädt App-Liste von Zone C."""
    user = check_auth(request)
    if not user: 
        return RedirectResponse(url="/login")
    
    apps = {}
    uplink_status = "Unknown"
    
    # Versuche, App-Liste von Zone C zu holen
    try:
        r = requests.get(
            f"{ZONE_C_URL}/api/get-apps", 
            headers={"x-api-key": INTERNAL_API_KEY}, 
            timeout=3
        )
        if r.status_code == 200: 
            apps = r.json()
            uplink_status = "Connected"
        else:
            uplink_status = f"Error {r.status_code}"
            print(f"Zone C Error: {r.text}")
    except Exception as e:
        print(f"Error connecting to Zone C: {e}")
        uplink_status = "Offline"

    # Rendert die Hauptseite mit Status-Indikator
    return templates.TemplateResponse("index.html", {
        "request": request, 
        "user": user, 
        "app_config": apps, 
        "current_page": "home",
        "uplink_status": uplink_status
    })

@app.get("/repeat")
async def repeat_page(request: Request):
    """Seite für wiederkehrende Aufgaben (Placeholder)."""
    user = check_auth(request)
    if not user: 
        return RedirectResponse(url="/login")

    return templates.TemplateResponse("repeat.html", {
        "request": request, 
        "user": user, 
        "current_page": "repeat"
    })

# --- LOGIN / LOGOUT ---

@app.get("/login")
async def login_page(request: Request):
    """Zeigt das Login-Formular."""
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    """Verarbeitet den Login."""
    if username in USERS and USERS[username] == password:
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    
    return templates.TemplateResponse("login.html", {
        "request": request, 
        "error": "ZUGRIFF VERWEIGERT: Ungültige Identität"
    })

@app.get("/logout")
async def logout(request: Request):
    """Loggt den User aus."""
    request.session.clear()
    return RedirectResponse(url="/login")

# --- API PROXY (BRIDGE TO ZONE C) ---

@app.post("/api/proxy_send")
async def proxy_send(request: Request):
    """
    Nimmt Formulardaten vom Frontend entgegen und leitet sie 
    an Zone C weiter. Dies schützt Zone C vor direktem Internetzugriff.
    """
    user = check_auth(request)
    if not user:
        return JSONResponse({"success": False, "log_entry": "Unauthorized Session"}, status_code=401)

    try:
        # Formulardaten auslesen
        form_data = await request.form()
        
        # Weiterleitung an Zone C
        # Wir senden exakt das, was wir bekommen haben, weiter + Auth Header
        # Timeout etwas höher setzen, da die Ausführung dauern kann
        r = requests.post(
            f"{ZONE_C_URL}/api/proxy_send",
            data=form_data,
            headers={"x-api-key": INTERNAL_API_KEY},
            timeout=15 
        )
        
        # Antwort von Zone C direkt an das Frontend zurückgeben
        if r.status_code == 200:
            return r.json()
        else:
            # Falls Zone C einen Fehler meldet (z.B. 404 oder 500)
            try:
                err_json = r.json()
                return JSONResponse(err_json, status_code=r.status_code)
            except:
                return JSONResponse({
                    "success": False, 
                    "log_entry": f"<span class='log-ts'>ERR</span> Zone C returned {r.status_code}"
                }, status_code=r.status_code)

    except requests.exceptions.ConnectionError:
        return JSONResponse({
            "success": False, 
            "log_entry": "<span class='log-ts'>CRIT</span> Zone C Unreachable (Connection Refused)"
        })
    except requests.exceptions.Timeout:
        return JSONResponse({
            "success": False, 
            "log_entry": "<span class='log-ts'>WARN</span> Zone C Timeout (Operation might still be running)"
        })
    except Exception as e:
        return JSONResponse({
            "success": False, 
            "log_entry": f"<span class='log-ts'>ERR</span> Proxy Error: {str(e)}"
        })