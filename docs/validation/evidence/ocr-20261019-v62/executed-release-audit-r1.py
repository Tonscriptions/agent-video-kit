"""Audit V62 frozen regression, raw native evidence, publication and Skill scope."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
from run_frozen_regression import frozen
from sync_local_ocr_documents import ROOT,BASE,MEDIA,INSTALL,EN,ZH,OFFLINE,REPORT,CONTRACT,DOCS


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def require(ok,why):
    if not ok:raise ValueError(why)


def run(output):
    require(not output.exists(),'choose new release audit path')
    before=frozen();rows={}
    def bind(path):
        require(path.is_file(),'missing '+str(path));rows[path.relative_to(ROOT).as_posix()]={'sha256':sha(path),'bytes':path.stat().st_size}
    def same_frozen(v):return v.get('frozen_before')==v.get('frozen_after')==before and v.get('frozen_equal')
    full=read(BASE/'full-r2.json');targeted=read(BASE/'unit-r6.json')
    require(full.get('terminal_ok') and full['exit_code']==0 and full['skipped']==0 and full['methods']==1401 and same_frozen(full),'full terminal frozen qualification missing')
    require(targeted['methods']==27 and targeted['terminal_ok'] and targeted['exit_code']==0 and targeted['skipped']==0 and same_frozen(targeted),'27 current OCR unit methods missing')
    for path in (BASE/'full-r2.json',BASE/'unit-r6.json'):
        v=read(path);require(sha(path.with_suffix('.log'))==v['log_sha256'],'regression log changed');bind(path);bind(path.with_suffix('.log'))
    current_calls=0;native_receipts={}
    for label,path in [('english',ROOT/'docs/assets'/EN),('chinese',ROOT/'docs/assets'/ZH),
                       ('installed-english',ROOT/'docs/assets'/OFFLINE/'english'),('installed-chinese',ROOT/'docs/assets'/OFFLINE/'chinese')]:
        v=read(path/'verification.json');native_receipts[label]=v
        require(v['status']=='passed_native_scan' and same_frozen(v) and not v['natural_quality_accepted'],'native case missing: '+label)
        require(v['generator_sha256']==sha(path/'executed-generator.py'),'executed recipe bytes changed')
        bind(path/'verification.json');bind(path/'executed-generator.py');bind(path/'ocr-report.json')
        for c in v['calls']:
            stdout,stderr=path/c['stdout'],path/c['stderr']
            require(c['exit_code']==c['expected_exit_code'] and sha(stdout)==c['stdout_sha256'] and sha(stderr)==c['stderr_sha256'],'native command bytes/status changed')
            if c['kind']=='native':
                raw=gzip.decompress(stdout.read_bytes()) if c['stdout_compressed'] else stdout.read_bytes()
                require(len(raw)==c['stdout_decoded_bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==c['stdout_decoded_sha256'],'native decoded stdout changed')
            elif not label.startswith('installed-'):current_calls+=1
            bind(stdout);bind(stderr)
        report=read(path/'ocr-report.json')
        for artifact in report['request']['adapter']['artifacts']+report['request']['programs']:
            artifact_path=Path(artifact['path'])
            require(artifact_path.stat().st_size==artifact['bytes'] and sha(artifact_path)==artifact['sha256'],
                    'current registered artifact differs from native run: '+artifact['role'])
        require(report['process_cleanup']['all_children_reaped'] and not report['process_cleanup']['active_after_cleanup'],'worker cleanup failed')
        require(report['response']['network']=='disabled' and report['response']['blocked_network_events']==[] and report['response']['providers']==['CPUExecutionProvider'],'OCR execution profile changed')
        if label.endswith('english'):
            require([c['exit_code'] for c in v['calls'][-3:]]==[2,6,8],'real ambiguity/timeout/cancel not exercised')
            for code in (7,):require(sum(c['kind']=='cli' and c['exit_code']==code for c in v['calls'])==4,'commercial rights rejection missing')
    require(current_calls==42,'current CLI count changed')
    media=read(MEDIA/'verification.json');installed_media=read(INSTALL/'installed-media/verification.json')
    for root,v in ((MEDIA,media),(INSTALL/'installed-media',installed_media)):
        require(v['status']=='passed_independent_controlled_ocr_media_checks' and same_frozen(v),'encoded media check missing')
        require(v['final_video_frames']==192 and v['encoded_geometry_frames']==32 and v['full_view_frames']==160 and v['stereo_pcm_sample_frames']==1152000,'encoded scope changed')
        require(len(v['english_targets'])==len(v['chinese_targets'])==4,'independent target count changed')
        require(min(x['glyph_coverage'] for x in v['english_targets']+v['chinese_targets'])>=.8 and max(x['center_max_axis_error_px'] for x in v['english_targets']+v['chinese_targets'])<=12,'OCR target geometry gate failed')
        require(max(x['edge_max_error_px'] for c in v['camera_checks'] for x in c['active_frames'])<=5 and max(x['max_rgb_error'] for c in v['camera_checks'] for x in c['full_view_frames'])<=3 and all(c['pcm_max_error']==0 for c in v['camera_checks']),'camera geometry/PCM gate failed')
        require(v['english_all_frame_zero_lines']['exact_lines']==5 and v['english_all_frame_zero_lines']['character_edits']==7,'raw English errors were changed or hidden')
        for name,item in v['files'].items():
            path=ROOT/name;require(sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],'media input/output changed: '+name);bind(path)
        for c in v['calls']:
            out,err=root/c['stdout'],root/c['stderr'];require(sha(out)==c['stdout_sha256'] and sha(err)==c['stderr_sha256'] and c['exit_code']==0,'independent audit log changed')
            raw=gzip.decompress(out.read_bytes()) if c['stdout_compressed'] else out.read_bytes()
            require('sha256:'+hashlib.sha256(raw).hexdigest()==c['stdout_decoded_sha256'] and len(raw)==c['stdout_decoded_bytes'],'independent decoded log changed');bind(out);bind(err)
        bind(root/'verification.json');bind(root/'executed-audit.py')
    install=read(INSTALL/'verification.json');require(install['status']=='passed_native_isolated_install_ocr_and_encoded_camera' and same_frozen(install) and install['installed_package_files']==131,'native installed product failed')
    require(install['package_bytes_equal_to_wheel_and_source'] and install['isolated_cli_calls']==2 and len(install['native_comparisons'])==2,'isolated installation scope invalid')
    require(read(BASE/'installed-decoded-comparison.json')['compared_streams']==10,'installed decoded comparison absent')
    for c in install['calls']:
        require(c['exit_code']==0 and sha(INSTALL/(c['name']+'.stdout.log'))==c['stdout_sha256'] and sha(INSTALL/(c['name']+'.stderr.log'))==c['stderr_sha256'],'installation log changed')
        bind(INSTALL/(c['name']+'.stdout.log'));bind(INSTALL/(c['name']+'.stderr.log'))
    for path in (INSTALL/'verification.json',BASE/'installed-decoded-comparison.json',BASE/'final-camera-metadata.json'):bind(path)
    for name in ('agent-video-kit-cp313-win_amd64.zip','release-manifest.json','install-receipt.json'):bind(ROOT/'docs/assets'/OFFLINE/name)
    require(sha(ROOT/'docs/assets'/OFFLINE/'agent-video-kit-cp313-win_amd64.zip')==install['release_zip_sha256'],'release zip changed')
    review=read(MEDIA/'static-review.json');require(review['status']=='static_frames_reviewed' and review['reviewed_samples']==12 and not review['continuous_playback'] and not review['audio_listened'] and not review['natural_quality_accepted'],'static review scope changed');bind(MEDIA/'static-review.json')
    processes=read(BASE/'post-native-owned-processes.json');require(processes['matched_count']==0 and not processes['continuous_process_monitor'],'post-native process snapshot failed');bind(BASE/'post-native-owned-processes.json')
    old=read(BASE/'full-r1.json');require(old['exit_code']!=0 and not old['terminal_ok'] and not old['frozen_equal'],'interrupted stale regression must remain unqualified')
    for path in (BASE/'full-r1.json',BASE/'full-r1.log',BASE/'development-full-r1-interruption.json',MEDIA.parent/'ocr-media-20261019-v62-r2/threshold-diagnosis.json'):bind(path)
    skills=read(BASE/'skills-r1.json');manifest=read(ROOT/'video-cut-install-manifest.json')
    require(skills['skill_count']==manifest['skill_count']==17 and skills['local_links_checked']==228,'Skill registration count changed')
    require(manifest['current_audit']['record_sha256']==sha(BASE/'skills-r1.json'),'Skill manifest audit not current')
    for item in skills['results']:
        path=ROOT/'skills'/item['skill']/'SKILL.md';entry=next(x for x in manifest['skills'] if x['name']==item['skill'])
        require(sha(path)==item['sha256']=='sha256:'+entry['skill_md_sha256'] and item['validator_exit_code']==0 and item['installed_directory_resolves_to_repo'],'Skill current source/registration invalid');bind(path)
    bind(BASE/'skills-r1.json');bind(ROOT/'video-cut-install-manifest.json')
    r06_root=ROOT/'docs/validation/evidence/openfilm-reuse-20261019-r06'
    r06=read(r06_root/'verification.json');refresh=read(ROOT/'docs/validation/evidence/openfilm-refresh-20261019-r06/verification.json')
    require(r06['status']=='passed_scoped_r06_source_research' and same_frozen(r06) and r06['totals']=={'tests':65,'pass':64,'fail':0,'skipped':1}
            and r06['row_probe']['cases']==8 and r06['all_cli_src_files_unchanged'] and not r06['product_adopted'],'R06 separate source scope changed')
    require(r06['refresh_sha256']==sha(ROOT/'docs/validation/evidence/openfilm-refresh-20261019-r06/verification.json')
            and refresh['source_archive_sha256']==sha(Path(refresh['source_archive'])),'R06 immutable source changed')
    require(r06['upstream_stdout_sha256']==sha(r06_root/'upstream-selected.stdout.log') and r06['upstream_stderr_sha256']==sha(r06_root/'upstream-selected.stderr.log'),'R06 original test log changed')
    for folder in (r06_root,ROOT/'docs/validation/evidence/openfilm-refresh-20261019-r06',ROOT/'docs/validation/evidence/openfilm-head-20261019-r06'):
        for path in folder.rglob('*'):
            if path.is_file():bind(path)
    bind(Path(refresh['source_archive']))
    docs=[*DOCS,'docs/validation/'+REPORT,'docs/specs/'+CONTRACT,'docs/third-party/PP-OCRv4离线模型与许可来源_2026-10-19.md','docs/OpenFilm创作流程本地适配设计_2026-10-19.md','docs/OpenFilm复用复核与开发成本更新_2026-10-19.md','docs/OpenFilm导出修复与纯轨道模块复用复核_2026-10-19.md']
    local_links=0
    for name in docs:
        path=ROOT/name;body=path.read_text(encoding='utf-8')
        if name in DOCS:require('<!-- V62-CURRENT -->' in body and '5/10' in body and '完整剪映等价' in body,'current document scope missing: '+name)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',body):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            require((path.parent/urllib.parse.unquote(target)).resolve().exists(),'broken doc link: '+name+' '+target);local_links+=1
        bind(path)
    require('| V62 |' in (ROOT/'README.md').read_text(encoding='utf-8') and f'docs/assets/{EN}/select.gif' in (ROOT/'README.md').read_text(encoding='utf-8'),'README numbered row or actual GIF missing')
    after=frozen();require(before==after,'product inputs changed during release audit')
    record={'status':'passed_v62_ocr_release_audit','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'full_methods':full['methods'],'unit_methods_subset':27,'current_cli_calls':current_calls,'installed_isolated_cli_calls':44,
        'final_frames':192,'stereo_sample_frames':1152000,'installed_frames_separate':192,'input_scenes':{'controlled_page_video':1,'authored_chinese_image':1},
        'raw_frame_zero_english_exact_lines':5,'raw_frame_zero_english_edits':7,'skills':17,'skill_links':228,
        'r06_separate_upstream_tests':r06['totals'],'r06_separate_pure_row_fixtures':8,'r06_new_product_adoption':False,
        'document_local_links_checked':local_links,'frozen_before':before,'frozen_after':after,'frozen_equal':True,
        'natural_quality_accepted':False,'complete_capcut_parity_accepted':False,'files':rows,'generator_sha256':sha(Path(__file__))}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','full_methods','current_cli_calls','document_local_links_checked','skills')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output.resolve())
