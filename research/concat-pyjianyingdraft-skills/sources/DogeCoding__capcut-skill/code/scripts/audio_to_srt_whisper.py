#!/usr/bin/env python3
"""
从视频/音频生成 SRT（可选依赖）：调用系统 PATH 中的 OpenAI Whisper CLI。

安装（任选其一，不在本 Skill 默认 requirements 里）：
  pip install openai-whisper   # 提供 `whisper` 命令，体积大
  # 或自行安装 whisper.cpp 并把可执行文件命名为 whisper 加入 PATH

与影视流水线：输出 SRT 后接 `jy_import_srt.py` 写入剪映文本轨。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Transcribe media to SRT via whisper CLI")
    ap.add_argument("media", help="视频或音频绝对路径")
    ap.add_argument("--output-dir", required=True, help="输出目录（写入 <basename>.srt）")
    ap.add_argument("--model", default="base", help="Whisper 模型名，如 tiny/base/small/medium")
    ap.add_argument("--language", default="Chinese", help="语言提示，如 Chinese / English")
    ap.add_argument("--whisper-cmd", default="", help="覆盖 whisper 可执行文件路径")
    args = ap.parse_args()

    exe = args.whisper_cmd or shutil.which("whisper")
    if not exe:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "whisper_cli_not_found",
                    "hint": "pip install openai-whisper 或安装 whisper.cpp 后加入 PATH",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        sys.exit(127)

    if not os.path.isfile(args.media):
        print(json.dumps({"ok": False, "error": "media_not_found"}), file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        exe,
        os.path.abspath(args.media),
        "--language",
        args.language,
        "--model",
        args.model,
        "--output_format",
        "srt",
        "--output_dir",
        str(out_dir),
    ]
    r = subprocess.run(cmd, timeout=7200)
    if r.returncode != 0:
        print(json.dumps({"ok": False, "error": "whisper_failed", "cmd": cmd}), file=sys.stderr)
        sys.exit(r.returncode)

    base = Path(args.media).stem
    srt_path = out_dir / f"{base}.srt"
    if not srt_path.is_file():
        # whisper 可能对中文名有不同命名，取最新 srt
        srts = sorted(out_dir.glob("*.srt"), key=lambda p: p.stat().st_mtime, reverse=True)
        srt_path = srts[0] if srts else None

    if not srt_path or not srt_path.is_file():
        print(json.dumps({"ok": False, "error": "srt_not_found", "output_dir": str(out_dir)}), file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"ok": True, "srt": str(srt_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
