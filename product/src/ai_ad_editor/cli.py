from __future__ import annotations

import argparse
import copy
import contextlib
import io
import json
import math
import os
import platform
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from . import ENGINE_ID, SCHEMA_VERSION, VERSION
from .ad_plan import build_ad_plan
from .captions import parse_caption_file, validate_cues, write_srt_file
from .convert import export_external, import_external
from .errors import AppError, argument_error, dependency_error
from .media import classify_path, ffmpeg_version, generate_proxy, generate_thumbnail, generate_waveform, probe_media, relink_missing_assets, stabilize_media
from .project import (
    asset_map,
    create_project,
    find_sequence,
    find_track,
    create_snapshot,
    history_dir,
    ledger_file,
    load_project,
    load_snapshot,
    lock_file,
    project_file,
    project_transaction,
    queue_cancel_lock,
    project_write_lock,
    recover_pending_transaction,
    restore_snapshot,
    save_project,
)
from .quality import GOLDEN_VERSION, build_golden_manifest, check_output, compare_golden_manifest, normalize_golden_constraints, validate_golden_manifest
from .recommend import recommend_highlights
from .library import duplicate_groups, index_directory, search_catalog, visual_similarity_groups
from .lut_library import inspect_lut, list_luts, prepare_lut_registration, register_lut
from .batch import _load_variants, run_template_batch
from .capabilities import build_capability_manifest
from .transcribe import transcribe_local, write_srt
from .render import OUTPUT_CONTAINERS, OUTPUT_PIXEL_FORMATS, OUTPUT_PROFILES, output_settings, render_fingerprints, render_project, speed_curve_duration_seconds
from .rights import VALID_STATUSES, active_records, add_record, apply_disposition_to_project, check_project_rights, create_disposition_decision, disposition_decisions, effective_disposition_decisions, impacted_artifacts, load_ledger, record_history, release_manifest, revise_record, save_ledger
from .understand import detect_beats, understand_media
from .tracking import build_reframe_plan, track_media
from .runtime import configure_local_runtime
from .template import apply_template_operations, instantiate
from .migration import SUPPORTED_SOURCE_VERSIONS, migrate_project_payload
from .speech import flite_available, synthesize_local_tts
from .effects import EFFECT_CATALOG_VERSION, get_effect, list_effects
from .motion_presets import MOTION_PRESET_CATALOG_VERSION, canonical_motion_preset, get_motion_preset, list_motion_presets
from .scopes import SCOPE_VERSION, generate_scopes
from .policy import audit_local_tree, policy_error_from_findings, require_local_reference
from .render_queue import JOB_STATUSES, cancel_path, enqueue as enqueue_render_jobs, find_job, load_queue, normalize_job, queue_path, save_queue, set_status
from .smart_cut import SMART_CUT_VERSION, build_smart_cut_plan, replace_clip_with_smart_cut
from .beat_edit import BEAT_CUT_VERSION, build_beat_cut_plan
from .utils import atomic_write_json, atomic_write_text, ensure_inside, idempotency_record_path, load_json, new_id, now_iso, request_fingerprint, safe_filename, sha256_file
from .validator import validate_project


def _common(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--format", choices=("json", "text"), default="json" if not suppress_defaults else default, help="输出格式")
    parser.add_argument("--request-id", default=default)
    parser.add_argument("--idempotency-key", default=default)
    parser.add_argument("--dry-run", action="store_true", default=default)
    parser.add_argument("--no-network", action="store_true", default=default if suppress_defaults else True)
    parser.add_argument("--progress", choices=("none", "jsonl"), default="none" if not suppress_defaults else default)


def _leaf_common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    _common(parser, suppress_defaults=True)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-ad-editor", description="本地优先、面向 Agent 的广告视频 CLI")
    _common(parser)
    subs = parser.add_subparsers(dest="domain", required=True)

    project = subs.add_parser("project", help="项目管理")
    ps = project.add_subparsers(dest="action", required=True)
    init = _leaf_common(ps.add_parser("init", help="创建项目"))
    init.add_argument("path", help="项目目录")
    init.add_argument("--name", default=None)
    init.add_argument("--project-id", default=None)
    inspect = _leaf_common(ps.add_parser("inspect", help="检查项目"))
    inspect.add_argument("--project", required=True)
    snapshot = _leaf_common(ps.add_parser("snapshot", help="创建项目快照"))
    snapshot.add_argument("--project", required=True)
    snapshot.add_argument("--label", default="manual")
    restore = _leaf_common(ps.add_parser("restore", help="恢复项目快照"))
    restore.add_argument("--project", required=True)
    restore.add_argument("--snapshot", required=True, help="快照 ID 或 history/*.json 路径")
    migrate = _leaf_common(ps.add_parser("migrate", help="将旧项目迁移到当前 Agent Project schema"))
    migrate.add_argument("--project", required=True)
    migrate.add_argument("--report", default=None, help="可选项目内迁移报告路径")
    recover = _leaf_common(ps.add_parser("recover", help="恢复上次中断的项目元数据事务"))
    recover.add_argument("--project", required=True)

    media = subs.add_parser("media", help="素材管理")
    ms = media.add_subparsers(dest="action", required=True)
    ingest = _leaf_common(ms.add_parser("ingest", help="导入本地素材"))
    ingest.add_argument("--project", required=True)
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--asset-id", default=None)
    ingest.add_argument("--source-url", default=None)
    ingest.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    ingest.add_argument("--license-url", default="")
    ingest.add_argument("--permitted-use", action="append", default=["internal"])
    ingest.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    ingest.add_argument("--evidence", default="")
    ingest.add_argument("--creator", default="unknown")
    stabilize = _leaf_common(ms.add_parser("stabilize", help="使用本地 FFmpeg vidstab 两遍分析生成防抖派生素材"))
    stabilize.add_argument("--project", required=True)
    stabilize.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    stabilize.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    stabilize.add_argument("--derived-asset-id", default=None, help="生成的派生资产 ID；默认自动生成")
    stabilize.add_argument("--output", default=None, help="项目内输出视频路径；默认 assets/derived/stabilized_<id>.mp4")
    stabilize.add_argument("--shakiness", type=int, default=5)
    stabilize.add_argument("--accuracy", type=int, default=15)
    stabilize.add_argument("--stepsize", type=int, default=6)
    stabilize.add_argument("--mincontrast", type=float, default=0.25)
    stabilize.add_argument("--smoothing", type=int, default=15)
    stabilize.add_argument("--maxshift", type=int, default=-1)
    stabilize.add_argument("--maxangle", type=float, default=-1.0)
    stabilize.add_argument("--crop", choices=("keep", "black"), default="keep")
    stabilize.add_argument("--optzoom", type=int, choices=(0, 1, 2), default=1)
    stabilize.add_argument("--zoom", type=float, default=0.0)
    stabilize.add_argument("--interpol", choices=("no", "linear", "bilinear", "bicubic"), default="bilinear")
    stabilize.add_argument("--source-url", default=None)
    stabilize.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    stabilize.add_argument("--license-url", default="")
    stabilize.add_argument("--permitted-use", action="append", default=["internal"])
    stabilize.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    stabilize.add_argument("--evidence", default="")
    stabilize.add_argument("--creator", default="unknown")
    understand = _leaf_common(ms.add_parser("understand", help="本地镜头/静音分析"))
    understand.add_argument("--project", required=True)
    understand.add_argument("--asset-id", default=None)
    understand.add_argument("--input", default=None)
    understand.add_argument("--scene-threshold", type=float, default=0.4)
    understand.add_argument("--beats", action="store_true", help="估计本地音频节拍锚点")
    understand.add_argument("--transcribe", action="store_true", help="使用已存在的本地 ASR 模型")
    understand.add_argument("--model-path", default=None, help="离线 ASR 模型目录；不会自动下载")
    understand.add_argument("--language", default=None)
    understand.add_argument("--srt", default=None, help="可选项目内 SRT 输出路径")
    prepare = _leaf_common(ms.add_parser("prepare", help="生成本地代理、缩略图和波形"))
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--asset-id", default=None)
    prepare.add_argument("--input", default=None)
    prepare.add_argument("--proxy-width", type=int, default=0, help="大于 0 时生成 H.264 代理")
    prepare.add_argument("--thumbnail", action="store_true")
    prepare.add_argument("--waveform", action="store_true")
    prepare.add_argument("--at-seconds", type=float, default=0.0)
    highlights = _leaf_common(ms.add_parser("highlights", help="本地启发式高光候选"))
    highlights.add_argument("--project", required=True)
    highlights.add_argument("--asset-id", default=None)
    highlights.add_argument("--input", default=None)
    highlights.add_argument("--top-k", type=int, default=5)
    highlights.add_argument("--min-duration", type=float, default=1.0)
    highlights.add_argument("--max-duration", type=float, default=8.0)
    highlights.add_argument("--beats", action="store_true")
    highlights.add_argument("--output", default=None)
    beat_cut = _leaf_common(ms.add_parser("beat-cut", help="按本地音频节拍生成并应用卡点剪辑计划"))
    beat_cut.add_argument("--project", required=True)
    beat_audio = beat_cut.add_mutually_exclusive_group(required=True)
    beat_audio.add_argument("--audio-asset-id", default=None, help="项目内含音频流的资产 ID")
    beat_audio.add_argument("--input", default=None, help="本地音频/视频路径；仅用于节拍分析")
    beat_cut.add_argument("--source-asset-id", action="append", required=True, help="可重复：项目内视频素材 ID")
    beat_cut.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    beat_cut.add_argument("--sequence-id", default=None, help="目标序列 ID，默认主序列")
    beat_cut.add_argument("--start-seconds", type=float, default=0.0, help="音频分析起点")
    beat_cut.add_argument("--end-seconds", type=float, default=None, help="音频分析终点；默认音频结束")
    beat_cut.add_argument("--timeline-start-seconds", type=float, default=0.0, help="写入时间线的起点")
    beat_cut.add_argument("--min-segment-seconds", type=float, default=0.2)
    beat_cut.add_argument("--max-clips", type=int, default=128)
    beat_cut.add_argument("--source-mode", choices=("cycle", "ordered"), default="cycle", help="源素材选择：循环或按顺序用完后复用最后一个")
    beat_cut.add_argument("--output", default=None, help="项目内卡点报告路径")
    beat_cut.add_argument("--apply", action="store_true", help="创建快照并将卡点片段写入目标视频轨道")
    beat_cut.add_argument("--replace-track", action="store_true", help="应用前清空目标视频轨道已有片段")
    smart_cut = _leaf_common(ms.add_parser("smart-cut", help="基于本地静音检测生成或应用智能剪口播计划"))
    smart_cut.add_argument("--project", required=True)
    smart_cut.add_argument("--sequence-id", default=None)
    smart_cut.add_argument("--clip-id", required=True, help="目标视频片段 ID")
    smart_cut.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    smart_cut.add_argument("--linked-track-id", action="append", default=[], help="可重复：按同一 clip-id 联动裁切音频轨道")
    smart_cut.add_argument("--linked-clip-id", action="append", default=[], help="可重复：与 --linked-track-id 一一对应的音频片段 ID；省略时复用目标 clip-id")
    smart_cut.add_argument("--min-silence-seconds", type=float, default=0.6)
    smart_cut.add_argument("--keep-padding-seconds", type=float, default=0.12)
    smart_cut.add_argument("--min-segment-seconds", type=float, default=0.2)
    smart_cut.add_argument("--silence-db", type=float, default=-35.0)
    smart_cut.add_argument("--output", default=None, help="项目内智能剪口播报告路径")
    smart_cut.add_argument("--apply", action="store_true", help="创建快照并将计划写回目标轨道")
    relink = _leaf_common(ms.add_parser("relink", help="按内容哈希重链接丢失素材"))
    relink.add_argument("--project", required=True)
    relink.add_argument("--search-root", required=True, help="本地素材搜索目录")
    relink.add_argument("--match-by-name", action="store_true", help="哈希无匹配时允许唯一文件名近似匹配")
    track = _leaf_common(ms.add_parser("track", help="本地对象跟踪并生成关键帧"))
    track.add_argument("--project", required=True)
    track.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    track.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    track.add_argument("--roi", required=True, help="归一化 ROI：x,y,width,height")
    track.add_argument("--start-seconds", type=float, default=0.0)
    track.add_argument("--end-seconds", type=float, default=None)
    track.add_argument("--step-frames", type=int, default=4)
    track.add_argument("--search-radius", type=int, default=48)
    track.add_argument("--max-width", type=int, default=640)
    track.add_argument("--max-samples", type=int, default=600, help="最大采样帧数，超过预算时降低采样频率并写入报告")
    track.add_argument("--output", default=None, help="项目内跟踪报告 JSON 路径")
    track.add_argument("--clip-id", default=None, help="可选：将位置关键帧应用到片段")
    track.add_argument("--track-id", default=None, help="与 --clip-id 联用以限定轨道")
    track.add_argument("--sequence-id", default=None, help="与 --clip-id 联用，默认主序列")
    reframe = _leaf_common(ms.add_parser("reframe", help="将本地对象跟踪转换为目标画幅动态裁切"))
    reframe.add_argument("--project", required=True)
    reframe.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    reframe.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    reframe.add_argument("--roi", required=True, help="归一化 ROI：x,y,width,height")
    reframe.add_argument("--clip-id", required=True, help="要写入动态裁切的直接媒体片段 ID")
    reframe.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    reframe.add_argument("--sequence-id", default=None, help="目标序列 ID，默认主序列")
    reframe.add_argument("--target-width", type=int, default=None, help="目标画布宽度；省略时读取项目画布")
    reframe.add_argument("--target-height", type=int, default=None, help="目标画布高度；省略时读取项目画布")
    reframe.add_argument("--target-aspect", type=float, default=None, help="目标宽高比；省略时由目标画布计算")
    reframe.add_argument("--margin", type=float, default=0.12, help="跟踪主体安全边距，范围 0..0.75")
    reframe.add_argument("--fit", choices=("fit", "fill", "stretch"), default="fill")
    reframe.add_argument("--start-seconds", type=float, default=None)
    reframe.add_argument("--end-seconds", type=float, default=None)
    reframe.add_argument("--step-frames", type=int, default=4)
    reframe.add_argument("--search-radius", type=int, default=48)
    reframe.add_argument("--max-width", type=int, default=640)
    reframe.add_argument("--max-samples", type=int, default=600)
    reframe.add_argument("--output", default=None, help="项目内自动重构图报告 JSON 路径")
    reframe.add_argument("--apply", action="store_true", help="创建快照并将动态裁切写回片段")

    ad = subs.add_parser("ad", help="本地广告结构规划")
    ads = ad.add_subparsers(dest="action", required=True)
    ad_plan = _leaf_common(ads.add_parser("plan", help="从 JSON brief 生成广告节拍与时间线标记"))
    ad_plan.add_argument("--project", required=True)
    ad_plan.add_argument("--input", required=True, help="广告 brief JSON")
    ad_plan.add_argument("--analysis", default=None, help="可选本地素材理解/高光报告 JSON")
    ad_plan.add_argument("--output", default=None)
    ad_apply = _leaf_common(ads.add_parser("apply", help="将本地广告计划写入序列标记和时长"))
    ad_apply.add_argument("--project", required=True)
    ad_apply.add_argument("--input", required=True, help="ad plan 输出 JSON 或 plan 对象")
    ad_apply.add_argument("--sequence-id", default=None)
    ad_apply.add_argument("--replace-markers", action="store_true", help="替换计划中同 ID 的既有标记")
    ad_apply.add_argument("--preserve-duration", action="store_true", help="不把序列时长设置为计划时长")

    subtitle = subs.add_parser("subtitle", help="字幕解析、验证与规范化")
    ss = subtitle.add_subparsers(dest="action", required=True)
    subtitle_validate = _leaf_common(ss.add_parser("validate", help="验证 SRT/VTT/ASS/SSA/TTML 字幕"))
    subtitle_validate.add_argument("--input", required=True)
    subtitle_validate.add_argument("--project", default=None)
    subtitle_validate.add_argument("--duration", type=float, default=None)
    subtitle_validate.add_argument("--allow-overlap", action="store_true")
    subtitle_validate.add_argument("--report", default=None)
    subtitle_normalize = _leaf_common(ss.add_parser("normalize", help="将字幕规范化为 SRT"))
    subtitle_normalize.add_argument("--input", required=True)
    subtitle_normalize.add_argument("--output", required=True)
    subtitle_normalize.add_argument("--project", default=None)
    subtitle_normalize.add_argument("--allow-overlap", action="store_true")

    tts = subs.add_parser("tts", help="本地离线文本转语音")
    tts_sub = tts.add_subparsers(dest="action", required=True)
    tts_synthesize = _leaf_common(tts_sub.add_parser("synthesize", help="使用 FFmpeg 内置 flite 生成本地 WAV"))
    tts_synthesize.add_argument("--project", required=True)
    tts_text = tts_synthesize.add_mutually_exclusive_group(required=True)
    tts_text.add_argument("--text", default=None, help="ASCII/英文文本")
    tts_text.add_argument("--input", default=None, help="本地 UTF-8 文本文件")
    tts_synthesize.add_argument("--output", default=None, help="项目内 WAV 输出路径")
    tts_synthesize.add_argument("--voice", default="kal", help="FFmpeg flite voice，例如 kal、slt、rms")
    tts_synthesize.add_argument("--sample-rate", type=int, default=48_000)
    tts_synthesize.add_argument("--channels", type=int, choices=(1, 2), default=2)

    effects = subs.add_parser("effects", help="查询本地 FFmpeg 效果目录")
    effects_sub = effects.add_subparsers(dest="action", required=True)
    effects_list = _leaf_common(effects_sub.add_parser("list", help="列出可用效果及参数契约"))
    effects_list.add_argument("--query", default=None, help="按 ID、别名、类别或后端筛选")
    effects_list.add_argument("--keyframable-only", action="store_true", help="只列出支持逐帧参数关键帧的效果")
    effects_inspect = _leaf_common(effects_sub.add_parser("inspect", help="查看单个效果的详细契约"))
    effects_inspect.add_argument("--name", required=True, help="效果 ID 或别名")

    motion = subs.add_parser("motion", help="查询和应用本地关键帧运镜预设")
    motion_sub = motion.add_subparsers(dest="action", required=True)
    motion_list = _leaf_common(motion_sub.add_parser("list", help="列出可用运镜预设及参数契约"))
    motion_list.add_argument("--query", default=None, help="按 ID、别名、类别或说明筛选")
    motion_inspect = _leaf_common(motion_sub.add_parser("inspect", help="查看单个运镜预设的详细契约"))
    motion_inspect.add_argument("--name", required=True, help="预设 ID 或别名")
    motion_apply = _leaf_common(motion_sub.add_parser("apply", help="将运镜预设应用到已有片段"))
    motion_apply.add_argument("--project", required=True)
    motion_apply.add_argument("--clip-id", required=True)
    motion_apply.add_argument("--track-id", default=None, help="可选轨道 ID，用于消除重复片段 ID")
    motion_apply.add_argument("--sequence-id", default=None, help="默认主序列")
    motion_apply.add_argument("--preset", required=True, help="预设 ID 或别名")
    motion_apply.add_argument("--amount", type=float, default=None, help="缩放/位移/抖动强度；默认使用目录值")
    motion_apply.add_argument("--degrees", type=float, default=None, help="旋转角度；默认使用目录值")
    motion_apply.add_argument("--points", type=int, default=None, help="shake 关键帧点数；默认使用目录值")
    motion_apply.add_argument("--start-tick", type=int, default=None, help="片段内起始 tick；默认 0")
    motion_apply.add_argument("--end-tick", type=int, default=None, help="片段内结束 tick；默认片段时长")

    timeline = subs.add_parser("timeline", help="时间线编排")
    ts = timeline.add_subparsers(dest="action", required=True)
    compose = _leaf_common(ts.add_parser("compose", help="应用 JSON 变更集"))
    compose.add_argument("--project", required=True)
    compose.add_argument("--input", required=True)
    compose.add_argument("--sequence-id", default=None)

    validate = _leaf_common(subs.add_parser("validate", help="验证项目"))
    validate.add_argument("--project", required=True)
    validate.add_argument("--target", default="commercial_ad")
    validate.add_argument("--strict-rights", action="store_true")
    validate.add_argument("--report", default=None)

    rights = subs.add_parser("rights", help="权利门禁")
    rs = rights.add_subparsers(dest="action", required=True)
    check = _leaf_common(rs.add_parser("check", help="检查发布资格"))
    check.add_argument("--project", required=True)
    check.add_argument("--target", default="commercial_ad")
    rights_list = _leaf_common(rs.add_parser("list", help="列出当前有效权利记录"))
    rights_list.add_argument("--project", required=True)
    rights_list.add_argument("--status", choices=tuple(sorted(VALID_STATUSES)), default=None)
    rights_history = _leaf_common(rs.add_parser("history", help="查看资产权利修订和审计历史"))
    rights_history.add_argument("--project", required=True)
    rights_history.add_argument("--asset-id", required=True)
    rights_update = _leaf_common(rs.add_parser("update", help="创建权利记录不可变修订"))
    rights_update.add_argument("--project", required=True)
    rights_update.add_argument("--asset-id", required=True)
    rights_update.add_argument("--status", choices=tuple(sorted(VALID_STATUSES)), default=None)
    rights_update.add_argument("--patch", default=None, help="本地 JSON 修订对象")
    rights_update.add_argument("--reason", required=True)
    rights_update.add_argument("--actor", default="ai-ad-editor")
    rights_update.add_argument("--reopen", action="store_true", help="恢复争议/过期/撤下/阻断记录")
    rights_update.add_argument("--source-url", default=None)
    rights_update.add_argument("--source-version", default=None)
    rights_update.add_argument("--retrieved-at", default=None)
    rights_update.add_argument("--creator", default=None)
    rights_update.add_argument("--license-spdx", default=None)
    rights_update.add_argument("--license-url", default=None)
    rights_update.add_argument("--attribution", default=None)
    rights_update.add_argument("--evidence", action="append", default=None)
    rights_update.add_argument("--expires-at", default=None)
    rights_update.add_argument("--takedown-status", choices=("clear", "notice", "blocked"), default=None)
    rights_update.add_argument("--permitted-use", action="append", default=None)
    rights_update.add_argument("--permitted-channel", action="append", default=None)
    rights_update.add_argument("--restriction", action="append", default=None)
    rights_export = _leaf_common(rs.add_parser("export", help="生成本地发布权利清单"))
    rights_export.add_argument("--project", required=True)
    rights_export.add_argument("--output", required=True, help="项目内 JSON 输出路径")
    rights_export.add_argument("--target", default="commercial_ad")
    rights_batch = _leaf_common(rs.add_parser("batch-update", help="原子批量创建权利记录修订"))
    rights_batch.add_argument("--project", required=True)
    rights_batch.add_argument("--input", required=True, help="本地 JSON：{updates:[{asset_id,patch,reason,actor,reopen}]} ")
    rights_impact = _leaf_common(rs.add_parser("impact", help="查找资产影响的本地历史产物"))
    rights_impact.add_argument("--project", required=True)
    rights_impact.add_argument("--asset-id", required=True)
    rights_retract = _leaf_common(rs.add_parser("retract", help="撤下资产并生成历史影响报告"))
    rights_retract.add_argument("--project", required=True)
    rights_retract.add_argument("--asset-id", required=True)
    rights_retract.add_argument("--status", choices=("takedown", "disputed", "blocked"), default="takedown")
    rights_retract.add_argument("--reason", required=True)
    rights_retract.add_argument("--actor", default="ai-ad-editor")
    rights_decide = _leaf_common(rs.add_parser("decide", help="记录历史成片替换/删除/保留决策"))
    rights_decide.add_argument("--project", required=True)
    rights_decide.add_argument("--asset-id", required=True)
    rights_decide.add_argument("--action", dest="disposition_action", choices=("replace", "delete", "retain"), required=True)
    rights_decide.add_argument("--status", choices=("proposed", "approved", "cancelled"), default="proposed")
    rights_decide.add_argument("--replacement-asset-id", default=None)
    rights_decide.add_argument("--supersedes-decision-id", default=None)
    rights_decide.add_argument("--target", default="commercial_ad")
    rights_decide.add_argument("--reason", required=True)
    rights_decide.add_argument("--actor", default="ai-ad-editor")
    rights_apply = _leaf_common(rs.add_parser("apply", help="执行已批准历史处置并更新当前项目"))
    rights_apply.add_argument("--project", required=True)
    rights_apply.add_argument("--decision-id", required=True)

    render = _leaf_common(subs.add_parser("render", help="本地 FFmpeg 渲染"))
    render.add_argument("--project", required=True)
    render.add_argument("--sequence-id", default=None)
    render.add_argument("--output", default=None)
    render.add_argument("--publish", action="store_true")
    render.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None, help="输出画布档案")
    render.add_argument("--width", type=int, default=None, help="自定义输出宽度；必须与 --height 一起使用")
    render.add_argument("--height", type=int, default=None, help="自定义输出高度；必须与 --width 一起使用")
    render.add_argument("--cancel-file", default=None, help="存在该文件时取消渲染并清理临时产物")
    render.add_argument("--resume", default=None, help="从此前失败/取消且依赖未变化的 render 操作重建")
    render.add_argument("--container", choices=tuple(OUTPUT_CONTAINERS), default=None, help="输出容器：mp4、webm 或 mkv")
    render.add_argument("--video-codec", choices=("libx264", "libx265", "libvpx-vp9", "libvpx", "libaom-av1"), default=None)
    render.add_argument("--audio-codec", choices=("aac", "libopus", "opus", "pcm_s16le"), default=None)
    render.add_argument("--crf", type=int, default=None, help="视频 CRF，范围 0..63")
    render.add_argument("--video-bitrate", default=None, help="可选视频码率，例如 8M")
    render.add_argument("--audio-bitrate", default=None, help="音频码率，例如 192k")
    render.add_argument("--pixel-format", choices=OUTPUT_PIXEL_FORMATS, default=None)

    queue = subs.add_parser("queue", help="项目内持久化渲染队列")
    queue_sub = queue.add_subparsers(dest="action", required=True)
    queue_enqueue = _leaf_common(queue_sub.add_parser("enqueue", help="写入一个或多个本地渲染作业"))
    queue_enqueue.add_argument("--project", required=True)
    queue_enqueue.add_argument("--input", required=True, help="作业 JSON；可为单个作业对象或 {jobs:[...]} 文件")
    queue_list = _leaf_common(queue_sub.add_parser("list", help="列出队列作业"))
    queue_list.add_argument("--project", required=True)
    queue_list.add_argument("--status", choices=tuple(sorted(JOB_STATUSES)), default=None)
    queue_inspect = _leaf_common(queue_sub.add_parser("inspect", help="检查单个队列作业"))
    queue_inspect.add_argument("--project", required=True)
    queue_inspect.add_argument("--job-id", required=True)
    queue_run = _leaf_common(queue_sub.add_parser("run", help="按顺序执行本地渲染作业"))
    queue_run.add_argument("--project", required=True)
    queue_run.add_argument("--job-id", default=None, help="只执行指定作业；失败或取消作业可显式重试")
    queue_run.add_argument("--max-jobs", type=int, default=None, help="本次最多执行的待处理作业数")
    queue_run.add_argument("--continue-on-error", action="store_true", help="单个作业失败后继续执行后续作业")
    queue_cancel = _leaf_common(queue_sub.add_parser("cancel", help="请求取消或取消尚未启动的作业"))
    queue_cancel.add_argument("--project", required=True)
    queue_cancel.add_argument("--job-id", required=True)

    quality = subs.add_parser("quality", help="输出质量检查")
    qs = quality.add_subparsers(dest="action", required=True)
    qcheck = _leaf_common(qs.add_parser("check", help="检查已渲染媒体"))
    qcheck.add_argument("--project", required=True)
    qcheck.add_argument("--input", required=True)
    qcheck.add_argument("--sequence-id", default=None)
    qcheck.add_argument("--report", default=None)
    qcheck.add_argument("--require-audio", action="store_true")
    qcheck.add_argument("--expensive", action="store_true", help="运行黑帧和响度扫描")
    qcheck.add_argument("--max-av-sync-ms", type=float, default=80.0, help="允许的视频/音频时长差，默认 80ms")
    qcheck.add_argument("--target-lufs", type=float, default=None, help="可选目标 integrated LUFS；需配合 --expensive")
    qcheck.add_argument("--lufs-tolerance", type=float, default=2.0)
    qcheck.add_argument("--fail-on-black", action="store_true", help="检测到黑帧区间时将质量检查判失败")
    qcheck.add_argument("--max-true-peak-dbfs", type=float, default=None, help="可选 true peak 上限，常用 -1 dBFS")
    qcheck.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None, help="按输出画布档案检查")
    qcheck.add_argument("--width", type=int, default=None)
    qcheck.add_argument("--height", type=int, default=None)
    qscopes = _leaf_common(qs.add_parser("scopes", help="生成本地 waveform/vectorscope/histogram 色彩审查图"))
    qscopes.add_argument("--project", required=True)
    qscopes.add_argument("--input", required=True)
    qscopes.add_argument("--at-seconds", type=float, default=0.0)
    qscopes.add_argument("--output-dir", default=None, help="项目内 scope 输出目录；默认 cache/scopes/<scope_id>")
    qgolden = _leaf_common(qs.add_parser("golden", help="捕获或验证固定本地质量 golden 清单"))
    qgolden.add_argument("--project", required=True)
    qgolden.add_argument("--input", required=True, help="待捕获或验证的本地媒体")
    qgolden.add_argument("--mode", choices=("capture", "verify"), default="verify")
    qgolden.add_argument("--manifest", default=None, help="项目内 golden JSON；默认 validation/golden-quality.json")
    qgolden.add_argument("--sequence-id", default=None)
    qgolden.add_argument("--require-audio", action=argparse.BooleanOptionalAction, default=None)
    qgolden.add_argument("--expensive", action=argparse.BooleanOptionalAction, default=None, help="运行黑帧和响度扫描；verify 默认沿用清单")
    qgolden.add_argument("--max-av-sync-ms", type=float, default=None)
    qgolden.add_argument("--target-lufs", type=float, default=None)
    qgolden.add_argument("--lufs-tolerance", type=float, default=None)
    qgolden.add_argument("--fail-on-black", action=argparse.BooleanOptionalAction, default=None)
    qgolden.add_argument("--max-true-peak-dbfs", type=float, default=None)
    qgolden.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None)
    qgolden.add_argument("--width", type=int, default=None)
    qgolden.add_argument("--height", type=int, default=None)

    convert = subs.add_parser("convert", help="项目/交换格式互操作")
    cs = convert.add_subparsers(dest="action", required=True)
    cimport = _leaf_common(cs.add_parser("import", help="导入 Agent JSON、OTIO 或 Kdenlive XML"))
    cimport.add_argument("--input", required=True)
    cimport.add_argument("--output", required=True, help="新项目目录")
    cexport = _leaf_common(cs.add_parser("export", help="导出 Agent Project JSON"))
    cexport.add_argument("--project", required=True)
    cexport.add_argument("--output", required=True)
    cexport.add_argument("--target-format", choices=("agent-json", "otio", "kdenlive-xml"), default="agent-json")

    template = subs.add_parser("template", help="模板实例化")
    ts2 = template.add_subparsers(dest="action", required=True)
    apply_template = _leaf_common(ts2.add_parser("apply", help="应用本地模板 JSON"))
    apply_template.add_argument("--project", required=True)
    apply_template.add_argument("--input", required=True)
    apply_template.add_argument("--variables", default=None, help="变量 JSON 文件")
    batch_template = _leaf_common(ts2.add_parser("batch", help="批量实例化并本地渲染模板"))
    batch_template.add_argument("--project", required=True)
    batch_template.add_argument("--input", required=True, help="模板 JSON 文件")
    batch_template.add_argument("--variables", required=True, help="variants JSON 文件")
    batch_template.add_argument("--output", required=True, help="项目内批量输出目录")
    batch_template.add_argument("--publish", action="store_true")
    batch_template.add_argument("--continue-on-error", action="store_true")

    library = subs.add_parser("library", help="本地素材与模板资产索引")
    ls = library.add_subparsers(dest="action", required=True)
    lindex = _leaf_common(ls.add_parser("index", help="索引本地媒体/字幕/字体"))
    lindex.add_argument("--root", required=True)
    lindex.add_argument("--output", required=True)
    lindex.add_argument("--max-files", type=int, default=5000)
    lindex.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    lindex.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    lindex.add_argument("--previous", default=None, help="上一版本地目录 JSON，用于增量刷新")
    lindex.add_argument("--incremental", action="store_true", help="按文件 stat 与字幕侧车签名复用未变化记录")
    lindex.add_argument("--visual-hash", action="store_true", help="通过本地 FFmpeg 生成候选感知哈希样本")
    lsearch = _leaf_common(ls.add_parser("search", help="查询本地资产索引"))
    lsearch.add_argument("--catalog", required=True)
    lsearch.add_argument("--query", default="")
    lsearch.add_argument("--kind", default=None)
    lsearch.add_argument("--verification-status", default=None)
    lsearch.add_argument("--min-duration", type=float, default=None)
    lsearch.add_argument("--max-duration", type=float, default=None)
    lsearch.add_argument("--min-width", type=int, default=None)
    lsearch.add_argument("--min-height", type=int, default=None)
    lsearch.add_argument("--has-audio", action=argparse.BooleanOptionalAction, default=None, help="按是否含音频流过滤")
    lsearch.add_argument("--duplicate-only", action="store_true", help="只返回精确内容重复组中的记录")
    lsearch.add_argument("--limit", type=int, default=50)
    lduplicates = _leaf_common(ls.add_parser("duplicates", help="按 SHA-256 列出精确重复素材组"))
    lduplicates.add_argument("--catalog", required=True)
    lduplicates.add_argument("--include-unique", action="store_true", help="同时返回只有一个成员的哈希组")
    lsimilar = _leaf_common(ls.add_parser("similar", help="按可选 FFmpeg 感知哈希列出相似画面候选组"))
    lsimilar.add_argument("--catalog", required=True)
    lsimilar.add_argument("--max-distance", type=int, default=12, help="平均哈希汉明距离上限")

    lut = subs.add_parser("lut", help="项目内本地 LUT 资产库")
    luts = lut.add_subparsers(dest="action", required=True)
    lut_register = _leaf_common(luts.add_parser("register", help="登记并复制本地 LUT 到项目资产库"))
    lut_register.add_argument("--project", required=True)
    lut_register.add_argument("--input", required=True, help="本地 .cube/.3dl/.csp/.dat 文件")
    lut_register.add_argument("--lut-id", default=None, help="稳定 LUT ID；默认由 SHA-256 派生")
    lut_register.add_argument("--name", default=None)
    lut_register.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    lut_register.add_argument("--license-url", default="")
    lut_register.add_argument("--permitted-use", action="append", default=["internal"])
    lut_register.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    lut_register.add_argument("--evidence", default="")
    lut_register.add_argument("--creator", default="unknown")
    lut_list = _leaf_common(luts.add_parser("list", help="列出项目内已登记 LUT"))
    lut_list.add_argument("--project", required=True)
    lut_list.add_argument("--query", default=None)
    lut_inspect = _leaf_common(luts.add_parser("inspect", help="检查 LUT 文件、哈希和元数据"))
    lut_inspect.add_argument("--project", required=True)
    lut_inspect.add_argument("--lut-id", required=True)

    doctor = _leaf_common(subs.add_parser("doctor", help="检查本机依赖"))
    doctor.add_argument("--project", default=None)
    operation = _leaf_common(subs.add_parser("operation", help="查看操作状态"))
    osub = operation.add_subparsers(dest="action", required=True)
    opinspect = _leaf_common(osub.add_parser("inspect", help="读取操作记录"))
    opinspect.add_argument("--project", required=True)
    opinspect.add_argument("--operation-id", required=True)
    _leaf_common(subs.add_parser("version", help="版本信息"))
    _leaf_common(subs.add_parser("capabilities", help="输出本地 Agent 能力清单"))
    policy = subs.add_parser("policy", help="本地运行策略")
    policy_sub = policy.add_subparsers(dest="action", required=True)
    policy_audit = _leaf_common(policy_sub.add_parser("audit", help="审计项目产物中的远程/闭源引用"))
    policy_audit.add_argument("--project", required=True)
    return parser


