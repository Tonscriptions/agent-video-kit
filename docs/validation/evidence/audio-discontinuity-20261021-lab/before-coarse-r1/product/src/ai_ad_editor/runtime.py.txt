from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .errors import AppError


def configure_local_runtime() -> dict[str, str]:
    """Keep this process's temporary files and library caches near the product.

    These are process environment settings, not global Windows settings. No
    data is copied from the user's existing caches and no weights are fetched.
    """
    configured_root = os.environ.get("AI_AD_EDITOR_RUNTIME_DIR")
    root = Path(configured_root).expanduser().resolve() if configured_root else Path(__file__).resolve().parents[2] / ".runtime"
    paths = {
        "root": root,
        "temp": root / "temp",
        "models": root / "models",
        "huggingface": root / "models" / "huggingface",
        "torch": root / "models" / "torch",
        "cache": root / "cache",
        "pip": root / "cache" / "pip",
    }
    try:
        for path in paths.values():
            path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError("RUNTIME_STORAGE_UNAVAILABLE", "无法建立本地运行缓存目录", exit_code=10, path=str(root), cause=str(exc)) from exc
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = str(paths["temp"])
    tempfile.tempdir = str(paths["temp"])
    os.environ["HF_HOME"] = str(paths["huggingface"])
    os.environ["HF_HUB_CACHE"] = str(paths["huggingface"] / "hub")
    os.environ["TORCH_HOME"] = str(paths["torch"])
    os.environ["XDG_CACHE_HOME"] = str(paths["cache"])
    os.environ["PIP_CACHE_DIR"] = str(paths["pip"])
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return {name: str(path) for name, path in paths.items()}
