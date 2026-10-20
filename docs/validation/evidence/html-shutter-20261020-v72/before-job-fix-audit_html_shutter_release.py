"""Bind V72 source, failures, whole-pixel media, fixtures and installed delivery."""
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
from sync_html_shutter_documents import BASE,REPORT,CONTRACT,RESEARCH,DOCUMENTS

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve();assert not output.exists()
    current=frozen();assert len(current)==218;bound={}
    def bind(path):
        assert path.is_file(),path;bound[path.relative_to(ROOT).as_posix()]=sha(path)
    def receipt(name):
        path=BASE/name;bind(path);return read(path)
    def stable(value):assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    full=receipt('full-r1.json');stable(full)
    assert full['status']=='passed' and full['terminal_ok'] and full['exit_code']==0 and full['methods']==1610 and full['skipped']==0
    assert full['external_fixtures_equal'] and full['external_fixture_count']==5 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
    for field,name in [('wrapper_sha256','run_with_regression_fixtures'),('inner_runner_sha256','run_frozen_regression'),('fixture_definition_sha256','materialize_regression_fixtures')]:
        path=ROOT/'scripts'/(name+'.py');bind(path);assert sha(path)==full[field]
    for name,expected in full['external_fixtures_after'].items():
        path=ROOT/name;bind(path);assert path.stat().st_size==expected['bytes'] and sha(path)==expected['sha256']
    assert full['external_fixtures_before']==full['external_fixtures_expected']==full['external_fixtures_after']
    manifest=ROOT/full['external_fixture_manifest'];bind(manifest);assert sha(manifest)==full['external_fixture_manifest_sha256']
    for path in (BASE/'full-r1.log',BASE/'full-r1.source.log',BASE/'full-r1.source.json'):bind(path)
    assert sha(BASE/'full-r1.log')==full['log_sha256']==sha(BASE/'full-r1.source.log')
    source=read(BASE/'full-r1.source.json');assert source['terminal_ok'] and source['methods']==1610
    focus=receipt('focus-r3.json');stable(focus)
    assert focus['terminal_ok'] and focus['methods']==21 and focus['skipped']==0
    methods=[node.name for node in ast.walk(ast.parse((ROOT/'product/tests/test_html_shutter.py').read_text(encoding='utf8')))
             if isinstance(node,ast.FunctionDef) and node.name.startswith('test_')]
    assert len(methods)==21
    raw=(BASE/'full-r1.log').read_text(encoding='utf8');assert all(re.search(r'^'+name+r' .*\.\.\. ok$',raw,re.M) for name in methods)
    dev=receipt('native-r2/verification.json');install=receipt('installed-r1/verification.json');actual=receipt('installed-r1/media/verification.json')
    for value in (dev,install,actual):
        stable(value);assert value['status']=='passed' and not value['full_capcut_parity']
        assert all(item['ok'] for item in value['checks'])
    assert dev['script_sha256']==actual['script_sha256']==sha(ROOT/'scripts/smoke_html_shutter.py')
    assert install['script_sha256']==sha(ROOT/'scripts/verify_html_shutter_install.py')
    assert len(install['resource_hashes'])==145 and install['bundle']['wheels']==install['installation']['wheels']==7
    assert install['isolated_cli_calls']==actual['cli_calls']+3 and install['module_origin_probes']==1
    def resources(path):return {p.name:sha(p) for p in path.iterdir() if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt'}}
    assert resources(ROOT/'product/src/ai_ad_editor')==resources(Path(install['installation']['target'])/'site/ai_ad_editor')==install['resource_hashes']
    for value in (dev,actual):
        assert len(value['renders'])==7 and len(value['checks'])==36
        assert value['cli_calls']==19
        for name,row in value['renders'].items():
            assert len(row['frame_rgba_sha256'])==16 and row['encoded_clock']['frame_count']==16 and row['encoded_clock']['all_frames_exact']
            assert row['cleanup']['all_children_reaped'] and not row['cleanup']['active_after_cleanup']
            assert row['worker_cleanup']['browser_closed'] and row['worker_cleanup']['pages_closed']==3
            if name!='zero':assert row['layout_frame_count']==row['source_capture_count']
        for name,expected in value['independent_reference_rgba_sha256'].items():assert value['renders'][name]['frame_rgba_sha256']==expected
    assert dev['public_files']==actual['public_files']
    assert dev['independent_reference_rgba_sha256']==actual['independent_reference_rgba_sha256']
    for folder,value in [('html-shutter-20261020-v72-native-r2',dev),('html-shutter-20261020-v72-installed-r1',actual)]:
        for name,row in value['public_files'].items():
            path=ROOT/'docs/assets'/folder/name;bind(path);assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
    old=receipt('default-compat-r1/verification.json');stable(old)
    assert old['status']=='passed' and old['isolated_older_cli_calls']==4 and len(old['checks'])==6 and all(x['ok'] for x in old['checks'])
    assert old['frame_rgba_sha256']==dev['renders']['sharp']['frame_rgba_sha256'] and old['container_bytes_identical']
    inventory=receipt('media-inventory-r1.json');stable(inventory)
    assert inventory['status']=='passed' and inventory['actual_video_probes']==14 and inventory['public_file_count']==29
    assert inventory['script_sha256']==sha(ROOT/'scripts/audit_html_shutter_media.py')
    for row in inventory['files']:
        path=ROOT/row['path'];bind(path);assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        if 'probe_path' in row:
            path=ROOT/row['probe_path'];bind(path);assert sha(path)==row['probe_sha256']
    static=receipt('static-review-r1.json')
    assert static['reviewed'] and len(static['files'])==2
    assert not any(static[k] for k in ('continuous_playback_reviewed','audio_listening_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    # Retain failures as failures; only the final complete run supplies acceptance.
    assert receipt('focus-r1.json')['methods']==13
    failed=receipt('focus-r2.json');assert failed['exit_code']!=0 and failed['methods']==20
    failed=receipt('native-r1/verification.json');assert failed['status']=='failed' and failed['frozen_equal']
    assert sha(BASE/'native-r1-executed-smoke.py')==failed['script_sha256']
    positive=receipt('fixture-gate-positive-r1.json');assert positive['terminal_ok'] and positive['methods']==13 and positive['external_fixtures_equal']
    negative=receipt('fixture-gate-negative-r1.json');assert not negative['terminal_ok'] and not negative['suite_launched']
    assert receipt('fixture-gate-negative-checks-r1.json')['status']=='passed'
    research=ROOT/'docs/validation/evidence/openfilm-shutter-20261020-r10/verification.json';bind(research)
    assert read(research)['status']=='passed_research_only'
    skills=receipt('skills-r1.json');assert skills['skill_count']==17 and skills['local_links_checked']==270
    mapping=read(ROOT/'video-cut-install-manifest.json');bind(ROOT/'video-cut-install-manifest.json')
    assert mapping['current_audit']['record_sha256']==sha(BASE/'skills-r1.json') and not mapping['current_audit']['candidate']
    for row in skills['results']:
        path=ROOT/'skills'/row['skill']/'SKILL.md';bind(path)
        assert sha(path)==row['sha256'] and row['installed_directory_resolves_to_repo'] and row['validator_exit_code']==0
        assert next(r for r in mapping['skills'] if r['name']==row['skill'])['skill_md_sha256']==row['sha256'][7:]
    for path in [*(ROOT/name for name in DOCUMENTS),REPORT,CONTRACT,RESEARCH,ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md']:
        bind(path);text=path.read_text(encoding='utf8');marker='V72-MEASURED' if path==REPORT else 'V72-CURRENT'
        if '<!-- '+marker+' -->' in text:text=text.split('<!-- '+marker+' -->',1)[1].split('<!-- /'+marker+' -->',1)[0]
        for raw in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)\)',text):
            name=urllib.parse.unquote(raw.split('#',1)[0])
            if name and not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',name):assert (path.parent/name).exists(),(path,name)
    for path in BASE.rglob('*'):
        if path.is_file() and path!=output:bind(path)
    for path in (ROOT/'docs/validation/evidence/openfilm-shutter-20261020-r10').rglob('*'):
        if path.is_file():bind(path)
    for name in ('smoke_html_shutter','verify_html_shutter_install','audit_html_shutter_media','compare_html_shutter_default',
                 'sync_html_shutter_documents','audit_html_shutter_release','publish_html_shutter','probe_openfilm_shutter',
                 'materialize_regression_fixtures','run_with_regression_fixtures'):bind(ROOT/'scripts'/(name+'.py'))
    bind(ROOT/'.gitattributes')
    record={'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,'bound_files':bound,
            'full_methods':1610,'focused_methods':21,'native_cli_calls':dev['cli_calls'],'native_checks':len(dev['checks']),
            'isolated_cli_calls':install['isolated_cli_calls'],'install_checks':len(install['checks']),'installed_module_probes':1,
            'old_install_cli_calls':4,'packaged_resources':145,'wheels':7,'skills':17,'skill_links':270,
            'public_files':29,'actual_video_probes':14,'external_fixture_count':5,
            'full_suite_location':'isolated branch; all 218 relative-path bytes and 5 external fixtures equal publication workspace',
            'natural_quality_accepted':False,'full_capcut_parity':False,'goal_complete':False,'force_push':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','full_methods','packaged_resources','skills','skill_links')}))


if __name__=='__main__':main()
