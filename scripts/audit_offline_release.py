"""Close V47 evidence, docs, wheel/license/skill integrity and native proofs."""
from __future__ import annotations
import argparse,ast,hashlib,json,re,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads((ROOT/path).read_bytes())


def run(output):
    assert not output.exists();output.parent.mkdir(parents=True,exist_ok=True)
    full=read('docs/validation/evidence/offline-release-tests-20261018/full.json')
    assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['methods']==1084
    assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']
    assert len(full['frozen_after'])==160 and all(sha(ROOT/name)==digest for name,digest in full['frozen_after'].items())
    assert sha(ROOT/'docs/validation/evidence/offline-release-tests-20261018/full.log')==full['log_sha256']
    real=read('docs/validation/evidence/offline-release-final-real-20261018/verification.json')
    assert real['status']=='passed' and real['frozen_before']==full['frozen_after']==real['frozen_after']
    assert real['packaged_source_files']==108 and real['guarded_native_cli_calls']==22 and real['process_calls']==29
    assert real['encoded_primary_frames']==90 and real['new_stereo_sample_frames']==432000
    assert real['nonperiodic_audio_distinguishes_slip'] and real['package_roundtrip_rgb_exact'] and real['package_roundtrip_pcm_exact']
    assert real['comparisons'][0]['pcm_sha256']!=real['comparisons'][1]['pcm_sha256']
    assert all(row['independent_pcm_max_difference']==0 and row['rgb_max_difference']==1 for row in real['comparisons'])
    assert real['static_review']['reviewed'] and not real['continuous_playback_review'] and not real['listening_review']
    public=ROOT/'docs/assets/offline-release-final-20261018'
    for name,row in real['public_files'].items():assert (public/name).stat().st_size==row['bytes'] and sha(public/name)==row['sha256'],name
    assert set(real['public_files'])=={p.relative_to(public).as_posix() for p in public.rglob('*') if p.is_file()}
    # Check decoded stream counts and separate audio/video/GIF evidence.
    probes=read('docs/validation/evidence/offline-release-final-real-20261018/media-probes.json')
    for name in ('before.mkv','after.mkv','restored.mkv','before.mp4','after.mp4','restored.mp4'):
        video=next(s for s in probes[name]['streams'] if s['codec_type']=='video')
        assert (int(video['width']),int(video['height']),int(video['nb_read_frames']),video['r_frame_rate'])==(240,136,30,'10/1'),name
        assert any(s['codec_type']=='audio' and s['sample_rate']=='48000' and s['channels']==2 for s in probes[name]['streams']),name
    gif=probes['comparison.gif']['streams'];assert len(gif)==1 and (gif[0]['width'],gif[0]['height'],int(gif[0]['nb_read_frames']))==(480,136,30)
    native=read('docs/validation/evidence/offline-release-final-real-20261018/powershell-launcher.json')
    assert native['exit_code']==0 and native['extra_native_process_calls']==1
    assert json.loads(native['stdout'])['data']['schema_validation']['ok']
    assert native['generator_sha256']==sha(ROOT/'scripts/verify_offline_native_entries.py')
    boundaries=read('docs/validation/evidence/offline-release-final-real-20261018/native-path-boundaries.json')
    assert boundaries['status']=='passed' and boundaries['extra_native_process_calls']==3 and boundaries['no_install_targets_created']
    assert boundaries['generator_sha256']==sha(ROOT/'scripts/verify_offline_native_entries.py')
    assert {row['name'] for row in boundaries['cases']}=={'unc-bundle','unc-target','uri-cancel'}
    assert all(row['exit_code']==2 and row['stdout']['code']=='NETWORK_PATH_FORBIDDEN' for row in boundaries['cases'])
    release=read('docs/assets/offline-release-final-20261018/release-manifest.json')
    assert sha(public/'release-manifest.json')==real['bundle']['manifest_sha256']
    with zipfile.ZipFile(public/'agent-video-kit-cp313-win_amd64.zip') as archive:
        assert archive.read('manifest.json')==(public/'release-manifest.json').read_bytes()
        inventory={x['path']:x for x in release['files']};assert set(archive.namelist())==set(inventory)|{'manifest.json'}
        for name,row in inventory.items():
            data=archive.read(name);assert len(data)==row['bytes'] and 'sha256:'+hashlib.sha256(data).hexdigest()==row['sha256'],name
        own=next(x for x in release['wheels'] if x['name']=='ai-ad-editor')
        import io
        with zipfile.ZipFile(io.BytesIO(archive.read(own['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/')]
            assert len(names)==108
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes(),name
        assert any(n.startswith('licenses/jsonschema/') for n in inventory)
        assert any(n.startswith('licenses/rpds-py/') for n in inventory)
    dependency=read('sources/python-runtime/cp313-win_amd64/lock.json')
    assert len(dependency['artifacts'])==6 and sum(x['bytes'] for x in dependency['artifacts'])==426392
    for item in dependency['artifacts']:
        path=ROOT/'sources/python-runtime/cp313-win_amd64'/item['filename'];assert path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
    adoption=read('docs/validation/evidence/offline-dependency-acquisition-20261018/adoption.json')
    upstream=ROOT/'docs/validation/evidence/offline-dependency-acquisition-20261018/rfc3339_validator.upstream.py'
    adapted=ROOT/'product/src/ai_ad_editor/rfc3339_dates.py';license_path=ROOT/'product/src/ai_ad_editor/RFC3339_VALIDATOR_LICENSE.txt'
    assert sha(upstream)==adoption['upstream_module_sha256'] and sha(adapted)==adoption['adopted_module_sha256'] and sha(license_path)==adoption['license_sha256']
    function=lambda path:next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n,ast.FunctionDef) and n.name=='validate_rfc3339')
    assert ast.dump(function(upstream),include_attributes=False)==ast.dump(function(adapted),include_attributes=False)
    canonical=ROOT/'docs/specs/agent-project.schema.json';assert canonical.read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
    assert sha(canonical)==release['schema_sha256']==adoption['bundled_schema_sha256']
    baseline=read('docs/validation/evidence/schema-release-corrected-baseline-20261018.json')
    assert baseline['status']=='verified' and baseline['field']=='project.created_at' and baseline['old_source']['exit_code']==0 and baseline['current_source']['exit_code']==2
    candidate=read('docs/validation/evidence/offline-release-real-dev1-20261018/verification.json')
    assert candidate['comparisons'][0]['pcm_sha256']==candidate['comparisons'][1]['pcm_sha256']
    assert sha(ROOT/'docs/validation/evidence/offline-release-real-dev1-20261018/smoke_offline_release.original.py')==candidate['generator_sha256']
    failed_log=(ROOT/'docs/validation/evidence/offline-release-tests-20261018/offline-schema-targeted-dev1-20261018.log').read_text(encoding='utf-8')
    assert 'FAILED (failures=5, errors=2)' in failed_log
    skills=read('docs/validation/evidence/offline-release-skills-20261018.json');manifest=read('video-cut-install-manifest.json')
    assert skills['skill_count']==manifest['skill_count']==14 and skills['local_links_checked']==162
    assert manifest['current_audit']['record_sha256']==sha(ROOT/'docs/validation/evidence/offline-release-skills-20261018.json')
    for row in manifest['skills']:assert sha(ROOT/'skills'/row['name']/'SKILL.md')=='sha256:'+row['skill_md_sha256']
    openfilm=read('docs/validation/evidence/openfilm-release-review-20261018/verification.json')
    assert openfilm['status']=='verified' and openfilm['actual_head']==openfilm['fixed_head'] and openfilm['upstream_files_checked']==702 and len(openfilm['adoptions'])==5
    mapping=read('docs/validation/evidence/openfilm-skill-local-mapping-20261018.json')
    assert mapping['status']=='static_mapping_verified' and mapping['source_commit']==openfilm['fixed_head']
    assert mapping['upstream_skills_checked']==len(mapping['rows'])==10 and mapping['dispatch_names_checked']==93
    assert mapping['current_cli_source_sha256']==sha(ROOT/'product/src/ai_ad_editor/cli.py')
    assert mapping['generator_sha256']==sha(ROOT/'scripts/map_openfilm_skills.py')
    archive_path=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip';assert mapping['archive_sha256']==sha(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        for row in mapping['rows']:
            names=[name for name in archive.namelist() if name.endswith('/'+row['source_path'])];assert len(names)==1
            data=archive.read(names[0]);assert 'sha256:'+hashlib.sha256(data).hexdigest()==row['source_sha256'] and len(data.splitlines())==row['source_lines']
            assert not row['new_skill_installed'] and not row['workflow_executed_this_research']
    examples_base=ROOT/'docs/validation/evidence/openfilm-examples-review-final-20261018'
    examples=read(examples_base/'verification.json')
    assert examples['status']=='read_only_inventory_verified' and examples['main_repository_file_count']==702
    assert examples['main_source_archive_sha256']==sha(archive_path) and examples['examples_tree_blobs']==402
    assert len(examples['main_repository_media'])==18 and len(examples['examples_media_inventory'])==222
    assert sum(row['bytes'] for row in examples['examples_media_inventory'])==224900384
    assert examples['media_files_downloaded']==examples['examples_rendered']==examples['new_model_inference']==0
    assert examples['generator_sha256']==sha(ROOT/'scripts/review_openfilm_examples.py')
    for name,row in examples['requests'].items():assert (examples_base/name).stat().st_size==row['bytes'] and sha(examples_base/name)==row['sha256']
    for name in examples['selected_text_sources']:
        blob=read(examples_base/(name.replace('/','__')+'.blob.raw.json'));raw=(examples_base/(name.replace('/','__')+'.raw.txt')).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==blob['sha']
    engine=read(examples_base/'px/verification.json')
    assert len(engine['sources'])==8 and not engine['code_adopted'] and not engine['engine_executed']
    assert engine['examples_commit']==examples['examples_commit'] and engine['generator_sha256']==sha(ROOT/'scripts/review_openfilm_example_engine.py')
    for row in engine['sources']:
        local=examples_base/'px'/Path(row['path']).name;assert local.stat().st_size==row['bytes'] and sha(local)==row['sha256']
        raw=local.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['git_blob_sha']
    pre_path=read('docs/validation/evidence/offline-release-tests-20261018/pre-path-full.json')
    assert pre_path['terminal_ok'] and pre_path['methods']==1081 and pre_path['frozen_after']!=full['frozen_after']
    interrupted=read('docs/validation/evidence/offline-release-tests-20261018/interrupted-pathguard-full.json')
    assert not interrupted.get('terminal_ok',False)
    # Local Markdown path audit; preserve historical records, skip fenced examples.
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))];links=0
    for document in documents:
        text=document.read_text(encoding='utf-8-sig');text=re.sub(r'^\s*```.*?^\s*```[^\n]*','',text,flags=re.M|re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            assert (document.parent/urllib.parse.unquote(target)).resolve().exists(),(document,target);links+=1
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert '| V47 |' in readme and '22 隔离 CLI' in readme and '1084/1084' in readme and 'OpenFilm官方Skill本地能力映射' in readme
    for name in ('docs/构建进度总表_2026-10-16.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
        text=(ROOT/name).read_text(encoding='utf-8');assert '**V47（产品）**' in text and '1084/1084' in text
    progress=(ROOT/'docs/构建进度总表_2026-10-16.md').read_text(encoding='utf-8')
    assert '| 本次状态快照 | 2026-10-18，README V47' in progress and '14 项格式/联接/162 引用通过' in progress
    output.write_text(json.dumps({'status':'passed','checked_at_utc':datetime.now(timezone.utc).isoformat(),'methods':1084,'frozen_files':160,'packaged_source_files':108,'public_files_checked':len(real['public_files']),'public_bytes_checked':sum(x['bytes'] for x in real['public_files'].values()),'documents_checked':len(documents),'local_links_checked':links,'skill_count':14,'skill_links':162,'openfilm_fixed_commit':openfilm['fixed_head'],'new_upstream_code':False,'main_guarded_cli_calls':22,'main_process_calls':29,'additional_powershell_entry_calls':1,'encoded_primary_frames':90,'new_stereo_sample_frames':432000,'source_schema_and_vendor_license_pinned':True,'candidate_weak_observation_and_failed_schema_tests_retained':True,'continuous_playback_review':False,'listening_review':False,'other_machine_accepted':False,'generator_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'status':'passed','documents':len(documents),'links':links,'package_files':108,'methods':1084},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();run(args.output.resolve())
