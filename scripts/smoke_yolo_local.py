"""Opt-in controlled YOLO integration evidence, using explicit existing inputs."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'product/src'))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output-root','python-executable','model-path','image','evidence'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    configure_local_runtime()
    root=Path(args.output_root).resolve()
    if root.exists():
        parser.error('Use a new output root; existing projects are never overwritten')
    for value in (args.python_executable,args.model_path,args.image,args.evidence):
        if not Path(value).is_file():
            parser.error('Every input must be an existing local file')
    root.mkdir(parents=True)
    checks=[]
    def invoke(*argv: str, expected: int=0) -> dict:
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            code=cli_main(list(argv))
        value=json.loads(output.getvalue())
        checks.append({'command':value.get('command'),'exit_code':code,'status':value.get('status')})
        print(json.dumps(checks[-1]),flush=True)
        if code!=expected:
            raise RuntimeError(output.getvalue())
        return value
    from PIL import Image
    photo=Image.open(args.image).convert('RGB').resize((240,240),Image.Resampling.BILINEAR)
    frames=[]
    for index in range(32):
        image=Image.new('RGB',(960,540),(40,45,50))
        if index not in (12,13,14):
            image.paste(photo,(30+5*index,20))
        image.paste(photo,(650-3*index,285))
        frames.append(image.tobytes())
    source=root/'controlled-two-objects.mp4'
    value=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s','960x540','-r','8','-i','pipe:0','-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(source)],input=b''.join(frames),capture_output=True,timeout=120)
    if value.returncode:
        raise RuntimeError(value.stderr.decode('utf-8',errors='replace'))
    del frames
    def project(path: Path):
        invoke('project','init',str(path))
        asset=invoke('media','ingest','--project',str(path),'--input',str(source))['data']['asset']
        registration=['media','adapter','register','--project',str(path),'--adapter-id','yolo_local','--engine','yolov10-onnx-cpu-tracking-v1','--model-path',str(Path(args.model_path).resolve()),'--executable',str(Path(args.python_executable).resolve()),'--evidence',str(Path(args.evidence).resolve())]
        invoke(*registration,'--dry-run')
        record=invoke(*registration)['data']['adapter']
        invoke('media','adapter','inspect','--project',str(path),'--adapter-id','yolo_local')
        plan=path/'cache/video-plan.json'
        atomic_write_json(plan,{'operations':[{'op':'append_clip','track_id':'track_video_1','id':'video','asset_id':asset['id'],'source_in_tick':0,'source_out_tick':360000}]})
        invoke('timeline','compose','--project',str(path),'--input',str(plan))
        return asset,record
    tracking=root/'tracking'
    asset,adapter=project(tracking)
    track=['media','track','--project',str(tracking),'--asset-id',asset['id'],'--adapter-id','yolo_local','--roi','0,0,1,1','--step-frames','1','--all-objects']
    first=invoke(*track)['data']['result']
    repeat=invoke(*track)['data']['result']
    assert first['objects']==repeat['objects'], 'Same CPU inputs/config did not reproduce trajectories'
    objects=sorted(first['objects'],key=lambda obj:obj['frames'][0]['y'])
    assert len(objects)==2 and [len(o['frames']) for o in objects]==[29,32]
    assert [round(f['at_seconds']*8) for f in objects[0]['frames']]==[i for i in range(32) if i not in (12,13,14)]
    errors=[]
    for obj,step in zip(objects,(5,-3)):
        initial=obj['frames'][0]['x']
        errors.append(max(abs(frame['x']-initial-step*round(frame['at_seconds']*8)/960) for frame in obj['frames']))
    assert max(errors)<.02, errors
    selected=objects[0]['object_id']
    plan=tracking/'cache/title-plan.json'
    atomic_write_json(plan,{'operations':[{'op':'add_track','track_id':'titles','kind':'subtitle','order':3},{'op':'append_clip','track_id':'titles','id':'title','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':360000,'subtitle':{'text':'Target','style':{'fontsize':20,'fontcolor':'white','box':True,'boxcolor':'black@0.6'}}}]})
    invoke('timeline','compose','--project',str(tracking),'--input',str(plan))
    binding=['media','track-bind','--project',str(tracking),'--asset-id',asset['id'],'--adapter-id','yolo_local','--object-id',selected,'--roi','0,0,1,1','--step-frames','1','--target-clip-id','title','--target-track-id','titles','--offset-y','-0.18','--apply']
    invoke(*binding,'--dry-run')
    bound=invoke(*binding)
    assert bound['data']['plan']['keyframes'][0]['keyframes'][-1]['at_tick']==348750
    horizontal=tracking/'renders/tracked-label.mp4'
    invoke('render','--project',str(tracking),'--output',str(horizontal),'--profile','custom','--width','640','--height','360')
    invoke('quality','check','--project',str(tracking),'--input',str(horizontal),'--width','640','--height','360')
    # A separate project keeps the binding-coordinate and crop checks independent.
    vertical=root/'reframe'
    vertical_asset,_=project(vertical)
    reframing=['media','reframe','--project',str(vertical),'--asset-id',vertical_asset['id'],'--adapter-id','yolo_local','--object-id',selected,'--roi','0,0,1,1','--step-frames','1','--clip-id','video','--track-id','track_video_1','--target-aspect',str(9/16),'--apply']
    invoke(*reframing,'--dry-run')
    reframed=invoke(*reframing)
    portrait=vertical/'renders/reframed-portrait.mp4'
    invoke('render','--project',str(vertical),'--output',str(portrait),'--profile','custom','--width','360','--height','640')
    invoke('quality','check','--project',str(vertical),'--input',str(portrait),'--width','360','--height','640')
    for path in (tracking,vertical):
        invoke('validate','--project',str(path))
        invoke('policy','audit','--project',str(path))
        invoke('rights','check','--project',str(path),expected=7)
    for file in (horizontal,portrait):
        for at in (.5,3.5):
            output=file.with_name(file.stem+f'-{at}.png')
            r=subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss',str(at),'-i',str(file),'-frames:v','1',str(output)],capture_output=True,timeout=60)
            if r.returncode:raise RuntimeError(r.stderr.decode('utf-8',errors='replace'))
    # Real protobuf with unregistered external data must fail before ORT loads it.
    bad=root/'external-data.onnx'
    program='import onnx,sys\nfrom onnx import helper,TensorProto\nt=TensorProto();t.name="weights";t.data_type=TensorProto.FLOAT;t.dims.append(1);t.data_location=TensorProto.EXTERNAL\ne=t.external_data.add();e.key="location";e.value="../unregistered.bin"\ng=helper.make_graph([],"external",[],[],[t]);m=helper.make_model(g)\nopen(sys.argv[1],"wb").write(m.SerializeToString())\n'
    r=subprocess.run([args.python_executable,'-I','-B','-X','utf8','-c',program,str(bad)],capture_output=True,text=True,timeout=60)
    if r.returncode:raise RuntimeError(r.stderr)
    invoke('media','adapter','register','--project',str(tracking),'--adapter-id','external_fixture','--engine','yolov10-onnx-cpu-tracking-v1','--model-path',str(bad),'--executable',args.python_executable,'--evidence',str(Path(args.evidence).resolve()))
    before=[(tracking/name).read_bytes() for name in ('project.json','rights-ledger.json','models/visual-adapters.json')]
    rejected=invoke('media','track','--project',str(tracking),'--asset-id',asset['id'],'--adapter-id','external_fixture','--roi','0,0,1,1','--all-objects',expected=6)
    assert 'VISION_ONNX_EXTERNAL_DATA_UNSUPPORTED' in json.dumps(rejected)
    assert before==[(tracking/name).read_bytes() for name in ('project.json','rights-ledger.json','models/visual-adapters.json')]
    empty=invoke('media','track','--project',str(tracking),'--asset-id',asset['id'],'--adapter-id','yolo_local','--roi','0,0,0.02,0.02','--all-objects','--end-seconds','0.5',expected=6)
    assert empty['errors'][0]['code']=='TRACK_OBJECT_NOT_FOUND'
    report={'scope':'controlled two-image instances; missing frames are complete image removal, not natural occlusion or broad identity acceptance','checks':checks,'source_sha256':'sha256:'+sha256_file(source),'image_sha256':'sha256:'+sha256_file(Path(args.image)),'adapter':adapter,'tracking':first,'repeated_trajectories_equal':True,'motion_residual_normalized_x':errors,'binding':bound['data']['plan'],'reframe':reframed['data']['plan'],'renders':[{'path':str(p),'sha256':'sha256:'+sha256_file(p)} for p in (horizontal,portrait)],'external_data_rejected':True,'empty_detection_rejected':True,'network':'disabled'}
    atomic_write_json(root/'smoke.json',report)
    print(json.dumps({'output':str(root),'objects':len(objects),'observations':[len(o['frames']) for o in objects],'max_residual_pixels':[v*960 for v in errors]}),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
