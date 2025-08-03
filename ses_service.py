import socket
import json
import threading
import time
import json
import uuid
from datetime import datetime
HOST = '0.0.0.0'
PORT = 2233

# 全局缓存
_cached_uuid = None
_cached_time = 0
UUID_CACHE_SECONDS = 120  # 缓存有效期（单位：秒）

def get_cached_uuid():
    global _cached_uuid, _cached_time
    now = time.time()

    if now - _cached_time > UUID_CACHE_SECONDS:
        _cached_uuid = uuid.uuid4().hex
        _cached_time = now

    return _cached_uuid

RESPONSE_6 = {
    "msgType": 6,
    "msgContent": json.dumps({
        "result": "true",
        "reason": ""
    })
}

def build_response_9(user_name: str = "") -> dict:
    command_uuid = get_cached_uuid()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = {
        "CommandUUID": command_uuid,
        "body": {
            "msgType": "deviceControlMsg",
            "reExecuteTimes": 0,
            "msgDate": now_str,
            "RequestType": "MultipleCommad"
        },
        "type": "HyteraCommand"
    }

    msg_content = {
        "UserName": user_name,
        "content": json.dumps(content),
        "fromName": "push",
        "CommandUUID": command_uuid
    }

    return {
        "msgType": 9,
        "msgContent": json.dumps(msg_content)
    }

def build_response_9_data(user_name: str = "") -> dict:
    command_uuid = get_cached_uuid()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    content = {
        "CommandUUID": command_uuid,
        "body": {
            "msgType": "read_frequencySilent",
            "reExecuteTimes": 0,
            "msgDate": now_str,
            "RequestType": "backupData"
        },
        "type": "HyteraCommand"
    }

    msg_content = {
        "UserName": user_name,
        "content": json.dumps(content),
        "fromName": "push",
        "CommandUUID": command_uuid
    }

    return {
        "msgType": 9,
        "msgContent": json.dumps(msg_content)
    }

def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                print(f"[-] Client {addr} disconnected")
                break

            try:
                decoded = data.decode("utf-8")
                print(f"[>] Received: {decoded}")

                payload = json.loads(decoded)
                msg_type = payload.get("msgType")
                msg_content_str = payload.get("msgContent", "{}")
                msg_content = json.loads(msg_content_str)
                name=msg_content.get("name", "")

                if msg_type == 5:
                    # 发送第一条
                    conn.sendall((json.dumps(RESPONSE_6) + "\n").encode("utf-8"))
                    print("[<] Sent msgType 6")
                elif msg_type == 4:
                    # 发送第二条
                    conn.sendall((json.dumps(build_response_9(user_name=name)) + "\n").encode("utf-8"))
                    #conn.sendall((json.dumps(build_response_9_data(user_name=name)) + "\n").encode("utf-8"))
                    print("[<] Sent msgType 9")
                elif msg_type == 8:
                    print("[>] Received Command ACK Good!")
                else:
                    print("[!] Invalid msgContent or msgType")

            except json.JSONDecodeError as e:
                print(f"[!] JSON decode error: {e}")
            except Exception as e:
                print(f"[!] Error processing data from {addr}: {e}")

    except Exception as e:
        print(f"[!] Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"[-] Connection closed for {addr}")

def ses_server():
    print(f"[*] Starting SES server on {HOST}:{PORT}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen()

        while True:
            conn, addr = server.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()


if __name__ == "__main__":
    ses_server()