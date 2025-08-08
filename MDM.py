# 标准库
import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime
from email.utils import formatdate
from pathlib import Path
from typing import Optional

# 第三方库
from fastapi import FastAPI, Form, Query, Request, Cookie
from fastapi.responses import HTMLResponse,JSONResponse,PlainTextResponse,RedirectResponse,FileResponse,Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import TimestampSigner, BadSignature, SignatureExpired

# 本地模块
from utils import data_memory_cache
from utils.aprs_report import aprs_report
from utils.ses_service import ses_server
from utils.responses import fixed_json_response, chunked_response, chunked_response_data_null
from utils.task_center import start_task_center, task_exists_for_device, add_device_default_tasks, end_task_center, load_tasks, save_tasks



app = FastAPI()
GLOBAL_CONFIG_PATH = Path("data/sys_conf.json")
GLOBAL_CONFIG=json.loads(Path(GLOBAL_CONFIG_PATH).read_text(encoding="utf-8"))

RESPONSE_PATH = Path("static/response.json")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

GLOBAL_mdmCertMd5=uuid.uuid4().hex

# 启动时生成一个随机的 secret key（每次重启都会变）
SECRET_KEY = secrets.token_hex(32)  # 64位十六进制字符串
signer = TimestampSigner(SECRET_KEY)

def get_logged_in_user(request: Request):
    token = request.cookies.get("admin_token")
    if not token:
        return None
    try:
        username = signer.unsign(token, max_age=1800).decode()
        return username
    except (BadSignature, SignatureExpired):
        return None

def get_user_device_scope(username: str):
    """
    返回用户可管理的设备列表：
    - 若 devices 包含 'any'，则返回当前缓存中的所有设备 ID
    - 否则返回 sys_conf.json 中配置的设备列表
    """
    try:
        allowed_devices = GLOBAL_CONFIG.get("sys_admin", {}).get(username, {}).get("devices", [])
        if "any" in allowed_devices:
            device_scope=list(data_memory_cache.get_device_cache().keys())
            device_scope.append("any")
            return device_scope
        else:
            return allowed_devices
    except Exception as e:
        print(f"[ERROR] 读取管理员权限失败: {e}")
        return []


@app.on_event("startup")
def startup_tasks():
    # 启动 SES 服务
    thread = threading.Thread(target=ses_server, daemon=True)
    thread.start()

    start_task_center()

    # 启动缓存管理器
    data_memory_cache.start_device_cache_manager()

@app.on_event("shutdown")
def graceful_shutdown():
    print("[Cache] Application is shutting down, flushing cache to disk")
    end_task_center()
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
        response_data["data"]["sesPort"]=GLOBAL_CONFIG.get("http_service_port")
        response_data["data"]["mdmPort"]=GLOBAL_CONFIG.get("http_service_port")
        response_data["data"]["sesIp"]=GLOBAL_CONFIG.get("server_ip")
        response_data["data"]["mdmCertMd5"]=GLOBAL_mdmCertMd5
    except Exception as e:
        print(f"[ERROR] 无法加载响应文件: {e}")
        response_data = {"code": "500", "success": "false", "msg": "内部错误", "data": None}
    return fixed_json_response(response_data)

@app.post("/login/login")
async def login(request: Request):
    body = await request.body()
    print("Body:", body.decode())

    try:
        payload = json.loads(body)
        device_name = payload.get("deviceId", "").strip()
    except Exception as e:
        print(f"[ERROR] 登录请求解析失败: {e}")
        return fixed_json_response({"code": "400", "success": "false", "msg": "无效请求", "data": None})

    print(f"[LOGIN] Device '{device_name}' 尝试登录")

    if device_name and not task_exists_for_device(device_name):
        print(f"[TASK] 新设备 {device_name}，添加默认任务")
        try:
            add_device_default_tasks(device_name)
        except Exception as e:
            print(f"[ERROR] 添加默认任务失败: {e}")

    # 返回固定响应
    try:
        with RESPONSE_PATH.open("r", encoding="utf-8") as f:
            response_data = json.load(f)["login"]
        response_data["data"]["token"]=uuid.uuid4().hex
        response_data["data"]["ip"]=GLOBAL_CONFIG.get("server_ip")
        response_data["data"]["port"]=GLOBAL_CONFIG.get("tcp_service_port")
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
        #print("Body:", body.decode())
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

        #print("Body:", body.decode())
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
        #print("Body:", body.decode())
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
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })
    #return chunked_response_data_null()


