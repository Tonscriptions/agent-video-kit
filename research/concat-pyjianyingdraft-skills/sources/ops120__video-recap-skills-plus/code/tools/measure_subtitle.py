#!/usr/bin/env python3
"""measure_subtitle.py - 字幕坐标标注工具(用户交互式确认)。

随机抽取 N 帧(默认 50 帧),只检测画面底部 50% 区域找字幕带。
严格条件: 字幕高度 30-50px + 白色像素横向覆盖 >= 20% 画面宽度。
过滤无字幕帧后,只把有字幕的帧+网格线保存到 preview/。
用户从多张预览图里挑带字幕的看,读出 Y 坐标,在命令行输入。

输出 subtitle_positions.json 供 assemble.py 使用。

Usage:
    python tools/measure_subtitle.py <video_path>
    python tools/measure_subtitle.py source.mp4 --frames 50
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def extract_frames(video_path: str, out_dir: str, num_frames: int = 50,
                   start_sec: float = 10.0) -> List[Tuple[str, float]]:
    """随机抽 N 帧(从 start_sec 后到结尾)。"""
    os.makedirs(out_dir, exist_ok=True)
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', video_path],
        capture_output=True, text=True, check=True
    )
    total_duration = float(probe.stdout.strip())
    end_sec = max(start_sec + 5, total_duration - 0.5)
    span = end_sec - start_sec

    random.seed(42)
    sample_times = sorted([start_sec + random.random() * span for _ in range(num_frames)])

    paths = []
    for i, t in enumerate(sample_times):
        out = os.path.join(out_dir, f"frame_{i:02d}_t{t:.2f}s.png")
        subprocess.run(['ffmpeg', '-y', '-ss', f'{t:.3f}', '-i', video_path,
                        '-frames:v', '1', '-q:v', '2', out],
                       capture_output=True, check=True)
        paths.append((out, t))
    return paths


def find_subtitle_in_bottom(image_path: str) -> Optional[Tuple[int, int]]:
    """在画面底部 50% 区域内找字幕带。

    严格条件(必须同时满足):
      1. 字幕行 row_max >= 200 (白字) + row_min <= 60 (深色描边)
      2. band 高度 30-50px (单行字幕)
      3. 白色像素横向覆盖 >= 20% 画面宽度 (排除金属反光等竖直误检)
      4. 在画面底部 50% 区域
    """
    im = np.array(Image.open(image_path).convert('L'))
    h, w = im.shape
    bottom_half = im[h // 2:]

    row_max = bottom_half.max(axis=1)
    row_min = bottom_half.min(axis=1)
    is_sub = (row_max >= 200) & (row_min <= 60)
    rows = np.where(is_sub)[0]
    if len(rows) == 0:
        return None

    gaps = np.diff(rows)
    breaks = np.where(gaps > 3)[0]
    bands = []
    s = rows[0]
    for b in breaks:
        bands.append((s, rows[b]))
        s = rows[b + 1]
    bands.append((s, rows[-1]))

    best_band = None
    best_width_ratio = 0
    for s, e in bands:
        height = e - s
        if not (30 <= height <= 50):
            continue
        band_pixels = bottom_half[s:e + 1]
        white_cols = (band_pixels > 200).any(axis=0)
        coverage = white_cols.sum() / w
        if coverage >= 0.20 and coverage > best_width_ratio:
            best_band = (s + h // 2, e + h // 2)
            best_width_ratio = coverage
    return best_band


def annotate_frame_with_grid(image_path: str, output_path: str,
                             detected_band: Optional[Tuple[int, int]] = None):
    """画网格线+字幕区高亮+检测结果(若提供)用红色细线。"""
    im = Image.open(image_path).convert('RGBA')
    overlay = Image.new('RGBA', im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = im.size

    try:
        font = ImageFont.truetype("arial.ttf", 16)
        font_big = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = font_big = ImageFont.load_default()

    for y in range(0, h, 50):
        color = (255, 220, 0, 160) if (y % 100 == 0) else (180, 180, 180, 100)
        draw.line([(0, y), (w, y)], fill=color, width=1)
        draw.text((5, y + 2), f"{y}", fill=(255, 255, 0, 220), font=font)

    band_top = int(h * 0.65)
    band_bot = int(h * 0.95)
    draw.rectangle([(0, band_top), (w, band_bot)],
                   outline=(0, 255, 255, 180), width=3)
    draw.text((w - 320, band_top - 30),
              f"Subtitle zone: y=[{band_top},{band_bot}]",
              fill=(0, 255, 255, 255), font=font_big)

    if detected_band:
        s, e = detected_band
        draw.rectangle([(0, s), (w, e)], outline=(255, 80, 80, 200), width=2)
        draw.text((w - 240, s - 25), f"detected: y=[{s},{e}]",
                  fill=(255, 80, 80, 230), font=font_big)

    out = Image.alpha_composite(im, overlay).convert('RGB')
    out.save(output_path)


def prompt_int(prompt_text: str, default: int) -> int:
    """命令行输入整数,EOF/空/无效输入返回默认值。"""
    try:
        raw = input(f"{prompt_text} [{default}]: ").strip()
    except EOFError:
        return default
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"  无效输入,使用默认值 {default}")
        return default


def write_positions_json(out_path: str, canvas: dict,
                         y_top: int, y_bot: int):
    data = {
        "canvas": canvas,
        "subtitle_y_top": y_top,
        "subtitle_y_bot": y_bot,
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser(
        description='字幕坐标标注工具: 随机抽50帧,严格过滤,用户读图输入坐标')
    ap.add_argument('video', help='输入视频路径')
    ap.add_argument('--out-dir', default=None,
                    help='输出目录(默认: <video_dir>/.subtitle_measure/,自动清空)')
    ap.add_argument('--start-sec', type=float, default=10.0,
                    help='起始采样秒数(默认10,跳过片头)')
    ap.add_argument('--frames', type=int, default=50,
                    help='采样帧数(默认50)')
    args = ap.parse_args()

    video_path = args.video
    if not os.path.exists(video_path):
        print(f"ERROR: 视频不存在: {video_path}", file=sys.stderr)
        sys.exit(1)

    if args.out_dir is None:
        video_dir = os.path.dirname(os.path.abspath(video_path))
        args.out_dir = os.path.join(video_dir, '.subtitle_measure')

    if os.path.exists(args.out_dir):
        shutil.rmtree(args.out_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    frames_dir = os.path.join(args.out_dir, 'frames')
    preview_dir = os.path.join(args.out_dir, 'preview')
    os.makedirs(preview_dir, exist_ok=True)

    print(f"[measure] 视频: {video_path}")
    print(f"[measure] 输出: {args.out_dir}")

    print(f"\n[1/3] 随机抽 {args.frames} 帧...")
    frame_paths = extract_frames(video_path, frames_dir,
                                 num_frames=args.frames,
                                 start_sec=args.start_sec)
    canvas_w, canvas_h = Image.open(frame_paths[0][0]).size
    print(f"  完成, 画布 {canvas_w}x{canvas_h}")

    print(f"\n[2/3] 严格过滤无字幕帧(底部50%区域 + 横向覆盖>=20%)...")
    with_subtitle = []
    detected_bands = []
    for p, t in frame_paths:
        band = find_subtitle_in_bottom(p)
        if band is not None:
            with_subtitle.append((p, t, band))
            detected_bands.append(band)
    print(f"  含字幕: {len(with_subtitle)} / {len(frame_paths)}")

    if not with_subtitle:
        print(f"ERROR: 全部帧都未检测到字幕", file=sys.stderr)
        sys.exit(2)

    tops = [b[0] for b in detected_bands]
    bots = [b[1] for b in detected_bands]
    suggested_top = int(np.median(tops))
    suggested_bot = int(np.median(bots))
    print(f"  启发式检测中位数: y_top={suggested_top}, y_bot={suggested_bot}")

    print(f"\n[3/3] 生成网格预览图...")
    for p, t, band in with_subtitle:
        preview_path = os.path.join(preview_dir, os.path.basename(p))
        annotate_frame_with_grid(p, preview_path, detected_band=band)
    print(f"  预览: {preview_dir}/ ({len(with_subtitle)} 张)")

    print(f"\n=== 请打开预览图查看字幕Y坐标 ===")
    print(f"  网格每50px一格,黄色刻度=100px整数倍")
    print(f"  青色框:'常见字幕区'(底部65%-95%),红色细线:启发式检测位置")
    print(f"  推荐: 打开几张预览图,看字幕文字的上下边界对应Y值")
    print()

    y_top = prompt_int(f"  字幕上沿 y_top (像素)", suggested_top)
    y_bot = prompt_int(f"  字幕下沿 y_bot (像素)", suggested_bot)

    if y_bot <= y_top:
        print(f"ERROR: y_bot ({y_bot}) 必须大于 y_top ({y_top})", file=sys.stderr)
        sys.exit(2)

    json_path = os.path.join(args.out_dir, 'subtitle_positions.json')
    write_positions_json(json_path,
                         {"width": canvas_w, "height": canvas_h},
                         y_top, y_bot)

    print(f"\n=== 完成 ===")
    print(f"  字幕带: y=[{y_top}, {y_bot}], 高度 {y_bot - y_top}px")
    print(f"  配置:   {json_path}")
    print(f"\n  使用方法:")
    print(f"    python recap.py <video> --subtitle-y-top {y_top} --subtitle-y-bot {y_bot} ...")


if __name__ == '__main__':
    main()