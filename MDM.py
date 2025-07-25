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
    return JSONResponse(content=response_data)


@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
async def get_device_info(request: Request):
    body = await request.body()
    print(f"[getDeviceInfoFromAndroid] Raw body length: {len(body)}")

    # 返回分块编码的响应（模拟 chunked transfer）
    chunk = '26\r\n{"code":"0","success":"true","msg":""}\r\n0\r\n\r\n'
    return Response(content=chunk, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


@app.post("/login/login")
async def login(request: Request):
    data = await request.json()
    print(f"[login] Received: {json.dumps(data, indent=2)}")

    token = "9d8d6205a63d437781419c6ed2a194b6"  # 瞎编的token
    response = {
        "msg": "",
        "code": "",
        "data": {
            "ip": "10.0.200.99",
            "port": "9999",
            "sslPort": "9997",
            "channelId": "",
            "token": token,
            "updateMd5": "true"
        },
        "success": "true"
    }

    # 手动构造 chunked 响应
    body = json.dumps(response)
    chunked = f"{hex(len(body))[2:]}\r\n{body}\r\n0\r\n\r\n"
    return Response(content=chunked, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


@app.post("/nrm/androidTask/uploadLocationInfo")
async def upload_location(request: Request):
    data = await request.json()
    print(f"[uploadLocationInfo] Received: {json.dumps(data, indent=2)}")

    chunk = '32\r\n{"code":"0","success":"true","msg":"","data":null}\r\n0\r\n\r\n'
    return Response(content=chunk, media_type="application/json", headers={"Transfer-Encoding": "chunked"})


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8083, reload=True)