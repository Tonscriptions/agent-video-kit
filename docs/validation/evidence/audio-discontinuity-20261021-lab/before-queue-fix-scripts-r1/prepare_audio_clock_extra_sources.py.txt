"""Generate original rate/origin and AAC decoded-frame/skip/discontinuity fixtures."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from ai_ad_editor.runtime import configure_local_runtime
configure_local_runtime()
from ai_ad_editor.media import ffmpeg_path,ffprobe_path
from test_audio_discontinuity import original_samples
import numpy as np

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--revision',required=True);args=parser.parse_args()
    evidence=ROOT/'docs/validation/evidence/audio-discontinuity-20261021-lab'/('extra-original-'+args.revision)
    assets=ROOT/'docs/assets/audio-discontinuity-20261021-lab'/('extra-original-'+args.revision)
    assert not evidence.exists() and not assets.exists();evidence.mkdir();assets.mkdir()
    record={'status':'running','started_at_utc':datetime.now(timezone.utc).isoformat(),'commands':[],
        'script_sha256':sha(Path(__file__)),'cases':{},'native_windows':True,'virtualization':False,'network':False,
        'rights':'Original deterministic PCM and flat video, CC0-1.0; AAC samples compared to actual decoding, never pre-encode PCM.'}
    def save():(evidence/'source-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def run(arguments):
        command=list(map(str,arguments));result=subprocess.run(command,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        record['commands'].append({'command':command,'exit_code':result.returncode,'stderr':result.stderr.decode('utf8','replace')[-8000:],
            'stdout_bytes':len(result.stdout),'stdout_sha256':'sha256:'+hashlib.sha256(result.stdout).hexdigest()});save()
        if result.returncode:raise RuntimeError(record['commands'][-1])
        return result.stdout
    save();(evidence/'executed-generator.py.txt').write_bytes(Path(__file__).read_bytes())
    try:
        originals=ROOT/'docs/assets/audio-discontinuity-20261021-lab/original-r1'
        mixed=originals/'mixed.nut'
        origin=assets/'nonzero-origin-mixed.nut'
        run([ffmpeg_path(),'-v','error','-copyts','-i',mixed,'-map','0','-c','copy','-output_ts_offset','5',origin])
        record['cases']['nonzero-origin-mixed']={'path':str(origin),'rate':48000,'channels':2,'known_container_origin_seconds':'5',
            'kind':'lossless-native-PCM','gap_samples':2400,'overlap_samples':240}
        for name,rate,channels,packet,gap,overlap,leading in [
            ('delayed-mixed',48000,2,480,2400,240,2400),('low-rate-mixed',8000,1,80,400,40,0),
            ('fractional-rate-mixed',44100,2,441,2205,220,0)]:
            count=20*packet;t=np.arange(count,dtype=np.float64)/rate;step=np.arange(count)//packet
            left=.17+.013*step+.08*np.sin(2*np.pi*433*t)
            pcm=left[:,None] if channels==1 else np.stack((left,-.19-.009*step+.07*np.sin(2*np.pi*739*t)),axis=1)
            pcm=pcm.astype('<f4');raw=assets/(name+'.source.f32');raw.write_bytes(pcm.tobytes());target=assets/(name+'.nut')
            expression=f'N+{leading}+if(gte(N,{5*packet}),{gap},0)-if(gte(N,{10*packet}),{overlap},0)'
            run([ffmpeg_path(),'-v','error','-f','lavfi','-i','color=c=0x203040:size=32x18:rate=25:duration=0.4',
                '-f','f32le','-ar',rate,'-ac',channels,'-i',raw,'-af',f"asetnsamples=n={packet}:p=0,asetpts='{expression}'",
                '-map','0:v:0','-map','1:a:0','-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',target])
            placed=np.zeros((round(.4*rate),channels),dtype='<f4')
            for i in range(20):
                position=i*packet+leading+(gap if i>=5 else 0)-(overlap if i>=10 else 0)
                placed[position:position+packet]=pcm[i*packet:(i+1)*packet]
            oracle=assets/(name+'.author-placed-native.f32');oracle.write_bytes(placed.tobytes())
            record['cases'][name]={'path':str(target),'rate':rate,'channels':channels,'packet_samples':packet,'gap_samples':gap,
                'overlap_samples':overlap,'leading_samples':leading,'kind':'lossless-native-PCM',
                'original_PCM':{'path':str(raw),'sha256':sha(raw)},'author_placed_native_PCM':{'path':str(oracle),'sha256':sha(oracle)}}
        pcm=assets/'aac-encoding-input.f32';pcm.write_bytes(np.tile(original_samples(),(5,1)).tobytes())
        continuous=assets/'aac-continuous.m4a'
        run([ffmpeg_path(),'-v','error','-f','f32le','-ar','48000','-ac','2','-i',pcm,'-c:a','aac','-b:a','192k',continuous])
        record['cases']['aac-continuous']={'path':str(continuous),'rate':48000,'channels':2,'kind':'AAC-actual-decoded-PCM-and-frame-PTS'}
        for name,gap,overlap in [('aac-gap',4800,0),('aac-overlap',0,240),('aac-gap-overlap',4800,240)]:
            expression=f'if(gte(N,10),{gap}/48000/TB,0)-if(gte(N,20),{overlap}/48000/TB,0)'
            target=assets/(name+'.mkv')
            run([ffmpeg_path(),'-v','error','-copyts','-i',continuous,'-map','0:a:0','-c:a','copy',
                '-bsf:a',f"setts=pts='PTS+{expression}':dts='DTS+{expression}'",'-avoid_negative_ts','disabled',target])
            record['cases'][name]={'path':str(target),'rate':48000,'channels':2,'kind':'AAC-actual-decoded-PCM-and-frame-PTS',
                'authored_packet_gap_samples':gap,'authored_packet_overlap_samples':overlap,'container_quantization_explicit':True}
        for name,row in record['cases'].items():
            target=Path(row['path']);raw=run([ffprobe_path(),'-v','error','-select_streams','a:0','-show_frames','-show_streams','-show_format',
                '-show_entries','frame=pts,nb_samples,sample_rate,channels,channel_layout:stream=time_base,sample_rate,channels,channel_layout:format=start_time,duration',
                '-of','json',target]);metadata=json.loads(raw);probe_file=evidence/(name+'.native-frames.json');probe_file.write_bytes(raw)
            decoded=assets/(name+'.actual-decoded.f32');run([ffmpeg_path(),'-v','error','-i',target,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le',decoded])
            expected=sum(int(frame['nb_samples']) for frame in metadata['frames']);actual=decoded.stat().st_size//(row['channels']*4)
            if expected!=actual:raise RuntimeError((name,'decoded frame/sample count differs',expected,actual))
            row.update(sha256=sha(target),bytes=target.stat().st_size,native_probe={'path':str(probe_file),'sha256':sha(probe_file)},
                actual_decoded_PCM={'path':str(decoded),'sha256':sha(decoded),'samples_per_channel':actual},
                native_frames=len(metadata['frames']),time_base=metadata['streams'][0]['time_base'],format=metadata['format']);save()
        record.update(status='passed-extra-original-native-frame-sample-counts',finished_at_utc=datetime.now(timezone.utc).isoformat());save()
        print(json.dumps({'status':record['status'],'sources':len(record['cases']),'commands':len(record['commands'])}));return 0
    except BaseException as exc:
        record.update(status='failed-preserved',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat());save();raise

if __name__=='__main__':raise SystemExit(main())
