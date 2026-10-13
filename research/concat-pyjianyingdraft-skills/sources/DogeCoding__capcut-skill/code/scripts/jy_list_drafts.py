#!/usr/bin/env python3
"""列出剪映草稿根目录下的子文件夹名（草稿名）。"""
from __future__ import annotations

import argparse
import json
import sys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft-root", required=True)
    args = ap.parse_args()
    import pyJianYingDraft as d

    try:
        folder = d.DraftFolder(args.draft_root)
        names = sorted(
            n for n in folder.list_drafts() if not n.startswith(".") and n != ".recycle_bin"
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"ok": True, "drafts": names}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
