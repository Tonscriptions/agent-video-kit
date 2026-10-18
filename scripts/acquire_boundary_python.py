"""Fetch two pinned official wheels into an explicit native research module overlay.

No pip, environment creation, activation, system package changes or runtime download.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main(args):
    output, evidence = args.output.resolve(), args.evidence.resolve()
    assert output.is_relative_to(ROOT / 'product/.runtime')
    assert evidence.is_relative_to(ROOT / 'docs/validation/evidence')
    output.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    rows = []
    for project, version in [('transformers', '4.57.6'), ('huggingface_hub', '0.36.0')]:
        url = f'https://pypi.org/pypi/{project}/{version}/json'
        with urllib.request.urlopen(url, timeout=30) as response:
            raw = response.read(2 * 1024 * 1024)
        (evidence / (project + '.pypi.json')).write_bytes(raw)
        metadata = json.loads(raw)
        candidates = [f for f in metadata['urls'] if f['filename'].endswith('-py3-none-any.whl')]
        assert len(candidates) == 1
        wheel = candidates[0]
        assert wheel['url'].startswith('https://files.pythonhosted.org/') and wheel['size'] < 32 * 1024 * 1024
        with urllib.request.urlopen(wheel['url'], timeout=30) as response:
            body = response.read(wheel['size'] + 1)
        assert len(body) == wheel['size'] and hashlib.sha256(body).hexdigest() == wheel['digests']['sha256']
        path = output / wheel['filename']
        path.write_bytes(body)
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                assert (output / item.filename).resolve().is_relative_to(output)
                assert item.file_size <= 16 * 1024 * 1024
            assert sum(i.file_size for i in archive.infolist()) < 128 * 1024 * 1024
            archive.extractall(output)
        rows.append({'name': project, 'version': version, 'wheel': wheel,
                     'pypi_json_sha256': hashlib.sha256(raw).hexdigest()})
    report = {'status': 'downloaded_extracted_and_hashed', 'native_existing_python_only': True,
        'system_site_packages_modified': False, 'virtual_environment_created': False,
        'packages': rows, 'files': {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(output.rglob('*')) if p.is_file()},
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (evidence / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'packages': len(rows), 'files': len(report['files'])}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    main(parser.parse_args())
