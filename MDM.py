import os
import json
import threading
import uuid
import time
import hashlib
from pathlib import Path
from fastapi import FastAPI, Request, Query, Form
from fastapi.responses import HTMLResponse,PlainTextResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request
from fastapi.responses import Response
from email.utils import formatdate
from datetime import datetime
from ses_service import ses_server

from utils.aprs_report import aprs_report
from utils.responses import fixed_json_response, chunked_response
from utils import data_memory_cache
from typing import Optional

app = FastAPI()

RESPONSE_PATH = Path("static/response.json")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
def startup_tasks():
    # 启动 SES 服务
    thread = threading.Thread(target=ses_server, daemon=True)
    thread.start()

    # 启动缓存管理器
    data_memory_cache.start_device_cache_manager()

@app.on_event("shutdown")
def graceful_shutdown():
    print("[Cache] Application is shutting down, flushing cache to disk")
    data_memory_cache.save_device_cache_once()

@app.post("/nrm/androidTask/checkDeviceSn")
async def check_device_sn(request: Request):
    # 读取请求体
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        req_data["update_time"]= int(time.time())
        device_id = req_data.get("deviceId")
    except Exception as e:
        print(f"[WARN] 无法解析请求体: {e}")
        req_data = {}
        device_id = None

    if device_id:
        existing = data_memory_cache.get_device_entry(device_id)
        existing.update(req_data)
        data_memory_cache.update_device_entry(device_id, existing)
        print(f"[Cache] 更新设备 {device_id}")

    # 返回固定响应
    try:
        with RESPONSE_PATH.open("r", encoding="utf-8") as f:
            response_data = json.load(f)["check_device_sn"]
    except Exception as e:
        print(f"[ERROR] 无法加载响应文件: {e}")
        response_data = {"code": "500", "success": "false", "msg": "内部错误", "data": None}
    #print(response_data)
    return fixed_json_response(response_data)

@app.post("/login/login")
async def login(request: Request):
    body = await request.body()
    print("Body:", body.decode())
    # 返回固定响应
    try:
        with RESPONSE_PATH.open("r", encoding="utf-8") as f:
            response_data = json.load(f)["login"]
            response_data["data"]["token"]=uuid.uuid4().hex
    except Exception as e:
        print(f"[ERROR] 无法加载响应文件: {e}")
        response_data = {"code": "500", "success": "false", "msg": "内部错误", "data": None}
    #print(response_data)
    return fixed_json_response(response_data)

@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
async def chunked_getDeviceInfoFromAndroid(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        req_data["update_time"]= int(time.time())
        device_id = req_data.get("deviceId")
        device_info_raw = req_data.get("deviceInfo")

        # 解析 deviceInfo（可能是字符串或对象）
        if isinstance(device_info_raw, str):
            device_info = json.loads(device_info_raw)
        else:
            device_info = device_info_raw or {}

        # 使用内存缓存
        if device_id:
            entry = data_memory_cache.get_device_entry(device_id)
            entry["deviceId"] = device_id
            entry["deviceInfo"] = device_info  # 只更新 deviceInfo，保留其它字段
            data_memory_cache.update_device_entry(device_id, entry)
            print(f"[Cache] Updated deviceInfo for {device_id}")

    except Exception as e:
        print(f"[getDeviceInfoFromAndroid] Logging error: {e}")

    # 返回原样 chunked 响应
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": ""
    })

@app.post("/nrm/androidTask/getAppInfoFromAndroid")
async def chunked_getAppInfoFromAndroid(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        if device_id:
            entry = data_memory_cache.get_device_entry(device_id)
            entry["update_time"]= int(time.time())
            data_memory_cache.update_device_entry(device_id, entry)
        print("Body:", body.decode())
    except Exception as e:
        print(f"Logging error: {e}") 
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": ""
    })

