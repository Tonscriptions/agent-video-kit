#!/usr/bin/env python3
"""
口播粗剪（独立于剪映）：用 FFmpeg silencedetect 找静音，反向保留「有声段」并拼接输出。
不调用云端 ASR，适合先去掉长停顿；精细删句需人工或其它工具。

依赖：系统已安装 ffmpeg、ffprobe。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile


def _duration(path: str) -> float:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr or "ffprobe failed")
    return float((r.stdout or "0").strip())


def _silence_intervals(path: str, noise_db: float, min_silence: float) -> list[tuple[float, float]]:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        path,
        "-af",
        f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f",
        "null",
        "-",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    err = r.stderr or ""
    starts = [float(m.group(1)) for m in re.finditer(r"silence_start: ([0-9.]+)", err)]
    ends = [float(m.group(1)) for m in re.finditer(r"silence_end: ([0-9.]+)", err)]
    pairs: list[tuple[float, float]] = []
    for i, s in enumerate(starts):
        if i < len(ends):
            e = ends[i]
            if e > s:
                pairs.append((s, e))
    return pairs


def _merge_intervals(iv: list[tuple[float, float]], eps: float = 0.01) -> list[tuple[float, float]]:
    if not iv:
        return []
    iv = sorted(iv)
    out = [iv[0]]
    for s, e in iv[1:]:
        ps, pe = out[-1]
        if s <= pe + eps:
            out[-1] = (ps, max(pe, e))
        else:
            out.append((s, e))
    return out


def _invert_keep(total: float, silent: list[tuple[float, float]], pad: float) -> list[tuple[float, float]]:
    """有声段 = 非静音区间，两侧可留 pad。"""
    if total <= 0:
        return []
    silent = _merge_intervals(silent)
    keep: list[tuple[float, float]] = []
    t = 0.0
    for s, e in silent:
        s = max(0, s)
        e = min(total, e)
        if s > t + pad:
            keep.append((max(0, t + pad), max(0, s - pad)))
        t = max(t, e)
    if t < total - pad:
        keep.append((max(0, t + pad), total))
    # 清理无效
    return [(a, b) for a, b in keep if b - a >= 0.05]


def _apply_segments(src: str, dst: str, segments: list[tuple[float, float]]) -> None:
    if not segments:
        raise ValueError("no segments to keep")
    with tempfile.TemporaryDirectory(prefix="capcut_skill_") as td:
        parts: list[str] = []
        for i, (a, b) in enumerate(segments):
            part = os.path.join(td, f"p{i:04d}.mp4")
            cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{a:.3f}",
                "-to",
                f"{b:.3f}",
                "-i",
                src,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                part,
            ]
            r = subprocess.run(cmd, timeout=3600)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg segment {i} failed")
            parts.append(part)
        list_path = os.path.join(td, "list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for p in parts:
                f.write(f"file '{p}'\n")
        r2 = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_path,
                "-c",
                "copy",
                dst,
            ],
            timeout=3600,
        )
        if r2.returncode != 0:
            raise RuntimeError("ffmpeg concat failed")


def main() -> None:
    ap = argparse.ArgumentParser(description="Rough cut talking video by silence detection (FFmpeg only)")
    ap.add_argument("input", help="输入视频路径")
    ap.add_argument("output", help="输出视频路径")
    ap.add_argument("--min-silence", type=float, default=0.45, help="视为静音的最短秒数")
    ap.add_argument("--noise-db", type=float, default=-35.0, help="silencedetect noise 阈值 (dB)")
    ap.add_argument("--pad", type=float, default=0.04, help="有声段边界向内收缩秒数，避免吞字")
    ap.add_argument("--dry-run", action="store_true", help="只打印 JSON，不写输出文件")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(json.dumps({"ok": False, "error": "input_not_found"}), file=sys.stderr)
        sys.exit(1)

    total = _duration(args.input)
    silent = _silence_intervals(args.input, args.noise_db, args.min_silence)
    keep = _invert_keep(total, silent, args.pad)

    report = {
        "ok": True,
        "duration_sec": round(total, 3),
        "silence_intervals": [[round(a, 3), round(b, 3)] for a, b in silent],
        "keep_segments": [[round(a, 3), round(b, 3)] for a, b in keep],
        "dry_run": args.dry_run,
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    if not keep:
        print(json.dumps({"ok": False, "error": "no_keep_segments", "detail": report}), file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.dirname(os.path.abspath(args.output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    _apply_segments(args.input, args.output, keep)
    report["output"] = os.path.abspath(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
