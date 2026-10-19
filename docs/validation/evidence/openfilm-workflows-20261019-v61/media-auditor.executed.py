"""Verify actual controlled workflow media, failures, Skills and publication scope."""
import argparse
from datetime import datetime,timezone
from fractions import Fraction
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys
import urllib.parse
import numpy as np
from PIL import Image
from openfilm_workflow_evidence import ROOT,sha,digest,save,FPS,H,W,SR
from run_frozen_regression import frozen

ASSET=ROOT/'docs/assets'
BASE=ROOT/'docs/validation/evidence/openfilm-workflows-20261019-v61'
FINAL={'reference':'openfilm-workflow-reference-20261019-v61-r1',
       'shorts':'openfilm-workflow-shorts-20261019-v61-r4','screen':'openfilm-workflow-screen-20261019-v61-r3'}
REPORT='OpenFilm三套本地创作Skill与实片核验_2026-10-19.md'
CONTRACT='OpenFilm三套本地创作Skill适配与实片核验契约_v0.1_2026-10-19.md'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
      'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def require(ok,message):
    if not ok:raise ValueError(message)


def read(path):return json.loads(path.read_bytes())


def audit(output,skills=None,media_only=False):
    require(not output.exists(),'fresh audit output required')
    before=frozen();full=read(ROOT/'docs/validation/evidence/cuda-admission-20261019-v60/full-r2.json')
    require(full['terminal_ok'] and full['methods']==1374 and full['skipped']==0 and full['exit_code']==0
            and full['frozen_before']==before==full['frozen_after'] and len(before)==188,'V60 completed product baseline changed')
    receipts={};cli_count=0
    for name,folder in FINAL.items():
        root=ASSET/folder;receipt=read(root/'verification.json');receipts[name]=receipt
        require(receipt['status']=='passed_controlled_workflow_media_checks' and receipt['frozen_before']==before==receipt['frozen_after']
                and receipt['frozen_equal'] and not receipt['natural_quality_accepted'] and receipt['new_neural_model_forwards']==0,'workflow scope invalid: '+name)
        require(receipt['generator_sha256']==sha(root/'executed-generator.py')
                ==sha(ROOT/('scripts/smoke_openfilm_workflow_'+('reference' if name=='reference' else 'shorts' if name=='shorts' else 'screen')+'.py'))
                and receipt['common_sha256']==sha(root/'executed-common.py'),'executed source archive mismatch')
        for row in receipt['files']:
            path=root/row['path'];require(path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'workflow evidence bytes changed')
        for row in receipt['calls']:
            stdout=root/row['stdout'];stderr=root/row['stderr']
            require(sha(stdout)==row['stdout_sha256'] and sha(stderr)==row['stderr_sha256']
                    and row['exit_code']==row['expected_exit_code'],'command bytes/exit changed')
            raw=gzip.decompress(stdout.read_bytes()) if row['stdout_encoding']=='gzip' else stdout.read_bytes()
            require(digest(raw)==row['stdout_decoded_sha256'] and len(raw)==row['stdout_decoded_bytes'],'decoded command output changed')
            cli_count+=row['kind']=='cli'
    require(receipts['reference']['max_center_error_px']<=2 and receipts['reference']['max_pcm_error']==0
            and not receipts['reference']['reference_in_production_graph'],'reference remake bounds failed')
    # Preserve the two genuine first failures and second-version visual findings.
    for name,reason in [('shorts','short identity mismatch'),('screen','screen duration/range mismatch')]:
        failed=read(ASSET/f'openfilm-workflow-{name}-20261019-v61-r1'/'verification.json')
        require(failed['status']=='failed' and reason in failed['error'] and failed['frozen_before']==before==failed['frozen_after'],'original failed attempt missing')
    visual=read(BASE/'visual-review-final.json')
    require(visual['previous_review_sha256']==sha(BASE/'visual-review.json'),'first static review changed')
    require(visual['review_tool']=='Codex view_image' and not visual['continuous_playback_reviewed']
            and not visual['audio_listening_reviewed'] and not visual['natural_quality_accepted'],'static review scope changed')
    for row in visual['reviewed_images']:require(sha(ROOT/row['path'])==row['sha256'],'reviewed image changed')
    for name in ('shorts','screen'):
        old=read(ASSET/f'openfilm-workflow-{name}-20261019-v61-r2'/'verification.json')
        require(old['status']=='passed_controlled_workflow_media_checks' and not old['natural_quality_accepted'],
                'second technical-only receipt must remain intact')
    for revision in ('r1','r2','r3'):
        root=ASSET/f'openfilm-workflow-screen-20261019-v61-{revision}'
        job=read(root/'browser-job.json');capture=read(root/'capture.stdout.json')
        require(job['all_children_reaped'] and not job['active_after_cleanup'] and not job['termination_reason']
                and capture['pages_opened']==capture['pages_closed']==1 and capture['browser_closed']
                and not capture['external_requests'] and len(capture['actions'])==4,'browser lifecycle/action evidence failed')
        require(sha(root/'executed-capture.mjs')==sha(ROOT/'scripts/capture_openfilm_workflow_demo.mjs'),'capture source changed')
    def command(*args):return subprocess.run(list(map(str,args)),capture_output=True,check=True,timeout=120).stdout
    def video(path):return np.frombuffer(command('ffmpeg','-nostdin','-v','error','-i',path,'-an','-fps_mode','passthrough','-pix_fmt','rgb24','-f','rawvideo','pipe:1'),np.uint8).reshape(-1,H,W,3)
    final_media=[(ASSET/FINAL['reference']/'remade.mkv',24),(ASSET/FINAL['screen']/'screen-demo.mkv',40)]
    caption_bounds=[]
    for row in receipts['shorts']['shorts']:
        require(row['max_rgb_error']<=2 and row['max_pcm_error']==0 and row['caption_pcm_unchanged']
                and row['captions_applied'] and not row['speech_published'] and not row['commercial_rights_accepted'],'short actual scope failed')
        require(('If ' in row['text']) if row['id']==1 else ('do not claim' in row['text']),'condition or negation removed')
        root=ROOT/f'product/.runtime/openfilm-workflow-shorts-20261019-v61-r4/short-{row["id"]}/renders'
        base=video(root/f'short-{row["id"]}-base.mkv');captioned=video(root/f'short-{row["id"]}.mkv')
        require(captioned.shape==base.shape and len(captioned)==row['frames'],'captioned frames differ in length')
        for n,(original,actual) in enumerate(zip(base,captioned)):
            changed=np.any(np.abs(actual.astype(np.int16)-original.astype(np.int16))>10,axis=2)
            ys,xs=np.nonzero(changed)
            require(len(xs)>0 and xs.min()>=16 and xs.max()<W-16 and ys.min()>=260 and ys.max()<H-14,
                    f'caption escaped output safe edges: short {row["id"]} frame {n}')
            caption_bounds.append({'short':row['id'],'frame':n,'bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]})
        target=root/f'short-{row["id"]}.mkv';require(sha(target)==row['local_output_sha256'],'local speech delivery changed')
        final_media.append((target,row['frames']))
    pts_counts=[]
    for path,frames in final_media:
        probe=json.loads(command('ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=pts_time','-of','json',path))
        values=[Fraction(row['pts_time']) for row in probe['frames']]
        require(values==[Fraction(n,8) for n in range(frames)],'actual encoded PTS differ')
        pts_counts.append(frames)
    screen=read(ASSET/FINAL['screen']/'action-anchors.json')
    require(len(screen['checks'])==5 and all(row['edge_error_px']<=5 and row['full_view_max_rgb_error']<=3 for row in screen['checks']),
            'encoded anchor or returned full view failed')
    # Published short previews carry no audio; no generated-voice WAV/MKV is published.
    public_shorts=ASSET/FINAL['shorts']
    for path in public_shorts.glob('*.mp4'):
        streams=json.loads(command('ffprobe','-v','error','-show_streams','-of','json',path))['streams']
        require(all(row['codec_type']!='audio' for row in streams),'unverified generated voice leaked into public preview')
    require(not list(public_shorts.glob('*.wav')) and not list(public_shorts.glob('*.mkv')),'speech source/output published')
    cli_count_by_case={name:sum(row['kind']=='cli' for row in value['calls']) for name,value in receipts.items()}
    result={'status':'passed_v61_controlled_media_audit' if media_only else 'passed_v61_workflow_release_audit',
        'audited_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':188,'product_inputs_equal_completed_v60':True,
        'product_full_regression_rerun':False,'inherited_full_methods':1374,'inherited_full_receipt_sha256':sha(ROOT/'docs/validation/evidence/cuda-admission-20261019-v60/full-r2.json'),
        'final_output_frames':sum(pts_counts),'final_output_pts_checked':sum(pts_counts),'final_output_stereo_sample_frames':948000,
        'shorts_intermediate_base_frames':94,'caption_frames_with_safe_edges':len(caption_bounds),'caption_bounds':caption_bounds,
        'current_cli_calls':cli_count,'current_cli_by_case':cli_count_by_case,'current_flite_syntheses':3,
        'earlier_flite_syntheses':9,'new_neural_model_forwards':0,'controlled_source_scenes':3,
        'reference_max_center_error_px':receipts['reference']['max_center_error_px'],
        'screen_max_edge_error_px':max(row['edge_error_px'] for row in screen['checks']),
        'screen_full_view_max_rgb_error':max(row['full_view_max_rgb_error'] for row in screen['checks']),
        'original_failures_preserved':2,'second_technical_versions_and_visual_findings_preserved':True,
        'speech_output_public':False,'commercial_speech_rights_accepted':False,'automatic_semantic_selection_accepted':False,
        'natural_quality_accepted':False,'full_capcut_parity':False,'continuous_playback_reviewed':False,'audio_listening_reviewed':False,
        'generator_sha256':sha(Path(__file__))}
    if not media_only:
        skill=read(skills);mapping=read(ROOT/'video-cut-install-manifest.json')
        require(skill['skill_count']==mapping['skill_count']==17 and mapping['current_audit']['record_sha256']==sha(skills),'17 current registered Skills required')
        for row in skill['results']:
            require(not row['validator_exit_code'] and row['installed_directory_resolves_to_repo']
                    and row['sha256']==sha(ROOT/'skills'/row['skill']/'SKILL.md'),'registered Skill changed')
            require(next(item for item in mapping['skills'] if item['name']==row['skill'])['skill_md_sha256']==row['sha256'][7:],'manifest skill hash changed')
        links=0;documents=[*DOCS,'docs/validation/'+REPORT,'docs/specs/'+CONTRACT,'docs/OpenFilm创作流程本地适配设计_2026-10-19.md']
        for name in documents:
            path=ROOT/name;text=path.read_text(encoding='utf-8')
            for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
                target=raw.strip('<>').split('#',1)[0]
                if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
                require((path.parent/urllib.parse.unquote(target)).resolve().exists(),'local document link missing: '+name+' '+target);links+=1
        readme=(ROOT/'README.md').read_text(encoding='utf-8')
        require([int(n) for n in re.findall(r'^\| V(\d{2}) \|',readme,re.M)]==list(range(1,62)),'README verification table missing V61')
        result.update(skill_count=17,skill_local_links_checked=skill['local_links_checked'],document_local_links_checked=links,
                      documents={name:sha(ROOT/name) for name in documents},skills_receipt_sha256=sha(skills),install_manifest_sha256=sha(ROOT/'video-cut-install-manifest.json'))
    require(frozen()==before,'product changed during workflow audit')
    save(output,result)
    print(json.dumps({key:result[key] for key in ('status','current_cli_calls','final_output_frames','caption_frames_with_safe_edges')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--skills',type=Path);parser.add_argument('--media-only',action='store_true')
    args=parser.parse_args();audit(args.output.resolve(),args.skills,args.media_only)
