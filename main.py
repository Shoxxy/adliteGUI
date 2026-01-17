import os
import json
import requests
import threading
import time
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware

# --- 1. INITIALISIERUNG & LOGGING SETUP ---
LOG_FILE = "security_activity.log"
user_tracker = {}  # Speichert IPs und Event-Counts pro Stunde
MAX_EVENTS_PER_HOUR = 40 

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

app = FastAPI(title="SuStoolz Lite Beta")

# Session Middleware (2 Stunden technisches Limit)
app.add_middleware(
    SessionMiddleware, 
    secret_key=os.environ.get("SESSION_SECRET", "gold-secret-999"),
    max_age=7200 
)

templates = Jinja2Templates(directory="templates")

# Konfiguration aus Environment Variables
ZONE_C_URL = os.environ.get("ZONE_C_URL", "").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY")

# --- 2. SICHERHEITS-FUNKTIONEN ---

def log_event(level, message):
    """Schreibt in die Logdatei mit Sicherheits-Präfix"""
    prefix = "!!! SECURITY ALERT !!! | " if level == "ALERT" else "INFO | "
    logging.info(f"{prefix}{message}")

def track_security(username, ip, action="event"):
    """Prüft auf Account-Sharing (IP-Wechsel) und Spamming"""
    if username not in user_tracker:
        user_tracker[username] = {"ips": {ip}, "count": 0}
    
    # Check: Account Sharing (Mehrere IPs)
    if ip not in user_tracker[username]["ips"]:
        user_tracker[username]["ips"].add(ip)
        if len(user_tracker[username]["ips"]) > 1:
            log_event("ALERT", f"VERDACHT ACCOUNT-SHARING: User '{username}' nutzt neue IP: {ip}. Bekannte IPs: {user_tracker[username]['ips']}")

    # Check: Event-Spamming
    if action == "event":
        user_tracker[username]["count"] += 1
        if user_tracker[username]["count"] > MAX_EVENTS_PER_HOUR:
            log_event("ALERT", f"MÖGLICHER MISSBRAUCH: User '{username}' überschreitet Limit ({user_tracker[username]['count']} Events/Std)")

def check_session(request: Request):
    """Prüft ob User eingeloggt ist und ob die 2 Stunden abgelaufen sind"""
    user = request.session.get("user")
    login_time_str = request.session.get("login_time")
    
    if not user or not login_time_str:
        return False
    
    login_time = datetime.fromisoformat(login_time_str)
    if datetime.now() > login_time + timedelta(hours=2):
        log_event("INFO", f"SESSION EXPIRED: User '{user}' automatisch ausgeloggt.")
        request.session.clear()
        return False
    return True

# --- 3. E-MAIL VERSAND (ALLE 60 MINUTEN) ---

def send_security_report():
    while True:
        time.sleep(600) # 10 Minuten warten
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            continue

        try:
            smtp_user = os.environ.get("SMTP_USER")
            smtp_pass = os.environ.get("SMTP_PASS")
            recipient = os.environ.get("REPORT_RECIPIENT", smtp_user)

            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = recipient
            msg['Subject'] = f"SECURITY REPORT: SuStoolz Activity {datetime.now().strftime('%d.%m. %H:%M')}"
            
            body = "Anbei das Aktivitäts-Log der letzten Stunde. Bitte auf 'SECURITY ALERT' achten."
            msg.attach(MIMEText(body, 'plain'))

            with open(LOG_FILE, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {LOG_FILE}")
                msg.attach(part)

            server = smtplib.SMTP(os.environ.get("SMTP_HOST", "smtp.gmail.com"), 587)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()

            # Log und Tracker für die nächste Stunde leeren
            with open(LOG_FILE, "w") as f:
                f.write(f"--- Log-Zyklus neu gestartet: {datetime.now()} ---\n")
            user_tracker.clear()
            
        except Exception as e:
            print(f"Fehler beim E-Mail Versand: {e}")

# Hintergrund-Thread für E-Mails starten
threading.Thread(target=send_security_report, daemon=True).start()

# --- 4. ROUTEN ---

@app.get("/")
async def index(request: Request):
    if not check_session(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    
    # App Konfiguration von Zone C laden
    app_config = {}
    try:
        resp = requests.get(f"{ZONE_C_URL}/api/get-apps", headers={"x-api-key": INTERNAL_API_KEY}, timeout=10)
        if resp.status_code == 200:
            app_config = resp.json()
    except:
        pass

    return templates.TemplateResponse("index.html", {"request": request, "app_config": app_config})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    users = json.loads(os.environ.get("USERS_JSON", '{"admin":"gold2026"}'))
    client_ip = request.client.host
    
    if username in users and users[username] == password:
        request.session["user"] = username
        request.session["login_time"] = datetime.now().isoformat()
        
        track_security(username, client_ip, "login")
        log_event("INFO", f"LOGIN ERFOLGREICH: User='{username}' | IP={client_ip}")
        
        return RedirectResponse(url="/", status_code=303)
    
    log_event("ALERT", f"LOGIN FEHLGESCHLAGEN: Versuch mit Username='{username}' | IP={client_ip}")
    return templates.TemplateResponse("login.html", {"request": request, "error": "ZUGRIFF VERWEIGERT"})

@app.get("/logout")
async def logout(request: Request):
    user = request.session.get("user")
    log_event("INFO", f"LOGOUT: User='{user}' hat sich abgemeldet.")
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
    user = request.session.get("user")
    client_ip = request.client.host
    
    if not check_session(request):
        return JSONResponse({"success": False, "message": "SESSION EXPIRED"}, status_code=401)

    # Tracking für Sicherheit & Missbrauch
    track_security(user, client_ip, "event")
    log_event("INFO", f"INJECTION: User='{user}' | App='{app_name}' | Event='{event_name}' | ID='{device_id}' | IP={client_ip}")

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
        log_event("ALERT", f"UPLINK FEHLER: Verbindung zu Zone C fehlgeschlagen für User '{user}'")
        return {"success": False, "message": "UPLINK TO ZONE C FAILED"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)