def _envelope(command: str, args: argparse.Namespace, *, data: Any = None, status: str = "succeeded", warnings: list[Any] | None = None, errors: list[Any] | None = None, operation_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": status == "succeeded" or status == "planned",
        "command": command,
        "request_id": args.request_id or new_id("req"),
        "operation_id": operation_id,
        "status": status,
        "data": data if data is not None else {},
        "artifacts": [],
        "warnings": warnings or [],
        "errors": errors or [],
        "provenance": {"cli_version": VERSION, "schema_version": SCHEMA_VERSION, "engine_version": ENGINE_ID, "started_at": now_iso(), "finished_at": now_iso(), "network": "disabled"},
    }


def _print(value: dict[str, Any], fmt: str = "json") -> None:
    if fmt == "text":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _command_name(args: argparse.Namespace) -> str:
    action = getattr(args, "action", None)
    return f"{args.domain}.{action}" if action else str(args.domain)


def _operation(root: Path, operation_id: str, payload: dict[str, Any]) -> None:
    atomic_write_json(root / "operations" / f"{operation_id}.json", payload)


def _progress(args: argparse.Namespace, operation_id: str, event_type: str, stage: str, percent: float | None, message: str, *, error: Any = None) -> None:
    if getattr(args, "progress", "none") != "jsonl":
        return
    event = {"event_id": new_id("event"), "operation_id": operation_id, "type": event_type, "at": now_iso(), "stage": stage, "percent": percent, "message": message, "artifacts": []}
    if error is not None:
        event["error"] = error
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), file=sys.stderr)


def _load_changes(path: str) -> dict[str, Any]:
    value = load_json(Path(path))
    if not isinstance(value, dict):
        raise argument_error("变更集必须是 JSON 对象")
    return value


