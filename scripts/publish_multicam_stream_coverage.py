"""Publish frozen multicamera source-coverage bytes after the exact complete suite."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from native_index_release_tools import MAIN,sha,git,staged_rows
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
MODIFIED={'product/src/ai_ad_editor/'+name+'.py' for name in ('multicam','cli','capabilities')}
ADDED={'product/tests/test_multicam_stream_coverage.py'}
REL='docs/validation/evidence/multicam-stream-coverage-20261021-lab'
ASSETS='docs/assets/multicam-stream-coverage-20261021-lab'
REPORT='docs/validation/多机位原生视频覆盖实测_2026-10-21.md'
CONTRACT='docs/specs/多机位原生帧覆盖与只读索引契约_v0.1_2026-10-21.md'
HISTORICAL_REPORT='docs/validation/多机位原生视频覆盖独立实验_2026-10-21.md'
HISTORICAL_CONTRACT='docs/specs/多机位原生帧覆盖与只读索引契约_实验_v0.1_2026-10-21.md'
MARKER='V87-MULTICAM-NATIVE-STREAM-COVERAGE'
SKILLS=('video-cut-agent-editor', 'video-cut-timeline', 'video-cut-quality', 'video-cut-video-understand')
MODULES=('multicam', 'cli', 'capabilities')
TESTS=('test_multicam_stream_coverage',)
SCRIPTS=('run_multicam_stream_after_parent', 'run_frozen_regression', 'run_with_regression_fixtures', 'materialize_regression_fixtures', 'run_stream_related_regressions_r2', 'run_stream_related_regressions', 'run_stream_audio_controls', 'prepare_stream_audio_related', 'prepare_stream_related', 'prepare_stream_coverage_lab', 'audit_stream_development', 'smoke_multicam_stream_coverage', 'verify_multicam_stream_coverage_install', 'finalize_multicam_stream_lab', 'prepare_stream_skills', 'prepare_stream_full_gate', 'prepare_stream_smoke', 'prepare_stream_install_verifier', 'native_index_release_tools', 'prepare_stream_publication', 'publish_multicam_stream_coverage')
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md')


def read(path):return json.loads(Path(path).read_bytes())


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value.rstrip()+'\n',encoding='utf8',newline='\n')


def save(path,value):write(path,json.dumps(value,ensure_ascii=False,indent=2))


def block(path,value):
    path=Path(path);text=path.read_text('utf8')
    replacement=f'<!-- {MARKER} -->\n{value.rstrip()}\n<!-- /{MARKER} -->'
    pattern=re.escape('<!-- '+MARKER+' -->')+'.*?'+re.escape('<!-- /'+MARKER+' -->')
    if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:replacement,text,flags=re.S)
    else:
        position=text.index('\n---',3)+4 if text.startswith('---\n') else text.index('\n')
        text=text[:position]+'\n\n'+replacement+'\n'+text[position:]
    write(path,text)


def source_files():
    names={f'product/src/ai_ad_editor/{name}.py' for name in MODULES}
    names|={f'product/tests/{name}.py' for name in TESTS}
    names|={f'scripts/{name}.py' for name in SCRIPTS}|{HISTORICAL_REPORT,HISTORICAL_CONTRACT}
    for prefix in (REL,ASSETS):
        names.update(path.relative_to(ROOT).as_posix() for path in (ROOT/prefix).rglob('*') if path.is_file())
    for name in names:
        path=ROOT/name;assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),name
    return {name:sha(ROOT/name) for name in sorted(names)}


def source_audit():
    current=frozen();base=ROOT/REL
    audit=read(base/'audit-r1.json')
    assert audit['status']=='passed-standalone-audit' and audit['targeted_methods']==104
    assert current==audit['frozen_inputs'] and len(current)==258
    for name,row in audit['media'].items():assert sha(ROOT/name)==row['sha256']
    assert len(audit['media'])==38 and audit['GIF_count']==14
    for key,name in (('media_manifest_sha256','media-manifest-r1.json'),('static_review_sha256','static-review-r1.json'),
                     ('native_verification_sha256','native-r1/verification.json'),
                     ('isolated_verification_sha256','installed-r1/verification.json'),
                     ('skill_draft_sha256','skills-draft-r1.json')):
        assert sha(base/name)==audit[key]
    related=read(base/'related-r2.json')
    assert related['status']=='passed-related-regressions' and related['terminal_ok'] and related['exit_code']==0
    assert related['methods']==related['distinct_methods']==104 and related['skipped']==0
    assert len(related['method_ids'])==len(set(related['method_ids']))==104
    assert related['frozen_before']==related['frozen_after']==current and related['frozen_equal']
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert sha(base/'related-r2.json')==audit['related_sha256']
    assert sha(base/'related-r2.log')==related['log_sha256']
    assert sha(base/'foundation-r1.json')==related['fixture_manifest_sha256']
    for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    for name,digest in related['fixture_inputs'].items():assert sha(ROOT/name)==digest
    installation=read(base/'installed-r1/verification.json')
    assert installation['status']=='passed' and installation['isolated_cli_calls']==36 and installation['module_origin_probes']==1
    assert installation['frozen_before']==installation['frozen_after']==current
    assert len(installation['checks'])==14 and all(row['ok'] for row in installation['checks'])
    assert len(installation['resource_hashes'])==161 and len(installation['optional_numpy_addon']['files'])==933
    for name,digest in installation['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
    for name in ('native-r1/verification.json','installed-r1/media/verification.json'):
        item=read(base/name)
        assert item['status']=='passed' and item['cli_calls']==33 and item['native_commands']==25
        assert len(item['checks'])==54 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before']==item['frozen_after']==current
    drafts=read(base/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and drafts['skill_count']==4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0 and not row['registered']
        assert sha(ROOT/row['parent_snapshot'])==row['parent_sha256']
    previous=read(base/'foundation-r1.json')['source_inputs']
    assert previous==audit['source_parent_inputs'] and len(previous)==257
    assert set(current)-set(previous)==ADDED
    assert {name for name in previous if previous[name]!=current[name]}==MODIFIED
    fixture=read(base/'external-fixtures-r1.json')
    assert fixture['status']=='passed' and fixture['fixture_count']==8
    for row in fixture['fixtures']:assert sha(ROOT/row['path'])==row['sha256']
    return current


def complete_gate(current):
    state=read(ROOT/'product/.runtime/multicam-stream-coverage-20261021/full-after-multicam-r1/run.json')
    assert state['status']=='passed-complete-suite-awaiting-reviewed-integration'
    full=read(ROOT/REL/'full-r1.json');alignment=read(ROOT/REL/'published-multicam-alignment-r1.json')
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2019 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==current
    assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['verification_scripts_equal']
    assert full['external_fixture_manifest_unchanged'] and state['full_sha256']==sha(ROOT/REL/'full-r1.json')
    assert len(state['verification_scripts'])==15
    for name,digest in state['verification_scripts'].items():assert sha(ROOT/'scripts'/name)==digest
    assert alignment['status']=='passed' and alignment['candidate_inputs']==current
    assert len(alignment['upstream_inputs'])==257 and alignment['remote_main']==alignment['published_commit']
    snapshots=read(ROOT/REL/'before-full-documents-r1.json');audit=read(ROOT/REL/'audit-r1.json')
    for name,row in snapshots['documents'].items():assert sha(ROOT/row['snapshot'])==row['sha256']==audit['documents'][name]
    return full,alignment


def documents(root,full):
    seconds=full['suite_seconds']
    assert full['methods']==2019 and full['skipped']==0 and full['terminal_ok']
    message=(f'V87 多机位原生视频覆盖已完成 {full["methods"]} 方法、{seconds:.3f} 秒、0 跳过的完整回归；'
        '258 个冻结输入、8 个已提交外部夹具及 15 份验证脚本前后相同。'
        '视频覆盖取原生首/末帧区间，独立于较长音轨和容器时长；原速剪辑保留真实缺口。')
    def link(document,target):return os.path.relpath(root/target,(root/document).parent).replace('\\','/')
    rows=[
        ('V87-01','完整回归',f'{full["methods"]} 方法 /{seconds:.3f} 秒 /0 跳过；258 输入、8 夹具、15 验证脚本。',REL+'/full-r1.json'),
        ('V87-02','相关回归','104 个不同方法：24 本轮＋22 父多机位＋16 空选区＋32 嵌套时钟＋10 CLI；属于完整套件子集，旧 102 不累计。',REL+'/related-r2.json'),
        ('V87-03','真实视频边界','两组视频实际范围 [0,.32) 与 [1,1.32)，音轨/容器均 2 秒；33 原生 CLI＋25 其他命令、54 检查。',REL+'/native-r1/verification.json'),
        ('V87-04','完整无损 RGBA/PCM','每组 50 帧、11,520,000 RGBA 字节与 768,000 float32 PCM 字节 /每声道 96,000 样本独立一致。主音轨须显式创作。',REL+'/native-r1/verification.json'),
        ('V87-05','MP4/GIF 与静态目检','trim/stretch 均 50 帧、PTS=n/25；trim 身份色块最大误差 1，非编码整帧一致。源 GIF 8 帧/320 ms，输出 GIF 2000 ms，黑帧会合并。',REL+'/static-review-r1.json'),
        ('V87-06','只读索引与损坏拒绝','命中经 SHA 核验的既有原生索引时 0 次源帧探针，仍读 SHA。损坏索引拒绝保留，工程/报告/快照/缓存不被自动修复。',REL+'/installed-r1/media/verification.json'),
        ('V87-07','当前源码的新隔离安装','161 资源源码/包/安装相同；36 CLI＋1 次 14 模块来源探针、14 安装检查＋54 媒体检查。7 wheels 不含 NumPy，实验只读复制既有 2.4.2 的 933 个 RECORD 文件及许可。',REL+'/installed-r1/verification.json'),
        ('V87-08','仅音频及未知 EOF','有效音频分析可返回偏移与 unknown 视频诊断，生成该机位切换时拒绝；未知视频状态采用模拟，音频真实生成。完整性错误仍拒绝。',REL+'/audio-only-after-r1.json'),
        ('V87-09','保留失败与生成器修复','真实修复前 8 方法有 7 方法/9 断言失败；另保留子测试错误、仅音频过度拒绝、汇总清单名及生成器数字替换失误。修复未冒称旧结果重跑。',REL+'/audit-r1.json'),
        ('V87-10','契约与范围','4 Skill 只合并本轮增量，17 份再审。自然/HDR/长片/RSS/漂移/非零音频流起点/连续播放听审及完整剪映功能效果仍待验收。',CONTRACT),
    ]
    for document in LATEST_DOCS:
        table='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
        table+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(document,target)+') |' for i,title,result,target in rows)
        gallery=''
        if document=='README.md':
            gallery=('\n\n原创参考（CC0 七段数字矩形及确定性音频，无外部字体/图片）：\n\n'
                '![V87 参考]('+ASSETS+'/native-r1/source-reference.gif)\n\n'
                '尾部视频在 .32 秒结束，原速保留后续背景（实际 MP4 解码 GIF）：\n\n'
                '![V87 尾部缺口]('+ASSETS+'/native-r1/tail-trim.gif)\n\n'
                '视频在 1 秒开始、1.32 秒结束，原速保留两端背景：\n\n'
                '![V87 延迟视频]('+ASSETS+'/native-r1/leading-trim.gif)\n\n'
                '[尾部原片 MKV]('+ASSETS+'/native-r1/source-tail.mkv) · '
                '[延迟原片 MKV]('+ASSETS+'/native-r1/source-leading.mkv) · '
                '[尾部原速 MP4]('+ASSETS+'/native-r1/tail-trim.mp4) · '
                '[延迟原速 MP4]('+ASSETS+'/native-r1/leading-trim.mp4) · '
                '[显式拉伸 MP4]('+ASSETS+'/native-r1/leading-stretch.mp4) · '
                '[拉伸 GIF]('+ASSETS+'/native-r1/leading-stretch.gif) · '
                '[全部资产 SHA]('+REL+'/media-manifest-r1.json)。'
                '原片保存真实 PTS 与 2 秒音轨；源 GIF 只展示 8 解码帧，没有伪造前后空白。'
                'GIF 不含音频，未作连续播放/听审；编码 MP4/AAC 不声明完整 RGBA/PCM 字节一致。')
        block(root/document,'### V87 多机位原生视频覆盖\n\n'+message+'\n\n'+table+gallery+
            '\n\n[完整实测]('+link(document,REPORT)+')。方法子集、原生命令、安装检查分开报告，不累计为额外完整方法或剪映等价。')
    report='# 多机位原生视频覆盖实测（V87，2026-10-21）\n\n'+message+'\n\n'
    report+='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
    report+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(REPORT,target)+') |' for i,title,result,target in rows)
    report+='\n\n'+'''视频覆盖不能由更长的音轨推断。使用原生首帧 PTS、末帧 PTS＋已知 duration、time_base、demux origin，保留精确有理数；原点舍入与渲染器一致。参考 r 对应源 r＋relative_delay_seconds。trim 按真实边界取交集、保持原速和参考事件位置；尾部为 8 彩帧＋42 背景帧，延迟为 25 背景＋8 彩帧＋17 背景。公开视频延迟样例使用参考第 25..32 帧本身，与参考事件身份一致。此前单元测试将第 0..7 帧延迟，仅验证覆盖范围，不能混写为同一素材。

默认 reject 拒绝覆盖不足。显式 stretch speed=.16，会填满作者区间并改变事件位置，保留 MULTICAM_SOURCE_CLOCK_CHANGED 警告；从真实首帧钳制。完全不相交、未知 EOF、畸形边界、锁定应用目标和亚 tick 段均拒绝。视频轨不自动提取声音，显式主音轨保持完整 2 秒；请求窗口及较长作者时长保留。

只读原生索引缺失时可探测但不写缓存，命中时报告 0 源帧探针，仍读取实际源及运行时 SHA；不能称为零 I/O、零成本或零解码。损坏索引拒绝保留，变更源 SHA 拒绝，不转换为成功音频分析。真实音频配合模拟未知视频状态验证了仅音频分析返回有效偏移和明确诊断；它没有验收一个真实未知末帧封装的完整观看副本。旧函数 0.1/0.2 输入只有容器时长时发警告；新 CLI 0.3 不静默降级。

本候选媒体和隔离安装均以当前 258 输入重新生成，不复用 V86 旧媒体。原生 33 CLI＋25 其他命令/54 检查；隔离 36 CLI＋1 来源进程/14 模块，另有 14 安装及 54 媒体检查。161 运行时资源源码、wheel、安装同字节。基础 7 wheels 仍不含 NumPy；实验只读复制既有 NumPy 2.4.2 的 933 个经 RECORD 核对文件及许可，未下载、未全局安装，不能写成产品安装器已新增 NumPy 发行支持。

38 资产、14 GIF 来自原生/隔离两次真实生成。源 GIF 为 8 帧/320 ms；两组 trim GIF 分别合并为 9/10 帧、2000 ms。每个实际 MP4 为 50 帧且 PTS=n/25，trim 身份色块最大误差 1。完整无损 RGBA/PCM 与编码观看副本分开验收；编码整帧及 AAC 没有字节一致声明。两张 1280×400 边界图做过静态目检，安装图像素一致；没有连续播放或听审。

保留原 8 方法 7 方法/9 断言失败、第一次子测试异常字段失误、仅音频过度拒绝；104 当前相关方法覆盖修正后 24＋22＋16＋32＋10，旧 102 是历史结果不累计。汇总器第一次因夹具清单名错误在写文档前失败；完整套件生成器第一次因未限制数字替换范围触及 SHA256 字面量，被 AST 一致性检查阻止，在生成启动器前失败。原脚本与原因均保留，产品源码和媒体没有因这些生成器修复改变。

非零视频封装原点和分数时钟有时间算术控制；不能外推为非零音频流起点验收。自然多机位、密集切换、设备漂移、HDR、长片吞吐、总 RSS、连续播放和听审均未验收；没有完成完整剪映功能或效果等价。原生 Windows，无 Docker、WSL、虚拟环境、远程模型或在线依赖安装。
'''
    for title,target in (('历史实验及失败',HISTORICAL_REPORT),('契约',CONTRACT),
        ('汇总器原失败',REL+'/finalize-public-media-failed-r1.json'),('启动器生成原失败',REL+'/full-gate-preparation-failed-r1.json'),
        ('尾部原片',ASSETS+'/native-r1/source-tail.mkv'),('延迟原片',ASSETS+'/native-r1/source-leading.mkv'),
        ('尾部实际 MP4',ASSETS+'/native-r1/tail-trim.mp4'),('延迟实际 MP4',ASSETS+'/native-r1/leading-trim.mp4')):
        report+='\n['+title+']('+link(REPORT,target)+')\n'
    report+='\n![实际延迟原速 GIF]('+link(REPORT,ASSETS+'/native-r1/leading-trim.gif')+')\n'
    report+='\n复现脚本：scripts/smoke_multicam_stream_coverage.py、scripts/verify_multicam_stream_coverage_install.py；精确源码、命令、日志及 SHA 在对应证据目录。\n'
    write(root/REPORT,report)
    constraints='\n'.join(line for line in (root/HISTORICAL_CONTRACT).read_text('utf8').splitlines() if line.startswith('|'))
    assert constraints.count('| SV-C')==12
    constraints=constraints.replace('完整回归/发布未完成','完整回归通过；本次接入生产，发布状态见实测')
    write(root/CONTRACT,'# 多机位原生帧覆盖与只读索引契约（v0.1 限定验收，2026-10-21）\n\n'+message+'\n\n'+constraints+
        '\n\n[实际原生/安装、原片/GIF 和保留失败](../validation/'+Path(REPORT).name+')。未知状态模拟、音频起点/漂移、长片与自然效果边界仍有效。')
    drafts=read(ROOT/REL/'skills-draft-r1.json');assert set(drafts['skills'])==set(SKILLS)
    for name,row in drafts['skills'].items():
        guidance=row['new_block'].replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        pending='This is an unregistered candidate; complete regression and main integration remain pending.'
        assert guidance.count(pending)==1;guidance=guidance.replace(pending,'')
        assert 'unregistered candidate' not in guidance and 'remain pending' not in guidance
        block(root/'skills'/name/'SKILL.md',guidance)
    attributes=(root/'.gitattributes').read_text('utf8')
    paths=[REL+'/** -text -whitespace',ASSETS+'/** -text -whitespace']
    paths += [f'product/src/ai_ad_editor/{name}.py -text whitespace=cr-at-eol' for name in MODULES]
    paths += [f'product/tests/{name}.py -text whitespace=cr-at-eol' for name in TESTS]
    paths += [f'scripts/{name}.py -text whitespace=cr-at-eol' for name in SCRIPTS]
    write(root/'.gitattributes',attributes+'\n# V87 exact tested native-stream coverage bytes.\n'+'\n'.join(paths))
    return {*LATEST_DOCS,REPORT,CONTRACT,'.gitattributes',*('skills/'+name+'/SKILL.md' for name in SKILLS)}



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True);parser.add_argument('--preflight-only',action='store_true')
    args=parser.parse_args();work=args.work.resolve()
    assert work.is_relative_to(ROOT/'product/.runtime') and not work.exists();work.mkdir(parents=True)
    state={'status':'checking-source','started_at_utc':datetime.now(timezone.utc).isoformat(),'calls':[],'force_push':False}
    def checkpoint():save(work/'run.json',state)
    try:
        current=source_audit();reviewed=source_files()
        state.update(status='passed-source-preflight-awaiting-full',frozen_inputs=current,source_files=reviewed);checkpoint()
        if args.preflight_only:return
        full,alignment=complete_gate(current);base=alignment['published_commit']
        assert git(MAIN,'branch','--show-current').decode().strip()=='main'
        assert git(MAIN,'rev-parse','HEAD').decode().strip()==base
        assert git(MAIN,'remote','get-url','origin').decode().strip()=='git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]==base
        assert not git(MAIN,'status','--porcelain','-z'),'Preserve unexpected main changes; no implicit integration'
        spec=importlib.util.spec_from_file_location('nested_native_main_freeze',MAIN/'scripts/run_frozen_regression.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        assert module.frozen()==alignment['upstream_inputs']
        tracked={p.decode('utf8') for p in git(MAIN,'ls-files','-z').split(b'\0') if p}
        generated={REPORT,CONTRACT,REL+'/skills-release-r1.json',REL+'/release-main-r1.json',REL+'/publication-copy-r1.json',REL+'/staged-release-r1.json'}
        for name in set(reviewed)|generated:
            path=MAIN/name;assert path.resolve().is_relative_to(MAIN) and not path.is_symlink()
            assert name in tracked or not path.exists(),'Existing untracked destination: '+name
        assert source_files()==reviewed and frozen()==current
        state.update(status='copying-reviewed-source',base_commit=base);checkpoint()
        for name,digest in reviewed.items():
            target=MAIN/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
            assert sha(target)==digest,name
        assert module.frozen()==current
        modified_docs=documents(MAIN,full)
        command=[sys.executable,'-E','-B','-X','utf8',str(MAIN/'scripts/audit_source_edit_skills.py'),
            '--expected-count','17','--output',str(MAIN/REL/'skills-release-r1.json')]
        result=subprocess.run(command,cwd=MAIN,capture_output=True,timeout=600)
        (work/'main-skills.stdout.log').write_bytes(result.stdout);(work/'main-skills.stderr.log').write_bytes(result.stderr)
        state['calls'].append({'command':command,'exit_code':result.returncode});checkpoint();assert result.returncode==0
        skills=read(MAIN/REL/'skills-release-r1.json');mapping_path=MAIN/'video-cut-install-manifest.json';mapping=read(mapping_path)
        mapping.setdefault('audit_history',[]).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row=next(item for item in skills['results'] if item['skill']==entry['name'])
            old,new=entry['skill_md_sha256'],row['sha256'][7:]
            if old!=new:
                entry.setdefault('skill_md_sha256_history',[]).append(old);entry['previous_manifest_skill_md_sha256']=old
            entry.update(skill_md_sha256=new,validation=row['validator_stdout'],prefix_verified=True,registration_verified=True)
            assert Path(entry['canonical_directory']).resolve()==(MAIN/'skills'/entry['name']).resolve()
        mapping['current_audit']={'date':'2026-10-21','skill_count':17,'local_links_checked':skills['local_links_checked'],
            'record':REL+'/skills-release-r1.json','record_sha256':sha(MAIN/REL/'skills-release-r1.json'),
            'previous_hashes_preserved':True,'semantics':'V87 native video intervals and readonly verified frame indices; audio-only unknown-coverage diagnostics; offset only, no drift or full CapCut parity acceptance'}
        save(mapping_path,mapping)
        links=[]
        for name in sorted(modified_docs-{'.gitattributes'}):
            path=MAIN/name;text=path.read_text('utf8')
            if name in LATEST_DOCS or name.startswith('skills/'):text=text.split('<!-- '+MARKER+' -->')[1].split('<!-- /'+MARKER+' -->')[0]
            for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',text):
                target=token.strip('<>').split('#',1)[0]
                if not target or re.match(r'^[a-zA-Z][\w+.-]*:',target):continue
                resolved=(path.parent/target).resolve();assert resolved.is_relative_to(MAIN) and resolved.exists(),(name,token)
                links.append({'document':name,'target':resolved.relative_to(MAIN).as_posix()})
        for name,digest in current.items():assert sha(MAIN/name)==digest
        for name,row in full['external_fixtures_expected'].items():assert sha(MAIN/name)==row['sha256']
        save(MAIN/REL/'release-main-r1.json',{'status':'passed-main-byte-and-document-audit','base_commit':base,
            'frozen_inputs':current,'full_methods':2019,'full_skipped':0,'full_sha256':sha(MAIN/REL/'full-r1.json'),
            'targeted_methods':104,'resources':161,'skills':17,'local_links':links,
            'documents':{name:sha(MAIN/name) for name in sorted(modified_docs)},'generator_sha256':sha(Path(__file__))})
        save(MAIN/REL/'publication-copy-r1.json',{'status':'passed-reviewed-copy','source':str(ROOT),
            'copied_files':reviewed,'frozen_inputs':current,'base_commit':base})
        changed={p.decode('utf8') for p in git(MAIN,'diff','--name-only','-z').split(b'\0') if p}
        changed.update(p.decode('utf8') for p in git(MAIN,'ls-files','--others','--exclude-standard','-z').split(b'\0') if p)
        allowed=set(reviewed)|modified_docs|generated|{'video-cut-install-manifest.json'}
        assert changed<=allowed,sorted(changed-allowed)
        stage=work/'stage-paths.nul';stage.write_bytes(b'\0'.join(name.encode('utf8') for name in sorted(changed))+b'\0')
        git(MAIN,'add','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        git(MAIN,'add','--renormalize','--pathspec-from-file='+str(stage),'--pathspec-file-nul')
        assert not git(MAIN,'diff','--name-only')
        assert {p.decode('utf8') for p in git(MAIN,'diff','--cached','--name-only','-z').split(b'\0') if p}==changed
        git(MAIN,'diff','--cached','--check');rows=staged_rows({**{name:sha(MAIN/name) for name in changed},**current})
        receipt=REL+'/staged-release-r1.json'
        save(MAIN/receipt,{'status':'passed','frozen_files':258,'compared_blobs':len(rows),'files':rows,
            'all_staged_bytes_equal_workspace':True,'all_frozen_bytes_equal_staged':True,
            'stream_buffer_bytes':65536,'full_sha256':sha(MAIN/REL/'full-r1.json'),'base_commit':base})
        git(MAIN,'add','--',receipt);staged_rows({receipt:sha(MAIN/receipt)})
        assert module.frozen()==current and not git(MAIN,'diff','--name-only')
        git(MAIN,'diff','--cached','--check');state.update(status='passed-staged-audit');checkpoint()
        git(MAIN,'commit','--quiet','-m','fix: use native video intervals for multicamera coverage')
        commit=git(MAIN,'rev-parse','HEAD').decode().strip();assert git(MAIN,'rev-parse','HEAD^').decode().strip()==base
        state.update(status='committed-awaiting-ordinary-push',commit=commit);checkpoint()
        git(MAIN,'push','origin','main');remote=git(MAIN,'ls-remote','origin','refs/heads/main').decode().split()[0]
        assert remote==commit and not git(MAIN,'status','--porcelain','-z') and module.frozen()==current
        state.update(status='published',remote_main=remote,main_clean=True,full_methods=2019)
    except BaseException as caught:
        state.update(status='failed',error={'type':type(caught).__name__,'message':str(caught)});raise
    finally:
        checkpoint();print(json.dumps({k:state.get(k) for k in ('status','commit','remote_main','error')},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
