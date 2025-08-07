import json
import time
import threading
import uuid
from pathlib import Path

TASK_FILE = Path("data/tasks.json")
LOCK = threading.Lock()
TASK_CACHE = None  # 内存缓存
DISK_FLUSH_INTERVAL = 5  # 每 N 秒写入磁盘

def _load_initial_cache():
    global TASK_CACHE
    if TASK_FILE.exists():
        with TASK_FILE.open("r", encoding="utf-8") as f:
            TASK_CACHE = json.load(f)
    else:
        raise FileNotFoundError("tasks.json 文件不存在，请先手动创建并配置")

def load_tasks():
    """只读返回缓存，不访问磁盘"""
    if TASK_CACHE is None:
        raise RuntimeError("任务缓存未初始化")
    return TASK_CACHE

def save_tasks(data):
    """更新内存缓存（不立即写盘）"""
    global TASK_CACHE
    with LOCK:
        TASK_CACHE = data

def flush_to_disk():
    """强制将缓存写入磁盘"""
    with LOCK:
        with TASK_FILE.open("w", encoding="utf-8") as f:
            json.dump(TASK_CACHE, f, indent=2)

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

def disk_flush_loop():
    """定时将缓存刷入磁盘"""
    while True:
        try:
            flush_to_disk()
        except Exception as e:
            print(f"[ERROR] 刷盘失败: {e}")
        time.sleep(DISK_FLUSH_INTERVAL)

def task_exists_for_device(device_id: str) -> bool:
    tasks = load_tasks()
    return device_id in tasks.get("device_task_list", {})

def add_device_default_tasks(device_id: str):
    tasks = load_tasks()
    if device_id in tasks.get("device_task_list", {}):
        return

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
    _load_initial_cache()
    threading.Thread(target=task_producer_loop, daemon=True).start()
    threading.Thread(target=disk_flush_loop, daemon=True).start()

def end_task_center():
    """在程序退出时强制将任务缓存写入磁盘"""
    try:
        flush_to_disk()
        print("[TaskCenter] 已手动触发任务缓存写盘")
    except Exception as e:
        print(f"[TaskCenter][ERROR] 手动写盘失败: {e}")