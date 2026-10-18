"""Audit a fixed upstream snapshot and a CSS parser fix without installing it.

Only audit_openfilm_refresh.py performs the explicit research acquisition. This
script executes selected dependency-free tests and synthetic XML/data examples.
It never launches OpenFilm, a browser, a provider, Docker or WSL.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_openfilm_refresh import contents, digest
from run_frozen_regression import frozen


XML_SAMPLE = r'''
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';
const [source, out] = process.argv.slice(2);
const base = join(source, 'packages/openfilm/studio/server');
const { fcpxmlDocument } = await import(pathToFileURL(join(base, 'fcpxml.mjs')));
const { nleRate } = await import(pathToFileURL(join(base, 'nle.mjs')));
const { filmSubtitleVtt } = await import(pathToFileURL(join(base, 'film-subtitle.mjs')));
for (const fps of [25, 29.97]) {
  const plan = {
    name: 'AVK research <local> & 中文', rate: nleRate(fps), width: 1920, height: 1080, durationFrames: 90,
    files: [
      { id: 'video', name: 'local & shot.mov', path: join(out, 'local & shot.mov'), durationFrames: 300,
        video: { w: 1920, h: 1080, alpha: false, still: false, fps: 25 } },
      { id: 'audio', name: 'local.wav', path: join(out, 'local.wav'), durationFrames: 300,
        audio: { channels: 2, sampleRate: 48000 } },
    ],
    video: [
      { enabled: true, clips: [
        { name: 'A', fileId: 'video', start: 0, end: 30, in: 60, out: 90, enabled: true },
        { name: 'B', fileId: 'video', start: 30, end: 90, in: 15, out: 75, enabled: true },
      ] },
      { enabled: true, clips: [
        { name: 'overlay', fileId: 'video', start: 45, end: 75, in: 5, out: 35, enabled: true },
      ] },
    ],
    audio: [{ enabled: true, sourceTrack: 3, clips: [
      { name: 'voice', fileId: 'audio', start: 15, end: 60, in: 30, out: 75, enabled: true, gain: .5 },
    ] }],
  };
  writeFileSync(join(out, `sample-${fps}.json`), JSON.stringify(plan, null, 2) + '\n');
  writeFileSync(join(out, `sample-${fps}.fcpxml`), fcpxmlDocument(plan, {
    cues: [{ startMs: 1100, durMs: 700, text: 'Hello & <world>\n第二行', speaker: 'Ann' }],
  }));
}
writeFileSync(join(out, 'escaped.vtt'), filmSubtitleVtt([
  { startMs: 0, durMs: 1000, text: 'A & <B> --> C', speaker: 'Ann & <X>' },
]));
process.stdout.write(JSON.stringify({ timelines: 2, media_created: false, frames_rendered: 0 }) + '\n');
'''


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = args.source.resolve(strict=True)
    refresh = json.loads(args.refresh.read_bytes())
    before = {p.relative_to(source).as_posix(): digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
    assert before == refresh['head_hashes']
    fixed = contents((ROOT / 'sources/upstream/openfilm-0.2.0/repo.zip').read_bytes())
    current = contents(Path(refresh['source_archive']).read_bytes())
    assert current['LICENSE'] == fixed['LICENSE'] == (ROOT / 'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    product_before = frozen()
    baseline = json.loads((ROOT / 'docs/validation/evidence/magnetic-reorder-tests-20261018/full-1.json').read_bytes())
    assert baseline['terminal_ok'] and baseline['methods'] == 1223
    changes = sorted(p for p in product_before if baseline['frozen_after'].get(p) != product_before[p])
    assert changes == ['product/src/ai_ad_editor/html_template_dom.mjs', 'product/tests/test_html_url_parser.py'], changes
    node = shutil.which('node')
    assert node
    temporary = ROOT / 'product/.runtime/openfilm-recheck-native-temp-20261018-r54'
    temporary.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary))
    runs = []

    def execute(name, command, *, timeout=60, expect_timeout=False):
        start = time.monotonic()
        expired = False
        try:
            result = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=timeout)
            stdout, stderr, code = result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired as exc:
            expired = True
            stdout, stderr, code = exc.stdout or b'', exc.stderr or b'', None
        (output / (name + '.stdout.log')).write_bytes(stdout)
        (output / (name + '.stderr.log')).write_bytes(stderr)
        row = {'id': name, 'command': command, 'exit_code': code, 'deadline_seconds': timeout,
               'timed_out': expired, 'seconds': time.monotonic() - start,
               'stdout_sha256': digest(stdout), 'stderr_sha256': digest(stderr)}
        runs.append(row)
        write(output / (name + '.json'), row)
        assert expired == expect_timeout and (expired or code == 0), row
        return stdout.decode('utf-8', 'replace')

    tests = [
        'studio/server/fcpxml.test.mjs', 'studio/server/film-subtitle.test.mjs',
        'studio/server/subtitle-segments.test.mjs', 'src/overrides.test.mjs',
        'studio/ui/src/lib/template-controls.test.ts',
    ]
    text = execute('upstream-selected', [node, '--experimental-strip-types', '--test', '--test-concurrency=1',
                    '--test-timeout=10000', *[str(source / 'packages/openfilm' / p) for p in tests]])
    counts = {key: int(re.findall(r'^# ' + key + r' (\d+)\s*$', text, re.M)[-1])
              for key in ['tests', 'pass', 'fail', 'skipped', 'cancelled']}
    assert counts['fail'] == counts['cancelled'] == 0 and counts['skipped'] == 1
    # Run the exact same watchdog/valid-URL probes against fixed old and current bridge bytes.
    spec = importlib.util.spec_from_file_location('recheck_url_test', ROOT / 'product/tests/test_html_url_parser.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = subprocess.run(['git', 'show', '7c2fbe153966a4f020e6bfa719a6911867909562:product/src/ai_ad_editor/html_template_dom.mjs'],
                         cwd=ROOT, capture_output=True, check=True).stdout
    assert digest(old) == baseline['frozen_after']['product/src/ai_ad_editor/html_template_dom.mjs']
    old_path = output / 'baseline-html_template_dom.mjs'
    old_path.write_bytes(old)
    for revision, bridge in [('baseline', old_path), ('current', module.BRIDGE)]:
        for mode in ['valid', 'double', 'single']:
            execute(revision + '-' + mode, [node, '--input-type=module', '-e', module.PROBE, str(bridge), mode],
                    timeout=5, expect_timeout=revision == 'baseline' and mode != 'valid')
    worker = output / 'xml-samples.mjs'
    worker.write_text(XML_SAMPLE, encoding='utf-8', newline='\n')
    execute('xml-data', [node, str(worker), str(source), str(output)])
    xml_checks = []
    for label, step in [('25', Fraction(1, 25)), ('29.97', Fraction(1001, 30000))]:
        tree = ET.parse(output / f'sample-{label}.fcpxml')
        root = tree.getroot()
        assert root.attrib['version'] == '1.10'
        sequence = root.find('./library/event/project/sequence')
        assert Fraction(sequence.attrib['duration'].removesuffix('s')) == 90 * step
        spine = sequence.find('spine')
        assert [p.attrib['name'] for p in spine] == ['A', 'B']
        assert [Fraction(p.attrib['offset'].removesuffix('s')) for p in spine] == [0, 30 * step]
        assert [Fraction(p.attrib['start'].removesuffix('s')) for p in spine] == [60 * step, 15 * step]
        # Overlay's source clock is relative to B's original in-point: 15 + (45 - 30) = 30.
        overlay = next(p for p in root.iter('asset-clip') if p.attrib['name'] == 'overlay')
        assert Fraction(overlay.attrib['offset'].removesuffix('s')) == 30 * step
        voice = next(p for p in root.iter('asset-clip') if p.attrib['name'] == 'voice')
        assert voice.attrib['audioRole'] == 'OpenFilm A1'
        assert Fraction(voice.attrib['offset'].removesuffix('s')) == 75 * step
        title = root.find('.//title/text/text-style')
        assert title.text == 'Ann：Hello & <world>\n第二行'
        xml_checks.append({'sample': label, 'exact_step': str(step), 'well_formed': True,
                           'timeline_and_source_clocks_checked': True, 'target_editor_imported': False})
    vtt = (output / 'escaped.vtt').read_text(encoding='utf-8')
    assert 'A &amp; &lt;B&gt; --&gt; C' in vtt and '<v Ann &amp; &lt;X&gt;>' in vtt
    adopted_paths = ['studio/server/subtitle-segments.mjs', 'src/overrides.mjs',
                     'studio/ui/src/lib/timeline-edit.ts', 'studio/ui/src/lib/transitions.ts',
                     'studio/server/saved.mjs', 'studio/ui/src/lib/saved-insert.ts', 'src/render.mjs']
    same = {p: current['packages/openfilm/' + p] == fixed['packages/openfilm/' + p] for p in adopted_paths}
    assert all(same.values())
    clock = re.search(rb'^export const FILM_CLOCK = .*;$', current['packages/openfilm/src/host.mjs'], re.M).group(0)
    assert clock in (ROOT / 'product/src/ai_ad_editor/openfilm_frame_clock.mjs').read_bytes()
    after = {p.relative_to(source).as_posix(): digest(p.read_bytes()) for p in source.rglob('*') if p.is_file()}
    assert before == after and product_before == frozen()
    record = {'status': 'passed_scoped_source_and_parser_review', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
              'head': refresh['head'], 'version': refresh['version'], 'stars': refresh['stars'], 'forks': refresh['forks'],
              'source_archive_sha256': refresh['source_archive_sha256'], 'upstream_files': len(before),
              'unchanged_adopted_or_related_files': same, 'original_frame_clock_unchanged': True, 'mit_unchanged': True,
              'source_before': before, 'source_after': after, 'product_before': product_before, 'product_after': frozen(),
              'product_changes_vs_v53': changes, 'upstream_counts': counts, 'upstream_selected_paths': tests,
              'runs': runs, 'xml_samples': xml_checks, 'synthetic_media_paths_only': True,
              'final_cut_dtd_validated': False, 'target_editor_imported': False, 'product_full_regression_rerun': False,
              'historical_product_full_methods': 1223, 'historical_product_full_receipt': digest((ROOT / 'docs/validation/evidence/magnetic-reorder-tests-20261018/full-1.json').read_bytes()),
              'new_model_calls': 0, 'encoded_video_frames': 0, 'browser_tabs_opened': 0, 'providers_executed': False,
              'dependencies_installed': 0, 'virtualization': False, 'measured_cost_savings_percent': None,
              'goal_complete': False, 'generator_sha256': digest(Path(__file__).read_bytes())}
    write(output / 'verification.json', record)
    print(json.dumps({k: record[k] for k in ['status', 'head', 'upstream_files', 'upstream_counts', 'product_changes_vs_v53']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--refresh', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args())
