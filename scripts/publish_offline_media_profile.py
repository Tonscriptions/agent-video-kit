"""Publish the complete offline media runtime after actual2043 and default bootstrap validation."""
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
WHEELHOUSE='sources/python-runtime/cp313-win_amd64-media'
MODIFIED={'product/offline/build.py', 'product/pyproject.toml', 'product/offline/install.py'}
ADDED={'product/tests/test_offline_media_profile.py'}
REL='docs/validation/evidence/offline-media-profile-20261021-lab'
ASSETS='docs/assets/offline-media-profile-20261021-lab'
REPORT='docs/validation/八轮离线媒体运行时实测_2026-10-21.md'
CONTRACT='docs/specs/离线媒体运行时与NumPy交付_v0.1_2026-10-21.md'
HISTORICAL_REPORT='docs/validation/八轮离线媒体运行时独立实验_2026-10-21.md'
HISTORICAL_CONTRACT='docs/specs/离线媒体运行时与NumPy交付_实验_v0.1_2026-10-21.md'
MARKER='V89-OFFLINE-MEDIA-PROFILE'
SKILLS=('video-cut-agent-editor', 'video-cut-timeline', 'video-cut-quality', 'video-cut-video-understand')
MODULES=()
TESTS=('test_offline_media_profile',)
SCRIPTS=('run_offline_media_after_parent', 'run_frozen_regression', 'run_with_regression_fixtures', 'materialize_regression_fixtures', 'prepare_offline_media_lab', 'prepare_media_wheelhouse', 'audit_media_profile_development', 'prepare_media_install_verifier', 'smoke_audio_source_origin', 'verify_media_profile_install', 'finalize_media_profile_lab', 'run_media_profile_related', 'prepare_media_profile_skills', 'finalize_media_profile_audit', 'prepare_media_full_gate', 'native_index_release_tools', 'prepare_media_publication', 'publish_offline_media_profile', 'smoke_default_media_profile')
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
    names |= MODIFIED
    for prefix in (REL,ASSETS,WHEELHOUSE):
        names.update(path.relative_to(ROOT).as_posix() for path in (ROOT/prefix).rglob('*') if path.is_file())
    for name in names:
        path=ROOT/name;assert path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT),name
    return {name:sha(ROOT/name) for name in sorted(names)}


def dependency_inputs():
    base=ROOT/REL;captured=read(base/'wheelhouse-r1.json');directory=ROOT/captured['wheelhouse']
    assert sha(directory/'lock.json')==captured['lock_sha256']
    lock=read(directory/'lock.json')
    assert lock['target']=='cp313-win_amd64' and lock['runtime_profile']=='media-analysis-v1'
    assert len(lock['artifacts'])==8 and sum(row['runtime_dependency'] for row in lock['artifacts'])==7
    expected={directory/'lock.json':captured['lock_sha256']}
    for row in lock['artifacts']:
        path=directory/row['filename'];assert path.parent==directory and path.is_file() and not path.is_symlink()
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256']
        expected[path]=row['sha256']
    assert {p for p in directory.iterdir() if p.is_file()}==set(expected)
    assert len(expected)==9
    return {p.relative_to(ROOT).as_posix():digest for p,digest in expected.items()}

