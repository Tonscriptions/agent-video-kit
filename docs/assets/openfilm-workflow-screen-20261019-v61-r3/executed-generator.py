"""Capture actual original test-page actions, then author local anchor pans."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
from PIL import Image,ImageDraw
from openfilm_workflow_evidence import Evidence,FPS,H,ROOT,SR,TPS,W,append,digest,font,save,sha,wav


def run(work,output):
    evidence=Evidence(work,output,Path(__file__));error=None;measurements={};job=None
    try:
        font(evidence.output)
        save(evidence.output/'provenance.json',{'original_test_application_text_and_events':'CC0-1.0',
            'font_license':'Bitstream-Vera','font_notice':'LICENSE_DEJAVU',
            'scope':'actual browser actions on an original offline controlled app; not a natural product recording or editor GUI',
            'timing':'48 screenshots sampled after explicit actions at author-assigned 8 fps; not measured wall-clock responsiveness'})
        runtime=json.loads((ROOT/'product/.runtime/html-motion-runtime-20261018-e2.json').read_bytes())
        sys.path.insert(0,str(ROOT/'product/src'))
        from ai_ad_editor.browser_process import BrowserProcessJob
        frames=evidence.work/'capture';html=evidence.output/'original-test-app.html'
        request={**runtime,'frames':str(frames),'font':str(evidence.output/'DejaVuSans.ttf'),'html':str(html)}
        worker=ROOT/'scripts/capture_openfilm_workflow_demo.mjs'
        shutil.copyfile(worker,evidence.output/'executed-capture.mjs');job=BrowserProcessJob(180)
        import subprocess
        process=job.start([runtime['node'],str(worker)],cwd=evidence.work,env=evidence.env,
                          stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:stdout,stderr=process.communicate((json.dumps(request)+'\n').encode(),timeout=180)
        finally:save(evidence.output/'browser-job.json',job.close());job=None
        (evidence.output/'capture.stdout.json').write_bytes(stdout);(evidence.output/'capture.stderr.log').write_bytes(stderr)
        capture=json.loads(stdout)
        if process.returncode or capture['status']!='passed_original_test_app_action_capture' or not capture['browser_closed'] or capture['pages_opened']!=capture['pages_closed'] or capture['external_requests']:
            raise ValueError('controlled page capture or lifecycle failed')
        source_frames=np.stack([np.asarray(Image.open(frames/f'{n:03}.png').convert('RGB')) for n in range(48)])
        source=evidence.output/'screen-input.mkv'
        evidence.ffmpeg('-framerate',FPS,'-i',frames/'%03d.png','-c:v','ffv1','-pix_fmt','bgr0',source)
        t=np.arange(6*SR)/SR;signal=np.rint(np.stack([.035*np.sin(2*np.pi*300*t),.025*np.sin(2*np.pi*470*t)],axis=1)*32767).astype('<i2')
        wav(evidence.output/'original-tone.wav',signal)
        project=evidence.project('screen-demo',5)
        evidence.ingest(project,source,'screen');evidence.ingest(project,evidence.output/'original-tone.wav','sound')
        # Author absolute source-time anchors from the recorded action element boxes.
        points=[]
        for action in capture['actions']:
            box=action['bounding_box'];points.append({'source_tick':action['source_tick'],'action':action['element_id'],
                'source_center':[box['x']+box['width']/2,box['y']+box['height']/2],
                'target_scale':1.4,'evidence':'actual browser locator box at action'})
        # Keep each real action in an editable clip; remove initial idle 0..1 s.
        # Five one-second retained blocks: select, type, preview, save, final result.
        operations=[]
        for i in range(5):
            box=points[min(i,3)]['source_center']
            x=.5+(W/2-box[0])*1.4/W;y=.5+(H/2-box[1])*1.4/H
            operations.append(append('screen',f'action-{i}','track_video_1',i*TPS,TPS,source=(i+1)*TPS,
                transform={'scale':1.4,'position':{'x':x,'y':y}},
                keyframes=[{'property':name,'keyframes':[{'at_tick':0,'value':start,'interpolation':'ease_in_out'},
                    {'at_tick':TPS//2,'value':end,'interpolation':'hold'}]} for name,start,end in
                    [('transform.scale',1.4,1.0),('transform.position.x',x,.5),('transform.position.y',y,.5)]]))
        operations.append(append('sound','tone','track_audio_1',0,5*TPS,source=TPS))
        evidence.compose(project,'screen-anchors',operations)
        target=evidence.render(project,'screen-demo')
        video=evidence.video(target);pcm=evidence.audio(target)
        expected_audio=signal[SR:6*SR].astype(np.float32)/32768
        if len(video)!=40 or pcm.shape!=expected_audio.shape:raise ValueError('screen duration/range mismatch')
        pcm_error=float(np.max(np.abs(pcm-expected_audio)))
        if pcm_error>2e-6:raise ValueError('screen source audio changed')
        # Compare an encoded control's solid-color run with independently projected
        # locator geometry. This checks actual output pixels, not only authored JSON.
        checks=[]
        for i in range(5):
            source=source_frames[(i+1)*FPS];actual=video[i*FPS]
            crop=actual[H//2-6:H//2+6,W//2-6:W//2+6].astype(np.float64)
            point=points[min(i,3)]['source_center'];sx,sy=map(round,point)
            original_patch=source[sy-4:sy+4,sx-4:sx+4].astype(np.float64)
            delta=float(np.max(np.abs(crop.mean(axis=(0,1))-original_patch.mean(axis=(0,1)))))
            box=capture['actions'][min(i,3)]['bounding_box']
            control_color=np.array((232,239,248) if i==1 else ((46,117,168) if i==2 else (34,110,82)))
            # Scan above the text baseline through the middle of the rounded rect.
            scan_y=round(H/2-box['height']*1.4/2+8)
            near=np.max(np.abs(actual[scan_y].astype(np.int16)-control_color),axis=1)<=5
            runs=[];start=None
            for x,on in enumerate([*near,False]):
                if on and start is None:start=x
                elif not on and start is not None:runs.append((start,x));start=None
            expected_left=W/2-box['width']*1.4/2;expected_right=W/2+box['width']*1.4/2
            candidates=[run for run in runs if run[0]<=W/2<run[1]]
            if len(candidates)!=1:raise ValueError('encoded action control not centered')
            run=candidates[0];edge_error=max(abs(run[0]-expected_left),abs(run[1]-expected_right))
            if edge_error>5:raise ValueError(f'encoded action control edges disagree by {edge_error} px')
            checks.append({'clip':i,'source_frame':(i+1)*FPS,'source_anchor':point,'sampled_center_mean_delta':delta,
                           'scan_y':scan_y,'encoded_color_run':list(run),'independent_projected_edges':[expected_left,expected_right],
                           'edge_error_px':edge_error,
                           'source_frame_sha256':digest(source.tobytes()),'output_frame_sha256':digest(actual.tobytes())})
        p=json.loads((project/'project.json').read_bytes());clips=next(t for t in p['sequences'][0]['tracks'] if t['id']=='track_video_1')['clips']
        for i,clip in enumerate(clips):
            point=points[min(i,3)]['source_center'];transform=clip['transform'];position=transform['position']
            mapped=[(point[0]-W/2)*transform['scale']+W*position['x'],(point[1]-H/2)*transform['scale']+H*position['y']]
            if abs(mapped[0]-W/2)>1e-6 or abs(mapped[1]-H/2)>1e-6:raise ValueError('action anchor not mapped to center')
            if clip['source_in_tick']!=(i+1)*TPS or clip['timeline_start_tick']!=i*TPS:raise ValueError('source event range lost')
        for i in range(5):
            actual=video[i*FPS+4].astype(np.int16);original=source_frames[(i+1)*FPS+4].astype(np.int16)
            full_view_delta=int(np.max(np.abs(actual-original)))
            if full_view_delta>3:raise ValueError('post-action result did not return to exact full view')
            checks[i]['full_view_frame']=i*FPS+4;checks[i]['full_view_max_rgb_error']=full_view_delta
        save(evidence.output/'action-anchors.json',{'actions':points,'checks':checks,'initial_idle_removed_tick':[0,TPS],
            'speed_changes':[],'wall_clock_response_speed_accepted':False,'automatic_click_detection_performed':False})
        evidence.cli('convert','export','--project',project,'--target-format','package','--output',evidence.output/'screen-demo.aevpkg.zip')
        evidence.preview(evidence.output/'screen-input.mkv','screen-input-preview');evidence.preview(target,'screen-demo-preview')
        contact=Image.new('RGB',(W*2,H*3))
        for row,index in enumerate((0,16,32)):
            contact.paste(Image.fromarray(source_frames[index]),(0,row*H));contact.paste(Image.fromarray(video[max(0,index-8)]),(W,row*H))
        contact.save(evidence.output/'input-output-contact.png')
        measurements={'case':'screen-demo','source_frames':48,'output_frames':40,'stereo_sample_frames':len(pcm),
            'max_pcm_error':pcm_error,'actual_page_actions':len(capture['actions']),'recorded_action_anchors':len(points),
            'browser_job_reaped':True,'source':'original controlled web app, actual actions, sampled screenshots',
            'natural_recording_accepted':False,'automatic_click_detection_performed':False,'new_original_source_scenes':1}
    except Exception as exc:error=exc;raise
    finally:
        if job is not None:save(evidence.output/'browser-job.json',job.close())
        evidence.finish(error,**measurements)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.work,args.output)
