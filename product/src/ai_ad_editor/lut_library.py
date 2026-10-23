from __future__ import annotations

"""Project-local LUT registry.

The renderer can consume a LUT by path, but an Agent needs a stable resource
identity that survives project moves and can be checked against the local
Rights Ledger.  This module keeps that identity in a small, human-readable
manifest under ``assets/lut-library.json``.  Registration copies the source
into the project, records its SHA-256 and parses the safe metadata available
from the common ``.cube`` format.  Unknown LUT formats remain usable through
their content hash and extension without guessing metadata.
"""

import re
import math
import shutil
from pathlib import Path
from typing import Any

from .errors import AppError, argument_error
from .utils import ID_RE, atomic_write_json, atomic_write_text, load_json, now_iso, sha256_bytes, sha256_file


LUT_LIBRARY_VERSION = "0.1.0"
LUT_EXTENSIONS = {".cube", ".3dl", ".csp", ".dat"}
LUT_INTERPOLATIONS = ("nearest", "trilinear", "tetrahedral", "pyramid", "prism")
_NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")


def lut_library_file(root: Path) -> Path:
    return root / "assets" / "lut-library.json"


def _empty_library() -> dict[str, Any]:
    return {
        "library_version": LUT_LIBRARY_VERSION,
        "updated_at": now_iso(),
        "records": [],
        "network": "disabled",
        "source": "project-local",
    }


def load_lut_library(root: Path) -> dict[str, Any]:
    path = lut_library_file(root)
    if not path.exists():
        return _empty_library()
    value = load_json(path)
    if not isinstance(value, dict):
        raise AppError("LUT_LIBRARY_INVALID", "LUT 库清单必须是 JSON 对象", exit_code=2, path=str(path))
    value.setdefault("records", [])
    value.setdefault("network", "disabled")
    value.setdefault("source", "project-local")
    value["library_version"] = LUT_LIBRARY_VERSION
    return value


def save_lut_library(root: Path, library: dict[str, Any]) -> None:
    library["library_version"] = LUT_LIBRARY_VERSION
    library["updated_at"] = now_iso()
    library["network"] = "disabled"
    library["source"] = "project-local"
    library.setdefault("records", [])
    atomic_write_json(lut_library_file(root), library)


def _parse_number(value: str) -> float | None:
    value = value.strip()
    if not _NUMBER_RE.fullmatch(value):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_lut_metadata(path: Path) -> dict[str, Any]:
    """Parse conservative metadata without interpreting color values.

    ``.cube`` headers are line-oriented and safe to inspect locally.  The
    other supported extensions have several dialects, so their metadata is
    reported as ``format=unknown`` until a dedicated parser is added.
    """
    metadata: dict[str, Any] = {"format": path.suffix.lower().lstrip(".")}
    if path.suffix.lower() != ".cube":
        return metadata
    title: str | None = None
    size: int | None = None
    size_1d: int | None = None
    input_ranges: dict[str, list[float]] = {}
    domain_min: list[float] | None = None
    domain_max: list[float] | None = None
    sample_count = 0
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                key = parts[0].upper()
                if key == "TITLE" and len(parts) >= 2:
                    title = " ".join(parts[1:]).strip().strip('"')[:256]
                elif key == "LUT_3D_SIZE" and len(parts) == 2:
                    try:
                        candidate = int(parts[1])
                    except ValueError:
                        candidate = 0
                    if 2 <= candidate <= 256:
                        size = candidate
                elif key == "LUT_1D_SIZE" and len(parts) == 2:
                    try:
                        candidate = int(parts[1])
                    except ValueError:
                        candidate = 0
                    if 2 <= candidate <= 65536:
                        size_1d = candidate
                elif key in {"LUT_1D_INPUT_RANGE", "LUT_3D_INPUT_RANGE"} and len(parts) == 3:
                    values = [_parse_number(item) for item in parts[1:]]
                    if all(value is not None and math.isfinite(value) for value in values) and values[0] < values[1]:
                        input_ranges[key.lower()] = [float(value) for value in values]
                elif key in {"DOMAIN_MIN", "DOMAIN_MAX"} and len(parts) == 4:
                    values = [_parse_number(item) for item in parts[1:]]
                    if all(value is not None for value in values):
                        if key == "DOMAIN_MIN":
                            domain_min = [float(value) for value in values if value is not None]
                        else:
                            domain_max = [float(value) for value in values if value is not None]
                elif len(parts) == 3 and all(_parse_number(item) is not None for item in parts):
                    sample_count += 1
    except OSError as exc:
        raise AppError("LUT_METADATA_READ_FAILED", f"读取 LUT 元数据失败: {path}", exit_code=2, path=str(path), cause=str(exc)) from exc
    if title:
        metadata["title"] = title
    if size is not None:
        metadata["lut_3d_size"] = size
    if size_1d is not None:
        metadata["lut_1d_size"] = size_1d
    if size is not None or size_1d is not None:
        expected = (size**3 if size is not None else 0)+(size_1d or 0)
        metadata["expected_samples"] = expected
        metadata["sample_count"] = sample_count
        metadata["sample_count_valid"] = sample_count == expected
    metadata.update(input_ranges)
    if domain_min is not None:
        metadata["domain_min"] = domain_min
    if domain_max is not None:
        metadata["domain_max"] = domain_max
    return metadata


