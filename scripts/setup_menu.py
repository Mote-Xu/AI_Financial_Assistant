"""企微菜单"""
import sys
sys.path.insert(0, ".")
from wecom_app import _get_token, _get_app_config
import requests

cfg = _get_app_config()
token = _get_token()
if not token:
    print("NO token")
    sys.exit(1)

# 三个一级菜单，按功能分类
menu = {
    "button": [
        {
            "name": "📈 行情",
            "sub_button": [
                {"name": "📊 市值快照", "type": "click", "key": "SNAPSHOT"},
                {"name": "📈 走势图", "type": "click", "key": "CHART"},
                {"name": "🚨 波动预警", "type": "click", "key": "ALERT"},
            ],
        },
        {
            "name": "🤖 分析",
            "sub_button": [
                {"name": "📋 月度体检", "type": "click", "key": "CHECKUP"},
                {"name": "💰 FIRE推算", "type": "click", "key": "FIRE"},
                {"name": "📊 定投回测", "type": "click", "key": "BACKTEST"},
            ],
        },
        {
            "name": "⚙️ 更多",
            "sub_button": [
                {"name": "❓ 使用帮助", "type": "click", "key": "HELP"},
            ],
        },
    ]
}

url = f"https://qyapi.weixin.qq.com/cgi-bin/menu/create?access_token={token}&agentid={cfg['agentid']}"
r = requests.post(url, json=menu, timeout=10)
print("OK" if r.json().get("errcode") == 0 else f"ERR {r.json()}")
