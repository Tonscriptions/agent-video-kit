"""Extract the pinned MIT DOM overrides and four pure template field functions."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'eefd6a8d379289102141359a4718dbab12170526'


def sha(value):
    return 'sha256:' + hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=False)
    archive_path = ROOT/'sources/upstream/openfilm-0.2.0/repo.zip'
    output = ROOT/'product/src/ai_ad_editor'
    with zipfile.ZipFile(archive_path) as archive:
        def read(tail):
            names = [n for n in archive.namelist() if n.endswith('/'+tail)]
            assert len(names) == 1
            return archive.read(names[0])
        overrides = read('packages/openfilm/src/overrides.mjs')
        controls = read('packages/openfilm/studio/ui/src/lib/template-controls.ts')
        roots = {n.split('/')[0] for n in archive.namelist()}
        assert len(roots) == 1
        license_bytes = archive.read(next(iter(roots))+'/LICENSE')
    assert license_bytes == (output/'OPENFILM_LICENSE.txt').read_bytes()
    text = controls.decode('utf-8')
    start = text.index('const COLOR = ')
    end = text.index('/** The clip\'s own value of a custom property')
    fragment = text[start:end]
    replacements = {
        'value: string, isColor: (v: string) => boolean = () => false): VarField': 'value, isColor = () => false)',
        'name: string, value: string): boolean': 'name, value)',
        'field: VarField): string': 'field)',
        'name: string): string': 'name)',
        'num[2]!': 'num[2]', 'quoted[2]!': 'quoted[2]', 'words[0]!': 'words[0]',
    }
    for old, new in replacements.items():
        assert old in fragment, old
        fragment = fragment.replace(old, new)
    assert not re.search(r': (?:VarField|boolean|string)', fragment)
    header = ('// Adapted from OpenFilm '+COMMIT+' template-controls.ts (MIT).\n'
              '// Copyright (c) 2026 OpenFilm contributors. See OPENFILM_LICENSE.txt.\n'
              '// Only TypeScript annotations/assertions are removed; four function bodies retain upstream rules.\n')
    fields = (header+fragment).encode('utf-8')
    (output/'openfilm_template_fields.mjs').write_bytes(fields)
    (output/'openfilm_overrides.mjs').write_bytes(overrides)
    (args.evidence/'template-controls.upstream.txt').write_bytes(controls)
    (args.evidence/'overrides.upstream.txt').write_bytes(overrides)
    (args.evidence/'LICENSE.txt').write_bytes(license_bytes)
    proof = {'commit': COMMIT, 'archive_sha256': sha(archive_path.read_bytes()),
             'license_sha256': sha(license_bytes), 'overrides_original_bytes_equal': True,
             'upstream_template_controls_sha256': sha(controls),
             'adopted': {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in
                         [('openfilm_overrides.mjs', overrides), ('openfilm_template_fields.mjs', fields)]},
             'template_adaptation': 'extract COLOR/NUMBER/QUOTED and fieldOf/isFontVar/valueOf/labelOf; remove TS only'}
    (args.evidence/'verification.json').write_text(json.dumps(proof, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
