"""Verify CTC evidence, final wheel bytes and honest current documentation."""
import argparse,hashlib,io,json,re,urllib.parse,zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence'
PUBLIC=ROOT/'docs/assets/ctc-alignment-20261018'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):return json.loads(path.read_bytes())


def run(output):
    assert not output.exists()
    full_path=EVIDENCE/'ctc-tests-20261018/full-2.json'
    full=read(full_path)
    assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['frozen_equal']
    assert full['methods']==1135 and len(full['frozen_after'])==170
    assert full['frozen_before']==full['frozen_after']
    assert all(sha(ROOT/name)==digest for name,digest in full['frozen_after'].items())
    assert full['log_sha256']==sha(full_path.with_suffix('.log'))
    changes={'product/offline/build.py','product/offline/install.py',
             'product/pyproject.toml','product/tests/test_offline_install.py'}
    model_runs=[];states={}
    for language,cli,workers,forwards in [('en',15,3,5),('zh',12,2,3)]:
        folder=EVIDENCE/f'ctc-real-{language}-20261018-b'
        state=read(folder/'state.json');states[language]=state
        assert state['status']=='verified' and state['frozen_equal']
        assert state['generator_sha256'].removeprefix('sha256:')==sha(ROOT/'scripts/smoke_ctc_alignment.py').removeprefix('sha256:')
        assert state['frozen_before']==state['frozen_after']
        assert set(state['frozen_after'])==set(full['frozen_after'])
        actual_changes={name for name,digest in state['frozen_after'].items() if full['frozen_after'][name]!=digest}
        assert actual_changes==changes,actual_changes
        assert state['cli_calls']==cli and state['actual_worker_processes']==workers and state['actual_model_forward_calls']==forwards
        results=read(folder/'results.json')
        runs=[r for r in results.values() if isinstance(r,dict) and r.get('engine')=='transformers-wav2vec2-ctc-local-v1']
        assert len(runs)==workers and sum(r['worker']['model_forward_calls'] for r in runs)==forwards
        assert len(results['long']['segments'][0]['windows'])==2
        for result in runs:
            assert result['review_required'] and result['sample_rate']==16000
            assert result['worker']['network']=='disabled' and result['worker']['blocked_network_events']==[]
            assert result['stride_samples']==320 and result['receptive_samples']==400
            for segment in result['segments']:
                for character in segment['characters']:
                    assert result['original_text'][character['start_char']:character['end_char']]==character['text']
                    assert 0<=character['start_sample']<character['end_sample']<=result['samples']
            model_runs.append({'language':language,'samples':result['samples'],
                'forward_calls':result['worker']['model_forward_calls'],'peak_cuda_bytes':result['worker']['peak_cuda_bytes']})
        calls=[read(p) for p in sorted((folder/'cli').glob('*.json'))]
        assert len(calls)==cli
        expected_failures=[c for c in calls if c['exit_code']]
        assert len(expected_failures)==(1 if language=='zh' else 0)
        if expected_failures:
            assert expected_failures[0]['exit_code']==2 and 'ALIGNMENT_OOV' in json.dumps(expected_failures[0])
    quality=read(EVIDENCE/'ctc-real-en-20261018-b/word-boundary-quality.json')
    assert not quality['passed'] and quality['predeclared_max_error_seconds']==2/30
    assert quality['observed_max_error_seconds']==0.2581875
    native=read(EVIDENCE/'ctc-native-installed-20261018-b/verification.json')
    assert native['status']=='passed' and native['isolated_cli_calls']==11 and native['installed_package_files']==116
    assert native['generator_sha256']==sha(ROOT/'scripts/verify_ctc_native_install.py')
    assert native['actual_worker_processes']==native['actual_model_forward_calls']==1
    assert native['rgb_equal_to_development'] and native['pcm_equal_to_development'] and native['word_times_equal_to_development']
    assert native['package_bytes_equal_to_wheel'] and native['registered_implementation_paths_inside_install']
    assert not native['other_machine_accepted'] and not native['natural_alignment_quality_accepted']
    installed_alignment=read(EVIDENCE/'ctc-native-installed-20261018-b/08.stdout.json')['data']['result']
    assert installed_alignment['worker']['network']=='disabled' and installed_alignment['worker']['blocked_network_events']==[]
    archive_path=PUBLIC/'agent-video-kit-cp313-win_amd64.zip'
    assert sha(archive_path)==native['release_zip_sha256']
    release=read(PUBLIC/'release-manifest.json')
    assert release['runtime_profile']=='font-text-v1' and len(release['wheels'])==7 and len(release['files'])==20
    assert {r['name'] for r in release['wheels']}=={'ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py','pillow'}
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.read('manifest.json')==(PUBLIC/'release-manifest.json').read_bytes()
        for row in release['files']:
            payload=archive.read(row['path'])
            assert len(payload)==row['bytes'] and 'sha256:'+hashlib.sha256(payload).hexdigest()==row['sha256']
        assert archive.read('install.py')==(ROOT/'product/offline/install.py').read_bytes()
        product=next(row for row in release['wheels'] if row['name']=='ai-ad-editor')
        with zipfile.ZipFile(io.BytesIO(archive.read(product['path']))) as wheel:
            names=[n for n in wheel.namelist() if n.startswith('ai_ad_editor/') and not n.endswith('/')]
            assert len(names)==116
            for name in names:assert wheel.read(name)==(ROOT/'product/src'/name).read_bytes()
            metadata=wheel.read(next(n for n in wheel.namelist() if n.endswith('.dist-info/METADATA')))
            assert b'Requires-Dist: Pillow' in metadata
    receipt=read(PUBLIC/'install-receipt.json')
    assert receipt['audit']['modules']['pillow']['version']=='12.1.0'
    assert receipt['audit']['modules']['pillow']['path'].startswith('PIL/') or receipt['audit']['modules']['pillow']['path'].startswith('PIL\\')
    media=read(EVIDENCE/'ctc-media-20261018/verification.json')
    assert media['generator_sha256'].removeprefix('sha256:')==sha(ROOT/'scripts/verify_ctc_media.py').removeprefix('sha256:')
    assert media['status']=='failed' and not media['pcm_equal_to_original']
    assert media['highlight_clock_matches'] and len(media['highlight_frame_checks'])==236
    assert all(r['matches'] for r in media['highlight_frame_checks'])
    for name,row in media['files'].items():
        assert sha(PUBLIC/name).removeprefix('sha256:')==row['sha256'].removeprefix('sha256:')
    clock=read(EVIDENCE/'ctc-media-clock-20261018-b/verification.json')
    assert clock['generator_sha256'].removeprefix('sha256:')==sha(ROOT/'scripts/audit_ctc_audio_clock.py').removeprefix('sha256:')
    assert clock['status']=='verified' and not clock['previous_direct_16khz_equality_goal_passed']
    assert clock['independent_native_resample_reference_equal'] and clock['encoded_samples_48k']==377550
    assert clock['pcm_sha256']==native['pcm']['sha256'] and native['encoded_frames']==236
    assert clock['gif_frames']==79 and clock['gif_duration_ms']==7900
    static=read(EVIDENCE/'ctc-static-review-20261018.json')
    assert static['static_review'] and not static['continuous_playback_review'] and not static['listening_review']
    assert static['sha256']==sha(ROOT/static['path'])
    skills_path=EVIDENCE/'ctc-skills-20261018.json';skills=read(skills_path)
    assert skills['skill_count']==14 and skills['local_links_checked']==172
    manifest=read(ROOT/'video-cut-install-manifest.json')
    assert manifest['current_audit']['record_sha256']==sha(skills_path)
    for row in manifest['skills']:
        assert sha(ROOT/'skills'/row['name']/'SKILL.md')=='sha256:'+row['skill_md_sha256']
    documents=[ROOT/'README.md',ROOT/'AGENTS.md',*sorted((ROOT/'docs').rglob('*.md'))]
    local=0;broken=[];generated_output_links=0
    for path in documents:
        text=path.read_text(encoding='utf-8-sig');assert text.strip(),path
        text=re.sub(r'^\s*```.*?^\s*```[^\n]*','',text,flags=re.M|re.S)
        for raw in re.findall(r'!?\[[^\]]*\]\((<[^>]+>|[^\s)]+)(?:\s+"[^\"]*")?\)',text):
            target=raw.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) and not re.match(r'^[A-Za-z]:[/\\]',target):continue
            target=target.split('#',1)[0]
            if not target:continue
            local+=1
            resolved=(path.parent/urllib.parse.unquote(target)).resolve()
            if resolved==output:
                generated_output_links+=1
            elif not resolved.exists():broken.append({'document':str(path),'target':target})
    assert not broken,broken
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert list(map(int,re.findall(r'^\| V(\d{2}) \|',readme,re.M)))==list(range(1,50))
    assert readme.index('V49（产品）')<readme.index('V48（产品）')
    assert '258.1875' in readme and '7,900 ms' in readme and '完整 **1135/1135**' in readme
    files={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(PUBLIC.rglob('*')) if p.is_file()}
    result={'status':'evidence_verified_with_acoustic_quality_gate_failed','checked_at_utc':datetime.now(timezone.utc).isoformat(),
        'full_methods':1135,'frozen_files':170,'unchanged_since_real_model_files':166,'distribution_only_changed_files':sorted(changes),
        'development_cli_calls':{'en':15,'zh':12,'zh_expected_oov_rejections':1},'development_worker_processes':5,
        'development_model_forward_calls':8,'actual_model_runs':model_runs,'installed_cli_calls':11,
        'installed_worker_processes':1,'installed_forward_calls':1,'package_files':116,'release_wheels':7,
        'encoded_frames':236,'encoded_audio_samples_48k':377550,'gif_frames':79,'gif_duration_ms':7900,
        'acoustic_word_boundary_gate':quality,'natural_quality_accepted':False,'continuous_playback_review':False,'listening_review':False,
        'skills':14,'skill_links':172,'documents':len(documents),'local_links':local,'generated_self_output_links':generated_output_links,'broken_links':broken,
        'files':files,'full_regression_sha256':sha(full_path),'generator_sha256':sha(Path(__file__))}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:result[k] for k in ('status','full_methods','frozen_files','documents','local_links')}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.output.resolve())
