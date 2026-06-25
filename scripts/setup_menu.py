"""设置企微自建应用底部菜单 (最多 3 个一级按钮)"""
import sys
sys.path.insert(0, ".")
from wecom_app import _get_token, _get_app_config
import requests

cfg = _get_app_config()
token = _get_token()
if not token:
    print("❌ 获取 access_token 失败")
    sys.exit(1)

menu = {
    "button": [
        {
            "name": "📊 分析",
            "sub_button": [
                {"name": "📈 市值快照", "type": "click", "key": "SNAPSHOT"},
                {"name": "📋 月度体检", "type": "click", "key": "CHECKUP"},
                {"name": "🚨 市场预警", "type": "click", "key": "ALERT"},
            ],
        },
        {
            "name": "⚙️ 设置",
            "sub_button": [
                {"name": "❓ 帮助", "type": "click", "key": "HELP"},
                {"name": "📊 资产看板", "type": "view", "url": "https://finance-assistant.mote-pal.xyz"},
                {"name": "📈 历史走势", "type": "view", "url": "https://finance-assistant.mote-pal.xyz/history"},
            ],
        },
        {
            "name": "🌐 看板",
            "type": "view",
            "url": "https://finance-assistant.mote-pal.xyz",
        },
    ]
}

url = f"https://qyapi.weixin.qq.com/cgi-bin/menu/create?access_token={token}&agentid={cfg['agentid']}"
r = requests.post(url, json=menu, timeout=10)
data = r.json()
if data.get("errcode") == 0:
    print("✅ 菜单设置成功！")
else:
    print(f"❌ 失败: {data}")
