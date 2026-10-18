"""Audit current V45 docs, byte-frozen product checks and public demo evidence."""
from __future__ import annotations
import argparse,ast,hashlib,json,re,sys,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
from smoke_fragments import frozen,save,sha
from finalize_html_template import CORE,CONTRACT,REPORT


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def run(output):
    from PIL import Image,ImageSequence
    assert not output.exists();save(output,{'status':'checking'})
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
    local=external=anchors=0;broken=[]
    for path in documents:
        text=path.read_text(encoding='utf-8-sig');assert text.strip(),path
        text=re.sub(r'^\s*```.*?^\s*```[^\n]*','',text,flags=re.M|re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) and not re.match(r'^[A-Za-z]:[/\\]',target):external+=1;continue
            target=target.split('#',1)[0]
            if not target:anchors+=1;continue
            local+=1
            if not (path.parent/urllib.parse.unquote(target)).resolve().exists():broken.append({'file':str(path),'target':raw})
    assert not broken,broken
    readme=(ROOT/'README.md').read_text(encoding='utf-8-sig')
    assert list(map(int,re.findall(r'^\| V(\d{2}) \|',readme,re.M)))==list(range(1,46))
    assert readme.index('V45（产品）')<readme.index('V44（研究）')<readme.index('V43（产品）')
    current_status=readme.split('## 当前状态',1)[1].split('\n-',2)[1]
    assert '最近产品 V45' in current_status and '1025/1025' in current_status
    assert '下一个可复用范围是离线模板变量' not in readme
    reuse=(ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md').read_text(encoding='utf-8')
    assert '**V45 已接入受控子集**' in reuse and 'V45 HTML 模板控件受控接入' in reuse
    for file in CORE:
        text=(ROOT/file).read_text(encoding='utf-8-sig')
        for term in ('V45（产品）','1025/1025','146 文件（含测试）','20 新增专项','26 CLI / 72 编码帧','100 包内文件 / 11 独立进程 CLI','14 Skills / 150 引用','未验收','FGT'):
            assert term in text,(file,term)
    current=frozen();assert len(current)==146
    full=load(ROOT/'docs/validation/evidence/html-template-tests-20261018/full.json')
    assert full['frozen_before']==full['frozen_after']==current and full['frozen_equal']
    assert full['methods']==1025 and full['skipped']==0 and full['exit_code']==0 and full['terminal_ok']
    assert full['log_sha256']==sha(ROOT/'docs/validation/evidence/html-template-tests-20261018/full.log')
    tree=ast.parse((ROOT/'product/tests/test_html_template.py').read_text(encoding='utf-8'))
    new_tests=sum(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name.startswith('test_') for x in ast.walk(tree))
    assert new_tests==20
    old=load(ROOT/'docs/validation/evidence/mask-edits-20261018/verification.json');assert old['full']['methods']==1005
    assert full['methods']-old['full']['methods']==new_tests
    primary=load(ROOT/'docs/validation/evidence/html-template-20261018/verification.json')
    assert primary['frozen_before']==primary['frozen_after']==current and primary['frozen_equal'] and primary['status']=='passed'
    assert primary['actual_cli_calls']==26 and primary['html_renders']==6 and primary['encoded_html_frames']==72
    assert primary['additional_order_redraws']==144 and primary['inspection_frames']==2 and primary['model_inference_calls']==0
    assert primary['independent_brand_pixels']==17280 and primary['independent_opaque_image_pixels']==84924
    for key in ('source_zip_unchanged','inherit_rgba_equal','reset_original_rgba_equal','package_rebuild_rgba_equal','fragment_rebuild_rgba_equal'):assert primary[key],key
    assert len(primary['media'])==23
    media_root=ROOT/'docs/assets/html-template-20261018'
    for name,item in primary['media'].items():
        path=media_root/name;assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],name
    assert primary['generator_sha256']==sha(ROOT/'scripts/smoke_html_template.py')
    publication=load(ROOT/'docs/validation/evidence/html-template-20261018/media-publication.json')
    assert primary['media_publication_sha256']==sha(ROOT/'docs/validation/evidence/html-template-20261018/media-publication.json')
    assert publication['generator_sha256']==sha(ROOT/'scripts/publish_html_template_media.py')
    assert publication['source_frozen_equal'] and not publication['page_or_model_rerun']
    assert len(publication['videos'])==4 and all(x['lossless_decoded_rgb_exact'] for x in publication['videos'])
    with Image.open(media_root/'comparison.gif') as gif:
        assert gif.size==(768,144) and gif.n_frames==12
        assert sum(frame.info.get('duration',0) for frame in ImageSequence.Iterator(gif))==2000
    opened=closed=0
    for item in primary['browser_reports']:
        assert item['cleanup']['all_children_reaped'] and item['cleanup']['active_after_cleanup']==[]
        if item['worker']:
            assert item['worker']['browser_closed'] and not item['worker']['denied_requests']
            opened+=item['worker']['pages_opened'];closed+=item['worker']['pages_closed']
    assert opened==closed==21,(opened,closed)
    adopted=load(ROOT/'docs/validation/evidence/openfilm-template-adoption-20261018-e2/verification.json')
    archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip';assert sha(archive)==adopted['archive_sha256']
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if n.endswith('/packages/openfilm/src/overrides.mjs')];assert len(names)==1
        assert z.read(names[0])==(ROOT/'product/src/ai_ad_editor/openfilm_overrides.mjs').read_bytes()
        review=load(ROOT/'docs/validation/evidence/openfilm-template-current-20261018/diagnostics-source-review.json')
        assert review['status']=='selected_source_review_only' and not review['new_runtime_execution']
        assert review['archive_sha256']==sha(archive) and len(review['files'])==3
        for name,item in review['files'].items():
            original=z.read(next(n for n in z.namelist() if n.endswith('/packages/'+name)))
            assert len(original)==item['bytes'] and 'sha256:'+hashlib.sha256(original).hexdigest()==item['sha256']
    for name,item in adopted['adopted'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==item['sha256']
    assert sha(ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt')==adopted['license_sha256']
    wheel=load(ROOT/'docs/validation/evidence/html-template-wheel-20261018/verification.json')
    assert wheel['frozen_before']==wheel['frozen_after']==current and wheel['package_file_count']==100 and wheel['fresh_process_cli_calls']==11
    assert wheel['host_optional_numpy_pillow_torch_blocked'] and wheel['host_socket_network_blocked']
    for name,item in wheel['package_files'].items():assert sha(ROOT/'product/src'/name)==item['sha256'],name
    skills=load(ROOT/'docs/validation/evidence/html-template-skills-20261018.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==150
    for item in skills['results']:
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md')==item['sha256'] and item['installed_directory_resolves_to_repo']
    manifest=load(ROOT/'video-cut-install-manifest.json')
    assert manifest['current_audit']['record_sha256']==sha(ROOT/'docs/validation/evidence/html-template-skills-20261018.json')
    assert any(x['record'].endswith('fgt-temporal-skills-20261018.json') for x in manifest['audit_history'])
    for item in manifest['skills']:assert sha(ROOT/'skills'/item['name']/'SKILL.md')=='sha256:'+item['skill_md_sha256']
    source_ref=load(ROOT/'docs/validation/evidence/openfilm-template-current-20261018/verification.json')
    assert source_ref['status']=='source_ref_verified' and source_ref['source_main_unchanged'] and not source_ref['current_stars_verified']
    assert source_ref['adopted_commit']==adopted['commit'] and not source_ref['new_full_tree_audit']
    tests=ROOT/'docs/validation/evidence/html-template-tests-20261018'
    assert not load(tests/'dev3.json')['frozen_equal']
    aborted=load(tests/'full-aborted.json')
    assert aborted['status']=='explicitly_aborted_after_known_failure' and aborted['frozen_equal_before_fix']
    assert not aborted['terminal_pass_claimed'] and aborted['all_captured_processes_exited']
    assert load(tests/'background-policy-reproduction.json')['status']=='failed'
    assert load(ROOT/'docs/validation/evidence/html-template-initial-20261018/terminal.json')['status']=='failed'
    text=(ROOT/REPORT).read_text(encoding='utf-8');assert all('| T'+str(i).zfill(2)+' |' in text for i in range(1,11))
    scripts=[p for p in (ROOT/'scripts').glob('*html_template*.py')]+[ROOT/'scripts/adopt_openfilm_template_controls.py']
    for path in scripts:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    tracked_docs=[ROOT/x for x in CORE]+[ROOT/REPORT,ROOT/CONTRACT,ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md',
        ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md',ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md']
    save(output,{'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'markdown_files':len(documents),
        'local_links':local,'external_links_not_fetched':external,'anchor_only_links':anchors,'broken_links':[],
        'readme_verification_rows':45,'current_frozen_file_count':146,'full_product_methods':1025,'new_methods_subset':20,
        'fixture_cli_calls':26,'wheel_fresh_process_clis':11,'fixture_browser_pages_opened_and_closed':21,
        'skills':14,'skill_links':150,'documents':{p.relative_to(ROOT).as_posix():sha(p) for p in tracked_docs},
        'scripts':{p.relative_to(ROOT).as_posix():sha(p) for p in scripts},'product_and_test_sha256':current,
        'support_evidence':{p.relative_to(ROOT).as_posix():sha(p) for folder in ('html-template-20261018','html-template-tests-20261018','html-template-wheel-20261018','openfilm-template-adoption-20261018-e2','openfilm-template-current-20261018')
            for p in sorted((ROOT/'docs/validation/evidence'/folder).rglob('*')) if p.is_file()},
        'whole_capcut_parity_accepted':False,'natural_fgt_quality_accepted':False,'continuous_playback_accepted':False})
    print(json.dumps({'markdown_files':len(documents),'local_links':local,'broken_links':0,'readme_rows':45}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.output.resolve())
