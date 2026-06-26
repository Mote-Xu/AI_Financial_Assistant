"""
企业微信自建应用 API — 主动推送消息到指定用户
用于回调回复、进度通知等，不走群机器人 webhook
"""

import os
import time
import threading
import requests
from pathlib import Path

_token_lock = threading.Lock()


def _get_app_config():
    """读取自建应用配置（CorpID + Secret + AgentID）"""
    config = {"corpid": "", "secret": "", "agentid": "1000002"}
    keys = {
        "WECOM_CORP_ID": "corpid",
        "WECOM_APP_SECRET": "secret",
        "WECOM_AGENT_ID": "agentid",
    }
    for env_key, cfg_key in keys.items():
        val = os.environ.get(env_key, "")
        if not val:
            env_file = Path(__file__).parent.parent / ".env"
            if env_file.exists():
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(env_key + "="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
        if val:  # 只覆盖非空值，保留默认值
            config[cfg_key] = val
    return config if config["corpid"] and config["secret"] else None


# 缓存 access_token
_token_cache = {"token": "", "expires": 0}


def _get_token() -> str | None:
    """获取应用 access_token（线程安全缓存）"""
    cfg = _get_app_config()
    if not cfg:
        return None

    now = time.time()
    with _token_lock:
        if _token_cache["token"] and now < _token_cache["expires"]:
            return _token_cache["token"]

    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={cfg['corpid']}&corpsecret={cfg['secret']}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("errcode") == 0:
            with _token_lock:
                _token_cache["token"] = data["access_token"]
                _token_cache["expires"] = now + data.get("expires_in", 7200) - 300
            return _token_cache["token"]
    except Exception:
        pass
    return None


def send_to_user(user_id: str, content: str) -> bool:
    """
    向指定用户发送消息（出现在应用私聊中）
    user_id: 回调中的 FromUserName
    """
    token = _get_token()
    if not token:
        return False

    cfg = _get_app_config()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    payload = {
        "touser": user_id,
        "msgtype": "text",
        "agentid": int(cfg["agentid"]),
        "text": {"content": content},
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        return data.get("errcode") == 0
    except Exception:
        return False


def send_markdown_to_user(user_id: str, content: str) -> bool:
    """向指定用户发送 Markdown 消息"""
    token = _get_token()
    if not token:
        return False

    cfg = _get_app_config()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
    payload = {
        "touser": user_id,
        "msgtype": "markdown",
        "agentid": int(cfg["agentid"]),
        "markdown": {"content": content},
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        data = r.json()
        return data.get("errcode") == 0
    except Exception:
        return False
