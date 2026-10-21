"""Bind the independent reverse prototype's real evidence, media and known limits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL=Path('docs/validation/evidence/vfr-reverse-20261021-lab')

def sha(path):
    with path.open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    output=ROOT/REL/'prototype-audit-r1.json'
    assert not output.exists()
    basis=frozen();checks=[]
    def check(name,ok,**details):
        checks.append({'name':name,'ok':bool(ok),**details});assert ok,name
    receipts={};method_ids=[]
    for name,count in [('targeted-with-budget-r1.json',13),('existing-nested-r2.json',73),('existing-clock-r2.json',14)]:
        path=ROOT/REL/name;d=json.loads(path.read_bytes())
        check(name+'-native-terminal',d['exit_code']==0 and d['terminal_ok'] and d['skipped']==0 and d['methods']==count,
              methods=d['methods'],seconds=d['suite_seconds'])
        check(name+'-exact-current-source',d['frozen_before']==d['frozen_after']==basis)
        check(name+'-log-digest',d['log_sha256']==sha(path.with_suffix('.log')))
        ids=re.findall(r'^test_\S+ \(([^)]+)\) \.\.\.',path.with_suffix('.log').read_text(encoding='utf8'),re.MULTILINE)
        check(name+'-method-identities',len(ids)==count)
        method_ids.extend(ids)
        receipts[name]={'sha256':sha(path),'methods':count,'seconds':d['suite_seconds']}
    check('one-hundred-distinct-method-identities',len(method_ids)==len(set(method_ids))==100)
    media=ROOT/REL/'native-r3/verification.json';d=json.loads(media.read_bytes())
    check('native-CLI-terminal',d['status']=='passed' and all(c['exit_code']==0 for c in d['calls']) and all(c['ok'] for c in d['checks']))
    check('native-exact-current-source',d['frozen_before']==d['frozen_after']==basis)
    check('eight-independent-cases',len(d['cases'])==8 and all(c['frames']==45 and c['max_rgb_error']==0 and c['PCM_equal'] for c in d['cases']))
    assets=ROOT/'docs/assets/vfr-reverse-20261021-lab/native-r3'
    for name,value in d['public_files'].items():
        path=assets/name
        check('actual-media-'+name,path.stat().st_size==value['bytes'] and sha(path)==value['sha256'])
    gifs={}
    for case in d['cases']:
        path=assets/(case['name']+'.gif')
        with Image.open(path) as image:
            delay=0
            for index in range(image.n_frames):
                image.seek(index);delay+=image.info.get('duration',0)
            gifs[case['name']]={'encoded_frames':image.n_frames,'source_output_frames':45,'duration_ms':delay}
        check(case['name']+'-GIF-duration',delay==1500,**gifs[case['name']])
    installed_path=ROOT/REL/'installed-r1/verification.json'
    installed=json.loads(installed_path.read_bytes())
    check('installed-terminal',installed['status']=='passed' and all(c['ok'] for c in installed['checks']))
    check('installed-exact-current-source',installed['frozen_before']==installed['frozen_after']==basis)
    installed_media=json.loads((installed_path.parent/'media/verification.json').read_bytes())
    check('installed-media-exact-current-source',installed_media['frozen_before']==installed_media['frozen_after']==basis)
    for name,value in installed_media['public_files'].items():
        path=ROOT/'docs/assets/vfr-reverse-20261021-lab/installed-r1'/name
        check('installed-actual-media-'+name,path.stat().st_size==value['bytes'] and sha(path)==value['sha256'])
    archive=ROOT/REL/'prototype-source-r1';assert not archive.exists();archive.mkdir()
    snapshots={}
    for name in ['product/src/ai_ad_editor/render.py','product/src/ai_ad_editor/reverse_video_clock.py',
                 'product/tests/test_reverse_video_clock.py','product/tests/test_reverse_video_budget.py']:
        path=ROOT/name;target=archive/(path.name+'.txt');target.write_bytes(path.read_bytes())
        snapshots[name]={'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target)}
    value={'status':'passed','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'prototype_only':True,'published_to_main':False,
        'native_windows':True,'virtualization':False,'network':False,'frozen_inputs':basis,
        'distinct_current_targeted_methods':100,'targeted_method_ids':method_ids,'targeted_receipts':receipts,
        'native_receipt_sha256':sha(media),'native_cli_calls':d['cli_calls'],'native_checks':len(d['checks']),
        'installed_receipt_sha256':sha(installed_path),'isolated_cli_calls':installed['isolated_cli_calls'],
        'module_origin_probes':installed['module_origin_probes'],'media_GIFs':gifs,'source_snapshots':snapshots,
        'checks':checks,'static_comparison_png_reviewed':True,'continuous_playback_reviewed':False,
        'audio_reviewed':False,'reverse_audio_accepted':False,'long_clip_performance_accepted':False,
        'full_prototype_regression_run':False,'full_capcut_parity':False,
        'foundation_test_cli_precedes_V81_test_only_correction':True}
    output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (ROOT/REL/'executed-prototype-audit.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':'passed','frozen':len(basis),'distinct_methods':100,
                      'native_CLI':d['cli_calls'],'isolated_CLI':installed['isolated_cli_calls'],'checks':len(checks)}))

if __name__=='__main__':main()