def _record_by_id(library: dict[str, Any], lut_id: str) -> dict[str, Any] | None:
    for record in library.get("records", []):
        if isinstance(record, dict) and str(record.get("id")) == str(lut_id):
            return record
    return None


def find_lut(root: Path, lut_id: str) -> dict[str, Any] | None:
    return _record_by_id(load_lut_library(root), str(lut_id))


def resolve_lut_path(root: Path, lut_id: str) -> tuple[Path, dict[str, Any]] | None:
    record = find_lut(root, lut_id)
    if not record:
        return None
    raw_uri = str(record.get("uri", ""))
    path = Path(raw_uri)
    if not path.is_absolute():
        path = root / path
    return path, record


def prepare_lut_registration(
    root: Path,
    source: Path,
    *,
    lut_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("LUT 输入必须是存在的本地文件", str(source))
    extension = source.suffix.lower()
    if extension not in LUT_EXTENSIONS:
        raise argument_error("LUT 文件扩展名只支持 .cube、.3dl、.csp 或 .dat", str(source))
    digest = sha256_file(source)
    resolved_id = lut_id or f"lut_{digest[:16]}"
    if not ID_RE.fullmatch(resolved_id):
        raise argument_error("LUT ID 只能包含字母、数字、点、下划线、冒号和短横线", "--lut-id")
    library = load_lut_library(root)
    existing = _record_by_id(library, resolved_id)
    if existing:
        if str(existing.get("sha256")) == f"sha256:{digest}":
            raise AppError("LUT_ALREADY_REGISTERED", f"LUT 已登记: {resolved_id}", exit_code=2, path="--lut-id")
        raise AppError("LUT_ID_CONFLICT", f"LUT ID 已绑定其他内容: {resolved_id}", exit_code=2, path="--lut-id")
    duplicate = next((item for item in library.get("records", []) if isinstance(item, dict) and item.get("sha256") == f"sha256:{digest}"), None)
    if duplicate:
        raise AppError("LUT_CONTENT_ALREADY_REGISTERED", f"相同 SHA-256 的 LUT 已登记: {duplicate.get('id')}", exit_code=2, path=str(source))
    metadata = parse_lut_metadata(source)
    destination = root / "assets" / "luts" / f"{resolved_id}{extension}"
    return {
        "id": resolved_id,
        "name": (name or metadata.get("title") or source.stem).strip()[:256],
        "uri": str(destination.relative_to(root)).replace("\\", "/"),
        "sha256": f"sha256:{digest}",
        "bytes": int(source.stat().st_size),
        "extension": extension,
        "metadata": metadata,
        "interpolations": list(LUT_INTERPOLATIONS),
        "source": {"original_name": source.name, "source_url": f"local://{source}"},
        "registered_at": now_iso(),
        "_source_path": str(source),
    }


def register_lut(root: Path, registration: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(registration.pop("_source_path"))).resolve()
    destination = root / str(registration["uri"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if source != destination.resolve():
            shutil.copy2(source, destination)
    except OSError as exc:
        raise AppError("LUT_COPY_FAILED", f"复制 LUT 到项目失败: {destination}", exit_code=2, path=str(destination), cause=str(exc)) from exc
    library = load_lut_library(root)
    library.setdefault("records", []).append(registration)
    library["records"].sort(key=lambda item: str(item.get("id", "")))
    save_lut_library(root, library)
    return registration


def list_luts(root: Path, *, query: str | None = None) -> list[dict[str, Any]]:
    query_text = str(query or "").casefold().strip()
    records = [item for item in load_lut_library(root).get("records", []) if isinstance(item, dict)]
    if query_text:
        records = [item for item in records if query_text in " ".join(str(item.get(key, "")) for key in ("id", "name", "extension")).casefold()]
    return sorted(records, key=lambda item: str(item.get("id", "")))


def inspect_lut(root: Path, lut_id: str) -> dict[str, Any]:
    record = find_lut(root, lut_id)
    if not record:
        raise AppError("LUT_NOT_FOUND", f"找不到 LUT: {lut_id}", exit_code=3, path="--lut-id")
    resolved = resolve_lut_path(root, lut_id)
    path = resolved[0] if resolved else root / str(record.get("uri", ""))
    report = {"record": record, "path": str(path), "exists": path.exists() and path.is_file(), "hash_matches": False}
    if report["exists"]:
        report["current_sha256"] = f"sha256:{sha256_file(path)}"
        report["hash_matches"] = report["current_sha256"] == record.get("sha256")
    return report


def _cube_samples(path: Path) -> tuple[list[str], int, tuple[float, float, float], tuple[float, float, float], list[tuple[float, float, float]]]:
    """Read the safe, line-oriented subset needed for static intensity mixing.

    The parser deliberately accepts only a complete 3D cube.  It does not try
    to infer 1D shaper LUTs or vendor-specific extensions, because guessing a
    color transform is worse than returning a structured render warning.
    """
    title: str | None = None
    size: int | None = None
    domain_min = (0.0, 0.0, 0.0)
    domain_max = (1.0, 1.0, 1.0)
    samples: list[tuple[float, float, float]] = []
    try:
        with path.open("r", encoding="utf-8-sig", errors="strict") as handle:
            for raw_line in handle:
                line = raw_line.split("#", 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                key = parts[0].upper()
                if key == "TITLE" and len(parts) >= 2:
                    title = " ".join(parts[1:]).strip().strip('"')[:256]
                    continue
                if key == "LUT_3D_SIZE" and len(parts) == 2:
                    try:
                        size = int(parts[1])
                    except ValueError:
                        size = None
                    continue
                if key in {"DOMAIN_MIN", "DOMAIN_MAX"} and len(parts) == 4:
                    values = [_parse_number(item) for item in parts[1:]]
                    if not all(value is not None and math.isfinite(float(value)) for value in values):
                        raise AppError("LUT_CUBE_INVALID", f"CUBE {key} 必须包含有限数字", exit_code=2, path=str(path))
                    vector = tuple(float(value) for value in values)  # type: ignore[arg-type]
                    if key == "DOMAIN_MIN":
                        domain_min = vector
                    else:
                        domain_max = vector
                    continue
                if len(parts) == 3:
                    values = [_parse_number(item) for item in parts]
                    if not all(value is not None and math.isfinite(float(value)) for value in values):
                        raise AppError("LUT_CUBE_INVALID", "CUBE 样本必须包含有限数字", exit_code=2, path=str(path))
                    samples.append(tuple(float(value) for value in values))  # type: ignore[arg-type]
                    continue
                raise AppError("LUT_CUBE_INVALID", f"无法解析 CUBE 行: {raw_line.strip()[:120]}", exit_code=2, path=str(path))
    except UnicodeError as exc:
        raise AppError("LUT_CUBE_INVALID", "CUBE 文件不是有效 UTF-8 文本", exit_code=2, path=str(path), cause=str(exc)) from exc
    if size is None or not 2 <= size <= 256:
        raise AppError("LUT_CUBE_INVALID", "CUBE 必须声明 2..256 的 LUT_3D_SIZE", exit_code=2, path=str(path))
    if any(high <= low for low, high in zip(domain_min, domain_max)):
        raise AppError("LUT_CUBE_INVALID", "CUBE DOMAIN_MAX 必须大于 DOMAIN_MIN", exit_code=2, path=str(path))
    expected = size ** 3
    if len(samples) != expected:
        raise AppError("LUT_CUBE_INVALID", f"CUBE 样本数 {len(samples)} 与 LUT_3D_SIZE {size}^3 不一致", exit_code=2, path=str(path))
    header: list[str] = []
    if title:
        header.append(f'TITLE "{title} (ai-ad-editor intensity)"')
    header.append(f"LUT_3D_SIZE {size}")
    header.append("DOMAIN_MIN " + " ".join(f"{value:.10g}" for value in domain_min))
    header.append("DOMAIN_MAX " + " ".join(f"{value:.10g}" for value in domain_max))
    return header, size, domain_min, domain_max, samples


def prepare_lut_intensity(root: Path, source: Path, intensity: float) -> Path:
    """Return a project-local derived CUBE for a static 0..1 LUT intensity.

    A derived table blends each LUT sample with the identity sample.  The
    source SHA-256 and normalized intensity form the cache key, so modifying a
    source file can never reuse an old derived transform.  The cache is a
    reproducible render artifact under ``cache/luts`` and never a network or
    external service dependency.
    """
    source = source.expanduser().resolve()
    if source.suffix.lower() != ".cube":
        raise AppError("LUT_INTENSITY_FORMAT_UNSUPPORTED", "静态 LUT 强度混合目前只支持 .cube", exit_code=2, path=str(source))
    try:
        numeric_intensity = float(intensity)
    except (TypeError, ValueError) as exc:
        raise AppError("LUT_INTENSITY_INVALID", "LUT intensity 必须是 0..1 的有限数字", exit_code=2, path="intensity") from exc
    if not math.isfinite(numeric_intensity) or not 0.0 <= numeric_intensity <= 1.0:
        raise AppError("LUT_INTENSITY_INVALID", "LUT intensity 必须位于 0..1", exit_code=2, path="intensity")
    if numeric_intensity <= 0.0:
        # No effect is represented by the caller as an omitted filter.  Keep a
        # valid path here for callers that want to inspect the normalized key.
        return source
    if numeric_intensity >= 1.0:
        return source
    source_digest = sha256_file(source)
    # v2 fixes CUBE's red-fastest sample order. The exact float key prevents
    # distinct strengths colliding after decimal normalization, and never
    # reuses a table generated by the earlier reversed red/blue algorithm.
    key = sha256_bytes(f"cube-identity-red-fastest-v2\n{source_digest}\n{numeric_intensity.hex()}".encode("utf-8"))
    destination = root / "cache" / "luts" / f"{key}.cube"
    header, size, domain_min, domain_max, samples = _cube_samples(source)
    if sha256_file(source) != source_digest:
        raise AppError("LUT_SOURCE_CHANGED", "LUT 文件在派生过程中发生变化", exit_code=6, path=str(source))
    lines = ["# Generated by ai-ad-editor; cube-identity-red-fastest-v2", f"# source_sha256: sha256:{source_digest}", f"# intensity: {numeric_intensity.hex()}", *header]
    for index, sample in enumerate(samples):
        red_index = index % size
        green_index = (index // size) % size
        blue_index = index // (size * size)
        identity = (
            domain_min[0] + red_index / float(size - 1) * (domain_max[0] - domain_min[0]),
            domain_min[1] + green_index / float(size - 1) * (domain_max[1] - domain_min[1]),
            domain_min[2] + blue_index / float(size - 1) * (domain_max[2] - domain_min[2]),
        )
        mixed = tuple(identity[channel] + (sample[channel] - identity[channel]) * numeric_intensity for channel in range(3))
        lines.append(" ".join(f"{max(-64.0, min(64.0, value)):.10f}" for value in mixed))
    text = "\n".join(lines) + "\n"
    if destination.exists():
        if not destination.is_file() or destination.read_bytes() != text.encode('utf-8'):
            raise AppError("LUT_INTENSITY_CACHE_HASH_MISMATCH", "派生 LUT 缓存与源内容/强度不匹配", exit_code=6, path=str(destination))
    else:
        atomic_write_text(destination, text)
    return destination

