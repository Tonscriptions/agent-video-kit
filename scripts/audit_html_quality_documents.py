"""Check V46 documentation, exact frozen checks, source adoption and media."""
from __future__ import annotations
import argparse,ast,hashlib,json,re,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path
from smoke_fragments import frozen,save,sha
from finalize_html_quality import CORE,CONTRACT,REPORT

ROOT=Path(__file__).resolve().parents[1]
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def run(output):
    from PIL import Image,ImageSequence
    from fontTools.ttLib import TTFont
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
    assert list(map(int,re.findall(r'^\| V(\d{2}) \|',readme,re.M)))==list(range(1,47))
    assert readme.index('V46（产品）')<readme.index('V45（产品）')<readme.index('V44（研究）')
    status=readme.split('## 当前状态',1)[1].split('\n-',2)[1]
    assert '最近产品 V46' in status and '1051/1051' in status
    for file in CORE:
        text=(ROOT/file).read_text(encoding='utf-8-sig')
        for term in ('V46（产品）','1051/1051','152 文件（含测试）','26 新增专项','26 CLI / 60 编码帧',
                     '104 包内文件 / 14 独立进程 CLI','14 Skills / 156 引用','未验收','FGT'):
            assert term in text,(file,term)
    current=frozen();assert len(current)==152
    full=load(ROOT/'docs/validation/evidence/html-quality-tests-20261018/full.json')
    assert full['frozen_before']==full['frozen_after']==current and full['frozen_equal']
    assert full['methods']==1051 and full['skipped']==0 and full['exit_code']==0 and full['terminal_ok']
    assert full['log_sha256']==sha(ROOT/'docs/validation/evidence/html-quality-tests-20261018/full.log')
    tests={}
    for file in ('test_font_coverage.py','test_html_quality.py'):
        tree=ast.parse((ROOT/'product/tests'/file).read_text(encoding='utf-8'))
        tests[file]=sum(isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name.startswith('test_') for x in ast.walk(tree))
    assert tests=={'test_font_coverage.py':13,'test_html_quality.py':13}
    old=load(ROOT/'docs/validation/evidence/html-template-tests-20261018/full.json')
    assert full['methods']-old['methods']==sum(tests.values())==26
    primary=load(ROOT/'docs/validation/evidence/html-quality-20261018/verification.json')
    assert primary['frozen_before']==primary['frozen_after']==current and primary['frozen_equal'] and primary['status']=='passed'
    assert primary['cli_calls']==26 and primary['html_renders']==5 and primary['encoded_html_frames']==60
    assert primary['render_extra_order_redraws']==120 and primary['quality_jobs']==9 and primary['quality_frames']==108 and primary['quality_reverse_redraws']==108
    assert primary['independent_fonttools_character_checks']==120 and primary['new_model_inference_calls']==0
    assert primary['rights_gate_status']=='failed' and not primary['legacy_pixels_published']
    for key in ('strict_rejections_preserve_project_ledger_assets','strict_rebuild_inherited_and_new_gate','package_rgba_exact'):assert primary[key],key
    media_root=ROOT/'docs/assets/html-quality-20261018';assert len(primary['media'])==40
    for name,item in primary['media'].items():
        path=media_root/name;assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],name
    assert primary['generator_sha256']==sha(ROOT/'scripts/smoke_html_quality.py')
    assert primary['manual_static_review']['status']=='reviewed' and primary['manual_static_review']['contact_sha256']==sha(media_root/'contact.png')
    assert not primary['continuous_playback_accepted'] and not primary['audio_fixture'] and not primary['capcut_parity_accepted']
    with Image.open(media_root/'comparison.gif') as gif:
        assert gif.size==(768,144) and gif.n_frames==12
        assert sum(frame.info.get('duration',0) for frame in ImageSequence.Iterator(gif))==2000
    for probe in primary['probes'].values():
        videos=[s for s in probe['streams'] if s['codec_type']=='video']
        assert len(videos)==1 and int(videos[0]['nb_read_frames'])==12 and videos[0]['r_frame_rate']=='6/1'
        assert videos[0]['pix_fmt']=='yuv420p' and float(probe['format']['duration'])==2
        assert not any(s['codec_type']=='audio' for s in probe['streams'])
    legacy=TTFont(media_root/'inputs/legacy-font.ttf').getBestCmap();complete=TTFont(media_root/'inputs/complete-font.ttf').getBestCmap()
    assert 79 not in legacy and 79 in complete
    assert (media_root/'inputs/legacy-font.ttf').read_bytes()==(ROOT/'docs/assets/html-template-20261018/template/font.ttf').read_bytes()
    opened=closed=0
    for item in primary['browser_reports']:
        assert item['cleanup']['all_children_reaped'] and not item['cleanup']['active_after_cleanup']
        assert item['worker']['browser_closed'] and not item['worker']['denied_requests']
        opened+=item['worker']['pages_opened'];closed+=item['worker']['pages_closed']
    assert opened==closed==33
    evidence=ROOT/'docs/validation/evidence/html-quality-20261018'
    outside=load(evidence/'outside-quality.json');clip=load(evidence/'clip-quality.json');missing=load(evidence/'legacy-font-quality.json')
    assert outside['validation_complete'] and outside['all_frame_orders_equal']
    assert {x['frame'] for x in outside['issues'] if x['code']=='TEXT_OUTSIDE_FRAME'}=={9,10,11}
    assert all(not any(x['sel']=='#title' for x in outside['frames'][i]['layout']['upstream_partial_clipping']) for i in (9,10,11))
    assert all(x['axes']==['x'] for x in clip['issues']) and {x['frame'] for x in clip['issues']}==set(range(12))
    assert {x['frame'] for x in missing['issues'] if x['code']=='FONT_GLYPH_MISSING'}==set(range(6))
    assert load(evidence/'fixed-quality.json')['quality_passed']
    adopted=load(ROOT/'docs/validation/evidence/openfilm-layout-adoption-20261018/verification.json')
    archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip';assert sha(archive)==adopted['archive_sha256']
    selected=(ROOT/'docs/validation/evidence/openfilm-layout-adoption-20261018/cutText.upstream.txt').read_bytes()
    actual=ROOT/'product/src/ai_ad_editor/openfilm_text_bounds.mjs'
    assert len(selected.splitlines())==38 and sha(actual)==adopted['adopted_sha256'] and actual.stat().st_size==2262
    assert selected in actual.read_bytes() and 'sha256:'+hashlib.sha256(selected).hexdigest()==adopted['selected_function_sha256']
    with zipfile.ZipFile(archive) as z:
        original=z.read(adopted['source_member']);assert selected in original
        assert 'sha256:'+hashlib.sha256(original).hexdigest()==adopted['source_sha256']
        license_bytes=z.read(next(n for n in z.namelist() if n.count('/')==1 and n.endswith('/LICENSE')))
        assert license_bytes==(ROOT/'product/src/ai_ad_editor/OPENFILM_LICENSE.txt').read_bytes()
    wheel=load(ROOT/'docs/validation/evidence/html-quality-wheel-20261018/verification.json')
    assert wheel['frozen_before']==wheel['frozen_after']==current and wheel['package_file_count']==104 and wheel['fresh_process_cli_calls']==14
    assert wheel['host_optional_numpy_pillow_torch_blocked'] and wheel['host_socket_network_blocked']
    assert wheel['strict_inherited_and_rerun'] and wheel['strict_rejected_evidence_survives'] and wheel['idempotent_replay']
    for name,item in wheel['package_files'].items():assert sha(ROOT/'product/src'/name)==item['sha256'],name
    assert sum(r['worker']['pages_opened'] for r in wheel['browser_reports'])==sum(r['worker']['pages_closed'] for r in wheel['browser_reports'])==14
    skills=load(ROOT/'docs/validation/evidence/html-quality-skills-20261018.json')
    assert skills['skill_count']==14 and skills['local_links_checked']==156
    for item in skills['results']:
        assert sha(ROOT/'skills'/item['skill']/'SKILL.md')==item['sha256'] and item['installed_directory_resolves_to_repo']
    manifest=load(ROOT/'video-cut-install-manifest.json')
    assert manifest['current_audit']['record_sha256']==sha(ROOT/'docs/validation/evidence/html-quality-skills-20261018.json')
    assert any(x['record'].endswith('html-template-skills-20261018.json') for x in manifest['audit_history'])
    for item in manifest['skills']:assert sha(ROOT/'skills'/item['name']/'SKILL.md')=='sha256:'+item['skill_md_sha256']
    for folder,count in [('html-quality-initial-20261018',18),('html-quality-argument-failure-20261018',20)]:
        failed=load(ROOT/'docs/validation/evidence'/folder/'terminal.json')
        assert failed['status']=='failed' and not failed['terminal_pass_claimed']
        assert len(list((ROOT/'docs/validation/evidence'/folder/'cli').glob('*.json')))==count
    report=(ROOT/REPORT).read_text(encoding='utf-8')
    assert all('| T'+str(i).zfill(2)+' |' in report for i in range(1,11)) and '--output' in report
    reuse=(ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md').read_text(encoding='utf-8')
    assert '**当前结论（V46）**' in reuse and 'V46 全帧布局与字体映射受控接入' in reuse
    scripts=list((ROOT/'scripts').glob('*html_quality*.py'))
    for path in scripts:ast.parse(path.read_text(encoding='utf-8'),filename=str(path))
    tracked=[ROOT/x for x in CORE]+[ROOT/REPORT,ROOT/CONTRACT,ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md',
        ROOT/'docs/third-party/OpenFilm复用声明_2026-10-17.md',ROOT/'docs/specs/AgentCLI契约_v0.1_2026-10-13.md']
    save(output,{'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'markdown_files':len(documents),
        'local_links':local,'external_links_not_fetched':external,'anchor_only_links':anchors,'broken_links':[],
        'readme_verification_rows':46,'current_frozen_file_count':152,'full_product_methods':1051,'new_methods_subset':26,
        'fixture_cli_calls':26,'wheel_fresh_process_clis':14,'fixture_browser_pages_opened_and_closed':33,'wheel_browser_pages_opened_and_closed':14,
        'skills':14,'skill_links':156,'documents':{p.relative_to(ROOT).as_posix():sha(p) for p in tracked},
        'scripts':{p.relative_to(ROOT).as_posix():sha(p) for p in scripts},'product_and_test_sha256':current,
        'support_evidence':{p.relative_to(ROOT).as_posix():sha(p) for folder in ('html-quality-20261018','html-quality-tests-20261018',
            'html-quality-wheel-20261018','html-quality-initial-20261018','html-quality-argument-failure-20261018','openfilm-layout-adoption-20261018')
            for p in sorted((ROOT/'docs/validation/evidence'/folder).rglob('*')) if p.is_file()},
        'whole_capcut_parity_accepted':False,'natural_fgt_quality_accepted':False,'continuous_playback_accepted':False})
    print(json.dumps({'markdown_files':len(documents),'local_links':local,'broken_links':0,'readme_rows':46}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();run(args.output.resolve())
