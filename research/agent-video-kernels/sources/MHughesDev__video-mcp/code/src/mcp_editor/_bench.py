"""Entry point wrapper so `mcp-editor-bench` works after `pip install`."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from scripts.benchmark import main as _main  # type: ignore[import]
    _main()


if __name__ == "__main__":
    main()
