import os
import requests
import json
from datetime import datetime
# WICHTIG: StaticFiles importieren
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles 
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="SuStoolz Zone A GUI")

# --- NEU: Statische Dateien mounten (für das Bannerbild) ---
# Der Ordner "static" muss im selben Verzeichnis wie main.py liegen.
app.mount("/static", StaticFiles(directory="static"), name="static")

# Setup und Config bleiben gleich...
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "super-secret-gui-key"))
templates = Jinja2Templates(directory="templates")

ZONE_C_URL = os.environ.get("ZONE_C_URL", "http://localhost:8000").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "secure-key-123")
USERS = json.loads(os.environ.get("USERS_JSON", '{"admin":"password"}'))

# ... check_auth Funktion bleibt gleich ...
def check_auth(request):
    return request.session.get("user")

# --- ROUTEN ---

@app.get("/")
async def index(request: Request):
    # ... (Inhalt von index bleibt gleich wie vorher) ...
    user = check_auth(request)
    if not user: return RedirectResponse(url="/login")
    
    apps = {}
    try:
        r = requests.get(f"{ZONE_C_URL}/api/get-apps", headers={"x-api-key": INTERNAL_API_KEY}, timeout=5)
        if r.status_code == 200: apps = r.json()
    except Exception as e: print(f"Error connecting to Zone B: {e}")

    # Rendert die Hauptseite
    return templates.TemplateResponse("index.html", {
        "request": request, "user": user, "app_config": apps, "current_page": "home"
    })

# --- NEUE ROUTE FÜR DAS UNTERMENÜ ---
@app.get("/repeat")
async def repeat_page(request: Request):
    user = check_auth(request)
    if not user: return RedirectResponse(url="/login")

    # Rendert die neue Repeat-Seite
    return templates.TemplateResponse("repeat.html", {
        "request": request, "user": user, "current_page": "repeat"
    })

# ... (Rest der Datei: login, logout, proxy_send bleiben exakt gleich) ...
@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
# ... usw ...