@app.post("/nrm/androidUploadInfo/uploadContact")
async def chunked_uploadContact(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        contacts = req_data.get("contactsList", [])
        if device_id:
            entry = data_memory_cache.get_device_entry(device_id)
            entry["update_time"]= int(time.time())
            data_memory_cache.update_device_entry(device_id, entry)

            # 保存 contactsList 为 JSON 文件
            Path("data").mkdir(parents=True, exist_ok=True)
            contact_file = Path("data") / f"{device_id}_contact.json"
            contact_file.write_text(json.dumps(contacts, ensure_ascii=False, indent=2),encoding="utf-8")

        print("Body:", body.decode())
    except Exception as e:
        print(f"Logging error: {e}") 
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": ""
    })

@app.post("/nrm/androidUploadInfo/appMd5Check")
async def chunked_data_array(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        if device_id:
            entry = data_memory_cache.get_device_entry(device_id)
            entry["update_time"]= int(time.time())
            data_memory_cache.update_device_entry(device_id, entry)
        print("Body:", body.decode())
    except Exception as e:
        print(f"Logging error: {e}") 
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": []
    })

@app.post("/nrm/androidUploadInfo/uploadWorkInterfaceInfo")
@app.post("/nrm/androidTask/getAndroidCommand")
async def chunked_data_null(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        if device_id:
            entry = data_memory_cache.get_device_entry(device_id)
            entry["update_time"]= int(time.time())
            data_memory_cache.update_device_entry(device_id, entry)
        #print("Body:", body.decode())
    except Exception as e:
        print(f"Logging error: {e}") 
    return None
    #无关上报日志太多了，考虑不返回
   #return chunked_response({
   #    "code": "0",
   #    "success": "true",
   #    "msg": "",
   #    "data": None
   #})

@app.post("/nrm/androidTask/uploadLocationInfo")
async def uploadLocationInfo(request: Request):
    body = await request.body()
    print("[APRS_Service]Body:", body.decode())

    try:
        req_data = json.loads((await request.body()).decode())
        device_id = req_data.get("deviceId")

        if not device_id:
            raise ValueError("缺少 deviceId")
        if float(req_data.get("latitude"))==0 and float(req_data.get("longitude"))==0:
            raise ValueError("无效的经纬度")
        location_data = {
            "latitude": req_data.get("latitude"),
            "longitude": req_data.get("longitude"),
            "altitude": req_data.get("altitude"),
            "update_time": int(time.time())
        }

        entry = data_memory_cache.get_device_entry(device_id)

        device_name = entry.get("deviceInfo", {}).get("wholeInfo", {}).get("alias", "")
        issiRadioId = entry.get("deviceInfo", {}).get("nbInfo", {}).get("issiRadioId", "")
        device_ssid = entry.get("location", {}).get("aprs_ssid")
        print(f"[APRS_Service]entry.get(location).get(aprs_ssid):{device_ssid}")
        device_ssid=aprs_report(location_data["latitude"], location_data["longitude"], device_name, issiRadioId, device_id, device_ssid)
        if device_ssid:
            print(f"[APRS_Service]aprs_report() return ssid {device_ssid}")
            location_data["aprs_ssid"] = device_ssid
        #entry.setdefault("deviceId", device_id)
        entry["location"] = location_data
        entry["update_time"]= int(time.time())
        data_memory_cache.update_device_entry(device_id, entry)
        print(f"[APRS_Service][Cache] 上报位置 {device_id} {device_ssid}")

        
    except Exception as e:
        print(f"[APRS_Service][uploadLocationInfo] Logging error: {e}")

    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })


@app.get("/")
async def default_image():
    image_path = "static/QRCODE_2232.png"  # 确保图片存在于该路径
    return FileResponse(image_path, media_type="image/jpeg")

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, filter_device: Optional[str] = None, map: Optional[str] = "baidu"):
    devices = data_memory_cache.get_device_cache()
    devices_all = data_memory_cache.get_device_cache()
    current_time = int(time.time())
    for i in devices:
        if "update_time" not in devices[i]:
            devices[i]["update_time"]=devices[i]["location"]["update_time"]

        # 如果传入筛选设备ID，只保留该设备
    if filter_device:
        devices = {
            k: v for k, v in devices.items()
            if k == filter_device
        }

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "devices": devices,
        "devices_all": devices_all,
        "now": current_time,
        "map_type": map  # 新增传递地图类型
    })

