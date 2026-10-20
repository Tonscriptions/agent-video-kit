"""Bind V79 implementation bytes, actual media, failure history and local references."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
from PIL import Image
from run_frozen_regression import frozen
from sync_html_components_documents import BASE, CONTRACT, DOCUMENTS, FOLLOWUPS, INSTALLED, NATIVE, REPORT, ROOT, SKILLS, SCRIPTS


def read(path): return json.loads(Path(path).read_bytes())
def sha(path): return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate', action='store_true'); args = parser.parse_args(); output = args.output.resolve()
    assert output.is_relative_to(BASE) and not output.exists()
    current = frozen(); assert len(current) == 237
    focus = read(BASE/'targeted-r3.json'); dev = read(BASE/'native-r2/verification.json')
    install = read(BASE/'installed-r1/verification.json'); isolated = read(BASE/'installed-r1/media/verification.json')
    assert focus['terminal_ok'] and focus['methods'] == 28 and focus['skipped'] == 0
    for value in (focus, dev, install, isolated):
        assert value['frozen_equal'] and value['frozen_before'] == value['frozen_after'] == current
    for value in (dev, install, isolated):
        assert value['status'] == 'passed' and all(row['ok'] for row in value['checks'])
    assert len(install['resource_hashes']) == 155 and install['bundle']['wheels'] == 7
    assert dev['decoded_case_hashes'] == isolated['decoded_case_hashes'] and len(dev['decoded_case_hashes']) == 7
    assert dev['source_resource_files'] == isolated['source_resource_files']
    assert dev['source_zip_sha256'] == isolated['source_zip_sha256']
    assert dev['rejected_cli'] == isolated['rejected_cli'] == 3
    assert install['isolated_cli_calls'] == isolated['successful_cli']+isolated['rejected_cli']+3
    for name, digest in install['resource_hashes'].items(): assert sha(ROOT/'product/src/ai_ad_editor'/name) == digest
    for directory, value, script in ((BASE/'native-r2', dev, 'smoke_html_components'),
            (BASE/'installed-r1/media', isolated, 'smoke_html_components'),
            (BASE/'installed-r1', install, 'verify_html_components_install')):
        filename = 'executed-install.py.txt' if script.startswith('verify_') else 'executed-smoke.py.txt'
        assert sha(directory/filename) == value['generator_sha256'] == sha(ROOT/'scripts'/(script+'.py'))
        for call in value['calls']:
            assert call['exit_code'] == call.get('expected_exit_code', 0)
            for stream in ('stdout', 'stderr'):
                path = directory/(call['label']+'.'+stream+'.log')
                if path.exists(): assert sha(path) == call[stream+'_sha256'], path
                else: assert stream == 'stdout' and call['label'].startswith('decode-'), path
        for browser in directory.glob('*-browser.json'):
            cleanup = read(browser)['cleanup']
            assert cleanup['all_children_reaped'] and cleanup['active_after_cleanup'] == [], browser
    for value in (dev, install, isolated):
        assert not any(value[k] for k in ('network', 'virtualization', 'continuous_playback_reviewed',
                                         'audio_reviewed', 'natural_quality_accepted', 'full_capcut_parity'))
        assert value['new_model_inference'] == 0
    failures = []
    for name in ('targeted-r1', 'targeted-r2'):
        value = read(BASE/(name+'.json')); assert value['exit_code'] != 0 and not value['terminal_ok']
        assert value['frozen_equal']; failures.append(name)
        assert sha(BASE/(name+'.log')) == value['log_sha256']
    failed = read(BASE/'native-r1/verification.json')
    assert failed['status'] == 'failed' and failed['frozen_equal']; failures.append('native-r1')
    retained = read(BASE/'native-r1/font-gate-retention.json')
    for row in retained['files']: assert sha(BASE/'native-r1'/row['retained']) == row['sha256']
    failed_skill = read(BASE/'skill-format-r1/verification.json')
    assert failed_skill['status'] == 'retained-validation-failure'
    for row in failed_skill['files']: assert sha(BASE/'skill-format-r1'/row['retained']) == row['sha256']
    failures.append('skill-format-r1')
    validator = Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    skill_formats = []
    for skill in SKILLS:
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(validator), str(ROOT/'skills'/skill)], capture_output=True, timeout=30)
        assert result.returncode == 0, (skill, result.stdout, result.stderr)
        skill_formats.append({'skill': skill, 'exit_code': 0, 'stdout': result.stdout.decode('utf8').strip(), 'skill_md_sha256': sha(ROOT/'skills'/skill/'SKILL.md')})
    static = read(BASE/'static-review-r1.json')
    assert static['review_mode'] == 'static-PNG-only'
    assert not any(static[k] for k in ('continuous_playback_reviewed', 'audio_reviewed', 'natural_quality_accepted', 'full_capcut_parity'))
    for row in static['files']: assert sha(ROOT/row['path']) == row['sha256']
    full = read(BASE/'full-r1.json')
    if not args.candidate:
        assert full['status'] == 'passed' and full['terminal_ok'] and full['methods'] == 1796 and full['skipped'] == 0
        assert full['frozen_equal'] and full['frozen_before'] == full['frozen_after'] == current
        assert full['external_fixtures_equal'] and full['external_fixture_count'] == 8
        assert full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
        skills = read(BASE/'skills-r1.json'); assert skills['skill_count'] == 17
    syntax = []
    for name in [*('scripts/'+s+'.py' for s in SCRIPTS), 'product/src/ai_ad_editor/html_components.py', 'product/tests/test_html_components.py']:
        path = ROOT/name; ast.parse(path.read_text(encoding='utf8')); syntax.append({'path': name, 'sha256': sha(path)})
    links = 0
    for path in [*(ROOT/n for n in DOCUMENTS+FOLLOWUPS), CONTRACT, REPORT, *(ROOT/'skills'/s/'SKILL.md' for s in SKILLS)]:
        text = path.read_text(encoding='utf8')
        if path not in (CONTRACT, REPORT):
            marker = 'V79-COMPONENTS' if path.name == 'SKILL.md' else 'V79-FOLLOWUP' if path.relative_to(ROOT).as_posix() in FOLLOWUPS else 'V79-CURRENT'
            match = re.search(r'<!-- '+marker+r' -->(.*?)<!-- /'+marker+r' -->', text, re.S); assert match, path; text = match[1]
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)', text):
            target = raw.strip('<>').split('#', 1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target): continue
            assert (path.parent/urllib.parse.unquote(target)).resolve().exists(), (path, target); links += 1
    media_files, probes, images = [], [], []
    ffprobe = shutil.which('ffprobe'); assert ffprobe
    for name, receipt in ((NATIVE, dev), (INSTALLED, isolated)):
        public = ROOT/name; manifest = read(public/'files.json')
        actual = {p.relative_to(public).as_posix() for p in public.rglob('*') if p.is_file()}-{'files.json'}
        assert actual == set(manifest)
        for relative, row in manifest.items():
            path = public/relative
            assert path.stat().st_size == row['bytes'] and sha(path) == row['sha256']; media_files.append({'path': path.relative_to(ROOT).as_posix(), **row})
            if path.suffix == '.png':
                with Image.open(path) as image: image.load(); images.append({'path': path.relative_to(ROOT).as_posix(), 'size': list(image.size)})
        for row in receipt['media']:
            path = ROOT/row['path']; assert sha(path) == row['sha256']
            result = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_frames', '-of', 'json', str(path)], capture_output=True, check=True, timeout=60)
            probe = json.loads(result.stdout); frames = [f for f in probe['frames'] if f['media_type'] == 'video']
            assert len(frames) == 20 and not any(s['codec_type'] == 'audio' for s in probe['streams'])
            assert all(abs(float(f.get('best_effort_timestamp_time', f.get('pts_time', -1)))-i/10) < 1e-6 for i, f in enumerate(frames))
            probes.append({'path': row['path'], 'sha256': row['sha256'], 'frames': 20, 'fps': 10, 'seconds': 2, 'audio_streams': 0})
    assert len(probes) == 14
    # Existing MIT modules remain pinned; component implementation does not silently replace them.
    upstream = {p.name: sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('openfilm_*.mjs')}
    assert len(upstream) == 6
    for name, digest in upstream.items():
        baseline = subprocess.run(['git', 'cat-file', 'blob', '9ef95856b8351f5c4fe46bc6f013f2a574be06ae:product/src/ai_ad_editor/'+name], cwd=ROOT, check=True, capture_output=True).stdout
        assert 'sha256:'+hashlib.sha256(baseline).hexdigest() == digest
    record = {'status': 'passed-candidate-audit' if args.candidate else 'passed', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'generator_sha256': sha(__file__), 'source_frozen_equal': current == frozen(), 'frozen_inputs': current,
        'methods': 28 if args.candidate else full['methods'], 'retained_failure_runs': failures,
        'resources': 155, 'syntax_parsed': syntax, 'local_links_checked': links, 'public_files': media_files,
        'skill_frontmatter_results': skill_formats,
        'actual_media_probes': probes, 'png_files': images, 'unchanged_openfilm_modules': upstream,
        'candidate_only': args.candidate, 'natural_quality_accepted': False, 'full_capcut_parity': False}
    assert record['source_frozen_equal']
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps({k: record[k] for k in ('status', 'resources', 'local_links_checked', 'retained_failure_runs')}))


if __name__ == '__main__': main()