@app.post("/nrm/androidTask/uploadLocationInfo")
async def uploadLocationInfo(request: Request):
    body = await request.body()
    print("[APRS_Service]Body:", body.decode())

    try:
        req_data = json.loads((await request.body()).decode())
        device_id = req_data.get("deviceId")

        if not device_id:
            raise ValueError("no deviceId")
        if float(req_data.get("latitude"))==0 and float(req_data.get("longitude"))==0:
            raise ValueError("invalid latitude or longitude")
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
        ssid_icon = entry.get("location", {}).get("aprs_icon","Q")
        print(f"[APRS_Service]entry.get(location).get(aprs_ssid):{device_ssid}")
        device_ssid=aprs_report(location_data["latitude"], location_data["longitude"], device_name, issiRadioId, device_id, device_ssid, ssid_icon)
        if device_ssid:
            print(f"[APRS_Service]aprs_report() return ssid {device_ssid}")
            location_data["aprs_ssid"] = device_ssid
            location_data["aprs_icon"] = ssid_icon
        #entry.setdefault("deviceId", device_id)
        entry["location"] = location_data
        entry["update_time"]= int(time.time())
        data_memory_cache.update_device_entry(device_id, entry)
        print(f"[APRS_Service][Cache]Report APRS for device_id：{device_id},device_ssid:{device_ssid}")

        
    except Exception as e:
        print(f"[APRS_Service][uploadLocationInfo] Logging error: {e}")

    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })


@app.get("/")
async def index(request: Request):
    server_ip = GLOBAL_CONFIG.get("server_ip", "")
    server_port = GLOBAL_CONFIG.get("http_service_port", "")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "server_ip": server_ip,
        "server_port": server_port
    })

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, filter_device: Optional[str] = None, map: Optional[str] = None):
    devices = data_memory_cache.get_device_cache()
    devices_all = data_memory_cache.get_device_cache()
    current_time = int(time.time())
    server_ip = GLOBAL_CONFIG.get("server_ip", "")
    server_port = GLOBAL_CONFIG.get("http_service_port", "")
    user = get_logged_in_user(request)

    for i in devices:
        if "update_time" not in devices[i]:
            devices[i]["update_time"]=devices[i]["location"]["update_time"]

        # 如果传入筛选设备ID，只保留该设备
    if filter_device:
        devices = {
            k: v for k, v in devices.items()
            if k == filter_device
        }
    # 如果登录了管理员
    if user and user in GLOBAL_CONFIG.get("sys_admin", {}):
        if map:
            # 更新当前用户的 map_type 并写回配置
            GLOBAL_CONFIG["sys_admin"][user]["map_type"] = map
            Path(GLOBAL_CONFIG_PATH).write_text(
                json.dumps(GLOBAL_CONFIG, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        else:
            # 如果未传入 map 参数，但用户配置中已有 map_type，则使用之
            map = GLOBAL_CONFIG["sys_admin"][user].get("map_type", "baidu")
    else:
        map = map or "baidu"

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "server_ip": server_ip,
        "server_port": server_port,
        "devices": devices,
        "devices_all": devices_all,
        "now": current_time,
        "logged_in_user": user,
        "map_type": map  # 新增传递地图类型
    })