def command_project_init(args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run:
        root = Path(args.path).expanduser().resolve()
        return _envelope("project.init", args, status="planned", data={"root": str(root), "name": args.name or root.name, "project_id": args.project_id or "generated-at-apply"})
    root, project = create_project(args.path, args.name, args.project_id)
    return _envelope("project.init", args, data={"project": str(project_file(root)), "root": str(root), "project_id": project["project"]["id"]})


def command_project_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    report = validate_project(root, project, strict_rights=False)
    return _envelope("project.inspect", args, data={"root": str(root), "project": project["project"], "assets": len(project.get("assets", [])), "sequences": len(project.get("sequences", [])), "validation": report})


def command_project_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.dry_run:
        return _envelope("project.snapshot", args, status="planned", data={"project": str(root), "label": args.label, "history": str(history_dir(root))})
    snapshot = create_snapshot(root, project, label=args.label)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.snapshot", "status": "succeeded", **snapshot})
    return _envelope("project.snapshot", args, data=snapshot, operation_id=operation_id)


def command_project_restore(args: argparse.Namespace) -> dict[str, Any]:
    root, current = load_project(args.project)
    requested = Path(args.snapshot).expanduser()
    if not requested.is_absolute() and requested.suffix.lower() == ".json":
        project_relative = (root / requested).resolve()
        history_relative = (history_dir(root) / requested.name).resolve()
        if project_relative.exists():
            requested = project_relative
        elif history_relative.exists():
            requested = history_relative
    if requested.suffix.lower() == ".json" and requested.exists():
        try:
            requested.resolve().relative_to(history_dir(root).resolve())
        except ValueError as exc:
            raise argument_error("快照路径必须位于项目 history 目录内", str(requested)) from exc
        snapshot_id = requested.stem
    else:
        snapshot_id = str(args.snapshot)
    payload = load_snapshot(root, snapshot_id)
    candidate = payload.get("project")
    if not isinstance(candidate, dict):
        raise AppError("SNAPSHOT_INVALID", "快照 project 字段无效", exit_code=2, path=f"{snapshot_id}.project")
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation["ok"]:
        raise AppError("SNAPSHOT_PROJECT_INVALID", "快照恢复前校验失败，拒绝覆盖当前项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("project.restore", args, status="planned", data={"snapshot_id": snapshot_id, "project_id": candidate.get("project", {}).get("id"), "validation": validation})
    backup = create_snapshot(root, current, label="before-restore")
    restored = restore_snapshot(root, payload)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.restore", "status": "succeeded", "snapshot_id": snapshot_id, "backup_snapshot_id": backup["snapshot_id"], "created_at": now_iso()})
    return _envelope("project.restore", args, data={"snapshot_id": snapshot_id, "backup": backup, **restored, "validation": validation}, operation_id=operation_id)


def command_project_migrate(args: argparse.Namespace) -> dict[str, Any]:
    root, current = load_project(args.project)
    if not isinstance(current.get("schema_version"), str) or current["schema_version"] not in SUPPORTED_SOURCE_VERSIONS:
        raise AppError("SCHEMA_VERSION_UNSUPPORTED", "迁移仅支持本项目 schema 0.0.0 和 0.1.0；未知格式须使用显式转换器", exit_code=2, path="schema_version")
    if args.report:
        requested_report = Path(args.report).expanduser()
        report_path = (root / "validation" / requested_report if not requested_report.is_absolute() else requested_report).resolve()
    else:
        report_path = root / "validation" / f"migration_{new_id('report')}.json"
    ensure_inside(root / "validation", report_path)
    if report_path.suffix.lower() != ".json":
        raise argument_error("迁移报告必须使用 validation 目录内的 JSON 文件", str(report_path))
    metadata: dict[str, dict[str, Any]] = {}
    for asset in current.get("assets", []):
        if not isinstance(asset, dict):
            continue
        if asset.get("sha256") and "probe" in asset:
            continue
        uri = asset.get("uri")
        if not isinstance(uri, str) or not uri or "://" in uri:
            raise AppError("MIGRATION_ASSET_URI_MISSING", "迁移资产必须包含本地文件 uri", exit_code=2, path="assets[].uri")
        source = Path(uri)
        if not source.is_absolute():
            source = root / source
        extensions = asset.get("extensions") if isinstance(asset.get("extensions"), dict) else {}
        source = ensure_inside(root, source, allow_external=bool(extensions.get("external_authorized")))
        if not source.is_file():
            raise AppError("MIGRATION_ASSET_HASH_MISSING", "资产缺少元数据且本地文件不存在，拒绝猜测内容指纹", exit_code=3, path=str(source))
        supplied: dict[str, Any] = {}
        if not asset.get("sha256"):
            supplied["sha256"] = f"sha256:{sha256_file(source)}"
        if "probe" not in asset:
            supplied["probe"] = probe_media(source)
        metadata[str(asset.get("id"))] = supplied
    candidate, migration = migrate_project_payload(current, timestamp=now_iso(), asset_metadata=metadata)
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation["ok"]:
        raise AppError(
            "MIGRATION_PROJECT_INVALID",
            "迁移候选项目校验失败，拒绝覆盖原项目",
            exit_code=2,
            path=str(project_file(root)),
            cause=json.dumps(validation, ensure_ascii=False),
        )
    if args.dry_run:
        return _envelope("project.migrate", args, status="planned", data={"project": str(root), "migration": migration, "validation": validation})
    backup: dict[str, Any] | None = None
    operation_id = new_id("op")
    if migration["changed"]:
        backup = create_snapshot(root, current, label="before-migrate")
        save_project(root, candidate)
    report_payload = {
        **migration,
        "created_at": now_iso(),
        "project_id": candidate.get("project", {}).get("id"),
        "operation_id": operation_id,
        "backup_snapshot_id": backup.get("snapshot_id") if backup else None,
        "validation": validation,
    }
    atomic_write_json(report_path, report_payload)
    status = "succeeded"
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.migrate", "status": status, "changed": migration["changed"], "report": str(report_path), "backup_snapshot_id": report_payload["backup_snapshot_id"], "created_at": now_iso()})
    return _envelope("project.migrate", args, data={"migration": migration, "report": str(report_path), "backup": backup, "validation": validation}, operation_id=operation_id)


def command_project_recover(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    journal = root / "operations" / "project-transaction.json"
    if args.dry_run:
        return _envelope("project.recover", args, status="planned", data={"project": str(root), "journal": str(journal), "pending": journal.exists()})
    recovery = recover_pending_transaction(root)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.recover", "status": "succeeded", "recovery": recovery, "created_at": now_iso()})
    return _envelope("project.recover", args, data={"project": str(root), "recovery": recovery}, operation_id=operation_id)


def command_media_ingest(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source = Path(args.input).expanduser().resolve()
    if source.as_uri().startswith("http") or not source.exists() or not source.is_file():
        raise argument_error("--input 必须是存在的本地文件", str(source))
    asset_id = args.asset_id or new_id("asset")
    if asset_id in asset_map(project):
        raise argument_error(f"资产 ID 已存在: {asset_id}", "--asset-id")
    probe = probe_media(source)
    kind = classify_path(source, probe)
    destination = root / "assets" / f"{asset_id}_{safe_filename(source.name)}"
    if not args.dry_run:
        shutil.copy2(source, destination)
    digest = sha256_file(source)
    uri = str(destination.relative_to(root)).replace("\\", "/")
    source_reference = require_local_reference(args.source_url or f"local://{source}", field="--source-url")
    license_reference = require_local_reference(args.license_url, field="--license-url") if args.license_url else ""
    evidence_reference = require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else f"local://{source}")
    asset = {"id": asset_id, "kind": kind, "uri": uri, "sha256": f"sha256:{digest}", "probe": probe, "rights_ref": asset_id, "source": {"source_url": source_reference, "retrieved_at": now_iso(), "original_name": source.name}}
    record = {"asset_id": asset_id, "kind": kind, "sha256": f"sha256:{digest}", "source_url": source_reference, "source_version": "local", "retrieved_at": now_iso(), "creator": args.creator, "license_spdx": args.license_spdx, "license_url": license_reference, "attribution": "", "permitted_uses": list(dict.fromkeys(args.permitted_use)), "restrictions": [], "evidence": evidence_reference, "verification_status": args.verification_status, "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "", "takedown_status": "clear", "notes": "Imported by local CLI"}
    if args.dry_run:
        return _envelope("media.ingest", args, status="planned", data={"asset": asset, "rights_record": record})
    project.setdefault("assets", []).append(asset)
    ledger = load_ledger(root)
    add_record(ledger, record)
    operation_id = new_id("op")
    _progress(args, operation_id, "started", "media.ingest", 0, "开始导入本地素材")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.ingest", "asset_id": asset_id, "at": now_iso()})
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.ingest", "status": "succeeded", "asset_id": asset_id, "sha256": digest, "created_at": now_iso()})
    _progress(args, operation_id, "completed", "media.ingest", 100, "素材导入完成")
    return _envelope("media.ingest", args, data={"asset": asset, "rights": record, "path": str(destination)}, operation_id=operation_id)


def command_media_stabilize(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    source_asset: dict[str, Any] | None = None
    parent_rights_ref: str | None = None
    if args.asset_id:
        source_asset = asset_map(project).get(str(args.asset_id))
        if not source_asset:
            raise argument_error(f"找不到资产: {args.asset_id}", "--asset-id")
        source = Path(str(source_asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
        parent_rights_ref = str(source_asset.get("rights_ref") or source_asset.get("id"))
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("--input 只接受本地视频文件", "--input")
        source = Path(raw_input).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("防抖输入不存在", str(source))
    derived_id = str(args.derived_asset_id or new_id("asset_stabilized"))
    if derived_id in asset_map(project):
        raise argument_error(f"派生资产 ID 已存在: {derived_id}", "--derived-asset-id")
    output = Path(args.output).expanduser() if args.output else Path("assets") / "derived" / f"stabilized_{safe_filename(derived_id)}.mp4"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    ensure_inside(root, output)
    if output.exists():
        raise argument_error("防抖输出已存在，为避免覆盖请指定新的 --output", str(output))
    parameters = {
        "shakiness": args.shakiness, "accuracy": args.accuracy, "stepsize": args.stepsize,
        "mincontrast": args.mincontrast, "smoothing": args.smoothing, "maxshift": args.maxshift,
        "maxangle": args.maxangle, "crop": args.crop, "optzoom": args.optzoom,
        "zoom": args.zoom, "interpol": args.interpol,
    }
    transform_dir = root / "cache" / "stabilization" / safe_filename(derived_id)
    if args.dry_run:
        return _envelope(
            "media.stabilize",
            args,
            status="planned",
            data={"input": str(source), "asset_id": args.asset_id, "derived_asset_id": derived_id, "output": str(output), "transform_dir": str(transform_dir), "parameters": parameters, "engine": "ffmpeg-local:vidstabdetect+vidstabtransform"},
        )
    snapshot = create_snapshot(root, project, label="before-stabilize")
    operation_id = new_id("op")
    _progress(args, operation_id, "started", "media.stabilize.detect", 0, "开始本地 vidstabdetect 分析")
    try:
        stabilization = stabilize_media(source, output, transform_dir, **parameters)
        _progress(args, operation_id, "progress", "media.stabilize.transform", 70, "完成运动轨迹分析，开始 vidstabtransform 输出")
        digest = str(stabilization["output_sha256"])
        if source_asset is not None:
            ledger = load_ledger(root)
            parent_records = {str(item.get("asset_id")): item for item in active_records(ledger)}
            parent_record = parent_records.get(parent_rights_ref or "")
            if parent_record is None:
                raise AppError("RIGHTS_RECORD_MISSING", "源资产缺少可继承的 Rights Ledger 记录", exit_code=7, path=parent_rights_ref)
            rights_source_url = f"local://{output}"
            record = {
                "asset_id": derived_id, "kind": "video", "sha256": digest, "source_url": rights_source_url,
                "source_version": "derived:vidstab", "retrieved_at": now_iso(), "creator": parent_record.get("creator", "unknown"),
                "license_spdx": parent_record.get("license_spdx", "LicenseRef-UNVERIFIED"), "license_url": parent_record.get("license_url", ""),
                "attribution": parent_record.get("attribution", ""), "permitted_uses": list(parent_record.get("permitted_uses", ["internal"])),
                "permitted_channels": list(parent_record.get("permitted_channels", [])), "restrictions": list(parent_record.get("restrictions", [])),
                "derived_from": [parent_rights_ref], "evidence": parent_record.get("evidence", ""),
                "verification_status": parent_record.get("verification_status", "unverified"), "verified_by": parent_record.get("verified_by", ""),
                "takedown_status": parent_record.get("takedown_status", "clear"), "notes": "Derived by local FFmpeg vidstab; inherits source rights",
            }
        else:
            rights_source_url = require_local_reference(args.source_url or f"local://{source}", field="--source-url")
            evidence_reference = require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else f"local://{output}")
            record = {
                "asset_id": derived_id, "kind": "video", "sha256": digest, "source_url": rights_source_url,
                "source_version": "derived:vidstab", "retrieved_at": now_iso(), "creator": args.creator,
                "license_spdx": args.license_spdx, "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
                "attribution": "", "permitted_uses": list(dict.fromkeys(args.permitted_use)), "permitted_channels": [],
                "restrictions": [], "derived_from": [], "evidence": evidence_reference, "verification_status": args.verification_status,
                "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "", "takedown_status": "clear",
                "notes": "Derived by local FFmpeg vidstab",
            }
        asset = {
            "id": derived_id, "kind": "video", "uri": str(output.relative_to(root)).replace("\\", "/"),
            "sha256": digest, "probe": stabilization["probe"], "rights_ref": derived_id,
            "source": {"source_url": rights_source_url, "retrieved_at": now_iso(), "original_name": output.name, "derived_from": [source_asset.get("id")] if source_asset else []},
        }
        report_path = root / "validation" / f"stabilization_{safe_filename(operation_id)}.json"
        report = {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "operation_id": operation_id, "snapshot_id": snapshot["snapshot_id"], "asset_id": derived_id, "parent_asset_id": source_asset.get("id") if source_asset else None, "stabilization": stabilization, "rights_dependency": parent_rights_ref}
        atomic_write_json(report_path, report)
        project.setdefault("assets", []).append(asset)
        ledger = load_ledger(root)
        add_record(ledger, record)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.stabilize", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "at": now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "media.stabilize", "status": "succeeded", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "created_at": now_iso()})
        _progress(args, operation_id, "completed", "media.stabilize", 100, "本地防抖派生素材完成")
        return _envelope("media.stabilize", args, data={"asset": asset, "rights": record, "snapshot": snapshot, "report": str(report_path), "stabilization": stabilization}, operation_id=operation_id)
    except Exception:
        if output.exists():
            try:
                output.unlink()
            except OSError:
                pass
        raise


def command_media_relink(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    search_root = Path(args.search_root).expanduser().resolve()
    if args.dry_run:
        return _envelope("media.relink", args, status="planned", data={"project": str(root), "search_root": str(search_root), "match_by_name": bool(args.match_by_name)})
    result = relink_missing_assets(root, project, search_root, match_by_name=args.match_by_name)
    report_path = root / "validation" / f"relink_{new_id('report')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **result})
    if result["relinked"]:
        ledger = load_ledger(root)
        by_asset = {str(record.get("asset_id")): record for record in ledger.get("records", [])}
        for entry in result["entries"]:
            if entry.get("status") in {"Exact", "Approximate"} and entry.get("asset_id") in by_asset:
                record = by_asset[str(entry["asset_id"])]
                record["sha256"] = entry.get("sha256")
        save_ledger(root, ledger)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "media.relink", "report": str(report_path), "at": now_iso(), "relinked": result["relinked"]})
        save_project(root, project)
    operation_id = new_id("op")
    status = "succeeded" if not any(item.get("status") == "Failed" for item in result["entries"]) else "failed"
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.relink", "status": status, "report": str(report_path), "relinked": result["relinked"], "created_at": now_iso()})
    return _envelope("media.relink", args, data={**result, "report": str(report_path)}, status=status, errors=[item for item in result["entries"] if item.get("status") == "Failed"], operation_id=operation_id)


def command_media_track(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    source: Path
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        source = Path(str(args.input)).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("跟踪输入不存在", str(source))
    sequence_id = args.sequence_id
    if args.clip_id:
        sequence = find_sequence(project, sequence_id)
        _find_clip(sequence, str(args.clip_id), args.track_id)
    if args.dry_run:
        return _envelope(
            "media.track",
            args,
            status="planned",
            data={
                "input": str(source),
                "asset_id": asset_id,
                "roi": args.roi,
                "clip_id": args.clip_id,
                "sequence_id": sequence_id,
                "step_frames": args.step_frames,
            },
        )
    report = track_media(
        source,
        args.roi,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        step_frames=args.step_frames,
        search_radius=args.search_radius,
        max_width=args.max_width,
        max_samples=args.max_samples,
        ticks_per_second=int(project["settings"]["timebase"]["ticks_per_second"]),
    )
    report["source_sha256"] = f"sha256:{sha256_file(source)}"
    report["asset_id"] = asset_id
    report["clip_id"] = args.clip_id
    report["sequence_id"] = sequence_id
    report_path = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"tracking_{new_id('run')}.json"
    try:
        report_path.relative_to(root)
    except ValueError as exc:
        raise argument_error("跟踪报告必须位于项目目录内", str(report_path)) from exc
    before_snapshot: dict[str, Any] | None = None
    operation_id = new_id("op")
    applied_properties: list[str] = []
    if args.clip_id:
        target_sequence = find_sequence(project, sequence_id)
        _, clip = _find_clip(target_sequence, str(args.clip_id), args.track_id)
        before_snapshot = create_snapshot(root, project, label="before-track-apply")
        for item in report.get("keyframes", []):
            if not isinstance(item, dict) or not isinstance(item.get("keyframes"), list):
                continue
            values: list[tuple[int, float, str]] = []
            for point in item["keyframes"]:
                if not isinstance(point, dict):
                    continue
                try:
                    values.append((int(point.get("at_tick", 0)), float(point.get("value", 0.0)), str(point.get("interpolation", "linear"))))
                except (TypeError, ValueError):
                    continue
            if values:
                _set_keyframe_track(clip, str(item.get("property")), values)
                applied_properties.append(str(item.get("property")))
        _clamp_clip_keyframes(clip)
        validation = validate_project(root, project, strict_rights=False)
        if not validation["ok"]:
            raise AppError("TRACK_APPLY_INVALID", "对象跟踪关键帧应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.track", "asset_id": asset_id, "clip_id": args.clip_id, "report": str(report_path), "at": now_iso()})
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **report})
    if args.clip_id:
        save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.track", "status": "succeeded", "report": str(report_path), "asset_id": asset_id, "clip_id": args.clip_id, "applied_properties": applied_properties, "before_snapshot": before_snapshot, "created_at": now_iso()})
    return _envelope("media.track", args, data={"report": str(report_path), "result": report, "applied_properties": applied_properties, "before_snapshot": before_snapshot}, warnings=[{"code": "TRACKING_APPROXIMATE", "message": "本地模板匹配可能在遮挡、缩放或镜头切换时漂移；请检查 confidence 和关键帧"}], operation_id=operation_id)


def command_media_reframe(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    sequence = find_sequence(project, args.sequence_id)
    _, clip = _find_clip(sequence, str(args.clip_id), args.track_id)
    if clip.get("sequence_id"):
        raise AppError("REFRAME_NESTED_UNSUPPORTED", "自动重构图当前只支持直接媒体片段", exit_code=2, path="clip_id")
    try:
        speed = float(clip.get("speed", 1.0))
    except (TypeError, ValueError) as exc:
        raise AppError("REFRAME_SPEED_UNSUPPORTED", "自动重构图无法解析片段 speed", exit_code=2, path="clip.speed") from exc
    if abs(speed - 1.0) > 1e-6 or bool(clip.get("reverse")) or clip.get("speed_curve") is not None:
        raise AppError("REFRAME_TIME_MAPPING_UNSUPPORTED", "自动重构图当前要求常速正向片段，请先烘焙变速或倒放", exit_code=2, path="clip.speed")
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        source = Path(str(args.input)).expanduser().resolve()
        asset = None
    if not source.exists() or not source.is_file():
        raise argument_error("自动重构图输入不存在", str(source))
    tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90_000))
    clip_source_in = int(clip.get("source_in_tick", 0))
    clip_source_out = int(clip.get("source_out_tick", clip_source_in + int(clip.get("duration_tick", 1))))
    start_seconds = clip_source_in / max(1, tps) if args.start_seconds is None else max(0.0, float(args.start_seconds))
    end_seconds = clip_source_out / max(1, tps) if args.end_seconds is None else args.end_seconds
    if end_seconds is not None and end_seconds <= start_seconds:
        raise argument_error("自动重构图 end_seconds 必须大于 start_seconds", "--end-seconds")
    probe = probe_media(source)
    video = probe.get("video") if isinstance(probe.get("video"), dict) else {}
    source_width = int(video.get("width", 0) or 0)
    source_height = int(video.get("height", 0) or 0)
    if source_width <= 0 or source_height <= 0:
        raise AppError("REFRAME_VIDEO_MISSING", "自动重构图需要视频流", exit_code=4, path="input")
    canvas = project.get("settings", {}).get("canvas") if isinstance(project.get("settings", {}).get("canvas"), dict) else {}
    target_width = int(args.target_width or canvas.get("width", 1080))
    target_height = int(args.target_height or canvas.get("height", 1920))
    target_aspect = float(args.target_aspect or (target_width / max(1, target_height)))
    if target_width <= 0 or target_height <= 0:
        raise argument_error("目标画布尺寸必须大于 0", "target_width")
    if args.dry_run:
        return _envelope("media.reframe", args, status="planned", data={"input": str(source), "asset_id": asset_id, "clip_id": args.clip_id, "track_id": args.track_id, "sequence_id": sequence.get("id"), "target_width": target_width, "target_height": target_height, "target_aspect": target_aspect, "margin": args.margin, "fit": args.fit, "start_seconds": start_seconds, "end_seconds": end_seconds})
    tracking = track_media(
        source,
        args.roi,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        step_frames=args.step_frames,
        search_radius=args.search_radius,
        max_width=args.max_width,
        max_samples=args.max_samples,
        ticks_per_second=tps,
    )
    plan = build_reframe_plan(
        tracking.get("frames", []),
        source_aspect=source_width / source_height,
        target_aspect=target_aspect,
        margin=args.margin,
        fit=args.fit,
    )
    plan.update({"project_id": project.get("project", {}).get("id"), "sequence_id": sequence.get("id"), "asset_id": asset_id, "clip_id": args.clip_id, "track_id": args.track_id, "source": str(source), "source_sha256": f"sha256:{sha256_file(source)}", "source_range": {"start_seconds": start_seconds, "end_seconds": end_seconds}, "tracking": tracking})
    report_path = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"reframe_{safe_filename(str(args.clip_id))}.json"
    ensure_inside(root, report_path)
    if not args.apply:
        atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": False, "plan": plan})
        return _envelope("media.reframe", args, status="planned", data={"report": str(report_path), "plan": plan, "applied": False}, warnings=[{"code": "REFRAME_APPROXIMATE", "message": "自动重构图使用本地模板跟踪；请检查 confidence 和裁切范围"}],)
    before_project = copy.deepcopy(project)
    before_snapshot = create_snapshot(root, before_project, label="before-reframe")
    clip["crop"] = copy.deepcopy(plan["crop"])
    for track in plan["keyframes"]:
        values = [(int(item["at_tick"]), float(item["value"]), str(item.get("interpolation", "linear"))) for item in track["keyframes"]]
        _set_keyframe_track(clip, str(track["property"]), values)
    _clamp_clip_keyframes(clip)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("REFRAME_APPLY_INVALID", "自动重构图应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    operation_id = new_id("op")
    plan["applied_properties"] = [str(item["property"]) for item in plan["keyframes"]]
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": True, "operation_id": operation_id, "before_snapshot_id": before_snapshot["snapshot_id"], "plan": plan, "validation": validation})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.reframe", "clip_id": args.clip_id, "track_id": args.track_id, "report": str(report_path), "before_snapshot_id": before_snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.reframe", "status": "succeeded", "clip_id": args.clip_id, "track_id": args.track_id, "report": str(report_path), "before_snapshot_id": before_snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("media.reframe", args, data={"report": str(report_path), "plan": plan, "before_snapshot": before_snapshot, "validation": validation}, warnings=[{"code": "REFRAME_APPROXIMATE", "message": "自动重构图使用本地模板跟踪；请检查 confidence、主体边界和裁切警告"}], operation_id=operation_id)


def command_media_understand(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source: Path | None = None
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    assert source is not None
    if not source.exists():
        raise argument_error("分析输入不存在", str(source))
    if args.dry_run:
        return _envelope("media.understand", args, status="planned", data={"input": str(source), "scene_threshold": args.scene_threshold})
    analysis = understand_media(source, scene_threshold=args.scene_threshold, include_beats=args.beats)
    if args.transcribe:
        analysis["transcription"] = transcribe_local(source, model_path=args.model_path, language=args.language)
        if args.srt:
            srt_path = Path(args.srt).expanduser()
            if not srt_path.is_absolute():
                srt_path = root / srt_path
            srt_path = srt_path.resolve()
            try:
                srt_path.relative_to(root)
            except ValueError as exc:
                raise argument_error("SRT 输出必须位于项目目录内", str(srt_path)) from exc
            write_srt(analysis["transcription"], srt_path)
            analysis["transcription"]["srt"] = str(srt_path)
    analysis["source_sha256"] = f"sha256:{sha256_file(source)}"
    analysis["asset_id"] = asset_id
    path = root / "validation" / f"understand_{asset_id or new_id('asset')}.json"
    atomic_write_json(path, analysis)
    return _envelope("media.understand", args, data={"analysis": str(path), "result": analysis})


def command_media_prepare(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset_id = args.asset_id
    source: Path | None = None
    asset: dict[str, Any] | None = None
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    assert source is not None
    if not source.exists() or not source.is_file():
        raise argument_error("准备输入不存在", str(source))
    if asset is None:
        asset = {"id": source.stem, "kind": classify_path(source), "uri": str(source)}
    kind = str(asset.get("kind", classify_path(source)))
    proxy_width = int(args.proxy_width or 0)
    make_thumbnail = bool(args.thumbnail)
    make_waveform = bool(args.waveform)
    if not proxy_width and not make_thumbnail and not make_waveform:
        proxy_width = 720 if kind == "video" else 0
        make_thumbnail = kind in {"video", "image"}
        make_waveform = kind in {"video", "audio"}
    if args.dry_run:
        return _envelope("media.prepare", args, status="planned", data={"asset_id": asset_id, "input": str(source), "proxy_width": proxy_width, "thumbnail": make_thumbnail, "waveform": make_waveform})
    artifacts: dict[str, Any] = {"asset_id": asset_id, "input": str(source)}
    if proxy_width:
        proxy_path = root / "cache" / "proxies" / f"{asset.get('id', source.stem)}_{proxy_width}.mp4"
        generate_proxy(source, proxy_path, width=proxy_width)
        artifacts["proxy"] = str(proxy_path)
        if asset_id:
            asset["proxy"] = {"uri": str(proxy_path.relative_to(root)).replace("\\", "/"), "width": proxy_width, "sha256": f"sha256:{sha256_file(proxy_path)}"}
    if make_thumbnail:
        thumbnail_path = root / "cache" / "thumbnails" / f"{asset.get('id', source.stem)}.jpg"
        generate_thumbnail(source, thumbnail_path, at_seconds=args.at_seconds)
        artifacts["thumbnail"] = str(thumbnail_path)
        if asset_id:
            asset["thumbnail"] = {"uri": str(thumbnail_path.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{sha256_file(thumbnail_path)}", "at_seconds": max(0.0, args.at_seconds)}
    if make_waveform:
        waveform_path = root / "cache" / "waveforms" / f"{asset.get('id', source.stem)}.png"
        generate_waveform(source, waveform_path)
        artifacts["waveform"] = str(waveform_path)
        if asset_id:
            asset["waveform"] = {"uri": str(waveform_path.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{sha256_file(waveform_path)}"}
    operation_id = new_id("op")
    if asset_id:
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.prepare", "asset_id": asset_id, "artifacts": artifacts, "at": now_iso()})
        save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.prepare", "status": "succeeded", "artifacts": artifacts, "created_at": now_iso()})
    return _envelope("media.prepare", args, data=artifacts, operation_id=operation_id)


def command_media_highlights(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    if not source.exists() or not source.is_file():
        raise argument_error("高光分析输入不存在", str(source))
    if args.dry_run:
        return _envelope("media.highlights", args, status="planned", data={"input": str(source), "top_k": args.top_k, "min_duration": args.min_duration, "max_duration": args.max_duration, "beats": bool(args.beats)})
    analysis = understand_media(source, include_beats=args.beats)
    recommendation = recommend_highlights(analysis, top_k=args.top_k, min_duration=args.min_duration, max_duration=args.max_duration)
    recommendation.update({"asset_id": asset_id, "source": str(source), "source_sha256": f"sha256:{sha256_file(source)}", "analysis": analysis})
    output: Path
    if args.output:
        output = Path(args.output).expanduser().resolve()
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise argument_error("高光报告必须位于项目目录内", str(output)) from exc
    else:
        output = root / "validation" / f"highlights_{asset_id or new_id('asset')}.json"
    atomic_write_json(output, recommendation)
    return _envelope("media.highlights", args, data={"report": str(output), "recommendation": recommendation})


def command_media_beat_cut(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, getattr(args, "sequence_id", None))
    target_track = find_track(sequence, args.track_id, None)
    if str(target_track.get("kind")) != "video":
        raise argument_error("按节拍剪辑目标轨道必须是 video 轨道", "track_id")
    if args.timeline_start_seconds < 0:
        raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
    assets = asset_map(project)
    source_assets: list[dict[str, Any]] = []
    for asset_id in args.source_asset_id:
        asset = assets.get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到源视频资产: {asset_id}", "source_asset_id")
        if str(asset.get("kind", "")).lower() != "video":
            raise argument_error(f"按节拍剪辑源素材必须是 video 资产: {asset_id}", "source_asset_id")
        source_assets.append(asset)

    audio_asset_id = args.audio_asset_id
    if audio_asset_id:
        audio_asset = assets.get(str(audio_asset_id))
        if not audio_asset:
            raise argument_error(f"找不到节拍分析资产: {audio_asset_id}", "audio_asset_id")
        source = Path(str(audio_asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("--input 只接受本地音频或视频文件", "input")
        source = Path(raw_input).expanduser().resolve()
        audio_asset = None
    if not source.exists() or not source.is_file():
        raise argument_error("节拍分析输入不存在", str(source))

    timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90_000))
    run_id = new_id("beatcut")
    report_path = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"beat_cut_{safe_filename(run_id)}.json"
    ensure_inside(root, report_path)
    if args.dry_run:
        return _envelope(
            "media.beat-cut",
            args,
            status="planned",
            data={
                "input": str(source),
                "audio_asset_id": audio_asset_id,
                "source_asset_ids": [str(asset["id"]) for asset in source_assets],
                "sequence_id": sequence.get("id"),
                "track_id": target_track.get("id"),
                "parameters": {
                    "start_seconds": args.start_seconds,
                    "end_seconds": args.end_seconds,
                    "timeline_start_seconds": args.timeline_start_seconds,
                    "min_segment_seconds": args.min_segment_seconds,
                    "max_clips": args.max_clips,
                    "source_mode": args.source_mode,
                    "apply": bool(args.apply),
                    "replace_track": bool(args.replace_track),
                },
                "engine": "ffmpeg-local-energy-beat-v1",
            },
        )

    probe = probe_media(source)
    beat_anchors = detect_beats(source)
    analysis = {
        "analysis_version": "0.1.0",
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "probe": probe,
        "beat_anchors": beat_anchors,
        "network": "disabled",
    }
    plan = build_beat_cut_plan(
        analysis,
        source_assets,
        ticks_per_second=timeline_tps,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        min_segment_seconds=args.min_segment_seconds,
        max_clips=args.max_clips,
        source_mode=args.source_mode,
    )
    timeline_offset = int(round(float(args.timeline_start_seconds) * timeline_tps))
    for clip in plan["clips"]:
        clip["id"] = f"{run_id}_{int(clip['index']):03d}"
        clip["timeline_start_tick"] = int(clip["timeline_start_tick"]) + timeline_offset
    plan.update(
        {
            "project_id": project.get("project", {}).get("id"),
            "sequence_id": sequence.get("id"),
            "track_id": target_track.get("id"),
            "audio_asset_id": audio_asset_id,
            "source": str(source),
            "source_sha256": analysis["source_sha256"],
            "timeline_start_seconds": round(float(args.timeline_start_seconds), 6),
            "replace_track": bool(args.replace_track),
        }
    )
    if not args.apply:
        atomic_write_json(report_path, {"report_version": BEAT_CUT_VERSION, "created_at": now_iso(), "applied": False, "plan": plan})
        return _envelope("media.beat-cut", args, status="planned", data={"report": str(report_path), "plan": plan, "applied": False}, warnings=plan.get("warnings"))

    existing_clips = list(target_track.get("clips", []))
    if not args.replace_track:
        for generated in plan["clips"]:
            generated_start = int(generated["timeline_start_tick"])
            generated_end = generated_start + int(generated["duration_tick"])
            for existing in existing_clips:
                existing_start = int(existing.get("timeline_start_tick", 0))
                existing_end = existing_start + int(existing.get("duration_tick", 0))
                if max(generated_start, existing_start) < min(generated_end, existing_end):
                    raise AppError("BEAT_CUT_TRACK_OVERLAP", "按节拍剪辑会覆盖目标轨道已有片段，请使用 --replace-track 或调整时间线起点", exit_code=2, path="track_id")
    before_project = copy.deepcopy(project)
    if args.replace_track:
        target_track["clips"] = []
    generated_clips: list[dict[str, Any]] = []
    for item in plan["clips"]:
        clip = {
            "id": item["id"],
            "asset_id": item["asset_id"],
            "timeline_start_tick": int(item["timeline_start_tick"]),
            "duration_tick": int(item["duration_tick"]),
            "source_in_tick": int(item["source_in_tick"]),
            "source_out_tick": int(item["source_out_tick"]),
        }
        if float(item.get("speed", 1.0)) != 1.0:
            clip["speed"] = float(item["speed"])
        target_track.setdefault("clips", []).append(clip)
        generated_clips.append(clip)
    _recompute_sequence_duration(sequence)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("BEAT_CUT_APPLY_INVALID", "按节拍剪辑应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-beat-cut")
    operation_id = new_id("op")
    plan["generated_clips"] = generated_clips
    payload = {
        "report_version": BEAT_CUT_VERSION,
        "created_at": now_iso(),
        "applied": True,
        "operation_id": operation_id,
        "before_snapshot_id": snapshot["snapshot_id"],
        "plan": plan,
        "validation": validation,
    }
    atomic_write_json(report_path, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append(
        {
            "operation_id": operation_id,
            "command": "media.beat-cut",
            "at": now_iso(),
            "report": str(report_path),
            "before_snapshot_id": snapshot["snapshot_id"],
            "sequence_id": sequence.get("id"),
            "track_id": target_track.get("id"),
            "clip_ids": [clip["id"] for clip in generated_clips],
        }
    )
    save_project(root, project)
    _operation(
        root,
        operation_id,
        {
            "operation_id": operation_id,
            "command": "media.beat-cut",
            "status": "succeeded",
            "report": str(report_path),
            "before_snapshot_id": snapshot["snapshot_id"],
            "clip_ids": [clip["id"] for clip in generated_clips],
            "created_at": now_iso(),
        },
    )
    return _envelope(
        "media.beat-cut",
        args,
        data={"report": str(report_path), "plan": plan, "generated_clips": generated_clips, "before_snapshot": snapshot, "validation": validation},
        warnings=plan.get("warnings"),
        operation_id=operation_id,
    )


def command_media_smart_cut(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, getattr(args, "sequence_id", None))
    target_track, clip = _find_clip(sequence, args.clip_id, args.track_id)
    asset = asset_map(project).get(str(clip.get("asset_id")))
    if not asset:
        raise argument_error("智能剪口播目标必须引用项目内媒体资产", "clip_id")
    source = Path(str(asset.get("uri", "")))
    if not source.is_absolute():
        source = root / source
    if not source.exists() or not source.is_file():
        raise argument_error("智能剪口播输入素材不存在", str(source))
    if str(clip.get("sequence_id", "")):
        raise argument_error("智能剪口播当前只支持直接媒体片段", "clip_id")
    analysis = understand_media(source, silence_db=args.silence_db)
    analysis["source_sha256"] = f"sha256:{sha256_file(source)}"
    duration_seconds = int(clip.get("duration_tick", 0)) / max(1, int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000)))
    plan = build_smart_cut_plan(
        analysis,
        duration_seconds=duration_seconds,
        min_silence_seconds=args.min_silence_seconds,
        keep_padding_seconds=args.keep_padding_seconds,
        min_segment_seconds=args.min_segment_seconds,
    )
    linked_track_ids = [str(value) for value in args.linked_track_id]
    linked_clip_ids = [str(value) for value in args.linked_clip_id]
    if linked_clip_ids and len(linked_clip_ids) not in {1, len(linked_track_ids)}:
        raise argument_error("--linked-clip-id 必须提供一个值或与 --linked-track-id 数量相同", "linked_clip_id")
    linked_pairs = [
        {"track_id": track_id, "clip_id": linked_clip_ids[0] if len(linked_clip_ids) == 1 else linked_clip_ids[index] if linked_clip_ids else str(args.clip_id)}
        for index, track_id in enumerate(linked_track_ids)
    ]
    plan.update({
        "project_id": project.get("project", {}).get("id"),
        "sequence_id": sequence.get("id"),
        "asset_id": asset.get("id"),
        "clip_id": clip.get("id"),
        "track_id": target_track.get("id"),
        "linked_track_ids": linked_track_ids,
        "linked_clips": linked_pairs,
        "source": str(source),
        "source_sha256": analysis["source_sha256"],
    })
    if args.dry_run:
        return _envelope("media.smart-cut", args, status="planned", data={"plan": plan, "apply": bool(args.apply)})
    output = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"smart_cut_{safe_filename(str(args.clip_id))}.json"
    ensure_inside(root, output)
    if not args.apply or not plan.get("changed"):
        payload = {"report_version": SMART_CUT_VERSION, "created_at": now_iso(), "plan": plan, "applied": False}
        atomic_write_json(output, payload)
        return _envelope("media.smart-cut", args, status="planned", data={"report": str(output), "plan": plan, "applied": False})
    before_project = copy.deepcopy(project)
    ticks_per_second = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000))
    targets = [(str(args.track_id), str(args.clip_id)), *[(item["track_id"], item["clip_id"]) for item in linked_pairs if item["track_id"] != str(args.track_id)]]
    replacements: list[dict[str, Any]] = []
    try:
        for track_id, clip_id in targets:
            track = find_track(sequence, track_id, None)
            pieces = replace_clip_with_smart_cut(track, clip_id, plan, ticks_per_second=ticks_per_second)
            replacements.append({"track_id": track_id, "clip_id": clip_id, "piece_ids": [item["id"] for item in pieces], "duration_tick": sum(int(item["duration_tick"]) for item in pieces)})
    except AppError:
        raise
    _recompute_sequence_duration(sequence)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "智能剪口播生成的项目未通过校验", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-smart-cut")
    operation_id = new_id("op")
    plan["replacements"] = replacements
    payload = {"report_version": SMART_CUT_VERSION, "created_at": now_iso(), "plan": plan, "applied": True, "operation_id": operation_id, "before_snapshot_id": snapshot["snapshot_id"], "validation": validation}
    atomic_write_json(output, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.smart-cut", "at": now_iso(), "report": str(output), "before_snapshot_id": snapshot["snapshot_id"], "replacements": replacements})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.smart-cut", "status": "succeeded", "report": str(output), "before_snapshot_id": snapshot["snapshot_id"], "replacements": replacements, "created_at": now_iso()})
    return _envelope("media.smart-cut", args, data={"report": str(output), "plan": plan, "replacements": replacements, "before_snapshot": snapshot, "validation": validation}, operation_id=operation_id)


def command_ad_plan(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    brief = load_json(Path(args.input).expanduser().resolve())
    analysis = load_json(Path(args.analysis).expanduser().resolve()) if args.analysis else None
    plan = build_ad_plan(brief, analysis=analysis)
    output = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"ad_plan_{new_id('run')}.json"
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise argument_error("广告规划输出必须位于项目目录内", str(output)) from exc
    if args.dry_run:
        return _envelope("ad.plan", args, status="planned", data={"output": str(output), "plan": plan})
    atomic_write_json(output, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "brief": brief, "plan": plan})
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "ad.plan", "output": str(output), "plan_version": plan["plan_version"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "ad.plan", "status": "succeeded", "output": str(output), "created_at": now_iso()})
    return _envelope("ad.plan", args, data={"output": str(output), "plan": plan}, operation_id=operation_id)


def command_ad_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    payload = load_json(Path(args.input).expanduser().resolve())
    plan = payload.get("plan") if isinstance(payload, dict) and isinstance(payload.get("plan"), dict) else payload
    if not isinstance(plan, dict):
        raise argument_error("广告计划必须是 JSON 对象", "input")
    operations = plan.get("timeline_operations")
    if not isinstance(operations, list) or not operations:
        raise argument_error("广告计划缺少非空 timeline_operations", "timeline_operations")
    sequence = find_sequence(project, args.sequence_id)
    duration_tick = plan.get("duration_tick")
    if duration_tick is not None:
        try:
            duration_tick = int(duration_tick)
        except (TypeError, ValueError) as exc:
            raise argument_error("广告计划 duration_tick 必须是整数", "duration_tick") from exc
        if duration_tick <= 0:
            raise argument_error("广告计划 duration_tick 必须大于 0", "duration_tick")
    before_project = copy.deepcopy(project)
    applied: list[dict[str, Any]] = []
    existing_ids = {str(marker.get("id")) for marker in sequence.get("markers", [])}
    for item in operations:
        if not isinstance(item, dict) or str(item.get("op", "")) != "add_marker":
            raise argument_error("ad apply 目前只接受 add_marker 计划操作", "timeline_operations")
        marker_id = str(item.get("id") or "")
        if not marker_id:
            raise argument_error("广告计划标记缺少 id", "timeline_operations[].id")
        try:
            at_tick = int(item.get("at_tick", 0))
        except (TypeError, ValueError) as exc:
            raise argument_error("广告计划标记 at_tick 必须是整数", "timeline_operations[].at_tick") from exc
        if at_tick < 0:
            raise argument_error("广告计划标记 at_tick 不能为负", "timeline_operations[].at_tick")
        if marker_id in existing_ids:
            if not args.replace_markers:
                raise argument_error(f"序列标记 ID 已存在: {marker_id}; 需要 --replace-markers", "timeline_operations[].id")
            sequence["markers"] = [marker for marker in sequence.get("markers", []) if str(marker.get("id")) != marker_id]
        marker = {"id": marker_id, "at_tick": at_tick, "label": str(item.get("label", ""))}
        sequence.setdefault("markers", []).append(marker)
        existing_ids.add(marker_id)
        applied.append({"op": "add_marker", "marker": marker})
    if duration_tick is not None and not args.preserve_duration:
        max_end = max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in sequence.get("tracks", []) for clip in track.get("clips", [])), default=0)
        if duration_tick < max_end:
            raise argument_error("计划时长短于已有片段末尾", "duration_tick")
        sequence["duration_tick"] = duration_tick
        applied.append({"op": "set_sequence_duration", "sequence_id": sequence["id"], "duration_tick": duration_tick})
    if args.dry_run:
        return _envelope("ad.apply", args, status="planned", data={"sequence_id": sequence["id"], "applied": applied, "plan_version": plan.get("plan_version")})
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "广告计划应用会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-ad-plan-apply")
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "ad.apply", "input": str(Path(args.input).expanduser().resolve()), "plan_version": plan.get("plan_version"), "applied": applied, "before_snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "ad.apply", "status": "succeeded", "applied": applied, "before_snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("ad.apply", args, data={"sequence_id": sequence["id"], "applied": applied, "validation": validation, "before_snapshot": snapshot}, operation_id=operation_id)


def command_subtitle_validate(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("字幕输入不存在", str(source))
    try:
        cues = parse_caption_file(source)
    except AppError:
        raise
    duration = args.duration
    root = None
    if args.project:
        root, project = load_project(args.project)
        if duration is None:
            sequence = find_sequence(project, None)
            sequence_duration_tick = int(sequence.get("duration_tick", 1))
            # A freshly initialized sequence uses one placeholder tick. Do not
            # reject a standalone subtitle file against that sentinel duration.
            if sequence_duration_tick > 1:
                duration = sequence_duration_tick / int(project["settings"]["timebase"]["ticks_per_second"])
    report = validate_cues(cues, duration, allow_overlap=args.allow_overlap)
    report["input"] = str(source)
    report["format"] = source.suffix.lower().lstrip(".")
    report_path = None
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
    elif root:
        report_path = root / "validation" / f"subtitle_{new_id('run')}.json"
    if report_path:
        atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), **report})
        report["report"] = str(report_path)
    status = "succeeded" if report["ok"] else "failed"
    return _envelope("subtitle.validate", args, data=report, status=status, errors=report["errors"])


