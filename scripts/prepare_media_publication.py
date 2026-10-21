"""Prepare a nineteen-script publisher with all pinned source wheels and default bootstrap evidence."""
import ast
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
DONOR=ROOT.parent/'audio-source-origin-lab-20261021'
REL='docs/validation/evidence/offline-media-profile-20261021-lab'
TARGET=ROOT/'scripts/publish_offline_media_profile.py'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def function(source,name):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(source,node)


def replace_function(source,name,body):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    lines=source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+body+'\n'+''.join(lines[node.end_lineno:])


def assign(source,name,value):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    lines=source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+name+'='+repr(value)+'\n'+''.join(lines[node.end_lineno:])


DOCUMENTS=r'''def documents(root,full):
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
'''


def main():
    output=ROOT/REL/'publication-preparation-r1.json';assert not output.exists() and not TARGET.exists()
    current=frozen();audit=json.loads((ROOT/REL/'audit-r1.json').read_bytes());assert current==audit['frozen_inputs'] and len(current)==260
    donor=DONOR/'scripts/publish_audio_source_origin.py';original=donor.read_text('utf8');source=original
    launcher=(ROOT/'scripts/run_offline_media_after_parent.py').read_text('utf8')
    assignment=next(n for n in ast.parse(launcher).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCRIPTS' for t in n.targets))
    approved=tuple(name[:-3] for name in ast.literal_eval(assignment.value))+('native_index_release_tools','prepare_media_publication','publish_offline_media_profile','smoke_default_media_profile')
    assert len(approved)==len(set(approved))==19
    constants={'REL':REL,'ASSETS':'docs/assets/offline-media-profile-20261021-lab',
        'REPORT':'docs/validation/八轮离线媒体运行时实测_2026-10-21.md','CONTRACT':'docs/specs/离线媒体运行时与NumPy交付_v0.1_2026-10-21.md',
        'HISTORICAL_REPORT':'docs/validation/八轮离线媒体运行时独立实验_2026-10-21.md',
        'HISTORICAL_CONTRACT':'docs/specs/离线媒体运行时与NumPy交付_实验_v0.1_2026-10-21.md',
        'MARKER':'V89-OFFLINE-MEDIA-PROFILE','MODIFIED':{'product/offline/build.py','product/offline/install.py','product/pyproject.toml'},
        'ADDED':{'product/tests/test_offline_media_profile.py'},'MODULES':(),'TESTS':('test_offline_media_profile',),'SCRIPTS':approved}
    for name,value in constants.items():source=assign(source,name,value)
    source=source.replace("ROOT=Path(__file__).resolve().parents[1]","ROOT=Path(__file__).resolve().parents[1]\nWHEELHOUSE='sources/python-runtime/cp313-win_amd64-media'",1)
    files=function(original,'source_files')
    files=files.replace("    for prefix in (REL,ASSETS):","    names |= MODIFIED\n    for prefix in (REL,ASSETS,WHEELHOUSE):")
    source=replace_function(source,'source_files',files)
    source_audit=function(launcher,'source_gate').replace('def source_gate():','def source_audit():',1)
    before="    for name,digest in audit['documents'].items():assert sha(ROOT/name)==digest\n";assert source_audit.count(before)==1;source_audit=source_audit.replace(before,'')
    before="return current,previous,{name:sha(ROOT/'scripts'/name) for name in SCRIPTS}";assert source_audit.count(before)==1
    default="""default=read(base/'default-profile-r1/verification.json')
    assert default['status']=='passed-default-wheelhouse-offline-bootstrap' and default['frozen_equal'] and default['dependency_inputs_equal']
    assert default['frozen_before']==default['frozen_after']==current
    assert default['dependency_inputs_before']==default['dependency_inputs_after']==dependency_inputs()
    assert len(default['checks'])==8 and all(row['ok'] for row in default['checks'])
    assert len(default['calls'])==3 and default['generator_sha256']==sha(ROOT/'scripts/smoke_default_media_profile.py')
    return current"""
    source_audit=source_audit.replace(before,default)
    source=replace_function(source,'source_audit',function(launcher,'dependency_inputs')+'\n\n'+source_audit)
    gate=function(original,'complete_gate')
    changes={'audio-source-origin-20261021/full-after-stream-r1':'offline-media-profile-20261021/full-after-audio-r1',
        'published-stream-alignment-r1':'published-audio-alignment-r1',"full['methods']==2031":"full['methods']==2043",
        "len(state['verification_scripts'])==18":"len(state['verification_scripts'])==15",
        "len(alignment['upstream_inputs'])==258":"len(alignment['upstream_inputs'])==259"}
    for before,after in changes.items():assert gate.count(before)==1,before;gate=gate.replace(before,after)
    before='    return full,alignment';assert gate.count(before)==1
    extra="""    dependencies=read(ROOT/REL/'full-dependencies-r1.json')
    assert dependencies['status']=='passed-dependency-artifact-freeze' and dependencies['artifact_count']==9
    assert dependencies['before']==dependencies['after']==state['dependency_artifact_inputs']==dependency_inputs()
    assert state['dependency_artifacts_unchanged'] and state['dependency_freeze_sha256']==sha(ROOT/REL/'full-dependencies-r1.json')
    assert dependencies['full_sha256']==sha(ROOT/REL/'full-r1.json')
"""
    source=replace_function(source,'complete_gate',gate.replace(before,extra+before))
    source=replace_function(source,'documents',DOCUMENTS)
    main_tree=ast.parse(function(original,'main'))
    class UpdateMain(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in {226,259,2031}:
                return ast.copy_location(ast.Constant(value={226:260,259:260,2031:2043}[node.value]),node)
            if isinstance(node.value,str):
                if node.value.startswith('V88 demux-relative native PCM'):
                    return ast.copy_location(ast.Constant(value='V89 media-analysis-v1 eight-wheel offline runtime including pinned NumPy; native operation/origin audit and tracked complete wheelhouse; no full CapCut parity acceptance'),node)
                if node.value=='fix: retain native audio source origins across editing and sync':
                    return ast.copy_location(ast.Constant(value='feat: ship verified NumPy in the default offline media runtime'),node)
            return node
    source=replace_function(source,'main',ast.unparse(ast.fix_missing_locations(UpdateMain().visit(main_tree))))
    source=source.replace('Publish native PCM source-clock bytes after the actual2031 complete suite.',
        'Publish the complete offline media runtime after actual2043 and default bootstrap validation.')
    compile(ast.parse(source),str(TARGET),'exec');assert 'sha(Path(__file__))' in source
    unchanged={name:ast.dump(ast.parse(function(original,name)),include_attributes=False)==ast.dump(ast.parse(function(source,name)),include_attributes=False) for name in ('read','write','save','block')}
    assert all(unchanged.values())
    helper=ROOT/'scripts/native_index_release_tools.py';assert not helper.exists();helper.write_bytes((DONOR/'scripts/native_index_release_tools.py').read_bytes())
    TARGET.write_text(source,encoding='utf8',newline='\n');assert frozen()==current
    record={'status':'prepared-not-published','approved_script_count':19,'frozen_inputs':current,
        'donor_script':str(donor),'donor_sha256':sha(donor),'shared_helpers_AST_unchanged':unchanged,
        'publisher_sha256':sha(TARGET),'shared_release_helper_sha256':sha(helper),
        'requires_actual_full_methods':2043,'requires_actual_published_parent_methods':2031,
        'tracked_wheelhouse_files':9,'default_bootstrap_required':True,'ordinary_push_only':True,
        'main_changed':False,'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','approved_script_count','requires_actual_full_methods','tracked_wheelhouse_files','main_changed')}))


if __name__=='__main__':main()
