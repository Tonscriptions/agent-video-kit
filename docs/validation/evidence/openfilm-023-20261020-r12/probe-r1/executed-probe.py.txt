"""Observe OpenFilm 0.2.3 cache invalidation and component input boundaries.

The cache-key fragment is copied literally, with only its unused server/worker
imports excluded. No upstream renderer, server, browser or provider is started.
These observations are research, not product or upstream whole-module tests.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from review_openfilm_r12 import ROOT, NEW, archive, sha, write
from run_frozen_regression import frozen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists()
    output.parent.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / 'product/.runtime/openfilm-r12-boundaries' / output.parent.name
    scratch.mkdir(parents=True, exist_ok=False)
    before = frozen()
    record = {'status': 'running', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'commit': NEW, 'script_sha256': sha(Path(__file__).read_bytes()),
              'frozen_before': before, 'network_calls': 0, 'browser_processes': 0,
              'renderer_executed': False, 'upstream_whole_module_test': False,
              'product_test_methods_executed': 0, 'virtualization': False}
    (output.parent / 'executed-probe.py.txt').write_bytes(Path(__file__).read_bytes())
    try:
        files, metadata = archive(NEW)
        record['archive'] = metadata
        prefix = 'packages/openfilm/'
        original = files[prefix + 'studio/server/preview-cache.mjs'].decode('utf8')
        start = original.index('const VERSION = 1;')
        end = original.index('/**\n * The stretches of the project known to play late')
        fragment = original[start:end]
        assert "export const TOOL_DIR = '.film';" in files[prefix + 'studio/server/projects.mjs'].decode()
        assert "export const FILM_FILE = 'film.html';" in files[prefix + 'src/film-doc.mjs'].decode()
        harness = ("// OpenFilm contributors, MIT; original contiguous cache-key fragment follows.\n"
                   "import { createHash } from 'node:crypto';\n"
                   "import { readdirSync, readFileSync, statSync } from 'node:fs';\n"
                   "import { extname, join } from 'node:path';\n"
                   "const FILM_FILE = 'film.html', TOOL_DIR = '.film';\n" + fragment)
        (scratch / 'cache-key-fragment.mjs').write_text(harness, encoding='utf8', newline='\n')
        (output.parent / 'cache-key-fragment.mjs.txt').write_text(harness, encoding='utf8', newline='\n')
        record['cache_fragment'] = {'original_module_sha256': sha(original.encode()),
                                    'original_contiguous_fragment_sha256': sha(fragment.encode()),
                                    'original_lines': [original[:start].count('\n') + 1, original[:end].count('\n')],
                                    'executed_module_sha256': sha(harness.encode())}
        for name in ('component-props.ts', 'film-overrides.ts', 'template-controls.ts'):
            data = files[prefix + 'studio/ui/src/lib/' + name]
            (scratch / name).write_bytes(data)
            (output.parent / (name + '.txt')).write_bytes(data)
        driver = r'''import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { previewKey } from './cache-key-fragment.mjs';
import { propsOf, withPropValue } from './component-props.ts';
const root = join(process.cwd(), 'project');
mkdirSync(root);
writeFileSync(join(root, 'film.html'), '<iframe src="frame.svg"></iframe>');
const path = join(root, 'frame.svg');
const stamp = new Date('2026-10-20T00:00:00Z');
const picture = color => `<svg xmlns="http://www.w3.org/2000/svg"><rect width="64" height="64" fill="${color}"/></svg>`;
const hash = p => createHash('sha256').update(readFileSync(p)).digest('hex');
writeFileSync(path, picture('#f00'));
utimesSync(path, stamp, stamp);
const before = { sha256: hash(path), bytes: statSync(path).size, mtimeMs: statSync(path).mtimeMs, key: previewKey(root, 0, 1, 30, 180) };
writeFileSync(path, picture('#00f'));
utimesSync(path, stamp, stamp);
const after = { sha256: hash(path), bytes: statSync(path).size, mtimeMs: statSync(path).mtimeMs, key: previewKey(root, 0, 1, 30, 180) };
assert.notEqual(before.sha256, after.sha256);
assert.equal(before.bytes, after.bytes);
assert.equal(before.mtimeMs, after.mtimeMs);
assert.equal(before.key, after.key);
assert.notEqual(after.key, previewKey(root, 0, 1, 30, 360));
const imageProp = { name: 'Hero', type: 'image', at: '#hero', kind: 'img' } as const;
const remote = withPropValue(undefined, imageProp, 'https://example.invalid/hero.png');
assert.ok(JSON.stringify(remote).includes('https://example.invalid/hero.png'));
const looseVar = propsOf({ attrs: { 'data-props': JSON.stringify([{ name: 'Color', type: 'var', var: '--' }]) } });
assert.equal(looseVar.length, 1);
const largeIndex = propsOf({ attrs: { 'data-props': JSON.stringify([{ name: 'Title', type: 'text', at: 'h1', n: 1e20 }]) } });
assert.equal(largeIndex.length, 1);
console.log(JSON.stringify({ cache: { before, after, changed_content_same_key: true },
  component: { remote_url_formatted_without_fetch: remote, short_variable_name_accepted: looseVar,
  large_match_index_accepted: largeIndex }, assertions: 8, rendered_frames: 0, network_calls: 0 }));
'''
        (scratch / 'probe.mts').write_text(driver, encoding='utf8', newline='\n')
        (output.parent / 'probe.mts.txt').write_text(driver, encoding='utf8', newline='\n')
        node = shutil.which('node')
        assert node
        env = dict(os.environ)
        env.pop('NODE_OPTIONS', None)
        env.pop('NODE_PATH', None)
        env.update(TMP=str(scratch), TEMP=str(scratch))
        argv = [node, '--experimental-strip-types', '--disallow-code-generation-from-strings', str(scratch / 'probe.mts')]
        result = subprocess.run(argv, cwd=scratch, env=env, capture_output=True, timeout=30)
        for stream in ('stdout', 'stderr'):
            (output.parent / (stream + '.log')).write_bytes(getattr(result, stream))
        record['execution'] = {'argv': argv, 'exit_code': result.returncode,
                               'stdout_sha256': sha(result.stdout), 'stderr_sha256': sha(result.stderr)}
        assert result.returncode == 0
        observations = json.loads(result.stdout)
        assert observations['assertions'] == 8 and observations['cache']['changed_content_same_key']
        record.update(observations=observations, status='passed_research_observations')
    except BaseException as exc:
        record.update(status='failed', error={'type': type(exc).__name__, 'message': str(exc)})
        raise
    finally:
        after = frozen()
        record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), frozen_after=after, frozen_equal=before == after)
        write(output, record)
    assert record['frozen_equal']
    print(json.dumps({'status': record['status'], 'observations': 4,
                      'assertions': observations['assertions'], 'stale_key_reproduced': True,
                      'frozen_equal': True}))


if __name__ == '__main__':
    main()
