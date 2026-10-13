from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from .config import input_dir, music_dir, references_dir
from .media import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tiff", ".bmp"}

_DIRECT_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS | IMAGE_EXTENSIONS

_CONTENT_TYPE_MAP = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
    "audio/ogg": ".ogg",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_DESTINATIONS = {
    "input": input_dir,
    "music": music_dir,
    "references": references_dir,
}


def _destination_dir(destination: str) -> Path:
    if destination not in _DESTINATIONS:
        raise ValueError(
            f"Invalid destination '{destination}'. Must be one of: {', '.join(_DESTINATIONS)}"
        )
    return _DESTINATIONS[destination]()


def _is_direct_file_url(url: str) -> bool:
    path_part = url.split("?")[0].split("#")[0]
    suffix = Path(path_part).suffix.lower()
    return suffix in _DIRECT_EXTENSIONS


def _download_direct(url: str, dest_dir: Path, filename: str) -> Path:
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()

    out_path = dest_dir / filename
    if not out_path.suffix:
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        ext = _CONTENT_TYPE_MAP.get(content_type, "")
        out_path = out_path.with_suffix(ext)

    with open(out_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return out_path


def _download_via_ytdlp(url: str, dest_dir: Path, filename: str) -> Path:
    template = str(dest_dir / f"{filename}.%(ext)s")
    cmd = ["yt-dlp", "--output", template, "--no-playlist", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    matches = list(dest_dir.glob(f"{filename}.*"))
    matches = [p for p in matches if p.suffix.lower() != ".part"]
    if not matches:
        raise RuntimeError(
            f"yt-dlp completed but no output file found for pattern '{filename}.*' in {dest_dir}"
        )
    return max(matches, key=lambda p: p.stat().st_size)


def download_asset(
    url: str,
    destination: str,
    filename: str | None = None,
) -> dict:
    dest_dir = _destination_dir(destination)

    if filename is None:
        path_part = url.split("?")[0].split("#")[0].rstrip("/")
        filename = Path(path_part).stem or "download"

    filename = filename.replace("/", "_").replace("\\", "_")

    if _is_direct_file_url(url):
        out_path = _download_direct(url, dest_dir, filename)
    else:
        out_path = _download_via_ytdlp(url, dest_dir, filename)

    return {
        "ok": True,
        "path": out_path.as_posix(),
        "filename": out_path.name,
        "size_bytes": out_path.stat().st_size,
        "destination": destination,
    }
