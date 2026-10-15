"""Explicit character-error-rate evidence; no language model or script guessing."""
from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any

from .captions import parse_caption_file
from .errors import argument_error
from .utils import sha256_file

CAPTION_SUFFIXES = {".srt", ".vtt", ".ass", ".ssa", ".ttml", ".dfxp"}


def read_transcript(path: Path) -> str:
    if not path.is_file():
        raise argument_error("转写或参考文件不存在", str(path))
    if path.suffix.lower() in CAPTION_SUFFIXES:
        return " ".join(cue["text"] for cue in parse_caption_file(path))
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise argument_error("逐字稿必须为 UTF-8 文本", str(path)) from exc


def normalize_text(text: str, mode: str) -> str:
    if mode == "raw":
        return text
    if mode != "nfkc-text":
        raise argument_error("normalization 只能为 raw 或 nfkc-text", "normalization")
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if unicodedata.category(c)[0] in "LMN")


def character_error_rate(reference: str, hypothesis: str, *, normalization: str = "nfkc-text") -> dict[str, Any]:
    ref, hyp = normalize_text(reference, normalization), normalize_text(hypothesis, normalization)
    if not ref:
        raise argument_error("归一化后的参考逐字稿不能为空", "reference")
    if len(ref) * len(hyp) > 25_000_000 or max(len(ref), len(hyp)) > 100_000:
        raise argument_error("CER 超出单次计算预算，请按节目或章节拆分", "input/reference")
    # Two rows retain deterministic edit counts, without an O(N*M) matrix.
    # Equal-cost paths prefer substitution, deletion, then insertion.
    previous = [(j, 0, 0, j) for j in range(len(hyp) + 1)]
    for i, expected in enumerate(ref, 1):
        current = [(i, 0, i, 0)]
        for j, actual in enumerate(hyp, 1):
            if expected == actual:
                current.append(previous[j - 1])
            else:
                d, s, deleted, inserted = previous[j - 1]
                substitution = (d + 1, s + 1, deleted, inserted)
                d, s, deleted, inserted = previous[j]
                deletion = (d + 1, s, deleted + 1, inserted)
                d, s, deleted, inserted = current[j - 1]
                insertion = (d + 1, s, deleted, inserted + 1)
                current.append(min((substitution, deletion, insertion), key=lambda x: x[0]))
        previous = current
    distance, substitutions, deletions, insertions = previous[-1]
    return {"normalization": normalization, "script_conversion": "none", "reference_text": ref, "hypothesis_text": hyp, "reference_characters": len(ref), "hypothesis_characters": len(hyp), "edit_distance": distance, "substitutions": substitutions, "deletions": deletions, "insertions": insertions, "cer": distance / len(ref), "exact_match": ref == hyp}


def evaluate_transcripts(reference: Path, hypothesis: Path, *, normalization: str) -> dict[str, Any]:
    return {"reference": str(reference), "input": str(hypothesis), "reference_sha256": "sha256:" + sha256_file(reference), "input_sha256": "sha256:" + sha256_file(hypothesis), **character_error_rate(read_transcript(reference), read_transcript(hypothesis), normalization=normalization)}