@app.get("/device", response_class=HTMLResponse)
async def view_device(
    request: Request,
    deviceid: str = Query(...),
    admin_token: str = Cookie(None)
):
    entry = data_memory_cache.get_device_entry(deviceid)
    if not entry:
        return HTMLResponse(f"<h2>设备 {deviceid} 不存在</h2>", status_code=404)

    devicename = entry.get("deviceInfo", {}).get("wholeInfo", {}).get("alias", deviceid)

    if "sn" not in entry:
        return HTMLResponse(f"<h2>设备 {deviceid} 没有 SN 信息，无法验证</h2>", status_code=400)

    # --- token 验证逻辑 ---
    if admin_token:
        try:
            username = signer.unsign(admin_token, max_age=1800).decode()
            allowed = GLOBAL_CONFIG.get("sys_admin", {}).get(username, {}).get("devices", [])

            if "any" in allowed or deviceid in allowed:
                # 构造哈希跳转 URL，绕过验证页
                timestamp = int(time.time())
                sn = entry["sn"]
                sn_hash = hashlib.sha256((sn + str(timestamp)).encode("utf-8")).hexdigest()

                redirect_url = f"/device/deviceinfo?deviceid={deviceid}&timestamp={timestamp}&sn_hash={sn_hash}"
                return RedirectResponse(url=redirect_url)
        except BadSignature:
            pass
        except Exception as e:
            print(f"[admin_token 验证失败] {e}")

    # 否则显示 SN 验证页面
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
    user = get_logged_in_user(request)
    skip_sn = False

    if user:
        allowed = GLOBAL_CONFIG["sys_admin"].get(user, {}).get("devices", [])
        if "any" in allowed or device_id in allowed:
            skip_sn = True
    now_device_ssid=""
    if device_id:
        entry = data_memory_cache.get_device_entry(device_id)
        now_device_ssid = entry.get("location", {}).get("aprs_ssid","")
        now_device_icon = entry.get("location", {}).get("aprs_icon","")

    return templates.TemplateResponse("change_aprs_ssid.html", {
        "request": request,
        "device_id": device_id,
        "skip_sn": skip_sn,
        "now_device_ssid": now_device_ssid,
        "now_device_icon": now_device_icon
    })

@app.post("/change_aprs_ssid", response_class=HTMLResponse)
async def change_aprs_ssid_submit(
    request: Request,
    device_id: str = Form(...),
    sn: str = Form(""),  # 默认允许为空，便于跳过校验
    aprs_ssid: str = Form(...),
    aprs_icon: str = Form(default="Q")
):
    entry = data_memory_cache.get_device_entry(device_id)
    if not entry:
        return HTMLResponse("""
            <h3>找不到设备</h3>
            <button onclick="history.back()" style="margin-top: 10px;">返回</button>
        """, status_code=404)

    user = get_logged_in_user(request)
    skip_sn = False
    if user:
        allowed = GLOBAL_CONFIG["sys_admin"].get(user, {}).get("devices", [])
        if "any" in allowed or device_id in allowed:
            skip_sn = True

    if not skip_sn and sn != entry.get("sn"):
        return HTMLResponse("""
            <h3>SN 验证失败</h3>
            <button onclick="history.back()" style="margin-top: 10px;">返回</button>
        """, status_code=403)

    try:
        entry["location"]["aprs_ssid"] = aprs_ssid
        entry["location"]["aprs_icon"] = aprs_icon
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

@app.get("/admin/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/admin/login")
async def admin_login(
    request: Request,
    username: str = Form(...),
    password_hash: str = Form(...)
):
    # 获取管理员信息
    admin_info = GLOBAL_CONFIG.get("sys_admin", {}).get(username)

    if not admin_info:
        return templates.TemplateResponse("login.html", {"request": request, "error": "用户名错误"})

    # 获取对应的哈希密码
    expected_hash = admin_info.get("password")
    if not expected_hash or password_hash != expected_hash:
        return templates.TemplateResponse("login.html", {"request": request, "error": "密码错误"})

    # 登录成功，生成 token
    token = signer.sign(username.encode()).decode()
    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie("admin_token", token, max_age=1800, httponly=True)
    return response


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login")

    allowed_devices = GLOBAL_CONFIG["sys_admin"].get(username, {}).get("devices", [])
    if "any" in allowed_devices:
        device_ids = list(data_memory_cache.get_device_cache().keys())
    else:
        device_ids = allowed_devices

    devices = {
        device_id: data_memory_cache.get_device_entry(device_id)
        for device_id in device_ids
        if data_memory_cache.get_device_entry(device_id) is not None
    }

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": username,
        "devices": devices
    })

@app.post("/admin/change_password", response_class=HTMLResponse)
async def change_password(
    request: Request,
    username: str = Form(...),
    old_password_hash: str = Form(...),
    new_password_hash: str = Form(...)
):
    sys_admin = GLOBAL_CONFIG.get("sys_admin", {})
    user_entry = sys_admin.get(username)

    if not user_entry:
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "username": username,
            "devices": {},
            "success": False,
            "message": "用户不存在"
        })

    current_password_hash = user_entry.get("password")
    if current_password_hash != old_password_hash:
        return templates.TemplateResponse("admin_dashboard.html", {
            "request": request,
            "username": username,
            "devices": {},
            "success": False,
            "message": "原密码不正确"
        })

    # 更新密码
    user_entry["password"] = new_password_hash
    GLOBAL_CONFIG_PATH.write_text(json.dumps(GLOBAL_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "username": username,
        "devices": {},  # 如果你希望重新加载设备信息，可在此查询
        "success": True,
        "message": "密码修改成功"
    })


