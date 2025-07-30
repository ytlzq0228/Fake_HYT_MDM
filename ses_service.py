import socket
import json
import threading
import time
import json
import uuid
from datetime import datetime
HOST = '0.0.0.0'
PORT = 2233

RESPONSE_6 = {
    "msgType": 6,
    "msgContent": json.dumps({
        "result": "true",
        "reason": ""
    })
}

def build_response_9(user_name: str = "00861067070143638") -> dict:
    command_uuid = uuid.uuid4().hex
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

                if msg_type == 5:
                    # 发送第一条
                    conn.sendall((json.dumps(RESPONSE_6) + "\n").encode("utf-8"))
                    print("[<] Sent msgType 6")
                    time.sleep(1)
                    # 发送第二条
                    conn.sendall((json.dumps(build_response_9()) + "\n").encode("utf-8"))
                    print("[<] Sent msgType 9")
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