@app.get("/device", response_class=HTMLResponse)
async def view_device(request: Request, deviceid: str = Query(...)):
    entry = data_memory_cache.get_device_entry(deviceid)
    devicename=entry["deviceInfo"]["wholeInfo"]["alias"]

    if not entry:
        return HTMLResponse(f"<h2>设备 {deviceid} 不存在</h2>", status_code=404)

    if "sn" not in entry:
        return HTMLResponse(f"<h2>设备 {deviceid} 没有 SN 信息，无法验证</h2>", status_code=400)

    return templates.TemplateResponse("device_verify.html", {
        "request": request,
        "deviceid": deviceid,
        "devicename": devicename,
        "sn": entry["sn"]
    })



@app.get("/device/deviceinfo", response_class=HTMLResponse)
async def verify_device_sn(
    deviceid: str = Query(...),
    timestamp: int = Query(...),
    sn_hash: str = Query(...)
):
    entry = data_memory_cache.get_device_entry(deviceid)
    if not entry:
        return HTMLResponse("<h3>设备不存在</h3>", status_code=404)

    real_sn = entry.get("sn")
    if not real_sn:
        return HTMLResponse("<h3>设备未注册 SN</h3>", status_code=400)

    now = int(time.time())
    if abs(now - timestamp) > 900:  # 超过±15分钟
        return HTMLResponse("<h3>时间戳无效（请求过期）</h3>", status_code=403)

    # 验证哈希
    expected = hashlib.sha256((real_sn + str(timestamp)).encode('utf-8')).hexdigest()
    if expected != sn_hash:
        return HTMLResponse("<h3>SN 校验失败</h3>", status_code=403)

    return PlainTextResponse(
        json.dumps(entry, indent=2, ensure_ascii=False),
        media_type="application/json"
    )

@app.get("/change_aprs_ssid", response_class=HTMLResponse)
async def change_aprs_ssid_form(request: Request, device_id: str = Query(...)):
    return templates.TemplateResponse("change_aprs_ssid.html", {
        "request": request,
        "device_id": device_id
    })

@app.post("/change_aprs_ssid", response_class=HTMLResponse)
async def change_aprs_ssid_submit(
    request: Request,
    device_id: str = Form(...),
    sn: str = Form(...),
    aprs_ssid: str = Form(...)
):
    entry = data_memory_cache.get_device_entry(device_id)
    if not entry:
        return HTMLResponse("""
            <h3>找不到设备</h3>
            <button onclick="history.back()" style="margin-top: 10px;">返回</button>
        """, status_code=404)

    if sn != entry.get("sn"):
        return HTMLResponse("""
            <h3>SN 验证失败</h3>
            <button onclick="history.back()" style="margin-top: 10px;">返回</button>
        """, status_code=403)

    try:
        entry["location"]["aprs_ssid"] = aprs_ssid
        data_memory_cache.update_device_entry(device_id, entry)
        print(f"[Cache] 更新设备 {device_id}")
    except Exception as e:
        return HTMLResponse(f"""
            <h3>更新失败: {e}</h3>
            <button onclick="history.back()" style="margin-top: 10px;">返回</button>
        """, status_code=500)


    return HTMLResponse(f"""
    <h3>APRS SSID 已更新为：{aprs_ssid}</h3>
    <a href="/dashboard">
        <button style="margin-top: 10px;">返回 Dashboard</button>
    </a>
""", status_code=200)


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(request: Request, full_path: str):
    body = await request.body()
    print(f"[UNMATCHED] {request.method} /{full_path}")
    print(body.decode(errors="ignore"))
    return PlainTextResponse("Unhandled path", status_code=404)

@app.post("/{unknown:path}")
async def fallback(request: Request, unknown: str):
    body = await request.body()
    print(f"[UNKNOWN] {request.method} {request.url.path}?{request.url.query}")
    try:
        print("Body:", body.decode())
    except:
        print("Body: <non-decodable>")
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": []
    })




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("MDM:app", host="0.0.0.0", port=2232, reload=True)