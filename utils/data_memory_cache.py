import json
import threading
import time
from pathlib import Path
import copy

DEVICE_LOG_PATH = Path("static/device_data.json")

# 全局缓存与锁
_device_cache = {}
_cache_lock = threading.RLock()  # 使用可重入锁防止死锁


def load_device_cache():
    """服务启动时读取已有数据到缓存"""
    global _device_cache
    with _cache_lock:
        if DEVICE_LOG_PATH.exists():
            try:
                with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
                    _device_cache = json.load(f)
                    print(f"[Cache] Loaded {len(_device_cache)} records from file")
            except Exception as e:
                print(f"[Cache] Failed to load from file: {e}")
        else:
            _device_cache = {}


def save_device_cache_periodically(interval: int = 5):
    """后台线程定期保存缓存到磁盘"""
    while True:
        time.sleep(interval)
        with _cache_lock:
            try:
                temp_cache = copy.deepcopy(_device_cache)  # 避免中途修改
                with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                    json.dump(temp_cache, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[Cache] Failed to write to file: {e}")


def start_device_cache_manager():
    load_device_cache()
    thread = threading.Thread(target=save_device_cache_periodically, daemon=True)
    thread.start()


def update_device_entry(device_id: str, partial_update: dict):
    """对指定设备进行增量更新，而非替换整个 entry"""
    with _cache_lock:
        entry = _device_cache.get(device_id, {})
        entry.update(partial_update)  # 增量更新，保留已有字段
        _device_cache[device_id] = entry


def get_device_entry(device_id: str) -> dict:
    with _cache_lock:
        return copy.deepcopy(_device_cache.get(device_id, {}))


def get_device_cache() -> dict:
    with _cache_lock:
        return copy.deepcopy(_device_cache)

def save_device_cache_once():
    """立即保存一次缓存到文件"""
    try:
        with _cache_lock:
            with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                json.dump(_device_cache, f, indent=2, ensure_ascii=False)
            print("[Cache] Flushed to disk (on shutdown)")
    except Exception as e:
        print(f"[Cache] Failed to flush on shutdown: {e}")