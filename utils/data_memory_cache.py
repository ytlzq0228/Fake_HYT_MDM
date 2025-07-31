import json
import threading
import time
from pathlib import Path

DEVICE_LOG_PATH = Path("static/device_registry_data.json")

# 全局缓存与锁
_device_cache = {}
_cache_lock = threading.Lock()


def load_device_cache():
    """服务启动时读取已有数据到缓存"""
    global _device_cache
    if DEVICE_LOG_PATH.exists():
        try:
            with DEVICE_LOG_PATH.open("r", encoding="utf-8") as f:
                _device_cache = json.load(f)
                print(f"[Cache] Loaded {_device_cache.__len__()} records from file")
        except Exception as e:
            print(f"[Cache] Failed to load from file: {e}")


def save_device_cache_periodically(interval: int = 5):
    """后台线程定期保存缓存到磁盘"""
    while True:
        time.sleep(interval)
        try:
            with _cache_lock:
                with DEVICE_LOG_PATH.open("w", encoding="utf-8") as f:
                    json.dump(_device_cache, f, indent=2, ensure_ascii=False)
                print("[Cache] Flushed to disk")
        except Exception as e:
            print(f"[Cache] Failed to write to file: {e}")


def start_device_cache_manager():
    load_device_cache()
    thread = threading.Thread(target=save_device_cache_periodically, daemon=True)
    thread.start()


def update_device_entry(device_id: str, entry: dict):
    with _cache_lock:
        _device_cache[device_id] = entry


def get_device_entry(device_id: str) -> dict:
    with _cache_lock:
        return _device_cache.get(device_id, {}).copy()


def get_device_cache() -> dict:
    with _cache_lock:
        return _device_cache.copy()
