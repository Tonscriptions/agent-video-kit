#!/usr/bin/env python3
"""
Resolve 剪映专业版 / CapCut (desktop) draft roots on macOS.
Override with env: CAPCUT_DRAFT_ROOT or JIANYING_DRAFT_ROOT (single directory).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _candidates() -> list[Path]:
    home = Path.home()
    out: list[Path] = []

    def add(p: Path) -> None:
        if p not in out:
            out.append(p)

    # Typical standalone installs
    add(home / "Movies/JianyingPro/User Data/Projects/com.lveditor.draft")
    add(home / "Movies/JianyingPro/User Data/Projects/com.open.lveditor.draft")
    add(home / "Movies/CapCut/User Data/Projects/com.lveditor.draft")
    add(home / "Movies/CapCut/User Data/Projects/com.open.lveditor.draft")

    # Application Support (some builds)
    add(
        home
        / "Library/Application Support/JianyingPro/User Data/Projects/com.lveditor.draft"
    )

    # Sandboxed / Mac App Store style containers
    containers = home / "Library/Containers"
    if containers.is_dir():
        for pattern in ("*Jianying*", "*jianying*", "*lvpro*", "*Lemon*", "*CapCut*"):
            for sub in containers.glob(pattern):
                if not sub.is_dir():
                    continue
                for name in ("JianyingPro", "CapCut"):
                    add(
                        sub
                        / "Data"
                        / "Movies"
                        / name
                        / "User Data"
                        / "Projects"
                        / "com.lveditor.draft"
                    )

    return out


def resolve() -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    env = (os.environ.get("CAPCUT_DRAFT_ROOT") or os.environ.get("JIANYING_DRAFT_ROOT") or "").strip()
    if env:
        p = Path(env).expanduser()
        if p.is_dir():
            found.append({"path": str(p.resolve()), "source": "env"})
        else:
            found.append({"path": str(p), "source": "env", "error": "not_a_directory"})

    for p in _candidates():
        if p.is_dir():
            found.append({"path": str(p.resolve()), "source": "auto"})

    seen: set[str] = set()
    uniq: list[dict[str, str]] = []
    for item in found:
        key = item["path"]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(item)
    return uniq


def main() -> None:
    data = {"draft_roots": resolve(), "platform": sys.platform}
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
