from fastapi import FastAPI, Request
from fastapi.responses import Response
import httpx
import uvicorn

REMOTE_HOST = "http://122.9.161.134:8083"

app = FastAPI()


@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(full_path: str, request: Request):
    # 收集原始请求内容
    method = request.method
    headers = dict(request.headers)
    query_string = request.url.query
    body = await request.body()

    # 打印请求详情
    print(f"\n--- Received Request ---")
    print(f"{method} /{full_path}?{query_string}")
    print("Headers:", headers)
    print("Body:", body.decode(errors="ignore"))

    # 转发请求到远端
    url = f"{REMOTE_HOST}/{full_path}"
    if query_string:
        url += f"?{query_string}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(method, url, content=body, headers=headers)

    # 打印响应
    print(f"\n--- Remote Response [{resp.status_code}] ---")
    print("Response Headers:", dict(resp.headers))
    print("Response Body:", resp.text)

    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))


if __name__ == "__main__":
    uvicorn.run("proxy_server:app", host="0.0.0.0", port=8083, reload=True)