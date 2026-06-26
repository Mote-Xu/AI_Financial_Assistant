"""
每日数据备份 — SQLite + CSV + Markdown → zip 存档
保留 30 天，自动轮转
用法: python scripts/backup.py [--list]
"""

import sys
import os
import zipfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from config import FINANCE_DIR, DB_PATH, HISTORY_FILE, SNAPSHOT_FILE, ensure_finance_dir

BACKUP_DIR = FINANCE_DIR / ".backups"
RETENTION_DAYS = 30


def _get_zip_name() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M") + ".zip"


def create_backup() -> Path | None:
    """创建增量备份包，返回备份文件路径"""
    ensure_finance_dir()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    zip_name = _get_zip_name()
    zip_path = BACKUP_DIR / zip_name

    # 收集需要备份的文件
    files_to_backup = []
    patterns = [
        "*.md",          # assets/income/insurance/liabilities/goals + analysis_* + snapshot
        "*.csv",         # history
        "*.db",          # SQLite
    ]

    for pattern in patterns:
        for f in FINANCE_DIR.glob(pattern):
            if f.is_file() and ".backups" not in str(f):
                files_to_backup.append(f)

    if not files_to_backup:
        print("⚠️ 没有找到需要备份的文件")
        return None

    try:
        with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files_to_backup:
                arcname = str(f.relative_to(FINANCE_DIR))
                zf.write(str(f), arcname)

        size_kb = zip_path.stat().st_size / 1024
        print(f"✅ 备份完成: {zip_name} ({size_kb:.0f} KB, {len(files_to_backup)} 个文件)")
        return zip_path
    except Exception as e:
        print(f"❌ 备份失败: {e}")
        return None


def rotate_backups():
    """清理超过保留期的旧备份"""
    if not BACKUP_DIR.exists():
        return

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0
    for f in sorted(BACKUP_DIR.glob("*.zip")):
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime < cutoff:
            f.unlink()
            deleted += 1

    if deleted:
        print(f"🗑️ 清理 {deleted} 个过期备份（>{RETENTION_DAYS}天）")


def list_backups():
    """列出所有备份"""
    if not BACKUP_DIR.exists():
        print("📭 暂无备份")
        return

    backups = sorted(BACKUP_DIR.glob("*.zip"), reverse=True)
    print(f"📦 {len(backups)} 个备份:\n")
    for f in backups:
        size = f.stat().st_size / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        print(f"  {f.name:20s} {size:6.0f} KB  {mtime.strftime('%m/%d %H:%M')}")


def main():
    if "--list" in sys.argv:
        list_backups()
        return

    path = create_backup()
    if path:
        rotate_backups()


if __name__ == "__main__":
    main()
