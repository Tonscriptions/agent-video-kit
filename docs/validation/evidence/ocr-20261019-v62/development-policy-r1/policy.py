from __future__ import annotations

"""Local-only runtime policy and reference auditing.

The editor is deliberately usable without a network connection.  This module
keeps that rule in one place so media, conversion, project inspection and
future local-model adapters cannot silently accept a remote endpoint.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit
from urllib.request import url2pathname

from .errors import AppError, argument_error


LOCAL_SCHEMES = {"", "file", "local"}
REMOTE_SCHEMES = {
    "http",
    "https",
    "ftp",
    "ftps",
    "s3",
    "gs",
    "rtmp",
    "rtmps",
    "rtsp",
    "ws",
    "wss",
}
REMOTE_MARKERS = (
    "api.heygen.",
    "api.openai.",
    "api.elevenlabs.",
    "api.fal.ai",
    "api.klingai.",
    "api.gemini.",
    "generativelanguage.googleapis.com",
    "fish.audio",
    "huggingface.co/",
    "youtube.com/",
    "youtu.be/",
    "vimeo.com/",
    "cloudinary.com/",
)
URL_RE = re.compile(r"(?i)\b(?:https?|ftp|s3|gs|rtmp|rtsp|wss?)://")


def reference_kind(value: Any) -> str | None:
    """Return ``local``, ``remote`` or ``provider`` for a scalar reference."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    # Content identities are metadata, not a network URI. Audit must accept
    # the hashes emitted by every media ingest and conversion command.
    if re.fullmatch(r"sha256:[0-9a-fA-F]{64}", text):
        return None
    lower = text.casefold()
    if any(marker in lower for marker in REMOTE_MARKERS):
        return "provider"
    parsed = urlsplit(text)
    scheme = parsed.scheme.casefold()
    if scheme in REMOTE_SCHEMES or URL_RE.search(text):
        return "remote"
    if scheme in {"file", "local"} or not scheme:
        return "local"
    # A Windows drive letter (C:\\...) is a path, not a URI scheme.
    if len(scheme) == 1 and len(text) > 2 and text[1] == ":":
        return "local"
    return "remote"


def require_local_reference(value: Any, *, field: str) -> str:
    """Validate a path/URI accepted by the runtime and return its text.

    ``local://`` and ``file://`` are metadata-only local references.  Plain
    absolute or project-relative paths are also accepted.  All network and
    provider references fail before an external process is started.
    """
    text = str(value or "").strip()
    kind = reference_kind(text)
    if kind in {"remote", "provider"}:
        raise argument_error("只允许本地路径或 local/file URI，禁止远程服务和网络素材", field)
    if not text:
        raise argument_error("本地引用不能为空", field)
    return text


def resolve_local_path(root: Path, value: Any, *, field: str) -> Path:
    """Resolve a validated local path or file/local URI against a project root."""
    text = require_local_reference(value, field=field)
    parsed = urlsplit(text)
    if parsed.scheme.casefold() == "file":
        raw_path = url2pathname(parsed.path)
    elif parsed.scheme.casefold() == "local":
        raw_path = url2pathname(parsed.path or parsed.netloc)
    else:
        raw_path = text
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _walk_scalars(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_scalars(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_scalars(child, f"{path}[{index}]")
    else:
        yield path, value


def _html_template_data_fields(value: Any, path: str = "$") -> set[str]:
    """Typed DOM/CSS text is not a resource address (e.g. p:first-child).

    Only the editor's explicit HTML recipe/report structures qualify. Actual
    URL syntax, known remote schemes and provider markers are still rejected
    by the caller, including within these data fields.
    """
    result: set[str] = set()
    if isinstance(value, dict):
        if value.get('engine') == 'agent-local-html-motion-v1':
            branches = [('template_overrides',), ('plan','template_overrides'), ('plan','compiled_overrides'),
                ('worker','template_controls'), ('worker','effective_template_controls'),
                ('worker','sample','controls'), ('worker','sample','effective_controls'),
                ('controls',), ('effective_controls',), ('frames',), ('issues',), ('font_sources',)]
            for branch in branches:
                node, prefix = value, path
                for key in branch:
                    if not isinstance(node,dict) or key not in node:
                        break
                    node=node[key];prefix+='.'+key
                else:
                    for field, scalar in _walk_scalars(node,prefix):
                        if isinstance(scalar,str) and (field.endswith(('.at','.value','.label','.src','.text','.painted_text','.container',
                            '.sel','.font_family','.family','.familyName','.postScriptName','.postscript_name')) or '.variables.' in field):
                            result.add(field)
        for key, child in value.items():
            result.update(_html_template_data_fields(child,f'{path}.{key}'))
    elif isinstance(value,list):
        for index, child in enumerate(value):
            result.update(_html_template_data_fields(child,f'{path}[{index}]'))
    return result


def audit_local_tree(root: Path) -> dict[str, Any]:
    """Audit JSON/JSONL project artifacts without reading or contacting URLs."""
    root = root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise argument_error("本地审计目录不存在", str(root))
    findings: list[dict[str, Any]] = []
    scanned = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in {".json", ".jsonl"}:
            continue
        scanned += 1
        try:
            if path.suffix.casefold() == ".jsonl":
                payloads = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                payloads = [json.loads(path.read_text(encoding="utf-8"))]
        except (OSError, UnicodeError, ValueError) as exc:
            findings.append({"code": "POLICY_SCAN_PARSE_FAILED", "path": str(path), "detail": str(exc)})
            continue
        for payload in payloads:
            template_data = _html_template_data_fields(payload)
            for field, value in _walk_scalars(payload):
                kind = reference_kind(value)
                if kind == 'remote' and field in template_data and '://' not in value and not URL_RE.search(value):
                    # Unknown schemes here are CSS pseudo classes or literal
                    # words, not an endpoint; keep all ordinary URI fields strict.
                    if urlsplit(value.strip()).scheme.casefold() not in REMOTE_SCHEMES:
                        continue
                if kind in {"remote", "provider"}:
                    findings.append({
                        "code": "POLICY_REMOTE_REFERENCE",
                        "kind": kind,
                        "file": str(path),
                        "field": field,
                        "value_sha256": hashlib.sha256(str(value).encode("utf-8")).hexdigest(),
                    })
    return {
        "root": str(root),
        "network": "disabled",
        "scanned_files": scanned,
        "findings": findings,
        "ok": not findings,
    }


def assert_local_project_reference(value: str, *, field: str) -> Path:
    """Resolve a local project path while rejecting URI-like values."""
    text = require_local_reference(value, field=field)
    parsed = urlsplit(text)
    if parsed.scheme.casefold() == "file":
        from urllib.request import url2pathname

        return Path(url2pathname(parsed.path)).expanduser().resolve()
    if parsed.scheme.casefold() == "local":
        return Path(parsed.path or parsed.netloc).expanduser().resolve()
    return Path(text).expanduser().resolve()


def policy_error_from_findings(report: dict[str, Any]) -> AppError | None:
    if report.get("ok"):
        return None
    first = report.get("findings", [{}])[0]
    return AppError(
        "POLICY_REMOTE_REFERENCE",
        "项目产物包含被本地策略禁止的远程或闭源服务引用",
        exit_code=2,
        path=str(first.get("file", report.get("root"))),
        cause=json.dumps(first, ensure_ascii=False),
    )
