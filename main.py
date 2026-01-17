# In Zone B main.py ergänzen/ändern:

@app.get("/")
async def index(request: Request):
    if not is_authenticated(request):
        return templates.TemplateResponse("login.html", {"request": request, "error": None})
    
    # Apps von Zone C abrufen
    try:
        resp = requests.get(
            f"{ZONE_C_URL}/api/get-apps", 
            headers={"x-api-key": INTERNAL_API_KEY}, 
            timeout=10
        )
        app_config = resp.json() # Format: {"AppName": ["Event1", "Event2"], ...}
    except:
        app_config = {}

    return templates.TemplateResponse("index.html", {
        "request": request, 
        "app_config": app_config # Wir geben die gesamte Config ans Template
    })

@app.post("/api/send")
async def proxy_send(
    request: Request,
    app_name: str = Form(...), # NEU
    platform: str = Form(...),
    device_id: str = Form(...),
    event_name: str = Form(...)
):
    if not is_authenticated(request): return JSONResponse(status_code=401)

    resp = requests.post(
        f"{ZONE_C_URL}/api/internal-execute",
        data={"app_name": app_name, "platform": platform, "device_id": device_id, "event_name": event_name},
        headers={"x-api-key": INTERNAL_API_KEY},
        timeout=35
    )
    return {"success": True, "message": resp.json().get("filtered_message")}