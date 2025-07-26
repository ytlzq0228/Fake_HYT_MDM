from fastapi import FastAPI, Request
from fastapi.responses import Response
from email.utils import formatdate
import json

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
    return fixed_json_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": {
            "sesPort": "8087",
            "mdmCertMd5": "470af1bd61ae8be30ac5b5ee61e487c7",
            "netDiskUrl": "http://192.168.31.221:8080/NetDiskWeb",
            "usageMode": "0",
            "mdmPort": "8083",
            "sesIp": "122.9.161.134",
            "checkResult": "0",
            "mdmScheme": "http",
            "isMasterSlaveModel": "0",
            "umcMode": "0"
        }
    })


@app.post("/nrm/androidTask/getDeviceInfoFromAndroid")
@app.post("/nrm/androidTask/getAppInfoFromAndroid")
@app.post("/nrm/androidUploadInfo/uploadContact")
@app.post("/nrm/androidTask/getAndroidCommand")
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
async def chunked_data_null(request: Request):
    await request.body()
    return chunked_response({
        "code": "0",
        "success": "true",
        "msg": "",
        "data": None
    })

@app.post("/nrm/androidTask/uploadLocationInfo")
async def chunked_data_null(request: Request):
    await request.body()
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