def command_subtitle_normalize(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("字幕输入不存在", str(source))
    root = None
    if args.project:
        root, _ = load_project(args.project)
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise argument_error("字幕输出必须位于项目目录内", str(output)) from exc
    cues = parse_caption_file(source)
    report = validate_cues(cues, allow_overlap=args.allow_overlap)
    if not report["ok"]:
        return _envelope("subtitle.normalize", args, data={"input": str(source), "output": str(output), "validation": report}, status="failed", errors=report["errors"])
    if args.dry_run:
        return _envelope("subtitle.normalize", args, status="planned", data={"input": str(source), "output": str(output), "cue_count": len(cues)})
    write_srt_file(output, cues)
    return _envelope("subtitle.normalize", args, data={"input": str(source), "output": str(output), "cue_count": len(cues), "validation": report})


def command_tts_synthesize(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.text is not None:
        text = str(args.text)
        source = {"kind": "inline", "path": None}
    else:
        source_path = Path(str(args.input)).expanduser().resolve()
        if not source_path.exists() or not source_path.is_file():
            raise argument_error("TTS 文本输入不存在", str(source_path))
        try:
            text = source_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            raise argument_error("TTS 文本输入必须是 UTF-8", str(source_path)) from exc
        source = {"kind": "file", "path": str(source_path)}
    operation_id = new_id("op")
    output = Path(args.output).expanduser().resolve() if args.output else root / "assets" / f"tts_{operation_id}.wav"
    ensure_inside(root, output)
    if args.dry_run:
        return _envelope(
            "tts.synthesize",
            args,
            status="planned",
            data={"output": str(output), "voice": args.voice, "sample_rate": args.sample_rate, "channels": args.channels, "source": source},
            operation_id=operation_id,
        )
    if not flite_available():
        raise dependency_error("当前 FFmpeg 没有 flite 音频滤镜", "安装包含 --enable-libflite 的原生 FFmpeg；不会自动下载或调用线上 TTS")
    result = synthesize_local_tts(
        root,
        text,
        output,
        operation_id=operation_id,
        voice=args.voice,
        sample_rate=args.sample_rate,
        channels=args.channels,
    )
    payload = {
        "operation_id": operation_id,
        "command": "tts.synthesize",
        "status": "succeeded",
        "project_id": project["project"]["id"],
        "source": source,
        "created_at": now_iso(),
        **{key: value for key, value in result.items() if key != "probe"},
        "duration_seconds": result["probe"].get("duration_seconds", 0.0),
    }
    _operation(root, operation_id, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append(
        {
            "operation_id": operation_id,
            "command": "tts.synthesize",
            "output": str(output),
            "engine": result["engine"],
            "text_sha256": result["text_sha256"],
            "at": now_iso(),
        }
    )
    save_project(root, project)
    return _envelope("tts.synthesize", args, data={**result, "source": source}, operation_id=operation_id)


def command_effects_list(args: argparse.Namespace) -> dict[str, Any]:
    effects = list_effects(args.query, keyframable_only=bool(args.keyframable_only))
    return _envelope(
        "effects.list",
        args,
        data={
            "catalog_version": EFFECT_CATALOG_VERSION,
            "source": "ffmpeg-local",
            "network": "disabled",
            "count": len(effects),
            "effects": effects,
        },
    )


def command_effects_inspect(args: argparse.Namespace) -> dict[str, Any]:
    effect = get_effect(args.name)
    if effect is None:
        raise argument_error(f"本地效果目录中不存在: {args.name}", "name")
    return _envelope(
        "effects.inspect",
        args,
        data={
            "catalog_version": EFFECT_CATALOG_VERSION,
            "source": "ffmpeg-local",
            "network": "disabled",
            "effect": effect,
        },
    )


def command_motion_list(args: argparse.Namespace) -> dict[str, Any]:
    presets = list_motion_presets(args.query)
    return _envelope(
        "motion.list",
        args,
        data={
            "catalog_version": MOTION_PRESET_CATALOG_VERSION,
            "source": "local-catalog",
            "engine": "timeline-keyframes",
            "network": "disabled",
            "count": len(presets),
            "presets": presets,
        },
    )


def command_motion_inspect(args: argparse.Namespace) -> dict[str, Any]:
    preset = get_motion_preset(args.name)
    if preset is None:
        raise argument_error(f"本地运镜目录中不存在: {args.name}", "name")
    return _envelope(
        "motion.inspect",
        args,
        data={
            "catalog_version": MOTION_PRESET_CATALOG_VERSION,
            "source": "local-catalog",
            "engine": "timeline-keyframes",
            "network": "disabled",
            "preset": preset,
        },
    )


def _clip_from_change(change: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    for field in ("source_in_tick", "source_out_tick"):
        if field not in change:
            raise argument_error(f"append_clip 缺少字段: {field}", field)
    asset_id = change.get("asset_id")
    sequence_id = change.get("nested_sequence_id")
    generator = change.get("generator")
    text_generator = isinstance(generator, dict) and str(generator.get("type", "")).lower() == "text" and isinstance(change.get("subtitle"), dict)
    if not asset_id and not sequence_id and not text_generator:
        raise argument_error("append_clip 必须提供 asset_id、nested_sequence_id 或有效的 text generator")
    source_in = int(change["source_in_tick"])
    source_out = int(change["source_out_tick"])
    duration = int(change.get("duration_tick", source_out - source_in))
    if duration <= 0 or source_out <= source_in:
        raise argument_error("片段 source/duration 时间范围无效")
    start = change.get("timeline_start_tick")
    if start is None:
        start = max((int(item.get("timeline_start_tick", 0)) + int(item.get("duration_tick", 0)) for item in track.get("clips", [])), default=0)
    clip = {"id": change.get("id") or new_id("clip"), "timeline_start_tick": int(start), "duration_tick": duration, "source_in_tick": source_in, "source_out_tick": source_out}
    if asset_id:
        clip["asset_id"] = asset_id
    if sequence_id:
        clip["sequence_id"] = sequence_id
    if text_generator:
        clip["generator"] = copy.deepcopy(generator)
    for field in ("speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "generator", "audio", "blend", "mask"):
        if field in change:
            clip[field] = change[field]
    return clip


def _find_clip(sequence: dict[str, Any], clip_id: str, track_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not clip_id:
        raise argument_error("操作必须提供 clip_id", "clip_id")
    tracks = sequence.get("tracks", [])
    if track_id:
        tracks = [track for track in tracks if track.get("id") == track_id]
    for track in tracks:
        for clip in track.get("clips", []):
            if clip.get("id") == clip_id:
                return track, clip
    raise argument_error(f"找不到片段: {clip_id}", "clip_id")


def _recompute_sequence_duration(sequence: dict[str, Any]) -> None:
    end = max(
        (int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0))
         for track in sequence.get("tracks", [])
         for clip in track.get("clips", [])),
        default=0,
    )
    sequence["duration_tick"] = max(1, end)


def _add_track(sequence: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    track_id = str(change.get("track_id") or change.get("id") or new_id("track"))
    if any(track.get("id") == track_id for track in sequence.get("tracks", [])):
        raise argument_error(f"轨道 ID 已存在: {track_id}", "track_id")
    kind = str(change.get("kind") or change.get("track_kind") or "video")
    if kind not in {"video", "audio", "subtitle", "data"}:
        raise argument_error(f"轨道 kind 无效: {kind}", "kind")
    order = int(change.get("order", max((int(track.get("order", 0)) for track in sequence.get("tracks", [])), default=-1) + 1))
    track = {
        "id": track_id,
        "kind": kind,
        "order": order,
        "muted": bool(change.get("muted", False)),
        "locked": bool(change.get("locked", False)),
        "clips": [],
    }
    if "overlap_policy" in change:
        track["overlap_policy"] = change["overlap_policy"]
    if isinstance(change.get("audio"), dict):
        track["audio"] = copy.deepcopy(change["audio"])
    sequence.setdefault("tracks", []).append(track)
    return track


def _set_keyframe_track(clip: dict[str, Any], property_name: str, values: list[tuple[int, float, str]]) -> None:
    tracks = clip.setdefault("keyframes", [])
    track = next((item for item in tracks if item.get("property") == property_name), None)
    payload = {"property": property_name, "keyframes": [{"at_tick": int(at), "value": float(value), "interpolation": interpolation} for at, value, interpolation in values]}
    if track is None:
        tracks.append(payload)
    else:
        track.clear()
        track.update(payload)


def _clamp_clip_keyframes(clip: dict[str, Any]) -> None:
    duration = max(1, int(clip.get("duration_tick", 1)))
    retained: list[dict[str, Any]] = []
    for track in clip.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        points = track.get("keyframes", [])
        if not isinstance(points, list):
            continue
        normalized: list[dict[str, Any]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            copy_point = dict(point)
            try:
                copy_point["at_tick"] = min(duration, max(0, int(copy_point.get("at_tick", 0))))
            except (TypeError, ValueError):
                continue
            normalized.append(copy_point)
        normalized.sort(key=lambda item: int(item["at_tick"]))
        if normalized:
            track["keyframes"] = normalized
            retained.append(track)
    clip["keyframes"] = retained


def _apply_motion_preset(clip: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    requested = str(change.get("preset") or change.get("motion_preset") or "")
    preset = canonical_motion_preset(requested)
    if not requested:
        raise argument_error("apply_motion_preset 缺少 preset", "preset")
    definition = get_motion_preset(preset or requested)
    if definition is None or preset is None:
        raise argument_error(f"不支持的运动预设: {requested}", "preset")
    duration = max(1, int(clip.get("duration_tick", 1)))
    start_tick = max(0, int(change.get("start_tick", 0)))
    end_tick = min(duration, int(change.get("end_tick", duration)))
    if end_tick <= start_tick:
        raise argument_error("运动预设的时间范围无效", "start_tick/end_tick")
    parameter_values = definition.get("parameters", {})

    def _number(name: str, *, absolute: bool = False) -> float:
        default = parameter_values.get(name, {}).get("default", 0.0)
        raw = change.get(name, default)
        if isinstance(raw, bool):
            raise argument_error(f"运动预设参数 {name} 必须是数字", name)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise argument_error(f"运动预设参数 {name} 必须是数字", name) from exc
        if not math.isfinite(value):
            raise argument_error(f"运动预设参数 {name} 必须是有限数字", name)
        if absolute:
            value = abs(value)
        spec = parameter_values.get(name, {})
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if (minimum is not None and value < float(minimum)) or (maximum is not None and value > float(maximum)):
            raise argument_error(f"运动预设参数 {name} 超出范围", name)
        return value

    def _integer(name: str) -> int:
        default = parameter_values.get(name, {}).get("default", 0)
        raw = change.get(name, default)
        if isinstance(raw, bool):
            raise argument_error(f"运动预设参数 {name} 必须是整数", name)
        if isinstance(raw, float) and not raw.is_integer():
            raise argument_error(f"运动预设参数 {name} 必须是整数", name)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise argument_error(f"运动预设参数 {name} 必须是整数", name) from exc
        spec = parameter_values.get(name, {})
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if (minimum is not None and value < int(minimum)) or (maximum is not None and value > int(maximum)):
            raise argument_error(f"运动预设参数 {name} 超出范围", name)
        return value

    amount = _number("amount", absolute=True) if "amount" in parameter_values else 0.0
    transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
    position = transform.get("position") if isinstance(transform.get("position"), dict) else {}
    scale = float(transform.get("scale", 1.0))
    x = float(position.get("x", transform.get("position_x", 0.5)))
    y = float(position.get("y", transform.get("position_y", 0.5)))
    ease = "ease_in_out"
    if preset == "zoom_in":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
    elif preset == "zoom_out":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale * (1 + amount), ease), (end_tick, scale, ease)])
    elif preset == "pan_left":
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x + amount / 2, ease), (end_tick, x - amount / 2, ease)])
    elif preset == "pan_right":
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 2, ease), (end_tick, x + amount / 2, ease)])
    elif preset == "pan_up":
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 2, ease), (end_tick, y - amount / 2, ease)])
    elif preset == "pan_down":
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y - amount / 2, ease), (end_tick, y + amount / 2, ease)])
    elif preset == "ken_burns":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 3, ease), (end_tick, x + amount / 3, ease)])
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 3, ease), (end_tick, y - amount / 3, ease)])
    elif preset == "rotate_in":
        degrees = _number("degrees")
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, degrees, ease), (end_tick, 0.0, ease)])
    elif preset == "rotate_out":
        degrees = _number("degrees")
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, 0.0, ease), (end_tick, degrees, ease)])
    elif preset == "fade_in":
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 0.0, "linear"), (end_tick, 1.0, ease)])
    elif preset == "fade_out":
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 1.0, ease), (end_tick, 0.0, "linear")])
    elif preset == "shake":
        points = _integer("points")
        values = []
        for index in range(points):
            progress = index / (points - 1)
            sign = -1 if index % 2 else 1
            values.append((round(start_tick + (end_tick - start_tick) * progress), x + sign * amount / 3, "linear"))
        _set_keyframe_track(clip, "transform.position.x", values)
    return {
        "preset": preset,
        "requested_preset": requested,
        "catalog_version": MOTION_PRESET_CATALOG_VERSION,
        "properties": definition["properties"],
        "start_tick": start_tick,
        "end_tick": end_tick,
        "amount": amount,
        **({"degrees": _number("degrees")} if "degrees" in parameter_values else {}),
        **({"points": _integer("points")} if "points" in parameter_values else {}),
    }


