"""Bind V71 source, original failures, decoded pixels, install and delivery gates."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.parse
from run_frozen_regression import frozen
from sync_contact_sheet_documents import DOCUMENTS,REPORT,CONTRACT

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/contact-sheet-20261020-v71'


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();assert len(current)==217;bound={}
    def bind(path):
        path=Path(path);assert path.is_file(),path;bound[path.relative_to(ROOT).as_posix()]=sha(path)
    def receipt(name):
        path=BASE/name;bind(path);return read(path)
    def stable(value):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    focus=receipt('focus-r5.json');stable(focus)
    assert focus['terminal_ok'] and focus['exit_code']==0 and focus['methods']==25 and focus['skipped']==0
    full=receipt('full-r2.json');stable(full)
    assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1593 and full['skipped']==0
    bind(BASE/'full-r2.log');assert sha(BASE/'full-r2.log')==full['log_sha256']
    assert full['external_fixtures_equal'] and full['external_fixture_count']==8 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
    for field,name in [('wrapper_sha256','run_with_regression_fixtures'),('inner_runner_sha256','run_frozen_regression'),('fixture_definition_sha256','materialize_regression_fixtures')]:
        path=ROOT/'scripts'/(name+'.py');bind(path);assert sha(path)==full[field]
    for name,value in full['external_fixtures_after'].items():
        path=ROOT/name;bind(path);assert path.stat().st_size==value['bytes'] and sha(path)==value['sha256']
    manifest=ROOT/full['external_fixture_manifest'];bind(manifest);assert sha(manifest)==full['external_fixture_manifest_sha256']
    old=receipt('full-r1.json');assert old['exit_code']==1 and not old['terminal_ok'] and old['methods']==1589
    diagnosis=receipt('full-r1-fixture-diagnosis-r2.json');assert diagnosis['fixture_related_failures']==70 and diagnosis['native_job_assignment_errors']==1
    job=receipt('job-start-r2.json');stable(job);assert job['terminal_ok'] and job['methods']==4 and job['skipped']==0
    race=receipt('job-race-r3/verification.json');stable(race);assert race['status']=='passed_controlled_race'
    tree=ast.parse((ROOT/'product/tests/test_contact_sheet.py').read_text(encoding='utf8'))
    methods=[n.name for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
    assert len(methods)==25;log=(BASE/'full-r2.log').read_text(encoding='utf8')
    assert all(re.search(r'^'+name+r' .*\.\.\. ok$',log,re.M) for name in methods)
    dev=receipt('native-r2/verification.json');actual=receipt('installed-r2/media/verification.json')
    install=receipt('installed-r2/verification.json')
    for value in (dev,actual,install):
        stable(value);assert value['status']=='passed' and not value['full_capcut_parity'] and not value['goal_complete']
        assert all(c['ok'] for c in value['checks'])
    assert sha(ROOT/'scripts/smoke_contact_sheet.py')[7:]==dev['script_sha256']==actual['script_sha256']
    assert sha(ROOT/'scripts/verify_contact_sheet_install.py')[7:]==install['script_sha256']
    assert install['isolated_cli_calls']==10 and install['module_origin_probes']==1
    assert len(install['calls'])==7 and len(install['checks'])==38
    assert install['bundle']['wheels']==install['installation']['wheels']==7
    assert len(install['resource_hashes'])==144
    package=ROOT/'product/src/ai_ad_editor';installed=Path(install['installation']['target'])/'site/ai_ad_editor'
    def resources(path):return {p.name:sha(p)[7:] for p in path.iterdir() if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
    assert resources(package)==resources(installed)==install['resource_hashes']
    for value in (dev,actual):
        assert value['cli_calls']==7 and len(value['calls'])==9 and len(value['checks'])==35
        assert not value['continuous_playback_reviewed'] and not value['audio_listening_reviewed']
        assert len(value['source_frame_rgba_sha256'])==24
        contact=value['contact_manifest'];frames=contact['frames']
        assert len(frames)==4 and sum(len(x['panels']) for x in frames)==16
        assert [r['requested_seconds'] for r in frames]==[0,.17,.75,1.5]
        assert [r['relative_seconds'] for r in frames]==[0,.25,.75,1.5]
        assert contact['process_cleanup']['all_children_reaped'] and not contact['quality_accepted']
        for row,index in zip(frames,(0,3,9,18)):
            assert row['rgba_sha256'][7:]==value['source_frame_rgba_sha256'][index]
            assert row['alpha_extrema']==[0,255]
        assert contact['contact']['sha256']==dev['contact_manifest']['contact']['sha256']
        assert contact['annotation_font']==dev['contact_manifest']['annotation_font']
        for row in value['public_files']:
            path=ROOT/row['path'];bind(path);assert sha(path)[7:]==row['sha256'] and path.stat().st_size==row['bytes']
    assert dev['source_frame_rgba_sha256']==actual['source_frame_rgba_sha256']
    inventory=receipt('media-inventory-r2.json');stable(inventory)
    assert inventory['status']=='passed' and inventory['public_file_count']==33 and inventory['actual_video_probes']==6
    assert inventory['panels_per_run']==16 and inventory['script_sha256']==sha(ROOT/'scripts/audit_contact_sheet_media.py')
    for row in inventory['files']:
        path=ROOT/row['path'];bind(path);assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
    static=receipt('static-review-r3.json');assert static['reviewed'] and len(static['files'])==2 and static['panels_per_run']==16
    assert not any(static[k] for k in ('continuous_playback_reviewed','audio_listening_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    # Raw failures stay failures; older 19-method passes do not replace 25 current methods.
    assert receipt('focus-r1.json')['exit_code']!=0
    assert receipt('focus-r2.json')['methods']==19
    receipt('clock-r1/verification.json')
    skills=receipt('skills-r1.json');mapping=read(ROOT/'video-cut-install-manifest.json');bind(ROOT/'video-cut-install-manifest.json')
    assert skills['skill_count']==mapping['skill_count']==17 and skills['local_links_checked']==264
    assert mapping['current_audit']['record_sha256']==sha(BASE/'skills-r1.json') and not mapping['current_audit']['candidate']
    for row in skills['results']:
        path=ROOT/'skills'/row['skill']/'SKILL.md';bind(path)
        assert sha(path)==row['sha256'] and row['installed_directory_resolves_to_repo'] and row['validator_exit_code']==0
        assert next(r for r in mapping['skills'] if r['name']==row['skill'])['skill_md_sha256']==row['sha256'][7:]
    for path in [*(ROOT/n for n in DOCUMENTS),REPORT,CONTRACT,ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md']:
        bind(path);text=path.read_text(encoding='utf8')
        marker='V71-MEASURED' if path==REPORT else 'V71-CURRENT'
        if '<!-- '+marker+' -->' in text:text=text.split('<!-- '+marker+' -->',1)[1].split('<!-- /'+marker+' -->',1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',text):
            name=urllib.parse.unquote(raw.split('#',1)[0])
            if name and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',name):assert (path.parent/name).exists(),(path,name)
    for path in BASE.rglob('*'):
        if path.is_file() and path!=output:bind(path)
    for name in ('smoke_contact_sheet','verify_contact_sheet_install','audit_contact_sheet_media',
                 'sync_contact_sheet_documents','audit_contact_sheet_release','publish_contact_sheet','materialize_regression_fixtures','run_with_regression_fixtures','probe_native_job_start'):
        bind(ROOT/'scripts'/(name+'.py'))
    bind(ROOT/'.gitattributes')
    record={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,
        'bound_files':bound,'full_methods':1593,'focused_methods':25,'native_cli_calls':7,'installed_cli_calls':10,
        'installed_module_probes':1,'packaged_resources':144,'wheels':7,'skills':17,'skill_links':264,
        'anchors_per_run':4,'panels_per_run':16,'public_files':33,'actual_video_probes':6,
        'full_suite_location':'isolated branch; all 217 relative-path bytes equal publication workspace',
        'natural_quality_accepted':False,'full_capcut_parity':False,'goal_complete':False,'force_push':False}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','full_methods','packaged_resources','skills','skill_links')}))


if __name__=='__main__':main()
