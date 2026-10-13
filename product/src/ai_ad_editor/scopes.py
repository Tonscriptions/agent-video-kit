from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .utils import run_process, sha256_file


SCOPE_VERSION = "0.1.0"
SCOPE_FILTERS = {
    "waveform": "waveform=mode=column:graticule=green",
    "vectorscope": "vectorscope=mode=color2:graticule=green",
    "histogram": "histogram=display_mode=overlay",
}


def generate_scopes(source: Path, output_dir: Path, *, at_seconds: float = 0.0) -> dict[str, Any]:
    """Render deterministic FFmpeg scope PNGs for Agent-side color review."""
    source = source.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("色彩 scope 输入不存在", str(source))
    if at_seconds < 0:
        raise argument_error("scope 时间点不能小于 0", "at_seconds")
    probe = probe_media(source)
    if not probe.get("video", {}).get("codec"):
        raise AppError("SCOPE_VIDEO_MISSING", "色彩 scope 需要视频流", exit_code=4, path=str(source))
    duration = float(probe.get("duration_seconds", 0.0) or 0.0)
    if duration and at_seconds > duration:
        raise argument_error("scope 时间点不能超过输入时长", "at_seconds")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict[str, Any]] = []
    for name, filtergraph in SCOPE_FILTERS.items():
        output = output_dir / f"{source.stem}_{name}.png"
        result = run_process(
            [
                ffmpeg_path(), "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{float(at_seconds):.3f}", "-i", str(source),
                "-vf", filtergraph, "-frames:v", "1", "-f", "image2", str(output),
            ],
            timeout=600,
        )
        if result.returncode != 0 or not output.exists() or output.stat().st_size == 0:
            raise AppError("SCOPE_RENDER_FAILED", f"{name} scope 生成失败", exit_code=6, retryable=True, path=str(output), cause=(result.stderr or result.stdout)[-3000:])
        artifacts.append({"type": name, "path": str(output), "sha256": f"sha256:{sha256_file(output)}", "bytes": output.stat().st_size})
    return {
        "scope_version": SCOPE_VERSION,
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "at_seconds": round(float(at_seconds), 3),
        "probe": probe,
        "engine": "ffmpeg-local",
        "artifacts": artifacts,
        "network": "disabled",
    }
