"""Optional 剪映片段特效：入场动画、滤镜（pyJianYingDraft 枚举名均为中文）。"""
from __future__ import annotations

from typing import Any


def _pick_enum(enum_cls: type, name: str) -> Any:
    for m in enum_cls:
        if m.name == name:
            return m
    valid = [m.name for m in enum_cls][:40]
    more = len(list(enum_cls)) > 40
    hint = ", ".join(valid) + ("..." if more else "")
    raise ValueError(f"未知枚举名 {name!r}，示例: {hint}")


def apply_video_decorations(
    vseg: Any,
    *,
    intro: str | None = None,
    filter_name: str | None = None,
    filter_intensity: float = 80.0,
) -> None:
    """在 add_segment 之前调用。转场需至少两段视频，单段草稿请用剪映内再加片。"""
    import pyJianYingDraft as d

    if intro:
        vseg.add_animation(_pick_enum(d.IntroType, intro))
    if filter_name:
        vseg.add_filter(_pick_enum(d.FilterType, filter_name), filter_intensity)
