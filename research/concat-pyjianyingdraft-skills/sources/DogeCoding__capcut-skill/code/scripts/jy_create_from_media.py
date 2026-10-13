#!/usr/bin/env python3
"""
在剪映草稿目录下新建草稿，主轨放入本地视频（可选一条音频）。
依赖：本目录上级已执行 pip install -r requirements.txt（推荐用 .venv）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from _draft_fx import apply_video_decorations


def main() -> None:
    ap = argparse.ArgumentParser(description="Create Jianying draft with video (+ optional audio)")
    ap.add_argument("--draft-root", required=True, help="剪映草稿根目录，如 .../com.lveditor.draft")
    ap.add_argument("--name", required=True, help="新草稿文件夹名（在剪映里显示为草稿名）")
    ap.add_argument("--video", required=True, help="主视频素材绝对路径")
    ap.add_argument("--audio", default="", help="可选：独立音频绝对路径（整段对齐从 0s 开始）")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--allow-replace", action="store_true", help="若同名草稿已存在则覆盖")
    ap.add_argument("--intro", default="", help="入场动画枚举名，如 斜切；见 jy_list_effect_names.py IntroType")
    ap.add_argument("--filter", dest="filter_name", default="", help="滤镜枚举名；见 jy_list_effect_names.py FilterType")
    ap.add_argument("--filter-intensity", type=float, default=80.0, help="滤镜强度 0–100，默认 80")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        print(json.dumps({"ok": False, "error": "video_not_found", "path": args.video}), file=sys.stderr)
        sys.exit(1)
    if args.audio and not os.path.isfile(args.audio):
        print(json.dumps({"ok": False, "error": "audio_not_found", "path": args.audio}), file=sys.stderr)
        sys.exit(1)

    import pyJianYingDraft as d
    from pyJianYingDraft.time_util import Timerange

    folder = d.DraftFolder(args.draft_root)
    script = folder.create_draft(
        args.name, args.width, args.height, fps=args.fps, allow_replace=args.allow_replace
    )
    script.add_track(d.TrackType.video)
    script.add_track(d.TrackType.audio)

    vm = d.VideoMaterial(args.video)
    vseg = d.VideoSegment(vm, Timerange(0, vm.duration))
    try:
        apply_video_decorations(
            vseg,
            intro=args.intro or None,
            filter_name=args.filter_name or None,
            filter_intensity=args.filter_intensity,
        )
    except ValueError as e:
        print(json.dumps({"ok": False, "error": "bad_effect_name", "detail": str(e)}), file=sys.stderr)
        sys.exit(2)
    script.add_segment(vseg)

    if args.audio:
        am = d.AudioMaterial(args.audio)
        # 音频与视频对齐从 0 开始；若长于视频，剪映内可再调
        alen = min(am.duration, vm.duration)
        aseg = d.AudioSegment(am, Timerange(0, alen))
        script.add_segment(aseg)

    script.save()
    out = {
        "ok": True,
        "draft_name": args.name,
        "draft_root": os.path.abspath(args.draft_root),
        "draft_path": os.path.join(os.path.abspath(args.draft_root), args.name),
        "resolution": [args.width, args.height],
        "fx": {"intro": args.intro or None, "filter": args.filter_name or None},
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
