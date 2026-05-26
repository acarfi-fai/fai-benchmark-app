from __future__ import annotations

import os
from pathlib import Path


def log_dir() -> str:
    return os.getenv("INSPECT_LOG_DIR") or os.getenv("LOG_DIR") or "./logs"


def frontend_dist_dir() -> Path:
    configured = os.getenv("FRONTEND_DIST_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "frontend" / "dist" / "fusionai-eval-console" / "browser"
