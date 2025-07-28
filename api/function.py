async def dashboard(request: Request):
    if DEVICE_LOG_PATH.exists():
        with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
            devices = json.load(f)
    else:
        devices = {}
    current_time = int(time.time())

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "devices": devices,  # 如果你 dashboard.html 中写的是 data.items()
        "now": current_time
    })