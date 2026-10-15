"""Combine an existing native YOLO project with crop/transform canvas binding."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'product/src'))
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json,sha256_file


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-project',required=True)
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--adapter-id',default='yolo_local')
    parser.add_argument('--object-id',required=True)
    args=parser.parse_args()
    configure_local_runtime()
    source=Path(args.source_project).resolve();root=Path(args.output_root).resolve()
    if not (source/'project.json').is_file() or root.exists():
        parser.error('Supply an existing local source project and a new output root')
    root.mkdir(parents=True)
    checks=[]
    def invoke(*argv,expected=0):
        output=io.StringIO()
        with contextlib.redirect_stdout(output): code=cli_main(list(argv))
        value=json.loads(output.getvalue())
        checks.append({'command':value['command'],'status':value['status'],'exit_code':code})
        print(json.dumps(checks[-1]),flush=True)
        if code != expected: raise RuntimeError(output.getvalue())
        return value
    package=root/'input.aevpkg.zip'
    invoke('convert','export','--project',str(source),'--target-format','package','--output',str(package))
    project=root/'project'
    invoke('convert','import','--input',str(package),'--output',str(project))
    payload=json.loads((project/'project.json').read_text(encoding='utf-8'))
    videos=[(t,c) for t in payload['sequences'][0]['tracks'] if t['kind']=='video' for c in t['clips']]
    if len(videos)!=1: raise RuntimeError('Use a one-video controlled source project')
    track,clip=videos[0];asset_id=clip['asset_id'];duration=clip['duration_tick']
    # This is an isolated fixture setup, before any rendering. The subsequent
    # edits, model inference, binding and deliverables use the public CLI.
    payload['settings']['canvas'].update(width=360,height=640)
    payload['settings']['timebase']['display_fps']={'num':8,'den':1}
    atomic_write_json(project/'project.json',payload)
    keys=list(clip.get('keyframes',[]))
    keys += [{'property':p,'keyframes':[{'at_tick':0,'value':a,'interpolation':'linear'},{'at_tick':duration,'value':b,'interpolation':'linear'}]} for p,a,b in [('transform.scale',.82,.95),('transform.rotation',-8,12)]]
    changes=project/'cache/geometry-setup.json'
    atomic_write_json(changes,{'operations':[{'op':'update_clip','track_id':track['id'],'clip_id':clip['id'],'patch':{'transform':{'scale':.82,'rotation':-8,'anchor':{'x':.4,'y':.5},'position':{'x':.45,'y':.52}},'keyframes':keys}}, {'op':'add_track','track_id':'geometry_titles','kind':'subtitle','order':5}, {'op':'append_clip','track_id':'geometry_titles','id':'geometry_label','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':duration,'subtitle':{'text':'TARGET','style':{'fontsize':20,'fontcolor':'white','box':True,'boxcolor':'black@0.6','x':'(w-text_w)/2','y':'(h-text_h)/2'}}}]})
    invoke('timeline','compose','--project',str(project),'--input',str(changes))
    invoke('media','adapter','inspect','--project',str(project),'--adapter-id',args.adapter_id)
    binding=['media','track-bind','--project',str(project),'--asset-id',asset_id,'--adapter-id',args.adapter_id,'--object-id',args.object_id,'--roi','0,0,1,1','--step-frames','1','--source-clip-id',clip['id'],'--source-track-id',track['id'],'--target-clip-id','geometry_label','--target-track-id','geometry_titles','--offset-y','-0.10','--scale-mode','roi','--rotation-mode','source','--output',str(project/'validation/geometry-binding.json'),'--apply']
    invoke(*binding,'--dry-run')
    bound=invoke(*binding)
    rendered=[]
    for name,width,height in [('portrait',360,640),('landscape-after-edit',640,360)]:
        if name.startswith('landscape'):
            current=json.loads((project/'project.json').read_text(encoding='utf-8'))
            video=next(c for t in current['sequences'][0]['tracks'] for c in t['clips'] if c['id']==clip['id'])
            crop={**video['crop'],'fit':'fit'}
            atomic_write_json(changes,{'operations':[{'op':'update_clip','track_id':track['id'],'clip_id':clip['id'],'patch':{'crop':crop,'effects':[{'type':'hflip'}]}}]})
            invoke('timeline','compose','--project',str(project),'--input',str(changes))
        output=project/'renders'/(name+'.mp4')
        result=invoke('render','--project',str(project),'--output',str(output),'--profile','custom','--width',str(width),'--height',str(height))
        quality=invoke('quality','check','--project',str(project),'--input',str(output),'--width',str(width),'--height',str(height))
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8'))
        binding_input=next(i for i in manifest['inputs'] if i['kind']=='tracking-binding')
        rendered.append({'file':output.name,'sha256':'sha256:'+sha256_file(output),'width':width,'height':height,'quality_ok':quality['ok'],'binding':binding_input,'filter_graph_transport':{k:v for k,v in result['data']['filter_graph_transport'].items() if k!='path'}})
        for at in (.5,3.5):
            image=root/f'{name}-{at}.png'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-ss',str(at),'-i',str(output),'-frames:v','1',str(image)],capture_output=True,check=True,timeout=60)
    invoke('validate','--project',str(project))
    invoke('policy','audit','--project',str(project))
    invoke('rights','check','--project',str(project),expected=7)
    summary={'checks':checks,'tracking_engine':bound['data']['plan']['engine'],'object_id':args.object_id,'observation_count':len(bound['data']['plan']['tracking_binding']['observations']),'binding_version':bound['data']['plan']['binding_version'],'rendered':rendered,'source_fixture_sha256':'sha256:'+sha256_file(source/'project.json'),'model_executed_by_registered_native_worker':True,'network':'disabled','docker_or_wsl_started':False,'browser_started':False,'downloads':False}
    atomic_write_json(root/'summary.json',summary)
    print(json.dumps({'output':str(root),'renders':len(rendered),'observations':summary['observation_count']}),flush=True)
    return 0


if __name__=='__main__': raise SystemExit(main())
