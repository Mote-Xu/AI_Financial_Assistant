"""
企业微信自建应用 — 消息加解密模块
协议: AES-256-CBC + PKCS7 padding
参考: https://developer.work.weixin.qq.com/document/path/90968
"""

import base64
import hashlib
import struct
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad


def _get_corp_config():
    """从 .env 或环境变量读取企微自建应用配置"""
    config = {}
    keys = {
        "WECOM_CORP_ID": "corp_id",
        "WECOM_APP_TOKEN": "token",
        "WECOM_APP_AES_KEY": "aes_key",
    }
    # 先查环境变量
    for env_key, cfg_key in keys.items():
        config[cfg_key] = os.environ.get(env_key, "")

    # 再查 .env 文件
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                for env_key, cfg_key in keys.items():
                    if line.startswith(env_key + "="):
                        config[cfg_key] = line.split("=", 1)[1].strip().strip('"').strip("'")

    # Allow testing with env var override
    if not config["corp_id"]:
        config["corp_id"] = os.environ.get("WECOM_CORP_ID", "")
    return config if config["token"] and config["aes_key"] else None


def _get_aes_key(aes_key_str: str) -> bytes:
    """EncodingAESKey 是 Base64 编码的 43 字符，解码后 32 字节"""
    # 企微的 key 是 43 字符，需要补一个 '=' 变成标准 base64
    return base64.b64decode(aes_key_str + "=")


def decrypt(encrypted: str, signature: str, timestamp: str, nonce: str) -> str | None:
    """
    解密企微回调消息
    Returns: 解密后的 XML 字符串，失败返回 None
    """
    cfg = _get_corp_config()
    if not cfg:
        return None

    # 1. 验证签名
    tmp = sorted([cfg["token"], timestamp, nonce, encrypted])
    expected = hashlib.sha1("".join(tmp).encode()).hexdigest()
    if signature != expected:
        return None

    # 2. AES 解密
    try:
        aes_key = _get_aes_key(cfg["aes_key"])
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])
        raw = cipher.decrypt(base64.b64decode(encrypted))

        # 3. 去除 PKCS7 padding + 解析: random(16) + msg_len(4) + msg + corp_id
        raw = unpad(raw, 32)
        msg_len = struct.unpack("!I", raw[16:20])[0]
        msg = raw[20:20 + msg_len].decode("utf-8")
        return msg
    except Exception:
        return None


def encrypt(reply_msg: str, nonce: str) -> tuple[str, str, str] | None:
    """
    加密回复消息
    Returns: (encrypted, signature, timestamp) 或 None
    """
    cfg = _get_corp_config()
    if not cfg:
        return None

    try:
        import time
        aes_key = _get_aes_key(cfg["aes_key"])
        cipher = AES.new(aes_key, AES.MODE_CBC, iv=aes_key[:16])

        # 构造: random(16) + msg_len(4) + msg + corp_id
        random_bytes = os.urandom(16)
        msg_bytes = reply_msg.encode("utf-8")
        msg_len_bytes = struct.pack("!I", len(msg_bytes))
        corp_id_bytes = cfg["corp_id"].encode("utf-8")
        raw = random_bytes + msg_len_bytes + msg_bytes + corp_id_bytes

        encrypted = base64.b64encode(cipher.encrypt(pad(raw, 32))).decode()
        timestamp = str(int(time.time()))

        # 签名
        token = cfg["token"]
        tmp = sorted([token, timestamp, nonce, encrypted])
        signature = hashlib.sha1("".join(tmp).encode()).hexdigest()

        return encrypted, signature, timestamp
    except Exception:
        return None