@app.get("/admin/taskcenter")
async def view_taskcenter(request: Request):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login")

    device_scope = get_user_device_scope(username)
    can_edit_all = "any" in device_scope

    tasks = load_tasks()

    # 获取有权限的设备任务列表
    if can_edit_all:
        visible_devices = list(tasks.get("device_task_list", {}).keys())
    else:
        visible_devices = [d for d in device_scope if d in tasks.get("device_task_list", {})]

    device_task_list = {
        dev: tasks["device_task_list"][dev] for dev in visible_devices
    }

    return templates.TemplateResponse("taskcenter.html", {
        "request": request,
        "username": username,
        "device_task_list": device_task_list,
        "task_templates": tasks.get("TaskConfig", {}),
        "default_tasks": tasks.get("Default_Task", []),
        "can_edit_default": can_edit_all
    })


@app.post("/admin/taskcenter/update_interval")
async def update_interval(request: Request, device_id: str = Form(...), task_index: int = Form(...), interval: int = Form(...)):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login")

    device_scope = get_user_device_scope(username)
    if device_id not in device_scope and "any" not in device_scope:
        return RedirectResponse("/admin/taskcenter")

    tasks = load_tasks()
    try:
        tasks["device_task_list"][device_id][task_index]["interval"] = interval
        save_tasks(tasks)
    except Exception as e:
        print(f"[ERROR] 更新任务间隔失败: {e}")

    return RedirectResponse("/admin/taskcenter", status_code=303)


@app.post("/admin/taskcenter/delete_task")
async def delete_task(request: Request, device_id: str = Form(...), task_index: int = Form(...)):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login")

    device_scope = get_user_device_scope(username)
    if device_id not in device_scope and "any" not in device_scope:
        return RedirectResponse("/admin/taskcenter")

    tasks = load_tasks()
    try:
        tasks["device_task_list"][device_id].pop(task_index)
        save_tasks(tasks)
    except Exception as e:
        print(f"[ERROR] 删除任务失败: {e}")

    return RedirectResponse("/admin/taskcenter", status_code=303)


@app.post("/admin/taskcenter/add_task")
async def add_task(request: Request, device_id: str = Form(...), task_name: str = Form(...), interval: int = Form(...)):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login")

    device_scope = get_user_device_scope(username)
    if device_id not in device_scope and "any" not in device_scope:
        return RedirectResponse("/admin/taskcenter")

    tasks = load_tasks()
    if task_name not in tasks.get("TaskConfig", {}):
        print(f"[ERROR] 任务模板不存在: {task_name}")
        return RedirectResponse("/admin/taskcenter")

    tasks["device_task_list"].setdefault(device_id, []).append({
        "task": task_name,
        "CommandUUID": "",
        "interval": interval,
        "lastExecuted": 0,
        "oneTime": False,
        "consumed": True
    })
    save_tasks(tasks)
    return RedirectResponse("/admin/taskcenter", status_code=303)


@app.post("/admin/taskcenter/update_default")
async def update_default_tasklist(request: Request, new_default: str = Form(...)):
    username = get_logged_in_user(request)
    if not username:
        return RedirectResponse("/admin/login", status_code=303)

    device_scope = get_user_device_scope(username)
    if "any" not in device_scope:
        return RedirectResponse("/admin/taskcenter", status_code=303)

    try:
        parsed = json.loads(new_default)
        if not isinstance(parsed, list) or not all(
            isinstance(item, dict) and "name" in item and "interval" in item
            for item in parsed
        ):
            raise ValueError("格式不正确")
    except Exception as e:
        print(f"[ERROR] Default_Task 格式错误: {e}")
        return RedirectResponse("/admin/taskcenter", status_code=303)

    tasks = load_tasks()
    tasks["Default_Task"] = parsed
    save_tasks(tasks)
    return RedirectResponse("/admin/taskcenter", status_code=303)


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