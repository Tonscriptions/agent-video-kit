"""Compile pinned MIT look data. Native Windows Python/FFmpeg only; no network.

Hald RGB samples retain their native bit depth; tables use red-fastest order.
Resampling uses tetrahedral interpolation with measured approximation error.
"""
from pathlib import Path
import gzip
import hashlib
import json
import re
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "product/src/ai_ad_editor/look_data"
EVIDENCE = ROOT / "docs/validation/evidence/lut-research-20261024-r1"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def tetra(table, rgb):
    n = round(len(table) ** (1 / 3))
    pos = np.clip(rgb, 0, 1) * (n - 1)
    low = np.minimum(np.floor(pos).astype(np.int64), n - 2)
    frac = pos - low
    order = np.argsort(-frac, axis=1, kind="stable")
    weights = np.take_along_axis(frac, order, axis=1)
    steps = np.array([1, n, n * n])[order]
    i0 = low @ np.array([1, n, n * n])
    i1 = i0 + steps[:, 0]
    i2 = i1 + steps[:, 1]
    i3 = i2 + steps[:, 2]
    return (table[i0] + weights[:, :1] * (table[i1] - table[i0])
            + weights[:, 1:2] * (table[i2] - table[i1])
            + weights[:, 2:3] * (table[i3] - table[i2]))


def read_table(path):
    if path.suffix.lower() == ".png":
        with Image.open(path) as image:
            width, height = image.size
        level = round(width ** (1 / 3))
        if width != height or level ** 3 != width:
            raise ValueError("Invalid Hald geometry: " + str(path))
        depth, color = path.read_bytes()[24:26]
        if depth == 8 and color == 2:
            # Expanding rgb24 through swscale can alter endpoints/dither. Read
            # native RGB bytes directly; never invent precision in an 8-bit Hald.
            with Image.open(path) as image:
                return np.asarray(image.convert("RGB")).reshape(-1,3).astype(np.float64)/255., level**2
        if depth != 16 or color != 2:
            raise ValueError("Only native RGB8/RGB16 Hald PNG is supported")
        result = subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-threads", "1", "-i", str(path),
                                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb48be", "pipe:1"],
                                capture_output=True, check=True, timeout=60)
        table = np.frombuffer(result.stdout, dtype=">u2").reshape(-1, 3).astype(np.float64) / 65535
        return table, level ** 2
    size = None
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        parts = line.split("#", 1)[0].split()
        if not parts:
            continue
        if parts[0] == "LUT_3D_SIZE":
            size = int(parts[1])
        elif parts[0] in {"DOMAIN_MIN", "DOMAIN_MAX"}:
            expected = [0., 0., 0.] if parts[0] == "DOMAIN_MIN" else [1., 1., 1.]
            if list(map(float, parts[1:])) != expected:
                raise ValueError("Non-unit domain requires explicit conversion")
        elif len(parts) == 3:
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                pass
    table = np.asarray(rows, dtype=np.float64)
    if not size or table.shape != (size ** 3, 3) or not np.isfinite(table).all():
        raise ValueError("Incomplete/invalid CUBE: " + str(path))
    return table, size


def reference_image():
    """Synthetic RGB reference, skin-tone swatches and a fictional product card."""
    w, h = 480, 300
    yy, xx = np.mgrid[0:h, 0:w]
    colors = np.stack([255 * xx / (w - 1), 255 * yy / (h - 1),
                       255 * (.5 + .5 * np.sin(xx / 60 + yy / 70))], axis=-1).astype("uint8")
    im = Image.fromarray(colors)
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 19)
    draw.rounded_rectangle((24, 35, 185, 239), radius=22, fill="#eee4cb")
    draw.rounded_rectangle((66, 68, 143, 166), radius=13, fill="#e29738", outline="#fff5db", width=5)
    draw.rectangle((86, 53, 123, 73), fill="#333b3b")
    draw.text((63, 184), "AVK / 100", fill="#293b44", font=font)
    swatches = ["#f5dbc6", "#cf9b7b", "#815438", "#ffffff", "#999999", "#111111"]
    for i, color in enumerate(swatches):
        draw.rectangle((215+i*40, 244, 250+i*40, 278), fill=color)
    return im


