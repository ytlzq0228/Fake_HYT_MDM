import json
import time
import threading
import uuid
from pathlib import Path

TASK_FILE = Path("data/tasks.json")
LOCK = threading.Lock()

def load_tasks():
    if TASK_FILE.exists():
        with TASK_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("tasks.json 文件不存在，请先手动创建并配置")

def save_tasks(data):
    with LOCK:
        with TASK_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

def generate_command_uuid():
    return uuid.uuid4().hex

def task_producer_loop():
    while True:
        tasks = load_tasks()
        now = time.time()
        changed = False

        for device_id, task_list in tasks.get("device_task_list", {}).items():
            for task in task_list:
                if task.get("oneTime"):
                    continue

                if task["task"] not in tasks["TaskConfig"]:
                    raise ValueError(f"[task_producer] 模板 '{task['task']}' 不存在于 TaskConfig 中")

                last_executed = task.get("lastExecuted", 0)
                interval = task.get("interval", 0)

                if now - last_executed >= interval:
                    task["CommandUUID"] = generate_command_uuid()
                    task["lastExecuted"] = now
                    task["consumed"] = False
                    changed = True

        if changed:
            save_tasks(tasks)

        time.sleep(1)

def task_exists_for_device(device_id: str) -> bool:
    tasks = load_tasks()
    return device_id in tasks.get("device_task_list", {})


def add_device_default_tasks(device_id: str):
    tasks = load_tasks()
    if device_id in tasks.get("device_task_list", {}):
        return  # 已存在，跳过

    default_tasks = tasks.get("Default_Task", [])
    task_config = tasks.get("TaskConfig", {})
    tasks["device_task_list"][device_id] = []

    for task_def in default_tasks:
        task_name = task_def.get("name")
        interval = task_def.get("interval", 300)

        if not task_name or task_name not in task_config:
            print(f"[WARNING] 默认任务 '{task_name}' 在 TaskConfig 中不存在，跳过")
            continue

        tasks["device_task_list"][device_id].append({
            "task": task_name,
            "CommandUUID": "",
            "interval": interval,
            "lastExecuted": 0,
            "oneTime": False,
            "consumed": True
        })

    save_tasks(tasks)

def start_task_center():
    thread = threading.Thread(target=task_producer_loop, daemon=True)
    thread.start()