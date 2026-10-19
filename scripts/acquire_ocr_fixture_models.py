"""Explicit development acquisition; the product never downloads OCR models."""
from __future__ import annotations
import argparse, hashlib, json, urllib.request, zipfile
from pathlib import Path

URL = 'https://files.pythonhosted.org/packages/af/74/4ff55e4f27878e46122f740cfe340a27731eb4762da58d1e82e31b738004/rapidocr_onnxruntime-1.3.25-py3-none-any.whl'
EXPECTED = '3d8e5416f5bf4ab6566009dfdf24175ff80be937f633578c93befb1b526ff587'


def run(target: Path):
    target.mkdir(parents=True, exist_ok=False)
    request = urllib.request.Request(URL, headers={'User-Agent': 'agent-video-kit-development-acquisition'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(16 * 1024 * 1024)
        assert response.read(1) == b''
    assert len(raw) == 14910442 and hashlib.sha256(raw).hexdigest() == EXPECTED
    wheel = target / 'rapidocr_onnxruntime-1.3.25-py3-none-any.whl'
    wheel.write_bytes(raw)
    rows = []
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            relative = Path(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            if name.endswith('/'):
                continue
            destination = target / 'extracted' / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            payload = archive.read(name)
            destination.write_bytes(payload)
            rows.append({'path': destination.relative_to(target).as_posix(), 'bytes': len(payload),
                         'sha256': 'sha256:' + hashlib.sha256(payload).hexdigest()})
    receipt = {'purpose': 'explicit_development_acquisition_not_runtime', 'url': URL,
               'wheel_sha256': 'sha256:' + EXPECTED, 'bytes': len(raw), 'installed': False, 'files': rows}
    (target / 'acquisition.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'acquired_not_installed', 'files': len(rows), 'target': str(target)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--target', type=Path, required=True)
    run(parser.parse_args().target.resolve())