def source_audit():
    current=frozen();base=ROOT/REL;audit=read(base/'audit-r1.json')
    assert audit['status']=='passed-standalone-audit' and audit['targeted_methods']==260
    assert current==audit['frozen_inputs'] and len(current)==260
    for name,row in audit['media'].items():assert sha(ROOT/name)==row['sha256']
    assert len(audit['media'])==42 and audit['GIF_count']==14
    for key,name in (('media_manifest_sha256','media-manifest-r1.json'),('static_review_sha256','static-review-r1.json'),
        ('native_verification_sha256','native-r2/verification.json'),('isolated_verification_sha256','installed-r1/verification.json'),
        ('skill_draft_sha256','skills-draft-r1.json'),('wheelhouse_sha256','wheelhouse-r1.json'),('media_audit_sha256','media-audit-r1.json')):
        assert sha(base/name)==audit[key]
    related=read(base/'related-r1.json')
    assert related['status']=='passed-related-regressions' and related['terminal_ok'] and related['exit_code']==0
    assert related['methods']==related['distinct_methods']==260 and related['skipped']==0
    assert len(related['method_ids'])==len(set(related['method_ids']))==260
    assert related['frozen_before']==related['frozen_after']==current and related['frozen_equal']
    assert related['fixtures_unchanged'] and related['fixture_manifest_unchanged'] and related['scripts_unchanged']
    assert len(related['script_hashes'])==10 and len(related['fixture_inputs'])==8
    assert sha(base/'related-r1.json')==audit['related_sha256'] and sha(base/'related-r1.log')==related['log_sha256']
    assert sha(base/'foundation-r1.json')==related['fixture_manifest_sha256']
    for name,digest in related['script_hashes'].items():assert sha(ROOT/'scripts'/name)==digest
    for name,digest in related['fixture_inputs'].items():assert sha(ROOT/name)==digest
    installation=read(base/'installed-r1/verification.json')
    assert installation['status']=='passed' and installation['isolated_cli_calls']==26 and installation['module_origin_probes']==1
    assert installation['frozen_before']==installation['frozen_after']==current
    assert len(installation['checks'])==20 and all(row['ok'] for row in installation['checks'])
    assert len(installation['resource_hashes'])==161 and installation['bundle']['wheels']==8
    distribution=installation['numpy_distribution']
    assert distribution['base_bundle_includes_numpy'] and not distribution['host_site_copied']
    assert distribution['version']=='2.4.2' and len(distribution['original_wheel_files_except_rewritten_RECORD'])==931
    assert len(installation['installation']['audit']['modules'])==8 and len(distribution['native_audit']['extensions'])==2
    for name,digest in installation['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
    for name in ('native-r2/verification.json','installed-r1/media/verification.json'):
        item=read(base/name)
        assert item['status']=='passed' and item['cli_calls']==23 and item['native_commands']==32
        assert len(item['checks'])==39 and all(row['ok'] for row in item['checks'])
        assert item['frozen_before']==item['frozen_after']==current
        assert item['script_sha256']==sha(ROOT/'scripts/smoke_audio_source_origin.py')
    drafts=read(base/'skills-draft-r1.json')
    assert drafts['status']=='passed-four-unregistered-drafts' and drafts['skill_count']==4 and not drafts['registered']
    for row in drafts['skills'].values():
        assert sha(ROOT/row['path'])==row['sha256'] and row['validator_exit_code']==0 and not row['registered']
        assert sha(ROOT/row['parent_snapshot'])==row['parent_sha256']
    previous=read(base/'foundation-r1.json')['source_inputs']
    assert previous==audit['source_parent_inputs'] and len(previous)==259
    assert set(current)-set(previous)==ADDED
    assert {name for name in previous if previous[name]!=current[name]}==MODIFIED
    fixture=read(base/'external-fixtures-r1.json')
    assert fixture['status']=='passed' and fixture['fixture_count']==8
    for row in fixture['fixtures']:assert sha(ROOT/row['path'])==row['sha256']
    dependency_inputs()
    default=read(base/'default-profile-r1/verification.json')
    assert default['status']=='passed-default-wheelhouse-offline-bootstrap' and default['frozen_equal'] and default['dependency_inputs_equal']
    assert default['frozen_before']==default['frozen_after']==current
    assert default['dependency_inputs_before']==default['dependency_inputs_after']==dependency_inputs()
    assert len(default['checks'])==8 and all(row['ok'] for row in default['checks'])
    assert len(default['calls'])==3 and default['generator_sha256']==sha(ROOT/'scripts/smoke_default_media_profile.py')
    return current


def complete_gate(current):
    state=read(ROOT/'product/.runtime/offline-media-profile-20261021/full-after-audio-r1/run.json')
    assert state['status']=='passed-complete-suite-awaiting-reviewed-integration'
    full=read(ROOT/REL/'full-r1.json');alignment=read(ROOT/REL/'published-audio-alignment-r1.json')
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2043 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==current
    assert full['external_fixture_count']==8 and full['external_fixtures_equal'] and full['verification_scripts_equal']
    assert full['external_fixture_manifest_unchanged'] and state['full_sha256']==sha(ROOT/REL/'full-r1.json')
    assert len(state['verification_scripts'])==15
    for name,digest in state['verification_scripts'].items():assert sha(ROOT/'scripts'/name)==digest
    assert alignment['status']=='passed' and alignment['candidate_inputs']==current
    assert len(alignment['upstream_inputs'])==259 and alignment['remote_main']==alignment['published_commit']
    snapshots=read(ROOT/REL/'before-full-documents-r1.json');audit=read(ROOT/REL/'audit-r1.json')
    for name,row in snapshots['documents'].items():assert sha(ROOT/row['snapshot'])==row['sha256']==audit['documents'][name]
    dependencies=read(ROOT/REL/'full-dependencies-r1.json')
    assert dependencies['status']=='passed-dependency-artifact-freeze' and dependencies['artifact_count']==9
    assert dependencies['before']==dependencies['after']==state['dependency_artifact_inputs']==dependency_inputs()
    assert state['dependency_artifacts_unchanged'] and state['dependency_freeze_sha256']==sha(ROOT/REL/'full-dependencies-r1.json')
    assert dependencies['full_sha256']==sha(ROOT/REL/'full-r1.json')
    return full,alignment


def documents(root,full):
    seconds=full['suite_seconds']
    assert full['methods']==2043 and full['skipped']==0 and full['terminal_ok']
    message=(f'V89 八轮离线媒体运行时完成{full["methods"]}方法/{seconds:.3f}秒/0跳过的完整源码回归；'
        '260产品输入、8既有外部夹具、15验证脚本和9依赖文件（8上游artifact＋lock）前后相同。'
        '默认构建包含NumPy2.4.2，安装会实际执行原生矩阵/FFT核验；没有复制宿主NumPy。')
    def link(document,target):return os.path.relpath(root/target,(root/document).parent).replace('\\','/')
    rows=[
        ('V89-01','完整源码回归',f'{full["methods"]}方法/{seconds:.3f}秒/0跳过；260输入、8夹具、15脚本。全量为源码原生环境；新安装另有独立CLI证据。',REL+'/full-r1.json'),
        ('V89-02','固定依赖冻结','8上游artifact＋lock共9文件；包含7个运行时依赖及1个不发行的历史非运行时wheel。运行时加产品共8wheels。完整回归前后字节不变。',REL+'/full-dependencies-r1.json'),
        ('V89-03','相关回归','260不同方法/708.130秒/0跳过＝父226＋旧安装22＋新安装12。旧34及12属于此子集，不重复累计。',REL+'/related-r1.json'),
        ('V89-04','相同断言修复前后','同12方法修复前6FAIL/1ERROR/5控制通过，修复后12/1.004秒通过；原测试和错误日志保留。',REL+'/after-r1.json'),
        ('V89-05','正式离线NumPy交付','官方NumPy2.4.2/cp313 Windows x64；932RECORD文件核对。新安装中931原文件除pip重写RECORD外完全相同，原通知在包和安装中保留。',REL+'/wheelhouse-r1.json'),
        ('V89-06','新隔离安装及原生运算','8个依赖模块来源审计、两个NumPy.pyd均来自安装site；实际dot=285、2×2求解及FFT通过。20安装检查，无宿主site复制。',REL+'/installed-r1/verification.json'),
        ('V89-07','默认入口实际执行','不传--wheelhouse的新构建＋全新安装＋1次-I/-S隔离CLI，8检查通过；另一次独立运行，未重复执行媒体或并入完整方法数。',REL+'/default-profile-r1/verification.json'),
        ('V89-08','新原生及安装媒体','开发23CLI＋32其他命令/39检查；安装26CLI＋1来源进程/14模块、20安装＋39媒体检查。161产品资源源码/wheel/site同字节。',REL+'/installed-r1/verification.json'),
        ('V89-09','完整无损帧与PCM','原点0/5秒、首音频PTS1/6秒；每输出75帧/17,280,000RGBA字节、1,152,000float32PCM字节/每声道144000样本独立一致。视频切换显式选择参考主音轨。',REL+'/native-r2/verification.json'),
        ('V89-10','原片/MP4/GIF及静态审查','42资产/14GIF两次新生成。MP4各75帧、PTS=n/25、身份色块最大误差1。AAC每声道144384含填充；不作编码整帧/PCM一致或播放听审声明。',REL+'/media-manifest-r1.json'),
        ('V89-11','保留验证器失败','native-r1在0CLI时因旧audit路径停止，native-r2只重绑路径/260输入后通过；相关生成器相对路径失误在写runner前失败。产品源码没有因这些修复改变。',REL+'/audit-r1.json'),
        ('V89-12','Skills与范围','四Skill只合并新块与精确条款，并更新两份通用安装指引；17份总审。固定平台/版本限定；通用依赖求解、完整模型发行、自然/HDR/长片/RSS/播放听审及全部剪映功能效果仍待验收。',CONTRACT),
    ]
    for document in LATEST_DOCS:
        table='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
        table+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(document,target)+') |' for i,title,result,target in rows)
        gallery=''
        if document=='README.md':
            gallery=('\n\n原创CC0参考和真实输入：\n\n'
                '[参考原片]('+ASSETS+'/native-r2/source-reference.mkv) · '
                '[源输入0/1秒]('+ASSETS+'/native-r2/source-native.mkv) · '
                '[源输入5/6秒]('+ASSETS+'/native-r2/source-offset.mkv)\n\n'
                '![V89 原始参考]('+ASSETS+'/native-r2/source-reference.gif)\n\n'
                '![V89 实际保留音频起点]('+ASSETS+'/native-r2/native-output.gif)\n\n'
                '![V89 实际同步剪辑]('+ASSETS+'/native-r2/native-synced.gif)\n\n'
                '![V89 实际解码PCM]('+ASSETS+'/native-r2/native-decoded-PCM.png)\n\n'
                '[保留起点MP4]('+ASSETS+'/native-r2/native-output.mp4) · '
                '[同步MP4]('+ASSETS+'/native-r2/native-synced.mp4) · '
                '[非零原点输出]('+ASSETS+'/native-r2/offset-output.mp4) · '
                '[非零原点同步]('+ASSETS+'/native-r2/offset-synced.mp4) · '
                '[逐资产SHA]('+REL+'/media-manifest-r1.json)。GIF3000ms，可能合并相同帧且不含声音；只静看实际PCM图。\n\n'
                '当前默认离线入口（仓库内已含固定wheelhouse；需原生Windows CPython3.13x64、pip/setuptools及已有FFmpeg；每次选择新输出路径）：\n\n'
                '```powershell\n'
                '$avkMediaBundle = & C:/Python313/python.exe -I -B -X utf8 product/offline/build.py --output product/.runtime/offline-media-demo/bundle | ConvertFrom-Json\n'
                '$avkMediaInstaller = Join-Path $avkMediaBundle.bundle "install.py"\n'
                '& C:/Python313/python.exe -I -B -X utf8 $avkMediaInstaller --target product/.runtime/offline-media-demo/installed --manifest-sha256 $avkMediaBundle.manifest_sha256\n'
                '& C:/Python313/python.exe -I -S -B -X utf8 product/.runtime/offline-media-demo/installed/run.py capabilities\n'
                '```\n\n'
                '固定源文件见[source wheelhouse]('+WHEELHOUSE+'/lock.json)。开发来源下载有独立记录；构建/安装/运行使用本地文件。'
                '历史font-text-v1七轮演示及其NumPy复制属于旧版本记录，复现应绑定各自历史提交；当前产品使用八轮默认入口。')
        block(root/document,'### V89 八轮离线媒体运行时\n\n'+message+'\n\n'+table+gallery+
            '\n\n[完整实测]('+link(document,REPORT)+')。源码全量、子集、独立安装和默认入口命令分别报告，不累计为额外完整方法。')
    report='# 八轮离线媒体运行时实测（V89，2026-10-21）\n\n'+message+'\n\n'
    report+='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
    report+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(REPORT,target)+') |' for i,title,result,target in rows)
    report+='\n\n'+"""当前产品依赖声明新增NumPy>=2.4.2,<3。默认wheelhouse为sources/python-runtime/cp313-win_amd64-media。构建先核对目标、profile完整依赖集合与每个源SHA，再创建输出或调用pip；缺少或篡改NumPy在产品wheel构建前失败。新的media-analysis-v1发行包为产品＋7依赖共8wheels。core-v1和font-text-v1继续用于其依赖匹配的历史产品包；声明NumPy的产品不能借七轮包落入宿主环境。

源码仓库交付9个固定文件：8个上游artifact和lock，其中7个artifact用于运行时，一个历史rfc3339-validator记录不进入发行。所有SHA/大小、官方来源元数据与原许可均保全，完整回归前后核对不变。NumPy2.4.2固定wheel的932个RECORD文件已核对；安装中除pip重写RECORD外931个原始文件字节相同。NumPy原通知在bundle/licenses和安装site同时保留。元数据许可表达式为BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0；以各实际wheel所附原始通知为准。

安装使用本地wheel、--no-index/--no-deps/--require-hashes/--only-binary，完成后用-I/-S原生新进程审计8依赖模块来源，并实际执行NumPy矩阵点积、2×2求解和FFT；两个原生.pyd来源必须在安装site。新验证器删除了宿主NumPy复制函数。独立默认入口验证未传--wheelhouse，另完成2构建/安装命令与1隔离CLI/8检查；未重复执行39媒体检查，也未加入全量方法数。

媒体流程沿用音频起点工作流，适配仅改成当前audit路径及260输入绑定；没有改变画面/PCM期望算法。原生和新安装各新生成两组320×180/25fps/3秒原创CC0色卡、矩形数字和确定性音频。完整75帧和每声道144000无损样本匹配独立期望；安装资源161份与源码/wheel完全相同。MP4每个75帧，PTS=n/25，身份色块最大误差1；AAC每声道144384含填充，不主张编码整帧/PCM相同。两张实际PCM图静态目检，安装图像素一致；没有播放或听审。

首个native-r1在0CLI/0其他命令时因继承的旧内部audit路径缺失停止；保留原脚本和失败收据，native-r2只改输入绑定后通过。相关runner生成器因相对Path dot父目录未解析而在写文件前失败，修复绝对解析后只启动一次260相关方法。完整源码回归使用当前本机原生测试环境；26次新隔离CLI、默认入口与原生DLL审计是独立安装证据，不能宣称全部2043方法都跑在该安装site中。

本次固定cp313/Windows x64/NumPy2.4.2限定，不提供通用版本求解或全模型权重发行。自然/HDR/长片吞吐、总RSS、连续播放、听审和全部剪映功能效果仍未验收。开发阶段有官方开源固定wheel来源下载，产品构建/安装/运行没有在线依赖。没有Docker、WSL、容器或虚拟环境。
"""
    for title,target in (('历史实验及失败',HISTORICAL_REPORT),('契约',CONTRACT),('固定依赖lock',WHEELHOUSE+'/lock.json'),
        ('官方来源及SHA',REL+'/wheelhouse-r1.json'),('初次媒体失败',REL+'/native-r1/verification.json'),
        ('相关生成器失败',REL+'/related-preparation-failed-r1.json'),
        ('实际输入',ASSETS+'/native-r2/source-native.mkv'),('保留起点MP4',ASSETS+'/native-r2/native-output.mp4'),
        ('实际同步MP4',ASSETS+'/native-r2/native-synced.mp4')):
        report+='\n['+title+']('+link(REPORT,target)+')\n'
    report+='\n[NumPy官方固定版本](https://pypi.org/project/numpy/2.4.2/)\n'
    report+='\n![实际同步GIF]('+link(REPORT,ASSETS+'/native-r2/native-synced.gif')+')\n'
    report+='\n复现：scripts/verify_media_profile_install.py、scripts/smoke_default_media_profile.py；每次使用新输出目录。命令、源码副本与SHA见对应证据目录。\n'
    write(root/REPORT,report)
    constraints='\n'.join(line for line in (root/HISTORICAL_CONTRACT).read_text('utf8').splitlines() if line.startswith('|'))
    assert constraints.count('| MP-C')==10
    constraints=constraints.replace('| 未完成 |','| 本次完整源码回归已通过；生产接入、Skill审计和发布状态见实测 |')
    write(root/CONTRACT,'# 离线媒体运行时与NumPy交付（v0.1限定验收，2026-10-21）\n\n'+message+'\n\n'+constraints+
        '\n\n[完整源码、独立安装、默认入口和实际媒体](../validation/'+Path(REPORT).name+')。全量环境与新安装证据分别有效，版本/平台、模型和自然效果边界不变。')
    install_refresh={'video-cut-agent-editor': {'before': 'For font/text rendering use a `font-text-v1` bundle with seven pinned wheels,\nincluding Pillow; the historical six-wheel `core-v1` bundle lacks that dependency.', 'after': 'For the current product use the eight-wheel `media-analysis-v1` bundle with\nPillow and NumPy. The seven-wheel `font-text-v1` and six-wheel `core-v1` profiles\nreproduce dependency-compatible historical products only.'}, 'video-cut-quality': {'before': 'Font/text installers use the seven-wheel `font-text-v1` profile with Pillow;\nverify actual font ingestion under the isolated launcher, not host imports.', 'after': 'Current font/text installations use the eight-wheel `media-analysis-v1` profile\nwith Pillow and NumPy. Use seven-wheel `font-text-v1` only for matching historical\nproducts; verify actual font ingestion under the isolated launcher, not host imports.'}}
    drafts=read(ROOT/REL/'skills-draft-r1.json');assert set(drafts['skills'])==set(SKILLS);refresh=drafts['future_parent_refresh']
    for name,row in drafts['skills'].items():
        parent=root/'skills'/name/'SKILL.md';body=parent.read_text('utf8')
        assert body.count(refresh['before'])==1,(name,'Actual V88 NumPy guidance missing or duplicated')
        assert refresh['after'] not in body;body=body.replace(refresh['before'],refresh['after'])
        if name in install_refresh:
            clause=install_refresh[name];assert body.count(clause['before'])==1,(name,'Historical generic install guidance missing or duplicated')
            assert clause['after'] not in body;body=body.replace(clause['before'],clause['after'])
        write(parent,body)
        guidance=row['new_block'].replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        pending='This is an unregistered candidate; complete regression and main integration remain pending.'
        assert guidance.count(pending)==1;guidance=guidance.replace(pending,'')
        assert 'unregistered candidate' not in guidance and 'remain pending' not in guidance
        block(parent,guidance)
    attributes=(root/'.gitattributes').read_text('utf8')
    paths=[REL+'/** -text -whitespace',ASSETS+'/** -text -whitespace',WHEELHOUSE+'/** -text -whitespace']
    paths += [name+' -text whitespace=cr-at-eol' for name in sorted(MODIFIED)]
    paths += [f'product/tests/{name}.py -text whitespace=cr-at-eol' for name in TESTS]
    paths += [f'scripts/{name}.py -text whitespace=cr-at-eol' for name in SCRIPTS]
    write(root/'.gitattributes',attributes+'\n# V89 exact tested offline media runtime and distributable wheels.\n'+'\n'.join(paths))
    return {*LATEST_DOCS,REPORT,CONTRACT,'.gitattributes',*('skills/'+name+'/SKILL.md' for name in SKILLS)}





