"""Package already verified native artifacts; do not rebuild product inputs."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
REL = ROOT / 'docs/releases' / TAG
WORK = ROOT / 'product/.runtime/first-release-20261024'
EV = ROOT / 'docs/validation/evidence' / ('release-' + TAG + '-r2')
ARTIFACTS = REL / 'artifacts'


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return 'sha256:' + h.hexdigest()


def make_zip(target, rows):
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=8) as z:
        for source, name in sorted(rows, key=lambda row: row[1]):
            z.write(source, name)


def tree(source, prefix):
    return [(p, prefix + '/' + p.relative_to(source).as_posix()) for p in source.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'}]


def main():
    receipt = json.loads((EV / 'release-verification.json').read_bytes())
    if receipt['status'] != 'passed':
        raise SystemExit('Release verification must pass first')
    if ARTIFACTS.exists():
        raise SystemExit('Existing artifact directory preserved')
    ARTIFACTS.mkdir()
    manifest = json.loads((WORK / 'bundle/manifest.json').read_bytes())
    version = {'release': TAG, 'stage': 'alpha-prerelease', 'cli_version': '0.1.0', 'schema_version': '0.1.0',
               'target': 'cp313-win_amd64', 'runtime_profile': 'media-analysis-v1',
               'created_at_utc': datetime.now(timezone.utc).isoformat(),
               'product_baseline_commit': 'ff23569e24ff0c36c620be1176f6db9dc23045fb',
               'product_frozen_inputs': len(receipt['frozen_inputs']), 'product_resources': 197,
               'manifest_sha256': sha(WORK / 'bundle/manifest.json'), 'wheels': manifest['wheels'],
               'python_included': False, 'ffmpeg_included': False, 'models_included': False,
               'virtualization_required': False, 'runtime_network': 'disabled', 'author_signature': False,
               'historical_full_methods': 2930, 'new_cli_calls': receipt['new_cli_calls'],
               'verification_sha256': sha(EV / 'release-verification.json'), 'full_capcut_parity': False}
    (ARTIFACTS / 'version.json').write_text(json.dumps(version, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    notes = f'''# Agent Video Kit {TAG}

面向 Agent 的原生 Windows 本地视频编辑 CLI 首个 alpha 预览版。首版闭环包含离线安装、结构化时间线、预览/渲染、权利与质量核验、模板、项目包，以及 17 个 `$video-cut-` Skills。

The first native Windows alpha preview of the local video editing CLI for Agents: offline installation, editable timelines, rendering/previews, rights/quality checks, templates, project packages and 17 prefixed Skills.

## 下载 / Downloads

- `cp313-win_amd64.zip`: 8-wheel offline application bundle. Requires existing native CPython 3.13 x64 and ffmpeg/ffprobe on PATH. No Python/FFmpeg/model weights included.
- `examples.zip`: original fictional CC0 media, actual rendered MP4/GIFs, complete CLI responses, project-package round trip and reproducer.
- `skills.zip`: 17 Skills with resources/notices and current manuals. Use the source checkout for historical linked contracts/evidence. No Agent host or models included.
- `version.json` and `SHA256SUMS.txt`: provenance and artifact digests. Digests are not an author signature.

## 验证 / Verification

Unchanged 331 product inputs match the **2,930 passed / 0 skipped** full baseline. Previous targeted fresh installation passed 118 methods / 197 resources (overlapping counts). This release newly rebuilt and installed 8 wheels, verified 197 installed resources, executed **28 isolated CLI calls: 27 successes + 1 expected refusal**, rendered two examples, round-tripped a package and checked all 17 Skill formats. The local documentation page passed 14 interaction checks with desktop/mobile screenshots and a real-response replay recording.

## 安装 / Installation

```powershell
Set-Location E:\\tools\\agent-video-kit-{TAG}
$avkPython = 'C:\\Python313\\python.exe'
$avkManifest = (Get-Content .\\version.json -Raw | ConvertFrom-Json).manifest_sha256
& $avkPython -I -B -X utf8 .\\bundle\\install.py --target E:\\tools\\avk-alpha1 --manifest-sha256 $avkManifest
& $avkPython -I -S -B -X utf8 E:\\tools\\avk-alpha1\\run.py doctor
```

先对照 SHA256SUMS 校验下载内容。Verify downloaded files against SHA256SUMS first.

## 文档 / Documentation

[中文 README](https://github.com/Tonscriptions/agent-video-kit/blob/{TAG}/README.md) · [English README](https://github.com/Tonscriptions/agent-video-kit/blob/{TAG}/README.en.md) · [Manual](https://github.com/Tonscriptions/agent-video-kit/blob/{TAG}/docs/releases/{TAG}/USAGE.md) · [Cases](https://github.com/Tonscriptions/agent-video-kit/blob/{TAG}/docs/releases/{TAG}/CASES.md) · [Skills](https://github.com/Tonscriptions/agent-video-kit/blob/{TAG}/docs/releases/{TAG}/SKILLS.md)

## 边界 / Boundaries

这是本地 CLI 的开发预览版，不宣称已达到完整剪映功能、素材生态或自然画质/听感等价。可选 AI 功能需要已有本地环境、权重和权利证据。截图与录制来自案例文档页；响应录制是实际日志回放，不是实时终端录像。

This preview does not establish full CapCut feature/ecosystem/perceptual equivalence. Optional AI adapters require existing local weights, runtimes and rights evidence. Screenshots/recording show the documentation page; the recording replays actual logs, not a live terminal. Natural-media playback/listening, HDR/ICC, long-form resources, other platforms/ABIs and universal draft compatibility remain open. R113/R114 and later experimental candidates are excluded.

Original code/docs are MIT; third-party components and media retain separate terms. No Docker, WSL or containers are required or used for this release.
'''
    (ARTIFACTS / 'RELEASE-NOTES.md').write_text(notes, encoding='utf8')
    rows = tree(WORK / 'bundle', 'bundle')
    rows += [(ARTIFACTS / 'version.json', 'version.json'), (ARTIFACTS / 'RELEASE-NOTES.md', 'README.md'),
             (ROOT / 'LICENSE', 'LICENSE'), (REL / 'THIRD_PARTY.md', 'THIRD_PARTY.md'),
             (EV / 'release-verification.json', 'verification.json')]
    make_zip(ARTIFACTS / ('agent-video-kit-' + TAG + '-cp313-win_amd64.zip'), rows)
    rows = tree(ROOT / 'docs/assets' / ('release-' + TAG + '-r2'), 'docs/assets/release-' + TAG + '-r2')
    rows += tree(EV, 'docs/validation/evidence/release-' + TAG + '-r2')
    rows += [(WORK / 'cases-r2/field.avk.zip', 'project/field.avk.zip'),
             (ROOT / 'scripts/first_release_cases.py', 'scripts/first_release_cases.py'),
             (REL / 'CASES.md', 'docs/releases/' + TAG + '/CASES.md'),
             (ROOT / 'product/examples/p0-basic/template.json', 'product/examples/p0-basic/template.json'),
             (ROOT / 'LICENSE', 'LICENSE')]
    example_note = WORK / 'EXAMPLES-README.md'
    example_note.write_text('''# Release examples / 发布案例

Actual inputs, rendered outputs and GIFs: docs/assets/release-v0.1.0-alpha.1-r2/.
Commands, complete stdout/stderr and checks: docs/validation/evidence/release-v0.1.0-alpha.1-r2/.
Project package with embedded media: project/field.avk.zip.
Rights Ledger retains original absolute evidence paths. After relocation, use rights update to bind the reviewed provided media/LICENSE.txt equivalent in docs/assets/release-v0.1.0-alpha.1-r2/, then check rights. Cross-machine evidence-path portability was not tested.
Reproducer: scripts/first_release_cases.py --help (existing native installed runtime and host Pillow required).
Source artwork/audio and template are CC0; no models or font binary included.
The archived C03 Float32 example is linked in the full source repository and is not duplicated in this examples ZIP.
See the tagged repository's bilingual README/CASES.md for complete navigation and historical evidence.
''', encoding='utf8')
    rows.append((example_note, 'README.md'))
    make_zip(ARTIFACTS / ('agent-video-kit-' + TAG + '-examples.zip'), rows)
    rows = tree(ROOT / 'skills', 'skills')
    rows += [(ROOT / 'LICENSE', 'LICENSE'), (ROOT / 'video-cut-install-manifest.json', 'video-cut-install-manifest.json'),
             (ROOT / 'register-video-cut-skills.ps1', 'register-video-cut-skills.ps1')]
    rows += [(p, p.relative_to(ROOT).as_posix()) for p in REL.glob('*.md')]
    rows += [(ROOT / 'docs/specs/agent-project.schema.json', 'docs/specs/agent-project.schema.json')]
    make_zip(ARTIFACTS / ('agent-video-kit-' + TAG + '-skills.zip'), rows)
    (ARTIFACTS / 'SHA256SUMS.txt').write_text(''.join(sha(f)[7:] + '  ' + f.name + '\n' for f in sorted(ARTIFACTS.iterdir()) if f.is_file()), encoding='ascii')
    print(json.dumps({'status': 'packaged', 'artifacts': [{'name': f.name, 'bytes': f.stat().st_size, 'sha256': sha(f)} for f in sorted(ARTIFACTS.iterdir())]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
