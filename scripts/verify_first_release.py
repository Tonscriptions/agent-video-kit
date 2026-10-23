"""Audit the first-release documents, Skills, native artifacts and frozen inputs."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
WORK = ROOT / 'product/.runtime/first-release-20261024'
EV = ROOT / 'docs/validation/evidence' / ('release-' + TAG + '-r2')
ASSETS = ROOT / 'docs/assets' / ('release-' + TAG + '-r2')


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024**2), b''):
            h.update(b)
    return 'sha256:' + h.hexdigest()


def read(p):
    return json.loads(Path(p).read_bytes())


def save(p, d):
    Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    result = {'status': 'running', 'release': TAG, 'date_utc': datetime.now(timezone.utc).isoformat(),
              'native_windows': sys.platform == 'win32', 'virtualization': False,
              'full_suite_reexecuted_this_release': False, 'full_capcut_parity': False, 'checks': []}
    def check(label, ok, details=None):
        result['checks'].append({'check': label, 'passed': bool(ok), 'details': details})
        if not ok:
            raise RuntimeError(label)
    try:
        baseline = read(ROOT / 'docs/validation/evidence/float-shaper-20261023-lab/full-r1.json')
        mismatch = [k for k, v in baseline['frozen_before'].items() if not (ROOT / k).is_file() or sha(ROOT / k) != v]
        check('331 frozen inputs equal the passed 2930-method baseline', not mismatch and len(baseline['frozen_before']) == 331, mismatch)
        result['frozen_inputs'] = baseline['frozen_before']
        result['historical_baseline'] = {'methods': 2930, 'skipped': 0, 'seconds': 6991.508,
            'receipt': 'docs/validation/evidence/float-shaper-20261023-lab/full-r1.json',
            'receipt_sha256': sha(ROOT / 'docs/validation/evidence/float-shaper-20261023-lab/full-r1.json')}
        check('baseline terminal and fixture verification passed', baseline['terminal_ok'] and baseline['frozen_equal'] and baseline['external_fixtures_equal'] and baseline['verification_scripts_equal'])
        prior = read(ROOT / 'docs/validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json')
        installed = WORK / 'installed/site/ai_ad_editor'
        bad = [k for k, v in prior['resource_hashes'].items() if sha(installed / k) != v]
        check('fresh installed product equals all 197 previously tested resources', not bad and len(prior['resource_hashes']) == 197, bad)
        manifest = read(WORK / 'bundle/manifest.json')
        check('complete eight-wheel media-analysis profile', len(manifest['wheels']) == 8 and manifest['runtime_profile'] == 'media-analysis-v1')
        for row in manifest['files']:
            f = WORK / 'bundle' / row['path']
            check('bundle inventory ' + row['path'], f.stat().st_size == row['bytes'] and sha(f) == row['sha256'])
        result['manifest_sha256'] = sha(WORK / 'bundle/manifest.json')
        result['wheels'] = manifest['wheels']
        # Invoke all existing Skill frontmatter validators; no behavioral-quality claim.
        validator = Path(os.environ.get('USERPROFILE', 'C:/Users/carzy')) / '.codex/skills/.system/skill-creator/scripts/quick_validate.py'
        skill_rows = []
        for directory in sorted((ROOT / 'skills').glob('video-cut-*')):
            p = subprocess.run([sys.executable, '-E', '-B', '-X', 'utf8', str(validator), str(directory)],
                               cwd=ROOT, capture_output=True, timeout=30, creationflags=0x08000000)
            row = {'name': directory.name, 'exit_code': p.returncode,
                   'output': p.stdout.decode('utf8', 'replace').strip(), 'skill_sha256': sha(directory / 'SKILL.md')}
            skill_rows.append(row)
            check('Skill format ' + directory.name, p.returncode == 0, row['output'])
        check('all 17 prefixed Skills validated', len(skill_rows) == 17)
        result['skills'] = skill_rows
        # Actual idempotent registration in the existing discovery directory.
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'register-video-cut-skills.ps1')]
        for n in range(2):
            p = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60, creationflags=0x08000000)
            check('actual Skill registration / repeat ' + str(n + 1), p.returncode == 0, p.stdout.decode('utf8', 'replace').strip())
        mapping = read(ROOT / 'video-cut-install-manifest.json')
        check('all registered Skill targets readable', all(Path(x['registration_directory'], 'SKILL.md').read_bytes() == Path(x['canonical_directory'], 'SKILL.md').read_bytes() for x in mapping['skills']))
        # Refuse an unrelated pre-existing destination without replacing its contents.
        conflict = WORK / 'registration-conflict'
        blocked = conflict / mapping['skills'][0]['name']
        blocked.mkdir(parents=True, exist_ok=True)
        sentinel = blocked / 'keep.txt'
        sentinel.write_text('unrelated content must survive', encoding='utf8')
        before_mapping = sha(ROOT / 'video-cut-install-manifest.json')
        p = subprocess.run(command + ['-SkillsDirectory', str(conflict)], cwd=ROOT, capture_output=True, timeout=60, creationflags=0x08000000)
        check('registration preserves conflicting directories and manifest', p.returncode != 0 and sentinel.read_text('utf8') == 'unrelated content must survive' and before_mapping == sha(ROOT / 'video-cut-install-manifest.json'))
        # Resolve only published onboarding links. History retains original evidence/layout.
        documents = [ROOT / 'README.md', ROOT / 'README.en.md', ROOT / 'docs/README.md']
        documents += list((ROOT / 'docs/releases' / TAG).glob('*.md'))
        documents += [ROOT / 'skills' / ('video-cut-' + s) / 'SKILL.md' for s in ('agent-editor', 'timeline', 'quality')]
        count, bad_links = 0, []
        future_receipt = EV / 'release-verification.json'
        for f in documents:
            text = re.sub(r'```[\s\S]*?```', '', f.read_text('utf8'))
            for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', text):
                target = target.strip('<>')
                if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:|^#', target):
                    continue
                raw = unquote(target.split('#', 1)[0])
                p = (f.parent / raw).resolve()
                count += 1
                if not p.exists() and p != future_receipt:
                    bad_links.append({'file': f.relative_to(ROOT).as_posix(), 'target': target})
        check('current bilingual onboarding and core Skill local links', not bad_links, {'checked': count, 'broken': bad_links})
        case = read(EV / 'verification.json')
        commands = read(EV / 'commands.json')
        check('new installed case execution complete', case['status'] == 'passed' and len(commands) == 28 and all(r['exit_code'] == r['expected_exit_code'] for r in commands))
        check('real refusal retained', sum(r['exit_code'] != 0 for r in commands) == 1)
        browser = read(EV / 'browser-verification.json')
        check('documentation page checks and browser cleanup', browser['status'] == 'passed' and all(browser[k] for k in ('browser_closed', 'contexts_closed', 'server_closed')) and not browser['external_requests'] and not browser['page_errors'])
        # Independently probe and fully decode every published new MP4, including recording.
        media = []
        for f in sorted(ASSETS.glob('*.mp4')):
            p = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(f)], capture_output=True, timeout=60, creationflags=0x08000000)
            check('probe ' + f.name, p.returncode == 0)
            probe = json.loads(p.stdout)
            (EV / (f.stem + '-final-probe.json')).write_bytes(p.stdout)
            p = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(f), '-f', 'null', '-'], capture_output=True, timeout=90, creationflags=0x08000000)
            check('full decode ' + f.name, p.returncode == 0 and not p.stderr, p.stderr.decode('utf8', 'replace'))
            media.append({'file': f.name, 'sha256': sha(f), 'bytes': f.stat().st_size,
                          'duration': probe['format']['duration'],
                          'video': [{k: s.get(k) for k in ('width', 'height', 'avg_frame_rate', 'nb_read_frames')} for s in probe['streams'] if s['codec_type'] == 'video']})
        result['new_media'] = media
        check('ad has exactly 180 frames and correct dimensions', any(r['file'] == 'field.mp4' and r['video'][0]['nb_read_frames'] == '180' and r['video'][0]['width'] == 360 and r['video'][0]['height'] == 640 for r in media))
        check('template has exactly 90 frames', any(r['file'] == 'variant.mp4' and r['video'][0]['nb_read_frames'] == '90' for r in media))
        result['new_cli_calls'] = {'total': 28, 'succeeded': 27, 'expected_refusals': 1}
        result['review'] = {'static_visual': 'original card, actual output frames at 1s and 4s, desktop and mobile documentation screenshots',
                            'continuous_playback': False, 'human_listening': False, 'new_model_inferences': 0}
        result['assets'] = [{'path': f.relative_to(ASSETS).as_posix(), 'bytes': f.stat().st_size, 'sha256': sha(f)}
                            for f in sorted(ASSETS.rglob('*')) if f.is_file()]
        result['status'] = 'passed'
    except BaseException as e:
        result['status'] = 'failed-preserved'
        result['error'] = str(e)
        raise
    finally:
        save(EV / 'release-verification.json', result)
    print(json.dumps({'status': result['status'], 'checks': len(result['checks']), 'links': count,
                      'skills': len(result['skills']), 'product_resources': 197, 'frozen_inputs': 331}, ensure_ascii=False))


if __name__ == '__main__':
    main()
