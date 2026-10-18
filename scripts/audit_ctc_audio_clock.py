"""Correct a review-clock assumption, preserving the failed 16 kHz PCM gate."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main(args):
    public,evidence=args.public.resolve(),args.evidence.resolve()
    evidence.mkdir(parents=True,exist_ok=False)
    previous_path=ROOT/'docs/validation/evidence/ctc-media-20261018/verification.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    assert previous['status']=='failed' and previous['all_rgb_equal_to_initial'] and previous['highlight_clock_matches'] and previous['frozen_equal']
    for name,row in previous['files'].items():assert sha(public/name).removeprefix('sha256:')==row['sha256'].removeprefix('sha256:'),name
    def call(*values):
        r=subprocess.run(list(map(str,values)),capture_output=True,check=True,timeout=180)
        return r.stdout
    stream=json.loads(call('ffprobe','-v','error','-show_streams','-of','json',public/'aligned-verified.mkv'))
    audio=next(s for s in stream['streams'] if s['codec_type']=='audio')
    assert audio['sample_rate']=='48000' and audio['channels']==1
    reference=public/'reference-48k-mono.wav'
    call('ffmpeg','-v','error','-nostdin','-n','-i',public/'input.wav','-ar','48000','-ac','1','-c:a','pcm_f32le',reference)
    def pcm(path):return call('ffmpeg','-v','error','-nostdin','-i',path,'-map','0:a:0','-f','f32le','-acodec','pcm_f32le','-')
    expected,actual=pcm(reference),pcm(public/'aligned-verified.mkv')
    assert actual==expected and len(actual)==377550*4
    report={'status':'verified','previous_failed_report_sha256':sha(previous_path),
        'previous_direct_16khz_equality_goal_passed':False,
        'review_correction':'Existing renderer mixes at fixed 48 kHz; source is 16 kHz. Compare every encoded mono float sample to a separately resampled original, preserving the failed direct-rate assumption.',
        'source_samples_16k':125850,'encoded_samples_48k':377550,'channels':1,
        'independent_native_resample_reference_equal':True,'pcm_sha256':'sha256:'+hashlib.sha256(actual).hexdigest(),
        'resampler_algorithm_independently_accepted':False,'natural_audio_and_listening_accepted':False,
        'all_236_frame_highlight_clocks_match':True,'video_unchanged_by_picture_audio_mute':True,
        'encoded_frames':236,'gif_frames':previous['gif_frames'],'gif_duration_ms':previous['gif_duration_ms'],
        'static_contact_frames':previous['static_contact_frames'],'static_review':False,'continuous_playback_review':False,
        'reference_file':{'name':reference.name,'bytes':reference.stat().st_size,'sha256':sha(reference)},
        'generator_sha256':sha(Path(__file__))}
    (evidence/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'verified','native_48k_pcm_samples':377550,'all_frame_clocks_match':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--public',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);main(p.parse_args())