def command_motion_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    before_project = copy.deepcopy(project)
    working = copy.deepcopy(project) if args.dry_run else project
    target_sequence = find_sequence(working, sequence["id"])
    track, clip = _find_clip(target_sequence, args.clip_id, args.track_id)
    change: dict[str, Any] = {"preset": args.preset}
    for field in ("amount", "degrees", "points", "start_tick", "end_tick"):
        value = getattr(args, field, None)
        if value is not None:
            change[field] = value
    motion = _apply_motion_preset(clip, change)
    validation = validate_project(root, working, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "运动预设会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope(
            "motion.apply",
            args,
            status="planned",
            data={"sequence_id": target_sequence["id"], "track_id": track["id"], "clip_id": clip["id"], "motion": motion, "clip": clip, "validation": validation},
        )
    snapshot = create_snapshot(root, before_project, label="before-motion-apply")
    operation_id = new_id("op")
    working.setdefault("provenance", {}).setdefault("change_log", []).append(
        {
            "operation_id": operation_id,
            "command": "motion.apply",
            "at": now_iso(),
            "sequence_id": target_sequence["id"],
            "track_id": track["id"],
            "clip_id": clip["id"],
            "motion": motion,
            "before_snapshot_id": snapshot["snapshot_id"],
        }
    )
    save_project(root, working)
    _operation(
        root,
        operation_id,
        {
            "operation_id": operation_id,
            "command": "motion.apply",
            "status": "succeeded",
            "project_id": working["project"]["id"],
            "sequence_id": target_sequence["id"],
            "track_id": track["id"],
            "clip_id": clip["id"],
            "motion": motion,
            "before_snapshot_id": snapshot["snapshot_id"],
            "created_at": now_iso(),
        },
    )
    return _envelope(
        "motion.apply",
        args,
        data={"sequence_id": target_sequence["id"], "track_id": track["id"], "clip_id": clip["id"], "motion": motion, "clip": clip, "validation": validation, "before_snapshot": snapshot},
        operation_id=operation_id,
    )


