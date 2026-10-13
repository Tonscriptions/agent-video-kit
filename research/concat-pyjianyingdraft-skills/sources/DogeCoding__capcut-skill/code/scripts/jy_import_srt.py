#!/usr/bin/env python3
"""
新建剪映草稿：主视频 + 从 SRT 导入字幕轨（pyJianYingDraft.import_srt）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from _draft_fx import apply_video_decorations


def main() -> None:
    ap = argparse.ArgumentParser(description="Create Jianying draft with video + SRT subtitles")
    ap.add_argument("--draft-root", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--track-name", default="subtitle", help="文本轨道名称")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--allow-replace", action="store_true")
    ap.add_argument("--intro", default="", help="入场动画，如 斜切")
    ap.add_argument("--filter", dest="filter_name", default="", help="滤镜枚举名")
    ap.add_argument("--filter-intensity", type=float, default=80.0)
    args = ap.parse_args()

    for label, p in ("video", args.video), ("srt", args.srt):
        if not os.path.isfile(p):
            print(json.dumps({"ok": False, "error": "not_found", "kind": label, "path": p}), file=sys.stderr)
            sys.exit(1)

    import pyJianYingDraft as d
    from pyJianYingDraft.time_util import Timerange

    folder = d.DraftFolder(args.draft_root)
    script = folder.create_draft(
        args.name, args.width, args.height, fps=args.fps, allow_replace=args.allow_replace
    )
    script.add_track(d.TrackType.video)
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

    script.import_srt(os.path.abspath(args.srt), args.track_name)

    script.save()
    print(
        json.dumps(
            {
                "ok": True,
                "draft_name": args.name,
                "draft_path": os.path.join(os.path.abspath(args.draft_root), args.name),
                "srt_track": args.track_name,
                "fx": {"intro": args.intro or None, "filter": args.filter_name or None},
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
