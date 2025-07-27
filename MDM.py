from fastapi import FastAPI, Request
from fastapi.responses import Response
from email.utils import formatdate
import json
from pathlib import Path
import time

app = FastAPI()

SERVER_HEADER = "nginx/1.24.0"

RESPONSE_PATH = Path("check_device_sn_response.json")
DEVICE_LOG_PATH = Path("device_registry_data.json")

def current_date_header() -> str:
    return formatdate(timeval=None, localtime=False, usegmt=True)


def fixed_json_response(data: dict) -> Response:
    body = json.dumps(data)
    headers = {
        "server": SERVER_HEADER,
        "date": current_date_header(),
        "content-type": "application/json",
        "content-length": str(len(body.encode("utf-8"))),
        "connection": "keep-alive"
    }
    return Response(content=body, headers=headers, media_type="application/json", status_code=200)


def chunked_response(data: dict) -> Response:
    body = json.dumps(data)
    chunked = f"{hex(len(body))[2:]}\r\n{body}\r\n0\r\n\r\n"
    headers = {
        "server": SERVER_HEADER,
        "date": current_date_header(),
        "content-type": "application/json",
        "transfer-encoding": "chunked",
        "connection": "keep-alive"
    }
    return Response(content=chunked, headers=headers, media_type="application/json", status_code=200)


@app.post("/nrm/androidTask/checkDeviceSn")
async def check_device_sn(request: Request):
    # 读取请求体
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
    except Exception as e:
        print(f"[WARN] 无法解析请求体: {e}")
        req_data = {}
        device_id = None

    if device_id:
        try:
            if DEVICE_LOG_PATH.exists():
                with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
                    registry = json.load(f)
            else:
                registry = {}
    
            existing = registry.get(device_id, {})
            existing.update(req_data)  # 合并更新
            registry[device_id] = existing
    
            with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            print(f"[LOG] 记录设备 deviceId: {device_id}")
        except Exception as e:
            print(f"[ERROR] 记录失败: {e}")

    # 返回固定响应
    try:
        with RESPONSE_PATH.open("r", encoding="utf-8") as f:
            response_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] 无法加载响应文件: {e}")
        response_data = {"code": "500", "success": "false", "msg": "内部错误", "data": None}

    return fixed_json_response(response_data)



@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
async def chunked_ok_empty_data(request: Request):
    try:
        body = await request.body()
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        device_info_raw = req_data.get("deviceInfo")

        if isinstance(device_info_raw, str):
            device_info = json.loads(device_info_raw)
        else:
            device_info = device_info_raw or {}

        # 记录 deviceInfo 到本地 JSON 文件
        if device_id:
            if DEVICE_LOG_PATH.exists():
                with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
                    device_registry = json.load(f)
            else:
                device_registry = {}

            entry = device_registry.get(device_id, {})
            entry["deviceId"] = device_id
            entry["deviceInfo"] = device_info
            device_registry[device_id] = entry

            with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                json.dump(device_registry, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"[getDeviceInfoFromAndroid] Logging error: {e}")

    # 返回原样 chunked 响应
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": ""
    })


@app.post("/nrm/androidTask/getAppInfoFromAndroid")
@app.post("/nrm/androidUploadInfo/uploadContact")
async def chunked_ok_empty_data(request: Request):
    await request.body()
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": ""
    })


@app.post("/nrm/androidUploadInfo/appMd5Check")
async def chunked_data_array(request: Request):
    await request.body()
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": []
    })


@app.post("/nrm/androidUploadInfo/uploadWorkInterfaceInfo")
@app.post("/nrm/androidTask/getAndroidCommand")
async def chunked_data_null(request: Request):
    body = await request.body()
    print("Body:", body.decode())
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })

@app.post("/nrm/androidTask/uploadLocationInfo")
async def chunked_data_null(request: Request):
    body = await request.body()
    print("Body:", body.decode())

    try:
        req_data = json.loads(body.decode())
        device_id = req_data.get("deviceId")
        location_data = {
            "latitude": req_data.get("latitude"),
            "longitude": req_data.get("longitude"),
            "altitude": req_data.get("altitude")
        }

        if device_id:
            if DEVICE_LOG_PATH.exists():
                with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
                    device_registry = json.load(f)
            else:
                device_registry = {}

            entry = device_registry.get(device_id, {})
            entry["deviceId"] = device_id
            entry["location"] = location_data
            entry["update_time"] = int(time.time())
            device_registry[device_id] = entry

            with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                json.dump(device_registry, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"[uploadLocationInfo] Logging error: {e}")

    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })


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
    uvicorn.run("main:app", host="0.0.0.0", port=8083, reload=True)