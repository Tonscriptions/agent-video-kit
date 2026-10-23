"""Check the final post-publication links and actual installation records.

Keeps the already published release-verification.json and artifact set unchanged.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
TAG = 'v0.1.0-alpha.1'
EV = ROOT / 'docs/validation/evidence' / ('release-' + TAG + '-r2')
ARTIFACTS = ROOT / 'docs/releases' / TAG / 'artifacts'


def main():
    files = [ROOT / 'README.md', ROOT / 'README.en.md', ROOT / 'docs/README.md']
    files += list((ROOT / 'docs/releases' / TAG).glob('*.md'))
    bad, count = [], 0
    for f in files:
        text = re.sub(r'```[\s\S]*?```', '', f.read_text('utf8'))
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', text):
            target = target.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:|^#', target):
                continue
            count += 1
            if not (f.parent / unquote(target.split('#', 1)[0])).exists():
                bad.append({'file': f.relative_to(ROOT).as_posix(), 'target': target})
    publication = json.loads((EV / 'publication.json').read_bytes())
    installation = json.loads((EV / 'installation-receipt.json').read_bytes())
    version = json.loads((ARTIFACTS / 'version.json').read_bytes())
    verification = json.loads((EV / 'release-verification.json').read_bytes())
    mismatches = [name for name, digest in verification['frozen_inputs'].items()
                  if not (ROOT / name).is_file() or 'sha256:' + hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    checks = {
        '331_product_inputs_still_equal_published_baseline': len(verification['frozen_inputs']) == 331 and not mismatches,
        'current_local_document_links': not bad,
        'public_release_and_workflow_succeeded': publication['status'] == 'published-and-download-verified' and publication['workflow_conclusion'] == 'success',
        'six_actual_downloads_match': len(publication['assets']) == 6 and all(x['download_verified'] for x in publication['assets']),
        'native_installation_uses_released_manifest': installation['manifest_sha256'] == version['manifest_sha256'],
        'eight_installed_distributions': len(installation['audit']['modules']) == 8,
        'actual_isolated_numpy_audit': installation['audit']['numpy_native']['dot'] == 285.0 and installation['audit']['numpy_native']['solve'] == [2.0, 3.0],
        'published_verification_receipt_preserved': 'sha256:' + hashlib.sha256((EV / 'release-verification.json').read_bytes()).hexdigest() == version['verification_sha256'],
    }
    for row in publication['assets']:
        checks['published_asset_preserved_' + row['name']] = 'sha256:' + hashlib.sha256((ARTIFACTS / row['name']).read_bytes()).hexdigest() == row['sha256']
    result = {'status': 'passed' if all(checks.values()) else 'failed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'current_document_links': count, 'broken_links': bad, 'checks': checks,
              'published_assets_replaced': False, 'product_input_mismatches': mismatches,
              'product_code_changed_since_release': bool(mismatches)}
    (EV / 'publication-docs-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, ensure_ascii=False))
    if result['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
