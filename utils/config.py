import hashlib
import json
import os
from pathlib import Path

# 1. 定义默认配置
DEFAULT_CONFIG = {
    "http_service_port": "2232",
    "tcp_service_port": "2233",
    "server_ip": "mdm.ctsdn.com",
    "sys_admin": {
        "admin": {
            "password": "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918",
            "devices": ["any", "00861067070143638"],
            "map_type": "openstreet"
        }
    }
}

# 2. 加载配置文件
def load_config_file():
    config_path = Path("data/sys_conf.json")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] 配置文件加载失败，使用默认配置: {e}")
    return {}

# 3. 读取环境变量
def get_env_config():
    env_config = {}
    if os.getenv("HTTP_SERVICE_PORT"):
        env_config["http_service_port"] = os.getenv("HTTP_SERVICE_PORT")
    if os.getenv("TCP_SERVICE_PORT"):
        env_config["tcp_service_port"] = os.getenv("TCP_SERVICE_PORT")
    if os.getenv("SERVER_IP"):
        env_config["server_ip"] = os.getenv("SERVER_IP")
    if os.getenv("ADMIN_PASSWORD"):
        hashed_pwd = hashlib.sha256(os.getenv("ADMIN_PASSWORD").encode()).hexdigest()
        env_config["sys_admin"] = {"admin": {"password": hashed_pwd}}
    if os.getenv("ALLOWED_DEVICES"):
        env_config.setdefault("sys_admin", {"admin": {}})["admin"]["devices"] = os.getenv("ALLOWED_DEVICES").split(",")
    if os.getenv("DEFAULT_MAP_TYPE"):
        env_config.setdefault("sys_admin", {"admin": {}})["admin"]["map_type"] = os.getenv("DEFAULT_MAP_TYPE")
    return env_config

# 4. 合并配置（优先级：环境变量 > 配置文件 > 默认值）
def merge_configs(env_conf, file_conf, default_conf):
    def deep_merge(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                deep_merge(target[key], value)
            else:
                target[key] = value
        return target
    merged = deep_merge(default_conf.copy(), file_conf)
    merged = deep_merge(merged, env_conf)
    return merged

# 生成最终配置
file_config = load_config_file()
env_config = get_env_config()
GLOBAL_CONFIG = merge_configs(env_config, file_config, DEFAULT_CONFIG)