def _split_clip_keyframes(clip: dict[str, Any], split_tick: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left = copy.deepcopy(clip.get("keyframes", []))
    right = copy.deepcopy(clip.get("keyframes", []))
    for tracks, offset, upper in ((left, 0, split_tick), (right, split_tick, int(clip.get("duration_tick", 0)))):
        for track in tracks:
            points = []
            for point in track.get("keyframes", []):
                at = int(point.get("at_tick", 0))
                if offset == 0 and at <= upper:
                    points.append(point)
                elif offset == split_tick and at >= offset and at <= upper:
                    updated = dict(point)
                    updated["at_tick"] = at - offset
                    points.append(updated)
            track["keyframes"] = points
    return [track for track in left if track.get("keyframes")], [track for track in right if track.get("keyframes")]


def _adjust_source_for_duration(clip: dict[str, Any], new_duration: int) -> None:
    old_duration = max(1, int(clip.get("duration_tick", 1)))
    source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
    speed = abs(float(clip.get("speed", 1.0) or 1.0))
    source_span = max(1, int(round(new_duration * speed)))
    if bool(clip.get("reverse")):
        clip["source_in_tick"] = max(0, int(clip.get("source_out_tick", source_span)) - source_span)
    else:
        clip["source_out_tick"] = int(clip.get("source_in_tick", 0)) + source_span
    clip["duration_tick"] = max(1, int(new_duration))


def _source_shift(clip: dict[str, Any], delta: int, asset: dict[str, Any]) -> None:
    source_in = int(clip.get("source_in_tick", 0)) + int(delta)
    source_out = int(clip.get("source_out_tick", 0)) + int(delta)
    total = int(asset.get("probe", {}).get("duration_tick", 0) or 0)
    if source_in < 0 or source_out <= source_in or (total and source_out > total):
        raise argument_error("slip_clip 会越过素材边界", "delta_source_tick")
    clip["source_in_tick"] = source_in
    clip["source_out_tick"] = source_out


def command_timeline_compose(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    changes = _load_changes(args.input)
    sequence = find_sequence(project, changes.get("sequence_id") or args.sequence_id)
    before_project = copy.deepcopy(project)
    if args.dry_run:
        working = json.loads(json.dumps(project))
    else:
        working = project
    operations = changes.get("operations")
    if operations is None:
        operations = [{"op": "append_clip", **item} for item in changes.get("clips", [])]
    applied: list[dict[str, Any]] = []
    for change in operations:
        operation = change.get("op", "append_clip")
        if operation == "append_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
            clip = _clip_from_change(change, track)
            if clip.get("speed_curve") is not None and "duration_tick" not in change:
                source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                curve_duration = speed_curve_duration_seconds(clip, source_span, int(working["settings"]["timebase"]["ticks_per_second"]))
                if curve_duration is not None:
                    clip["duration_tick"] = max(1, int(round(curve_duration * int(working["settings"]["timebase"]["ticks_per_second"]))))
            if any(existing.get("id") == clip["id"] for existing in track.get("clips", [])):
                raise argument_error(f"片段 ID 已存在: {clip['id']}")
            track.setdefault("clips", []).append(clip)
            target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
            preset = change.get("motion_preset") or change.get("preset")
            applied_item = {"op": operation, "track_id": track["id"], "clip": clip}
            if preset:
                applied_item["motion"] = _apply_motion_preset(clip, {**change, "motion_preset": preset})
            applied.append(applied_item)
        elif operation == "add_sequence":
            sequence_id = str(change.get("id") or change.get("sequence_id") or new_id("seq"))
            if any(item.get("id") == sequence_id for item in working.get("sequences", [])):
                raise argument_error(f"序列 ID 已存在: {sequence_id}", "id")
            target = {"id": sequence_id, "name": str(change.get("name") or sequence_id), "duration_tick": max(1, int(change.get("duration_tick", 1))), "tracks": [], "markers": []}
            for track_kind, track_id, order in (("video", f"{sequence_id}_video_1", 0), ("audio", f"{sequence_id}_audio_1", 0)):
                target["tracks"].append({"id": str(change.get(f"{track_kind}_track_id") or track_id), "kind": track_kind, "order": order, "muted": False, "locked": False, "clips": []})
            working.setdefault("sequences", []).append(target)
            applied.append({"op": operation, "sequence": target})
        elif operation == "append_sequence_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
            nested_change = {**change, "nested_sequence_id": change.get("nested_sequence_id") or change.get("child_sequence_id")}
            clip = _clip_from_change(nested_change, track)
            if not clip.get("sequence_id"):
                raise argument_error("append_sequence_clip 必须提供 nested_sequence_id", "nested_sequence_id")
            if any(existing.get("id") == clip["id"] for existing in track.get("clips", [])):
                raise argument_error(f"片段 ID 已存在: {clip['id']}")
            track.setdefault("clips", []).append(clip)
            target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "split_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            split_tick = int(change.get("at_tick", 0))
            duration = int(clip.get("duration_tick", 0))
            if split_tick <= 0 or split_tick >= duration:
                raise argument_error("split_clip 的 at_tick 必须位于片段内部", "at_tick")
            source_span = int(clip.get("source_out_tick", 0)) - int(clip.get("source_in_tick", 0))
            source_split = int(clip.get("source_in_tick", 0)) + int(round(source_span * split_tick / duration))
            left = copy.deepcopy(clip)
            right = copy.deepcopy(clip)
            left["id"] = str(change.get("left_id") or f"{clip['id']}_a")
            right["id"] = str(change.get("right_id") or f"{clip['id']}_b")
            if left["id"] == right["id"] or any(item.get("id") in {left["id"], right["id"]} for item in track.get("clips", []) if item is not clip):
                raise argument_error("split_clip 生成的片段 ID 已存在", "left_id/right_id")
            left["duration_tick"] = split_tick
            left["source_out_tick"] = source_split
            right["timeline_start_tick"] = int(clip.get("timeline_start_tick", 0)) + split_tick
            right["duration_tick"] = duration - split_tick
            right["source_in_tick"] = source_split
            left["keyframes"], right["keyframes"] = _split_clip_keyframes(clip, split_tick)
            position = track["clips"].index(clip)
            track["clips"][position : position + 1] = [left, right]
            applied.append({"op": operation, "track_id": track["id"], "source_clip_id": clip["id"], "clips": [left, right]})
        elif operation == "ripple_insert":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            at_tick = int(change.get("at_tick", 0))
            delta = int(change.get("duration_tick", 0))
            if at_tick < 0 or delta <= 0:
                raise argument_error("ripple_insert 需要非负 at_tick 和正 duration_tick")
            selected = [find_track(target_sequence, change.get("track_id"), None)] if change.get("track_id") else target_sequence.get("tracks", [])
            for track in selected:
                for clip in track.get("clips", []):
                    start = int(clip.get("timeline_start_tick", 0))
                    end = start + int(clip.get("duration_tick", 0))
                    if start < at_tick < end:
                        raise argument_error("ripple_insert 暂不在片段内部切开；请先 split_clip", "at_tick")
                    if start >= at_tick:
                        clip["timeline_start_tick"] = start + delta
            target_sequence["duration_tick"] = int(target_sequence.get("duration_tick", 1)) + delta
            applied.append({"op": operation, "at_tick": at_tick, "duration_tick": delta})
        elif operation == "ripple_delete":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            at_tick = int(change.get("at_tick", 0))
            delta = int(change.get("duration_tick", 0))
            if at_tick < 0 or delta <= 0:
                raise argument_error("ripple_delete 需要非负 at_tick 和正 duration_tick")
            end_tick = at_tick + delta
            selected = [find_track(target_sequence, change.get("track_id"), None)] if change.get("track_id") else target_sequence.get("tracks", [])
            for track in selected:
                retained: list[dict[str, Any]] = []
                for clip in track.get("clips", []):
                    start = int(clip.get("timeline_start_tick", 0))
                    end = start + int(clip.get("duration_tick", 0))
                    if end <= at_tick:
                        retained.append(clip)
                    elif start >= end_tick:
                        clip["timeline_start_tick"] = start - delta
                        retained.append(clip)
                    elif start < at_tick and end > end_tick:
                        new_duration = int(clip.get("duration_tick", 0)) - delta
                        _adjust_source_for_duration(clip, new_duration)
                        retained.append(clip)
                    elif start < at_tick:
                        new_duration = max(1, at_tick - start)
                        _adjust_source_for_duration(clip, new_duration)
                        retained.append(clip)
                    elif end > end_tick:
                        clip["timeline_start_tick"] = at_tick
                        clip["source_in_tick"] = int(clip.get("source_in_tick", 0)) + int(round(delta * abs(float(clip.get("speed", 1.0) or 1.0))))
                        clip["duration_tick"] = end - end_tick
                        retained.append(clip)
                track["clips"] = retained
            target_sequence["duration_tick"] = max(1, int(target_sequence.get("duration_tick", 1)) - delta)
            applied.append({"op": operation, "at_tick": at_tick, "duration_tick": delta})
        elif operation == "slip_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            asset = asset_map(working).get(str(clip.get("asset_id")))
            if not asset:
                raise argument_error("slip_clip 只支持直接引用媒体资产", "asset_id")
            _source_shift(clip, int(change.get("delta_source_tick", 0)), asset)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "slide_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            new_start = int(clip.get("timeline_start_tick", 0)) + int(change.get("delta_tick", 0))
            if new_start < 0:
                raise argument_error("slide_clip 不能移动到负时间", "delta_tick")
            clip["timeline_start_tick"] = new_start
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "set_clip_speed":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            speed = float(change.get("speed", 1.0))
            if speed <= 0:
                raise argument_error("speed 必须大于 0", "speed")
            clip["speed"] = speed
            if str(change.get("duration_mode", "preserve_source")) == "preserve_source":
                source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                clip["duration_tick"] = max(1, int(round(source_span / speed)))
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "set_clip_speed_curve":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            curve = change.get("speed_curve") if isinstance(change.get("speed_curve"), (dict, list)) else {"keyframes": change.get("keyframes", [])}
            if isinstance(curve, dict):
                keyframes = curve.get("keyframes")
            else:
                keyframes = curve
            if not isinstance(keyframes, list) or not keyframes:
                raise argument_error("set_clip_speed_curve 需要非空 keyframes", "speed_curve.keyframes")
            clip["speed_curve"] = curve
            source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
            curve_duration = speed_curve_duration_seconds(clip, source_span, int(working["settings"]["timebase"]["ticks_per_second"]))
            if curve_duration is not None and str(change.get("duration_mode", "preserve_source")) == "preserve_source":
                clip["duration_tick"] = max(1, int(round(curve_duration * int(working["settings"]["timebase"]["ticks_per_second"]))))
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip, "curve_duration_seconds": curve_duration})
        elif operation == "reverse_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            clip["reverse"] = bool(change.get("enabled", not bool(clip.get("reverse", False))))
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"], "reverse": clip["reverse"]})
        elif operation == "freeze_frame":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            freeze_duration = int(change.get("duration_tick", 0))
            if freeze_duration <= 0:
                raise argument_error("freeze_frame 需要正 duration_tick", "duration_tick")
            at_tick = int(change.get("at_tick", int(clip.get("duration_tick", 1))))
            if at_tick < 0 or at_tick > int(clip.get("duration_tick", 1)):
                raise argument_error("freeze_frame 的 at_tick 越过片段", "at_tick")
            audio_mode = str(change.get("audio_mode", "silence")).lower()
            if audio_mode not in {"silence", "continue"}:
                raise argument_error("freeze_frame 的 audio_mode 只支持 silence 或 continue", "audio_mode")
            clip["freeze"] = {"at_tick": at_tick, "duration_tick": freeze_duration, "audio_mode": audio_mode}
            clip["duration_tick"] = int(clip.get("duration_tick", 1)) + freeze_duration
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "add_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = _add_track(target_sequence, change)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track": track})
        elif operation == "remove_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track_id = str(change.get("track_id") or change.get("id") or "")
            track = find_track(target_sequence, track_id, None)
            if track.get("locked"):
                raise argument_error(f"轨道已锁定，不能删除: {track_id}", "track_id")
            if track.get("clips") and not bool(change.get("force", False)):
                raise argument_error("含片段的轨道需要 force=true 才能删除", "force")
            target_sequence["tracks"] = [item for item in target_sequence.get("tracks", []) if item is not track]
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track_id": track_id})
        elif operation == "update_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), None)
            patch = change.get("patch") if isinstance(change.get("patch"), dict) else change
            for field in ("muted", "locked", "order", "overlap_policy", "audio"):
                if field in patch:
                    track[field] = copy.deepcopy(patch[field]) if field == "audio" else patch[field]
            applied.append({"op": operation, "track_id": track["id"], "track": track})
        elif operation == "remove_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            track["clips"] = [item for item in track.get("clips", []) if item is not clip]
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"]})
        elif operation == "update_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            patch = change.get("patch") if isinstance(change.get("patch"), dict) else change
            if "id" in patch or "clip_id" in patch:
                raise argument_error("update_clip 不允许修改片段 ID", "patch")
            for field in ("asset_id", "sequence_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick", "speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "generator", "audio", "blend", "mask"):
                if field in patch:
                    clip[field] = patch[field]
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "apply_motion_preset":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            motion = _apply_motion_preset(clip, change)
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"], "motion": motion})
        elif operation == "set_sequence_duration":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            duration_tick = int(change.get("duration_tick", 0))
            if duration_tick <= 0:
                raise argument_error("duration_tick 必须大于 0", "duration_tick")
            max_end = max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in target_sequence.get("tracks", []) for clip in track.get("clips", [])), default=0)
            if duration_tick < max_end and not bool(change.get("trim", False)):
                raise argument_error("序列时长不能短于片段末尾；需要 trim=true 才能继续", "duration_tick")
            target_sequence["duration_tick"] = duration_tick
            if change.get("trim"):
                for track in target_sequence.get("tracks", []):
                    track["clips"] = [clip for clip in track.get("clips", []) if int(clip.get("timeline_start_tick", 0)) < duration_tick]
                    for clip in track.get("clips", []):
                        end = int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0))
                        if end > duration_tick:
                            clip["duration_tick"] = max(1, duration_tick - int(clip.get("timeline_start_tick", 0)))
                        _clamp_clip_keyframes(clip)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "duration_tick": target_sequence["duration_tick"]})
        elif operation == "add_marker":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            marker = {"id": change.get("id") or new_id("marker"), "at_tick": int(change.get("at_tick", 0)), "label": change.get("label", "")}
            if any(item.get("id") == marker["id"] for item in target_sequence.get("markers", [])):
                raise argument_error(f"标记 ID 已存在: {marker['id']}", "id")
            target_sequence.setdefault("markers", []).append(marker)
            applied.append({"op": operation, "marker": marker})
        elif operation == "remove_marker":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            marker_id = str(change.get("marker_id") or change.get("id") or "")
            before = len(target_sequence.get("markers", []))
            target_sequence["markers"] = [item for item in target_sequence.get("markers", []) if item.get("id") != marker_id]
            if len(target_sequence["markers"]) == before:
                raise argument_error(f"找不到标记: {marker_id}", "marker_id")
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "marker_id": marker_id})
        else:
            raise argument_error(f"不支持的时间线操作: {operation}")
    validation = validate_project(root, working, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "时间线变更会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("timeline.compose", args, status="planned", data={"applied": applied, "validation": validation})
    snapshot = create_snapshot(root, before_project, label="before-timeline-compose")
    operation_id = new_id("op")
    working.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "timeline.compose", "input": str(Path(args.input).resolve()), "at": now_iso(), "changes": applied, "before_snapshot_id": snapshot["snapshot_id"]})
    save_project(root, working)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "timeline.compose", "status": "succeeded", "changes": applied, "before_snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("timeline.compose", args, data={"sequence_id": sequence["id"], "applied": applied, "validation": validation, "before_snapshot": snapshot}, operation_id=operation_id)


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    report = validate_project(root, project, strict_rights=args.strict_rights, target=args.target)
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
    else:
        report_path = root / "validation" / f"validation_{new_id('run')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **report})
    status = "succeeded" if report["ok"] else "failed"
    errors = report.get("errors", [])
    return _envelope("validate", args, data={"report": str(report_path), **report}, status=status, warnings=report.get("warnings", []), errors=errors)


