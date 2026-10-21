"""Create and verify six original native packet-clock fixtures once for before/after reuse."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from test_audio_discontinuity import fixture_sources
from run_frozen_regression import sha,frozen
OUT=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab/original-r1'
ASSETS=ROOT/'docs/assets/audio-discontinuity-20261021-lab/original-r1'
assert not OUT.exists() and not ASSETS.exists();OUT.mkdir(parents=True)
before=frozen();assert len(before)==264
data=fixture_sources(ASSETS)
assert frozen()==before
data.update(status='passed-original-native-packet-clocks',generator_sha256=sha(Path(__file__)),
    fixture_generator_sha256=sha(ROOT/'product/tests/test_audio_discontinuity.py'),frozen_before=before,frozen_after=frozen(),
    native_windows=True,virtualization=False,network=False)
(OUT/'source-manifest.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
(OUT/'executed-generator.py.txt').write_bytes(Path(__file__).read_bytes())
(OUT/'executed-test-fixture.py.txt').write_bytes((ROOT/'product/tests/test_audio_discontinuity.py').read_bytes())
print(json.dumps({'status':data['status'],'sources':len(data['cases']),'source_PCM_samples':9600}))
