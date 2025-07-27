from fastapi import FastAPI, Request
from fastapi.responses import Response
from email.utils import formatdate
import json
from pathlib import Path

app = FastAPI()

SERVER_HEADER = "nginx/1.24.0"


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
    await request.body()

    # 从 JSON 文件中加载响应体
    response_path = Path("check_device_sn_response.json")
    with response_path.open("r", encoding="utf-8") as f:
        response_data = json.load(f)

    return fixed_json_response(response_data)



@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
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
@app.post("/nrm/androidTask/uploadLocationInfo")
async def chunked_data_null(request: Request):
    body = await request.body()
    print("Body:", body.decode())
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