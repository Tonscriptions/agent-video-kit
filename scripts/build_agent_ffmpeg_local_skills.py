"""Create the local-release Skill namespace without changing legacy Skills."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'agent-ffmpeg-local-'
ROWS = [
    ('editor', 'agent-editor', '总入口：计划、项目创建与交付', 'Build and deliver local video edits',
     'Edit advertising videos or assemble a local Agent Project using the installed Agent Video Kit CLI. Use for project setup, editing, previews, renders and package delivery.',
     'Read `version`, `doctor`, `capabilities` and `schema show` first. Turn the brief into an explicit edit plan.\nCreate an owned project, ingest existing local media with rights evidence, compose, validate, preview, render,\ncheck the encoded output and export a project package. Route detailed timeline, template, model and quality work\nto the corresponding `agent-ffmpeg-local-` Skills.'),
    ('timeline', 'timeline', '时间线、关键帧、运镜、转场、嵌套', 'Author timelines, keyframes and camera moves',
     'Compose local video timelines, keyframes, camera presets, transitions, masks, speed curves, nested sequences, captions and audio automation using the installed CLI.',
     'Inspect `schema show`, `effects list` and `timeline compose --help`. Author an edit JSON with integer ticks,\nsource ranges, explicit tracks and audio. Use `timeline compose` or `timeline edit` only with supported operations.\nUse `preview frame` or `preview range` to inspect actual results before rendering. Keep native PTS and nested clocks.'),
    ('quality', 'quality', '成片、像素、蒙版、Scope 与证据核验', 'Check actual renders, scopes and evidence',
     'Review locally rendered video, pixels, masks, audio presence, scopes and render manifests. Use for output verification, quality reports and comparing source with actual encoded output.',
     'Run `validate` and `rights check`, then `quality check` on the actual encoded file. Inspect `quality scopes`\nand `quality golden` help for requested comparisons. Retain reports, manifests and actual source/output frames.\nSeparate automatic decode/PCM checks, static review, continuous playback and human listening. A passed encode\ndoes not establish natural quality or full CapCut parity.'),
    ('project-ops', 'project-ops', '快照、恢复、重链和队列', 'Operate local projects, snapshots and queues',
     'Manage local Agent Projects, snapshots, recovery, migration, media relinking, persistent render queues and cancellation with the installed CLI.',
     'Inspect `project --help`, `media relink --help` and `queue --help`. Snapshot before substantial edits.\nKeep source hashes and explicit relink mappings. Inspect saved state before recovery or replay. Run queued jobs\nwith explicit output paths and preserve cancellation/failure evidence; do not assume every command is idempotent.'),
    ('local-policy', 'local-policy', '离线运行与远程引用审计', 'Audit local execution and media references',
     'Audit local-only Agent video execution, project references and offline dependencies. Use to detect remote references, cloud providers, missing local models or implicit downloads.',
     'Run `policy audit --help`, then audit the project. Preserve structured refusal codes and nonzero exits.\nUse existing local media, tools and registered models. Missing weights or dependencies require a clear blocked\ncapability report; do not download, call cloud APIs or replace the pipeline silently.'),
    ('rights-ledger', 'rights-ledger', '素材、字体、模型与模板权利台账', 'Record local rights evidence and check gates',
     'Record source, license, creator and local rights evidence for media, fonts, templates, LUTs, audio and model artifacts; check local publication gates.',
     'Inspect `rights --help` and `media ingest --help`. Record the actual source and license evidence per asset;\nunknown rights remain unverified. Use `rights check` before `render --publish`. The publish flag is a local gate,\nnot a platform upload. When moving a project, rebind local license-evidence paths and recheck the ledger.'),
    ('local-models', 'local-models', '显式登记并运行已有离线模型', 'Run explicitly registered offline adapters',
     'Register existing offline model adapters for transcription, OCR, speech, separation, tracking, matting or repair. Use when local model paths and license evidence are available.',
     'Inspect `media adapter --help`, `media adapter register --help` and the advertised capability before running.\nRequire explicit existing weights, native dependencies, adapter settings and rights evidence. The base package\ncontains no model weights. Verify returned artifacts and actual inference reports; do not claim a missing adapter\nis integrated or copy experimental post-release commands from old notes.'),
    ('video-understand', 'video-understand', '镜头、静音、帧证据与转写', 'Analyze local shots, silence and frame evidence',
     'Analyze local video or audio for scene/silence candidates, contact sheets, transcripts and frame evidence using native analysis or explicitly registered offline models.',
     'Ingest and inspect local media, then read `media understand --help` and `media contact-sheet --help`.\nRetain candidate times, source ranges and extracted evidence. FFmpeg scene scores are candidates, not semantic\nunderstanding. OCR/ASR requires a registered local adapter. Keep transcript corrections traceable to source timing.'),
    ('template-library', 'template-library', '模板变量、素材索引和片段组复用', 'Apply local templates and reusable clip groups',
     'Build or apply local advertising templates, variable-driven variants, asset indexes and reusable edited clip groups using the installed CLI.',
     'Inspect `template --help`, `fragment --help` and `library --help`. Define required variables and asset IDs,\nverify rights, then apply into an owned project. Validate and preview each variant before rendering. Preserve\neditable clips, keyframes, audio and nested timing when reusing groups; do not replace them with a flattened render.'),
    ('long-to-short', 'long-to-short', '长视频、课程和口播转短片', 'Turn reviewed long recordings into short clips',
     'Turn a local talk, interview, course or recording into editable short clips using supplied or reviewed transcripts. Use for 长转短, 切片, 高光 and 拆条.',
     'Inspect the recording and supplied transcript. Use `media highlights --help` to propose candidates, then\nreview complete statements and surrounding context. Preserve selected source ranges, create explicit timelines\nwith captions/audio, preview and render. Without ASR weights use supplied transcripts; do not invent quotations.'),
    ('screen-demo', 'screen-demo', '录屏锚点、缩放与产品演示', 'Edit screen demos with anchors and clear zooms',
     'Edit local screen recordings into product demos with explicit action anchors, keyframed zooms, captions and visible outcomes. Use for 录屏演示, 产品教程 or 操作视频.',
     'Map actual actions, pauses and visible results to source times. Use supported timeline keyframes or camera\npresets, keeping cursor actions and result text legible. Retain honest waits or disclose sped-up sections.\nPreview key anchors at output resolution, render and verify the result. This Skill edits recordings; it is not\na browser-control integration. Close unused tabs if a separate browser tool is used.'),
    ('reference-remake', 'reference-remake', '参考片结构复刻与原创素材替换', 'Rebuild reference pacing using owned assets',
     'Rebuild a local reference video pacing, cuts, layout and motion as an editable Agent Project using original replacement assets. Use for 复刻, 做同款 and reference remakes.',
     'Analyze local reference evidence, separate timing/layout/motion from copyrighted creative assets, and map\nreplacement media to an explicit edit plan. Use supported timeline and effect contracts. Keep reference and\nreplacement provenance separate; preview comparison frames and record approximation or unsupported elements.'),
    ('ffmpeg', 'ffmpeg', '本地 FFmpeg 格式和媒体处理', 'Convert and inspect media with native FFmpeg',
     'Use native local FFmpeg and ffprobe for conversion, resizing, compression, audio extraction, GIF/MP4 conversion and preparation of local editing assets.',
     'Locate existing native `ffmpeg` and `ffprobe`, inspect the input and choose explicit codecs, streams and\noutput settings. Use argument arrays and a new local output; never concatenate untrusted shell text. Validate\nactual streams, duration and decode. For editable projects use the installed Agent CLI instead of flattening\nall edits. Read upstream examples only after checking current tool help and local policy.'),
    ('video-edit', 'video-edit', '修剪、拼接、变速与压缩', 'Trim, join and compress existing local media',
     'Trim, concatenate, resize, speed up, overlay, extract or replace audio, compress and convert local videos using native FFmpeg or the installed editable-project CLI.',
     'Probe inputs first. Use the installed CLI for edits that must remain editable; use native FFmpeg for\nexplicit one-off transformations. Select streams and audio policy deliberately. Preserve source files, reject\naccidental overwrite, and check the actual encoded output. Review any bundled helper before executing it.'),
    ('ad-creative', 'ad-creative', '广告文案、Hook 和创意变体', 'Plan ad hooks, copy and creative variants',
     'Plan or iterate ad copy, hooks, scripts, product claims and creative variants from a supplied offer and audience. Use for 广告创意, 广告建议 or ad creative testing.',
     'Collect the actual offer, audience, proof and call to action. Propose distinct hooks and a shot/copy plan,\nthen map the accepted variant to local assets, captions and timing for the editor Skill. Do not invent product\nclaims or performance metrics. This is creative guidance, not a rendering engine or ad-platform connector.\nUse the credited upstream reference for detailed copy frameworks.'),
    ('video-content-strategist', 'video-content-strategist', '内容定位、脚本与渠道策略', 'Plan content direction, scripts and variants',
     'Plan video content direction, scripts, short-form series or long-to-short reuse from supplied goals, audience and references. Use for 视频内容策略 or short-form planning.',
     'Define the audience, objective and format using supplied context. Produce a content plan and script with\nclear visual beats and evidence-backed claims. Hand an accepted brief to the installed editor workflow.\nUse local/supplied references; this Skill provides no platform scraping, online publishing or rendering kernel.'),
    ('campaign-analytics', 'campaign-analytics', '依据本地数据分析投放与变体', 'Analyze supplied campaign data and next edits',
     'Analyze supplied local campaign data for ROAS, CPA, conversion funnels, attribution assumptions and creative iteration. Use for 广告投放分析 or campaign analytics.',
     'Inspect the supplied dataset, period, units and missing values. State attribution assumptions and compute\nmetrics from actual rows. Keep observed facts separate from hypotheses. Recommend the next creative test\nand pass its brief to the ad/editor Skills. No ad-account connection or real-time campaign access is provided.\nReview the credited local analysis helpers and their dependencies before use.'),
]


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + '\n', encoding='utf8', newline='\n')


def main():
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    directories = [ROOT / 'skills' / (PREFIX + row[0]) for row in ROWS]
    if (ROOT / 'agent-ffmpeg-local-install-manifest.json').exists():
        raise SystemExit('Existing namespace manifest is preserved')
    if any((p / 'SKILL.md').exists() for p in directories):
        raise SystemExit('Existing prefixed Skills are preserved')
    entries = []
    upstream = {'ffmpeg', 'video-edit', 'ad-creative', 'video-content-strategist', 'campaign-analytics'}
    for suffix, legacy, zh, short, description, workflow in ROWS:
        name = PREFIX + suffix
        directory = ROOT / 'skills' / name
        source = ROOT / 'skills' / ('video-cut-' + legacy)
        reference = ''
        if suffix in upstream:
            copied = directory / 'references/upstream'
            shutil.copytree(source, copied)
            (copied / 'SKILL.md').rename(copied / 'workflow.md')
            reference = '\n## Credited reference\n\n[Upstream workflow and resources](references/upstream/workflow.md) retain their original provenance and licenses.\nThe installed-release contract above takes precedence over older source-launch examples.\n'
        runtime_text = '''Use the installed release, not `ai-ad-editor.ps1` or `product/src`. The shared launcher pins
`v0.1.0-alpha.1`, checks the installation receipt and launcher hash, and starts native Python with `-I -S`.

```powershell
$avkSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $avkSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk doctor
& $avk capabilities
& $avk COMMAND --help
```

Use argument arrays for paths with spaces/Chinese characters. A missing installation is an error; never
silently fall back to source. Read [the shared runtime contract](../agent-ffmpeg-local-editor/references/runtime.md)
for installation, CLI response checks and a complete project workflow.'''
        body = f'''---
name: {name}
description: {json.dumps(description, ensure_ascii=False)}
---

# Agent FFmpeg Local / {suffix}

{zh}. Local release: `v0.1.0-alpha.1`.

## Installed runtime

{runtime_text}

## Workflow

{workflow}

## Execution contract

- Native local Windows tools only; no Docker, WSL, containers or virtual environments.
- Media must be local; model inference requires existing explicitly registered weights and dependencies.
- Keep edits and output artifacts in the owned project; preserve source media and existing output files.
- Check exit code, `ok`, `status`, `errors`, `warnings` and `artifacts`; a dry plan is not an actual render.
- Author audio explicitly. `render --publish` checks local rights; it does not upload media.
- Inspect capabilities before effects or Float32 work; do not substitute unsupported features silently.
- Close unused browser tabs after any separately authorized browser operation.
{reference}'''
        save(directory / 'SKILL.md', body)
        title = 'Agent FFmpeg Local ' + suffix.replace('-', ' ').title()
        save(directory / 'agents/openai.yaml', '\n'.join([
            'interface:', '  display_name: ' + json.dumps(title),
            '  short_description: ' + json.dumps(short),
            '  default_prompt: ' + json.dumps('Use $' + name + ' to ' + description.split('. Use')[0][0].lower() + description.split('. Use')[0][1:].rstrip('.') + '.')]))
        entries.append({'name': name, 'purpose_zh': zh, 'legacy_name': source.name,
                        'legacy_skill_sha256': hashlib.sha256((source / 'SKILL.md').read_bytes()).hexdigest(),
                        'skill_md_sha256': hashlib.sha256((directory / 'SKILL.md').read_bytes()).hexdigest(),
                        'canonical_directory': str(directory), 'registration_directory': None,
                        'registration_verified': False})
    reference = '''# Installed-release runtime contract

This namespace always calls the locally installed `v0.1.0-alpha.1` package, using the editor Skill's
`scripts/run.ps1`. Other Skills share this launcher. The editable Skill source stays on E:; Codex reads
Windows directory junctions. `local/agent-ffmpeg/runtime.json` selects the native Python and installed path.
The launcher verifies the release pin, installation receipt and launcher digest, then runs the installed
`run.py` with `-I -S -B -X utf8`. It sets temporary/runtime paths on E: and offline model environment flags.
These flags are not an operating-system network sandbox; do not invoke network tools or providers.

To install on another checkout with existing Windows CPython 3.13 x64 and FFmpeg/ffprobe on PATH:

```powershell
& C:/Python313/python.exe -E -B -X utf8 scripts/install_agent_ffmpeg_local.py --evidence E:/path/to/checkout/docs/validation/evidence/my-local-install
.\\register-agent-ffmpeg-local-skills.ps1
```

Run the install script in the repository; the pinned release ZIP is in `docs/releases/v0.1.0-alpha.1/artifacts/`.
The installer preserves existing destinations. An unavailable installation requires repair/reinstallation,
not a source fallback. The namespace manifest lists all 17 entries. Legacy `video-cut-` Skills are separate.

## Project workflow

Read actual command help, `capabilities` and `schema show` before authoring JSON. Example with `$avk` set
as in SKILL.md (all source files and changes.json must already exist):

```powershell
$avkProject = 'E:/video-work/my-ad'
& $avk project init $avkProject --name 'My ad'
& $avk media ingest --project $avkProject --input 'E:/media/product.mp4'
# Use the returned data.asset.id in the edit JSON. Audio is an explicit track.
& $avk timeline compose --project $avkProject --input 'E:/video-work/changes.json'
& $avk validate --project $avkProject
& $avk preview frame --project $avkProject --frame 0
& $avk render --project $avkProject --output 'E:/video-work/my-ad/renders/ad.mp4'
& $avk quality check --project $avkProject --input 'E:/video-work/my-ad/renders/ad.mp4'
```

For publication, add actual license/source evidence and check `rights check`; `--publish` is only a local gate.
Project packages can retain absolute license-evidence paths: when moving hosts, rebind and recheck those paths.

## Rendering and verification

The default renderer uses FFmpeg. Explicit `settings.pixel_pipeline.engine = "float32-native-v1"` selects
its advertised subset and requires complete source/working/delivery signal settings and budgets from the
schema. `surface export` is a separate frame-bundle interchange command. Do not treat experimental later
Float32 transitions or legacy development notes as release capabilities. Node/Chromium and model weights
are optional existing dependencies, not bundled base features.

Return exact output paths, warnings, exit codes and error details. Verify actual decoded files and manifests;
static frames, continuous playback, automatic audio checks and human listening have separate acceptance.
The alpha package does not provide complete CapCut parity.
'''
    save(ROOT / 'skills' / (PREFIX + 'editor') / 'references/runtime.md', reference)
    manifest = {'format': 'agent-ffmpeg-local-skills-v1', 'status': 'prepared',
                'created_at_utc': datetime.now(timezone.utc).isoformat(),
                'release': runtime['release'], 'manifest_sha256': runtime['manifest_sha256'],
                'runtime_config': 'local/agent-ffmpeg/runtime.json', 'project_directory': str(ROOT),
                'codex_skills_directory': None, 'skill_count': len(entries), 'skills': entries}
    save(ROOT / 'agent-ffmpeg-local-install-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'ok': True, 'skills': len(entries), 'prefix': PREFIX}))


if __name__ == '__main__':
    main()
