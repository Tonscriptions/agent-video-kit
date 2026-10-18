"""Bind current V51 documentation, media, installed package and full regression."""
from __future__ import annotations
import argparse,hashlib,json,re,sys,urllib.parse,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_frozen_regression import frozen
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()

def run(output):
    assert not output.exists()
    evidence=ROOT/'docs/validation/evidence';public=ROOT/'docs/assets/nested-freeze-v51-final-20261018'
    def receipt(name):return json.loads((evidence/name).read_bytes())
    full=receipt('nested-freeze-tests-20261018/full-2.json');targeted=receipt('nested-freeze-tests-20261018/targeted-8.json')
    installed=receipt('nested-freeze-native-install-final-20261018/verification.json');skills=receipt('nested-freeze-skills-final-20261018.json')
    baseline=receipt('nested-freeze-baseline-20261018/verification.json');media=receipt('nested-freeze-real-final-20261018/media-audit.json')
    smoke=json.loads((public/'verification.json').read_bytes());current=frozen()
    assert full['methods']==1161 and full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==targeted['frozen_before']==targeted['frozen_after']==smoke['frozen_before']==smoke['frozen_after']==current
    assert len(current)==172 and targeted['methods']==26 and targeted['terminal_ok']
    assert sha(evidence/'nested-freeze-tests-20261018/full-2.log')==full['log_sha256']
    assert baseline['methods']==26 and len(baseline['failed_methods'])==22 and baseline['control_passed_methods']==4 and not baseline['error_methods']
    assert baseline['same_current_test_sha256']==sha(ROOT/'product/tests/test_nested_freeze.py')
    assert len(smoke['cases'])==9 and smoke['cli_calls']==30 and len(smoke['native_graph_probes'])==2
    assert smoke['final_main_frames']==327 and smoke['final_stereo_sample_frames']==1567101
    assert sum(c['stereo_sample_frames'] for c in smoke['cases'] if c['audio_content_accepted'])==1440000
    assert smoke['status']=='core_passed_delivery_alpha_failed' and not smoke['all_delivery_gates_passed']
    assert smoke['delivery_alpha']['max_alpha_error']==1 and smoke['delivery_alpha']['mismatched_alpha_pixels']==326400 and smoke['delivery_alpha']['threshold_unchanged']==0
    assert installed['status']=='passed' and installed['installed_package_files']==117 and installed['isolated_cli_calls']==9
    assert sum(x['frames'] for x in installed['outputs'])==80 and all(x['rgb_pcm_equal_to_development'] for x in installed['outputs'])
    assert skills['skill_count']==14 and skills['local_links_checked']==182
    assert media['main_frames']==327 and len(media['gifs'])==8
    fractional=receipt('nested-freeze-fractional-delivery-20261018/verification.json')
    assert fractional['frozen_before']==fractional['frozen_after']==current and fractional['cli_calls']==3
    assert fractional['mp4_cli_exit_code']==6 and not fractional['mp4_published']
    assert fractional['mkv_actual_display_frames']==41 and fractional['mkv_actual_stereo_sample_frames']==192480
    assert sha(public/'fractional-root-control.mkv')==fractional['mkv_sha256']
    for name,entry in media['public_files'].items():assert sha(public/name)==entry['sha256'],name
    assert sha(public/'agent-video-kit-cp313-win_amd64.zip')==installed['release_zip_sha256']
    with zipfile.ZipFile(public/'agent-video-kit-cp313-win_amd64.zip') as bundle:
        manifest=json.loads(bundle.read('manifest.json'))
        for entry in manifest['files']:
            raw=bundle.read(entry['path']);assert len(raw)==entry['bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==entry['sha256']
        product=next(row for row in manifest['wheels'] if row['name']=='ai-ad-editor')
        import io
        with zipfile.ZipFile(io.BytesIO(bundle.read(product['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==117
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes(),name
    report='复合片段定格与完整音画时钟实测_2026-10-18.md'
    docs=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/validation/'+report,
        'docs/specs/复合片段定格与完整音画时钟契约_v0.1_2026-10-18.md','docs/specs/嵌套转场合成与作者时钟契约_v0.1_2026-10-18.md',
        'docs/OpenFilm当前复用决策_2026-10-18.md']
    links=0;document_hashes={}
    for name in docs:
        p=ROOT/name;t=p.read_text(encoding='utf-8-sig');assert 'V51_FULL_SUITE_PENDING' not in t and 'V51_INSTALL_PENDING' not in t and 'V51_REVIEW_PENDING' not in t
        document_hashes[name]=sha(p)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',t):
            target=raw.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            assert (p.parent/urllib.parse.unquote(target)).resolve().exists(),(name,target)
            links+=1
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert '| V51 |' in readme and '最近 V51 完整' in readme and 'nested-freeze-v51-final-20261018/NF06.gif' in readme
    manifest=json.loads((ROOT/'video-cut-install-manifest.json').read_bytes())
    assert manifest['current_audit']['record_sha256']==sha(evidence/'nested-freeze-skills-final-20261018.json')
    for row in manifest['skills']:
        p=Path(row['canonical_directory']);assert row['skill_md_sha256']==sha(p/'SKILL.md').split(':',1)[1]
        assert (Path(row['registration_directory'])).resolve()==p.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    value={'status':'passed_scoped_release_audit','full_methods':1161,'full_suite_seconds':full['suite_seconds'],'frozen_files':len(current),
        'new_targeted_methods_subset':26,'baseline_failed_methods':22,'baseline_control_passes':4,'main_frames':327,
        'main_stereo_sample_frames':1567101,'audio_content_reference_sample_frames':1440000,'development_cli_calls':30,
        'native_graph_precision_probes':2,'extra_fractional_gate_cli_calls':3,'extra_fractional_control_frames':41,
        'fractional_mp4_delivery_gate_passed':False,'installed_package_files':117,'isolated_installed_cli_calls':9,'installed_frames':80,
        'skills':14,'skill_local_links':182,'documents_checked':len(docs),'document_local_links':links,'broken_links':0,
        'document_hashes':document_hashes,'delivery_exact_alpha_passed':False,'all_capcut_features_and_quality_accepted':False,
        'public_media_audit_sha256':sha(evidence/'nested-freeze-real-final-20261018/media-audit.json'),'generator_sha256':sha(Path(__file__))}
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:value[k] for k in ['status','full_methods','frozen_files','documents_checked','document_local_links','broken_links']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