def main():
    sources = json.loads((ROOT / "sources/lut-research-20261024/look-sources.json").read_bytes())
    for sub in ("luts", "previews", "licenses"):
        (DEST / sub).mkdir(parents=True, exist_ok=True)
    ref = reference_image()
    ref.save(DEST / "previews/reference.png")
    ref_rgb = np.asarray(ref).reshape(-1, 3) / 255.
    b, g, r = np.meshgrid(*([np.linspace(0, 1, 33)] * 3), indexing="ij")
    grid = np.stack([r, g, b], axis=-1).reshape(-1, 3)
    random = np.random.default_rng(100).uniform(0, 1, (8192, 3))
    records = []
    for source in sources:
        repo = source["repository"]
        short = "t3" if repo.startswith("t3mujinpack") else "sp"
        upstream_dir = EVIDENCE / repo.replace("/", "--")
        notice = upstream_dir / ("LICENSE.txt" if short == "t3" else "LICENSE")
        notice_rel = f"licenses/{short}-MIT.txt"
        (DEST / notice_rel).write_bytes(notice.read_bytes())
        for entry in source["files"]:
            path = ROOT / entry["path"]
            if digest(path.read_bytes()) != entry["sha256"]:
                raise ValueError("Source hash changed: " + str(path))
            table, size = read_table(path)
            # Keep CUBE grids exactly: moving a 64-grid LUT onto a 33-grid can
            # soften abrupt creative transitions. Dense 144-grid Hald images
            # use a portable 33-grid with disclosed error measurements.
            out_size = size if short == "sp" else 33
            normalized = table if short == "sp" else tetra(table, grid)
            title = path.stem.split(" - ")[-1]
            look_id = short + "-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            folder = entry["upstream_path"]
            category = ("film-bw" if "Black and White" in folder else "film-negative" if "Color Negative" in folder
                        else "film-slide" if "Color Slide" in folder else "cinema" if "Cinema Through" in folder
                        else "infrared" if "Infrared" in folder else "lomography" if "Lomography" in folder
                        else "landscape" if "Scenic Moods" in folder else "creative")
            labels = {"film-bw":"黑白胶片", "film-negative":"彩色负片", "film-slide":"反转片",
                      "cinema":"电影", "infrared":"红外创意", "lomography":"Lomo", "landscape":"风景", "creative":"创意色彩"}
            raw = (f'TITLE "AVK {look_id}"\nLUT_3D_SIZE {out_size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n'
                   + "".join("%.7f %.7f %.7f\n" % tuple(row) for row in normalized)).encode("ascii")
            lut_rel = f"luts/{look_id}.cube.gz"
            existing = DEST / lut_rel
            packed = existing.read_bytes() if existing.is_file() else b""
            if not packed or gzip.decompress(packed) != raw:
                packed = gzip.compress(raw, compresslevel=9, mtime=0)
            (DEST / lut_rel).write_bytes(packed)
            output = tetra(normalized, ref_rgb)
            preview = Image.fromarray(np.rint(np.clip(output, 0, 1)*255).astype("uint8").reshape(300, 480, 3))
            preview.thumbnail((240, 150))
            preview_rel = f"previews/{look_id}.webp"
            preview.save(DEST / preview_rel, lossless=True, method=4)
            err = np.abs(tetra(table, random) - tetra(normalized, random))
            records.append({"id":look_id, "name":title, "name_zh":f"{labels[category]} · {title}",
                "category":category, "tags":[labels[category], short, "SDR", "MIT", title],
                "recommended_strength":1.0, "grid_size":out_size, "lut":lut_rel, "sha256":digest(raw),
                "packed_sha256":digest(packed), "bytes":len(raw), "transform_sha256":digest(normalized.astype("<f4").tobytes()),
                "preview":preview_rel, "preview_sha256":digest((DEST / preview_rel).read_bytes()),
                "source":{"repository":repo, "commit":source["commit"], "path":entry["upstream_path"],
                          "sha256":entry["sha256"], "git_blob":entry["git_blob"], "grid_size":size},
                "license":{"spdx":"MIT", "file":notice_rel, "sha256":digest(notice.read_bytes()),
                           "creator":"João Almeida" if short == "t3" else "Nixua / Striped Purple"},
                "normalization":{"method":"native-CUBE-grid-retained-v1" if short == "sp" else "native-depth-Hald-to-33-tetrahedral-v1",
                                 "source_bit_depth":int(path.read_bytes()[24]) if short == 't3' else None,
                                 "sample_count":len(random), "sampled_max_abs_rgb_error":float(err.max()),
                                 "sampled_mean_abs_rgb_error":float(err.mean())}})
            print(json.dumps({"id":look_id, "source_grid":size, "packed_bytes":len(packed)}), flush=True)
    records.sort(key=lambda x:x["id"])
    if len(records) != 100 or any(len({r[k] for r in records}) != 100 for k in ("id", "transform_sha256", "preview_sha256")):
        raise ValueError("Expected 100 different IDs, transforms AND rendered previews")
    catalog = {"version":"1.0.0", "count":100, "network":"disabled", "records":records,
        "color_contract":"Creative encoded RGB for SDR display-referred material; upstream transfer/primaries unspecified. Not a camera/Log/HDR calibration.",
        "trademarks":"Community film-inspired names identify upstream looks; no manufacturer endorsement or official proprietary filter equivalence.",
        "reference":{"file":"previews/reference.png", "sha256":digest((DEST / "previews/reference.png").read_bytes()),
                     "kind":"synthetic-product-gradients-and-skin-color-swatches", "license":"CC0-1.0"}}
    (DEST / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"count":100,"packed_bytes":sum((DEST/r["lut"]).stat().st_size for r in records),
                      "unique_transforms":100,"max_sampled_rgb_error":max(r["normalization"]["sampled_max_abs_rgb_error"] for r in records)}))


if __name__ == "__main__":
    main()
