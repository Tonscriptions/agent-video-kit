"""Validate four unregistered audio-origin deltas against a clean, actually published parent."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/audio-source-origin-20261021-lab'
MARKER='NATIVE-AUDIO-SOURCE-ORIGIN-LAB-20261021'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    output=REL/'skills-draft-r1.json';assert not output.exists()
    publication=MAIN/'product/.runtime/multicam-source-range-lab-20261021/product/.runtime/multicam-source-range-20261021/publication-r1/run.json'
    parent=json.loads(publication.read_bytes());assert parent['status']=='published' and parent['main_clean']
    assert parent['full_methods']==1995 and parent['remote_main']==parent['commit']
    actual=subprocess.check_output(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=MAIN,timeout=60).decode().strip()
    assert actual==parent['commit']
    native=json.loads((REL/'native-r1/verification.json').read_bytes())
    installed=json.loads((REL/'installed-r1/verification.json').read_bytes())
    assert native['status']==installed['status']=='passed'
    roles={
        'video-cut-agent-editor':'When media.source_audio_clock advertises demux-relative-first-audio-pts-v1, retain source-leading silence before selecting, reversing or retiming audio. Keep the master audio track explicit.',
        'video-cut-timeline':'Use one source clock for scalar, reverse, speed-curve, nested and offline R3 source windows. A positive audio PTS relative to the container origin is a real source gap, not an instruction to move the content earlier.',
        'video-cut-quality':'Compare the complete lossless PCM to independent leading silence plus original samples, and compare full lossless RGBA separately. MP4/AAC padding, encoded identity patches and GIFs have distinct checks and do not establish exact encoded PCM/RGBA equality.',
        'video-cut-video-understand':'For multicam 0.4.0, source_time = reference_time + relative_delay_seconds includes the native audio start. The score uses overlap Pearson correlation without the unmatched first-difference boundary; it is not a probability, drift estimate or semantic shot decision.',
    }
    old='Unknown-EOF audio-analysis controls include simulated video state. Nonzero audio stream origin, clock drift, natural multicamera quality, HDR, long-form/RSS, continuous playback and listening remain separate acceptance work.'
    new='Unknown-EOF audio-analysis controls include simulated video state. Native PCM source-leading gaps and nonzero container origins use the separately advertised source_audio_clock contract. Compressed priming/edit lists, clock drift, natural multicamera quality, HDR, long-form/RSS, continuous playback and listening remain separate acceptance work.'
    record={'status':'preparing','registered':False,'new_block_marker':MARKER,'skills':{},'published_snapshot_parent_commit':actual,
        'future_parent_refresh':{'before':old,'after':new,'require_each_actual_V87_parent':True},
        'merge_policy':'Only insert new block and the exact reviewed refresh into actual published V87 parents; do not replace full bodies with these V86 snapshots.'}
    validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
    for name,role in roles.items():
        parent_path=MAIN/'skills'/name/'SKILL.md';body=parent_path.read_text('utf8');assert MARKER not in body
        snapshot=REL/'skill-parent-snapshots-r1'/(name+'.md');snapshot.parent.mkdir(parents=True,exist_ok=True)
        assert not snapshot.exists();snapshot.write_bytes(parent_path.read_bytes())
        block=f'''<!-- {MARKER} -->
{role}
The native PCM acceptance uses demux-relative input timestamps with aresample first_pts=0 before source selection. Async clock-drift correction is disabled. Zero-origin audio and equal nonzero container/audio origins must not gain false silence.
Read the [source audio clock contract](../../docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md) and [actual native/isolated evidence](../../docs/validation/原生音频起点与同步独立实验_2026-10-21.md).
The real two-case sample covers container origins 0/5 seconds and audio starts 1/6 seconds, each a one-second relative gap. Source-normalized audio and offset-applied camera cuts are checked separately. R3 input/output frame and silence controls do not establish listening, pitch or stereo-phase quality.
Compressed-codec priming, negative timestamps/edit lists, internal timestamp discontinuities, device drift, natural recordings, long-form/RSS, continuous playback and listening still need acceptance.
Seven base offline wheels do not include NumPy; isolated evidence uses an explicit readonly RECORD/license-verified copy of existing local NumPy 2.4.2. Do not treat that copy as automatic dependency installation.
This is an unregistered candidate; complete regression and main integration remain pending.
<!-- /{MARKER} -->'''
        at=body.index('\n---',3)+4 if body.startswith('---\n') else body.index('\n')
        folder=ROOT/'skills'/name;folder.mkdir(parents=True);target=folder/'SKILL.md'
        target.write_text(body[:at]+'\n\n'+block+'\n'+body[at:],encoding='utf8',newline='\n')
        command=[sys.executable,'-E','-B','-X','utf8',str(validator),str(folder)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60)
        assert result.returncode==0,result.stdout.decode('utf8','replace')+result.stderr.decode('utf8','replace')
        record['skills'][name]={'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target),
            'parent_sha256':sha(parent_path),'parent_snapshot':snapshot.relative_to(ROOT).as_posix(),
            'new_block':block,'registered':False,'validator_exit_code':result.returncode,
            'validator_stdout':result.stdout.decode('utf8','replace')}
    record.update(status='passed-four-unregistered-drafts',skill_count=4,generator_sha256=sha(__file__))
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':record['status'],'skill_count':4,'registered':False,'snapshot_parent_commit':actual}))


if __name__=='__main__':main()
