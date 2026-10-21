"""Create four unregistered, validated deltas against actual published V89 skills."""
import json
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import sha
ROOT=Path(__file__).resolve().parents[1];MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/multicam-affine-clock-20261021-lab'
OUT=REL/'skill-drafts-r1';assert not OUT.exists();OUT.mkdir()
validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
names=('video-cut-agent-editor','video-cut-timeline','video-cut-quality','video-cut-video-understand')
record={'status':'running','registered':False,'skill_count':4,'skills':{},'canonical_skill_count':len(list((MAIN/'skills').glob('*/SKILL.md')))}
assert record['canonical_skill_count']==17
replacements={
    'The 50 Hz envelope estimates one offset; it does not estimate clock drift or choose semantic shots.':
        'The default offset mode estimates one constant delay. Explicit advertised affine mode estimates a bounded clock rate; neither mode chooses semantic shots.',
    'device drift, natural recordings':'nonlinear/discontinuous device drift, natural recordings',
    'clock drift, natural multicamera quality':'nonlinear/discontinuous clock drift, natural multicamera quality',
}
block='''
<!-- MULTICAM-AFFINE-CLOCK-LAB-20261021 -->
When capabilities advertise media.multicam_clock / multicam-affine-clock-v1, use media multicam --clock-model affine explicitly for bounded device clock-rate calibration. Default offset stays constant-delay mode.
Inspect source = offset_seconds + source_per_reference * reference, matched anchors, ambiguity, residuals, observed interval and asset SHA bindings. Do not fabricate a successful model or fall back silently after rejected calibration.
Use --dry-run first when applying a switch plan. Keep source rates and inverse coverage; trim leaves real gaps, stretch changes sync and warns. Observed-interval extrapolation requires --allow-clock-extrapolation and retains its warning. Author master audio explicitly.
The analysis prefix is bounded to 600 seconds, with 3–31 anchors, 4–60 second windows and at most 20000 ppm (default 5000). It does not implement nonlinear/discontinuous drift or acoustic-room quality acceptance.
Read the [affine clock contract](../../docs/specs/多机位仿射时钟与漂移校准_实验_v0.1_2026-10-21.md) and [independent native/isolated report](../../docs/validation/多机位仿射时钟与浮点音频独立实验_2026-10-21.md).
Scalar render source normalization is floating point before author selection; do not introduce intermediate s16 quantization. Preserve native leading gaps and keep async resampling drift correction disabled.
The 590-second synthetic event interval and three short output windows are not complete long-form, natural/HDR/RSS, listening or full CapCut parity acceptance. Native frame-coverage identity is not identical event counters at differing camera sample phases.
<!-- /MULTICAM-AFFINE-CLOCK-LAB-20261021 -->
'''
for name in names:
    source=MAIN/'skills'/name/'SKILL.md';text=source.read_text('utf8');applied=[]
    for old,new in replacements.items():
        count=text.count(old);assert count<=1
        if count:text=text.replace(old,new);applied.append({'before':old,'after':new,'count':count})
    marker='\n---\n';end=text.index(marker,3)+len(marker)
    text=text[:end]+block+text[end:]
    folder=OUT/name;folder.mkdir();draft=folder/'SKILL.md';draft.write_text(text,encoding='utf8',newline='\n')
    parent=folder/'published-parent.SKILL.md.txt';parent.write_bytes(source.read_bytes())
    result=subprocess.run([sys.executable,'-E','-B','-X','utf8',validator,folder],cwd=ROOT,capture_output=True,timeout=60)
    record['skills'][name]={'path':draft.relative_to(ROOT).as_posix(),'sha256':sha(draft),'parent_snapshot':parent.relative_to(ROOT).as_posix(),
        'parent_sha256':sha(source),'registered':False,'precise_replacements':applied,'validator_exit_code':result.returncode,
        'validator_stdout':result.stdout.decode('utf8','replace'),'validator_stderr':result.stderr.decode('utf8','replace')}
    assert result.returncode==0,record['skills'][name]
record.update(status='passed-four-unregistered-drafts',generator_sha256=sha(Path(__file__)))
(REL/'skills-draft-r1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({k:record[k] for k in ('status','skill_count','registered')}))