def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--preflight-only', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    assert work.is_relative_to(ROOT / 'product/.runtime') and (not work.exists())
    work.mkdir(parents=True)
    state = {'status': 'checking-source', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'calls': [], 'force_push': False}

    def checkpoint():
        save(work / 'run.json', state)
    try:
        current = source_audit()
        reviewed = source_files()
        state.update(status='passed-source-preflight-awaiting-full', frozen_inputs=current, source_files=reviewed)
        checkpoint()
        if args.preflight_only:
            return
        full, alignment = complete_gate(current)
        base = alignment['published_commit']
        assert git(MAIN, 'branch', '--show-current').decode().strip() == 'main'
        assert git(MAIN, 'rev-parse', 'HEAD').decode().strip() == base
        assert git(MAIN, 'remote', 'get-url', 'origin').decode().strip() == 'git@github.com:Tonscriptions/agent-video-kit.git'
        assert git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0] == base
        assert not git(MAIN, 'status', '--porcelain', '-z'), 'Preserve unexpected main changes; no implicit integration'
        spec = importlib.util.spec_from_file_location('nested_native_main_freeze', MAIN / 'scripts/run_frozen_regression.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        assert module.frozen() == alignment['upstream_inputs']
        tracked = {p.decode('utf8') for p in git(MAIN, 'ls-files', '-z').split(b'\x00') if p}
        generated = {REPORT, CONTRACT, REL + '/skills-release-r1.json', REL + '/release-main-r1.json', REL + '/publication-copy-r1.json', REL + '/staged-release-r1.json'}
        for name in set(reviewed) | generated:
            path = MAIN / name
            assert path.resolve().is_relative_to(MAIN) and (not path.is_symlink())
            assert name in tracked or not path.exists(), 'Existing untracked destination: ' + name
        assert source_files() == reviewed and frozen() == current
        state.update(status='copying-reviewed-source', base_commit=base)
        checkpoint()
        for name, digest in reviewed.items():
            target = MAIN / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
            assert sha(target) == digest, name
        assert module.frozen() == current
        modified_docs = documents(MAIN, full)
        command = [sys.executable, '-E', '-B', '-X', 'utf8', str(MAIN / 'scripts/audit_source_edit_skills.py'), '--expected-count', '17', '--output', str(MAIN / REL / 'skills-release-r1.json')]
        result = subprocess.run(command, cwd=MAIN, capture_output=True, timeout=600)
        (work / 'main-skills.stdout.log').write_bytes(result.stdout)
        (work / 'main-skills.stderr.log').write_bytes(result.stderr)
        state['calls'].append({'command': command, 'exit_code': result.returncode})
        checkpoint()
        assert result.returncode == 0
        skills = read(MAIN / REL / 'skills-release-r1.json')
        mapping_path = MAIN / 'video-cut-install-manifest.json'
        mapping = read(mapping_path)
        mapping.setdefault('audit_history', []).append(mapping['current_audit'])
        for entry in mapping['skills']:
            row = next((item for item in skills['results'] if item['skill'] == entry['name']))
            old, new = (entry['skill_md_sha256'], row['sha256'][7:])
            if old != new:
                entry.setdefault('skill_md_sha256_history', []).append(old)
                entry['previous_manifest_skill_md_sha256'] = old
            entry.update(skill_md_sha256=new, validation=row['validator_stdout'], prefix_verified=True, registration_verified=True)
            assert Path(entry['canonical_directory']).resolve() == (MAIN / 'skills' / entry['name']).resolve()
        mapping['current_audit'] = {'date': '2026-10-21', 'skill_count': 17, 'local_links_checked': skills['local_links_checked'], 'record': REL + '/skills-release-r1.json', 'record_sha256': sha(MAIN / REL / 'skills-release-r1.json'), 'previous_hashes_preserved': True, 'semantics': 'V89 media-analysis-v1 eight-wheel offline runtime including pinned NumPy; native operation/origin audit and tracked complete wheelhouse; no full CapCut parity acceptance'}
        save(mapping_path, mapping)
        links = []
        for name in sorted(modified_docs - {'.gitattributes'}):
            path = MAIN / name
            text = path.read_text('utf8')
            if name in LATEST_DOCS or name.startswith('skills/'):
                text = text.split('<!-- ' + MARKER + ' -->')[1].split('<!-- /' + MARKER + ' -->')[0]
            for token in re.findall('!?\\[[^\\]]*\\]\\(([^)\\n]+)\\)', text):
                target = token.strip('<>').split('#', 1)[0]
                if not target or re.match('^[a-zA-Z][\\w+.-]*:', target):
                    continue
                resolved = (path.parent / target).resolve()
                assert resolved.is_relative_to(MAIN) and resolved.exists(), (name, token)
                links.append({'document': name, 'target': resolved.relative_to(MAIN).as_posix()})
        for name, digest in current.items():
            assert sha(MAIN / name) == digest
        for name, row in full['external_fixtures_expected'].items():
            assert sha(MAIN / name) == row['sha256']
        save(MAIN / REL / 'release-main-r1.json', {'status': 'passed-main-byte-and-document-audit', 'base_commit': base, 'frozen_inputs': current, 'full_methods': 2043, 'full_skipped': 0, 'full_sha256': sha(MAIN / REL / 'full-r1.json'), 'targeted_methods': 260, 'resources': 161, 'skills': 17, 'local_links': links, 'documents': {name: sha(MAIN / name) for name in sorted(modified_docs)}, 'generator_sha256': sha(Path(__file__))})
        save(MAIN / REL / 'publication-copy-r1.json', {'status': 'passed-reviewed-copy', 'source': str(ROOT), 'copied_files': reviewed, 'frozen_inputs': current, 'base_commit': base})
        changed = {p.decode('utf8') for p in git(MAIN, 'diff', '--name-only', '-z').split(b'\x00') if p}
        changed.update((p.decode('utf8') for p in git(MAIN, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\x00') if p))
        allowed = set(reviewed) | modified_docs | generated | {'video-cut-install-manifest.json'}
        assert changed <= allowed, sorted(changed - allowed)
        stage = work / 'stage-paths.nul'
        stage.write_bytes(b'\x00'.join((name.encode('utf8') for name in sorted(changed))) + b'\x00')
        git(MAIN, 'add', '--pathspec-from-file=' + str(stage), '--pathspec-file-nul')
        git(MAIN, 'add', '--renormalize', '--pathspec-from-file=' + str(stage), '--pathspec-file-nul')
        assert not git(MAIN, 'diff', '--name-only')
        assert {p.decode('utf8') for p in git(MAIN, 'diff', '--cached', '--name-only', '-z').split(b'\x00') if p} == changed
        git(MAIN, 'diff', '--cached', '--check')
        rows = staged_rows({**{name: sha(MAIN / name) for name in changed}, **current})
        receipt = REL + '/staged-release-r1.json'
        save(MAIN / receipt, {'status': 'passed', 'frozen_files': 260, 'compared_blobs': len(rows), 'files': rows, 'all_staged_bytes_equal_workspace': True, 'all_frozen_bytes_equal_staged': True, 'stream_buffer_bytes': 65536, 'full_sha256': sha(MAIN / REL / 'full-r1.json'), 'base_commit': base})
        git(MAIN, 'add', '--', receipt)
        staged_rows({receipt: sha(MAIN / receipt)})
        assert module.frozen() == current and (not git(MAIN, 'diff', '--name-only'))
        git(MAIN, 'diff', '--cached', '--check')
        state.update(status='passed-staged-audit')
        checkpoint()
        git(MAIN, 'commit', '--quiet', '-m', 'feat: ship verified NumPy in the default offline media runtime')
        commit = git(MAIN, 'rev-parse', 'HEAD').decode().strip()
        assert git(MAIN, 'rev-parse', 'HEAD^').decode().strip() == base
        state.update(status='committed-awaiting-ordinary-push', commit=commit)
        checkpoint()
        git(MAIN, 'push', 'origin', 'main')
        remote = git(MAIN, 'ls-remote', 'origin', 'refs/heads/main').decode().split()[0]
        assert remote == commit and (not git(MAIN, 'status', '--porcelain', '-z')) and (module.frozen() == current)
        state.update(status='published', remote_main=remote, main_clean=True, full_methods=2043)
    except BaseException as caught:
        state.update(status='failed', error={'type': type(caught).__name__, 'message': str(caught)})
        raise
    finally:
        checkpoint()
        print(json.dumps({k: state.get(k) for k in ('status', 'commit', 'remote_main', 'error')}, ensure_ascii=False), flush=True)


if __name__=='__main__':main()
