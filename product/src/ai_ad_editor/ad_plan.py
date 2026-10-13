from __future__ import annotations

import math
from typing import Any

from .errors import argument_error
from .project import TICKS_PER_SECOND
from .utils import ID_RE, safe_filename


DEFAULT_PHASES: tuple[tuple[str, str, float], ...] = (
    ("hook", "Hook", 0.16),
    ("problem", "Problem", 0.14),
    ("benefit", "Benefit", 0.24),
    ("proof", "Proof", 0.18),
    ("offer", "Offer", 0.10),
    ("cta", "CTA", 0.18),
)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def build_ad_plan(brief: dict[str, Any], *, analysis: dict[str, Any] | None = None) -> dict[str, Any]:
    if not isinstance(brief, dict):
        raise argument_error("广告 brief 顶层必须是 JSON 对象")
    product = _text(brief.get("product") or brief.get("product_name"))
    if not product:
        raise argument_error("广告 brief 缺少 product", "product")
    try:
        duration_seconds = float(brief.get("duration_seconds", brief.get("duration", 15)))
    except (TypeError, ValueError) as exc:
        raise argument_error("广告时长必须是数字", "duration_seconds") from exc
    if not math.isfinite(duration_seconds) or duration_seconds < 3 or duration_seconds > 180:
        raise argument_error("广告时长必须在 3 到 180 秒之间", "duration_seconds")
    cta = _text(brief.get("cta"), "立即了解")
    audience = _text(brief.get("audience"), "目标受众")
    platform = _text(brief.get("platform"), "generic")
    profile = _text(brief.get("profile"), "vertical")

    custom_phases = brief.get("phases")
    phase_specs: list[tuple[str, str, float]] = []
    seen_phase_ids: set[str] = set()
    if custom_phases is not None:
        if not isinstance(custom_phases, list) or not custom_phases:
            raise argument_error("phases 必须是非空数组", "phases")
        for index, item in enumerate(custom_phases):
            if not isinstance(item, dict):
                raise argument_error(f"phases[{index}] 必须是对象", f"phases[{index}]")
            phase_id = safe_filename(_text(item.get("id") or item.get("name"), f"phase_{index + 1}"))
            if not ID_RE.fullmatch(phase_id):
                raise argument_error(f"phases[{index}].id 不符合 ID 规范", f"phases[{index}].id")
            if phase_id in seen_phase_ids:
                raise argument_error(f"phases[{index}].id 重复: {phase_id}", f"phases[{index}].id")
            seen_phase_ids.add(phase_id)
            label = _text(item.get("label"), phase_id)
            try:
                weight = float(item.get("weight", item.get("ratio", 0)))
            except (TypeError, ValueError) as exc:
                raise argument_error(f"phases[{index}].weight 必须是数字", f"phases[{index}].weight") from exc
            if weight <= 0:
                raise argument_error(f"phases[{index}].weight 必须大于 0", f"phases[{index}].weight")
            phase_specs.append((phase_id, label, weight))
    else:
        phase_specs = list(DEFAULT_PHASES)
    total_weight = sum(item[2] for item in phase_specs)
    if total_weight <= 0:
        raise argument_error("广告阶段总权重必须大于 0", "phases")

    total_tick = int(round(duration_seconds * TICKS_PER_SECOND))
    visuals = brief.get("visuals") if isinstance(brief.get("visuals"), dict) else {}
    phases: list[dict[str, Any]] = []
    cursor = 0
    for index, (phase_id, label, weight) in enumerate(phase_specs):
        phase_duration = int(round(total_tick * weight / total_weight))
        if index == len(phase_specs) - 1:
            phase_duration = max(1, total_tick - cursor)
        phases.append({
            "id": phase_id,
            "label": label,
            "start_tick": cursor,
            "duration_tick": phase_duration,
            "end_tick": cursor + phase_duration,
            "message": _text(brief.get(phase_id)),
            "visual_direction": _text(visuals.get(phase_id), "选择与阶段目标匹配的本地素材"),
        })
        cursor += phase_duration

    markers = [{"id": f"marker_{phase['id']}", "at_tick": phase["start_tick"], "label": phase["label"]} for phase in phases]
    operations = [{"op": "add_marker", "id": marker["id"], "at_tick": marker["at_tick"], "label": marker["label"]} for marker in markers]
    analysis_summary: dict[str, Any] = {"provided": False}
    if isinstance(analysis, dict):
        candidates = analysis.get("candidates") if isinstance(analysis.get("candidates"), list) else []
        scenes = analysis.get("scenes") if isinstance(analysis.get("scenes"), list) else []
        analysis_summary = {"provided": True, "engine": analysis.get("engine"), "candidate_count": len(candidates), "scene_count": len(scenes), "source_sha256": analysis.get("source_sha256")}
    return {
        "plan_version": "0.1.0",
        "engine": "local-ad-plan",
        "network": "disabled",
        "product": product,
        "audience": audience,
        "cta": cta,
        "platform": platform,
        "profile": profile,
        "duration_seconds": duration_seconds,
        "duration_tick": total_tick,
        "phases": phases,
        "markers": markers,
        "timeline_operations": operations,
        "analysis": analysis_summary,
        "guidance": {
            "hook": "前两秒给出明确冲突、结果或新奇画面",
            "proof": "优先使用可核验的本地素材、数据或演示镜头",
            "cta": cta,
        },
    }
