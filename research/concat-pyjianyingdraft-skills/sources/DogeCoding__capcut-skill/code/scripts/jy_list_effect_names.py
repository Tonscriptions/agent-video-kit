#!/usr/bin/env python3
"""列出 pyJianYingDraft 中带中文名的入场动画、转场、滤镜枚举，供 Agent / 用户填参。"""
from __future__ import annotations

import argparse
import json
import sys

import pyJianYingDraft as d


def _names(enum_cls: type) -> list[str]:
    return [m.name for m in enum_cls]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=("all", "intro", "transition", "filter"), default="all")
    args = ap.parse_args()

    out: dict = {"ok": True}
    if args.kind in ("all", "intro"):
        out["IntroType"] = _names(d.IntroType)
    if args.kind in ("all", "transition"):
        out["TransitionType"] = _names(d.TransitionType)
    if args.kind in ("all", "filter"):
        out["FilterType"] = _names(d.FilterType)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)
