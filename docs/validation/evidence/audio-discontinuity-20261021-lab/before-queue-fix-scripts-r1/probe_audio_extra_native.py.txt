"""Compare original native PCM and actual AAC decoding with independent edit-group placement."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab'
ASSETS=ROOT/'docs/assets/audio-discontinuity-20261021-lab'
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.native_audio_clock import acquire
from ai_ad_editor.project import create_project
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from test_audio_discontinuity import original_samples
import numpy as np

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(arguments):
    result=subprocess.run(list(map(str,arguments)),capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf8','replace'))
    return result.stdout

def quantized_control():
    directory=REL/'quantized-original-r1';asset=ASSETS/'quantized-original-r1';manifest=directory/'source-manifest.json'
    if manifest.exists():
        value=json.loads(manifest.read_bytes())
        for key in ('source','native_probe','actual_decoded_PCM'):
            assert sha(value[key]['path'])==value[key]['sha256']
        return value['row'],manifest
    assert not directory.exists() and not asset.exists();directory.mkdir();asset.mkdir()
    source=asset/'aac-quantized-continuous.mkv';original=ASSETS/'extra-original-r1/aac-continuous.m4a'
    command=[ffmpeg_path(),'-v','error','-copyts','-i',original,'-map','0:a:0','-c:a','copy','-avoid_negative_ts','disabled',source]
    run(command);probe=directory/'native-frames.json'
    probe.write_bytes(run([ffprobe_path(),'-v','error','-select_streams','a:0','-show_frames','-show_streams','-show_format',
        '-show_entries','frame=pts,nb_samples,channels:stream=time_base,sample_rate,channels:format=start_time,duration','-of','json',source]))
    pcm=asset/'actual-decoded.f32';run([ffmpeg_path(),'-v','error','-i',source,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le',pcm])
    row={'path':str(source),'sha256':sha(source),'rate':48000,'channels':2,'kind':'AAC-actual-decoded-PCM-and-frame-PTS',
        'authored_packet_gap_samples':0,'authored_packet_overlap_samples':0,
        'native_probe':{'path':str(probe),'sha256':sha(probe)},'actual_decoded_PCM':{'path':str(pcm),'sha256':sha(pcm)}}
    value={'status':'prepared-original-quantized-AAC-control','command':list(map(str,command)),'row':row,
        'source':{'path':str(source),'sha256':sha(source)},'native_probe':row['native_probe'],'actual_decoded_PCM':row['actual_decoded_PCM'],
        'script_sha256':sha(Path(__file__)),'rights':'Original CC0 source; codec priming and final padding kept from actual decode.'}
    manifest.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8');return row,manifest

def expected_PCM(name,row):
    if name=='nonzero-origin-mixed':
        result=np.zeros((19200,2),dtype='<f4');source=original_samples()
        for i in range(20):
            left=i*480+(2400 if i>=5 else 0)-(240 if i>=10 else 0);result[left:left+480]=source[i*480:(i+1)*480]
        return result
    if row['kind']=='lossless-native-PCM':
        value=row['author_placed_native_PCM'];assert sha(value['path'])==value['sha256']
        return np.fromfile(value['path'],dtype='<f4').reshape(-1,row['channels'])
    metadata=json.loads(Path(row['native_probe']['path']).read_bytes());frames=metadata['frames']
    tb=Fraction(metadata['streams'][0]['time_base']);origin=Fraction(metadata['format'].get('start_time','0'))
    decoded=row['actual_decoded_PCM'];assert sha(decoded['path'])==decoded['sha256']
    raw=np.fromfile(decoded['path'],dtype='<f4').reshape(-1,row['channels'])
    assert sum(frame['nb_samples'] for frame in frames)==len(raw)
    # The generator edits packet10 and/or packet20. Within each authored group,
    # place every decoded sample contiguously from that group's actual first PTS.
    # This oracle never uses the implementation's threshold or index/cache rows.
    cuts=[0]+([10] if row.get('authored_packet_gap_samples') else [])+([20] if row.get('authored_packet_overlap_samples') else [])+[len(frames)]
    counts=[sum(frame['nb_samples'] for frame in frames[left:right]) for left,right in zip(cuts,cuts[1:])]
    starts=[round((Fraction(frames[left]['pts'])*tb-origin)*row['rate']) for left in cuts[:-1]]
    result=np.zeros((max(start+count for start,count in zip(starts,counts)),row['channels']),dtype='<f4');cursor=0
    for start,count in zip(starts,counts):
        skip=max(0,-start);result[max(0,start):start+count]=raw[cursor+skip:cursor+count];cursor+=count
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('before','after'),required=True)
    parser.add_argument('--revision',required=True);args=parser.parse_args();out=REL/('extra-native-'+args.phase+'-'+args.revision)
    assert not out.exists();out.mkdir();(out/'executed-probe.py.txt').write_bytes(Path(__file__).read_bytes())
    manifest=REL/'extra-original-r1/source-manifest.json';data=json.loads(manifest.read_bytes());assert data['status']=='passed-extra-original-native-frame-sample-counts'
    extra,quantized=quantized_control();rows=dict(data['cases']);rows['aac-quantized-continuous']=extra
    project=out/'project';create_project(project);initial=frozen()
    record={'status':'running','phase':args.phase,'started_at_utc':datetime.now(timezone.utc).isoformat(),'cases':{},'frozen_before':initial,
        'script_sha256':sha(Path(__file__)),'fixture_manifest_sha256':sha(manifest),'quantized_manifest_sha256':sha(quantized),
        'native_windows':True,'virtualization':False,'network':False,'AAC_preencode_lossless_equality_claimed':False}
    def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save()
    for name,row in rows.items():
        assert sha(row['path'])==row['sha256'];expected=expected_PCM(name,row);raw=out/(name+'.actual.f32');truth=out/(name+'.expected.f32');truth.write_bytes(expected.tobytes())
        try:
            item=acquire(project,Path(row['path']),row['sha256'],persist=True)
            command=[ffmpeg_path(),'-v','error',*item['input_args'],'-map','0:a:0','-vn','-af',
                f"aresample={row['rate']}:osf=flt:first_pts=0,apad=whole_len={len(expected)},atrim=end_sample={len(expected)}",'-c:a','pcm_f32le','-f','f32le',raw]
            run(command);actual=np.fromfile(raw,dtype='<f4').reshape(-1,row['channels'])
            record['cases'][name]={'status':'passed' if actual.shape==expected.shape and actual.tobytes()==expected.tobytes() else 'failed-PCM-equality',
                'command':list(map(str,command)),'clock':item,'expected_shape':list(expected.shape),'actual_shape':list(actual.shape),
                'actual_sha256':sha(raw),'expected_sha256':sha(truth),'maximum_absolute_error':float(np.max(np.abs(actual.astype(float)-expected))) if actual.shape==expected.shape else None}
        except BaseException as exc:record['cases'][name]={'status':'failed-preserved','error':repr(exc)}
        save()
    record.update(frozen_after=frozen(),finished_at_utc=datetime.now(timezone.utc).isoformat());record['source_unchanged']=initial==record['frozen_after']
    record['status']='passed' if record['source_unchanged'] and all(row['status']=='passed' for row in record['cases'].values()) else 'failed-preserved';save()
    print(json.dumps({'status':record['status'],'phase':args.phase,'cases':{name:{k:row[k] for k in ('status','error','maximum_absolute_error') if k in row} for name,row in record['cases'].items()}}))
    return 0 if args.phase=='before' and record['source_unchanged'] else (0 if record['status']=='passed' else 1)

if __name__=='__main__':raise SystemExit(main())
