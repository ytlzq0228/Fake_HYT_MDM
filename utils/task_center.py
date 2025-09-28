import json
import os
import time
import threading
import uuid
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

TASK_FILE = Path("data/tasks.json")
LOCK = threading.RLock()
TASK_CACHE: Optional[Dict[str, Any]] = None  # 内存缓存
DISK_FLUSH_INTERVAL = 5  # 每 N 秒写入磁盘

# ------- 内部工具 -------

_DEFAULT_STRUCTURE: Dict[str, Any] = {
    "version": 1,
    "TaskConfig": {},
    "Default_Task": [],
    "device_task_list": {}  # device_id -> [task, ...]
}

def _ensure_parent_dir(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

def _validate_shape(obj: Any) -> Dict[str, Any]:
    """轻量结构校验，保证关键字段存在并类型正确。"""
    if not isinstance(obj, dict):
        return _DEFAULT_STRUCTURE.copy()
    obj.setdefault("version", 1)
    obj.setdefault("TaskConfig", {})
    obj.setdefault("Default_Task", [])
    obj.setdefault("device_task_list", {})
    if not isinstance(obj["TaskConfig"], dict):
        obj["TaskConfig"] = {}
    if not isinstance(obj["Default_Task"], list):
        obj["Default_Task"] = []
    if not isinstance(obj["device_task_list"], dict):
        obj["device_task_list"] = {}
    return obj

def _safe_load_json(path: Path) -> Dict[str, Any]:
    """
    文件存在：
      - 空文件或损坏 JSON -> 回退默认结构
      - 正常 -> 校验结构后返回
    文件不存在：
      - 维持与原逻辑兼容：由上层决定是否抛 FileNotFoundError
    """
    with path.open("rb") as f:
        data = f.read()
    if not data.strip():
        return _DEFAULT_STRUCTURE.copy()
    try:
        obj = json.loads(data.decode("utf-8"))
    except json.JSONDecodeError:
        return _DEFAULT_STRUCTURE.copy()
    return _validate_shape(obj)

def _atomic_dump_json(path: Path, payload: Dict[str, Any]):
    """原子写：临时文件写完 fsync 后再替换，避免半截文件。"""
    _ensure_parent_dir(path)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_tasks_", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmpf:
            json.dump(payload, tmpf, ensure_ascii=False, indent=2, separators=(",", ": "))
            tmpf.flush()
            os.fsync(tmpf.fileno())
        os.replace(tmp_path, str(path))
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except OSError:
            pass

# ------- 对外接口（保持兼容） -------

def _load_initial_cache():
    """初始化内存缓存：保持原接口。若文件不存在，仍按原逻辑抛 FileNotFoundError。"""
    global TASK_CACHE
    with LOCK:
        if TASK_FILE.exists():
            TASK_CACHE = _safe_load_json(TASK_FILE)
        else:
            # 与原实现保持一致：缺少文件时抛错
            raise FileNotFoundError("tasks.json 文件不存在，请先手动创建并配置")

def load_tasks():
    """只读返回缓存，不访问磁盘"""
    with LOCK:
        if TASK_CACHE is None:
            raise RuntimeError("任务缓存未初始化")
        return TASK_CACHE

def save_tasks(data):
    """更新内存缓存（不立即写盘）"""
    global TASK_CACHE
    with LOCK:
        TASK_CACHE = _validate_shape(data)

def flush_to_disk():
    """强制将缓存写入磁盘"""
    with LOCK:
        if TASK_CACHE is None:
            raise RuntimeError("任务缓存未初始化")
        _atomic_dump_json(TASK_FILE, TASK_CACHE)

def generate_command_uuid():
    return uuid.uuid4().hex

def task_producer_loop():
    """
    周期性扫描任务，按 interval 生成 CommandUUID。
    兼容点：
      - 沿用原有调度与字段：task, interval, lastExecuted, oneTime, consumed, CommandUUID
      - 当模板缺失时不再 raise，而是告警并跳过该条，避免线程整个退出
    """
    while True:
        try:
            with LOCK:
                tasks = load_tasks()  # 返回引用
                now = time.time()
                changed = False

                device_map = tasks.get("device_task_list", {})
                task_config = tasks.get("TaskConfig", {})

                for device_id, task_list in list(device_map.items()):
                    if not isinstance(task_list, list):
                        # 自动纠正为列表
                        device_map[device_id] = []
                        changed = True
                        continue

                    for task in task_list:
                        # oneTime 任务不重复生产
                        if task.get("oneTime"):
                            continue

                        tname = task.get("task")
                        if not tname or tname not in task_config:
                            # 与原实现不同：避免 raise 终止线程，仅告警并跳过
                            # 如需保持严格，可改回 raise
                            print(f"[task_producer][WARNING] 模板 '{tname}' 不存在于 TaskConfig 中，已跳过")
                            continue

                        last_executed = float(task.get("lastExecuted", 0) or 0)
                        interval = float(task.get("interval", 0) or 0)

                        if interval <= 0:
                            # 非法 interval，跳过但不终止循环
                            print(f"[task_producer][WARNING] 任务 '{tname}' interval 非法({interval})，已跳过")
                            continue

                        if now - last_executed >= interval:
                            task["CommandUUID"] = generate_command_uuid()
                            task["lastExecuted"] = now
                            task["consumed"] = False
                            changed = True

                if changed:
                    # 仅更新内存，由刷盘线程负责持久化
                    # 注：仍保持接口 save_tasks 的使用
                    save_tasks(tasks)
        except Exception as e:
            # 防止任何异常杀死生产者线程
            print(f"[task_producer][ERROR] {e}")

        time.sleep(1)

def disk_flush_loop():
    """定时将缓存刷入磁盘：仅在内容变化时写盘，减少抖动"""
    last_snapshot = None
    while True:
        try:
            with LOCK:
                if TASK_CACHE is not None:
                    snapshot = json.dumps(TASK_CACHE, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                else:
                    snapshot = None

            if snapshot is not None and snapshot != last_snapshot:
                flush_to_disk()
                last_snapshot = snapshot
        except Exception as e:
            print(f"[ERROR] 刷盘失败: {e}")

        time.sleep(DISK_FLUSH_INTERVAL)

def task_exists_for_device(device_id: str) -> bool:
    with LOCK:
        tasks = load_tasks()
        return device_id in tasks.get("device_task_list", {})

def add_device_default_tasks(device_id: str):
    with LOCK:
        tasks = load_tasks()
        if device_id in tasks.get("device_task_list", {}):
            return

        default_tasks = tasks.get("Default_Task", [])
        task_config = tasks.get("TaskConfig", {})
        tasks.setdefault("device_task_list", {})
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
    threading.Thread(target=task_producer_loop, daemon=True, name="task-producer").start()
    threading.Thread(target=disk_flush_loop, daemon=True, name="task-flusher").start()

def end_task_center():
    """在程序退出时强制将任务缓存写入磁盘"""
    try:
        flush_to_disk()
        print("[TaskCenter] 已手动触发任务缓存写盘")
    except Exception as e:
        print(f"[TaskCenter][ERROR] 手动写盘失败: {e}")