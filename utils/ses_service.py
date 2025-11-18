import socket
import json
import threading
import time
import json
import uuid
from datetime import datetime
from utils.task_center import load_tasks, save_tasks
from utils.config import GLOBAL_CONFIG

HOST = '0.0.0.0'
PORT = int(GLOBAL_CONFIG["tcp_service_port"])  # 从配置读取端口

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

def pop_next_task_for_device(device_id: str):
    tasks = load_tasks()
    device_tasks = tasks.get("device_task_list", {}).get(device_id, [])

    for task_ref in device_tasks:
        if not task_ref.get("consumed", False):
            task_name = task_ref["task"]
            task_template = tasks["TaskConfig"].get(task_name)
            if task_template:
                # 标记为已消费
                task_ref["consumed"] = True
                task_ref["lastExecuted"] = time.time()
                save_tasks(tasks)

                # 合并 CommandUUID 进任务模板
                task_data = {
                    "CommandUUID": task_ref["CommandUUID"],
                    "body": task_template["body"],
                    "type": task_template["type"]
                }

                return task_data

    return None

RESPONSE_6 = {
    "msgType": 6,
    "msgContent": json.dumps({
        "result": "true",
        "reason": ""
    })
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
                    # 发送命令

                    task_obj = pop_next_task_for_device(name)
                    if task_obj:
                        task_body = task_obj["body"].copy()
                        task_body["msgDate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                        response = {
                            "msgType": 9,
                            "msgContent": json.dumps({
                                "UserName": name,
                                "fromName": "push",
                                "CommandUUID": task_obj["CommandUUID"],
                                "content": json.dumps({
                                    "CommandUUID": task_obj["CommandUUID"],
                                    "type": task_obj["type"],
                                    "body": task_body
                                })
                            })
                        }
                
                        conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
                        print(f"[<] Sent task {task_body['RequestType']} to {name}")
                    else:
                        print(f"[!] No pending task for device {name}")
                

                    #conn.sendall((json.dumps(build_response_9(user_name=name)) + "\n").encode("utf-8"))
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
