"""
集中式路径配置 — 所有脚本统一从这里获取路径
通过 FINANCE_DATA_DIR 环境变量切换 demo/真实数据目录

用法:
    from config import FINANCE_DIR, ASSETS_FILE, ensure_finance_dir

    # Demo 模式（默认）: FINANCE_DIR → <project>/finance_demo/
    # 真实模式: export FINANCE_DATA_DIR=finance  → <project>/finance/
    # 外部路径: export FINANCE_DATA_DIR=~/MyData/ → /home/user/MyData/

注意: 本模块不产生副作用 — 调用 ensure_finance_dir() 才会创建目录
"""

import os
from pathlib import Path

# === 项目根目录 (AI_Financial_Assistant/) ===
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# === 数据目录 ===
# 优先级: 环境变量 > 默认 finance_demo
_env_dir = os.getenv("FINANCE_DATA_DIR", "")
if _env_dir:
    _p = Path(_env_dir).expanduser().resolve()
    if _p.is_absolute():
        FINANCE_DIR = _p
    else:
        # 极端情况: expanduser+resolve 后仍非绝对（不太可能）
        FINANCE_DIR = (PROJECT_ROOT / _env_dir).resolve()
else:
    FINANCE_DIR = (PROJECT_ROOT / "finance_demo").resolve()


def ensure_finance_dir():
    """显式创建数据目录 — 在入口脚本中调用，避免 import 副作用"""
    FINANCE_DIR.mkdir(parents=True, exist_ok=True)


# === 文件锁（防止 cron 重叠执行） ===
# Linux: fcntl.flock（操作系统管理，进程崩溃自动释放）
# Windows: 文件 touch/unlink 兜底
import sys as _sys
_lock_fd = None

def acquire_lock() -> bool:
    """尝试获取运行锁，返回 True 表示可以继续执行"""
    global _lock_fd
    if _sys.platform == "linux":
        import fcntl
        _lock_fd = open(FINANCE_DIR / ".runner.lock", "w")
        try:
            fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            return False
    else:
        # Windows 兜底
        _lock_file = FINANCE_DIR / ".runner.lock"
        if _lock_file.exists():
            return False
        _lock_file.touch()
        return True


def release_lock():
    """释放运行锁"""
    global _lock_fd
    if _sys.platform == "linux" and _lock_fd:
        try:
            import fcntl
            fcntl.flock(_lock_fd, fcntl.LOCK_UN)
            _lock_fd.close()
        except Exception:
            pass
    else:
        try:
            (FINANCE_DIR / ".runner.lock").unlink(missing_ok=True)
        except Exception:
            pass


# === 错误日志 ===
import logging
import logging.handlers

_LOG_FILE = FINANCE_DIR / "error.log"

def _setup_logging():
    """初始化日志（仅写文件，不输出到终端）"""
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        str(_LOG_FILE), maxBytes=100 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger = logging.getLogger("finance")
    logger.setLevel(logging.WARNING)
    logger.addHandler(handler)
    return logger


_logger = _setup_logging()


def log_error(msg: str):
    """记录错误到本地日志（不输出敏感数据）"""
    _logger.error(msg)


def log_warning(msg: str):
    """记录警告"""
    _logger.warning(msg)


# === 便捷文件路径 ===
ASSETS_FILE = FINANCE_DIR / "assets.md"
INCOME_FILE = FINANCE_DIR / "income.md"
INSURANCE_FILE = FINANCE_DIR / "insurance.md"
LIABILITIES_FILE = FINANCE_DIR / "liabilities.md"
GOALS_FILE = FINANCE_DIR / "goals.md"
SNAPSHOT_FILE = FINANCE_DIR / "portfolio_snapshot.md"
HISTORY_FILE = FINANCE_DIR / "history.csv"
DB_PATH = FINANCE_DIR / "finance_data.db"
CHART_FILE = FINANCE_DIR / "history_chart.png"
