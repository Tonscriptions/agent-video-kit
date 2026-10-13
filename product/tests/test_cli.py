from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from PIL import Image

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import probe_media
from ai_ad_editor.render import _expr_arg, _flatten_sequence_tracks, _keyframe_expr, _reverse_speed_curve_segments, _transform_exprs
from ai_ad_editor.utils import run_process
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.migration import migrate_project_payload


ROOT = Path(__file__).resolve().parents[2]


def invoke(*argv: str) -> tuple[int, dict]:
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(argv))
    return code, json.loads(stream.getvalue())


class P0CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        configure_local_runtime()

    def make_media(self, directory: Path, name: str = "fixture.mp4") -> Path:
        target = directory / name
        completed = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=1",
                "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:d=1",
                "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(target),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def make_image(self, directory: Path, name: str = "fixture.png") -> Path:
        target = directory / name
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=320x180", "-frames:v", "1", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def make_pulse_audio(self, directory: Path, name: str = "pulse.wav") -> Path:
        target = directory / name
        completed = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "aevalsrc=if(lt(mod(t\\,0.5)\\,0.12)\\,0.8*sin(2*PI*880*t)\\,0):s=48000:d=2", "-c:a", "pcm_s16le", str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return target

    def test_local_p0_pipeline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            code, result = invoke("project", "init", str(project), "--name", "P0")
            self.assertEqual(code, 0)
            code, result = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://fixture", "--license-spdx", "CC0-1.0",
                "--license-url", "local://license", "--evidence", "local://evidence",
            )
            self.assertEqual(code, 0, result)
            asset_id = result["data"]["asset"]["id"]
            ingest_operation = result["operation_id"]
            code, operation_result = invoke("operation", "inspect", "--project", str(project), "--operation-id", ingest_operation)
            self.assertEqual(code, 0, operation_result)
            self.assertEqual(operation_result["data"]["operation"]["status"], "succeeded")
            code, understanding = invoke("media", "understand", "--project", str(project), "--asset-id", asset_id)
            self.assertEqual(code, 0, understanding)
            self.assertEqual(understanding["data"]["result"]["engine"], "ffmpeg-local")
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"sequence_id": "seq_main", "operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            code, result = invoke("validate", "--project", str(project), "--strict-rights")
            self.assertEqual(code, 0, result)
            output = project / "renders" / "p0.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            probe = probe_media(output)
            self.assertEqual(probe["video"]["width"], 1080)
            self.assertEqual(probe["video"]["height"], 1920)
            self.assertGreater(probe["duration_seconds"], 0.8)
            self.assertTrue((output.with_suffix(".mp4.manifest.json")).exists())
            code, quality = invoke("quality", "check", "--project", str(project), "--input", str(output), "--require-audio")
            self.assertEqual(code, 0, quality)
            self.assertTrue(quality["data"]["ok"])
            code, expensive_quality = invoke("quality", "check", "--project", str(project), "--input", str(output), "--require-audio", "--expensive", "--max-av-sync-ms", "80", "--target-lufs", "-14", "--lufs-tolerance", "20", "--max-true-peak-dbfs", "-1")
            self.assertEqual(code, 0, expensive_quality)
            self.assertIn("black_intervals", expensive_quality["data"]["metrics"])
            self.assertIn("av_duration_delta_seconds", expensive_quality["data"]["metrics"])
            self.assertIn("integrated_lufs", expensive_quality["data"]["metrics"])
            self.assertIn("true_peak_dbfs", expensive_quality["data"]["metrics"])
            exported = workspace / "with-assets.json"
            code, result = invoke("convert", "export", "--project", str(project), "--output", str(exported))
            self.assertEqual(code, 0, result)
            imported = workspace / "with-assets-imported"
            code, result = invoke("convert", "import", "--input", str(exported), "--output", str(imported))
            self.assertEqual(code, 0, result)
            imported_project = json.loads((imported / "project.json").read_text(encoding="utf-8"))
            self.assertTrue((imported / imported_project["assets"][0]["uri"]).exists())
            otio = workspace / "timeline.otio"
            code, otio_result = invoke("convert", "export", "--project", str(project), "--output", str(otio), "--target-format", "otio")
            self.assertEqual(code, 0, otio_result)
            self.assertEqual(json.loads(otio.read_text(encoding="utf-8"))["OTIO_SCHEMA"], "Timeline.1")
            otio_imported = workspace / "otio-imported"
            code, otio_import_result = invoke("convert", "import", "--input", str(otio), "--output", str(otio_imported))
            self.assertEqual(code, 0, otio_import_result)
            self.assertTrue((otio_imported / "project.json").exists())
            kdenlive = workspace / "timeline.kdenlive"
            code, kdenlive_result = invoke("convert", "export", "--project", str(project), "--output", str(kdenlive), "--target-format", "kdenlive-xml")
            self.assertEqual(code, 0, kdenlive_result)
            self.assertIn("<mlt", kdenlive.read_text(encoding="utf-8"))
            kdenlive_imported = workspace / "kdenlive-imported"
            code, kdenlive_import_result = invoke("convert", "import", "--input", str(kdenlive), "--output", str(kdenlive_imported))
            self.assertEqual(code, 0, kdenlive_import_result)
            self.assertTrue((kdenlive_imported / "project.json").exists())

    def test_project_snapshots_restore_edit_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-snapshot-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, snapshot = invoke("project", "snapshot", "--project", str(project), "--label", "baseline")
            self.assertEqual(code, 0, snapshot)
            snapshot_id = snapshot["data"]["snapshot_id"]
            self.assertTrue((project / "history" / f"{snapshot_id}.json").exists())
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "add_marker", "id": "hook", "at_tick": 0, "label": "Hook",
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["sequences"][0]["markers"][0]["id"], "hook")
            code, restored = invoke("project", "restore", "--project", str(project), "--snapshot", str(project / "history" / f"{snapshot_id}.json"))
            self.assertEqual(code, 0, restored)
            restored_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(restored_project["sequences"][0]["markers"], [])
            self.assertTrue(restored["data"]["backup"]["snapshot_id"])

    def test_project_migrate_legacy_defaults_and_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-migrate-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload["schema_version"] = "0.0.0"
            payload["settings"].pop("output", None)
            payload["settings"].pop("audio", None)
            payload["settings"].pop("color", None)
            payload["sequences"][0].pop("markers", None)
            payload["sequences"][0]["tracks"][0].pop("muted", None)
            payload["sequences"][0]["tracks"][0].pop("locked", None)
            payload["provenance"] = {"change_log": []}
            payload["extensions"] = {"legacy_payload": {"unknown": "preserved"}}
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            original = (project / "project.json").read_bytes()
            migrated_once = migrate_project_payload(payload, timestamp="2026-10-13T00:00:00Z")
            self.assertEqual(migrated_once, migrate_project_payload(payload, timestamp="2026-10-13T00:00:00Z"))
            self.assertEqual(payload["schema_version"], "0.0.0")
            code, planned = invoke("project", "migrate", "--project", str(project), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertEqual((project / "project.json").read_bytes(), original)
            self.assertFalse(list((project / "history").iterdir()))
            code, result = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 0, result)
            self.assertTrue(result["data"]["migration"]["changed"])
            self.assertTrue(result["data"]["backup"]["snapshot_id"])
            migrated = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], "0.1.0")
            self.assertEqual(migrated["settings"]["output"]["container"], "mp4")
            self.assertEqual(migrated["extensions"], payload["extensions"])
            backup = json.loads(Path(result["data"]["backup"]["path"]).read_text(encoding="utf-8"))
            self.assertEqual(backup["project"], payload)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            saved = (project / "project.json").read_bytes()
            code, repeated = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 0, repeated)
            self.assertFalse(repeated["data"]["migration"]["changed"])
            self.assertEqual((project / "project.json").read_bytes(), saved)
            code, relative_report = invoke("project", "migrate", "--project", str(project), "--report", "relative.json")
            self.assertEqual(code, 0, relative_report)
            self.assertEqual(Path(relative_report["data"]["report"]), project / "validation" / "relative.json")
            self.assertTrue((project / "validation" / "relative.json").exists())

    def test_project_migrate_rejects_unlocatable_legacy_asset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-migrate-invalid-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            payload["schema_version"] = "0.0.0"
            payload["assets"] = [{"id": "asset_legacy", "kind": "video", "uri": "assets/missing.mp4", "probe": {}, "rights_ref": "asset_legacy"}]
            (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
            code, result = invoke("project", "migrate", "--project", str(project))
            self.assertEqual(code, 3, result)
            self.assertEqual(result["errors"][0]["code"], "MIGRATION_ASSET_HASH_MISSING")
            for version in ("0.2.0", "unknown", None):
                payload["schema_version"] = version
                (project / "project.json").write_text(json.dumps(payload), encoding="utf-8")
                before = (project / "project.json").read_bytes()
                code, rejected = invoke("project", "migrate", "--project", str(project))
                self.assertEqual(code, 2, rejected)
                self.assertEqual(rejected["errors"][0]["code"], "SCHEMA_VERSION_UNSUPPORTED")
                self.assertEqual((project / "project.json").read_bytes(), before)

    def test_missing_asset_can_be_relinked_by_content_hash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-relink-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingested["data"]["asset"]["id"]
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            missing = project / project_json["assets"][0]["uri"]
            missing.unlink()
            code, result = invoke("media", "relink", "--project", str(project), "--search-root", str(workspace))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["relinked"], 1)
            self.assertEqual(result["data"]["entries"][0]["status"], "Exact")
            relinked_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            relinked_path = project / relinked_project["assets"][0]["uri"]
            self.assertTrue(relinked_path.exists())
            self.assertEqual(relinked_project["assets"][0]["id"], asset_id)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_media_understand_exposes_local_beat_anchors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-beats-") as raw:
            workspace = Path(raw)
            source = self.make_pulse_audio(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--beats")
            self.assertEqual(code, 0, result)
            beats = result["data"]["result"]["beat_anchors"]
            self.assertIn(beats["status"], {"ok", "no_peaks", "insufficient_signal", "no_audio"})
            self.assertNotEqual(beats["status"], "failed")

    def test_local_asr_requires_explicit_offline_model(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-asr-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--transcribe")
            self.assertEqual(code, 2, result)
            self.assertEqual(result["errors"][0]["code"], "ARGUMENT_INVALID")
            missing = workspace / "missing-model"
            code, result = invoke("media", "understand", "--project", str(project), "--input", str(source), "--transcribe", "--model-path", str(missing))
            self.assertEqual(code, 10, result)
            self.assertEqual(result["errors"][0]["code"], "LOCAL_ASR_MODEL_MISSING")

    def test_subtitle_formats_validate_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-subtitle-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            srt = workspace / "captions.srt"
            srt.write_text("1\n00:00:00,000 --> 00:00:00,500\n第一句\n\n2\n00:00:00,500 --> 00:00:01,000\n第二句\n", encoding="utf-8")
            code, result = invoke("subtitle", "validate", "--project", str(project), "--input", str(srt))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 2)
            normalized = project / "validation" / "normalized.srt"
            code, result = invoke("subtitle", "normalize", "--project", str(project), "--input", str(srt), "--output", str(normalized))
            self.assertEqual(code, 0, result)
            self.assertIn("第一句", normalized.read_text(encoding="utf-8"))
            vtt = workspace / "captions.vtt"
            vtt.write_text("WEBVTT\n\n00:00.000 --> 00:00.750\nVTT cue\n", encoding="utf-8")
            self.assertEqual(invoke("subtitle", "validate", "--input", str(vtt))[0], 0)
            ass = workspace / "captions.ass"
            ass.write_text("[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:00.80,Default,,0,0,0,,ASS cue\n", encoding="utf-8")
            code, result = invoke("subtitle", "validate", "--input", str(ass))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 1)
            _, ingested = invoke("media", "ingest", "--project", str(project), "--input", str(srt))
            self.assertEqual(ingested["data"]["asset"]["kind"], "subtitle")

    def test_local_library_index_and_search(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-library-") as raw:
            workspace = Path(raw)
            media_dir = workspace / "library"
            media_dir.mkdir()
            source = self.make_media(media_dir, "product.mp4")
            (media_dir / "captions.srt").write_text("1\n00:00:00,000 --> 00:00:00,500\nLocal product\n", encoding="utf-8")
            catalog = workspace / "catalog.json"
            code, result = invoke("library", "index", "--root", str(media_dir), "--output", str(catalog))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["indexed_count"], 2)
            code, result = invoke("library", "search", "--catalog", str(catalog), "--query", "product")
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["count"], 1)
            self.assertEqual(result["data"]["results"][0]["name"], source.name)

    def test_media_prepare_generates_proxy_thumbnail_and_waveform(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-prepare-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            code, result = invoke("media", "prepare", "--project", str(project), "--asset-id", asset_id, "--proxy-width", "160", "--thumbnail", "--waveform")
            self.assertEqual(code, 0, result)
            self.assertTrue(Path(result["data"]["proxy"]).exists())
            self.assertTrue(Path(result["data"]["thumbnail"]).exists())
            self.assertTrue(Path(result["data"]["waveform"]).exists())
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            asset = project_json["assets"][0]
            self.assertEqual(asset["proxy"]["width"], 160)
            self.assertIn("thumbnail", asset)
            self.assertIn("waveform", asset)

    def test_local_highlight_recommendation_writes_auditable_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-highlights-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "highlights", "--project", str(project), "--input", str(source), "--beats", "--top-k", "3")
            self.assertEqual(code, 0, result)
            report = Path(result["data"]["report"])
            self.assertTrue(report.exists())
            recommendation = result["data"]["recommendation"]
            self.assertEqual(recommendation["engine"], "local-heuristic")
            self.assertEqual(recommendation["network"], "disabled")
            self.assertLessEqual(len(recommendation["candidates"]), 3)

    def test_local_ad_plan_writes_timed_phases_and_markers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-plan-") as raw:
            workspace = Path(raw)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            brief = workspace / "brief.json"
            brief.write_text(json.dumps({
                "product": "Local Camera",
                "audience": "短视频创作者",
                "duration_seconds": 12,
                "cta": "立即试用",
                "hook": "三秒完成自动剪辑",
                "benefit": "离线快速导出",
                "profile": "vertical",
            }), encoding="utf-8")
            code, result = invoke("ad", "plan", "--project", str(project), "--input", str(brief))
            self.assertEqual(code, 0, result)
            plan = result["data"]["plan"]
            self.assertEqual(plan["engine"], "local-ad-plan")
            self.assertEqual(plan["network"], "disabled")
            self.assertEqual(plan["duration_tick"], sum(item["duration_tick"] for item in plan["phases"]))
            self.assertEqual(len(plan["markers"]), len(plan["phases"]))
            self.assertTrue(Path(result["data"]["output"]).exists())

    def test_capabilities_manifest_is_local_and_agent_readable(self) -> None:
        code, result = invoke("capabilities")
        self.assertEqual(code, 0, result)
        manifest = result["data"]
        self.assertEqual(manifest["engine"]["network"], "disabled")
        self.assertIn("bezier", manifest["capabilities"]["keyframes"]["interpolation"])
        self.assertIn("crossfade", manifest["capabilities"]["transitions"]["features"])
        self.assertIn("safe_resume", manifest["capabilities"]["render"]["features"])
        self.assertIn("snapshot", manifest["capabilities"]["project"]["features"])
        self.assertIn("relink_by_hash", manifest["capabilities"]["media"]["features"])
        self.assertIn("target_lufs_gate", manifest["capabilities"]["quality"]["features"])
        self.assertIn("effect_parameter_keyframes", manifest["capabilities"]["effects"]["features"])
        self.assertIn("sequence_adjustments", manifest["capabilities"]["effects"]["features"])
        self.assertIn("lut3d_project_local", manifest["capabilities"]["effects"]["features"])
        self.assertIn("yuv420p10le", manifest["capabilities"]["output"]["pixel_formats"])
        self.assertIn("yuva420p", manifest["capabilities"]["output"]["pixel_formats"])
        self.assertIn("hable", manifest["capabilities"]["output"]["tone_mapping"])
        self.assertEqual(manifest["policies"]["jianying_runtime_enabled"], False)

    def test_runtime_storage_is_local_to_product(self) -> None:
        paths = configure_local_runtime()
        self.assertEqual(Path(paths["root"]).resolve(), (ROOT / "product" / ".runtime").resolve())
        self.assertTrue(Path(paths["temp"]).is_dir())
        self.assertTrue(Path(paths["cache"]).is_dir())

    def test_cli_unicode_paths_and_progress_use_utf8_pipes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-utf8-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "广告项目🎬"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "product" / "src")
            env["PYTHONUTF8"] = "0"
            env["PYTHONIOENCODING"] = "ascii:strict"
            completed = subprocess.run(
                [sys.executable, "-m", "ai_ad_editor", "media", "ingest", "--project", str(project),
                 "--input", str(source), "--progress", "jsonl", "--request-id", "请求_中文路径🎬"],
                env=env, capture_output=True, timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8"))
            response = json.loads(completed.stdout.decode("utf-8"))
            self.assertTrue(response["ok"])
            self.assertEqual(response["request_id"], "请求_中文路径🎬")
            events = [json.loads(line) for line in completed.stderr.decode("utf-8").splitlines()]
            self.assertEqual([event["type"] for event in events], ["started", "completed"])
            self.assertEqual(events[0]["message"], "开始导入本地素材")
            self.assertTrue((project / "project.json").exists())

    def test_template_batch_creates_isolated_local_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-batch-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            template = workspace / "template.json"
            template.write_text(json.dumps({"id": "batch.test", "version": "0.1.0", "variables": [{"name": "asset_id", "required": True}], "operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": "{{asset_id}}", "source_in_tick": 0, "source_out_tick": 90000}]}), encoding="utf-8")
            variants = workspace / "variants.json"
            variants.write_text(json.dumps({"variants": [{"id": "hook-a", "variables": {"asset_id": asset_id}}, {"id": "hook-b", "variables": {"asset_id": asset_id}}]}), encoding="utf-8")
            output_root = project / "exports" / "batch"
            code, result = invoke("template", "batch", "--project", str(project), "--input", str(template), "--variables", str(variants), "--output", str(output_root))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["succeeded"], 2)
            for variant_id in ("hook-a", "hook-b"):
                self.assertTrue((output_root / variant_id / "project.json").exists())
                self.assertTrue((output_root / variant_id / "renders" / f"{variant_id}.mp4").exists())

    def test_rights_gate_blocks_unverified_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-rights-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            self.assertEqual(code, 0)
            code, result = invoke("rights", "check", "--project", str(project))
            self.assertEqual(code, 7)
            self.assertFalse(result["ok"])
            self.assertTrue(result["data"]["failures"])

    def test_ingest_dry_run_does_not_change_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-dry-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            code, result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--dry-run")
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "planned")
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["assets"], [])
            self.assertFalse(list((project / "assets").iterdir()))

    def test_project_bound_idempotency_replays_and_rejects_conflict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-idempotency-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            first_code, first = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--idempotency-key", "ingest-1")
            self.assertEqual(first_code, 0, first)
            second_code, second = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--idempotency-key", "ingest-1")
            self.assertEqual(second_code, 0, second)
            self.assertEqual(first["operation_id"], second["operation_id"])
            self.assertTrue(any(item.get("code") == "IDEMPOTENT_REPLAY" for item in second["warnings"]))
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(len(project_json["assets"]), 1)
            conflict_code, conflict = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--license-spdx", "CC0-1.0", "--idempotency-key", "ingest-1")
            self.assertEqual(conflict_code, 2, conflict)
            self.assertEqual(conflict["errors"][0]["code"], "IDEMPOTENCY_CONFLICT")

    def test_project_init_dry_run_and_agent_export_import(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-convert-") as raw:
            workspace = Path(raw)
            planned = workspace / "planned"
            code, result = invoke("project", "init", str(planned), "--dry-run")
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "planned")
            self.assertFalse(planned.exists())
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            exported = workspace / "exported.json"
            code, result = invoke("convert", "export", "--project", str(project), "--output", str(exported))
            self.assertEqual(code, 0, result)
            imported = workspace / "imported"
            code, result = invoke("convert", "import", "--input", str(exported), "--output", str(imported))
            self.assertEqual(code, 0, result)
            self.assertTrue((imported / "project.json").exists())

    def test_published_json_schema_rejects_invalid_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-schema-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            del project_json["settings"]
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, result = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, result)
            self.assertEqual(result["data"]["schema_engine"], "jsonschema")
            self.assertTrue(any(item["code"] == "SCHEMA_VALIDATION_FAILED" for item in result["errors"]))

    def test_bezier_control_points_are_schema_and_semantically_validated(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-bezier-validation-") as raw:
            project = Path(raw) / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_json["sequences"][0]["tracks"][0]["clips"].append({
                "id": "clip_bezier",
                "sequence_id": "seq_main",
                "timeline_start_tick": 0,
                "duration_tick": 1,
                "source_in_tick": 0,
                "source_out_tick": 1,
                "keyframes": [{
                    "property": "transform.scale",
                    "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [1.2, 0.4, 0.8, 0.9]}],
                }],
            })
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, result = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, result)
            self.assertTrue(any(item["code"] == "BEZIER_CONTROL_POINT_RANGE" for item in result["errors"]))

    def test_bezier_keyframe_expression_preserves_value_endpoints(self) -> None:
        """Cubic easing must interpolate the property range exactly once."""
        clip = {
            "keyframes": [{
                "property": "transform.scale",
                "keyframes": [
                    {"at_tick": 0, "value": 2.0, "interpolation": "bezier", "control_points": [0.0, 0.2, 0.8, 1.0]},
                    {"at_tick": 90000, "value": 4.0, "interpolation": "linear"},
                ],
            }],
        }
        expression = _keyframe_expr(clip, ("transform.scale",), 1.0, 0.0, 90000, time_variable="t")
        decoded = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", f"aevalsrc=exprs={_expr_arg(expression)}:s=1000:d=1",
                "-f", "f32le", "pipe:1",
            ],
            capture_output=True,
        )
        self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
        samples = memoryview(decoded.stdout).cast("f")
        self.assertGreater(len(samples), 900)
        self.assertAlmostEqual(samples[0], 2.0, delta=0.02)
        self.assertAlmostEqual(samples[-1], 4.0, delta=0.02)
        self.assertTrue(2.0 < samples[500] < 4.0, samples[500])

    def test_template_snapshot_applies_local_change_set(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-template-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            template = workspace / "template.json"
            template.write_text(json.dumps({"id": "tpl.test", "version": "0.1.0", "variables": [{"name": "asset_id", "required": True}], "operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": "{{asset_id}}", "source_in_tick": 0, "source_out_tick": 90000}]}), encoding="utf-8")
            variables = workspace / "variables.json"
            variables.write_text(json.dumps({"asset_id": asset_id}), encoding="utf-8")
            code, result = invoke("template", "apply", "--project", str(project), "--input", str(template), "--variables", str(variables))
            self.assertEqual(code, 0, result)
            self.assertEqual(result["data"]["template_snapshot"]["id"], "tpl.test")
            self.assertEqual(len(result["data"]["applied"]), 1)

    def test_image_clip_renders_with_local_loop(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-image-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://image", "--license-spdx", "CC0-1.0", "--evidence", "local://image")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000}]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "image.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())

    def test_keyframes_effects_subtitle_and_audio_automation_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effects-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://effects", "--license-spdx", "CC0-1.0", "--evidence", "local://effects")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "transform": {"position": {"x": 0.5, "y": 0.5}}, "keyframes": [{"property": "transform.scale", "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.2, 0.82, 0.8, 0.98]}, {"at_tick": 90000, "value": 1.0, "interpolation": "linear"}]}], "effects": [{"type": "grayscale"}], "subtitle": {"text": "Local ad", "style": {"fontsize": 36, "line_spacing": 8, "borderw": 2, "bordercolor": "black", "shadowx": 2, "shadowy": 2, "shadowcolor": "black@0.7", "text_align": "center+middle", "boxborderw": 14, "text_shaping": True, "fix_bounds": True, "expansion": "none", "animation": {"type": "slide_up", "duration": 0.25, "distance": 80}}}, "transition_in": {"type": "fade", "duration": 0.1}},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"volume": 0.5, "fade_in": 0.1, "fade_out": 0.1, "equalizer": {"frequency": 1000, "gain": 2, "width": 1}, "highpass": 60, "lowpass": 18000}}
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "effects.mp4"
            code, result = invoke("render", "--project", str(project), "--publish", "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertEqual(result["data"]["warnings"], [])

    def test_extended_effects_and_typewriter_subtitle_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effects-extended-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://extended-effects", "--license-spdx", "CC0-1.0", "--evidence", "local://extended-effects")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [
                    {"type": "posterize", "levels": 8},
                    {"type": "color_temperature", "kelvin": 7200},
                    {"type": "deband", "threshold": 0.02, "range": 8},
                ],
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]},
                "subtitle": {"text": "Type", "style": {"fontsize": 32, "animation": {"type": "typewriter", "duration": 0.4}}},
            }, {
                "op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "extended-effects.mp4"
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            unsupported = [item for item in result["data"]["warnings"] if item.get("code") == "RENDER_FEATURE_UNSUPPORTED"]
            self.assertEqual(unsupported, [])
            self.assertTrue(any(item.get("feature") == "audio_speed_curve_piecewise" for item in result["data"]["warnings"]))

    def test_effect_parameter_keyframes_render_with_frame_evaluation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-effect-keyframes-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://effect-keyframes", "--license-spdx", "CC0-1.0",
                "--evidence", "local://effect-keyframes",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{
                    "type": "brightness", "parameters": {"amount": 0.0},
                    "keyframes": [{"property": "amount", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.7, "interpolation": "ease_in_out"},
                    ]}],
                }],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "effect-keyframes.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("eq=brightness='", graph)
            self.assertIn(":eval=frame", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    [
                        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                        "-frames:v", "1", "-vf", "crop=100:100:490:910,format=gray", "-f", "rawvideo", "-",
                    ], capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            self.assertGreater(center_luma(0.85), center_luma(0.10) + 15.0)

    def test_sequence_adjustment_stack_applies_after_track_composite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-sequence-adjustment-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["adjustments"] = [{
                "id": "global_grade",
                "effects": [{
                    "type": "brightness",
                    "parameters": {"amount": 0.0},
                    "keyframes": [{"property": "amount", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.7, "interpolation": "linear"},
                    ]}],
                }],
            }]
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "sequence-adjustment.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("null[vout]", graph)
            self.assertIn("eq=brightness='", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                     "-frames:v", "1", "-vf", "crop=100:100:110:40,format=gray", "-f", "rawvideo", "-"],
                    capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            self.assertGreater(center_luma(0.85), center_luma(0.10) + 15.0)

    def test_interval_adjustment_layer_reassembles_sequence_clock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-interval-adjustment-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["adjustments"] = [{
                "id": "mid_grade",
                "start_tick": 36000,
                "duration_tick": 27000,
                "effects": [{"type": "brightness", "parameters": {"amount": 0.7}}],
            }]
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "interval-adjustment.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("trim=start=0.400000:end=0.700000", graph)
            self.assertIn("concat=n=3:v=1:a=0", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def center_luma(at_seconds: float) -> float:
                completed = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at_seconds), "-i", str(output),
                     "-frames:v", "1", "-vf", "crop=100:100:110:40,format=gray", "-f", "rawvideo", "-"],
                    capture_output=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", errors="replace"))
                self.assertGreater(len(completed.stdout), 0)
                return sum(completed.stdout) / len(completed.stdout)

            before = center_luma(0.20)
            during = center_luma(0.55)
            after = center_luma(0.90)
            self.assertGreater(during, before + 15.0)
            self.assertLess(abs(after - before), 8.0)

    def test_project_local_lut3d_is_validated_and_rendered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-lut-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            lut_path = project / "luts" / "red.cube"
            lut_path.parent.mkdir(parents=True, exist_ok=True)
            lut_path.write_text(
                'TITLE "Solid Red"\nLUT_3D_SIZE 2\nDOMAIN_MIN 0.0 0.0 0.0\nDOMAIN_MAX 1.0 1.0 1.0\n'
                + "\n".join(["1.0 0.0 0.0"] * 8) + "\n",
                encoding="utf-8",
            )
            invalid_changes = workspace / "invalid-lut.json"
            invalid_changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{"type": "lut3d", "parameters": {"path": "https://example.invalid/look.cube"}}],
            }]}), encoding="utf-8")
            code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(invalid_changes))
            self.assertEqual(code, 2, rejected)
            self.assertIn("LUT_PATH_NETWORK", rejected["errors"][0].get("cause", ""))

            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
                "effects": [{"type": "lut3d", "parameters": {"path": "luts/red.cube", "interpolation": "tetrahedral"}}],
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "lut.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertEqual(rendered["data"]["warnings"], [])
            frame = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"],
                capture_output=True,
            )
            self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", errors="replace"))
            center = (90 * 320 + 160) * 3
            self.assertGreater(frame.stdout[center], 180)
            self.assertLess(frame.stdout[center + 1], 90)

    def test_10bit_pixel_format_and_color_metadata_reach_ffmpeg_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-10bit-output-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "10bit.mp4"
            code, planned = invoke(
                "render", "--project", str(project), "--output", str(output),
                "--profile", "custom", "--width", "320", "--height", "180",
                "--pixel-format", "yuv420p10le", "--dry-run",
            )
            self.assertEqual(code, 0, planned)
            command = planned["data"]["plan"]["command"]
            self.assertIn("yuv420p10le", command)
            self.assertIn("-color_primaries", command)
            self.assertIn("bt709", command)
            self.assertIn("-color_trc", command)
            self.assertIn("-colorspace", command)
            self.assertIn("-color_range", command)
            code, rendered = invoke(
                "render", "--project", str(project), "--output", str(output),
                "--profile", "custom", "--width", "320", "--height", "180",
                "--pixel-format", "yuv420p10le",
            )
            self.assertEqual(code, 0, rendered)
            self.assertEqual(probe_media(output)["video"]["pix_fmt"], "yuv420p10le")

    def test_transparent_webm_output_uses_project_alpha_canvas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-alpha-output-") as raw:
            workspace = Path(raw)
            source = workspace / "overlay.png"
            Image.new("RGBA", (64, 64), (255, 0, 0, 96)).save(source)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://alpha", "--license-spdx", "CC0-1.0", "--evidence", "local://alpha")
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "alpha.webm"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "64", "--height", "64", "--container", "webm", "--video-codec", "libvpx-vp9", "--audio-codec", "libopus", "--pixel-format", "yuva420p", "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("yuva420p", planned["data"]["plan"]["command"])
            self.assertIn("color=c=black@0.0", planned["data"]["plan"]["filter_complex"])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "64", "--height", "64", "--container", "webm", "--video-codec", "libvpx-vp9", "--audio-codec", "libopus", "--pixel-format", "yuva420p")
            self.assertEqual(code, 0, rendered)
            probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream_tags=alpha_mode", "-of", "json", str(output)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(json.loads(probe.stdout)["streams"][0]["tags"].get("alpha_mode"), "1")

    def test_hdr_tone_map_chain_is_local_and_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-hdr-tonemap-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            project_payload = json.loads((project / "project.json").read_text(encoding="utf-8"))
            project_payload["settings"]["color"].update({
                "tone_map": "hable",
                "input_transfer": "smpte2084",
                "input_primaries": "bt2020",
                "input_matrix": "bt2020nc",
                "input_range": "limited",
                "tone_map_desat": 0.5,
            })
            (project / "project.json").write_text(json.dumps(project_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            output = project / "renders" / "tonemapped.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180", "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("zscale=rin=tv:pin=bt2020:tin=smpte2084", graph)
            self.assertIn("tonemap=tonemap=hable", graph)
            self.assertEqual(planned["data"]["plan"]["warnings"], [])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_reverse_speed_curve_reflects_ramp_without_approximation_warning(self) -> None:
        segments = [(0.0, 0.25, 1.0, 1.0), (0.25, 0.75, 2.0, 2.0), (0.75, 1.0, 4.0, 4.0)]
        self.assertEqual(_reverse_speed_curve_segments(segments), [
            (0.0, 0.25, 4.0, 4.0),
            (0.25, 0.75, 2.0, 2.0),
            (0.75, 1.0, 1.0, 1.0),
        ])
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-reverse-speed-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            curve = {"keyframes": [
                {"at_tick": 0, "speed": 1.0, "interpolation": "hold"},
                {"at_tick": 22500, "speed": 2.0, "interpolation": "hold"},
                {"at_tick": 67500, "speed": 4.0, "interpolation": "hold"},
                {"at_tick": 90000, "speed": 4.0, "interpolation": "hold"},
            ]}
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000, "speed_curve": curve, "reverse": True,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            code, planned = invoke("render", "--project", str(project), "--output", str(project / "renders" / "reverse.mp4"), "--dry-run")
            self.assertEqual(code, 0, planned)
            warnings = planned["data"]["plan"]["warnings"]
            self.assertFalse(any(item.get("feature") == "speed_curve_reverse" for item in warnings))
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("/4.00000000", graph)
            code, rendered = invoke("render", "--project", str(project), "--output", str(project / "renders" / "reverse.mp4"))
            self.assertEqual(code, 0, rendered)
            self.assertTrue((project / "renders" / "reverse.mp4").exists())

    def test_speed_curve_with_nonzero_source_in_uses_clip_local_clock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-speed-source-in-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 45000, "source_out_tick": 90000,
                "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 1.0}]},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "source-in-speed.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("trim=start=0.500000:end=1.000000", graph)
            self.assertIn("PTS-STARTPTS", graph)
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertAlmostEqual(probe_media(output)["duration_seconds"], 0.5, delta=0.12)

    def test_word_timing_subtitle_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-word-timing-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://word-timing", "--license-spdx", "CC0-1.0", "--evidence", "local://word-timing")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000,
                "subtitle": {"text": "hello world", "word_timing": [{"text": "hello", "start": 0.0, "end": 0.35}, {"text": "world", "start": 0.35, "end": 0.8}], "style": {"fontsize": 34, "max_width": 160, "active_color": "yellow"}},
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "word-timing.mp4"
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("code") == "RENDER_FEATURE_UNSUPPORTED" for item in result["data"]["warnings"]))
            self.assertTrue(any(item.get("feature") == "subtitle_layout_wrap" for item in result["data"]["warnings"]))

    def test_local_object_tracking_report_and_keyframe_apply(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-tracking-") as raw:
            workspace = Path(raw)
            source = workspace / "moving-object.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=12:d=1",
                    "-f", "lavfi", "-i", "color=c=white:s=36x36:r=12:d=1",
                    "-filter_complex", "overlay=x='20+80*t':y=55:eval=frame:shortest=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "id": "track_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            report_path = project / "validation" / "tracking.json"
            code, tracked = invoke(
                "media", "track", "--project", str(project), "--asset-id", asset_id,
                "--roi", "0.05,0.28,0.14,0.24", "--clip-id", "track_clip", "--output", str(report_path),
            )
            self.assertEqual(code, 0, tracked)
            self.assertTrue(report_path.exists())
            self.assertGreaterEqual(len(tracked["data"]["result"]["frames"]), 2)
            trajectory = tracked["data"]["result"]["frames"]
            self.assertGreater(trajectory[-1]["x"], trajectory[0]["x"] + 0.08)
            self.assertIn("transform.position.x", tracked["data"]["applied_properties"])
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clip = project_json["sequences"][0]["tracks"][0]["clips"][0]
            self.assertTrue(any(item.get("property") == "transform.position.x" for item in clip.get("keyframes", [])))
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)

    def test_nested_sequence_render_and_cycle_rejection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-nested-sequence-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://nested", "--license-spdx", "CC0-1.0", "--evidence", "local://nested")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_sequence", "id": "seq_nested", "name": "Nested", "duration_tick": 90000},
                {"op": "append_clip", "sequence_id": "seq_nested", "track_id": "seq_nested_video_1", "id": "nested_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.42}},
                {"op": "append_clip", "sequence_id": "seq_nested", "track_id": "seq_nested_video_1", "id": "nested_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.42}},
                {"op": "append_sequence_clip", "sequence_id": "seq_main", "track_id": "track_video_1", "nested_sequence_id": "seq_nested", "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 90000, "reverse": True, "mask": {"type": "rectangle", "x": 0.08, "y": 0.08, "width": 0.84, "height": 0.84}, "transform": {"position": {"x": 0.7, "y": 0.5}, "scale": 0.5}, "keyframes": [{"property": "transform.scale", "keyframes": [{"at_tick": 0, "value": 1.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.75, "interpolation": "linear"}]}], "effects": [{"type": "grayscale"}]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "nested.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "nested_sequence_inherited_properties" for item in rendered["data"]["warnings"]))
            self.assertFalse(any(item.get("feature") == "nested_sequence_reverse" for item in rendered["data"]["warnings"]))
            self.assertTrue(any(item.get("feature") == "nested_sequence_multiple_masks" for item in rendered["data"]["warnings"]))
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            nested = next(item for item in project_json["sequences"] if item["id"] == "seq_nested")
            nested["tracks"][0]["clips"].append({"id": "cycle", "sequence_id": "seq_main", "timeline_start_tick": 0, "duration_tick": 1, "source_in_tick": 0, "source_out_tick": 1})
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, rejected = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, rejected)
            self.assertTrue(any(item.get("code") == "SEQUENCE_CYCLE" for item in rejected["errors"]))

    def test_nested_sequence_speed_and_parent_rotation_are_composed(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed": 2.0, "transform": {"position": {"x": 0.5, "y": 0.5}, "rotation": 90.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.5, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {
                            "id": "child_clip_a", "asset_id": "asset", "timeline_start_tick": 0,
                            "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                            "transform": {"position": {"x": 0.75, "y": 0.5}, "scale": 0.5},
                        },
                        {
                            "id": "child_clip_b", "asset_id": "asset", "timeline_start_tick": 90000,
                            "duration_tick": 90000, "source_in_tick": 90000, "source_out_tick": 180000,
                            "transform": {"position": {"x": 0.75, "y": 0.5}, "scale": 0.5},
                        },
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = next(track["clips"] for track in flattened if track["clips"])
        self.assertEqual(len(clips), 2)
        first, second = clips
        self.assertEqual((first["source_in_tick"], first["source_out_tick"], first["duration_tick"]), (0, 90000, 45000))
        self.assertEqual((second["source_in_tick"], second["source_out_tick"], second["duration_tick"]), (90000, 180000, 45000))
        self.assertAlmostEqual(first["speed"], 2.0, places=6)
        self.assertAlmostEqual(second["speed"], 2.0, places=6)
        for clip in clips:
            self.assertAlmostEqual(clip["transform"]["position"]["x"], 0.75, places=6)
            self.assertAlmostEqual(clip["transform"]["position"]["y"], 0.5, places=6)
            self.assertAlmostEqual(clip["transform"].get("rotation", 0.0), 0.0, places=6)
            self.assertAlmostEqual(clip["transform"]["scale"], 0.5, places=6)
            self.assertAlmostEqual(clip["_nested_parent_transform"]["rotation"], 90.0, places=6)
            self.assertTrue(any(item.get("property") == "nested.parent.transform.scale" for item in clip["keyframes"]))
        first_scale = next(item for item in first["keyframes"] if item.get("property") == "nested.parent.transform.scale")["keyframes"]
        second_scale = next(item for item in second["keyframes"] if item.get("property") == "nested.parent.transform.scale")["keyframes"]
        self.assertEqual([item["at_tick"] for item in first_scale], [0, 90000])
        self.assertEqual([item["at_tick"] for item in second_scale], [-45000, 45000])
        self.assertEqual([item["value"] for item in second_scale], [1.0, 0.5])
        self.assertIn("clip(", _transform_exprs(second, 45000 / 90000, 90000)["scale"])
        self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve" for item in warnings))

    def test_nested_reverse_reverses_parent_bezier_easing(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "reverse": True,
                        "transform": {"scale": 1.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.1, 0.2, 0.7, 0.9]},
                            {"at_tick": 90000, "value": 1.2, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 90000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [{
                        "id": "child_clip", "asset_id": "asset", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 0.8, "interpolation": "bezier", "control_points": [0.1, 0.2, 0.7, 0.9]},
                            {"at_tick": 90000, "value": 1.2, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        leaf = next(track["clips"][0] for track in flattened if track["clips"])
        track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.transform.scale")
        points = sorted(track["keyframes"], key=lambda item: item["at_tick"])
        self.assertEqual([item["at_tick"] for item in points], [0, 90000])
        self.assertEqual(len(points[1]["control_points"]), 4)
        for actual, expected in zip(points[1]["control_points"], [0.3, 0.1, 0.9, 0.8]):
            self.assertAlmostEqual(actual, expected, places=9)
        leaf_track = next(item for item in leaf["keyframes"] if item.get("property") == "transform.scale")
        leaf_points = sorted(leaf_track["keyframes"], key=lambda item: item["at_tick"])
        self.assertEqual([item["at_tick"] for item in leaf_points], [0, 90000])
        for actual, expected in zip(leaf_points[1]["control_points"], [0.3, 0.1, 0.9, 0.8]):
            self.assertAlmostEqual(actual, expected, places=9)
        self.assertFalse(any(item.get("feature") == "nested_sequence_reverse_keyframes" for item in warnings))

    def test_nested_sequence_speed_curve_maps_source_boundaries(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 124766,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 124766, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed_curve": {"keyframes": [
                            {"at_tick": 0, "speed": 1.0},
                            {"at_tick": 90000, "speed": 2.0, "interpolation": "linear"},
                            {"at_tick": 180000, "speed": 1.0},
                        ]},
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {"id": "child_all", "asset_id": "asset", "timeline_start_tick": 0, "duration_tick": 180000, "source_in_tick": 0, "source_out_tick": 180000},
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = sorted(next(track["clips"] for track in flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([(clip["timeline_start_tick"], clip["duration_tick"]) for clip in clips], [(0, 62383), (62383, 62383)])
        self.assertEqual([(clip["source_in_tick"], clip["source_out_tick"]) for clip in clips], [(0, 90000), (90000, 180000)])
        self.assertEqual(len({clip["id"] for clip in clips}), 2)
        self.assertTrue(all(abs(clip["speed"] - 1.4427007358) < 1e-6 for clip in clips))
        self.assertTrue(any(item.get("feature") == "nested_sequence_speed_curve_piecewise" for item in warnings))
        self.assertFalse(any(item.get("feature") == "nested_sequence_speed_curve" for item in warnings))

    def test_nested_sequence_speed_curve_renders_locally(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-nested-speed-curve-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://nested-speed-curve", "--license-spdx", "CC0-1.0", "--evidence", "local://nested-speed-curve")
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_sequence", "id": "seq_speed_child", "name": "Speed child", "duration_tick": 90000},
                {"op": "append_clip", "sequence_id": "seq_speed_child", "track_id": "seq_speed_child_video_1", "id": "child_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000},
                {"op": "append_clip", "sequence_id": "seq_speed_child", "track_id": "seq_speed_child_video_1", "id": "child_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000},
                {"op": "append_sequence_clip", "sequence_id": "seq_main", "track_id": "track_video_1", "nested_sequence_id": "seq_speed_child", "id": "nested_speed", "source_in_tick": 0, "source_out_tick": 90000, "duration_tick": 62383, "speed_curve": {"keyframes": [{"at_tick": 0, "speed": 1.0}, {"at_tick": 45000, "speed": 2.0, "interpolation": "linear"}, {"at_tick": 90000, "speed": 1.0}]}}
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "nested-speed-curve.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertTrue(any(item.get("feature") == "nested_sequence_speed_curve_piecewise" for item in rendered["data"]["warnings"]))

    def test_nested_sequence_reverse_preserves_temporal_order(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "nested", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 180000,
                        "speed": 2.0, "reverse": True,
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 180000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [
                        {"id": "child_a", "asset_id": "asset", "timeline_start_tick": 0, "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000},
                        {"id": "child_b", "asset_id": "asset", "timeline_start_tick": 90000, "duration_tick": 90000, "source_in_tick": 90000, "source_out_tick": 180000},
                    ]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        clips = sorted(next(track["clips"] for track in flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([clip["id"] for clip in clips], ["nested.child_b", "nested.child_a"])
        self.assertEqual([(clip["timeline_start_tick"], clip["source_in_tick"], clip["source_out_tick"]) for clip in clips], [(0, 90000, 180000), (45000, 0, 90000)])
        self.assertTrue(all(clip.get("reverse") for clip in clips))
        self.assertFalse(any(item.get("feature") == "nested_sequence_reverse" for item in warnings))

        partial_project = json.loads(json.dumps(project))
        partial_parent = partial_project["sequences"][0]["tracks"][0]["clips"][0]
        partial_parent["source_in_tick"] = 45000
        partial_parent["source_out_tick"] = 135000
        partial_parent["speed"] = 1.0
        partial_warnings: list[dict] = []
        partial_flattened = _flatten_sequence_tracks(partial_project, partial_project["sequences"][0], partial_warnings)
        partial_clips = sorted(next(track["clips"] for track in partial_flattened if track["clips"]), key=lambda item: item["timeline_start_tick"])
        self.assertEqual([(clip["timeline_start_tick"], clip["source_in_tick"], clip["source_out_tick"]) for clip in partial_clips], [(0, 90000, 135000), (45000, 45000, 90000)])
        self.assertTrue(all(clip.get("reverse") for clip in partial_clips))

    def test_nested_sequence_multiple_keyframed_parents_keep_global_clock(self) -> None:
        project = {
            "sequences": [
                {
                    "id": "seq_main", "duration_tick": 90000,
                    "tracks": [{"id": "main_video", "kind": "video", "order": 0, "clips": [{
                        "id": "outer", "sequence_id": "seq_child", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "transform": {"position": {"x": 0.65, "y": 0.5}, "scale": 1.0},
                        "keyframes": [{"property": "transform.scale", "keyframes": [
                            {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.8, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_child", "duration_tick": 90000,
                    "tracks": [{"id": "child_video", "kind": "video", "order": 0, "clips": [{
                        "id": "inner", "sequence_id": "seq_grandchild", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                        "transform": {"position": {"x": 0.5, "y": 0.5}, "rotation": 10.0},
                        "keyframes": [{"property": "transform.rotation", "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 45.0, "interpolation": "linear"},
                        ]}],
                    }]}],
                },
                {
                    "id": "seq_grandchild", "duration_tick": 90000,
                    "tracks": [{"id": "grandchild_video", "kind": "video", "order": 0, "clips": [{
                        "id": "leaf", "asset_id": "asset", "timeline_start_tick": 0,
                        "duration_tick": 90000, "source_in_tick": 0, "source_out_tick": 90000,
                    }]}],
                },
            ],
        }
        warnings: list[dict] = []
        flattened = _flatten_sequence_tracks(project, project["sequences"][0], warnings)
        leaf = next(clip for track in flattened for clip in track["clips"] if clip["id"].endswith("leaf"))
        layers = leaf["_nested_parent_transforms"]
        self.assertEqual(len(layers), 2)
        self.assertFalse(any(item.get("feature") == "nested_sequence_multiple_parent_keyframes" for item in warnings))
        scale_track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.0.transform.scale")
        rotation_track = next(item for item in leaf["keyframes"] if item.get("property") == "nested.parent.1.transform.rotation")
        self.assertEqual([item["at_tick"] for item in scale_track["keyframes"]], [0, 90000])
        self.assertEqual([item["at_tick"] for item in rotation_track["keyframes"]], [0, 90000])
        expressions = _transform_exprs(leaf, 0.5, 90000)
        self.assertIn("-0.20000000", expressions["scale"])
        self.assertIn("45.00000000", expressions["rotation"])

    def test_mask_and_blend_compositing_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-composite-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source), "--verification-status", "verified", "--permitted-use", "commercial_ad", "--source-url", "local://composite", "--license-spdx", "CC0-1.0", "--evidence", "local://composite")
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "id": "track_video_2", "kind": "video", "order": 1},
                {"op": "add_track", "id": "track_video_3", "kind": "video", "order": 2},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "mask": {"type": "ellipse", "cx": 0.5, "cy": 0.5, "rx": 0.45, "ry": 0.35, "feather": 0.02}, "keyframes": [{"property": "mask.cx", "keyframes": [{"at_tick": 0, "value": 0.5, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.55, "interpolation": "linear"}]}]},
                {"op": "append_clip", "track_id": "track_video_2", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "blend": {"mode": "multiply", "opacity": 0.65}},
                {"op": "append_clip", "track_id": "track_video_3", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "mask": {"type": "path", "points": [[0.15, 0.2], [0.85, 0.2], [0.5, 0.85]]}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            progress_stderr = io.StringIO()
            with contextlib.redirect_stderr(progress_stderr):
                code, result = invoke("render", "--project", str(project), "--output", str(project / "renders" / "composite.mp4"), "--progress", "jsonl")
            self.assertEqual(code, 0, result)
            self.assertTrue((project / "renders" / "composite.mp4").exists())
            self.assertFalse(any(item.get("feature", "").startswith("mask:") for item in result["data"]["warnings"]))
            events = [json.loads(line) for line in progress_stderr.getvalue().splitlines() if line.strip()]
            self.assertTrue({"render_started", "artifact_written", "completed"}.issubset({event["type"] for event in events}), events)

    def test_mask_keyframes_and_feather_change_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-mask-pixels-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "timeline_start_tick": 45000, "source_in_tick": 0, "source_out_tick": 90000,
                "transform": {"opacity": 0.5},
                "mask": {"type": "circle", "cx": 0.2, "cy": 0.5, "radius": 0.18, "feather": 0.04,
                         "keyframes": [{"property": "cy", "keyframes": [{"at_tick": 0, "value": 0.5, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.6, "interpolation": "linear"}]}]},
                "keyframes": [{"property": "mask.cx", "keyframes": [{"at_tick": 0, "value": 0.2, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.8, "interpolation": "linear"}]}],
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "animated-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_feather" for item in rendered["warnings"]))

            def frame(at: float) -> bytes:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(result.stdout), 320 * 180 * 3)
                return result.stdout

            early, late = frame(0.5), frame(1.3)
            red_early = early[0::3]
            red_late = late[0::3]
            center_early = sum((i % 320) * value for i, value in enumerate(red_early)) / sum(red_early)
            center_late = sum((i % 320) * value for i, value in enumerate(red_late)) / sum(red_late)
            self.assertGreater(center_late - center_early, 130)
            # Alpha survives masking, the edge is feathered and pixels outside
            # the mask stay black. These assertions inspect the decoded output.
            self.assertTrue(100 <= red_early[90 * 320 + 64] <= 155)
            self.assertTrue(20 <= red_early[90 * 320 + 96] <= 100)
            self.assertLess(red_early[90 * 320 + 130], 15)

    def test_dynamic_polygon_mask_keyframes_change_pixels(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-polygon-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            points = [[0.08, 0.18], [0.42, 0.18], [0.25, 0.82]]
            tracks = []
            for index, (x, _y) in enumerate(points):
                tracks.append({
                    "property": f"points.{index}.x",
                    "keyframes": [
                        {"at_tick": 0, "value": x, "interpolation": "linear"},
                        {"at_tick": 90000, "value": x + 0.5, "interpolation": "linear"},
                    ],
                })
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "polygon", "points": points, "keyframes": tracks},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "animated-polygon.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_path_animation" for item in rendered["data"]["warnings"]), rendered)

            def red_centroid(at: float) -> float:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                red = result.stdout[0::3]
                total = sum(red)
                self.assertGreater(total, 0)
                return sum((index % 320) * value for index, value in enumerate(red)) / total

            self.assertGreater(red_centroid(0.15), 45)
            self.assertGreater(red_centroid(0.85) - red_centroid(0.15), 90)

    def test_dynamic_polygon_mask_feather_renders_inner_soft_edge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-polygon-feather-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {
                    "type": "polygon",
                    "points": [[0.2, 0.2], [0.8, 0.2], [0.5, 0.8]],
                    "keyframes": [{"property": "feather", "keyframes": [
                        {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 0.12, "interpolation": "linear"},
                    ]}],
                },
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-polygon-feather.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "mask_dynamic_feather" for item in rendered["data"]["warnings"]), rendered)

            def frame_rgb(at: float) -> bytes:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(result.stdout), 320 * 180 * 3)
                return result.stdout

            early, late = frame_rgb(0.1), frame_rgb(0.9)
            edge_index = (42 * 320 + 160) * 3
            outside_index = (25 * 320 + 160) * 3
            center_index = (90 * 320 + 160) * 3
            self.assertGreater(early[edge_index], late[edge_index] + 60, (early[edge_index], late[edge_index]))
            self.assertGreater(early[edge_index], 180, (early[edge_index], late[edge_index]))
            self.assertLess(late[edge_index], 190, (early[edge_index], late[edge_index]))
            self.assertGreater(late[center_index], 210)
            self.assertLess(late[outside_index], 15)

    def test_cubic_path_mask_segments_are_validated_and_rendered(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-cubic-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "path", "segments": [
                    {"type": "line", "from": [0.2, 0.2], "to": [0.8, 0.2]},
                    {"type": "cubic", "from": [0.8, 0.2], "control1": [0.95, 0.55], "control2": [0.05, 0.55], "to": [0.2, 0.2], "samples": 8},
                ]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            output = project / "renders" / "cubic-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "mask:path" for item in rendered["data"]["warnings"]), rendered)

    def test_dynamic_simple_mask_feather_renders_soft_edge(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-dynamic-feather-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            masks = [
                {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.25},
                {"type": "ellipse", "cx": 0.5, "cy": 0.5, "rx": 45 / 320, "ry": 45 / 180},
                {"type": "rectangle", "x": 115 / 320, "y": 45 / 180, "width": 90 / 320, "height": 90 / 180},
            ]
            for mask in masks:
                with self.subTest(mask=mask["type"]):
                    project = workspace / mask["type"]
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "mask": {**mask, "keyframes": [{"property": "feather", "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 0.12, "interpolation": "linear"},
                        ]}]},
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "dynamic-feather.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
                    self.assertEqual(code, 0, rendered)
                    self.assertFalse(any(item.get("feature") == "mask_dynamic_feather" for item in rendered["data"]["warnings"]), rendered)

                    def red_at(at: float, x: int, y: int = 90) -> int:
                        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                        return result.stdout[(y * 320 + x) * 3]

                    early, late = red_at(0.1, 120), red_at(0.9, 120)
                    self.assertGreater(early, late + 35, (early, late))
                    self.assertGreater(red_at(0.9, 160), 210)
                    self.assertLess(red_at(0.9, 90), 15)

    def test_dynamic_blend_opacity_changes_composite(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-blend-opacity-") as raw:
            workspace = Path(raw)
            red_source = self.make_image(workspace, "red.png")
            blue_source = workspace / "blue.png"
            completed = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180", "-frames:v", "1", str(blue_source)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, red_ingest = invoke("media", "ingest", "--project", str(project), "--input", str(red_source))
            _, blue_ingest = invoke("media", "ingest", "--project", str(project), "--input", str(blue_source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "add_track", "id": "track_overlay", "kind": "video", "order": 1},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": red_ingest["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_overlay", "asset_id": blue_ingest["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000, "blend": {"mode": "multiply", "opacity": 0.0}, "keyframes": [{"property": "blend.opacity", "keyframes": [{"at_tick": 0, "value": 0.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 1.0, "interpolation": "linear"}]}]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-blend.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)

            def center_red(at: float) -> int:
                result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                return result.stdout[(90 * 320 + 160) * 3]

            early, late = center_red(0.1), center_red(0.9)
            self.assertGreater(early, late + 80, (early, late))
            self.assertGreater(early, 190, (early, late))
            self.assertLess(late, 55, (early, late))

    def test_opacity_keyframes_on_normal_layers_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-normal-opacity-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            for property_name in ("transform.opacity", "blend.opacity"):
                with self.subTest(property=property_name):
                    project = workspace / property_name.replace(".", "_")
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "timeline_start_tick": 45000, "source_in_tick": 0, "source_out_tick": 90000,
                        "blend": {"mode": "normal", "opacity": 0.5 if property_name == "transform.opacity" else 1.0},
                        "keyframes": [{"property": property_name, "keyframes": [
                            {"at_tick": 0, "value": 0.0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                        ]}],
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "normal-opacity.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
                    self.assertEqual(code, 0, rendered)
                    colors = []
                    for at in (0.6, 1.3):
                        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
                        colors.append(result.stdout[(90 * 320 + 160) * 3])
                    self.assertGreater(colors[1], colors[0] + 60, colors)

    def test_inverted_mask_changes_coverage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-inverted-mask-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "mask": {"type": "circle", "cx": 0.2, "cy": 0.5, "radius": 0.18, "invert": True},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "inverted-mask.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
            self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
            red = frame.stdout[0::3]
            self.assertLess(red[90 * 320 + 64], 20)
            self.assertGreater(red[90 * 320 + 160], 180)

    def test_audio_ducking_and_volume_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-audio-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_audio_1", "overlap_policy": "allow"},
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "voice", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"role": "voice", "volume": 1.0}},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "music", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"role": "music", "duck_under_voice": True, "volume": 0.4}, "timeline_start_tick": 0},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "ducking.mp4"
            code, result = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertTrue(any(item.get("code") == "AUDIO_DUCKING_APPLIED" for item in result["warnings"]))

    def test_audio_pan_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-pan-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "id": "pan_automation", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000, "audio": {"pan": 0.0}, "keyframes": [{
                    "property": "audio.pan", "keyframes": [
                        {"at_tick": 0, "value": -1.0, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ],
                }]},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "pan-automation.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def channel_levels(at: float) -> tuple[float, float]:
                decoded = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-t", "0.1", "-vn", "-ac", "2", "-ar", "48000", "-f", "s16le", "pipe:1"],
                    capture_output=True,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
                samples = memoryview(decoded.stdout).cast("h")
                left = [abs(value) for value in samples[0::2]]
                right = [abs(value) for value in samples[1::2]]
                self.assertTrue(left and right)
                return sum(left) / len(left), sum(right) / len(right)

            early_left, early_right = channel_levels(0.15)
            late_left, late_right = channel_levels(0.85)
            self.assertGreater(early_left, early_right * 2.0)
            self.assertGreater(late_right, late_left * 2.0)

    def test_audio_pan_keyframes_reject_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-pan-invalid-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            before = (project / "project.json").read_bytes()
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_audio_1", "asset_id": ingest_result["data"]["asset"]["id"], "source_in_tick": 0, "source_out_tick": 90000,
                "keyframes": [{"property": "audio.pan", "keyframes": [{"at_tick": 0, "value": 1.1, "interpolation": "linear"}]}],
            }]}), encoding="utf-8")
            code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertNotEqual(code, 0, rejected)
            self.assertIn("PAN_KEYFRAME_RANGE", json.dumps(rejected))
            self.assertEqual((project / "project.json").read_bytes(), before)

    def test_numeric_pan_preserves_stereo_channels(self) -> None:
        """A centered numeric pan must not collapse an already-stereo asset."""
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-stereo-pan-") as raw:
            workspace = Path(raw)
            source = workspace / "stereo.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=green:s=320x180:r=24:d=1",
                    "-f", "lavfi", "-i", "aevalsrc=0.8*sin(2*PI*440*t)|0:s=48000:d=1",
                    "-shortest", "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
                ],
                capture_output=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "audio": {"pan": 0.0}, "keyframes": [{"property": "audio.pan", "keyframes": [{"at_tick": 0, "value": 0.0, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.0, "interpolation": "linear"}]}]},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "stereo-pan.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)

            decoded = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "0.5", "-i", str(output), "-t", "0.1", "-vn", "-ac", "2", "-ar", "48000", "-f", "s16le", "pipe:1"],
                capture_output=True,
            )
            self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", "replace"))
            samples = memoryview(decoded.stdout).cast("h")
            left = sum(abs(value) for value in samples[0::2]) / max(1, len(samples[0::2]))
            right = sum(abs(value) for value in samples[1::2]) / max(1, len(samples[1::2]))
            self.assertGreater(left, 1000)
            self.assertLess(right, left * 0.08, (left, right))

    def test_crossfade_transition_renders_with_overlapping_handles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-transition-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_video_1", "overlap_policy": "allow"},
                {"op": "append_clip", "track_id": "track_video_1", "id": "transition_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "timeline_start_tick": 0, "duration_tick": 45000},
                {"op": "append_clip", "track_id": "track_video_1", "id": "transition_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 36000, "duration_tick": 45000, "transition_in": {"type": "crossfade", "duration": 0.1}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            output = project / "renders" / "crossfade.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("code") == "RENDER_FEATURE_UNSUPPORTED" for item in rendered["warnings"]))

    def test_extended_xfade_catalog_transition_renders(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-xfade-catalog-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "update_track", "track_id": "track_video_1", "overlap_policy": "allow"},
                {"op": "append_clip", "track_id": "track_video_1", "id": "catalog_a", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "timeline_start_tick": 0, "duration_tick": 45000},
                {"op": "append_clip", "track_id": "track_video_1", "id": "catalog_b", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 36000, "duration_tick": 45000, "transition_in": {"type": "circleopen", "duration": 0.1}},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            output = project / "renders" / "circleopen.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            self.assertFalse(any(item.get("feature") == "complex_transition" for item in rendered["data"]["warnings"]), rendered)

    def test_normalized_crop_and_fill_mode_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-fit-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "crop": {"unit": "normalized", "x": 0.25, "y": 0, "width": 0.5, "height": 1, "fit": "fill"},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "normalized-crop.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "320", "--height", "180")
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_dynamic_crop_position_keyframes_render(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-keyframes-") as raw:
            workspace = Path(raw)
            source = workspace / "fixed-quadrants.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1,drawbox=x=0:y=0:w=160:h=90:color=red:t=fill,drawbox=x=160:y=90:w=160:h=90:color=blue:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for unit in ("pixels", "normalized"):
                with self.subTest(unit=unit):
                    project = workspace / unit
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    x_end, y_end = (160, 90) if unit == "pixels" else (0.5, 0.5)
                    def animated(property_name: str, end: float) -> dict:
                        return {"property": property_name, "keyframes": [
                            {"at_tick": 0, "value": 0, "interpolation": "linear"},
                            {"at_tick": 90000, "value": end, "interpolation": "linear"},
                        ]}
                    changes = workspace / "changes.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000, "timeline_start_tick": 45000,
                        "crop": {"unit": unit, "x": 0, "y": 0, "width": x_end, "height": y_end, "fit": "stretch", "keyframes": [animated("x", x_end)]},
                        "keyframes": [animated("crop.y", y_end)],
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / "dynamic-crop.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
                    self.assertEqual(code, 0, rendered)

                    def center_rgb(at: float) -> bytes:
                        frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                        self.assertEqual(len(frame.stdout), 160 * 90 * 3)
                        offset = (45 * 160 + 80) * 3
                        return frame.stdout[offset:offset + 3]

                    early = center_rgb(0.625)
                    late = center_rgb(1.375)
                    self.assertGreater(early[0], 220, early)
                    self.assertLess(early[2], 30, early)
                    self.assertLess(late[0], 30, late)
                    self.assertGreater(late[2], 220, late)

    def test_crop_keyframes_reject_invalid_or_unsupported_values_before_save(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-invalid-") as raw:
            workspace = Path(raw)
            source = self.make_image(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            before = (project / "project.json").read_bytes()
            cases = [
                ("x", 1.5, "CROP_KEYFRAME_RANGE"),
                ("width", 0.0, "CROP_KEYFRAME_RANGE"),
                ("fit", 0.5, "CROP_KEYFRAME_PROPERTY_UNSUPPORTED"),
                ("x", True, "CROP_KEYFRAME_VALUE_INVALID"),
            ]
            for property_name, value, expected in cases:
                with self.subTest(property=property_name, value=value):
                    changes = workspace / "invalid.json"
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "crop": {"unit": "normalized", "width": 0.5, "height": 0.5, "keyframes": [{
                            "property": property_name, "keyframes": [{"at_tick": 0, "value": value, "interpolation": "linear"}],
                        }]},
                    }]}), encoding="utf-8")
                    code, rejected = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertNotEqual(code, 0, rejected)
                    self.assertIn(expected, json.dumps(rejected))
                    self.assertEqual((project / "project.json").read_bytes(), before)

    def test_dynamic_crop_size_keyframes_render_on_fixed_canvas(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-size-keyframes-") as raw:
            workspace = Path(raw)
            source = workspace / "fixed-quadrants.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=black:s=320x180:r=24:d=1,drawbox=x=0:y=0:w=160:h=90:color=red:t=fill,drawbox=x=160:y=90:w=160:h=90:color=blue:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
                "crop": {"unit": "normalized", "x": 0, "y": 0, "width": 0.5, "height": 0.5, "fit": "stretch", "keyframes": [
                    {"property": "width", "keyframes": [
                        {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ]},
                    {"property": "height", "keyframes": [
                        {"at_tick": 0, "value": 0.5, "interpolation": "linear"},
                        {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                    ]},
                ]},
            }]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            output = project / "renders" / "dynamic-crop-size.mp4"
            code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
            self.assertEqual(code, 0, rendered)
            self.assertFalse(any(item.get("feature") == "crop_dynamic_size" for item in rendered["data"]["warnings"]), rendered)

            def sample(at: float) -> bytes:
                frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                self.assertEqual(len(frame.stdout), 160 * 90 * 3)
                offset = (60 * 160 + 120) * 3
                return frame.stdout[offset:offset + 3]

            early, late = sample(0.1), sample(0.9)
            self.assertGreater(early[0], 220, early)
            self.assertLess(early[2], 35, early)
            self.assertLess(late[0], 35, late)
            self.assertGreater(late[2], 180, late)

    def test_dynamic_crop_size_keyframes_support_fit_and_fill(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-crop-size-modes-") as raw:
            workspace = Path(raw)
            source = workspace / "source.mp4"
            completed = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=320x180:r=24:d=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            for fit in ("fit", "fill"):
                with self.subTest(fit=fit):
                    project = workspace / fit
                    self.assertEqual(invoke("project", "init", str(project))[0], 0)
                    _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
                    changes = workspace / f"{fit}.json"
                    size_tracks = [
                        {"property": "width", "keyframes": [{"at_tick": 0, "value": 0.8, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.2, "interpolation": "linear"}]},
                        {"property": "height", "keyframes": [{"at_tick": 0, "value": 0.2, "interpolation": "linear"}, {"at_tick": 90000, "value": 0.8, "interpolation": "linear"}]},
                    ]
                    changes.write_text(json.dumps({"operations": [{
                        "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest_result["data"]["asset"]["id"],
                        "source_in_tick": 0, "source_out_tick": 90000,
                        "crop": {"unit": "normalized", "x": 0.1, "y": 0.1, "width": 0.8, "height": 0.2, "fit": fit, "keyframes": size_tracks},
                    }]}), encoding="utf-8")
                    code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
                    self.assertEqual(code, 0, composed)
                    output = project / "renders" / f"dynamic-crop-{fit}.mp4"
                    code, rendered = invoke("render", "--project", str(project), "--output", str(output), "--profile", "custom", "--width", "160", "--height", "90")
                    self.assertEqual(code, 0, rendered)
                    self.assertEqual(rendered["data"]["probe"]["video"]["width"], 160)
                    self.assertEqual(rendered["data"]["probe"]["video"]["height"], 90)

                    def pixel(at: float, x: int, y: int) -> tuple[int, int, int]:
                        frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(at), "-i", str(output), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], capture_output=True)
                        self.assertEqual(frame.returncode, 0, frame.stderr.decode("utf-8", "replace"))
                        offset = (y * 160 + x) * 3
                        return tuple(frame.stdout[offset:offset + 3])

                    early_top = pixel(0.1, 80, 2)
                    early_center = pixel(0.1, 80, 45)
                    late_left = pixel(0.9, 2, 45)
                    late_center = pixel(0.9, 80, 45)
                    if fit == "fit":
                        self.assertLess(max(early_top), 20, early_top)
                        self.assertLess(max(late_left), 20, late_left)
                    else:
                        self.assertGreater(early_top[0], 180, early_top)
                        self.assertGreater(late_left[0], 180, late_left)
                    self.assertGreater(early_center[0], 180, early_center)
                    self.assertGreater(late_center[0], 180, late_center)

    def test_timeline_edit_operations_update_and_remove(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-timeline-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest_result = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest_result["data"]["asset"]["id"]
            first = workspace / "first.json"
            first.write_text(json.dumps({"operations": [
                {"op": "append_clip", "track_id": "track_video_1", "id": "clip_edit", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000, "motion_preset": "zoom_in", "amount": 0.1},
                {"op": "add_track", "track_id": "track_video_2", "kind": "video", "order": 1},
                {"op": "add_marker", "id": "marker_hook", "at_tick": 12000, "label": "hook"},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(first))
            self.assertEqual(code, 0, result)
            first_project = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(first_project["sequences"][0]["tracks"][0]["clips"][0]["keyframes"][0]["property"], "transform.scale")
            second = workspace / "second.json"
            second.write_text(json.dumps({"operations": [
                {"op": "update_clip", "clip_id": "clip_edit", "patch": {"duration_tick": 45000, "source_out_tick": 45000, "speed": 1.25, "reverse": True, "crop": {"x": 0, "y": 0, "width": 160, "height": 90}, "mask": {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.4}}},
                {"op": "set_sequence_duration", "duration_tick": 45000},
                {"op": "remove_marker", "marker_id": "marker_hook"},
                {"op": "remove_track", "track_id": "track_video_2"},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(second))
            self.assertEqual(code, 0, result)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            sequence = project_json["sequences"][0]
            self.assertEqual(sequence["duration_tick"], 45000)
            self.assertEqual(len(sequence["tracks"]), 2)
            self.assertEqual(sequence["tracks"][0]["clips"][0]["speed"], 1.25)
            self.assertTrue(sequence["tracks"][0]["clips"][0]["reverse"])
            self.assertEqual(sequence["tracks"][0]["clips"][0]["crop"]["width"], 160)
            self.assertEqual(sequence["tracks"][0]["clips"][0]["mask"]["type"], "circle")
            self.assertEqual(sequence["markers"], [])
            self.assertEqual(invoke("validate", "--project", str(project))[0], 0)
            third = workspace / "third.json"
            third.write_text(json.dumps({"operations": [{"op": "remove_clip", "clip_id": "clip_edit"}]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(third))
            self.assertEqual(code, 0, result)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project_json["sequences"][0]["duration_tick"], 1)

    def test_timeline_ripple_split_slip_speed_reverse_and_freeze(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-advanced-timeline-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "clip_a", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 45000, "duration_tick": 45000},
                {"op": "append_clip", "id": "clip_b", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 45000, "source_out_tick": 90000, "timeline_start_tick": 45000, "duration_tick": 45000},
                {"op": "split_clip", "clip_id": "clip_a", "at_tick": 20000, "left_id": "clip_a_left", "right_id": "clip_a_right"},
                {"op": "slip_clip", "clip_id": "clip_b", "delta_source_tick": -5000},
                {"op": "slide_clip", "clip_id": "clip_b", "delta_tick": 5000},
                {"op": "ripple_insert", "at_tick": 100000, "duration_tick": 9000},
                {"op": "ripple_delete", "at_tick": 0, "duration_tick": 9000},
                {"op": "set_clip_speed", "clip_id": "clip_b", "speed": 1.25},
                {"op": "reverse_clip", "clip_id": "clip_b", "enabled": True},
                {"op": "freeze_frame", "clip_id": "clip_b", "duration_tick": 9000},
            ]}), encoding="utf-8")
            code, result = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, result)
            code, validation = invoke("validate", "--project", str(project))
            self.assertEqual(code, 0, validation)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            clips = project_json["sequences"][0]["tracks"][0]["clips"]
            ids = {clip["id"] for clip in clips}
            self.assertTrue({"clip_a_left", "clip_a_right", "clip_b"}.issubset(ids))
            clip_b = next(clip for clip in clips if clip["id"] == "clip_b")
            self.assertTrue(clip_b["reverse"])
            self.assertEqual(clip_b["freeze"]["duration_tick"], 9000)
            output = project / "renders" / "advanced.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            self.assertIn("setpts=(PTS-STARTPTS)/1.25000000", planned["data"]["plan"]["filter_complex"])
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

    def test_midpoint_freeze_is_inserted_into_video_timeline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-midpoint-freeze-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "freeze.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "freeze_clip", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "freeze_frame", "clip_id": "freeze_clip", "at_tick": 45000, "duration_tick": 18000},
            ]}), encoding="utf-8")
            code, composed = invoke("timeline", "compose", "--project", str(project), "--input", str(changes))
            self.assertEqual(code, 0, composed)
            project_json = json.loads((project / "project.json").read_text(encoding="utf-8"))
            freeze_clip = project_json["sequences"][0]["tracks"][0]["clips"][0]
            freeze_clip["freeze"]["at_tick"] = freeze_clip["duration_tick"] + 1
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            code, invalid = invoke("validate", "--project", str(project))
            self.assertEqual(code, 2, invalid)
            freeze_clip["freeze"]["at_tick"] = 45000
            (project / "project.json").write_text(json.dumps(project_json), encoding="utf-8")
            output = project / "renders" / "midpoint-freeze.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            filter_graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("split=3[freeze0prein][freeze0holdin][freeze0postin]", filter_graph)
            self.assertFalse(any(item.get("feature") == "freeze_frame" for item in planned["data"]["plan"]["warnings"]))
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())
            probe = probe_media(output)
            self.assertAlmostEqual(probe["duration_seconds"], 1.2, delta=0.15)

    def test_midpoint_freeze_audio_pause_is_inserted_at_same_timeline_position(self) -> None:
        """The default freeze policy inserts silence where video is held."""
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-freeze-audio-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "freeze-audio.json"
            changes.write_text(json.dumps({"operations": [
                {"op": "append_clip", "id": "freeze_video", "track_id": "track_video_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000},
                {"op": "append_clip", "id": "freeze_audio", "track_id": "track_audio_1", "asset_id": asset_id, "source_in_tick": 0, "source_out_tick": 90000,
                 "keyframes": [{"property": "audio.volume", "keyframes": [
                     {"at_tick": 0, "value": 1.0, "interpolation": "linear"},
                     {"at_tick": 45000, "value": 0.2, "interpolation": "linear"},
                     {"at_tick": 90000, "value": 1.0, "interpolation": "linear"},
                 ]}]},
                {"op": "freeze_frame", "clip_id": "freeze_video", "at_tick": 45000, "duration_tick": 18000},
                {"op": "freeze_frame", "clip_id": "freeze_audio", "at_tick": 45000, "duration_tick": 18000},
            ]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "freeze-audio.mp4"
            code, planned = invoke("render", "--project", str(project), "--output", str(output), "--dry-run")
            self.assertEqual(code, 0, planned)
            graph = planned["data"]["plan"]["filter_complex"]
            self.assertIn("anullsrc=r=48000:cl=stereo,atrim=end_sample=9600", graph)
            self.assertIn("concat=n=3:v=0:a=1", graph)
            self.assertIn("t-0.20000000", graph)
            self.assertNotIn("apad=pad_dur=0.200000", graph)
            code, rendered = invoke("render", "--project", str(project), "--output", str(output))
            self.assertEqual(code, 0, rendered)
            self.assertTrue(output.exists())

            def mean_audio_abs(at: float) -> float:
                decoded = subprocess.run(
                    ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}", "-t", "0.08", "-i", str(output), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "pipe:1"],
                    capture_output=True,
                )
                self.assertEqual(decoded.returncode, 0, decoded.stderr.decode("utf-8", errors="replace"))
                samples = memoryview(decoded.stdout).cast("h")
                return sum(abs(value) for value in samples) / max(1, len(samples))

            before = mean_audio_abs(0.35)
            during = mean_audio_abs(0.56)
            after = mean_audio_abs(0.85)
            self.assertGreater(before, 300, (before, during, after))
            self.assertLess(during, before * 0.2, (before, during, after))
            self.assertGreater(after, 300, (before, during, after))

    def test_render_profiles_and_custom_canvas_quality(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-profiles-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://profiles", "--license-spdx", "CC0-1.0", "--evidence", "local://profiles",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            square = project / "renders" / "square.mp4"
            code, rendered = invoke("render", "--project", str(project), "--profile", "square", "--publish", "--output", str(square))
            self.assertEqual(code, 0, rendered)
            self.assertEqual(rendered["data"]["profile"], "square")
            self.assertEqual((rendered["data"]["probe"]["video"]["width"], rendered["data"]["probe"]["video"]["height"]), (1080, 1080))
            code, checked = invoke("quality", "check", "--project", str(project), "--input", str(square), "--profile", "square", "--require-audio")
            self.assertEqual(code, 0, checked)
            custom = project / "renders" / "custom.mp4"
            code, rendered = invoke("render", "--project", str(project), "--profile", "custom", "--width", "640", "--height", "360", "--output", str(custom))
            self.assertEqual(code, 0, rendered)
            self.assertEqual((rendered["data"]["probe"]["video"]["width"], rendered["data"]["probe"]["video"]["height"]), (640, 360))
            cancel_file = workspace / "cancel.flag"
            cancel_file.write_text("cancel", encoding="utf-8")
            cancelled_output = project / "renders" / "cancelled.mp4"
            code, cancelled = invoke("render", "--project", str(project), "--profile", "square", "--cancel-file", str(cancel_file), "--output", str(cancelled_output))
            self.assertEqual(code, 8, cancelled)
            self.assertEqual(cancelled["errors"][0]["code"], "CANCELLED")
            self.assertFalse(cancelled_output.exists())

    def test_render_local_webm_encoder_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-codec-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke("media", "ingest", "--project", str(project), "--input", str(source))
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": ingest["data"]["asset"]["id"],
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)
            output = project / "renders" / "codec.webm"
            code, result = invoke(
                "render", "--project", str(project), "--container", "webm", "--video-codec", "libvpx-vp9",
                "--audio-codec", "libopus", "--crf", "32", "--output", str(output),
            )
            self.assertEqual(code, 0, result)
            self.assertTrue(output.exists())
            self.assertIn("webm", result["data"]["probe"]["format"])
            manifest = json.loads((output.with_suffix(output.suffix + ".manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["settings"]["output"]["container"], "webm")
            self.assertEqual(manifest["settings"]["output"]["video"]["codec"], "libvpx-vp9")

    def test_cancelled_render_can_resume_with_unchanged_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-resume-") as raw:
            workspace = Path(raw)
            source = self.make_media(workspace)
            project = workspace / "project"
            self.assertEqual(invoke("project", "init", str(project))[0], 0)
            _, ingest = invoke(
                "media", "ingest", "--project", str(project), "--input", str(source),
                "--verification-status", "verified", "--permitted-use", "commercial_ad",
                "--source-url", "local://resume", "--license-spdx", "CC0-1.0", "--evidence", "local://resume",
            )
            asset_id = ingest["data"]["asset"]["id"]
            changes = workspace / "changes.json"
            changes.write_text(json.dumps({"operations": [{
                "op": "append_clip", "track_id": "track_video_1", "asset_id": asset_id,
                "source_in_tick": 0, "source_out_tick": 90000,
            }]}), encoding="utf-8")
            self.assertEqual(invoke("timeline", "compose", "--project", str(project), "--input", str(changes))[0], 0)

            cancel_file = workspace / "cancel.flag"
            cancel_file.write_text("cancel", encoding="utf-8")
            output = project / "renders" / "resume.mp4"
            code, cancelled = invoke("render", "--project", str(project), "--output", str(output), "--cancel-file", str(cancel_file))
            self.assertEqual(code, 8, cancelled)
            self.assertEqual(cancelled["errors"][0]["code"], "CANCELLED")
            operation_id = cancelled["operation_id"]
            self.assertEqual(operation_id, cancelled["errors"][0]["operation_id"])
            record_path = project / "operations" / f"{operation_id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "cancelled")
            self.assertTrue(record["plan"]["filter_complex"])
            self.assertTrue(record["project_fingerprint"])
            self.assertIn(asset_id, record["input_hashes"])

            asset_path = project / json.loads((project / "project.json").read_text(encoding="utf-8"))["assets"][0]["uri"]
            original_bytes = asset_path.read_bytes()
            asset_path.write_bytes(original_bytes + b"changed-after-cancel")
            cancel_file.unlink()
            code, changed = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 2, changed)
            self.assertEqual(changed["errors"][0]["code"], "RESUME_INPUT_CHANGED")
            asset_path.write_bytes(original_bytes)

            code, resumed = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 0, resumed)
            self.assertTrue(output.exists())
            self.assertEqual(resumed["data"]["resume_of"], operation_id)
            self.assertNotEqual(resumed["operation_id"], operation_id)

            code, rejected = invoke("render", "--project", str(project), "--resume", operation_id)
            self.assertEqual(code, 2, rejected)
            self.assertEqual(rejected["errors"][0]["code"], "RESUME_INPUT_CHANGED")

    def test_running_local_process_can_be_cancelled(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ai-ad-editor-cancel-process-") as raw:
            cancel_file = Path(raw) / "cancel.flag"
            timer = threading.Timer(0.25, lambda: cancel_file.write_text("cancel", encoding="utf-8"))
            timer.start()
            try:
                with self.assertRaises(AppError) as raised:
                    run_process([sys.executable, "-c", "import time; time.sleep(2)"], timeout=10, cancel_file=cancel_file)
            finally:
                timer.cancel()
            self.assertEqual(raised.exception.code, "CANCELLED")
            self.assertEqual(raised.exception.exit_code, 8)


if __name__ == "__main__":
    unittest.main()

