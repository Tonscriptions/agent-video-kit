"""Private existing natural clip: explicit wrist correction and real LaMa consumption.

Publishes scalar/hash/CLI evidence only. Never copies natural media into docs.
This is the old scene and five old assertions, not a new blind quality test.
"""
from __future__ import annotations
import argparse, contextlib, hashlib, io, json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from smoke_fragments import frozen, save, sha
sys.path.insert(0, str(ROOT/'product/src'))
from ai_ad_editor.cli import main
from ai_ad_editor.runtime import configure_local_runtime


def run(work, output):
    assert not work.exists() and not output.exists()
    work.mkdir(parents=True); configure_local_runtime(); before = frozen()
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    old = ROOT/'product/.runtime/mask-review-natural-20261016'
    original = json.loads((old/'project/project.json').read_text(encoding='utf-8'))
    sources = {a['id']: old/'project'/a['uri'] for a in original['assets']}
    previous = json.loads((old/'summary.json').read_text(encoding='utf-8'))
    expectations = json.loads((old/'expectations.json').read_text(encoding='utf-8'))
    w, h, frames = 512, 288, 32
    def digest(data): return 'sha256:'+hashlib.sha256(data).hexdigest()
    def native(argv):
        result = subprocess.run(argv, capture_output=True, timeout=120)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        return result.stdout
    def decode(path):
        return np.frombuffer(native(['ffmpeg','-v','error','-i',str(path),'-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1']), np.uint8).reshape(frames,h,w,4)
    calls = []
    def cli(*args, expected=0):
        stream = io.StringIO(); started = time.monotonic()
        with contextlib.redirect_stdout(stream): code = main(list(map(str,args)))
        value = json.loads(stream.getvalue()); path = work/f'cli-{len(calls)+1:02}.json'
        path.write_text(stream.getvalue(), encoding='utf-8', newline='\n')
        calls.append({'args':list(map(str,args)), 'exit_code':code, 'seconds':time.monotonic()-started, 'private_log':str(path), 'sha256':sha(path)})
        save(work/'calls.json', calls)
        assert code == expected, value
        print(json.dumps({'call':len(calls),'command':value['command'],'exit_code':code}),flush=True)
        return value
    project = work/'project'; cli('project','init',project)
    assets = {}
    for name, source in [('source',sources['source']),('mask',sources['corrected_mask'])]:
        assets[name] = cli('media','ingest','--project',project,'--asset-id',name,'--input',source)['data']['asset']
    save(work/'expectations.json',expectations)
    failed = cli('quality','mask','--project',project,'--asset-id','mask','--expectations',work/'expectations.json',expected=2)
    assert len(failed['data']['failed_points']) == 1 and failed['data']['failed_points'][0]['frame'] == 31
    edits = {'version':'1.0.0','coordinate_space':'normalized-output','scene_cut_frames':[],
        'mask':{'asset_id':'mask','sha256':assets['mask']['sha256'],'channel':'alpha','width':w,'height':h,'frames':frames,'fps':'8'},
        'operations':[{'id':'explicit-final-wrist','type':'brush','mode':'add','start_frame':31,'end_frame':32,
            'interpolation':'hold','keyframes':[{'frame':31,'points':[[7/w,214/h],[15/w,209/h],[30/w,193/h]],'radius_pixels':5}]}]}
    save(work/'edits.json',edits)
    edited = cli('media','mask-edit','--project',project,'--asset-id','mask','--derived-asset-id','fixed',
        '--edits',work/'edits.json')['data']
    passed = cli('quality','mask','--project',project,'--asset-id','fixed','--expectations',work/'expectations.json')
    assert passed['data']['checked_points'] == 5 and not passed['data']['failed_points']
    a, b, source = decode(project/assets['mask']['uri']), decode(project/edited['asset']['uri']), decode(project/assets['source']['uri'])
    assert np.array_equal(a[:31,:,:,3],b[:31,:,:,3])
    # Independently authored capsule distance oracle on the final frame.
    yy,xx = np.mgrid[:h,:w]; px,py = xx+.5,yy+.5
    support = np.zeros((h,w),bool)
    for p,q in [((7,214),(15,209)),((15,209),(30,193))]:
        dx,dy = q[0]-p[0],q[1]-p[1]
        t = np.clip(((px-p[0])*dx+(py-p[1])*dy)/(dx*dx+dy*dy),0,1)
        support |= (px-p[0]-t*dx)**2+(py-p[1]-t*dy)**2 <= 25
    expected = a[:,:,:,3].copy(); expected[-1][support] = 255
    assert np.array_equal(expected,b[:,:,:,3]) and np.all(b[:,:,:,:3]==255)
    model = ROOT/'product/.runtime/models/inpainting/big-lama.pt'
    executable = Path(sys.executable)
    adapter = cli('media','adapter','register','--project',project,'--adapter-id','lama_local',
        '--engine','torchscript-lama-local-v1','--model-path',model,'--executable',executable,
        '--evidence',model.with_name('lama-evidence.json'),'--device','cuda')['data']['adapter']
    repaired = cli('media','inpaint','--project',project,'--asset-id','source','--mask-asset-id','fixed',
        '--adapter-id','lama_local','--derived-asset-id','repaired','--mask-grow','4','--model-max-edge','256',
        '--repair-blend','harmonic')['data']
    result = repaired['inpainting']; metrics = result['worker']['metrics']
    actual = decode(project/repaired['asset']['uri'])
    grown = np.stack([np.asarray(Image.fromarray(frame).filter(ImageFilter.MaxFilter(9)))>127 for frame in b[:,:,:,3]])
    rgb_changes = np.any(actual[:,:,:,:3]!=source[:,:,:,:3],axis=3)
    outside = int(np.count_nonzero(rgb_changes & ~grown)); assert outside == 0
    assert np.array_equal(source[:,:,:,3],actual[:,:,:,3])
    assert metrics['decoded_mask_rgba_sha256'] == digest(b.tobytes()) and metrics['model_calls'] > 0
    # Decode the preserved real audio independently, not from a claimed manifest.
    pcm = []
    for path in [project/assets['source']['uri'],project/repaired['asset']['uri']]:
        pcm.append(native(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1']))
    assert pcm[0] and pcm[0] == pcm[1]
    validation = cli('validate','--project',project)
    policy = cli('policy','audit','--project',project)
    rights = cli('rights','check','--project',project,expected=7)
    # Local inspection only. No natural RGB, alpha or contact is published.
    contact = Image.new('RGB',(w*3,h+28),'#151e29'); d = ImageDraw.Draw(contact)
    for c,(label,pixels) in enumerate([('SOURCE / PRIVATE',source[-1,:,:,:3]),('EDITED SELECTION / PRIVATE',source[-1,:,:,:3].copy()),('REAL LAMA / UNACCEPTED',actual[-1,:,:,:3])]):
        if c == 1:
            selected=b[-1,:,:,3]>127; pixels[selected]=(pixels[selected].astype(np.float32)*.5+np.array([120,20,10])).clip(0,255).astype(np.uint8)
        contact.paste(Image.fromarray(pixels),(c*w,28)); d.text((c*w+5,5),label,fill='white')
    contact_path=work/'private-frame-31.png'; contact.save(contact_path)
    assert before == frozen()
    record = {'status':'execution_verified_semantic_and_repair_quality_unaccepted', 'generator_sha256':sha(Path(__file__)),
        'frozen_product':before,'calls':calls,'actual_cli_calls':len(calls),'frames':frames,'new_scene_count':0,
        'new_segmentation_model_runs':0,'new_repair_worker_runs':1,'actual_model_calls':metrics['model_calls'],
        'source':{'path':str(sources['source']),'sha256':sha(sources['source'])},
        'input_mask':{'path':str(sources['corrected_mask']),'sha256':sha(sources['corrected_mask'])},
        'edited_mask':{'path':str(project/edited['asset']['uri']),'sha256':edited['asset']['sha256']},
        'repaired':{'path':str(project/repaired['asset']['uri']),'sha256':repaired['asset']['sha256']},
        'editable_plan':edits,'plan_sha256':edited['mask_edit']['plan']['plan_sha256'],
        'expectations':expectations,'before':failed['data'],'after':passed['data'],
        'independent_alpha_exact':True,'first_31_alpha_frames_unchanged':True,
        'changed_final_frame_alpha_pixels':int(np.count_nonzero(a[-1,:,:,3]!=b[-1,:,:,3])),
        'every_pts_exact':edited['mask_edit']['every_pts_exact'],'model_received_exact_edited_rgba':True,
        'model_adapter':adapter,'worker':result['worker'],'outside_grown_mask_changed_rgb_pixels':outside,
        'source_alpha_exact':True,'changed_inside_pixels':int(np.count_nonzero(rgb_changes & grown)),
        'pcm_bytes':len(pcm[0]),'pcm_sha256':digest(pcm[0]),'pcm_exact':True,
        'policy_passed':policy['ok'],'validation_passed':validation['ok'],'rights_expected_exit_code':7,
        'rights_check':rights['data'],'private_contact':{'path':str(contact_path),'sha256':sha(contact_path)},
        'manual_contact_inspection_completed':False,'dense_ground_truth_available':False,
        'natural_pixels_published':False,'natural_quality_accepted':False,'complete_capcut_parity_accepted':False,
        'continuous_playback_reviewed':False,'sound_reviewed':False,'browser_started':False,'virtualization':False,
        'limitation':'Five preexisting sparse assertions now pass after explicit manual geometry. This does not prove object completeness, identity, edge quality, texture reconstruction or temporal stability.'}
    save(output,record)
    print(json.dumps({'calls':len(calls),'model_calls':metrics['model_calls'],'before_failed':1,'after_failed':0,
        'outside_changed':outside,'pcm_bytes':len(pcm[0])}),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.work.resolve(),args.output.resolve())
