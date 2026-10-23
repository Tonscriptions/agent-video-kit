# 使用手册 / User manual

[中文 README](../../../README.md) · [English README](../../../README.en.md) · [Skills](SKILLS.md) · [Cases](CASES.md) · [Release](RELEASE.md)

## 1. 选择运行方式 / Select a runtime

建议使用发布包的固定 `cp313-win_amd64` 离线配置。软件包安装在新目录，不需要 Docker、WSL、容器或虚拟环境。
Use the pinned native Windows/CPython 3.13 x64 release bundle. Install to a new directory; no Docker, WSL, containers or virtual environments.
The release tag is `v0.1.0-alpha.1`; CLI/package/schema currently report `0.1.0`. The prerelease tag describes the acceptance stage, not a different schema version.

```powershell
# Source checkout, with existing development dependencies:
Set-Location E:\dev\sandbox\AI广告剪辑
.\ai-ad-editor.ps1 version
.\ai-ad-editor.ps1 doctor
.\ai-ad-editor.ps1 capabilities
.\ai-ad-editor.ps1 schema show
# Rebuild offline from the existing locked wheelhouse (new output only):
C:\Python313\python.exe -E -B -X utf8 product/offline/build.py --output E:\video-work\new-bundle --wheelhouse sources/python-runtime/cp313-win_amd64-media
```

Source launch uses the host's installed dependencies. The released `run.py` uses `-I -S` to isolate product dependencies from global site-packages.
本次全新安装的真实[安装回执](../../validation/evidence/release-v0.1.0-alpha.1-r2/installation-receipt.json)与[隔离依赖审计](../../validation/evidence/release-v0.1.0-alpha.1-r2/installation-dependency-audit.json)可直接复核。Actual native installation and isolated dependency audits are preserved separately from the historical test suite.
依赖固定为 ai-ad-editor 0.1.0、jsonschema 4.26.0、attrs 25.4.0、jsonschema-specifications 2025.9.1、referencing 0.37.0、rpds-py 2026.6.3、Pillow 12.1.0、NumPy 2.4.2。完整 wheel 与文件摘要在 bundle/manifest.json。

## 2. Agent 调用协议 / Agent protocol

1. Read `version`, `doctor`, `capabilities`, `schema show` and the relevant command's `--help`.
2. Create a new project; ingest existing local files with provenance and explicit usage permissions.
3. Write a reviewed edit JSON; apply it through compose/edit, inspect the plan and authored project.
4. Validate, check rights/policy, preview selected frames or ranges, and inspect actual artifacts.
5. Render to an absolute path inside the project, check output quality and preserve its manifest.
6. Export a portable project package with its conversion/loss report; retain the source project.

先探测能力，再创建工程、导入素材、计划编辑、核验、预览、渲染与交付。Agent 必须读取实际 JSON 和退出码；不能把“支持命令”当作任务已经执行。

Successful responses include `ok`, `command`, `request_id`, `operation_id`, `status`, `data`, `artifacts`, `warnings`, `errors`, `provenance`.
Failures retain a nonzero exit and error code. [Actual success](../../validation/evidence/release-v0.1.0-alpha.1-r2/render.stdout.json) · [Actual refusal](../../validation/evidence/release-v0.1.0-alpha.1-r2/remote-refused.stdout.json).
Do not infer exact failure exit numbers for every command from one example.

`--request-id` associates caller requests; `--idempotency-key` is supported by selected writes; `--progress jsonl` requests progress where implemented; `--dry-run` previews supported mutations without substituting for execution. Run command help for the chosen operation.

## 3. 时间线与项目结构 / Timelines and projects

默认作者时基为 90,000 ticks/秒，显示帧率 30/1；源时间、输出时间和原生 PTS 是不同量。编辑 JSON 必须使用真实返回的 asset ID。
Default author timebase is 90,000 ticks/second with a 30/1 display rate. Source time, authored time and native PTS differ. Use actual returned asset IDs.

```json
{
  "sequence_id": "seq_main",
  "operations": [
    {"op":"append_clip", "track_id":"track_video_1", "asset_id":"REPLACE_WITH_REAL_ID", "source_in_tick":0, "source_out_tick":270000},
    {"op":"append_clip", "track_id":"track_audio_1", "asset_id":"REPLACE_WITH_REAL_ID", "source_in_tick":0, "source_out_tick":270000}
  ]
}
```

This illustrative edit is not a ready-made input until its asset IDs and source ranges match a real asset. [Executed edit](../../validation/evidence/release-v0.1.0-alpha.1-r2/changes.json).
Audio is authored on an audio track explicitly; adding a video clip alone does not add its sound.

```text
project/
  project.json           # authored settings, assets and sequences
  rights-ledger.json     # provenance and permitted uses
  assets/                # imported / derived files
  history/               # snapshots
  operations/            # operation records
  renders/               # chosen output files and manifests
  cache/                 # derived previews / analysis (not the source of truth)
```

范围编辑优先使用 `timeline edit` 的事务入口。修剪、拆分、关键帧、速度曲线、倒放、跟踪和嵌套受各自契约约束。
Use transactional `timeline edit` for supported range edits. Trim/split, keyframes, speed curves, reverse, tracking and nesting retain their specific contracts. Never mutate an executing project's files to bypass locks.

## 4. 两条渲染路径 / Renderer selection

| Path | Selection | Supported intent | Boundary |
|---|---|---|---|
| Existing FFmpeg graph / 默认图 | default | Current advertised timeline, text, transitions and audio operations | Encoded precision and supported combinations follow existing contracts |
| Native Float32 / 显式浮点 | `settings.pixel_pipeline.engine = "float32-native-v1"` with complete configuration | Advertised native source clocks, floating composition, masks, geometry and selected color chains | Explicit source/working/delivery signals; unsupported effects reject; no automatic fallback |
| Frame bundle / 帧包交换 | `surface export` | Interchange Float32 frames and original int64 source clocks | Separate from selecting a render pipeline |

