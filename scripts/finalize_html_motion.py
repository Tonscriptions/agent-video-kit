"""Retain support evidence and assemble the final byte-frozen HTML motion record."""
from __future__ import annotations
import argparse,hashlib,json,shutil,zipfile
from datetime import datetime,timezone
from pathlib import Path
from smoke_fragments import frozen,save,sha

ROOT=Path(__file__).resolve().parents[1];EV=ROOT/'docs/validation/evidence'


def entries(folder):
    return {p.relative_to(folder).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(folder.rglob('*')) if p.is_file()}


def support():
    wheel_work=ROOT/'product/.runtime/html-motion-wheel-20261018'
    target=EV/'html-motion-wheel-20261018';target.mkdir(exist_ok=False)
    wheel=next((wheel_work/'dist').glob('*.whl'))
    shutil.copyfile(wheel,target/wheel.name)
    shutil.copyfile(wheel_work/'verification.json',target/'verification.json')
    with zipfile.ZipFile(target/'raw-cli-and-build.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(wheel_work.glob('*.log')):archive.write(path,path.name)
    with zipfile.ZipFile(target/'raw-cli-and-build.zip') as archive:assert archive.testzip() is None
    dev=EV/'html-motion-development-20261018';dev.mkdir(exist_ok=False)
    before=ROOT/'docs/assets/html-motion-clock-failure-20261018'
    expected=json.loads((before/'run-state.json').read_text(encoding='utf-8'))['source_before']
    historical={}
    for name,value in expected.items():
        content=(ROOT/name).read_bytes()
        if 'sha256:'+hashlib.sha256(content).hexdigest()==value:
            historical[name]=content;continue
        text=content.decode('utf-8')
        if name.endswith('/html_motion.py'):
            text=text.replace('from .media import ffmpeg_path, ffprobe_path, probe_media','from .media import ffmpeg_path, probe_media')
            text=text.replace(', sha256_file, run_process',', sha256_file')
            text=text.replace("'output':'ffv1-bgra-nut'","'output':'ffv1-bgra-mkv'").replace("scratch=temp/'result.nut'","scratch=temp/'result.mkv'")
            a=text.index('            pts_result=run_process(');b=text.index('            if scratch.stat().st_size>',a)
            text=text[:a]+text[b:]
        elif name.endswith('/cli.py'):
            text=text.replace("html_motion.digest(args.asset_id.encode())[7:39] + '.nut'","html_motion.digest(args.asset_id.encode())[7:39] + '.mkv'")
            text=text.replace('        save_ledger(root, ledger)  # validation sees the same candidate rights; transaction protects rollback\n','')
            a=text.index('    except BaseException as exc:\n',text.index('def command_html_render('));b=text.index('\n\ndef command_motion_list(',a)
            text=text[:a]+'''    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
'''+text[b:]
        elif name.endswith('/media.py'):
            text=text.replace(', ".nut"}','}')
        elif name.endswith('/capabilities.py'):
            text=text.replace('straight_alpha_ffv1_bgra_nut_exact_rational_frame_clock','straight_alpha_ffv1_bgra_native_timeline_asset')
        elif name.endswith('/test_html_motion.py'):
            text=text.replace("        self.assertEqual(result['data']['asset']['probe']['duration_tick'],TPS)\n",'')
            text=text.replace(".rglob('*.nut')",".rglob('*.mkv')")
            a=text.index('    def test_twelve_fps_retains_every_frame_after_native_timeline_composition(')
            b=text.index('    def test_cancel_after_page_open_kills_all_native_descendants(',a)
            text=text[:a]+text[b:]
        else:raise AssertionError('unexpected historical difference: '+name)
        content=text.encode('utf-8')
        assert 'sha256:'+hashlib.sha256(content).hexdigest()==value,'reconstruction mismatch: '+name
        historical[name]=content
    with zipfile.ZipFile(dev/'matroska-source-frozen.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,content in sorted(historical.items()):archive.writestr(name,content)
    with zipfile.ZipFile(dev/'matroska-source-frozen.zip') as archive:
        assert archive.testzip() is None
        for name,content in historical.items():assert archive.read(name)==content
    source=ROOT/'product/.runtime/html-motion-final-20261018/main/renders/S03-timeline.mkv.manifest.json'
    shutil.copyfile(source,dev/'matroska-before.manifest.json')
    for name in ('diagnose_html_timebase.py','inspect_html_composite.py'):
        shutil.copyfile(ROOT/'product/.runtime'/name,dev/name)
    logs={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(EV.glob('html-motion-development-20261018-*')) if p.is_file()}
    directories={name:entries(ROOT/'docs/assets'/name) for name in ('html-motion-development-20261018','html-motion-clock-failure-20261018')}
    save(dev/'verification.json',{'status':'retained_development_evidence','logs':logs,'original_media_directories':directories,
        'matroska_source_reconstructed_exactly_from_final':True,'historical_source_files':len(historical),'historical_frozen':expected,
        'support_files':entries(dev),'note':'Historical failures and diagnostic NUT are not final product pass counts; source reconstruction verifies all original byte hashes'})
    print(json.dumps({'wheel_files':len(entries(target)),'development_logs':len(logs),'historical_source_files':len(historical)}))


def finish():
    full=json.loads((EV/'html-motion-final-full-20261018.json').read_text(encoding='utf-8'))
    assert full.get('exit_code')==0 and full.get('terminal_ok') and full.get('frozen_equal') and full.get('skipped')==0
    assert full['frozen_after']==frozen()
    spec=json.loads((EV/'html-motion-final-specific-20261018.json').read_text(encoding='utf-8'))
    assert spec['methods']==37 and spec['terminal_ok'] and spec['frozen_after']==frozen()
    media=json.loads((EV/'html-motion-media-final-20261018.json').read_text(encoding='utf-8'))
    for name,item in media['public_files'].items():assert sha(ROOT/'docs/assets/html-motion-20261018'/name)==item['sha256']
    record={'status':'passed','created_at_utc':datetime.now(timezone.utc).isoformat(),'goal_still_active':True,
        'complete_capcut_parity_accepted':False,'full':full,'specific':spec,
        'public_cases':json.loads((ROOT/'docs/assets/html-motion-20261018/verification.json').read_text(encoding='utf-8')),
        'public_media_audit':media,'wheel':json.loads((EV/'html-motion-wheel-20261018/verification.json').read_text(encoding='utf-8')),
        'wheel_files':entries(EV/'html-motion-wheel-20261018'),'development':json.loads((EV/'html-motion-development-20261018/verification.json').read_text(encoding='utf-8')),
        'skills':json.loads((EV/'html-motion-skills-20261018.json').read_text(encoding='utf-8')),
        'openfilm':json.loads((EV/'openfilm-html-adoption-20261018/verification.json').read_text(encoding='utf-8')),
        'static_review':json.loads((EV/'html-motion-static-20261018.json').read_text(encoding='utf-8')),
        'generator_sha256':sha(Path(__file__))}
    save(EV/'html-motion-20261018.json',record)
    print(json.dumps({'methods':full['methods'],'seconds':full['suite_seconds'],'frozen_files':len(full['frozen_after']),
                      'media_files':media['file_count'],'cli_calls':record['public_cases']['calls']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['support','finish']);args=parser.parse_args()
    support() if args.phase=='support' else finish()
