"""Build bilingual, evidence-linked first-release documentation (no network)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
REL = ROOT / 'docs/releases' / TAG
ASSET = 'docs/assets/release-' + TAG + '-r2'
EVIDENCE = 'docs/validation/evidence/release-' + TAG + '-r2'
BASE = 'docs/validation/evidence/float-shaper-20261023-lab'
URL = 'https://github.com/Tonscriptions/agent-video-kit'


def save(path, text):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + '\n', encoding='utf8', newline='\n')


def jread(path):
    return json.loads((ROOT / path).read_bytes())


SKILLS = [
('agent-editor', '总入口：计划、项目创建与交付', 'Route editing work, initialize projects and deliver outputs', 'brief + local media → project / manifest', 'project init; timeline compose; render'),
('timeline', '时间线、关键帧、运镜、转场、嵌套', 'Author timelines, keyframes, camera moves, transitions and nesting', 'edit JSON → editable sequence', 'timeline compose; timeline edit; preview frame'),
('quality', '像素、蒙版、Scope、渲染证据核验', 'Review pixels, masks, scopes and render evidence', 'render + manifest → review report', 'quality check; quality scopes; quality golden'),
('project-ops', '快照、恢复、重链和队列', 'Manage snapshots, recovery, relinking and render queues', 'project / jobs → recoverable operations', 'project snapshot; project recover; queue run'),
('local-policy', '本地运行规则与远程引用审计', 'Audit local-only execution and remote references', 'project → audit / refusal', 'policy audit'),
('rights-ledger', '素材、字体、模型和模板权利台账', 'Record and check media, font, model and template rights', 'local evidence → rights ledger', 'rights check; rights update'),
('local-models', '显式登记已有离线模型', 'Register and run existing offline model adapters', 'existing weights + licenses → local inference artifacts', 'media adapter register; subtitle transcribe; audio separate'),
('video-understand', '镜头、静音、帧证据与转写', 'Analyze scenes, silence, frame evidence and transcripts', 'local video / audio → analysis JSON', 'media understand; media contact-sheet'),
('template-library', '模板变量、素材索引、片段组复用', 'Apply templates, index assets and reuse edited clip groups', 'template + variables → editable variant', 'template apply; library index; fragment apply'),
('long-to-short', '口播/课程长视频转短片', 'Turn talks or lessons into reviewed short clips', 'recording + reviewed transcript → short-clip projects', 'media highlights; timeline compose'),
('screen-demo', '录屏锚点、缩放与产品演示', 'Edit screen demos with action anchors and zooms', 'screen recording + action anchors → demo project', 'timeline compose; preview range'),
('reference-remake', '参考片结构复刻并替换原创素材', 'Rebuild reference pacing and layout using replacement assets', 'reference + original replacements → editable remake', 'media understand; timeline compose'),
('ffmpeg', '通用本地音视频处理', 'Perform general local FFmpeg media operations', 'local files → converted / extracted media', 'native ffmpeg / ffprobe'),
('video-edit', '修剪、拼接、压缩等工具流程', 'Trim, concatenate, resize and compress local media', 'local files + edit instructions → output', 'native ffmpeg; inspect bundled scripts'),
('ad-creative', '广告创意、文案和变体规划', 'Plan ad copy, hooks and creative variants', 'offer + audience → creative brief', 'advisory skill; no render kernel'),
('video-content-strategist', '内容定位与脚本策略', 'Plan content direction, scripts and channel strategy', 'goals + supplied references → content plan', 'advisory skill; no render kernel'),
('campaign-analytics', '基于提供数据的投放分析', 'Analyze supplied campaign data', 'local campaign data → analysis / next variant', 'advisory skill; no platform connector'),
]


def archive():
    for source, name, original_parent in [('README.md', 'README.zh.pre-release.md', ROOT),
                                          ('docs/README.md', 'docs-index.pre-release.md', ROOT / 'docs')]:
        dest = REL / 'history' / name
        if dest.exists():
            continue
        text = (ROOT / source).read_text('utf8')
        def link(m):
            target = m.group(2)
            if re.match(r'^[a-zA-Z]+:|^#|^/', target):
                return m.group(0)
            import os
            raw, sep, anchor = target.partition('#')
            if not raw:
                return m.group(0)
            rebased = Path(os.path.relpath(original_parent / raw, dest.parent)).as_posix()
            return m.group(1) + '(' + rebased + (sep + anchor if sep else '') + ')'
        text = re.sub(r'(!?\[[^\]\n]*\])\(([^)\n]+)\)', link, text)
        save(dest.relative_to(ROOT), '> Historical snapshot before the first release / 首版发布前历史快照。\n'
             '> Evidence counts retain their original dates and scope. Historical links may reflect older layouts.\n\n' + text)


def skills():
    # Archive only the three entrypoints with contradictory accumulated routing.
    for suffix in ('agent-editor', 'timeline', 'quality'):
        directory = ROOT / 'skills' / ('video-cut-' + suffix)
        original = directory / 'references/pre-release-routing.md'
        text = (directory / 'SKILL.md').read_text('utf8')
        if not original.exists():
            original.parent.mkdir(exist_ok=True)
            history = text.replace('../../docs/', '../../../docs/')
            original.write_text('> Historical instructions; current release entrypoint takes precedence.\n\n' + history, encoding='utf8')
        front = text.split('---', 2)[1]
        specific = {
            'agent-editor': '''Start with `version`, `capabilities`, `doctor` and `schema show` from the chosen installed runtime.
Convert the user's intent into an explicit edit plan. Create a new owned project, ingest existing local assets
with evidence, compose the timeline, validate, preview, render, then check quality and export a project package.
Use the timeline, rights, quality and model Skills when their specialist contracts apply.
For advisory ad/strategy Skills, turn their outputs into an edit plan; they do not supply an editing engine.''',
            'timeline': '''Use `timeline compose --input EDIT.json` for composition and `timeline edit --input EDIT.json`
for supported range edits. Read the current schema and command help before authoring operations.
Keep integer author ticks (default 90000/s), source ranges, explicit audio tracks, native PTS and nested clocks.
Use advertised keyframe properties for scale/position/rotation/opacity and effects. Preview actual output frames.
Legacy source-handle transitions and explicit Float32 support are distinct capability sets; inspect before use.''',
            'quality': '''Validate the authored project and Rights Ledger before publication. Run `quality check` on the actual
encoded output; use `quality scopes` and `quality golden` when requested. Inspect source/output frames and manifests.
Distinguish automatic decode/pixel/PCM checks, static visual review, continuous playback and human listening.
A successful encode or a passed test count does not establish natural quality or complete CapCut parity.
For Float32 work inspect the declared color signal, renderer protocol and independent reference evidence.''',
        }[suffix]
        body = f'''---{front}---

# Video Cut / {suffix}

Current release: `{TAG}`. Source of truth: [bilingual release manual](../../docs/releases/{TAG}/USAGE.md)
and [Skill catalog](../../docs/releases/{TAG}/SKILLS.md).

{specific}

## Execution boundaries

- Native local execution only. No Docker, WSL, containers, runtime downloads, cloud providers or telemetry.
- Use existing Python/FFmpeg and explicit local model paths; missing dependencies must produce a truthful refusal.
- Output paths are absolute and inside the owned project. Preserve existing outputs and failure evidence.
- Run dry plans where supported; author audio explicitly. Video placement alone does not create an audio track.
- Inspect actual `ok`, `status`, `errors`, exit code and artifact paths. Preserve warnings and conversion losses.
- `--publish` performs local rights gating; it does not upload media.

## Renderer choice

Default render/preview uses the existing FFmpeg graph. Explicit `settings.pixel_pipeline.engine = "float32-native-v1"`
uses the advertised Float32 path for its supported subset. Declare source/working/delivery color signals using
the current schema and [Float32 contracts](../../docs/Agent浮点帧包CLI使用与验收边界_2026-10-22.md).
Do not silently change pipeline or substitute unsupported effects. Native `surface export` is a separate
frame-bundle interchange command. Float transition/runtime experiments beyond released V112 are not this release.

## References

- [First-release cases and real responses](../../docs/releases/{TAG}/CASES.md)
- [Release gates and known limitations](../../docs/releases/{TAG}/RELEASE.md)
- [Complete schema](../../docs/specs/agent-project.schema.json)
- [Historical routing and evidence](references/pre-release-routing.md), only for its dated capability scope.
'''
        save((directory / 'SKILL.md').relative_to(ROOT), body)
    manifest = jread('video-cut-install-manifest.json')
    for entry in manifest['skills']:
        file = ROOT / 'skills' / entry['name'] / 'SKILL.md'
        entry['skill_md_sha256'] = hashlib.sha256(file.read_bytes()).hexdigest()
        entry['file_count'] = sum(f.is_file() for f in file.parent.rglob('*'))
        entry['release'] = TAG
    save('video-cut-install-manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    table = '\n'.join(f'| {i} | [`$video-cut-{s}`](../../../skills/video-cut-{s}/SKILL.md) | {zh}<br>{en} | `{io}` | `{cmd}` |'
                      for i, (s, zh, en, io, cmd) in enumerate(SKILLS, 1))
    save(REL.relative_to(ROOT) / 'SKILLS.md', f'''
# Skills / 技能目录

[中文 README](../../../README.md) · [English README](../../../README.en.md) · [使用逻辑 / Usage](USAGE.md)

17 个入口全部以 `$video-cut-` 开头。Skill 是给 Agent 的任务说明；实际媒体处理由 CLI、FFmpeg 或明确登记的本地模型完成。
All 17 entries use `$video-cut-`. Skills instruct an Agent; media processing runs in the CLI, FFmpeg, or explicitly registered local models.

| # | Skill | 用途 / Purpose | 输入 → 输出 / Input → output | 相关入口 / Related commands |
|---|---|---|---|---|
{table}

## 安装与发现 / Install and discovery

```powershell
Set-Location E:\\dev\\sandbox\\AI广告剪辑
.\\register-video-cut-skills.ps1
# Optional custom discovery location; existing unrelated directories are preserved:
.\\register-video-cut-skills.ps1 -SkillsDirectory E:\\agent-skills
```

脚本从当前仓库 `skills/` 推导目标，创建 Windows 目录联接，并更新本机安装映射。仓库迁移后重新运行；已经指向其他目录的同名项会拒绝覆盖。
The script derives targets from this checkout, creates Windows junctions and updates the local mapping. Run it after relocation. A conflicting existing entry is preserved and refused.
The installed CLI bundle does not itself install an Agent host or register Skills. Download the Skills asset or use the source checkout, then register with your Agent's supported discovery mechanism.

## 调用示例 / Example requests

```text
$video-cut-agent-editor 用本地两张产品图和配乐制作 6 秒竖屏广告；保留可编辑项目、权利证据和输出检查。
$video-cut-timeline Add a reviewed zoom preset to the local clip, preserve source timing, and preview its first and last frames.
$video-cut-quality 核验当前输出与 manifest；分别说明自动检查、目检、连续播放和听审结果。
$video-cut-template-library Apply this local template to the supplied product image and render one editable variant.
```

## 组合逻辑与依赖 / Routing and dependencies

创意/策略 → agent-editor → rights-ledger + local-policy → video-understand → timeline/template → quality → project-ops。
Creative/strategy → agent-editor → rights-ledger + local-policy → understanding → timeline/template → quality → project operations.

`local-models` 只有在任务需要时使用；ASR、OCR、RVM、SAM2、LaMa、VACE、HDemucs、SoulX 等需要各自已有的原生环境、权重和许可证明，不包含在基础安装包。
Optional model adapters require their own existing native environment, weights and license evidence. They are not bundled or downloaded automatically.
Advertising strategy and campaign analysis use supplied information; they do not establish model execution, platform access, attribution accuracy or ad performance.

前 3 个核心入口已按首版重整，完整历史移至各自 `references/pre-release-routing.md`。其余入口保留专项说明，以本版能力清单和契约为准。
The three core entrypoints were condensed for this release; dated instructions remain in their references. Specialist entries retain their contracts. Current capabilities and release boundaries take precedence over older paragraphs.

第三方 Skill 的固定来源、哈希和单独许可证见 [安装清单](../../../video-cut-install-manifest.json)。修改过的本地入口不能视作上游原样版本。
Pinned upstream origins, local hashes and separate licenses are recorded in the installation manifest. Locally edited entries are not pristine upstream versions.
''')


def readmes():
    rows_zh = '\n'.join(f'| {i} | `$video-cut-{s}` | {zh} |' for i, (s, zh, *_rest) in enumerate(SKILLS, 1))
    rows_en = '\n'.join(f'| {i} | `$video-cut-{s}` | {en} |' for i, (s, _zh, en, *_rest) in enumerate(SKILLS, 1))
    install = f'''```powershell
# Existing native CPython 3.13 x64 and ffmpeg/ffprobe on PATH are required.
# Extract the Windows release asset into E:\\tools\\agent-video-kit-{TAG}.
Set-Location E:\\tools\\agent-video-kit-{TAG}
$avkPython = 'C:\\Python313\\python.exe'
# Copy the exact manifest digest from the release's version.json / SHA256SUMS.txt.
$avkManifest = (Get-Content .\\version.json -Raw | ConvertFrom-Json).manifest_sha256
& $avkPython -I -B -X utf8 .\\bundle\\install.py --target E:\\tools\\avk-alpha1 --manifest-sha256 $avkManifest
& $avkPython -I -S -B -X utf8 E:\\tools\\avk-alpha1\\run.py doctor
& $avkPython -I -S -B -X utf8 E:\\tools\\avk-alpha1\\run.py capabilities
```
'''
    pipeline = '''```mermaid
flowchart LR
  A[Agent + video-cut Skills] --> B[CLI / JSON responses]
  B --> C[Agent Project + Rights Ledger]
  C --> D[Validate / plan / preview]
  D --> E[FFmpeg graph or explicit Float32]
  E --> F[Video + manifest + quality report]
  G[Existing local models] --> C
```
'''
    evidence_zh = f'''| 编号 | 核验 | 实际结果 | 证据与边界 |
|---|---|---|---|
| R01 | 基线完整回归 | **2,930 通过，0 跳过** | [原始记录]({BASE}/full-r1.json)；2026-10-23，6991.508 秒；本版沿用同一 331 项冻结输入，非本轮新跑 2,930 项 |
| R02 | 已有 V112 新离线安装专项 | **118 通过，197 个产品资源** | [隔离安装记录]({BASE}/installed-r1/verification.json)；该专项与全量有重叠，不相加 |
| R03 | 本轮发布包重新构建与安装 | 8 个固定 wheel，`-I -S` 启动 | [本轮清单]({EVIDENCE}/release-verification.json)；原生 Windows/CPython 3.13 x64 |
| R04 | 本轮竖屏广告与模板 | 实际输入、输出、GIF、JSON、包导出/导入 | [案例核验]({EVIDENCE}/verification.json)；合成素材，0 新模型推理 |
| R05 | 本地策略拒绝 | 远程来源返回非零退出与结构化错误 | [真实失败响应]({EVIDENCE}/remote-refused.stdout.json)；不是上传功能 |
| R06 | 文档页与响应演示 | 桌面/移动截图、交互检查、响应回放录制 | [页面核验]({EVIDENCE}/browser-verification.json)；本地文档页，不是剪辑 GUI；录制为真实日志回放 |
| R07 | Skill 与链接 | 17 个入口格式核验、发布文档本地链接核验 | [门禁结果]({EVIDENCE}/release-verification.json)；格式验证不等于 Agent 决策质量 |
| R08 | 留存失败 | 首轮案例输出路径错误 | [失败记录](docs/validation/evidence/release-{TAG}-r1/failure.json)；脚本已改绝对项目内路径后重跑 |
'''
    evidence_en = evidence_zh.replace('编号', 'ID').replace('核验 | 实际结果 | 证据与边界', 'Check | Observed result | Evidence and limits')
    zh = f'''# Agent Video Kit

**面向 Agent 的本地视频编辑 CLI。** 用可编辑 JSON 时间线、固定能力契约和真实渲染证据，让 Agent 完成广告剪辑、模板变体、关键帧运镜与视频自动化。

[English](README.en.md) · [下载首版]({URL}/releases/tag/{TAG}) · [文档入口](docs/README.md) · [使用手册](docs/releases/{TAG}/USAGE.md) · [Skill 详情](docs/releases/{TAG}/SKILLS.md) · [完整案例](docs/releases/{TAG}/CASES.md)

**当前发布：`{TAG}`，Windows 本地 CLI 预览版。** 首版范围已收口为“离线安装、结构化编辑、预览/渲染、核验与交付”的闭环。完整剪映功能、素材生态及自然画质/听感等价仍属于后续目标。[发布判定与未关闭需求](docs/releases/{TAG}/RELEASE.md)。

![真实发布案例与 CLI 响应回放]({ASSET}/workflow.gif)

上图是本地案例文档页对真实 CLI 日志的回放。产品本体提供 CLI；文档页用于阅读案例与响应，未提供可视化剪辑 GUI。[MP4 录制]({ASSET}/workflow.mp4) · [桌面截图]({ASSET}/desktop.png) · [移动截图]({ASSET}/mobile.png)。

## 方案与运行逻辑

{pipeline}
核心是 Python CLI + Agent Project schema + FFmpeg，本版包含显式选择的 Float32 原生处理路径。Concat 是早期路线研究对象；当前发行物是本仓库的 Python 实现，并非删除 Concat GUI 后得到的二进制。已复用的 OpenFilm 字幕分段、帧时钟、HTML 动效/模板等模块保留来源与许可证；不依赖 OpenFilm 在线服务。

Agent 通过 Skill 把创意转换成编辑计划，读取 `capabilities` 和 `schema show`，再调用 CLI。项目保存源素材引用、时间线、权利台账、快照与操作记录；输出同时保存 manifest 和质量检查。默认使用 FFmpeg 图，只有工程明确设置 `settings.pixel_pipeline.engine = "float32-native-v1"` 并补全信号、源与预算配置才采用受限 Float32 路径；两条路径不承诺功能对等，也不会将不支持项悄悄降级。

## 本版功能范围

| # | 能力 | 使用入口 | 本版边界 |
|---|---|---|---|
| F01 | 项目、事务、快照、恢复、重链 | `project` / `media relink` | 本地项目；操作与失败留证 |
| F02 | 导入、探测、镜头/静音分析、缩略图/波形 | `media ingest/understand/prepare` | 本地文件；语义理解取决于显式适配器 |
| F03 | 多轨、修剪/拆分、范围编辑、关联编辑、嵌套 | `timeline compose/edit` | 整数 ticks、作者时钟、锁与事务约束 |
| F04 | 关键帧、缩放/平移/旋转、运镜预设与效果 | `effects list` + 编辑 JSON | 按已公布属性；不等于剪映全部预设/特效 |
| F05 | 源句柄转场、变速曲线、倒放、定格 | 时间线声明与契约 | 默认路径支持已实现组合；Float32 转场扩展候选未包含 |
| F06 | 蒙版、合成、色彩、HSL、LUT/1D shaper | 效果 JSON / `lut` / `surface` | Float32 源/工作/交付信号需显式声明；不宣称 HDR/ICC 完备 |
| F07 | 字幕、分段、逐字高亮、HTML 动效/模板 | `subtitle` / `motion` / 时间线 | 部分功能另需已有 Node/Chromium；不自动安装 |
| F08 | 音频提取、混音、总线、闪避、同步 | `audio` / 时间线音轨 / `media multicam` | 视频轨不自动代表音轨；自然听感需另审 |
| F09 | 模板变量、批量、片段组、素材库 | `template` / `fragment` / `library` | 用户提供可用本地素材与模板；无商业素材订阅库 |
| F10 | 模型接口：转写/OCR/跟踪/抠像/修复等 | 本地模型注册与对应命令 | 模型和大型推理环境不随基础包分发；不是开箱全功能 AI |
| F11 | 帧/区间预览、队列、取消、质量与 Scope | `preview` / `queue` / `quality` | 配额不等于峰值 RSS 或实时性能保证 |
| F12 | 项目包、JSON、OTIO、MLT/明文草稿交换 | `convert import/export` | 目标格式支持程度不同；保留 Exact/Approximate/Unsupported/Failed 损失报告 |

精确参数以随包 `capabilities`、`schema show`、`COMMAND --help` 为准。[架构和完整使用逻辑](docs/releases/{TAG}/USAGE.md)。明文草稿适配器只处理已有合法本地 JSON；不运行剪映，不读取私有在线资源，不保证全部字段或编辑效果无损往返。

## 安装

首版验证平台为 **原生 Windows x64 + CPython 3.13**。已存在的 `ffmpeg`、`ffprobe` 必须在 `PATH`。发行包包含应用与 7 个依赖 wheel（含 NumPy、Pillow），安装时不联网、不创建虚拟环境、不修改全局 site-packages。Python、FFmpeg、Node、Chromium、CUDA 和模型权重均不随基础包分发。

{install}
先用发布页的 `SHA256SUMS.txt` 校验 ZIP 和 `version.json`；manifest 哈希用于检测包内容变化，**不是作者数字签名**。本版支持并验证的是指定 ABI；`pyproject` 的 Python 下限不代表其他 Python/操作系统已经验证。

已有开发依赖时，可从源码执行 `./ai-ad-editor.ps1 doctor`。完整离线构建、安装、故障排查和回滚见[使用手册](docs/releases/{TAG}/USAGE.md)。

## 最短使用闭环

```powershell
$avkRun = 'E:\\tools\\avk-alpha1\\run.py'
$avkProject = 'E:\\video-work\\first-ad'
& $avkPython -I -S -B -X utf8 $avkRun project init $avkProject --name 'First ad'
& $avkPython -I -S -B -X utf8 $avkRun media ingest --project $avkProject --input E:\\media\\product.mp4
# Inspect returned data.asset.id, then put that ID in changes.json.
& $avkPython -I -S -B -X utf8 $avkRun timeline compose --project $avkProject --input E:\\video-work\\changes.json
& $avkPython -I -S -B -X utf8 $avkRun validate --project $avkProject
& $avkPython -I -S -B -X utf8 $avkRun preview frame --project $avkProject --frame 0
& $avkPython -I -S -B -X utf8 $avkRun render --project $avkProject --output E:\\video-work\\first-ad\\renders\\ad.mp4
& $avkPython -I -S -B -X utf8 $avkRun quality check --project $avkProject --input E:\\video-work\\first-ad\\renders\\ad.mp4
```

默认导入的权利状态是未核验。商业发布前补全来源、许可和本地证据，再使用 `rights check` 与 `render --publish`；`--publish` 只执行**本地权利门禁**，不会上传或发布到平台。上例中的源文件和编辑 JSON 需自行准备；[完整可复现案例](docs/releases/{TAG}/CASES.md)包含生成脚本、真实 ID、命令和全部响应。

CLI 默认输出 JSON，Agent 应同时检查进程退出码、`ok`、`status`、`errors`、`warnings` 和 `artifacts`。失败不是空成功，`--dry-run` 的计划不是实际渲染；支持幂等的写操作可使用 `--idempotency-key`，不要给所有命令推断相同语义。

## 完整案例与原始媒体

| 案例 | 输入 → 输出 | 真实材料 |
|---|---|---|
| C01 / FIELD 竖屏广告 | 自绘产品卡 + 合成脉冲音 → 6 秒 360×640 MP4 | [原输入]({ASSET}/input.mp4) · [输出]({ASSET}/field.mp4) · [GIF]({ASSET}/field.gif) · [编辑 JSON]({EVIDENCE}/changes.json) · [真实响应]({EVIDENCE}/render.stdout.json) |
| C02 / 模板换款 | 参数化模板 + 第三张产品卡 → 3 秒变体 | [模板]({EVIDENCE}/template.json) · [变量]({EVIDENCE}/variables.json) · [输出]({ASSET}/variant.mp4) · [GIF]({ASSET}/variant.gif) |
| C03 / Float32 色彩链 | 历史 V112 合成源 → 1D LUT/shaper + 3D LUT 输出 | [原输入](docs/assets/float-shaper-20261023-installed-r1/original.mp4) · [实际输出](docs/assets/float-shaper-20261023-installed-r1/edited.mp4) · [对照 GIF](docs/assets/float-shaper-20261023-installed-r1/formal-comparison.gif) · [原始安装核验]({BASE}/installed-r1/verification.json) |
| C04 / 交付与拒绝 | 项目包导出/导入、校验；远程来源拒绝 | [导出响应]({EVIDENCE}/export-package.stdout.json) · [恢复验证]({EVIDENCE}/restored-validate.stdout.json) · [拒绝响应]({EVIDENCE}/remote-refused.stdout.json) |

![真实广告成片 GIF]({ASSET}/field.gif)

素材是本仓库生成的虚构产品图和合成音，不是新增模型推理。C03 为带日期的既有实测，不计作本轮新执行。GIF 不含声音；自动解码、静态目检、连续播放、人工听审分别记录，不能互相替代。[所有案例步骤、权利、哈希与复现](docs/releases/{TAG}/CASES.md)。

## 17 个 Agent Skills

| # | Skill | 作用 |
|---|---|---|
{rows_zh}

```powershell
.\\register-video-cut-skills.ps1
```

脚本会为当前检出创建 Windows 目录联接，默认接入当前用户的 Codex Skills 目录；同名无关目录不会覆盖。Skill 包是任务指导，不包含商业模型、素材订阅或 Agent 宿主。[逐项输入输出、依赖、安装与组合示例](docs/releases/{TAG}/SKILLS.md)。

## 功能核验与发布证据

{evidence_zh}

## 已知限制与后续开发

本版是 alpha，可用于固定环境的本地试用与可复核工作流。完整剪映特效/转场/素材生态、普遍自然素材画质/听感、HDR/ICC、长片峰值内存/实时性能、其他平台和 ABI、第三方草稿全量无损兼容仍未验收。已实现接口、历史成功样例与生产级等价不是同一验收结论。

下一阶段优先补全渲染路径能力一致性、连续播放与自然素材质量、性能/取消/恢复可靠性，再扩展模板和模型覆盖。R113/R114 的 Float32 转场/运行时闭包候选及后续调节实验没有纳入本版。[范围判定、门禁、风险与路线图](docs/releases/{TAG}/RELEASE.md)。

## 文档、复现与许可

- [双语使用手册](docs/releases/{TAG}/USAGE.md)、[Skill 目录](docs/releases/{TAG}/SKILLS.md)、[完整案例](docs/releases/{TAG}/CASES.md)、[发布记录](docs/releases/{TAG}/RELEASE.md)。
- [产品需求与路线基线](docs/产品需求与开发路线基线_2026-10-12.md)、[系统架构](docs/architecture/系统边界与模块契约_v0.1_2026-10-13.md)、[机器可读 schema](docs/specs/agent-project.schema.json)。
- [发布前完整编号核验历史](docs/releases/{TAG}/history/README.zh.pre-release.md)、[历史文档索引](docs/releases/{TAG}/history/docs-index.pre-release.md)、[全部文档](docs/README.md)。旧测试不累计为新增能力。
- 自有代码和文档按 [MIT](LICENSE) 分发；第三方快照、Skill、模型、字体、媒体保留各自许可，见[第三方通知](docs/releases/{TAG}/THIRD_PARTY.md)。权利台账是证据记录与门禁，不是自动法律认定。
- 提交问题时附版本、最小可公开工程、实际命令/错误、manifest 与工具版本。功能更新维护 `main`、中英 README 与证据；原生回归入口为 `scripts/run_frozen_regression.py`，使用说明见手册。
'''
    save('README.md', zh)
    en = f'''# Agent Video Kit

**A local video editing CLI for Agents.** Editable JSON timelines, explicit capability contracts and real render evidence for advertising edits, template variants, keyframes and video automation.

[简体中文](README.md) · [Download]({URL}/releases/tag/{TAG}) · [Documentation](docs/README.md) · [Manual](docs/releases/{TAG}/USAGE.md) · [Skills](docs/releases/{TAG}/SKILLS.md) · [Complete cases](docs/releases/{TAG}/CASES.md)

**Release: `{TAG}` — a native Windows CLI preview.** This milestone closes offline installation, structured editing, previews, rendering, checks and delivery. Full CapCut feature coverage, its asset ecosystem and perceptual equivalence remain future goals. [Release decision and open requirements](docs/releases/{TAG}/RELEASE.md).

![Actual case and CLI response replay]({ASSET}/workflow.gif)

This is the local case documentation page replaying actual CLI logs. The product is a CLI; the page documents cases and responses. [Recording]({ASSET}/workflow.mp4) · [Desktop screenshot]({ASSET}/desktop.png) · [Mobile screenshot]({ASSET}/mobile.png).

## Architecture and operation

{pipeline}
The shipped implementation is a Python CLI, Agent Project schema and FFmpeg, with an explicitly selected native Float32 processing path. Concat informed earlier research; this release is this repository's Python implementation. Reused OpenFilm subtitle segmentation, frame-clock and HTML motion/template modules retain their provenance and licenses. No OpenFilm online service is required.

An Agent uses Skills to turn a brief into an edit plan, reads `capabilities` and `schema show`, then invokes the CLI. Projects retain assets, authored sequences, a Rights Ledger, snapshots and operations. Outputs include manifests and quality reports. The default renderer uses the existing FFmpeg graph. `settings.pixel_pipeline.engine = "float32-native-v1"`, with complete source/signal/budget declarations, explicitly selects its advertised subset; unsupported effects must be refused. The two paths have different coverage.

## Included capabilities

| # | Capability | Entry point | Release boundary |
|---|---|---|---|
| F01 | Projects, transactions, snapshots, recovery, relinking | `project` / `media relink` | Local projects with operation evidence |
| F02 | Ingest, probes, scenes/silence, thumbnails/waveforms | `media ingest/understand/prepare` | Local files; semantic tasks need explicit adapters |
| F03 | Multitrack, trim/split, range and linked edits, nesting | `timeline compose/edit` | Integer author ticks, clocks, locks and transactions |
| F04 | Keyframes, scale/pan/rotation, camera presets, effects | `effects list` + edit JSON | Advertised properties; not CapCut's full preset catalog |
| F05 | Source-handle transitions, speed curves, reverse, freeze | Timeline contracts | Implemented default-render combinations; newer Float32 transition candidates excluded |
| F06 | Masks, composition, color, HSL, LUT/1D shapers | Effects / `lut` / `surface` | Explicit Float32 source/working/delivery signals; no complete HDR/ICC claim |
| F07 | Subtitles, segmentation, word highlighting, HTML motion | `subtitle` / `motion` / timeline | Some commands need existing Node/Chromium |
| F08 | Audio extraction/mixing/buses/ducking, multicam sync | `audio` / audio tracks / `media multicam` | Author audio explicitly; perceptual audio review is separate |
| F09 | Template variables/batches, fragments, asset indexing | `template` / `fragment` / `library` | Existing local assets; no subscription library |
| F10 | Optional ASR/OCR/tracking/matting/repair adapters | Model registration and related commands | Weights and large inference runtimes are not bundled |
| F11 | Frame/range previews, queues, cancellation, scopes | `preview` / `queue` / `quality` | Budgets are not peak-RSS or real-time guarantees |
| F12 | Project packages, JSON, OTIO, MLT/plain draft exchange | `convert import/export` | Format-specific Exact/Approximate/Unsupported/Failed reports |

Use bundled `capabilities`, `schema show` and `COMMAND --help` for the exact supported contract. Plain draft adapters operate on existing authorized local JSON, do not run CapCut, and do not promise lossless compatibility with every proprietary effect. [Detailed manual](docs/releases/{TAG}/USAGE.md).

## Installation

The verified profile is **native Windows x64 with CPython 3.13**. Existing `ffmpeg` and `ffprobe` must be on `PATH`. The asset contains the application and seven pinned dependency wheels, including Pillow and NumPy. Installation is offline, uses no virtual environment and does not modify global site-packages. Python, FFmpeg, Node, Chromium, CUDA and model weights are separate prerequisites.

{install}
Verify the ZIP and `version.json` against `SHA256SUMS.txt` on the release page first. A manifest digest detects changed contents; it is **not an author signature**. Other ABIs and platforms are unverified even where package metadata allows a lower Python version.

With development dependencies already installed, `./ai-ad-editor.ps1 doctor` runs from a source checkout. See the manual for offline builds, dependency troubleshooting, recovery and rollback.

## Minimal workflow

```powershell
$avkRun = 'E:\\tools\\avk-alpha1\\run.py'
$avkProject = 'E:\\video-work\\first-ad'
& $avkPython -I -S -B -X utf8 $avkRun project init $avkProject --name 'First ad'
& $avkPython -I -S -B -X utf8 $avkRun media ingest --project $avkProject --input E:\\media\\product.mp4
# Use the returned data.asset.id in a locally authored changes.json.
& $avkPython -I -S -B -X utf8 $avkRun timeline compose --project $avkProject --input E:\\video-work\\changes.json
& $avkPython -I -S -B -X utf8 $avkRun validate --project $avkProject
& $avkPython -I -S -B -X utf8 $avkRun preview frame --project $avkProject --frame 0
& $avkPython -I -S -B -X utf8 $avkRun render --project $avkProject --output E:\\video-work\\first-ad\\renders\\ad.mp4
& $avkPython -I -S -B -X utf8 $avkRun quality check --project $avkProject --input E:\\video-work\\first-ad\\renders\\ad.mp4
```

Ingested rights default to unverified. Provide local license/provenance evidence before a commercial delivery, then run `rights check` and `render --publish`. **`--publish` is a local rights gate; it does not upload media.** The source and edit JSON in this example are supplied by you. [Reproducible cases](docs/releases/{TAG}/CASES.md) include generated inputs, actual IDs, all commands and complete responses.

Agents must inspect the process exit code plus JSON `ok`, `status`, `errors`, `warnings` and `artifacts`. A dry plan is not a render. Use `--idempotency-key` only for commands implementing it; command-specific semantics remain authoritative.

## Real cases

| Case | Input → output | Complete artifacts |
|---|---|---|
| C01 / FIELD vertical ad | Original fictional-product cards + synthetic pulse → 6 s, 360×640 MP4 | [Input]({ASSET}/input.mp4) · [Output]({ASSET}/field.mp4) · [GIF]({ASSET}/field.gif) · [Edit JSON]({EVIDENCE}/changes.json) · [Response]({EVIDENCE}/render.stdout.json) |
| C02 / Template variant | Parameterized template + replacement card → 3 s variant | [Template]({EVIDENCE}/template.json) · [Variables]({EVIDENCE}/variables.json) · [Output]({ASSET}/variant.mp4) · [GIF]({ASSET}/variant.gif) |
| C03 / Float32 color chain | Dated V112 synthetic source → 1D LUT/shaper and 3D LUT | [Input](docs/assets/float-shaper-20261023-installed-r1/original.mp4) · [Output](docs/assets/float-shaper-20261023-installed-r1/edited.mp4) · [Comparison](docs/assets/float-shaper-20261023-installed-r1/formal-comparison.gif) · [Receipt]({BASE}/installed-r1/verification.json) |
| C04 / Delivery and refusal | Package export/import/validation and a rejected remote reference | [Export]({EVIDENCE}/export-package.stdout.json) · [Restored validation]({EVIDENCE}/restored-validate.stdout.json) · [Refusal]({EVIDENCE}/remote-refused.stdout.json) |

![Actual rendered advertising case]({ASSET}/field.gif)

These new assets are locally generated graphics and synthetic audio, with zero new model inferences. C03 is dated historical evidence. GIFs carry no sound; automated decoding, static review, continuous playback and human listening are reported separately. [Provenance, hashes, inputs and reproduction](docs/releases/{TAG}/CASES.md).

## 17 Agent Skills

| # | Skill | Purpose |
|---|---|---|
{rows_en}

```powershell
.\\register-video-cut-skills.ps1
```

Registration creates Windows junctions from the current checkout to the user's Codex Skills directory and preserves conflicting unrelated entries. Skills provide task guidance; the bundle does not install an Agent host, subscription assets or commercial models. [Inputs, outputs, dependencies and routing](docs/releases/{TAG}/SKILLS.md).

## Verification

| ID | Check | Observed result | Evidence and limits |
|---|---|---|---|
| R01 | Baseline full regression | **2,930 passed; 0 skipped**, 6991.508 s | [2026-10-23 receipt]({BASE}/full-r1.json); this release rechecks identical 331 frozen inputs, rather than claiming a new full run |
| R02 | Previous V112 fresh installation | **118 methods; 197 product resources** | [Receipt]({BASE}/installed-r1/verification.json); overlaps the full suite, not additive |
| R03 | Newly rebuilt and installed release | Eight pinned wheels, isolated `-I -S` launch | [Release gate]({EVIDENCE}/release-verification.json); Windows/CPython 3.13 x64 |
| R04 | New ad and template cases | Real inputs, encoded outputs, GIFs, responses and package round trip | [New case receipt]({EVIDENCE}/verification.json); synthetic media, zero new inference |
| R05 | Local policy refusal | Nonzero exit and structured error for remote provenance | [Actual response]({EVIDENCE}/remote-refused.stdout.json) |
| R06 | Documentation UI and recording | Desktop/mobile captures, interaction checks, log replay | [Browser receipt]({EVIDENCE}/browser-verification.json); documentation UI, not an editor GUI or live terminal recording |
| R07 | Skills and links | All 17 entry formats and release-document local links checked | [Gate]({EVIDENCE}/release-verification.json); format validation is not behavioral quality proof |
| R08 | Preserved failed first case run | Incorrect relative output path in the case driver | [Failure](docs/validation/evidence/release-{TAG}-r1/failure.json); corrected to an absolute in-project path before rerunning |

## Limitations and next milestones

This alpha supports reproducible local workflows in the stated environment. Full CapCut effect/transition/library coverage, broad natural-media picture and audio quality, HDR/ICC, long-form peak memory and interactive performance, other platforms/ABIs and universal lossless draft compatibility remain unaccepted.

Next priorities are renderer capability consistency, natural-media playback and perceptual review, performance/cancellation/recovery, then broader templates and model coverage. R113/R114 Float32 transition/runtime-closure candidates and later adjustment experiments are excluded. [Release scope, gates, risks and roadmap](docs/releases/{TAG}/RELEASE.md).

## Documentation, contributions and licensing

- [Manual](docs/releases/{TAG}/USAGE.md), [Skills](docs/releases/{TAG}/SKILLS.md), [cases](docs/releases/{TAG}/CASES.md), [release notes](docs/releases/{TAG}/RELEASE.md), and [all documentation](docs/README.md). Release-specific guides are bilingual; older research/specifications are primarily Chinese.
- [Product baseline](docs/产品需求与开发路线基线_2026-10-12.md), [system architecture](docs/architecture/系统边界与模块契约_v0.1_2026-10-13.md), and [machine-readable schema](docs/specs/agent-project.schema.json).
- [Complete historical numbered verification log](docs/releases/{TAG}/history/README.zh.pre-release.md) and [historical index](docs/releases/{TAG}/history/docs-index.pre-release.md). Dated counts are retained rather than added together.
- Original code/documentation is [MIT licensed](LICENSE). Vendored projects, Skills, models, fonts and media retain their separate terms. [Third-party notices](docs/releases/{TAG}/THIRD_PARTY.md). The Rights Ledger records evidence and gates work; it does not automatically establish legal clearance.
- Issues should include version, a minimal shareable project, actual command/error, manifests and tool versions. Changes maintain `main`, both READMEs and evidence. See the manual for the native frozen-regression entrypoint.
'''
    save('README.en.md', en)


def guides():
    save(REL.relative_to(ROOT) / 'USAGE.md', f'''
# 使用手册 / User manual

[中文 README](../../../README.md) · [English README](../../../README.en.md) · [Skills](SKILLS.md) · [Cases](CASES.md) · [Release](RELEASE.md)

## 1. 选择运行方式 / Select a runtime

建议使用发布包的固定 `cp313-win_amd64` 离线配置。软件包安装在新目录，不需要 Docker、WSL、容器或虚拟环境。
Use the pinned native Windows/CPython 3.13 x64 release bundle. Install to a new directory; no Docker, WSL, containers or virtual environments.
The release tag is `{TAG}`; CLI/package/schema currently report `0.1.0`. The prerelease tag describes the acceptance stage, not a different schema version.

```powershell
# Source checkout, with existing development dependencies:
Set-Location E:\\dev\\sandbox\\AI广告剪辑
.\\ai-ad-editor.ps1 version
.\\ai-ad-editor.ps1 doctor
.\\ai-ad-editor.ps1 capabilities
.\\ai-ad-editor.ps1 schema show
# Rebuild offline from the existing locked wheelhouse (new output only):
C:\\Python313\\python.exe -E -B -X utf8 product/offline/build.py --output E:\\video-work\\new-bundle --wheelhouse sources/python-runtime/cp313-win_amd64-media
```

Source launch uses the host's installed dependencies. The released `run.py` uses `-I -S` to isolate product dependencies from global site-packages.
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
Failures retain a nonzero exit and error code. [Actual success](../../validation/evidence/release-{TAG}-r2/render.stdout.json) · [Actual refusal](../../validation/evidence/release-{TAG}-r2/remote-refused.stdout.json).
Do not infer exact failure exit numbers for every command from one example.

`--request-id` associates caller requests; `--idempotency-key` is supported by selected writes; `--progress jsonl` requests progress where implemented; `--dry-run` previews supported mutations without substituting for execution. Run command help for the chosen operation.

## 3. 时间线与项目结构 / Timelines and projects

默认作者时基为 90,000 ticks/秒，显示帧率 30/1；源时间、输出时间和原生 PTS 是不同量。编辑 JSON 必须使用真实返回的 asset ID。
Default author timebase is 90,000 ticks/second with a 30/1 display rate. Source time, authored time and native PTS differ. Use actual returned asset IDs.

```json
{{
  "sequence_id": "seq_main",
  "operations": [
    {{"op":"append_clip", "track_id":"track_video_1", "asset_id":"REPLACE_WITH_REAL_ID", "source_in_tick":0, "source_out_tick":270000}},
    {{"op":"append_clip", "track_id":"track_audio_1", "asset_id":"REPLACE_WITH_REAL_ID", "source_in_tick":0, "source_out_tick":270000}}
  ]
}}
```

This illustrative edit is not a ready-made input until its asset IDs and source ranges match a real asset. [Executed edit](../../validation/evidence/release-{TAG}-r2/changes.json).
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
C:\\Python313\\python.exe -E -B -X utf8 scripts/first_release_cases.py --installed E:\\tools\\avk-alpha1 --output E:\\video-work\\release-case --evidence E:\\video-work\\release-evidence --assets E:\\video-work\\release-media
# Inspect available native full-run options before allocating a long regression:
C:\\Python313\\python.exe -E -B -X utf8 scripts/run_frozen_regression.py --help
```

The generator uses existing host Pillow and Segoe UI to create raster art, while each product command runs via the fresh installed `-I -S` launcher. It uses FFmpeg, no models/network/virtualization. Exact commands and native checks are retained.
Full baseline regression is 2,930 methods, 0 skips; optional native tools, pinned external fixtures and sufficient disk are required to reproduce that full environment. Release documentation checks reuse its unchanged frozen inputs and add new installed-case smoke checks; they do not claim a newly rerun full suite.

## 9. 更新与回滚 / Upgrade and rollback

保留旧安装目录、发布 ZIP/摘要和项目快照，在新目录安装新版本，对工程副本核验后切换 Agent 的启动命令。回滚时切回已保留的 `run.py` 和对应工程快照；不跨 schema 盲目降级。
Keep the previous install, release archive/digests and project snapshot. Install upgrades side by side and validate project copies before switching Agent commands. Roll back to the retained launcher and matching snapshot; do not blindly downgrade schemas. This first release has no earlier public release to roll back to.
''')
    save(REL.relative_to(ROOT) / 'CASES.md', f'''
# 完整案例 / Complete cases

[README 中文](../../../README.md) · [English](../../../README.en.md) · [Usage](USAGE.md) · [Skills](SKILLS.md)

本轮真实案例在全新离线安装的 `-I -S` CLI 上运行；媒体均为虚构产品原创图形与合成音，0 次新增模型推理。
The new cases run against a fresh native offline install using `-I -S`. Inputs are original fictional-product graphics and synthetic audio, with zero new model inference.

## C01 / 6 秒 FIELD 竖屏广告 / Six-second vertical ad

目标：保留可编辑结构、显式音轨、商业用途证据，生成可交付短片。Brief: deliver a short fictional desk-light ad with editable structure, explicit audio and reviewed synthetic-asset provenance.

| Stage | Actual artifact |
|---|---|
| Original input | [Card 1](../../assets/release-{TAG}-r2/input/card-1.png), [Card 2](../../assets/release-{TAG}-r2/input/card-2.png), [synthetic pulse](../../assets/release-{TAG}-r2/input/pulse.wav), [input MP4](../../assets/release-{TAG}-r2/input.mp4) |
| Composition | [Actual edit JSON](../../validation/evidence/release-{TAG}-r2/changes.json), [authored project](../../validation/evidence/release-{TAG}-r2/author-project.json) |
| Local gates | [Validate](../../validation/evidence/release-{TAG}-r2/validate.stdout.json), [rights](../../validation/evidence/release-{TAG}-r2/rights-check.stdout.json), [policy](../../validation/evidence/release-{TAG}-r2/policy-audit.stdout.json) |
| Plan / output | [Dry plan](../../validation/evidence/release-{TAG}-r2/render-plan.stdout.json), [actual render response](../../validation/evidence/release-{TAG}-r2/render.stdout.json), [MP4](../../assets/release-{TAG}-r2/field.mp4), [GIF](../../assets/release-{TAG}-r2/field.gif) |
| Checks | [Quality](../../validation/evidence/release-{TAG}-r2/quality.stdout.json), [scopes](../../validation/evidence/release-{TAG}-r2/scopes.stdout.json), [stream/frame probes](../../validation/evidence/release-{TAG}-r2/media-probes.json) |

![Rendered ad](../../assets/release-{TAG}-r2/field.gif)

The input MP4 previews the first source card; the complete original inputs are the individual PNG/WAV files. This case is a deliberate card-cut ad, not a generative-video, keyframe or tracking demonstration. Two cards occupy 0–3 and 3–6 seconds; the synthetic pulse occupies its own 0–6 second audio track. Output is 360×640, 30 fps, 180 frames; exact stream metadata is in the probe receipt.
该案例验证导入、结构化拼接、显式音轨、权利门禁、输出和交付；不把卡片剪切当作 AI 特效或运镜展示。

## C02 / 模板换款 / Parameterized variant

同一基础模板接收真实 `asset_id` 和 `duration_tick`，插入 [第三张原始产品卡](../../assets/release-{TAG}-r2/input/card-3.png)。
The basic template takes an actual asset ID and duration to create an editable three-second variant.
[Template](../../validation/evidence/release-{TAG}-r2/template.json) · [Variables](../../validation/evidence/release-{TAG}-r2/variables.json) · [Apply response](../../validation/evidence/release-{TAG}-r2/template-apply.stdout.json) · [Render response](../../validation/evidence/release-{TAG}-r2/template-render.stdout.json) · [MP4](../../assets/release-{TAG}-r2/variant.mp4).

![Template variant](../../assets/release-{TAG}-r2/variant.gif)

This is one actually rendered template variant, not a claimed large batch benchmark. It is silent by design; its quality check does not require an audio stream.

## C03 / 原生浮点色彩链 / Native Float32 color chain (dated evidence)

既有 V112 安装版本实测：保持作者信号和时钟，明确声明 1D LUT/shaper 与 3D LUT 的顺序。
Dated V112 installed-runtime evidence covers ordered 1D LUT/shaper and 3D LUT evaluation with explicit signal and clock declarations.
[Original](../../assets/float-shaper-20261023-installed-r1/original.mp4) · [Edited](../../assets/float-shaper-20261023-installed-r1/edited.mp4) · [Contact sheet](../../assets/float-shaper-20261023-installed-r1/formal-contact.png) · [Authored project](../../assets/float-shaper-20261023-installed-r1/author-project.json) · [Original receipt](../../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json).

![Actual historical Float32 comparison](../../assets/float-shaper-20261023-installed-r1/formal-comparison.gif)

This case is historical, not a new release-run inference or a general HDR/ICC/perceptual-quality acceptance. Its original inputs, per-case metrics and limitations remain authoritative. A separate 4K single-frame oracle does not establish continuous 4K performance.

## C04 / 可恢复交付与真实拒绝 / Delivery and truthful refusal

实际执行 `convert export --target-format package` → `convert import` → `validate`，保留[导出](../../validation/evidence/release-{TAG}-r2/export-package.stdout.json)、[导入](../../validation/evidence/release-{TAG}-r2/import-package.stdout.json)和[复核](../../validation/evidence/release-{TAG}-r2/restored-validate.stdout.json)响应。
An actual package round trip exports, imports to a new project and validates it on the same native host. The examples asset includes the project package with embedded media. Original absolute license/evidence paths remain in its Rights Ledger: when relocating, point `rights update --license-url ... --evidence ... --reason ...` at the provided reviewed CC0 LICENSE file, then recheck rights. Cross-machine evidence-path portability was not tested.

A local file with `--source-url https://example.invalid/asset.png` is rejected before remote access. [Full error JSON](../../validation/evidence/release-{TAG}-r2/remote-refused.stdout.json) and nonzero exit are retained in the command ledger. This is a policy refusal, not a simulated network failure.
首轮脚本将输出路径误写为工作目录相对路径，失败记录[保留](../../validation/evidence/release-{TAG}-r1/failure.json)；改用项目内绝对路径后整轮重跑。

## 响应内容、截图与录制 / Responses, screenshots and recording

[Every command, exit code and timing](../../validation/evidence/release-{TAG}-r2/commands.json) · [Case verification, SHA-256 and rights](../../validation/evidence/release-{TAG}-r2/verification.json) · [Source generator](../../../scripts/first_release_cases.py) · [CC0 evidence](../../assets/release-{TAG}-r2/LICENSE.txt).

The local [case page](../../demo/index.html) loads complete JSON responses, lets readers switch cases/commands, copy commands, inspect original inputs and play output media. Serve the repository locally to use it:

```powershell
C:\\Python313\\python.exe -E -B -X utf8 -m http.server 8765 --bind 127.0.0.1 --directory E:\\dev\\sandbox\\AI广告剪辑
# Open http://127.0.0.1:8765/docs/demo/index.html ; Ctrl+C stops the server.
```

GitHub renders Markdown and media links; it does not execute this HTML page in the repository file viewer. No public website deployment is implied.

![Desktop documentation page](../../assets/release-{TAG}-r2/desktop.png)

[Mobile capture](../../assets/release-{TAG}-r2/mobile.png) · [response-panel capture](../../assets/release-{TAG}-r2/responses.png) · [MP4 recording](../../assets/release-{TAG}-r2/workflow.mp4) · [GIF recording](../../assets/release-{TAG}-r2/workflow.gif) · [capture checks](../../validation/evidence/release-{TAG}-r2/browser-verification.json).

录制内容是本地文档页对已执行 CLI 日志的逐步回放，**不是实时终端录像**。所有响应来自保留的 stdout，未编造成功返回。媒体可以自动复解码并做静态目检；未完成自然素材连续播放和人工听审，不据此宣称达到剪映观感。
The recording is a documentation replay of executed CLI responses, **not a live terminal capture**. Responses come from retained stdout. Decode checks and static review are distinguished from unperformed continuous natural-media playback and human listening.
''')
    save(REL.relative_to(ROOT) / 'RELEASE.md', f'''
# 首版范围与发布记录 / First-release scope and notes

Release: **`{TAG}`** · Stage: **prerelease / alpha** · Acceptance date: **2026-10-24 (Asia/Taipei)**.
CLI/package/schema report 0.1.0. The prerelease tag describes the acceptance stage.

## 发布判定 / Decision

可以收口并发布第一份本地 Agent CLI 预览版；不能关闭“全面达到剪映功能与自然观感”的长期需求。
The local Agent CLI milestone can close and ship as a preview. Full CapCut feature/perceptual equivalence remains open.
The baseline product commit is `ff23569e24ff0c36c620be1176f6db9dc23045fb`; release documentation, Skills and registration improvements are layered over its unchanged 331 frozen inputs.

| # | Scope | Decision / 判定 |
|---|---|---|
| S01 | Native offline install and structured CLI | Included / 纳入：Windows x64 / CPython 3.13, eight pinned wheels |
| S02 | Editable timeline → render → checks → package | Included / 纳入：new source-generated cases and full real responses |
| S03 | Advertised editing/effect/model interfaces | Included within declared contracts; models remain optional external local dependencies |
| S04 | Bilingual onboarding, 17 Skills and case evidence | Included / 纳入：Chinese/English READMEs and bilingual release guides |
| S05 | Complete CapCut feature/preset/library equivalence | Open / 未收口 |
| S06 | Broad natural-media visual/audio acceptance | Open / 未收口：no universal playback/listening/perceptual claim |
| S07 | Continuous 4K/long-form performance and peak RSS | Open / 未收口 |
| S08 | Other platforms/ABIs, universal draft round trip | Open / 未收口 |
| S09 | R113 transitions, R114 runtime closure, later adjustments | Excluded candidates / 未合入本版 |

This is a development preview, not the production `release` stage defined by the older operations plan. Outstanding natural-quality and distribution gates are not silently waived or relabeled as passed. Optional experimental integrations must be enabled deliberately and retain their own rights/runtime requirements.

## 验证口径 / Verification accounting

- Baseline: 2,930 methods passed, 0 skipped, 6991.508 s, source and external fixtures unchanged. [Raw record](../../validation/evidence/float-shaper-20261023-lab/full-r1.json).
- Historical fresh V112 installation: 118 targeted methods and 197 product resources. It overlaps the full suite; do not add counts.
- This release: new eight-wheel build/install, byte comparison with the frozen product, real isolated CLI cases, complete output decoding/probes, Skills and release-document links, desktop/mobile documentation capture and interaction checks. [Current gate](../../validation/evidence/release-{TAG}-r2/release-verification.json).
- Preserve actual failed first case attempt and any corrective rerun; distinguish documentation/fixture errors from product defects.

## 资产与运行边界 / Distribution boundary

| Asset | Contents | Not included |
|---|---|---|
| `agent-video-kit-{TAG}-cp313-win_amd64.zip` | Offline bundle, fixed wheels, installer, version/provenance, notices, install instructions | Python, FFmpeg, models, GPU drivers, Node/Chromium |
| `agent-video-kit-{TAG}-examples.zip` | Generated original inputs, outputs/GIFs, actual logs, project package and reproducer | Unreviewed third-party media or model weights |
| `agent-video-kit-{TAG}-skills.zip` | 17 prefixed Skills, their resources/licenses and relevant manuals | Agent host, online services or automatically enabled models |
| `SHA256SUMS.txt`, `version.json` | Artifact digests and release metadata | Author signature; no signature is claimed |

## 已知风险与下一阶段 / Risks and next milestones

| # | Open requirement | Next acceptance evidence |
|---|---|---|
| N01 | Renderer coverage differences | Explicit compatibility matrix and real unsupported/supported composition checks |
| N02 | Natural visuals, transitions, masks and color | Authorized varied source set, continuous playback, independent oracles and documented reviewer decisions |
| N03 | Audio quality and sync | Natural speech/music, listening review, phase/pitch and codec-origin coverage |
| N04 | Long-form/4K resource reliability | Measured decode/render latency, peak RSS/VRAM/disk, cancellation and recovery at meaningful durations |
| N05 | Distribution and reproducibility | Additional clean-host evidence, toolchain provenance and versioned upgrade tests |
| N06 | Template/model ecosystem | Redistributable assets with license evidence, reproducible local adapters and quality baselines |
| N07 | Interchange | Real authorized draft corpus with per-feature exact/approximate/unsupported/failure reports |

优先解决质量与运行可靠性，再扩大效果数量；历史通过数不替代新的验收。尚未合入的候选继续保留，不用候选计划测试数冒充已发布结果。
Prioritize quality and runtime reliability before growing the effect catalog. Preserve unmerged candidates, and never present their planned test counts as shipped results.

## 维护与回滚 / Maintenance and rollback

`main` receives validated updates through normal pushes. Tags and existing assets are not overwritten. Maintain Chinese/English READMEs and numbered evidence for every functional update. [Install and rollback instructions](USAGE.md).
Keep the release archive and project snapshot; upgrades install side by side. If a release issue appears, preserve reproduction evidence and publish a subsequent prerelease rather than replacing an existing asset silently.
''')
    save(REL.relative_to(ROOT) / 'THIRD_PARTY.md', '''
# 许可与第三方通知 / Licensing and third-party notices

Original Agent Video Kit code and documentation: [MIT](../../../LICENSE). This grant does not relicense separately identified upstream code, repositories, Skills, models, fonts or media.
自有代码与文档使用 MIT；各第三方内容保留独立许可证，不以根目录许可覆盖第三方条款。

| Component | Preserved evidence / notices | Distribution boundary |
|---|---|---|
| Python dependencies | Offline `bundle/manifest.json`, `requirements.lock`, `licenses/`; original notices in wheels | Eight pinned wheels; no runtime fetch |
| OpenFilm | [MIT](../../../product/src/ai_ad_editor/OPENFILM_LICENSE.txt), [examples notices](../../../product/src/ai_ad_editor/OPENFILM_EXAMPLES_LICENSE.txt) | Identified adapted/preserved modules, not its hosted service |
| pdoom-video adaptation | [Original notice](../../../product/src/ai_ad_editor/PDOOM_VIDEO_LICENSE.txt) | Identified local modules |
| Native HSL kernel | [MIT](../../../product/src/ai_ad_editor/NATIVE_HSL_LICENSE.txt), [source](../../../product/src/ai_ad_editor/native_hsl.c) | Packaged Windows DLL and corresponding source |
| RFC3339 checker adaptation | [BSD notice](../../../product/src/ai_ad_editor/RFC3339_VALIDATOR_LICENSE.txt) | Local schema validation |
| OpenSeeFace / Paddle interfaces | [OpenSeeFace](../../../product/src/ai_ad_editor/OPENSEEFACE_LICENSE.txt), [Paddle](../../../product/src/ai_ad_editor/PADDLE_OCR_LICENSE.txt) and adjacent NOTICE files | Adapter attribution; model weights are not bundled |
| External Skills | [Origin/commit/hash mapping](../../../video-cut-install-manifest.json), per-Skill LICENSE/resources | Modified entries identified as local copies |
| New release examples | [CC0 declaration](../../assets/release-v0.1.0-alpha.1-r2/LICENSE.txt), generator, individual SHA-256 inventory | Fictional generated artwork/audio; no font binary or model weights |
| Older examples / research | Their own LICENSE, Rights Ledger and dated evidence | Historical; not all research assets are included in the release examples ZIP |
| FFmpeg and optional native tools | Existing local installation/build versions recorded by doctor and case checks | Not redistributed in the base release; required features depend on your build |

模型、参考声音、商用字体或外部媒体的权利不由接口存在自动获得；需要使用者提供对应本地证据。
An adapter's existence does not grant rights to model weights, reference voices, commercial fonts or external media. Supply appropriate evidence for your own assets.
''')


def index():
    save('docs/README.md', f'''
# Agent Video Kit 文档 / Documentation

[中文 README](../README.md) · [English README](../README.en.md) · [Release]({URL}/releases/tag/{TAG})

当前入口以 `{TAG}` 为准。首版关闭本地 CLI 试用闭环；完整剪映等价仍未验收。Release-specific onboarding is bilingual; historical research and specifications are mainly Chinese.

| 阅读目标 / Goal | Document |
|---|---|
| 安装、结构、命令、渲染路径、故障与恢复 / Install and operate | [USAGE](releases/{TAG}/USAGE.md) |
| 17 个 Skill 的输入输出和组合 / Skill routing | [SKILLS](releases/{TAG}/SKILLS.md) |
| 原视频、输出、GIF、响应与复现 / Complete examples | [CASES](releases/{TAG}/CASES.md) |
| 范围、验收、风险与下一阶段 / Release scope and gates | [RELEASE](releases/{TAG}/RELEASE.md) |
| 许可与依赖 / Notices | [THIRD_PARTY](releases/{TAG}/THIRD_PARTY.md) |
| 本地案例阅读页 / Local documentation gallery | [Demo page](demo/index.html), serve locally as described in CASES |
| 需求与路径基线 / Product baseline | [产品需求与开发路线基线](产品需求与开发路线基线_2026-10-12.md) |
| 模块边界 / Architecture | [系统边界与模块契约](architecture/系统边界与模块契约_v0.1_2026-10-13.md) |
| Agent Project 合同 / Schema | [JSON schema](specs/agent-project.schema.json) |
| 当前基线完整回归 / Frozen baseline | [2930-method receipt](validation/evidence/float-shaper-20261023-lab/full-r1.json) |
| 本轮发布验证 / New release checks | [Release gate](validation/evidence/release-{TAG}-r2/release-verification.json) |
| 历史编号功能与核验 / Complete historical numbered checks | [Archived README](releases/{TAG}/history/README.zh.pre-release.md) |
| 历史全部文档入口 / Historical document catalog | [Archived index](releases/{TAG}/history/docs-index.pre-release.md) |

专项合同保留在 `specs/`，真实实测和失败记录在 `validation/`，媒体在 `assets/`，第三方来源在 `third-party/`，版本发布文档在 `releases/`。不将历史测试、当轮案例和研究检查累计为一个“完成度”。
Contracts remain in specs; raw successes/failures in validation; media in assets; upstream evidence in third-party; milestone guides in releases. Historical tests, new cases and research checks retain separate scopes.
''')


def main():
    if (ROOT / EVIDENCE / 'publication.json').exists():
        raise SystemExit('First release is already public. Preserve its artifacts and publication records; edit maintained documentation directly.')
    archive()
    # Existing MIT wording already shipped for the project's own native kernel.
    shutil.copyfile(ROOT / 'product/src/ai_ad_editor/NATIVE_HSL_LICENSE.txt', ROOT / 'LICENSE')
    skills()
    readmes()
    guides()
    index()
    print(json.dumps({'status': 'written', 'release': TAG, 'skills': len(SKILLS)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