Float32 source/working/delivery declarations, numeric ranges, 1D LUT/shaper order and delivery quantization must follow the current schema and contracts. Specifying `linear` or wide-gamut primaries alone does not prove HDR, ICC compliance or physical luminance correctness.
See [native surface guide](../../Agent浮点帧包CLI使用与验收边界_2026-10-22.md) and [V112 actual installed color-chain evidence](../../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json).

## 5. 可选依赖 / Optional dependencies

| Feature | Additional existing local prerequisite | Missing prerequisite behavior |
|---|---|---|
| Basic render/probe/scopes | FFmpeg/ffprobe with required filters/codecs | doctor / command reports missing tool or capability |
| HTML motion/template | Native Node + pinned Playwright/Chromium configuration | Explicit refusal; no browser download |
| Local ASR/OCR/CTC/tracking/matting | Registered native inference environment + weights + evidence | Refusal; no model fetch or cloud fallback |
| LaMa/VACE/outpainting | Explicit weights/runtime/device and task-specific resources | Model/resource/rights failures remain visible |
| SoulX/local voice | Existing model and authorized reference voice | No assumed voice permission |
| Hardware encode/decode | Compatible existing native driver + encoder/decoder | `prefer`/`require` follow declared fallback/refusal behavior |

本轮发布案例没有调用模型；历史模型实测有各自时间、输入与失败边界，不代表基础包开箱具备相同推理环境。
The new release cases execute no models. Historical inference receipts describe their own runtime, inputs and limitations; they do not establish a bundled inference environment.

## 6. 权利、转换与交付 / Rights, conversion and delivery

默认导入 `unverified`。核验来源后用 `rights update` 保存许可和本地证据，执行 `rights check`。`render --publish` 是本地权利门禁，不向外发消息、不上传。
Imported assets start unverified. Record reviewed provenance using `rights update`, then `rights check`. `render --publish` applies local rights gating and performs no upload.
Our synthetic case sources have explicit CC0 evidence. Your media, fonts, templates, models and voices require their own permissions.

`convert export --target-format package` supports project delivery. JSON/OTIO/MLT/plain-draft adapters have different feature coverage. Review the conversion report; `--strict` refuses applicable approximate/unsupported/failed conversions. Lossless success for one package does not establish proprietary draft parity.

## 7. 预览、质量与失败恢复 / Preview, quality and recovery

`preview frame`/`preview range` produce real project output and cache metadata. `quality check` inspects encoded outputs; `--expensive` adds relevant scans. `quality scopes` creates local color-analysis images. `quality golden` compares a fixed reviewed baseline.
A passed decode, numerical comparison, static visual check, continuous playback and human listening are different evidence categories. Generated reports do not assert artistic quality.

项目变更前使用 `project snapshot`。事务中断使用 `project recover`；恢复历史快照使用 `project restore`。队列查看/运行/取消遵守项目锁；`render --resume` 仅在原操作与依赖仍符合当前契约时使用。
Snapshot before edits. Use `project recover` after interrupted metadata transactions, `project restore` for a reviewed snapshot, and inspect queue state before rerunning jobs. Resume is conditional on matching dependencies; this release does not include the later R114 runtime-closure candidate.

| Symptom | Action |
|---|---|
| FFmpeg/ffprobe missing | Put the existing native binary directory on `PATH`; rerun doctor |
| Output outside project | Use an absolute path under the chosen project; relative paths resolve against process cwd |
| Existing output / install target | Choose a new owned directory; previous evidence is preserved |
| Publish blocked | Inspect Rights Ledger restrictions and missing local evidence; do not mark third-party media verified without review |
| Unsupported Float32 effect | Read capabilities; change the reviewed plan or explicitly choose another supported path |
| Project busy | Inspect operation/queue owner, cancel through supported channels or wait; do not delete locks blindly |
| Model / browser absent | Supply an existing registered native runtime; the CLI does not fetch it |

## 8. 复现与回归 / Reproduction and regression

```powershell
# New output/evidence/assets directories are mandatory; failed runs are retained.
C:\Python313\python.exe -E -B -X utf8 scripts/first_release_cases.py --installed E:\tools\avk-alpha1 --output E:\video-work\release-case --evidence E:\video-work\release-evidence --assets E:\video-work\release-media
# Inspect available native full-run options before allocating a long regression:
C:\Python313\python.exe -E -B -X utf8 scripts/run_frozen_regression.py --help
```

The generator uses existing host Pillow and Segoe UI to create raster art, while each product command runs via the fresh installed `-I -S` launcher. It uses FFmpeg, no models/network/virtualization. Exact commands and native checks are retained.
Full baseline regression is 2,930 methods, 0 skips; optional native tools, pinned external fixtures and sufficient disk are required to reproduce that full environment. Release documentation checks reuse its unchanged frozen inputs and add new installed-case smoke checks; they do not claim a newly rerun full suite.

## 9. 更新与回滚 / Upgrade and rollback

保留旧安装目录、发布 ZIP/摘要和项目快照，在新目录安装新版本，对工程副本核验后切换 Agent 的启动命令。回滚时切回已保留的 `run.py` 和对应工程快照；不跨 schema 盲目降级。
Keep the previous install, release archive/digests and project snapshot. Install upgrades side by side and validate project copies before switching Agent commands. Roll back to the retained launcher and matching snapshot; do not blindly downgrade schemas. This first release has no earlier public release to roll back to.