def command_rights_check(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    result = check_project_rights(project, load_ledger(root), args.target, strict=True)
    status = "succeeded" if result["ok"] else "failed"
    return _envelope("rights.check", args, data=result, status=status, errors=result.get("failures", []), warnings=result.get("warnings", []))


def command_rights_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    records = active_records(load_ledger(root))
    if args.status:
        records = [record for record in records if record.get("verification_status") == args.status]
    return _envelope("rights.list", args, data={"records": records, "count": len(records)})


def command_rights_history(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    ledger = load_ledger(root)
    history = record_history(ledger, args.asset_id)
    events = [event for event in ledger.get("events", []) if str(event.get("asset_id")) == str(args.asset_id)]
    if not history:
        raise AppError("RIGHTS_RECORD_MISSING", f"找不到 Rights Ledger 记录: {args.asset_id}", exit_code=3, path="asset_id")
    return _envelope("rights.history", args, data={"asset_id": args.asset_id, "records": history, "events": events, "decisions": disposition_decisions(ledger, args.asset_id), "effective_decisions": effective_disposition_decisions(ledger, args.asset_id), "count": len(history)})


def command_rights_update(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    patch: dict[str, Any] = {}
    if args.patch:
        patch_path = Path(require_local_reference(args.patch, field="--patch")).expanduser().resolve()
        patch_payload = load_json(patch_path)
        if not isinstance(patch_payload, dict):
            raise argument_error("--patch 顶层必须是 JSON 对象", "--patch")
        patch.update(patch_payload)
    flags = {
        "verification_status": args.status,
        "source_url": args.source_url,
        "source_version": args.source_version,
        "retrieved_at": args.retrieved_at,
        "creator": args.creator,
        "license_spdx": args.license_spdx,
        "license_url": args.license_url,
        "attribution": args.attribution,
        "evidence": args.evidence,
        "expires_at": args.expires_at,
        "takedown_status": args.takedown_status,
        "permitted_uses": args.permitted_use,
        "permitted_channels": args.permitted_channel,
        "restrictions": args.restriction,
    }
    patch.update({key: value for key, value in flags.items() if value is not None})
    planned_ledger = copy.deepcopy(ledger)
    result = revise_record(planned_ledger, args.asset_id, patch, reason=args.reason, actor=args.actor, reopen=args.reopen)
    if args.dry_run:
        return _envelope("rights.update", args, status="planned", data={"revision": result, "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-revision")
    operation_id = new_id("op")
    committed = revise_record(ledger, args.asset_id, patch, reason=args.reason, actor=args.actor, reopen=args.reopen)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.update", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "record_version": committed["record"]["record_version"], "reason": args.reason, "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.update", "status": "succeeded", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "record_version": committed["record"]["record_version"], "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("rights.update", args, data={"revision": committed, "snapshot": snapshot, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_export(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    output = ensure_inside(root, Path(args.output))
    manifest = release_manifest(project, load_ledger(root), args.target)
    if args.dry_run:
        return _envelope("rights.export", args, status="planned", data={"manifest": manifest, "output": str(output)})
    atomic_write_json(output, manifest)
    status = "succeeded" if manifest["rights_check"]["ok"] else "failed"
    return _envelope("rights.export", args, data={"manifest": manifest, "output": str(output)}, status=status, errors=manifest["rights_check"].get("failures", []), warnings=manifest["rights_check"].get("warnings", []))


def command_rights_batch_update(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    input_path = Path(require_local_reference(args.input, field="--input")).expanduser().resolve()
    payload = load_json(input_path)
    updates = payload.get("updates")
    if not isinstance(updates, list) or not updates:
        raise argument_error("Rights Ledger 批量输入必须包含非空 updates 数组", "--input")

    def apply_updates(target_ledger: dict[str, Any]) -> list[dict[str, Any]]:
        planned: list[dict[str, Any]] = []
        for index, item in enumerate(updates):
            if not isinstance(item, dict):
                raise argument_error(f"批量修订第 {index} 项必须是对象", "updates")
            asset_id = str(item.get("asset_id") or "")
            if not asset_id:
                raise argument_error(f"批量修订第 {index} 项缺少 asset_id", "updates")
            patch = copy.deepcopy(item.get("patch"))
            if patch is None:
                patch = {}
                if item.get("status") is not None:
                    patch["verification_status"] = item["status"]
            if not isinstance(patch, dict):
                raise argument_error(f"批量修订第 {index} 项 patch 必须是对象", "updates")
            reason = str(item.get("reason") or "")
            actor = str(item.get("actor") or "ai-ad-editor")
            revision = revise_record(target_ledger, asset_id, patch, reason=reason, actor=actor, reopen=bool(item.get("reopen", False)))
            planned.append({"asset_id": asset_id, "revision": revision})
        return planned

    planned_ledger = copy.deepcopy(ledger)
    planned = apply_updates(planned_ledger)
    if args.dry_run:
        return _envelope("rights.batch-update", args, status="planned", data={"updates": planned, "count": len(planned), "input": str(input_path)})
    snapshot = create_snapshot(root, project, label="rights-batch-update")
    operation_id = new_id("op")
    committed = apply_updates(ledger)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.batch-update", "count": len(committed), "snapshot_id": snapshot["snapshot_id"], "input": str(input_path), "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.batch-update", "status": "succeeded", "count": len(committed), "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("rights.batch-update", args, data={"updates": committed, "count": len(committed), "snapshot": snapshot, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_impact(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    artifacts = impacted_artifacts(root, args.asset_id)
    return _envelope("rights.impact", args, data={"asset_id": args.asset_id, "artifacts": artifacts, "count": len(artifacts)})


def command_rights_retract(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    before = impacted_artifacts(root, args.asset_id)
    patch = {"verification_status": args.status}
    planned_ledger = copy.deepcopy(ledger)
    revision = revise_record(planned_ledger, args.asset_id, patch, reason=args.reason, actor=args.actor)
    if args.dry_run:
        return _envelope("rights.retract", args, status="planned", data={"revision": revision, "impacted_artifacts": before})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-retract")
    operation_id = new_id("op")
    committed = revise_record(ledger, args.asset_id, patch, reason=args.reason, actor=args.actor)
    save_ledger(root, ledger)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.retract", "asset_id": args.asset_id, "status": args.status, "reason": args.reason, "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    after = impacted_artifacts(root, args.asset_id)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.retract", "status": "succeeded", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "snapshot_id": snapshot["snapshot_id"], "impacted_artifacts": after, "created_at": now_iso()})
    return _envelope("rights.retract", args, data={"revision": committed, "snapshot": snapshot, "impacted_artifacts": after, "previous_impact": before}, operation_id=operation_id)


def command_rights_decide(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    impacted = impacted_artifacts(root, args.asset_id)
    planned_ledger = copy.deepcopy(ledger)
    decision = create_disposition_decision(planned_ledger, args.asset_id, action=args.disposition_action, status=args.status, reason=args.reason, actor=args.actor, target=args.target, replacement_asset_id=args.replacement_asset_id, impacted=impacted, supersedes_decision_id=args.supersedes_decision_id, project=project)
    impacted = decision["affected_artifacts"]
    if args.dry_run:
        return _envelope("rights.decide", args, status="planned", data={"decision": decision, "impacted_artifacts": impacted, "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-disposition")
    operation_id = new_id("op")
    committed = create_disposition_decision(ledger, args.asset_id, action=args.disposition_action, status=args.status, reason=args.reason, actor=args.actor, target=args.target, replacement_asset_id=args.replacement_asset_id, impacted=impacted, supersedes_decision_id=args.supersedes_decision_id, project=project)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.decide", "asset_id": args.asset_id, "action": args.disposition_action, "status": args.status, "decision_id": committed["decision_id"], "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.decide", "status": "succeeded", "asset_id": args.asset_id, "action": args.disposition_action, "decision_status": args.status, "decision_id": committed["decision_id"], "snapshot_id": snapshot["snapshot_id"], "impacted_artifacts": impacted, "created_at": now_iso()})
    return _envelope("rights.decide", args, data={"decision": committed, "snapshot": snapshot, "impacted_artifacts": impacted, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    if any(event.get("event") == "disposition_applied" and event.get("decision_id") == args.decision_id for event in ledger.get("events", [])):
        raise AppError("RIGHTS_DISPOSITION_ALREADY_APPLIED", "该历史处置决策已经 apply", exit_code=2, path="decision_id")
    candidate = copy.deepcopy(project)
    applied = apply_disposition_to_project(candidate, ledger, args.decision_id)
    validation = validate_project(root, candidate, strict_rights=False, target="commercial_ad")
    if not validation["ok"]:
        raise AppError("RIGHTS_DISPOSITION_APPLY_INVALID", "处置后的项目未通过结构或时间线校验", exit_code=2, path="project", cause=json.dumps(validation, ensure_ascii=False))
    rights_validation = check_project_rights(candidate, ledger, str(applied["decision"].get("target") or "commercial_ad"), strict=True)
    if not rights_validation["ok"]:
        raise AppError("RIGHTS_DISPOSITION_APPLY_RIGHTS_BLOCKED", "处置后的当前项目未通过最新权利门禁", exit_code=7, path="project", cause=json.dumps(rights_validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("rights.apply", args, status="planned", data={"applied": applied, "validation": validation, "rights_check": rights_validation, "project": str(project_file(root)), "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"before-rights-{args.decision_id}-apply")
    operation_id = new_id("op")
    applied["operation_id"] = operation_id
    ledger.setdefault("events", []).append({"event_id": new_id("rightsevent"), "event": "disposition_applied", "decision_id": args.decision_id, "asset_id": applied["asset_id"], "action": applied["action"], "replacement_asset_id": applied.get("replacement_asset_id"), "operation_id": operation_id, "snapshot_id": snapshot["snapshot_id"], "changed_clips": copy.deepcopy(applied["changed_clips"]), "removed_clips": copy.deepcopy(applied["removed_clips"]), "at": now_iso()})
    candidate.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.apply", "decision_id": args.decision_id, "asset_id": applied["asset_id"], "action": applied["action"], "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, candidate)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.apply", "status": "succeeded", "decision_id": args.decision_id, "snapshot_id": snapshot["snapshot_id"], "applied": applied, "rights_check": rights_validation, "created_at": now_iso()})
    return _envelope("rights.apply", args, data={"applied": applied, "snapshot": snapshot, "validation": validation, "rights_check": rights_validation, "project": str(project_file(root)), "ledger": str(ledger_file(root))}, operation_id=operation_id)


def _render_settings_for_args(project: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], str | None]:
    profile = getattr(args, "profile", None)
    width = getattr(args, "width", None)
    height = getattr(args, "height", None)
    if (width is None) != (height is None):
        raise argument_error("--width 与 --height 必须同时提供")
    if profile and profile != "custom" and (width is not None or height is not None):
        raise argument_error("指定预设 --profile 时不能再传 --width/--height；请使用 --profile custom")
    if profile == "custom" and width is None:
        raise argument_error("--profile custom 必须同时提供 --width 与 --height")
    if profile and profile != "custom":
        width, height = OUTPUT_PROFILES[profile]
    settings = copy.deepcopy(project["settings"])
    output_patch: dict[str, Any] = {}
    if getattr(args, "container", None) is not None:
        output_patch["container"] = args.container
    video_patch = {key: value for key, value in (("codec", getattr(args, "video_codec", None)), ("crf", getattr(args, "crf", None)), ("bitrate", getattr(args, "video_bitrate", None)), ("pixel_format", getattr(args, "pixel_format", None))) if value is not None}
    audio_patch = {key: value for key, value in (("codec", getattr(args, "audio_codec", None)), ("bitrate", getattr(args, "audio_bitrate", None))) if value is not None}
    if video_patch:
        output_patch["video"] = video_patch
    if audio_patch:
        output_patch["audio"] = audio_patch
    if output_patch:
        existing_output = settings.get("output") if isinstance(settings.get("output"), dict) else {}
        merged_output = copy.deepcopy(existing_output)
        merged_output.update({key: value for key, value in output_patch.items() if key not in {"video", "audio"}})
        for branch in ("video", "audio"):
            if branch in output_patch:
                existing_branch = merged_output.get(branch) if isinstance(merged_output.get(branch), dict) else {}
                existing_branch.update(output_patch[branch])
                merged_output[branch] = existing_branch
        settings["output"] = merged_output
    if width is None:
        normalized = output_settings(settings)
        settings["output"] = normalized
        return settings, None
    width = int(width)
    height = int(height)
    if width < 64 or height < 64 or width > 8192 or height > 8192:
        raise argument_error("输出画布必须在 64 到 8192 像素之间")
    if width % 2 or height % 2:
        raise argument_error("输出画布宽高必须是偶数，以兼容 yuv420p")
    settings["canvas"] = dict(project["settings"].get("canvas", {}))
    settings["canvas"].update({"width": width, "height": height})
    settings["output"] = output_settings(settings)
    return settings, profile or "custom"


def _load_render_resume(root: Path, project: dict[str, Any], sequence: dict[str, Any], operation_id: str) -> dict[str, Any]:
    path = root / "operations" / f"{operation_id}.json"
    if not path.exists():
        raise AppError("RESUME_OPERATION_NOT_FOUND", f"找不到可续跑的渲染操作: {operation_id}", exit_code=3, path=str(path))
    record = load_json(path)
    if record.get("command") != "render" or record.get("status") not in {"failed", "cancelled"}:
        raise AppError("RESUME_NOT_ALLOWED", "只能从 failed 或 cancelled 的 render 操作重建", exit_code=2, path=str(path))
    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    if not record.get("project_fingerprint") or not record.get("input_hashes") or not plan.get("filter_complex"):
        raise AppError("RESUME_METADATA_MISSING", "原渲染操作缺少经过验证的计划或输入指纹，拒绝盲目续跑", exit_code=2, path=str(path))
    if record.get("project_id") and record.get("project_id") != project.get("project", {}).get("id"):
        raise AppError("RESUME_PROJECT_MISMATCH", "续跑操作不属于当前项目", exit_code=2, path=str(path))
    if record.get("sequence_id") and record.get("sequence_id") != sequence.get("id"):
        raise AppError("RESUME_SEQUENCE_MISMATCH", "续跑操作不属于当前序列", exit_code=2, path=str(path))
    return record


def command_render(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    resume_record = _load_render_resume(root, project, sequence, args.resume) if args.resume else None
    settings_overridden = any(getattr(args, field, None) is not None for field in ("profile", "width", "height", "container", "video_codec", "audio_codec", "crf", "video_bitrate", "audio_bitrate", "pixel_format"))
    if resume_record:
        if args.output is None:
            args.output = resume_record.get("output")
    report = validate_project(root, project, strict_rights=args.publish, target="commercial_ad")
    if not report["ok"]:
        raise AppError("PROJECT_INVALID", "项目验证失败，拒绝渲染", exit_code=7 if args.publish else 2, cause=json.dumps(report, ensure_ascii=False))
    if resume_record and not settings_overridden and isinstance(resume_record.get("settings"), dict):
        render_settings, profile = copy.deepcopy(resume_record["settings"]), resume_record.get("profile")
    else:
        render_settings, profile = _render_settings_for_args(project, args)
    if resume_record:
        current_fingerprints = render_fingerprints(project, sequence, render_settings, root)
        if current_fingerprints.get("project_fingerprint") != resume_record.get("project_fingerprint") or current_fingerprints.get("input_hashes") != resume_record.get("input_hashes"):
            raise AppError("RESUME_INPUT_CHANGED", "项目、素材哈希或输出设置已变化，拒绝续跑", exit_code=2, path=str(root / "operations" / f"{args.resume}.json"), retryable=False)
    container = str(render_settings.get("output", {}).get("container", "mp4")) if isinstance(render_settings.get("output"), dict) else "mp4"
    default_extension = {"mp4": ".mp4", "webm": ".webm", "mkv": ".mkv"}.get(container, ".mp4")
    output = Path(args.output).expanduser().resolve() if args.output else root / "renders" / f"{sequence['id']}_{new_id('render')}{default_extension}"
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise argument_error("输出路径必须位于项目目录内", str(output)) from exc
    cancel_file = Path(args.cancel_file).expanduser().resolve() if args.cancel_file else None
    progress_callback = None
    if getattr(args, "progress", "none") == "jsonl":
        progress_callback = lambda operation_id, event_type, percent, message: _progress(args, operation_id, event_type, "render", percent, message)
    result = render_project(root, project, sequence, output, dry_run=args.dry_run, render_settings=render_settings, profile=profile, cancel_file=cancel_file, progress_callback=progress_callback, resume_of=args.resume)
    if result.get("status") == "planned":
        return _envelope("render", args, status="planned", data=result)
    encoder = render_settings.get("output", {}) if isinstance(render_settings.get("output"), dict) else {}
    project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": container, "profile": profile, "canvas": render_settings.get("canvas", {}), "video": encoder.get("video", {}), "audio": encoder.get("audio", {}), "target_platform": "generic"})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "render", "at": now_iso(), "output": str(output), "manifest": result.get("manifest")})
    save_project(root, project)
    _operation(root, result.get("operation_id", new_id("op")), {"operation_id": result.get("operation_id"), "command": "render", "status": "succeeded", "output": str(output), "manifest": result.get("manifest"), "warnings": result.get("warnings", []), "profile": profile, "settings": render_settings, "project_id": project["project"]["id"], "sequence_id": sequence["id"], "project_fingerprint": result.get("project_fingerprint"), "input_hashes": result.get("input_hashes", {}), "resume_of": args.resume, "created_at": now_iso()})
    return _envelope("render", args, data=result, operation_id=result.get("operation_id"), warnings=report.get("warnings", []) + result.get("warnings", []))


def _queue_counts(queue: dict[str, Any]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(JOB_STATUSES)}
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("status") in counts:
            counts[str(job["status"])] += 1
    return counts


def _queue_job_args(root: Path, job: dict[str, Any], args: argparse.Namespace) -> argparse.Namespace:
    """Map a persisted job to the render settings contract without shell parsing."""
    return argparse.Namespace(
        profile=job.get("profile"),
        width=job.get("width"),
        height=job.get("height"),
        container=job.get("container"),
        video_codec=job.get("video_codec"),
        audio_codec=job.get("audio_codec"),
        crf=job.get("crf"),
        video_bitrate=job.get("video_bitrate"),
        audio_bitrate=job.get("audio_bitrate"),
        pixel_format=job.get("pixel_format"),
        output=str(root / str(job["output"])),
        publish=bool(job.get("publish", False)),
        sequence_id=job.get("sequence_id"),
        cancel_file=str(cancel_path(root, str(job["job_id"]))),
        resume=None,
        dry_run=False,
        progress=getattr(args, "progress", "none"),
    )


def command_queue_enqueue(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    payload = load_json(Path(args.input).expanduser().resolve())
    if args.dry_run:
        queue = load_queue(root, project_id=project["project"]["id"])
        raw_jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else [payload]
        if not raw_jobs:
            raise argument_error("渲染队列作业不能为空")
        existing = {str(job.get("job_id")) for job in queue.get("jobs", []) if isinstance(job, dict)}
        planned: list[dict[str, Any]] = []
        for raw in raw_jobs:
            job = normalize_job(root, raw)
            if job["job_id"] in existing:
                raise argument_error(f"队列作业 ID 已存在: {job['job_id']}", "job_id")
            existing.add(job["job_id"])
            planned.append(job)
        return _envelope("queue.enqueue", args, status="planned", data={"queue": str(queue_path(root)), "jobs": planned, "count": len(planned)})
    queue, added = enqueue_render_jobs(root, project["project"]["id"], payload)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "queue.enqueue", "status": "succeeded", "project_id": project["project"]["id"], "queue": str(queue_path(root)), "jobs": [job["job_id"] for job in added], "created_at": now_iso()})
    return _envelope("queue.enqueue", args, data={"queue": str(queue_path(root)), "jobs": added, "count": len(added), "counts": _queue_counts(queue)}, operation_id=operation_id)


def _queue_job_view(root: Path, job: dict[str, Any]) -> dict[str, Any]:
    """Expose an atomic cancellation marker without mutating queue state."""
    view = copy.deepcopy(job)
    marker = cancel_path(root, str(view["job_id"]))
    if marker.exists():
        view["cancel_requested"] = True
        view["cancel_marker"] = str(marker)
    return view


def command_queue_list(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    jobs = [_queue_job_view(root, job) for job in queue.get("jobs", []) if isinstance(job, dict) and (args.status is None or job.get("status") == args.status)]
    return _envelope("queue.list", args, data={"queue": str(queue_path(root)), "queue_version": queue.get("queue_version"), "project_id": project["project"]["id"], "counts": _queue_counts(queue), "jobs": jobs})


def command_queue_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    job = find_job(queue, args.job_id)
    return _envelope("queue.inspect", args, data={"queue": str(queue_path(root)), "job": _queue_job_view(root, job)})


def command_queue_cancel(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    job = find_job(queue, args.job_id)
    status = str(job.get("status"))
    marker = cancel_path(root, args.job_id)
    if status == "succeeded":
        raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
    if status == "failed":
        raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
    if args.dry_run:
        return _envelope("queue.cancel", args, status="planned", data={"queue": str(queue_path(root)), "job_id": args.job_id, "status": status, "marker": str(marker)})
    acknowledged = False
    confirmed = False
    try:
        # This short channel lock arbitrates marker writes with queue start and
        # finalization. It is never held during FFmpeg rendering.
        with queue_cancel_lock(root, timeout=2.0):
            _, project = load_project(root)
            queue = load_queue(root, project_id=project["project"]["id"])
            job = find_job(queue, args.job_id)
            status = str(job.get("status"))
            if status == "succeeded":
                raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
            if status == "failed":
                raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
            if status == "pending":
                try:
                    with project_write_lock(root):
                        _, latest_project = load_project(root)
                        latest_queue = load_queue(root, project_id=latest_project["project"]["id"])
                        job = find_job(latest_queue, args.job_id)
                        if job.get("status") == "pending":
                            set_status(job, "cancelled")
                            job["cancel_requested"] = True
                            save_queue(root, latest_queue)
                            queue = latest_queue
                            project = latest_project
                            acknowledged = True
                            confirmed = True
                        elif job.get("status") == "running":
                            atomic_write_text(marker, "cancel_requested\n")
                            acknowledged = True
                        elif job.get("status") == "cancelled":
                            marker.unlink(missing_ok=True)
                            acknowledged = True
                            confirmed = True
                        elif job.get("status") == "succeeded":
                            raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
                        elif job.get("status") == "failed":
                            raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
                except AppError as exc:
                    if exc.code != "PROJECT_WRITE_LOCKED":
                        raise
                    atomic_write_text(marker, "cancel_requested\n")
                    acknowledged = True
                    confirmed = False
                    job["cancel_requested"] = True
            elif status == "running":
                atomic_write_text(marker, "cancel_requested\n")
                acknowledged = True
                confirmed = False
            else:
                # Repeating a cancellation request is idempotent for an already cancelled job.
                marker.unlink(missing_ok=True)
                acknowledged = True
                confirmed = True
    except AppError as exc:
        if exc.code != "QUEUE_CANCEL_CHANNEL_BUSY":
            raise
        # The finalization window is intentionally short. If another process
        # still owns it, preserve the request as a marker for the next state
        # observation instead of overwriting queue JSON from a stale snapshot.
        atomic_write_text(marker, "cancel_requested\n")
        acknowledged = True
        confirmed = False
        job["cancel_requested"] = True
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "queue.cancel", "status": "succeeded", "project_id": project["project"]["id"], "job_id": args.job_id, "job_status": job.get("status"), "acknowledged": acknowledged, "confirmed": confirmed, "cancel_marker": str(marker) if marker.exists() else None, "created_at": now_iso()})
    return _envelope("queue.cancel", args, data={"queue": str(queue_path(root)), "job": job, "marker": str(marker) if marker.exists() else None, "acknowledged": acknowledged, "confirmed": confirmed}, operation_id=operation_id)


def command_queue_run(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    if args.job_id:
        selected = [find_job(queue, args.job_id)]
        if selected[0].get("status") not in {"pending", "failed", "cancelled"}:
            raise AppError("QUEUE_JOB_STATE_INVALID", "指定作业必须处于 pending、failed 或 cancelled 状态", exit_code=2, path=args.job_id)
    else:
        selected = [job for job in queue.get("jobs", []) if isinstance(job, dict) and job.get("status") == "pending"]
        if args.max_jobs is not None:
            if args.max_jobs <= 0:
                raise argument_error("--max-jobs 必须大于 0", "--max-jobs")
            selected = selected[:args.max_jobs]
    if args.dry_run:
        return _envelope("queue.run", args, status="planned", data={"queue": str(queue_path(root)), "jobs": [job.get("job_id") for job in selected], "count": len(selected), "continue_on_error": bool(args.continue_on_error)})

    queue_operation_id = new_id("op")
    summary = {"selected": len(selected), "succeeded": 0, "failed": 0, "cancelled": 0, "skipped": 0}
    errors: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    for job in selected:
        job_id = str(job["job_id"])
        marker = cancel_path(root, job_id)
        with queue_cancel_lock(root, timeout=2.0):
            # A marker on a pending job is a new cancellation request, even
            # when the caller names that job explicitly. A cancelled/failed job
            # with an explicit ID is a retry authorization and clears an old
            # marker before starting; a new marker written after this point
            # remains effective.
            if marker.exists() and job.get("status") == "pending":
                set_status(job, "cancelled")
                job["cancel_requested"] = True
                summary["cancelled"] += 1
                job_results.append({"job_id": job_id, "status": "cancelled", "reason": "cancel marker exists before start"})
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
                continue
            marker.unlink(missing_ok=True)
            job["attempts"] = int(job.get("attempts", 0)) + 1
            job["cancel_requested"] = False
            job["operation_id"] = None
            set_status(job, "running")
            save_queue(root, queue)
        try:
            sequence = find_sequence(project, job.get("sequence_id"))
            report = validate_project(root, project, strict_rights=bool(job.get("publish", False)), target="commercial_ad")
            if not report["ok"]:
                raise AppError("PROJECT_INVALID", "项目验证失败，拒绝执行队列作业", exit_code=7 if job.get("publish") else 2, cause=json.dumps(report, ensure_ascii=False))
            render_args = _queue_job_args(root, job, args)
            render_settings, profile = _render_settings_for_args(project, render_args)
            output = ensure_inside(root, root / str(job["output"]))
            progress_callback = None
            if getattr(args, "progress", "none") == "jsonl":
                progress_callback = lambda operation_id, event_type, percent, message: _progress(args, operation_id, event_type, "queue.render", percent, message)
            result = render_project(root, project, sequence, output, dry_run=False, render_settings=render_settings, profile=profile, cancel_file=marker, progress_callback=progress_callback)
            with queue_cancel_lock(root, timeout=2.0):
                if marker.exists():
                    raise AppError("CANCELLED", "队列作业在渲染完成提交前收到取消请求", exit_code=8, path=str(marker))
                encoder = render_settings.get("output", {}) if isinstance(render_settings.get("output"), dict) else {}
                project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": encoder.get("container", job.get("container", "mp4")), "profile": profile, "canvas": render_settings.get("canvas", {}), "video": encoder.get("video", {}), "audio": encoder.get("audio", {}), "target_platform": "generic"})
                project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "queue.run", "queue_job_id": job_id, "at": now_iso(), "output": str(output), "manifest": result.get("manifest")})
                save_project(root, project)
                _operation(root, result.get("operation_id", new_id("op")), {"operation_id": result.get("operation_id"), "command": "render", "queue_job_id": job_id, "status": "succeeded", "output": str(output), "manifest": result.get("manifest"), "warnings": result.get("warnings", []), "profile": profile, "settings": render_settings, "project_id": project["project"]["id"], "sequence_id": sequence["id"], "project_fingerprint": result.get("project_fingerprint"), "input_hashes": result.get("input_hashes", {}), "created_at": now_iso()})
                queue_warnings = report.get("warnings", []) + result.get("warnings", [])
                job["warnings"] = queue_warnings
                set_status(job, "succeeded", operation_id=result.get("operation_id"))
                summary["succeeded"] += 1
                job_results.append({"job_id": job_id, "status": "succeeded", "operation_id": result.get("operation_id"), "path": str(output), "warnings": queue_warnings})
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
        except AppError as exc:
            error = exc.as_dict()
            set_status(job, "cancelled" if exc.code == "CANCELLED" else "failed", error=error, operation_id=exc.operation_id)
            summary["cancelled" if exc.code == "CANCELLED" else "failed"] += 1
            errors.append({"job_id": job_id, **error})
            job_results.append({"job_id": job_id, "status": job["status"], "error": error})
            with queue_cancel_lock(root, timeout=2.0):
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
            if exc.code != "CANCELLED" and not args.continue_on_error:
                break

    final_status = "succeeded" if not errors and summary["cancelled"] == 0 else "partial"
    _operation(root, queue_operation_id, {"operation_id": queue_operation_id, "command": "queue.run", "status": final_status, "project_id": project["project"]["id"], "summary": summary, "jobs": job_results, "created_at": now_iso()})
    return _envelope("queue.run", args, data={"queue": str(queue_path(root)), "summary": summary, "jobs": job_results, "counts": _queue_counts(queue)}, status=final_status, errors=errors, operation_id=queue_operation_id)


def command_quality_check(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("质量检查输入不存在", str(media))
    sequence = find_sequence(project, args.sequence_id) if args.sequence_id else None
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    expected_duration = (int(sequence["duration_tick"]) / tps) if sequence else None
    quality_settings, profile = _render_settings_for_args(project, args)
    if args.dry_run:
        return _envelope("quality.check", args, status="planned", data={"input": str(media), "expected_duration": expected_duration, "expensive": bool(args.expensive), "require_audio": bool(args.require_audio), "max_av_sync_ms": args.max_av_sync_ms, "target_lufs": args.target_lufs, "lufs_tolerance": args.lufs_tolerance, "fail_on_black": bool(args.fail_on_black), "max_true_peak_dbfs": args.max_true_peak_dbfs, "profile": profile, "settings": quality_settings})
    result = check_output(media, quality_settings, expected_duration, require_audio=args.require_audio, run_expensive=args.expensive, max_av_sync_ms=args.max_av_sync_ms, target_lufs=args.target_lufs, lufs_tolerance=args.lufs_tolerance, fail_on_black=args.fail_on_black, max_true_peak_dbfs=args.max_true_peak_dbfs)
    report_path = Path(args.report).expanduser().resolve() if args.report else root / "validation" / f"quality_{new_id('run')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "input": str(media), "profile": profile, "settings": quality_settings, **result})
    status = "succeeded" if result["ok"] else "failed"
    return _envelope("quality.check", args, data={"report": str(report_path), **result}, status=status, warnings=result.get("warnings", []), errors=result.get("errors", []))


def command_quality_golden(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("golden 质量输入不存在", str(media))
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else root / "validation" / "golden-quality.json"
    ensure_inside(root, manifest_path)
    existing_manifest: dict[str, Any] | None = None
    if args.mode == "verify":
        if not manifest_path.exists() or not manifest_path.is_file():
            return _envelope("quality.golden", args, status="failed", data={"manifest": str(manifest_path), "mode": args.mode}, errors=[{"code": "QUALITY_GOLDEN_MISSING", "message": f"找不到 golden 清单: {manifest_path}"}])
        existing_manifest = load_json(manifest_path)
        manifest_errors = validate_golden_manifest(existing_manifest)
        if manifest_errors:
            return _envelope("quality.golden", args, status="failed", data={"manifest": str(manifest_path), "mode": args.mode, "golden_version": existing_manifest.get("golden_version")}, errors=manifest_errors)
        if args.sequence_id is None and existing_manifest.get("sequence_id"):
            args.sequence_id = existing_manifest.get("sequence_id")
        if args.profile is None and existing_manifest.get("profile"):
            args.profile = existing_manifest.get("profile")
            if args.profile == "custom":
                canvas = existing_manifest.get("canvas") if isinstance(existing_manifest.get("canvas"), dict) else {}
                args.width = canvas.get("width")
                args.height = canvas.get("height")
    sequence = find_sequence(project, args.sequence_id) if args.sequence_id else None
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    expected_duration = (int(sequence["duration_tick"]) / tps) if sequence else None
    if args.mode == "verify" and expected_duration is None and existing_manifest is not None:
        stored_expected = existing_manifest.get("expected_duration_seconds")
        expected_duration = float(stored_expected) if stored_expected is not None else None
    quality_settings, profile = _render_settings_for_args(project, args)
    overrides = {"require_audio": args.require_audio, "expensive": args.expensive, "max_av_sync_ms": args.max_av_sync_ms, "target_lufs": args.target_lufs, "lufs_tolerance": args.lufs_tolerance, "fail_on_black": args.fail_on_black, "max_true_peak_dbfs": args.max_true_peak_dbfs}
    constraints = normalize_golden_constraints(existing_manifest.get("constraints") if existing_manifest else None, overrides)
    if args.dry_run:
        return _envelope("quality.golden", args, status="planned", data={"mode": args.mode, "manifest": str(manifest_path), "input": str(media), "sequence_id": args.sequence_id, "expected_duration": expected_duration, "golden_version": GOLDEN_VERSION, "profile": profile, "settings": quality_settings, "constraints": constraints})
    result = check_output(media, quality_settings, expected_duration, require_audio=constraints["require_audio"], run_expensive=constraints["expensive"], max_av_sync_ms=constraints["max_av_sync_ms"], target_lufs=constraints["target_lufs"], lufs_tolerance=constraints["lufs_tolerance"], fail_on_black=constraints["fail_on_black"], max_true_peak_dbfs=constraints["max_true_peak_dbfs"])
    if args.mode == "capture":
        if not result["ok"]:
            return _envelope("quality.golden", args, status="failed", data={"mode": args.mode, "manifest": str(manifest_path), **result}, warnings=result.get("warnings", []), errors=result.get("errors", []))
        manifest = build_golden_manifest(media, project_id=project["project"]["id"], sequence_id=args.sequence_id, expected_duration=expected_duration, settings=quality_settings, profile=profile, result=result, constraints=constraints)
        manifest["created_at"] = now_iso()
        atomic_write_json(manifest_path, manifest)
        operation_id = new_id("op")
        _operation(root, operation_id, {"operation_id": operation_id, "command": "quality.golden", "mode": "capture", "status": "succeeded", "manifest": str(manifest_path), "created_at": now_iso()})
        return _envelope("quality.golden", args, data={"mode": args.mode, "manifest": str(manifest_path), "golden_version": GOLDEN_VERSION, **result}, operation_id=operation_id, warnings=result.get("warnings", []))
    mismatches = compare_golden_manifest(existing_manifest or {}, media, project_id=project["project"]["id"], settings=quality_settings, result=result)
    stored_expected = (existing_manifest or {}).get("expected_duration_seconds")
    if stored_expected is not None and expected_duration is not None and abs(float(stored_expected) - float(expected_duration)) > 0.001:
        mismatches.append({"code": "QUALITY_GOLDEN_EXPECTED_DURATION_MISMATCH", "expected": stored_expected, "actual": expected_duration, "tolerance": 0.001})
    errors = list(result.get("errors", [])) + mismatches
    status = "succeeded" if not errors else "failed"
    return _envelope("quality.golden", args, data={"mode": args.mode, "manifest": str(manifest_path), "golden_version": GOLDEN_VERSION, "mismatches": mismatches, **result}, status=status, warnings=result.get("warnings", []), errors=errors)


def command_quality_scopes(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("色彩 scope 输入不存在", str(media))
    scope_id = new_id("scope")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else root / "cache" / "scopes" / scope_id
    try:
        output_dir.relative_to(root)
    except ValueError as exc:
        raise argument_error("scope 输出目录必须位于项目目录内", str(output_dir)) from exc
    if args.dry_run:
        return _envelope("quality.scopes", args, status="planned", data={"input": str(media), "output_dir": str(output_dir), "at_seconds": args.at_seconds, "scope_types": ["waveform", "vectorscope", "histogram"]})
    result = generate_scopes(media, output_dir, at_seconds=args.at_seconds)
    report_path = root / "validation" / f"scopes_{scope_id}.json"
    atomic_write_json(report_path, {"report_version": SCOPE_VERSION, "created_at": now_iso(), "project_id": project["project"]["id"], **result})
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "quality.scopes", "status": "succeeded", "report": str(report_path), "artifacts": result["artifacts"], "created_at": now_iso()})
    return _envelope("quality.scopes", args, data={"report": str(report_path), **result}, operation_id=operation_id)


def command_convert_import(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    destination = Path(args.output).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("转换输入不存在", str(source))
    if destination.exists() and any(destination.iterdir()):
        raise argument_error("转换输出目录必须不存在或为空", str(destination))
    if args.dry_run:
        return _envelope("convert.import", args, status="planned", data={"input": str(source), "output": str(destination), "format": source.suffix.lower()})
    try:
        result = import_external(source, destination)
    except ValueError as exc:
        raise argument_error(str(exc), str(source)) from exc
    report = result["report_data"]
    status = "succeeded" if not report.get("failures") else "failed"
    return _envelope("convert.import", args, data=result, status=status, warnings=report.get("warnings", []), errors=report.get("failures", []))


def command_convert_export(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    output = Path(args.output).expanduser().resolve()
    if args.dry_run:
        return _envelope("convert.export", args, status="planned", data={"project": str(root), "output": str(output), "format": args.target_format})
    try:
        result = export_external(root, project, output, args.target_format)
    except ValueError as exc:
        raise argument_error(str(exc), "--target-format") from exc
    return _envelope("convert.export", args, data=result)


def command_template_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    template = load_json(Path(args.input))
    variables = load_json(Path(args.variables)) if args.variables else {}
    if not isinstance(variables, dict):
        raise argument_error("模板变量必须是 JSON 对象", "--variables")
    try:
        resolved = instantiate(template, variables)
    except (KeyError, ValueError) as exc:
        raise argument_error(str(exc), str(Path(args.input))) from exc
    operations = resolved.get("operations") or resolved.get("changes") or []
    if not isinstance(operations, list):
        raise argument_error("模板 operations/changes 必须是数组")
    if args.dry_run:
        return _envelope("template.apply", args, status="planned", data={"template_id": template.get("id"), "version": template.get("version"), "operations": operations, "variables": variables})
    applied = apply_template_operations(project, operations, resolved.get("sequence_id"))
    snapshot = resolved.get("template_snapshot", {"id": template.get("id"), "version": template.get("version"), "variables": variables})
    snapshot_variables = resolved.get("template_snapshot", {}).get("variables", variables)
    project.setdefault("templates", []).append({"id": template.get("id") or new_id("template"), "version": template.get("version", "0.0.0"), "variables": [{"name": key, "value": value} for key, value in snapshot_variables.items()], "assets": sorted({item.get("clip", {}).get("asset_id") for item in applied if isinstance(item.get("clip"), dict) and item.get("clip", {}).get("asset_id")})})
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "template.apply", "template_snapshot": snapshot, "applied": applied, "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "template.apply", "status": "succeeded", "template_snapshot": snapshot, "applied": applied, "created_at": now_iso()})
    return _envelope("template.apply", args, data={"template_snapshot": snapshot, "applied": applied}, operation_id=operation_id)


def command_template_batch(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    template = load_json(Path(args.input))
    variables_path = Path(args.variables).expanduser().resolve()
    variants = _load_variants(variables_path)
    output_root = Path(args.output).expanduser().resolve()
    if args.dry_run:
        return _envelope("template.batch", args, status="planned", data={"template_id": template.get("id"), "variant_count": len(variants), "output_root": str(output_root), "publish": bool(args.publish)})
    report = run_template_batch(root, template, variants, output_root, publish=args.publish, continue_on_error=args.continue_on_error)
    report_path = root / "validation" / f"batch_{new_id('report')}.json"
    atomic_write_json(report_path, report)
    status = "succeeded" if report["failed"] == 0 else "failed"
    return _envelope("template.batch", args, data={"report": str(report_path), **report}, status=status, errors=[item for item in report["variants"] if item["status"] != "succeeded"])


def command_library_index(args: argparse.Namespace) -> dict[str, Any]:
    source_root = Path(args.root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise argument_error("素材库根目录不存在", str(source_root))
    if args.incremental and not args.previous:
        raise argument_error("--incremental 必须同时提供 --previous 上一版目录", "--previous")
    previous_catalog = None
    if args.previous:
        previous_path = Path(args.previous).expanduser().resolve()
        previous_catalog = load_json(previous_path)
        previous_root = Path(str(previous_catalog.get("root", ""))).expanduser().resolve()
        if previous_root != source_root:
            raise argument_error("增量目录的 root 必须与 --root 相同", str(previous_path))
    incremental = bool(args.incremental or args.previous)
    if args.dry_run:
        return _envelope("library.index", args, status="planned", data={"root": str(source_root), "output": str(output), "max_files": args.max_files, "incremental": incremental, "previous": str(Path(args.previous).expanduser().resolve()) if args.previous else None, "visual_hash": bool(args.visual_hash)})
    catalog = index_directory(
        source_root,
        output,
        max_files=args.max_files,
        license_spdx=args.license_spdx,
        verification_status=args.verification_status,
        previous_catalog=previous_catalog,
        incremental=incremental,
        include_visual_hash=bool(args.visual_hash),
    )
    return _envelope("library.index", args, data={"catalog": str(output), "indexed_count": catalog["indexed_count"], "error_count": len(catalog["errors"]), "warning_count": len(catalog.get("warnings", [])), "index_refresh": catalog.get("index_refresh", {})})


def command_library_search(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    results = search_catalog(
        catalog,
        query=args.query,
        kind=args.kind,
        verification_status=args.verification_status,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        min_width=args.min_width,
        min_height=args.min_height,
        has_audio=args.has_audio,
        duplicate_only=args.duplicate_only,
        limit=args.limit,
    )
    return _envelope("library.search", args, data={"catalog": str(catalog_path), "count": len(results), "results": results, "search": {"source": "deterministic-local", "vector_index": False}})


def command_library_duplicates(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    groups = duplicate_groups(catalog, include_unique=args.include_unique)
    return _envelope("library.duplicates", args, data={"catalog": str(catalog_path), "count": len(groups), "groups": groups, "method": "sha256-exact"})


def command_library_similar(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    groups = visual_similarity_groups(catalog, max_distance=args.max_distance)
    visual_count = sum(
        1
        for record in catalog.get("records", [])
        if isinstance(record, dict)
        and isinstance(record.get("semantic"), dict)
        and isinstance(record["semantic"].get("visual_hash"), dict)
    )
    return _envelope(
        "library.similar",
        args,
        data={"catalog": str(catalog_path), "count": len(groups), "groups": groups, "method": "ahash-v1", "visual_hash_records": visual_count, "max_distance": max(0, int(args.max_distance))},
        warnings=[] if visual_count else [{"code": "VISUAL_HASH_UNAVAILABLE", "message": "目录未包含视觉哈希；请重新执行 library index --visual-hash"}],
    )


def command_lut_register(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source = Path(args.input).expanduser().resolve()
    registration = prepare_lut_registration(root, source, lut_id=args.lut_id, name=args.name)
    preview = {key: value for key, value in registration.items() if key != "_source_path"}
    rights_record = {
        "asset_id": registration["id"],
        "kind": "lut",
        "sha256": registration["sha256"],
        "source_url": registration["source"]["source_url"],
        "source_version": "local",
        "retrieved_at": registration["registered_at"],
        "creator": args.creator,
        "license_spdx": args.license_spdx,
        "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
        "attribution": "",
        "permitted_uses": list(dict.fromkeys(args.permitted_use)),
        "restrictions": [],
        "evidence": require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else registration["source"]["source_url"]),
        "verification_status": args.verification_status,
        "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "",
        "takedown_status": "clear",
        "notes": "Registered by local LUT library CLI",
    }
    if args.dry_run:
        return _envelope("lut.register", args, status="planned", data={"lut": preview, "rights_record": rights_record})
    snapshot = create_snapshot(root, project, label="before-lut-register")
    registered = register_lut(root, registration)
    ledger = load_ledger(root)
    add_record(ledger, rights_record)
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({
        "operation_id": operation_id,
        "command": "lut.register",
        "lut_id": registered["id"],
        "sha256": registered["sha256"],
        "before_snapshot_id": snapshot["snapshot_id"],
        "at": now_iso(),
    })
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "lut.register", "status": "succeeded", "lut_id": registered["id"], "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("lut.register", args, data={"lut": registered, "rights": rights_record, "snapshot": snapshot, "library": str(root / "assets" / "lut-library.json")}, operation_id=operation_id)


def command_lut_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    records = list_luts(root, query=args.query)
    return _envelope("lut.list", args, data={"library": str(root / "assets" / "lut-library.json"), "library_version": "0.1.0", "count": len(records), "luts": records, "network": "disabled"})


def command_lut_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    return _envelope("lut.inspect", args, data=inspect_lut(root, args.lut_id))


def command_doctor(args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, Any] = {"platform": platform.platform(), "python": sys.version.split()[0], "native_windows": os.name == "nt", "network_default": "disabled", "virtualization_commands": {}}
    checks["runtime_storage"] = configure_local_runtime()
    for name in ("ffmpeg", "ffprobe", "docker", "wsl", "cargo", "node"):
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"] = checks.get("virtualization_commands" if name in {"docker", "wsl"} else "tools", {})
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"][name] = shutil.which(name)
    checks["ffmpeg_version"] = ffmpeg_version() if checks["tools"].get("ffmpeg") else None
    checks["local_features"] = {"flite_tts": flite_available() if checks["tools"].get("ffmpeg") else False}
    checks["policy"] = {"docker_or_wsl_started": False, "closed_services_enabled": False, "jianying_runtime_enabled": False}
    if args.project:
        policy_report = audit_local_tree(Path(args.project))
        checks["project_policy"] = policy_report
    ok = bool(checks["native_windows"] and checks["tools"].get("ffmpeg") and checks["tools"].get("ffprobe"))
    return _envelope("doctor", args, data={"ok": ok, "checks": checks}, status="succeeded" if ok else "failed", errors=[] if ok else [{"code": "DEPENDENCY_UNAVAILABLE", "message": "FFmpeg/FFprobe 不完整", "retryable": False}])


def command_operation_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    path = root / "operations" / f"{args.operation_id}.json"
    if not path.exists():
        raise AppError("OPERATION_NOT_FOUND", f"找不到操作记录: {args.operation_id}", exit_code=3, path=str(path))
    return _envelope("operation.inspect", args, data={"path": str(path), "operation": load_json(path)})


def command_version(args: argparse.Namespace) -> dict[str, Any]:
    return _envelope("version", args, data={"cli_version": VERSION, "schema_version": SCHEMA_VERSION, "engine": ENGINE_ID, "runtime": "python+ffmpeg-local", "network": "disabled"})


def command_capabilities(args: argparse.Namespace) -> dict[str, Any]:
    return _envelope("capabilities", args, data=build_capability_manifest())


def command_policy_audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project).expanduser().resolve()
    report = audit_local_tree(root)
    error = policy_error_from_findings(report)
    if error:
        return _envelope("policy.audit", args, data=report, status="failed", errors=[error.as_dict()])
    return _envelope("policy.audit", args, data=report)


def _idempotency_context(args: argparse.Namespace) -> tuple[Path, Path, str] | None:
    key = getattr(args, "idempotency_key", None)
    project_value = getattr(args, "project", None)
    if not key or getattr(args, "dry_run", False) or not project_value:
        return None
    root = Path(project_value).expanduser().resolve()
    if root.suffix.lower() == ".json" and root.name.lower() == "project.json":
        root = root.parent
    command = _command_name(args)
    return root, idempotency_record_path(root, command, str(key)), request_fingerprint(command, args)


_READ_ONLY_PROJECT_COMMANDS = {
    ("project", "inspect"),
    ("operation", "inspect"),
    ("queue", "list"),
    ("queue", "inspect"),
    ("lut", "list"),
    ("lut", "inspect"),
    ("rights", "check"),
    ("rights", "list"),
    ("rights", "history"),
    ("rights", "impact"),
    ("validate", None),
    ("policy", "audit"),
    ("quality", "check"),
    ("motion", "list"),
    ("motion", "inspect"),
}


def _project_operation_lock(args: argparse.Namespace):
    """Return the operation-wide lock for a mutating project command."""
    project = getattr(args, "project", None)
    key = (getattr(args, "domain", None), getattr(args, "action", None))
    if not project or getattr(args, "dry_run", False) or key in _READ_ONLY_PROJECT_COMMANDS or key == ("queue", "cancel"):
        return contextlib.nullcontext()
    return project_write_lock(project)


COMMANDS: dict[tuple[str, str | None], Callable[[argparse.Namespace], dict[str, Any]]] = {
    ("project", "init"): command_project_init,
    ("project", "inspect"): command_project_inspect,
    ("project", "snapshot"): command_project_snapshot,
    ("project", "restore"): command_project_restore,
    ("project", "migrate"): command_project_migrate,
    ("project", "recover"): command_project_recover,
    ("media", "ingest"): command_media_ingest,
    ("media", "stabilize"): command_media_stabilize,
    ("media", "relink"): command_media_relink,
    ("media", "track"): command_media_track,
    ("media", "reframe"): command_media_reframe,
    ("media", "understand"): command_media_understand,
    ("media", "prepare"): command_media_prepare,
    ("media", "highlights"): command_media_highlights,
    ("media", "beat-cut"): command_media_beat_cut,
    ("media", "smart-cut"): command_media_smart_cut,
    ("ad", "plan"): command_ad_plan,
    ("ad", "apply"): command_ad_apply,
    ("subtitle", "validate"): command_subtitle_validate,
    ("subtitle", "normalize"): command_subtitle_normalize,
    ("tts", "synthesize"): command_tts_synthesize,
    ("effects", "list"): command_effects_list,
    ("effects", "inspect"): command_effects_inspect,
    ("motion", "list"): command_motion_list,
    ("motion", "inspect"): command_motion_inspect,
    ("motion", "apply"): command_motion_apply,
    ("timeline", "compose"): command_timeline_compose,
    ("validate", None): command_validate,
    ("rights", "check"): command_rights_check,
    ("rights", "list"): command_rights_list,
    ("rights", "history"): command_rights_history,
    ("rights", "update"): command_rights_update,
    ("rights", "export"): command_rights_export,
    ("rights", "batch-update"): command_rights_batch_update,
    ("rights", "impact"): command_rights_impact,
    ("rights", "retract"): command_rights_retract,
    ("rights", "decide"): command_rights_decide,
    ("rights", "apply"): command_rights_apply,
    ("render", None): command_render,
    ("queue", "enqueue"): command_queue_enqueue,
    ("queue", "list"): command_queue_list,
    ("queue", "inspect"): command_queue_inspect,
    ("queue", "run"): command_queue_run,
    ("queue", "cancel"): command_queue_cancel,
    ("quality", "check"): command_quality_check,
    ("quality", "golden"): command_quality_golden,
    ("quality", "scopes"): command_quality_scopes,
    ("convert", "import"): command_convert_import,
    ("convert", "export"): command_convert_export,
    ("template", "apply"): command_template_apply,
    ("template", "batch"): command_template_batch,
    ("library", "index"): command_library_index,
    ("library", "search"): command_library_search,
    ("library", "duplicates"): command_library_duplicates,
    ("library", "similar"): command_library_similar,
    ("lut", "register"): command_lut_register,
    ("lut", "list"): command_lut_list,
    ("lut", "inspect"): command_lut_inspect,
    ("doctor", None): command_doctor,
    ("operation", "inspect"): command_operation_inspect,
    ("version", None): command_version,
    ("capabilities", None): command_capabilities,
    ("policy", "audit"): command_policy_audit,
}


def main(argv: list[str] | None = None) -> int:
    # Agent pipe consumers use UTF-8 regardless of the Windows console locale.
    # Keep in-memory streams used by embedding callers unchanged.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        configure_local_runtime()
        handler = COMMANDS[(args.domain, getattr(args, "action", None))]
        replayed = False
        idempotency = _idempotency_context(args)
        with _project_operation_lock(args):
            transaction_root = getattr(args, "project", None)
            command_key = (args.domain, getattr(args, "action", None))
            transaction_enabled = bool(transaction_root) and not getattr(args, "dry_run", False) and command_key not in _READ_ONLY_PROJECT_COMMANDS and command_key not in {("project", "recover"), ("queue", "cancel")}
            with (project_transaction(transaction_root, command=_command_name(args)) if transaction_enabled else contextlib.nullcontext({"active": False, "recovered": False})) as transaction:
                if idempotency:
                    root, record_path, fingerprint = idempotency
                    if record_path.exists():
                        record = load_json(record_path)
                        if record.get("fingerprint") != fingerprint:
                            raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已经绑定到不同请求", exit_code=2, path=str(record_path))
                        result = json.loads(json.dumps(record.get("response", {}), ensure_ascii=False))
                        result.setdefault("warnings", []).append({"code": "IDEMPOTENT_REPLAY", "message": "已返回相同幂等键的既有结果", "operation_id": result.get("operation_id")})
                        replayed = True
                    else:
                        result = handler(args)
                        atomic_write_json(record_path, {"record_version": "0.1.0", "command": _command_name(args), "key": args.idempotency_key, "fingerprint": fingerprint, "response": result, "created_at": now_iso()})
                else:
                    result = handler(args)
            if transaction.get("recovered"):
                result.setdefault("warnings", []).append({"code": "PROJECT_TRANSACTION_RECOVERED", "message": "执行本次命令前已恢复上次中断的项目元数据事务", "transaction_id": transaction.get("recovery", {}).get("transaction_id"), "command": transaction.get("recovery", {}).get("command")})

        _print(result, args.format)
        return 0 if result.get("ok") else (7 if args.domain == "rights" or getattr(args, "publish", False) else 2)
    except AppError as exc:
        result = _envelope(_command_name(args), args, status="failed", errors=[exc.as_dict()], operation_id=exc.operation_id)
        _print(result, args.format)
        return exc.exit_code
    except (KeyError, ValueError, TypeError) as exc:
        result = _envelope(_command_name(args), args, status="failed", errors=[{"code": "INTERNAL_INPUT_ERROR", "message": str(exc), "retryable": False}])
        _print(result, args.format)
        return 9

