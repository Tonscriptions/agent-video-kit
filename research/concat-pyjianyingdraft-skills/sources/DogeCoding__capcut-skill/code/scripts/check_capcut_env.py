#!/usr/bin/env python3
"""检查本 Skill：FFmpeg、可选 .venv 中的 pyJianYingDraft。"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent


def _which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def _run_version(argv: list[str]) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=15)
        line = (r.stdout or r.stderr or "").strip().splitlines()[0] if r.returncode == 0 else ""
        return r.returncode == 0, line[:200]
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def _venv_pyjianying() -> dict:
    vpy = SKILL_ROOT / ".venv" / "bin" / "python"
    if not vpy.is_file():
        return {
            "venv_python": None,
            "pyJianYingDraft": False,
            "hint": f"cd {SKILL_ROOT} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
        }
    r = subprocess.run(
        [str(vpy), "-c", "import pyJianYingDraft as p; print(getattr(p,'__version__','ok'))"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    ok = r.returncode == 0
    ver = (r.stdout or "").strip() if ok else (r.stderr or "").strip()[:200]
    return {"venv_python": str(vpy), "pyJianYingDraft": ok, "version_or_error": ver}


def main() -> None:
    strict = "--strict" in sys.argv
    ffmpeg = _which("ffmpeg")
    ok_ff, ff_line = _run_version([ffmpeg, "-version"]) if ffmpeg else (False, "not found")

    jy = _venv_pyjianying()
    whisper = _which("whisper")
    report = {
        "skill_root": str(SKILL_ROOT),
        "ffmpeg": {"path": ffmpeg, "ok": ok_ff, "version_line": ff_line},
        "ffprobe": {"path": _which("ffprobe")},
        "whisper_cli": {"path": whisper, "ok": bool(whisper)},
        "jianying_python": jy,
        "ready": {
            "ffmpeg": ok_ff,
            "draft_scripts": jy.get("pyJianYingDraft", False),
        },
        "notes": [
            "草稿脚本请用 .venv/bin/python 运行（或先安装依赖）",
            "pyJianYingDraft 在 macOS 不支持其自带的剪映 GUI 自动导出，仅生成草稿 JSON",
            "Whisper 字幕为可选：PATH 中有 whisper 时可用 audio_to_srt_whisper.py；见 requirements-optional.txt",
        ],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if strict and (not ok_ff or not jy.get("pyJianYingDraft")):
        sys.exit(1)


if __name__ == "__main__":
    main()
