"""Review previews from actual encoded timeline output; no browser or renderer."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
from smoke_fragments import save,sha


def run(public):
    import numpy as np
    from PIL import Image
    record=json.loads((public/'verification.json').read_text(encoding='utf-8'))
    video=public/'S03-timeline.mkv'
    assert sha(video)==record['files'][video.name]['sha256']
    raw=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(video),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
    actual=np.frombuffer(raw,np.uint8).reshape(24,360,640,3)
    background=np.asarray(Image.open(public/'source.png').convert('RGB'))
    compared=np.concatenate([np.repeat(background[None],24,axis=0),actual],axis=2)
    output=public/'native-comparison.mp4'
    assert not output.exists(),'choose fresh public output directory'
    subprocess.run([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','rgb24','-video_size','1280x360',
        '-framerate','12','-i','pipe:0','-an','-c:v','libx264rgb','-preset','ultrafast','-crf','0',str(output)],
        input=compared.tobytes(),check=True)
    images=[Image.fromarray(frame).resize((960,270),Image.Resampling.LANCZOS) for frame in compared[::2]]
    images[0].save(public/'native-comparison.gif',save_all=True,append_images=images[1:],duration=[170,160,170]*4,loop=0,disposal=2)
    for i in (0,12,23):Image.fromarray(compared[i]).save(public/f'native-comparison-{i:02}.png')
    paths=[output,public/'native-comparison.gif',*(public/f'native-comparison-{i:02}.png' for i in (0,12,23))]
    save(public/'native-review-artifacts.json',{'status':'generated','generator':'scripts/create_html_motion_review_artifacts.py',
        'generator_sha256':sha(Path(__file__)),'source_video_sha256':sha(video),'left':'original procedural PNG',
        'right':'actual decoded native product timeline output; no independent recomposition',
        'video':{'width':1280,'height':360,'fps':12,'frames':24,'seconds':2,'audio':False},
        'gif':{'width':960,'height':270,'frames':12,'milliseconds':2000},
        'files':{p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in paths}})
    print(json.dumps({'files':len(paths),'video_frames':24,'gif_frames':12}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--public',type=Path,required=True);args=parser.parse_args();run(args.public.resolve())
