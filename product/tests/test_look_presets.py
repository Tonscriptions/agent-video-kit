"""Behavioral checks for offline look assets, safe edits and native pixels."""
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ai_ad_editor import looks
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.rights import load_ledger
from test_magnetic_reorder import invoke

WORK = Path(__file__).resolve().parents[1] / ".runtime/look-tests"


class LookCatalogTests(unittest.TestCase):
    def test_hald_decode_uses_red_fastest_axes_and_preserves_channel_permutation(self):
        spec=importlib.util.spec_from_file_location("build_look_catalog", Path(__file__).resolve().parents[2]/"scripts/build_look_catalog.py")
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        b,g,r=np.meshgrid(*([np.arange(4)]*3), indexing="ij")
        expected=np.stack([b,r,g], axis=-1).reshape(-1,3)/3.
        WORK.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            path=Path(tmp)/"hald.png"
            Image.fromarray(np.rint(expected*255).astype("uint8").reshape(8,8,3)).save(path)
            actual,size=builder.read_table(path)
            self.assertEqual(size,4);np.testing.assert_allclose(actual,expected,atol=1e-12)
            samples=np.random.default_rng(42).uniform(0,1,(600,3))
            np.testing.assert_allclose(builder.tetra(actual,samples),samples[:,[2,0,1]],atol=1e-12)

    def test_all_100_have_distinct_numeric_transforms_and_verified_open_assets(self):
        rows = looks.catalog()["records"]
        for field in ("id", "transform_sha256", "preview_sha256"):
            self.assertEqual(len({r[field] for r in rows}), 100, field)
        for row in rows:
            with self.subTest(look=row["id"]):
                self.assertTrue(looks.inspect_look(row["id"])["verified"])
                self.assertEqual(row["license"]["spdx"], "MIT")
                raw = gzip.decompress((looks.DATA / row["lut"]).read_bytes()).decode("ascii")
                values = [list(map(float, line.split())) for line in raw.splitlines()
                          if line and (line[0].isdigit() or line[0] == "-")]
                self.assertEqual(len(values), row["grid_size"]**3)
                self.assertTrue(np.isfinite(values).all())

    def test_search_chinese_english_and_category(self):
        self.assertEqual(looks.list_looks()["count"], 100)
        self.assertEqual(looks.list_looks("黑白")["count"], 12)
        self.assertTrue(looks.list_looks("portra")["count"])
        self.assertTrue(all(r["category"] == "cinema" for r in looks.list_looks(category="cinema")["looks"]))
        self.assertEqual(looks.list_looks("does-not-exist")["count"], 0)

    def test_unknown_look_and_nonfinite_strength_fail(self):
        with self.assertRaises(AppError):
            looks.get_look("missing")
        for value in (float("nan"), float("inf"), -.1, 1.1):
            with self.assertRaises(AppError):
                looks.strength_value(value)

    def test_changed_packed_asset_is_refused(self):
        row = looks.catalog()["records"][0]
        WORK.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=WORK) as tmp:
            root = Path(tmp)
            for rel in (row["lut"], row["license"]["file"]):
                target=root/rel;target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((looks.DATA/rel).read_bytes())
            (root/row["lut"]).write_bytes(b"tampered")
            with patch.object(looks, "DATA", root), self.assertRaises(AppError) as caught:
                looks._payload(row)
            self.assertEqual(caught.exception.code, "LOOK_RESOURCE_INVALID")


class LookEditTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=WORK);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/"project"
        create_project(self.root, name="Look test")
        self.look="t3-kodak-gold-200"

    def run_apply(self, *extra):
        return invoke("look", "apply", "--project", str(self.root), "--id", self.look, "--global", *extra)

    def test_dry_run_does_not_write_project_assets_ledger_or_snapshots(self):
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        code, result=self.run_apply("--dry-run")
        self.assertEqual(code, 0, result);self.assertEqual(result["status"], "planned")
        after={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_apply_replaces_presets_preserves_manual_effects_and_explicit_append(self):
        _,project=load_project(self.root)
        manual={"type":"saturation", "parameters":{"value":.8}}
        project["settings"]["adjustments"]=[manual];save_project(self.root, project)
        for _ in range(2):
            code,result=self.run_apply();self.assertEqual(code, 0, result)
        _,project=load_project(self.root)
        effects=project["settings"]["adjustments"]
        self.assertEqual(len(effects), 2);self.assertEqual(effects[0], manual)
        code,result=self.run_apply("--append");self.assertEqual(code, 0, result)
        _,project=load_project(self.root)
        self.assertEqual(len(project["settings"]["adjustments"]), 3)
        ledger=load_ledger(self.root)
        self.assertEqual(len([r for r in ledger["records"] if r["asset_id"].startswith("look_")]), 1)

    def test_idempotent_replay_does_not_stack_or_add_snapshot(self):
        code,first=self.run_apply("--append", "--idempotency-key", "look-once");self.assertEqual(code, 0, first)
        before=(self.root/"project.json").read_bytes()
        code,second=self.run_apply("--append", "--idempotency-key", "look-once");self.assertEqual(code, 0, second)
        self.assertEqual((self.root/"project.json").read_bytes(), before)
        self.assertEqual(first["operation_id"], second["operation_id"])

    def test_portable_lut_and_license_evidence_are_copied_relative_to_project(self):
        code,result=self.run_apply();self.assertEqual(code, 0, result)
        resource=result["data"]["resource"]
        moved=self.root.with_name("moved");shutil.copytree(self.root, moved)
        self.assertTrue((moved/resource["uri"]).is_file())
        for field in ("license_url", "evidence"):
            self.assertFalse(Path(resource["rights"][field]).is_absolute())
            self.assertTrue((moved/resource["rights"][field]).is_file())
        code,result=invoke("look", "apply", "--project", str(moved), "--id", self.look, "--global")
        self.assertEqual(code, 0, result)

    def test_changed_project_lut_and_license_are_preserved_and_refused(self):
        code,result=self.run_apply();self.assertEqual(code, 0, result)
        cube=self.root/result["data"]["resource"]["uri"]
        cube.write_bytes(b"human-modified")
        before=(self.root/"project.json").read_bytes()
        code,result=self.run_apply();self.assertNotEqual(code, 0)
        self.assertEqual(cube.read_bytes(), b"human-modified")
        self.assertEqual((self.root/"project.json").read_bytes(), before)

    def test_invalid_target_and_strength_leave_metadata_unchanged(self):
        before=(self.root/"project.json").read_bytes()
        for value in ("nan", "inf", "-0.01", "1.01"):
            code,result=self.run_apply("--strength", value);self.assertNotEqual(code, 0, result)
        code,result=invoke("look", "apply", "--project", str(self.root), "--id", self.look, "--clip-id", "missing")
        self.assertNotEqual(code, 0);self.assertEqual((self.root/"project.json").read_bytes(), before)

    def test_clip_scope_preserves_other_clips_and_refuses_locked_or_audio_tracks(self):
        _,project=load_project(self.root)
        track=project["sequences"][0]["tracks"][0]
        track["clips"]=[{"id":"clip_a","effects":[]}, {"id":"clip_b","effects":[]}]
        candidate,plan=looks.plan_apply(project, self.look, .6, clip_id="clip_a")
        self.assertEqual(candidate["sequences"][0]["tracks"][0]["clips"][1], track["clips"][1])
        self.assertEqual(len(candidate["sequences"][0]["tracks"][0]["clips"][0]["effects"]), 1)
        self.assertEqual(project["sequences"][0]["tracks"][0]["clips"][0]["effects"], [])
        track["locked"]=True
        with self.assertRaises(AppError):looks.plan_apply(project, self.look, 1., clip_id="clip_a")
        track["locked"]=False;track["kind"]="audio"
        with self.assertRaises(AppError):looks.plan_apply(project, self.look, 1., clip_id="clip_a")

    def test_hdr_and_float_pipeline_are_explicitly_refused(self):
        _,project=load_project(self.root)
        for patch_value in ({"pixel_pipeline":{"engine":"float32-native-v1"}}, {"color":{"transfer":"smpte2084"}}):
            trial=copy.deepcopy(project);trial["settings"].update(patch_value)
            with self.assertRaises(AppError):looks.plan_apply(trial, self.look, 1., clip_id=None, global_scope=True)

    def test_metadata_failure_rolls_back_registry_and_ledger(self):
        before=(self.root/"project.json").read_bytes()
        with patch("ai_ad_editor.cli.save_project", side_effect=AppError("TEST_FAIL", "simulated disk failure", exit_code=5)):
            code,result=self.run_apply()
        self.assertNotEqual(code, 0)
        self.assertEqual((self.root/"project.json").read_bytes(), before)
        self.assertFalse((self.root/"assets/lut-library.json").exists())
        self.assertFalse(any(r["asset_id"].startswith("look_") for r in load_ledger(self.root)["records"]))

    def test_package_roundtrip_retains_builtin_id_registry_and_relative_evidence(self):
        code,result=self.run_apply();self.assertEqual(code, 0, result)
        package=self.root.with_name("looks.zip")
        code,result=invoke("convert","export","--project",self.root,"--output",package,"--target-format","package")
        self.assertEqual(code, 0, result)
        imported=self.root.with_name("imported")
        code,result=invoke("convert","import","--input",package,"--output",imported);self.assertEqual(code, 0, result)
        _,project=load_project(imported)
        self.assertEqual(project['settings']['adjustments'][0]['parameters']['lut_id'], "look_"+self.look)
        self.assertTrue((imported/f"assets/look-evidence/{self.look}/LICENSE.txt").is_file())
        self.assertTrue((imported/"assets/lut-library.json").is_file())
        code,result=invoke("look","apply","--project",imported,"--id",self.look,"--global")
        self.assertEqual(code, 0, result)

    def test_second_edit_failure_preserves_existing_registry(self):
        code,result=self.run_apply();self.assertEqual(code, 0, result)
        before=(self.root/"assets/lut-library.json").read_bytes()
        with patch("ai_ad_editor.cli.save_project", side_effect=AppError("TEST_FAIL", "disk failure", exit_code=5)):
            code,result=invoke("look","apply","--project",self.root,"--id","t3-fuji-velvia-50","--global")
        self.assertNotEqual(code, 0)
        self.assertEqual((self.root/"assets/lut-library.json").read_bytes(), before)


@unittest.skipUnless(shutil.which("ffmpeg"), "native FFmpeg required")
class LookPixelTests(unittest.TestCase):
    def setUp(self):
        WORK.mkdir(parents=True, exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=WORK);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_strength_zero_preserves_pixels_and_full_preset_changes_them(self):
        source=looks.DATA/"previews/reference.png"
        zero=self.root/"zero.png";full=self.root/"full.png"
        looks.preview("t3-kodak-gold-200", str(zero), input_path=str(source), strength=0)
        looks.preview("t3-kodak-gold-200", str(full), input_path=str(source), strength=1)
        self.assertEqual(Image.open(zero).convert("RGB").tobytes(), Image.open(source).convert("RGB").tobytes())
        self.assertNotEqual(Image.open(full).convert("RGB").tobytes(), Image.open(source).convert("RGB").tobytes())

    def test_preview_partial_strength_dry_run_and_existing_output_protection(self):
        target=self.root/"preview.png"
        looks.preview("sp-amber-haze", str(target), strength=.5, dry_run=True)
        self.assertFalse(target.exists())
        result=looks.preview("sp-amber-haze", str(target), strength=.5)
        self.assertTrue(result["warnings"])
        before=target.read_bytes()
        with self.assertRaises(AppError):looks.preview("sp-amber-haze", str(target))
        self.assertEqual(before, target.read_bytes())

    def test_remote_input_and_output_are_refused(self):
        with self.assertRaises(AppError):looks.preview("sp-amber-haze", str(self.root/"x.png"), input_path="https://example.com/a.png")
        with self.assertRaises(AppError):looks.preview("sp-amber-haze", "https://example.com/a.png")


if __name__ == "__main__":
    unittest.main()
