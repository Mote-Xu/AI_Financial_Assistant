"""设置企微自建应用底部菜单"""
import sys
sys.path.insert(0, ".")
from wecom_app import _get_token, _get_app_config
import requests

cfg = _get_app_config()
token = _get_token()
if not token:
    print("❌ token failed")
    sys.exit(1)

menu = {
    "button": [
        {
            "name": "📊 分析",
            "sub_button": [
                {"name": "📈 快照", "type": "click", "key": "SNAPSHOT"},
                {"name": "📋 体检", "type": "click", "key": "CHECKUP"},
                {"name": "🚨 预警", "type": "click", "key": "ALERT"},
            ],
        },
        {
            "name": "💰 FIRE",
            "type": "click",
            "key": "FIRE",
        },
        {
            "name": "📋 更多",
            "sub_button": [
                {"name": "📈 走势", "type": "click", "key": "CHART"},
                {"name": "📊 回测", "type": "click", "key": "BACKTEST"},
                {"name": "❓ 帮助", "type": "click", "key": "HELP"},
            ],
        },
    ]
}

url = f"https://qyapi.weixin.qq.com/cgi-bin/menu/create?access_token={token}&agentid={cfg['agentid']}"
r = requests.post(url, json=menu, timeout=10)
d = r.json()
print("✅" if d.get("errcode") == 0 else f"❌ {d}")
