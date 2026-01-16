import os, requests, threading, time, json
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
# WICHTIG: Erstelle einen SECRET_KEY in Render für die Session-Sicherheit
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "super-geheim-schluessel"))
templates = Jinja2Templates(directory="templates")

ZONE_C_URL = os.environ.get("ZONE_C_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")
MY_OWN_URL = os.environ.get("MY_OWN_URL")

# --- AUTH LOGIK ---
def get_users():
    return json.loads(os.environ.get("USERS_JSON", "{}"))

def is_logged_in(request: Request):
    return request.session.get("user") is not None

# --- KEEP ALIVE ---
def keep_alive():
    while True:
        try:
            requests.get(f"{ZONE_C_URL}/health", timeout=10)
            if MY_OWN_URL: requests.get(MY_OWN_URL, timeout=10)
        except: pass
        time.sleep(600)

threading.Thread(target=keep_alive, daemon=True).start()

# --- ROUTES ---

@app.get("/")
async def index(request: Request):
    if not is_logged_in(request):
        return templates.TemplateResponse("login.html", {"request": request})
    
    events = ["Own Ico", "Collect NFTs", "Token Buyback Mechanism", "Jeremy Palmer", "Akatzuki", "Aniverse", "Bloxverse", "5000 lvl Crypto World", "Max lvl Own Ico Business", "kauf19.99", "kauf49.99", "Purchase IAP"]
    return templates.TemplateResponse("index.html", {"request": request, "events": events})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    users = get_users()
    if username in users and users[username] == password:
        request.session["user"] = username
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Ungültige Daten"})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.post("/api/send")
async def proxy_send(request: Request, platform: str = Form(...), device_id: str = Form(...), event_name: str = Form(...)):
    if not is_logged_in(request):
        return JSONResponse({"success": False, "message": "Nicht eingeloggt."}, status_code=401)

    try:
        resp = requests.post(
            f"{ZONE_C_URL}/api/internal-execute",
            data={"platform": platform, "device_id": device_id, "event_name": event_name},
            headers={"x-api-key": INTERNAL_API_KEY},
            timeout=30
        )
        return {"success": True, "message": resp.json().get("filtered_message")}
    except:
        return {"success": False, "message": "Verbindung zu Zone C fehlgeschlagen."}