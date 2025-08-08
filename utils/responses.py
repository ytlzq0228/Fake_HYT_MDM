import json
import time
from email.utils import formatdate
from fastapi.responses import Response

def current_date_header() -> str:
    """生成符合 GMT 要求的日期头"""
    return formatdate(timeval=None, localtime=False, usegmt=True)

def fixed_json_response(data: dict) -> Response:
    """
    返回标准 JSON 响应，带固定长度的 Content-Length。
    用于普通 JSON 响应。
    """
    body = json.dumps(data)
    headers = {
        "server": "nginx/1.24.0",
        "date": current_date_header(),
        "content-type": "application/json",
        "content-length": str(len(body.encode("utf-8"))),
        "connection": "keep-alive"
    }
    return Response(
        content=body,
        headers=headers,
        media_type="application/json",
        status_code=200
    )

def chunked_response(data: dict) -> Response:

    # JSON 内容（和真实服务器保持一致）
    #data = {"code": "0", "success": "true", "msg": "", "data": None}
    body_json = json.dumps(data, separators=(",", ":"))

    # 头部——只让框架包一层 chunk
    headers = {
        "Server": "nginx/1.24.0",
        "Date": formatdate(usegmt=True),
        "Content-Type": "application/json",
        "Transfer-Encoding": "chunked",
        "Connection": "keep-alive",
    }

    # 直接交给 Response，不手动拼 chunk
    return Response(content=body_json, status_code=200, headers=headers)

def chunked_response_data_null():
    # JSON 内容（和真实服务器保持一致）
    data = {"code": "0", "success": "true", "msg": "", "data": None}
    body_json = json.dumps(data, separators=(",", ":"))

    # 头部——只让框架包一层 chunk
    headers = {
        "Server": "nginx/1.24.0",
        "Date": formatdate(usegmt=True),
        "Content-Type": "application/json",
        "Transfer-Encoding": "chunked",
        "Connection": "keep-alive",
    }

    # 直接交给 Response，不手动拼 chunk
    return Response(content=body_json, status_code=200, headers=headers)