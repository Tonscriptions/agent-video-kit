#!/usr/bin/env python3
"""
漫剧 / 口播 一键流水线（本地、无第三方 Git 仓依赖）：

1. （可选）FFmpeg 静音粗剪
2. （可选）Whisper → SRT
3. 剪映草稿：视频 +（若有 SRT）字幕轨 +（可选）入场/滤镜

与 OpenClaw 内 **jimeng-video-volc-sdk** 衔接：即梦输出的 mp4 可作为本脚本 --video。

环境变量 CAPCUT_DRAFT_ROOT 可覆盖草稿根；否则自动调用 capcut_paths 逻辑。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
VENV_PY = SKILL_ROOT / ".venv" / "bin" / "python"


def _draft_root(cli_root: str) -> str:
    if cli_root:
        return os.path.abspath(cli_root)
    # 与 capcut_paths 同逻辑
    sys.path.insert(0, str(SCRIPT_DIR))
    import capcut_paths as cp

    roots = cp.resolve()
    if not roots:
        raise SystemExit(
            json.dumps({"ok": False, "error": "no_draft_root", "hint": "设置 CAPCUT_DRAFT_ROOT"}, ensure_ascii=False)
        )
    for r in roots:
        if "error" not in r:
            return r["path"]
    raise SystemExit(json.dumps({"ok": False, "error": "draft_root_invalid"}, ensure_ascii=False))


def _run(py: Path, script: str, args: list[str]) -> None:
    cmd = [str(py), str(SCRIPT_DIR / script)] + args
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


def main() -> None:
    ap = argparse.ArgumentParser(description="Film pipeline: rough_cut → whisper SRT → Jianying draft")
    ap.add_argument("--video", required=True, help="主视频绝对路径（或即梦成片 mp4）")
    ap.add_argument("--name", required=True, help="剪映草稿名")
    ap.add_argument("--draft-root", default="", help="草稿根；默认同 capcut_paths")
    ap.add_argument("--no-rough-cut", action="store_true")
    ap.add_argument("--min-silence", type=float, default=0.45)
    ap.add_argument("--noise-db", type=float, default=-35.0)
    ap.add_argument("--no-whisper", action="store_true")
    ap.add_argument("--srt", default="", help="已有 SRT 则跳过 Whisper")
    ap.add_argument("--whisper-model", default="base")
    ap.add_argument("--whisper-language", default="Chinese")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--allow-replace", action="store_true")
    ap.add_argument("--intro", default="")
    ap.add_argument("--filter", dest="filter_name", default="")
    ap.add_argument("--filter-intensity", type=float, default=80.0)
    ap.epilog = (
        "若同时指定 --srt 与默认粗剪，请确认字幕时间轴与剪切后视频一致；"
        "否则使用 --no-rough-cut 或先粗剪再对最终 mp4 跑 Whisper。"
    )
    args = ap.parse_args()

    py = VENV_PY if VENV_PY.is_file() else Path(sys.executable)
    if not Path(args.video).is_file():
        print(json.dumps({"ok": False, "error": "video_not_found"}), file=sys.stderr)
        sys.exit(1)

    work_video = os.path.abspath(args.video)
    tmpdir: tempfile.TemporaryDirectory[str] | None = None
    whisper_tmp: str | None = None
    srt_path = args.srt.strip()

    try:
        if not args.no_rough_cut:
            tmpdir = tempfile.TemporaryDirectory(prefix="capcut_pipeline_")
            cut_path = os.path.join(tmpdir.name, "rough_cut.mp4")
            _run(
                py,
                "rough_cut_silence.py",
                [work_video, cut_path, "--min-silence", str(args.min_silence), "--noise-db", str(args.noise_db)],
            )
            work_video = cut_path

        if not srt_path and not args.no_whisper:
            if tmpdir:
                wdir = tmpdir.name
            else:
                wdir = tempfile.mkdtemp(prefix="capcut_whisper_")
                whisper_tmp = wdir
            _run(
                py,
                "audio_to_srt_whisper.py",
                [
                    work_video,
                    "--output-dir",
                    wdir,
                    "--model",
                    args.whisper_model,
                    "--language",
                    args.whisper_language,
                ],
            )
            # parse stdout last line json - fragile; use glob
            srts = sorted(Path(wdir).glob("*.srt"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not srts:
                print(json.dumps({"ok": False, "error": "whisper_no_srt"}), file=sys.stderr)
                sys.exit(1)
            srt_path = str(srts[0])

        root = _draft_root(args.draft_root)

        if srt_path:
            cmd = [
                "--draft-root",
                root,
                "--name",
                args.name,
                "--video",
                work_video,
                "--srt",
                os.path.abspath(srt_path),
                "--width",
                str(args.width),
                "--height",
                str(args.height),
            ]
            if args.allow_replace:
                cmd.append("--allow-replace")
            if args.intro:
                cmd += ["--intro", args.intro]
            if args.filter_name:
                cmd += ["--filter", args.filter_name, "--filter-intensity", str(args.filter_intensity)]
            _run(py, "jy_import_srt.py", cmd)
        else:
            cmd = [
                "--draft-root",
                root,
                "--name",
                args.name,
                "--video",
                work_video,
                "--width",
                str(args.width),
                "--height",
                str(args.height),
            ]
            if args.allow_replace:
                cmd.append("--allow-replace")
            if args.intro:
                cmd += ["--intro", args.intro]
            if args.filter_name:
                cmd += ["--filter", args.filter_name, "--filter-intensity", str(args.filter_intensity)]
            _run(py, "jy_create_from_media.py", cmd)

        print(
            json.dumps(
                {
                    "ok": True,
                    "draft_root": root,
                    "draft_name": args.name,
                    "used_video": work_video,
                    "srt": srt_path or None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if tmpdir:
            tmpdir.cleanup()
        if whisper_tmp:
            shutil.rmtree(whisper_tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
