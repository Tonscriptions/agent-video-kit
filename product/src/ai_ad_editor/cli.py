from __future__ import annotations

import argparse
import copy
import io
import json
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
from .media import classify_path, ffmpeg_version, generate_proxy, generate_thumbnail, generate_waveform, probe_media, relink_missing_assets
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
    restore_snapshot,
    save_project,
)
from .quality import check_output
from .recommend import recommend_highlights
from .library import index_directory, search_catalog
from .batch import _load_variants, run_template_batch
from .capabilities import build_capability_manifest
from .transcribe import transcribe_local, write_srt
from .render import OUTPUT_CONTAINERS, OUTPUT_PIXEL_FORMATS, OUTPUT_PROFILES, output_settings, render_fingerprints, render_project, speed_curve_duration_seconds
from .rights import add_record, check_project_rights, load_ledger, save_ledger
from .understand import understand_media
from .tracking import track_media
from .runtime import configure_local_runtime
from .template import instantiate
from .migration import SUPPORTED_SOURCE_VERSIONS, migrate_project_payload
from .speech import flite_available, synthesize_local_tts
from .effects import EFFECT_CATALOG_VERSION, get_effect, list_effects
from .utils import atomic_write_json, ensure_inside, idempotency_record_path, load_json, new_id, now_iso, request_fingerprint, safe_filename, sha256_file
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

    ad = subs.add_parser("ad", help="本地广告结构规划")
    ads = ad.add_subparsers(dest="action", required=True)
    ad_plan = _leaf_common(ads.add_parser("plan", help="从 JSON brief 生成广告节拍与时间线标记"))
    ad_plan.add_argument("--project", required=True)
    ad_plan.add_argument("--input", required=True, help="广告 brief JSON")
    ad_plan.add_argument("--analysis", default=None, help="可选本地素材理解/高光报告 JSON")
    ad_plan.add_argument("--output", default=None)

    subtitle = subs.add_parser("subtitle", help="字幕解析、验证与规范化")
    ss = subtitle.add_subparsers(dest="action", required=True)
    subtitle_validate = _leaf_common(ss.add_parser("validate", help="验证 SRT/VTT/ASS 字幕"))
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
    lsearch = _leaf_common(ls.add_parser("search", help="查询本地资产索引"))
    lsearch.add_argument("--catalog", required=True)
    lsearch.add_argument("--query", default="")
    lsearch.add_argument("--kind", default=None)
    lsearch.add_argument("--verification-status", default=None)
    lsearch.add_argument("--limit", type=int, default=50)

    doctor = _leaf_common(subs.add_parser("doctor", help="检查本机依赖"))
    doctor.add_argument("--project", default=None)
    operation = _leaf_common(subs.add_parser("operation", help="查看操作状态"))
    osub = operation.add_subparsers(dest="action", required=True)
    opinspect = _leaf_common(osub.add_parser("inspect", help="读取操作记录"))
    opinspect.add_argument("--project", required=True)
    opinspect.add_argument("--operation-id", required=True)
    _leaf_common(subs.add_parser("version", help="版本信息"))
    _leaf_common(subs.add_parser("capabilities", help="输出本地 Agent 能力清单"))
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
    asset = {"id": asset_id, "kind": kind, "uri": uri, "sha256": f"sha256:{digest}", "probe": probe, "rights_ref": asset_id, "source": {"source_url": args.source_url or f"local://{source}", "retrieved_at": now_iso(), "original_name": source.name}}
    record = {"asset_id": asset_id, "kind": kind, "sha256": f"sha256:{digest}", "source_url": args.source_url or f"local://{source}", "source_version": "local", "retrieved_at": now_iso(), "creator": args.creator, "license_spdx": args.license_spdx, "license_url": args.license_url, "attribution": "", "permitted_uses": list(dict.fromkeys(args.permitted_use)), "restrictions": [], "evidence": args.evidence or ("" if args.verification_status == "unverified" else f"local://{source}"), "verification_status": args.verification_status, "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "", "takedown_status": "clear", "notes": "Imported by local CLI"}
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


def _clip_from_change(change: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    for field in ("source_in_tick", "source_out_tick"):
        if field not in change:
            raise argument_error(f"append_clip 缺少字段: {field}", field)
    asset_id = change.get("asset_id")
    sequence_id = change.get("nested_sequence_id")
    if not asset_id and not sequence_id:
        raise argument_error("append_clip 必须提供 asset_id 或 nested_sequence_id")
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
    for field in ("speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "audio", "blend", "mask"):
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
    preset = str(change.get("preset") or change.get("motion_preset") or "").lower().replace("-", "_")
    if not preset:
        raise argument_error("apply_motion_preset 缺少 preset", "preset")
    duration = max(1, int(clip.get("duration_tick", 1)))
    start_tick = max(0, int(change.get("start_tick", 0)))
    end_tick = min(duration, int(change.get("end_tick", duration)))
    if end_tick <= start_tick:
        raise argument_error("运动预设的时间范围无效", "start_tick/end_tick")
    amount = abs(float(change.get("amount", 0.15)))
    transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
    position = transform.get("position") if isinstance(transform.get("position"), dict) else {}
    scale = float(transform.get("scale", 1.0))
    x = float(position.get("x", transform.get("position_x", 0.5)))
    y = float(position.get("y", transform.get("position_y", 0.5)))
    ease = "ease_in_out"
    if preset in {"zoom_in", "push_in"}:
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
    elif preset in {"zoom_out", "pull_out"}:
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale * (1 + amount), ease), (end_tick, scale, ease)])
    elif preset in {"pan_left", "slide_left"}:
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x + amount / 2, ease), (end_tick, x - amount / 2, ease)])
    elif preset in {"pan_right", "slide_right"}:
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 2, ease), (end_tick, x + amount / 2, ease)])
    elif preset in {"pan_up", "slide_up"}:
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 2, ease), (end_tick, y - amount / 2, ease)])
    elif preset in {"pan_down", "slide_down"}:
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y - amount / 2, ease), (end_tick, y + amount / 2, ease)])
    elif preset in {"ken_burns", "kenburns"}:
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 3, ease), (end_tick, x + amount / 3, ease)])
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 3, ease), (end_tick, y - amount / 3, ease)])
    elif preset in {"rotate_in", "rotate_left"}:
        degrees = float(change.get("degrees", 8.0))
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, degrees, ease), (end_tick, 0.0, ease)])
    elif preset in {"rotate_out", "rotate_right"}:
        degrees = float(change.get("degrees", 8.0))
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, 0.0, ease), (end_tick, degrees, ease)])
    elif preset in {"fade_in", "opacity_in"}:
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 0.0, "linear"), (end_tick, 1.0, ease)])
    elif preset in {"fade_out", "opacity_out"}:
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 1.0, ease), (end_tick, 0.0, "linear")])
    elif preset == "shake":
        points = max(2, int(change.get("points", 8)))
        values = []
        for index in range(points):
            progress = index / (points - 1)
            sign = -1 if index % 2 else 1
            values.append((round(start_tick + (end_tick - start_tick) * progress), x + sign * amount / 3, "linear"))
        _set_keyframe_track(clip, "transform.position.x", values)
    else:
        raise argument_error(f"不支持的运动预设: {preset}", "preset")
    return {"preset": preset, "start_tick": start_tick, "end_tick": end_tick, "amount": amount}


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
            for field in ("muted", "locked", "order", "overlap_policy"):
                if field in patch:
                    track[field] = patch[field]
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
            for field in ("asset_id", "sequence_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick", "speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "audio", "blend", "mask"):
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
    sequence = find_sequence(project, resolved.get("sequence_id"))
    applied: list[dict[str, Any]] = []
    for change in operations:
        if change.get("op", "append_clip") != "append_clip":
            raise argument_error(f"模板暂不支持操作: {change.get('op')}")
        target_sequence = find_sequence(project, change.get("sequence_id") or sequence["id"])
        track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
        clip = _clip_from_change(change, track)
        if clip["asset_id"] not in asset_map(project):
            raise argument_error(f"模板引用的资产不存在: {clip['asset_id']}", "asset_id")
        track.setdefault("clips", []).append(clip)
        target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
        applied.append({"op": "append_clip", "track_id": track["id"], "clip": clip})
    snapshot = resolved.get("template_snapshot", {"id": template.get("id"), "version": template.get("version"), "variables": variables})
    project.setdefault("templates", []).append({"id": template.get("id") or new_id("template"), "version": template.get("version", "0.0.0"), "variables": [{"name": key, "value": value} for key, value in variables.items()], "assets": sorted({item["clip"].get("asset_id") for item in applied})})
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
    if args.dry_run:
        return _envelope("library.index", args, status="planned", data={"root": str(source_root), "output": str(output), "max_files": args.max_files})
    catalog = index_directory(source_root, output, max_files=args.max_files, license_spdx=args.license_spdx, verification_status=args.verification_status)
    return _envelope("library.index", args, data={"catalog": str(output), "indexed_count": catalog["indexed_count"], "error_count": len(catalog["errors"])})


def command_library_search(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    results = search_catalog(catalog, query=args.query, kind=args.kind, verification_status=args.verification_status, limit=args.limit)
    return _envelope("library.search", args, data={"catalog": str(catalog_path), "count": len(results), "results": results})


def command_doctor(args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, Any] = {"platform": platform.platform(), "python": sys.version.split()[0], "native_windows": os.name == "nt", "network_default": "disabled", "virtualization_commands": {}}
    checks["runtime_storage"] = configure_local_runtime()
    for name in ("ffmpeg", "ffprobe", "docker", "wsl", "cargo", "node"):
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"] = checks.get("virtualization_commands" if name in {"docker", "wsl"} else "tools", {})
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"][name] = shutil.which(name)
    checks["ffmpeg_version"] = ffmpeg_version() if checks["tools"].get("ffmpeg") else None
    checks["local_features"] = {"flite_tts": flite_available() if checks["tools"].get("ffmpeg") else False}
    checks["policy"] = {"docker_or_wsl_started": False, "closed_services_enabled": False, "jianying_runtime_enabled": False}
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


COMMANDS: dict[tuple[str, str | None], Callable[[argparse.Namespace], dict[str, Any]]] = {
    ("project", "init"): command_project_init,
    ("project", "inspect"): command_project_inspect,
    ("project", "snapshot"): command_project_snapshot,
    ("project", "restore"): command_project_restore,
    ("project", "migrate"): command_project_migrate,
    ("media", "ingest"): command_media_ingest,
    ("media", "relink"): command_media_relink,
    ("media", "track"): command_media_track,
    ("media", "understand"): command_media_understand,
    ("media", "prepare"): command_media_prepare,
    ("media", "highlights"): command_media_highlights,
    ("ad", "plan"): command_ad_plan,
    ("subtitle", "validate"): command_subtitle_validate,
    ("subtitle", "normalize"): command_subtitle_normalize,
    ("tts", "synthesize"): command_tts_synthesize,
    ("effects", "list"): command_effects_list,
    ("effects", "inspect"): command_effects_inspect,
    ("timeline", "compose"): command_timeline_compose,
    ("validate", None): command_validate,
    ("rights", "check"): command_rights_check,
    ("render", None): command_render,
    ("quality", "check"): command_quality_check,
    ("convert", "import"): command_convert_import,
    ("convert", "export"): command_convert_export,
    ("template", "apply"): command_template_apply,
    ("template", "batch"): command_template_batch,
    ("library", "index"): command_library_index,
    ("library", "search"): command_library_search,
    ("doctor", None): command_doctor,
    ("operation", "inspect"): command_operation_inspect,
    ("version", None): command_version,
    ("capabilities", None): command_capabilities,
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

