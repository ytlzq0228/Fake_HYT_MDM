import socket
import json
import threading

HOST = '0.0.0.0'
PORT = 2233

RESPONSE_6 = {
    "msgType": 6,
    "msgContent": json.dumps({
        "result": "true",
        "reason": ""
    })
}

RESPONSE_9 = {
    "msgType": 9,
    "msgContent": json.dumps({
        "UserName": "00861067070143638",
        "content": json.dumps({
            "CommandUUID": "e117fc8fd54c484d939c0cb157987ee1",
            "body": {
                "msgType": "deviceControlMsg",
                "reExecuteTimes": 0,
                "msgDate": "2025-07-29 21:01:15",
                "RequestType": "MultipleCommad"
            },
            "type": "HyteraCommand"
        }),
        "fromName": "push",
        "CommandUUID": "e117fc8fd54c484d939c0cb157987ee1"
    })
}


def handle_client(conn, addr):
    print(f"[+] Connection from {addr}")
    try:
        data = conn.recv(4096).decode("utf-8")
        print(f"[>] Received: {data}")

        try:
            payload = json.loads(data)
            msg_type = payload.get("msgType")
            msg_content_str = payload.get("msgContent", "{}")
            msg_content = json.loads(msg_content_str)

            if (
                msg_type == 5
                #and msg_content.get("name") == "00861067070143638"
                #and msg_content.get("password") == "077A7C98232FF38A0784BB89690BA91D"
                #and msg_content.get("token") == "04b9deb9bd03417bb07ee9c8b775f476"
                #and msg_content.get("type") == "0"
            ):
                # 发送第一条
                conn.sendall((json.dumps(RESPONSE_6) + "\n").encode("utf-8"))
                print("[<] Sent msgType 6")

                # 发送第二条
                conn.sendall((json.dumps(RESPONSE_9) + "\n").encode("utf-8"))
                print("[<] Sent msgType 9")

            else:
                print("[!] Invalid msgContent or msgType")
        except Exception as e:
            print(f"[!] JSON decode error: {e}")

    except Exception as e:
        print(f"[!] Error handling client {addr}: {e}")
    finally:
        conn.close()
        print(f"[-] Connection closed for {addr}")


def ses_server():
    print(f"[*] Starting TCP server on {HOST}:{PORT}")
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