"""Bind standalone index evidence without publishing or claiming a full run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/native-frame-index-20261021-lab'
REPORT='docs/validation/原生帧索引缓存独立实验_2026-10-21.md'
CONTRACT='docs/specs/原生帧索引缓存契约_实验_v0.1_2026-10-21.md'


def read(path):return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    with path.open('rb') as source:return 'sha256:'+hashlib.file_digest(source,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    base=ROOT/REL;output=args.output.resolve();assert output.is_relative_to(base) and not output.exists()
    current=frozen();assert len(current)==254
    methods=set();receipts={}
    for name,count in (('integration-r2',37),('reverse-r1',50),('nested-r1',63),('preview-r1',22)):
        record=read(base/(name+'.json'))
        assert record['exit_code']==0 and record['terminal_ok'] and record['methods']==count and record['skipped']==0
        assert record['frozen_before']==record['frozen_after']==current
        log=base/(name+'.log');assert sha(log)==record['log_sha256']
        found=set(re.findall(r'^test\S+ \(([^)]+)\) \.\.\.',log.read_text(encoding='utf8'),re.M))
        assert len(found)==count and not methods&found
        methods|=found;receipts[name]={'methods':count,'sha256':sha(base/(name+'.json'))}
    assert len(methods)==172
    previous=read(base/'reverse-ops-r1.json')
    assert previous['terminal_ok'] and previous['methods']==13 and previous['skipped']==0
    assert previous['frozen_before']==previous['frozen_after']==current
    found=set(re.findall(r'^test\S+ \(([^)]+)\) \.\.\.',(base/'reverse-ops-r1.log').read_text(encoding='utf8'),re.M))
    assert len(found)==13 and found<=methods
    installed=read(base/'installed-r1/verification.json')
    assert installed['status']=='passed' and installed['isolated_cli_calls']==20 and installed['module_origin_probes']==1
    assert len(installed['checks'])==9 and all(row['ok'] for row in installed['checks'])
    assert installed['frozen_before']==installed['frozen_after']==current
    assert installed['generator_sha256']==sha(ROOT/'scripts/verify_native_frame_index_install.py')
    resources=installed['resource_hashes'];assert len(resources)==161
    for name,digest in resources.items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest,name
    native=read(base/'native-r1/verification.json');media={};gifs={}
    for directory in ('native-r1','installed-r1/media'):
        result=read(base/directory/'verification.json')
        assert result['status']=='succeeded' and result['cli_calls']==17 and len(result['calls'])==26
        assert len(result['checks'])==24 and all(item['ok'] for item in result['checks'])
        assert all(call['exit_code']==0 for call in result['calls'])
        assert result['frozen_before']==result['frozen_after']==current
        assert (base/directory/'executed-smoke.py.txt').read_bytes()==(ROOT/'scripts/smoke_native_frame_index.py').read_bytes()
        assert len(result['source_frame_hashes'])==9
        assert result['source_frame_hashes']==native['source_frame_hashes']
        assert result['cache_frame_hashes']==result['source_frame_hashes'][:8][::-1]
        assert result['preview_reference']['bytes']==294912 and result['preview_reference']['max_RGBA_error']==0
        first,second,rebuilt=(result['native_index_'+name] for name in ('first','second','rebuilt'))
        assert first['source_index_decode_calls']==rebuilt['source_index_decode_calls']==1
        assert second['source_index_decode_calls']==0 and second['status']=='cache-hit'
        assert first['key']==second['key']==rebuilt['key']
        for name in ('pts','durations'):assert first['files'][name]['sha256']==rebuilt['files'][name]['sha256']
        assert not result['repeated_render_still_decodes_native_source_index']
        assert result['source_hash_io_still_required_on_index_hits']
        for name,row in result['media'].items():
            path=ROOT/name;assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
            media[name]=row
            if path.suffix=='.gif':
                with Image.open(path) as image:
                    durations=[]
                    for i in range(image.n_frames):image.seek(i);durations.append(image.info['duration'])
                assert durations==[40]*8;gifs[name]={'frames':8,'duration_ms':320,'sha256':sha(path)}
    assert len(gifs)==4
    report=ROOT/REPORT;value=report.read_text(encoding='utf8')
    value=value.replace('正在运行；未标记通过 | [倒放状态]',
        '倒放 50 项 /305.730 秒、嵌套 63 项 /152.656 秒、预览 22 项 /48.097 秒，均通过且 0 跳过；与 37 项组成 172 个不同方法；13 项共用清理属于 50 项子集 | [倒放状态]')
    if '[预览](evidence/native-frame-index-20261021-lab/preview-r1.json)' not in value:
        value=value.replace('[嵌套状态](evidence/native-frame-index-20261021-lab/nested-r1.json)',
            '[嵌套状态](evidence/native-frame-index-20261021-lab/nested-r1.json) · [预览](evidence/native-frame-index-20261021-lab/preview-r1.json)')
    report.write_text(value,encoding='utf8',newline='\n')
    readme=ROOT/'README.md';value=readme.read_text(encoding='utf8').replace(
        '| NI-E03 | 倒放专项、嵌套相邻检查 | 正在运行，未标记通过 |',
        '| NI-E03 | 倒放、嵌套与预览相邻检查 | 50＋63＋22 方法通过；与 37 项组成 172 个不同方法，均 0 跳过；13 项清理不重复累计 |')
    readme.write_text(value,encoding='utf8',newline='\n')
    links=[]
    for name in ('README.md',REPORT,CONTRACT):
        path=ROOT/name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',path.read_text(encoding='utf8')):
            target=token.strip('<>').split('#',1)[0]
            if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
            resolved=(path.parent/target).resolve();assert resolved.is_relative_to(ROOT) and resolved.exists(),(name,token)
            links.append({'document':name,'target':resolved.relative_to(ROOT).as_posix()})
    skills=[]
    for name in ('video-cut-agent-editor','video-cut-timeline','video-cut-quality','video-cut-project-ops'):
        path=ROOT/'skills'/name/'SKILL.md'
        result=subprocess.run([sys.executable,'-E','-B','-X','utf8',
            'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(path.parent)],
            capture_output=True,timeout=60)
        assert result.returncode==0,name
        value=path.read_text(encoding='utf8').split('<!-- NATIVE-INDEX-LAB-20261021 -->',1)[1]
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',value):
            target=(path.parent/token).resolve();assert target.is_relative_to(ROOT) and target.is_file()
        skills.append({'name':name,'sha256':sha(path),'validator_stdout':result.stdout.decode('utf8'),
                       'exit_code':result.returncode,'registered':False,'full_main_links_audited':False})
    assert links and current==frozen()
    output.write_text(json.dumps({
        'status':'passed-standalone-audit','frozen_inputs':current,'frozen_equal':True,
        'distinct_targeted_methods':sorted(methods),'targeted_methods':172,
        'source_wheel_installed_resources':161,'isolated_cli_calls':20,'module_origin_probes':1,
        'native_checks':24,'native_commands':26,'native_cli_calls':17,
        'media':media,'GIF':gifs,'local_links':links,'receipts':receipts,'experimental_skills':skills,
        'documents':{name:sha(ROOT/name) for name in ('README.md',REPORT,CONTRACT)},
        'native_output_contact_sheet_reviewed':True,'continuous_playback_reviewed':False,'audio_reviewed':False,
        'complete_regression_executed':False,'main_integrated':False,'pushed':False,
        'long_duration_latency_accepted':False,'peak_process_memory_measured':False,
        'natural_quality_accepted':False,'HDR_accepted':False,'full_capcut_parity':False,
        'generator_sha256':sha(Path(__file__)),
    },ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'passed-standalone-audit','targeted_methods':172,'frozen_inputs':254,
                      'resources':161,'media_files':len(media),'local_links':len(links),'main_integrated':False}))


if __name__=='__main__':main()
