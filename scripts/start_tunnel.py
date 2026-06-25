"""启动 cloudflared 公网隧道 — 持久运行，URL 写入文件"""
import pycloudflared
import time
import os
from pathlib import Path

URL_FILE = Path(__file__).parent.parent / ".tunnel_url"

def main():
    print("Downloading cloudflared binary (one-time, ~50MB)...", flush=True)

    try:
        result = pycloudflared.try_cloudflare(5000)
        tunnel_url = result.tunnel
    except Exception as e:
        print(f"Error: {e}", flush=True)
        return 1

    # Write URL to file
    URL_FILE.write_text(tunnel_url)
    print(f"\n{'='*60}")
    print(f"  🌐 {tunnel_url}/control")
    print(f"  📱 手机浏览器打开上方链接 → 点按钮 → 报告推回手机")
    print(f"  📍 URL 已保存到: {URL_FILE}")
    print(f"{'='*60}\n")
    print("Tunnel active. Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\nTunnel stopped.")
        URL_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
