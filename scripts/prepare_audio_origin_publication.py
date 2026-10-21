"""Prepare a publisher that requires the actual frozen2031 suite and published V87 parent."""
import ast
import hashlib
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
DONOR=ROOT.parent/'multicam-stream-coverage-lab-20261021'
REL='docs/validation/evidence/audio-source-origin-20261021-lab'
TARGET=ROOT/'scripts/publish_audio_source_origin.py'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def function(source,name):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return ast.get_source_segment(source,node)


def replace_function(source,name,value):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name==name)
    lines=source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+value+'\n'+''.join(lines[node.end_lineno:])


def assign(source,name,value):
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
    lines=source.splitlines(keepends=True)
    return ''.join(lines[:node.lineno-1])+name+'='+repr(value)+'\n'+''.join(lines[node.end_lineno:])


DOCUMENTS=r'''def documents(root,full):
    seconds=full['suite_seconds']
    assert full['methods']==2031 and full['skipped']==0 and full['terminal_ok']
    message=(f'V88 原生音频起点与同步已完成 {full["methods"]} 方法、{seconds:.3f} 秒、0 跳过的完整回归；'
        '259 产品输入、8 已提交外部夹具和18份验证脚本前后相同。'
        '源音频首先按 demux 相对 PTS 保留前置静音，再选择、反向、变速或分析同步；不启用 async 漂移校正。')
    def link(document,target):return os.path.relpath(root/target,(root/document).parent).replace('\\','/')
    rows=[
        ('V88-01','完整回归',f'{full["methods"]} 方法/{seconds:.3f}秒/0跳过；259输入、8夹具、18脚本。',REL+'/full-r1.json'),
        ('V88-02','当前相关检查','226个不同方法：12本轮＋104父相关＋110既有音频方法。是完整套件子集，各次12方法不重复累计。',REL+'/related-r1.json'),
        ('V88-03','修复前后相同控制','同12方法：修复前7FAIL/1ERROR/4通过；修复后12通过。中间两次各1个置信度断言失败，均保留。',REL+'/after-controls-r3.json'),
        ('V88-04','真实源时钟','容器原点0/5秒，音频首PTS1/6秒，两例均有1秒相对缺口；零原点及等原点不得增加错误静音。',REL+'/native-r1/verification.json'),
        ('V88-05','完整无损样本与帧','每个输出75帧、17,280,000 RGBA字节；立体声float32 PCM 1,152,000字节/每声道144000样本，与独立期望完全相同。',REL+'/native-r1/verification.json'),
        ('V88-06','同步与显式主音轨','实际CLI偏移1秒，原速source[1,3)放置reference[0,2)，末25帧保留背景；显式作者参考主音轨。score=1仅为此确定性样例。',REL+'/installed-r1/media/verification.json'),
        ('V88-07','原生与新隔离安装','原生23CLI＋32其他命令/39检查；隔离26CLI＋1来源进程/14模块、15安装＋39媒体检查；161资源同字节。',REL+'/installed-r1/verification.json'),
        ('V88-08','离线依赖范围','7基础wheel不含NumPy；隔离实测只读复制现有NumPy2.4.2的933个RECORD/许可文件，不能视为安装器已内置。',REL+'/installed-r1/verification.json'),
        ('V88-09','观看副本与静态目检','42资产/14GIF来自两次新生成；实际MP4各75帧、PTS=n/25、身份色块最大误差1。AAC解码每声道144384样本，编码填充单列。',REL+'/media-manifest-r1.json'),
        ('V88-10','反向/曲线/嵌套/R3','实际R3输入/输出帧和全静音选区检查；不代表R3输出全PCM相同或听感/音高/立体声相位质量已验收。',REL+'/after-controls-r3.json'),
        ('V88-11','保留失败与研究边界','最早观察夹具字段错误的渲染结果无效，另有更正后的before-r2；未执行smoke缺import及检查点编码拼写错误均保留，不归为产品故障。',REL+'/audit-r1.json'),
        ('V88-12','Skill及尚缺验收','四Skill仅增量＋精确父版条款更新，17份再审。压缩priming/edit-list、负/不连续时间戳、漂移、自然/HDR/长片/RSS/播放听审与完整剪映等价未验收。',CONTRACT),
    ]
    for document in LATEST_DOCS:
        table='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
        table+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(document,target)+') |' for i,title,result,target in rows)
        gallery=''
        if document=='README.md':
            gallery=('\n\n原创CC0参考、真实输入和实际输出：\n\n'
                '[参考MKV]('+ASSETS+'/native-r1/source-reference.mkv) · '
                '[原点0/音频1秒输入]('+ASSETS+'/native-r1/source-native.mkv) · '
                '[原点5/音频6秒输入]('+ASSETS+'/native-r1/source-offset.mkv)\n\n'
                '![V88 参考原片]('+ASSETS+'/native-r1/source-reference.gif)\n\n'
                '保留源起点的实际MP4及其解码GIF：\n\n'
                '![V88 源音频起点]('+ASSETS+'/native-r1/native-output.gif)\n\n'
                '按实际偏移剪辑并显式使用参考主音轨：\n\n'
                '![V88 同步剪辑]('+ASSETS+'/native-r1/native-synced.gif)\n\n'
                '![V88 实际解码PCM采样图]('+ASSETS+'/native-r1/native-decoded-PCM.png)\n\n'
                '[保留起点MP4]('+ASSETS+'/native-r1/native-output.mp4) · '
                '[同步MP4]('+ASSETS+'/native-r1/native-synced.mp4) · '
                '[非零原点输出]('+ASSETS+'/native-r1/offset-output.mp4) · '
                '[非零原点同步]('+ASSETS+'/native-r1/offset-synced.mp4) · '
                '[逐资产SHA]('+REL+'/media-manifest-r1.json)。'
                'GIF各3000ms、可能合并相同帧、不含声音；图来自真实解码PCM。静态目检不等于播放或听审。'
                '编码MP4/AAC不声明完整RGBA/PCM字节一致。')
        block(root/document,'### V88 原生音频起点与同步\n\n'+message+'\n\n'+table+gallery+
            '\n\n[完整实测]('+link(document,REPORT)+')。完整套件、方法子集、CLI命令和安装检查分开报告。')
    report='# 原生音频起点与同步实测（V88，2026-10-21）\n\n'+message+'\n\n'
    report+='| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
    report+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(REPORT,target)+') |' for i,title,result,target in rows)
    report+='\n\n'+"""物理源音频在选择前采用 aresample first_pts=0，以容器解封装原点为零保留起点缺口。普通选区、反向、曲线和嵌套沿用同一时钟；R3在上下文选区前规范化解码，source_audio_clock与当前实现SHA进入计划身份。没有启用async，也不代表处理了中间时间戳断裂或设备漂移。

同步source_time=reference_time+relative_delay_seconds。包络仍是50Hz；相关分数使用实际重叠窗口的Pearson，并排除无共同前史的一阶差分首点，至少保留1秒物理重叠。分数不是概率，也不是自然素材校准、语义镜头决定或漂移估计。音频时钟与V87视频覆盖独立：正确偏移不会凭空扩展视频边界。

实际原生和新隔离安装分别生成两组320×180/25fps/3秒素材。容器原点0/5秒、音频首PTS1/6秒，完整无损输出分别核对全部75帧和每声道144000采样。同步输出的末25帧保留背景；音轨由作者显式选择参考，切换视频不隐式选择主音频。dry-run核对所有工程文件字节不变。

四个观看输出各75帧、PTS=n/25、身份色块最大误差1；AAC解码每声道144384，含编码填充，不与无损PCM作字节一致声明。14GIF总时长各3000ms；输出GIF来自实际MP4解码，源GIF只展示实际源帧。两张实际PCM图做静态目检，安装图像素一致，没有播放或听审。全部素材为本项目原创CC0矩形字形、色卡及确定性音频，没有外部字体/图像。

基础离线7wheels不含NumPy。隔离实验仅把既有本地NumPy2.4.2的933个RECORD核对文件及许可只读复制到E盘安装site；这不能写成产品安装器已解决NumPy发行。当前没有新增运行依赖、在线模型或远程provider。

修复前同12方法为7FAIL/1ERROR/4通过，其中实际R3源长度错误。两次中间修复各剩1个分数断言失败，最终12/8.890秒通过；测试正文不变。226个相关方法包括父104与110既有音频方法，不和12控制重复累计。最早before-r1夹具把kind写成type，其渲染观察无效；更正before-r2后才归因原渲染器。初始smoke生成器缺NumPy导入，在执行前修正，保留原未执行脚本。检查点编码名utf8-sig拼写错误也保留，未改变产品源码。

压缩编解码priming/edit-list、负时间戳、内部不连续、设备漂移、自然录音歧义、HDR、长片吞吐与总RSS、连续播放和听审仍须分别验收。R3当前控制不代表输出音高/相位/听感等价。全部剪映功能及效果仍未验收。原生Windows，无Docker/WSL/容器/虚拟环境。
"""
    for title,target in (('历史实验及失败',HISTORICAL_REPORT),('契约',CONTRACT),
        ('修复前12方法',REL+'/before-controls-r1.json'),
        ('有效修复前观察',REL+'/before-r2/observations.json'),
        ('更正前无效渲染观察',REL+'/before-r1/observations.json'),
        ('未执行初稿',REL+'/smoke-preparation-r1-unexecuted.py.txt'),
        ('检查点失败',REL+'/checkpoint-failed-r1.json'),
        ('真实原片',ASSETS+'/native-r1/source-native.mkv'),
        ('实际保留起点MP4',ASSETS+'/native-r1/native-output.mp4'),
        ('实际同步MP4',ASSETS+'/native-r1/native-synced.mp4')):
        report+='\n['+title+']('+link(REPORT,target)+')\n'
    report+='\n![实际同步GIF]('+link(REPORT,ASSETS+'/native-r1/native-synced.gif')+')\n'
    report+='\n复现：scripts/smoke_audio_source_origin.py 与 scripts/verify_audio_source_origin_install.py；对应证据目录保存精确命令、脚本、日志与SHA。\n'
    write(root/REPORT,report)
    constraints='\n'.join(line for line in (root/HISTORICAL_CONTRACT).read_text('utf8').splitlines() if line.startswith('|'))
    assert constraints.count('| AO-C')==10
    constraints=constraints.replace('CLI/媒体/隔离已完成；Skill/完整套件/生产发布未完成',
        'CLI/媒体/隔离与完整套件已完成；本次接入生产，Skill总审计和发布状态见实测')
    write(root/CONTRACT,'# 原生音频起点与作者采样时钟（v0.1限定验收，2026-10-21）\n\n'+message+'\n\n'+constraints+
        '\n\n[实际原生/安装、原片/GIF与失败记录](../validation/'+Path(REPORT).name+')。AO-C08的缓存身份完整产品重放、AO-C10自然质量等边界仍分别有效。')
    drafts=read(ROOT/REL/'skills-draft-r1.json');assert set(drafts['skills'])==set(SKILLS)
    refresh=drafts['future_parent_refresh']
    for name,row in drafts['skills'].items():
        parent=root/'skills'/name/'SKILL.md';body=parent.read_text('utf8')
        assert body.count(refresh['before'])==1,(name,'Actual V87 guidance clause missing or duplicated')
        assert refresh['after'] not in body
        write(parent,body.replace(refresh['before'],refresh['after']))
        guidance=row['new_block'].replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        pending='This is an unregistered candidate; complete regression and main integration remain pending.'
        assert guidance.count(pending)==1;guidance=guidance.replace(pending,'')
        assert 'unregistered candidate' not in guidance and 'remain pending' not in guidance
        block(parent,guidance)
    attributes=(root/'.gitattributes').read_text('utf8')
    paths=[REL+'/** -text -whitespace',ASSETS+'/** -text -whitespace']
    paths += [f'product/src/ai_ad_editor/{name}.py -text whitespace=cr-at-eol' for name in MODULES]
    paths += [f'product/tests/{name}.py -text whitespace=cr-at-eol' for name in TESTS]
    paths += [f'scripts/{name}.py -text whitespace=cr-at-eol' for name in SCRIPTS]
    write(root/'.gitattributes',attributes+'\n# V88 exact tested native PCM source-clock bytes.\n'+'\n'.join(paths))
    return {*LATEST_DOCS,REPORT,CONTRACT,'.gitattributes',*('skills/'+name+'/SKILL.md' for name in SKILLS)}
'''


