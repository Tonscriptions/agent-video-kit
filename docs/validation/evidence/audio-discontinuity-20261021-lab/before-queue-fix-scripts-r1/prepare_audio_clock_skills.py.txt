"""Prepare four unregistered video-cut drafts against seventeen exact published parents."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT.parents[2]
OUT=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab/skills-r1'
NAMES=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
COMMON='''

### Native source audio intervals

Discover `native_audio_source_clock` with `capabilities` before using this path.
The protocol is `native-decoded-audio-interval-clock-v1`. It keeps the original
asset ID, URI, source SHA and authored ranges. Native decoded PTS/sample counts
place hard gaps as silence and let later decoded frames overwrite overlaps.
Continuous sources retain their original input; discontinuous sources use a
hash-bound derived native-rate float PCM cache. Soft async drift compensation
stays disabled. Coarse PTS has per-measurement rounding uncertainty; its already
lost subtick clock jumps cannot be reconstructed. Exact native sample timebases
retain a real one-sample gap.

Apply this source clock before scalar/reverse/curve/nested selection, offline R3
input and multicam envelopes. R3 may use audio EOF silence within verified native
video coverage, and must reject invented handles beyond actual source coverage.
Preserve structured clock/cache errors; do not silently retry with a legacy clock.

Use `cache list --project PROJECT --kind native-audio-clock` and explicit
`cache prune --project PROJECT --kind native-audio-clock`. Inventory is not byte
integrity validation. Registered source assets protect matching cache entries;
do not delete protected files manually or present a cache hit as new inference.
The frame/index/PCM/directory bounds do not prove peak RSS or long-file latency.

See [source clock contract](../../docs/specs/源音频内部时钟与硬缺口缓存_实验_v0.1_2026-10-21.md)
and [actual source/MP4/GIF and failure evidence](../../docs/validation/源音频硬缺口与重叠缓存独立实验_2026-10-21.md).
Synthetic sample equality does not establish natural listening, arbitrary codec
changes, HDR, long-form reliability or full CapCut parity.
'''
SPECIFIC={
    'video-cut-agent-editor':'Require capability/protocol discovery before requesting this cache kind. Keep an explicit source master audio track; source interval normalization does not infer device drift or editorial camera choices.',
    'video-cut-timeline':'Retain source gaps and EOF silence before reversal. Keep parent and leaf author clocks editable; a curve or nested retime must consume the same native source placement.',
    'video-cut-project-ops':'Before pruning, inspect protected_source_reference and protected_reference_keys. Source SHA protection covers assets still registered in the author project. Cancellation must clean only owned staging; preserve corrupt or failed media as evidence.',
    'video-cut-quality':'Separate lossless float master equality from MP4 AAC checks. Compressed inputs compare to actual decoded PCM and native frame counts, including codec skip/padding. Treat amplitude GIFs as audio diagnostics; record static viewing, continuous playback and listening separately.',
}
def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    assert not OUT.exists();OUT.mkdir();(OUT/'executed-generator.py.txt').write_bytes(Path(__file__).read_bytes())
    parents={p.parent.name:p for p in (MAIN/'skills').glob('*/SKILL.md')};assert len(parents)==17 and set(NAMES)<=set(parents)
    commit=subprocess.run(['git','-c','gc.auto=0','-c','maintenance.auto=false','rev-parse','HEAD'],cwd=MAIN,capture_output=True,text=True,check=True).stdout.strip()
    assert commit=='7545d747dffd196434e9591d57d4702850faa94d'
    record={'status':'preparing-unregistered-drafts','started_at_utc':datetime.now(timezone.utc).isoformat(),'published_parent':commit,
        'parents':{name:sha(path) for name,path in sorted(parents.items())},'drafts':{},'registration_changed':False,
        'native_windows':True,'virtualization':False,'network':False,'script_sha256':sha(__file__)}
    for name,path in parents.items():
        backup=OUT/'parent-17'/(name+'.SKILL.md.txt');backup.parent.mkdir(exist_ok=True);backup.write_bytes(path.read_bytes())
    validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py');assert validator.is_file()
    for name in NAMES:
        directory=OUT/'drafts'/name;directory.mkdir(parents=True);path=directory/'SKILL.md'
        path.write_text(parents[name].read_text(encoding='utf8').rstrip()+'\n'+COMMON+'\n'+SPECIFIC[name]+'\n',encoding='utf8',newline='\n')
        command=[sys.executable,'-E','-B','-X','utf8',str(validator),str(directory)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        (directory/'validator.stdout.txt').write_bytes(result.stdout);(directory/'validator.stderr.txt').write_bytes(result.stderr)
        record['drafts'][name]={'path':str(path),'sha256':sha(path),'command':command,'exit_code':result.returncode}
        assert result.returncode==0,(name,result.stdout,result.stderr)
    assert record['parents']=={name:sha(path) for name,path in sorted(parents.items())}
    record.update(status='passed-four-unregistered-draft-metadata-checks',parent_count=17,draft_count=4,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),link_resolution_pending_prospective_publication_tree=True)
    (OUT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':record['status'],'parents':17,'drafts':4,'registration_changed':False}))

if __name__=='__main__':main()
