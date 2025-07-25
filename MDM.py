from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
import uvicorn
import json

app = FastAPI()


@app.post("/nrm/androidTask/checkDeviceSn")
async def check_device_sn(request: Request):
    data = await request.json()
    print(f"[checkDeviceSn] Received: {json.dumps(data, indent=2)}")

    response_data = {
        "code": "0",
        "success": "true",
        "msg": "",
        "data": {
            "sesPort": "8087",
            "mdmCertMd5": "470af1bd61ae8be30ac5b5ee61e487c7",
            "netDiskUrl": "http://10.0.200.99:8080/NetDiskWeb",
            "usageMode": "0",
            "mdmPort": "8083",
            "sesIp": "10.0.200.99",
            "checkResult": "0",
            "mdmScheme": "http",
            "isMasterSlaveModel": "0",
            "umcMode": "0"
        }
    }

    body_str = json.dumps(response_data)
    headers = {
        "Server": "nginx/1.24.0",
        "Date": "Fri, 25 Jul 2025 12:28:40 GMT",
        "Content-Type": "application/json",
        "Content-Length": str(len(body_str.encode("utf-8"))),
        "Connection": "keep-alive"
    }
    # 打印响应
    print("Response Headers:", headers)
    print("Response Body:", body_str)
    return Response(content=body_str, headers=headers, media_type="application/json")


@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
async def get_device_info(request: Request):
    body = await request.body()
    print(f"[getDeviceInfoFromAndroid] Raw body length: {len(body)}")

    body_str = json.dumps({"code": "0", "success": "true", "msg": ""})
    chunked = f"{hex(len(body_str))[2:]}\r\n{body_str}\r\n0\r\n\r\n"

    return Response(content=chunked, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


@app.post("/nrm/androidTask/uploadLocationInfo")
async def upload_location(request: Request):
    data = await request.json()
    print(f"[uploadLocationInfo] Received: {json.dumps(data, indent=2)}")

    body_str = json.dumps({"code": "0", "success": "true", "msg": "", "data": None})
    chunked = f"{hex(len(body_str))[2:]}\r\n{body_str}\r\n0\r\n\r\n"

    return Response(content=chunked, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


@app.post("/login/login")
async def login(request: Request):
    data = await request.json()
    print(f"[login] Received: {json.dumps(data, indent=2)}")

    response = {
        "msg": "",
        "code": "",
        "data": {
            "ip": "10.0.200.99",
            "port": "9999",
            "sslPort": "9997",
            "channelId": "",
            "token": "9d8d6205a63d437781419c6ed2a194b6",
            "updateMd5": "true"
        },
        "success": "true"
    }

    body_str = json.dumps(response)
    chunked = f"{hex(len(body_str))[2:]}\r\n{body_str}\r\n0\r\n\r\n"

    return Response(content=chunked, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


# 🟡 兜底处理器，返回固定响应体和固定响应头
@app.post("/{full_path:path}")
async def catch_all(request: Request, full_path: str):
    headers = dict(request.headers)
    body = await request.body()
    print(f"[UNKNOWN] POST /{full_path}?{request.url.query}")
    print("Headers:", headers)
    try:
        print("Body:", body.decode())
    except:
        print("Body: <non-decodable>")

    body_json = {"code": "0", "success": "true", "msg": "", "data": []}
    body_str = json.dumps(body_json)

    fixed_headers = {
        "Server": "nginx/1.24.0",
        "Date": "Fri, 25 Jul 2025 12:28:40 GMT",
        "Content-Type": "application/json",
        "Content-Length": str(len(body_str.encode("utf-8"))),
        "Connection": "keep-alive"
    }

    return Response(
        content=body_str,
        status_code=200,
        headers=fixed_headers,
        media_type="application/json"
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8083, reload=True)