def main():
    assert not TARGET.exists()
    output=ROOT/REL/'publication-preparation-r1.json';assert not output.exists()
    current=frozen();audit=json.loads((ROOT/REL/'audit-r1.json').read_bytes())
    assert audit['status']=='passed-standalone-audit' and current==audit['frozen_inputs'] and len(current)==259
    donor_path=DONOR/'scripts/publish_multicam_stream_coverage.py';original=donor_path.read_text('utf8');source=original
    launcher=(ROOT/'scripts/run_audio_origin_after_parent.py').read_text('utf8')
    scripts=next(n for n in ast.parse(launcher).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SCRIPTS' for t in n.targets))
    pins=ast.literal_eval(scripts.value)
    approved=tuple(name[:-3] for name in pins)+('native_index_release_tools','prepare_audio_origin_publication','publish_audio_source_origin')
    assert len(approved)==len(set(approved))==21
    constants={'REL':REL,'ASSETS':'docs/assets/audio-source-origin-20261021-lab',
        'REPORT':'docs/validation/原生音频起点与同步实测_2026-10-21.md',
        'CONTRACT':'docs/specs/原生音频起点与作者采样时钟_v0.1_2026-10-21.md',
        'HISTORICAL_REPORT':'docs/validation/原生音频起点与同步独立实验_2026-10-21.md',
        'HISTORICAL_CONTRACT':'docs/specs/原生音频起点与作者采样时钟_实验_v0.1_2026-10-21.md',
        'MARKER':'V88-NATIVE-AUDIO-SOURCE-ORIGIN',
        'MODIFIED':{'product/src/ai_ad_editor/'+n+'.py' for n in ('multicam','render','audio_stretch','capabilities')},
        'ADDED':{'product/tests/test_audio_source_origin.py'},'MODULES':('multicam','render','audio_stretch','capabilities'),
        'TESTS':('test_audio_source_origin',),'SCRIPTS':approved}
    for name,value in constants.items():source=assign(source,name,value)
    source_audit=function(launcher,'source_gate').replace('def source_gate():','def source_audit():',1)
    before="    for name,digest in audit['documents'].items():assert sha(ROOT/name)==digest\n"
    assert source_audit.count(before)==1;source_audit=source_audit.replace(before,'')
    before="return current,previous,{name:sha(ROOT/'scripts'/name) for name in SCRIPTS}"
    assert source_audit.count(before)==1;source_audit=source_audit.replace(before,'return current')
    source=replace_function(source,'source_audit',source_audit)
    gate=function(original,'complete_gate')
    changes={
        'multicam-stream-coverage-20261021/full-after-multicam-r1':'audio-source-origin-20261021/full-after-stream-r1',
        'published-multicam-alignment-r1':'published-stream-alignment-r1',
        "full['methods']==2019":"full['methods']==2031",
        "len(state['verification_scripts'])==15":"len(state['verification_scripts'])==18",
        "len(alignment['upstream_inputs'])==257":"len(alignment['upstream_inputs'])==258"}
    for before,after in changes.items():assert gate.count(before)==1,before;gate=gate.replace(before,after)
    source=replace_function(source,'complete_gate',gate)
    source=replace_function(source,'documents',DOCUMENTS)
    main_tree=ast.parse(function(original,'main'))
    class UpdateMain(ast.NodeTransformer):
        def visit_Constant(self,node):
            if type(node.value) is int and node.value in {104,258,2019}:
                return ast.copy_location(ast.Constant(value={104:226,258:259,2019:2031}[node.value]),node)
            if isinstance(node.value,str):
                if node.value.startswith('V87 native video intervals'):
                    return ast.copy_location(ast.Constant(value='V88 demux-relative native PCM source origin before selection, reverse, speed curves, nested/R3 and multicam envelopes; no async/drift or full CapCut parity acceptance'),node)
                if node.value=='fix: use native video intervals for multicamera coverage':
                    return ast.copy_location(ast.Constant(value='fix: retain native audio source origins across editing and sync'),node)
            return node
    adapted=ast.unparse(ast.fix_missing_locations(UpdateMain().visit(main_tree)))
    source=replace_function(source,'main',adapted)
    source=source.replace('Publish frozen multicamera source-coverage bytes after the exact complete suite.',
        'Publish native PCM source-clock bytes after the actual2031 complete suite.')
    compile(ast.parse(source),str(TARGET),'exec')
    unchanged={}
    for name in ('read','write','save','block','source_files'):
        unchanged[name]=ast.dump(ast.parse(function(original,name)),include_attributes=False)==ast.dump(ast.parse(function(source,name)),include_attributes=False)
    assert all(unchanged.values()) and 'sha(Path(__file__))' in source
    helper=ROOT/'scripts/native_index_release_tools.py';donor_helper=DONOR/'scripts/native_index_release_tools.py'
    if helper.exists():assert sha(helper)==sha(donor_helper)
    else:helper.write_bytes(donor_helper.read_bytes())
    TARGET.write_text(source,encoding='utf8',newline='\n')
    assert frozen()==current
    record={'status':'prepared-not-published','approved_script_count':21,'frozen_inputs':current,
        'donor_script':str(donor_path),'donor_sha256':sha(donor_path),'shared_helpers_AST_unchanged':unchanged,
        'shared_release_helper_sha256':sha(helper),'shared_release_helper_unchanged':True,
        'publisher':TARGET.relative_to(ROOT).as_posix(),'publisher_sha256':sha(TARGET),
        'requires_actual_full_methods':2031,'requires_actual_published_parent_methods':2019,
        'ordinary_push_only':True,'main_changed':False,'generator_sha256':sha(__file__)}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:record[k] for k in ('status','approved_script_count','requires_actual_full_methods','requires_actual_published_parent_methods','main_changed')}))


if __name__=='__main__':main()
