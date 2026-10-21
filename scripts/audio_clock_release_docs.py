"""Project actual source-audio evidence into release docs; previews cannot write main."""
from pathlib import Path
import json
import re
from audio_clock_release_common import ROOT, MAIN

REL='docs/validation/evidence/audio-discontinuity-20261021-lab'
ASSETS='docs/assets/audio-discontinuity-20261021-lab'
REPORT='docs/validation/源音频硬缺口与重叠缓存实测_2026-10-21.md'
CONTRACT='docs/specs/源音频内部时钟与硬缺口缓存_v0.1_2026-10-21.md'
HISTORICAL_REPORT='docs/validation/源音频硬缺口与重叠缓存独立实验_2026-10-21.md'
HISTORICAL_CONTRACT='docs/specs/源音频内部时钟与硬缺口缓存_实验_v0.1_2026-10-21.md'
MARKER='V91-NATIVE-AUDIO-INTERVAL-CLOCK'
SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md')

def write(path, text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')

def block(path, text):
    path=Path(path);original=path.read_text('utf8')
    replacement='<!-- '+MARKER+' -->\n'+text.rstrip()+'\n<!-- /'+MARKER+' -->'
    pattern=re.escape('<!-- '+MARKER+' -->')+'.*?'+re.escape('<!-- /'+MARKER+' -->')
    if re.search(pattern,original,re.S):original=re.sub(pattern,lambda _:replacement,original,flags=re.S)
    else:
        first,body=original.split('\n',1);original=first+'\n\n'+replacement+'\n'+body
    write(path,original)

def relative_links(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda m:m[1]+prefix+'docs/',text)

def summary(full):
    if full is None:
        return '文档预览：原生32次CLI历史媒体与新八轮隔离安装92项分别通过；首次2145完整回归4失败已保留，队列空派生修复31项通过，当前2148完整回归尚待实际终态。未合入main、未更新注册Skill，不是发布或剪映等价验收。'
    assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2148 and full['skipped']==0
    assert len(full['frozen_before'])==267 and full['frozen_before']==full['frozen_after']
    return ('V91 完整原生回归 **2148方法 /'+format(full['suite_seconds'],'.3f')+'秒 /0跳过**；'
        '267产品输入、8外部夹具、16验证脚本和9依赖文件保持相同。'
        '源内部缺口/重叠按原生采样时钟处理，原始工程引用保留；合入、17份Skill注册和普通推送以发布审计为准。')

def documents(root,full):
    root=Path(root).resolve()
    if full is None:assert root!=MAIN and root.is_relative_to(ROOT/'product/.runtime')
    status=summary(full)
    installed=json.loads((ROOT/REL/'installed-r3/verification.json').read_bytes())
    media=json.loads((ROOT/REL/'media-manifest-r2.json').read_bytes())
    assert installed['status']=='passed' and installed['isolated_methods']['methods']==92
    installed_seconds=format(installed['isolated_methods']['suite_seconds'],'.3f')
    full_row=('待实际2148完整终态；本预览没有伪造通过收据或秒数' if full is None else
              '2148方法 /'+format(full['suite_seconds'],'.3f')+'秒 /0跳过；专项与隔离各自保留，不累计')
    content=f'''### V91 源音频内部缺口、重叠与派生缓存

{status}

| 编号 | 核验内容 | 实际执行结果与边界 | 证据 |
|---|---|---|---|
| V91-01 | 原生源时钟 | 解码帧PTS/样本数建整数索引；正缺口补零，后解码帧覆盖重叠；精确采样格保留真实单采样缺口 | [规格]({CONTRACT}) |
| V91-02 | 原实现失败 | 同6原片13项实际11失败/2连续对照通过/0错误/0跳过；原日志和旧实现保留 | [before]({REL}/before-r1.json) |
| V91-03 | AAC粗时基修复 | 另9原片先5通过/4失败，修复后9份实际解码PCM逐采样相同；粗PTS已丢失的亚tick跳变不能恢复 | [补充前后]({REL}/extra-native-after-r1/verification.json) |
| V91-04 | 缓存与生命周期 | 源/工具/实现/派生字节SHA绑定，流式管道、损坏拒绝、原子写入、明确list/prune及登记源保护；队列合法空派生仍绑定SHA，原素材非空门禁保留；31专项通过 | [队列修复]({REL}/queue-cache-fix-r1.json) |
| V91-05 | 全部音频入口 | scalar/reverse/曲线/嵌套、真实R3输入及多机位只读分析通过；R3仅在实际视频覆盖内允许音频EOF静音，超界源句柄拒绝 | [路径12项]({REL}/paths-r2.json) |
| V91-06 | 原生CLI与所有帧/样本 | 32次CLI＋22条其他原生命令、37检查；forward/reverse各120帧及230400样本/声道，R3为96帧及184320样本/声道 | [实际收据]({REL}/native-r1/verification.json) |
| V91-07 | 全新八轮离线安装 | 163资源源/wheel/安装字节相同；官方NumPy2.4.2及原生数学前向；27隔离CLI、92方法/{installed_seconds}s/0跳过，含31队列方法；三组媒体重新运行 | [安装收据]({REL}/installed-r3/verification.json) |
| V91-08 | 历史专项和失败完整 | 2145全量4个队列失败保留；队列修复只变2输入，旧native/152表面其余265输入相同；更早r2三组另差能力发现及测试，明确分开 | [纪元及完整绑定]({REL}/audit-r2.json) |
| V91-09 | 原片/失败片/MP4/GIF | {media['asset_count']}实际文件、{media['GIF_count']}GIF、{media['native_probe_commands']}次原生ffprobe，包含新安装重新生成结果；MP4每帧PTS/二进制ID另验，AAC不声明波形无损 | [逐文件SHA]({REL}/media-manifest-r2.json) |
| V91-10 | 完整回归 | {full_row} | [当前完整]({REL}/full-r2.json)、[原失败]({REL}/full-r1.json) |
| V91-11 | 文档/Skill/发布 | 4份Skill由固定17父版衍生；发布时重验全部17注册、链接与索引字节，普通推送；OpenFilm R14/R15结论保留 | [完整实测]({REPORT}) |
| V91-12 | 未验收范围 | 仅目检1张PCM诊断PNG；未试听、未连续播放；自然设备异常、任意编解码变化、长片/HDR/RSS、完整AI及剪映等价继续待验 | [目检记录]({REL}/static-review-r1.json) |

[原创含音轨NUT]({ASSETS}/native-r1/original.nut) · [原视频MP4（无音轨）]({ASSETS}/native-r1/original-video-only.mp4) · [原始GIF]({ASSETS}/native-r1/original.gif) · [forward MP4]({ASSETS}/native-r1/forward.mp4) · [reverse MP4]({ASSETS}/native-r1/reverse.mp4) · [R3 MP4]({ASSETS}/native-r1/R3.mp4) · [V90真实失败无损]({ASSETS}/native-r1/before-forward-lossless.nut)

![原片实际解码GIF]({ASSETS}/native-r1/original.gif)

![实际PCM幅度诊断：独立真值/V90旧实现/当前实现；动画线仅标记时间]({ASSETS}/native-r1/actual-PCM-comparison.gif)

这些是限定原创样例的真实输出；诊断GIF不代替自然录音试听或特效质量验收。'''
    modified=set()
    for name in LATEST_DOCS:
        block(root/name,relative_links(content,name));modified.add(name)
    for origin,target in ((HISTORICAL_REPORT,REPORT),(HISTORICAL_CONTRACT,CONTRACT)):
        text=(ROOT/origin).read_text('utf8')
        text=re.sub(r'<!-- AUDIO-CLOCK-FULL-R1 -->.*?<!-- /AUDIO-CLOCK-FULL-R1 -->\s*','',text,flags=re.S)
        text=re.sub(r'<!-- AUDIO-CLOCK-FULL-R2 -->.*?<!-- /AUDIO-CLOCK-FULL-R2 -->\s*','',text,flags=re.S)
        text=text.replace(HISTORICAL_CONTRACT.split('/')[-1],CONTRACT.split('/')[-1]).replace(HISTORICAL_REPORT.split('/')[-1],REPORT.split('/')[-1])
        if origin==HISTORICAL_REPORT:
            begin=text.index('目标和15条约束')
            text='# 源音频硬缺口与重叠缓存实测\n\n'+status+'\n\n'+text[begin:]
            text=text.replace('## 4. 离线安装与待完成门禁','## 4. 离线安装与发布门禁')
            text=text.replace('草稿链接将在候选发布树核对，实际2145完整回归、主线README编号表/规格/实测/Skill合并及普通推送仍须各自通过。',
                '候选发布树核对全部17份Skill链接；完整回归状态见文首，主线合并、注册与普通推送以发布审计收据为准。')
            text += ('\n\n当前新安装为r3，92方法/'+installed_seconds+'秒/0跳过，含31队列方法；三组媒体重新执行，'
                '与历史native-r1的原无损RGBA/PCM相同。完整当前纪元见文首。'
                '\n\n[当前安装](evidence/audio-discontinuity-20261021-lab/installed-r3/verification.json) · '
                '[全部实际媒体](evidence/audio-discontinuity-20261021-lab/media-manifest-r2.json)\n')
        else:
            text=text.replace('以当前V90候选的263产品输入为独立开发基线；其2084完整回归与发布尚在原任务中推进。本实验的后续完整门禁必须绑定实际发布V90，不能以候选拷贝或专项通过代替父版发布。',
                '本版以已实际发布V90 /7545d747的263输入及2084完整回归为父版，当前267输入；本版完整回归状态见文首。源缓存协议与设备仿射校准分别发现，不推断主音轨或镜头取舍。')
            text=text.replace('在PTS量化的半tick容限内保持连续样本，不因粗容器时基把正常1024样本包反复剪短或补零；精确原生采样时基下的真实单采样跳变需要独立核验',
                '每个粗PTS有半tick舍入不确定性，相对同样量化的段首可累计至一个粗tick；按这一相对容限保留实际连续AAC包。精确原生采样格仍以半采样阈值保留真实单采样缺口；粗容器已丢失的亚tick跳变不能恢复')
            text=text.replace('本实验仍需自己的完整回归和主线门禁；专项/安装不得替代。','本版完整回归及发布另有收据，专项/安装不得替代。')
            first,body=text.split('\n',1);text=first+'\n\n'+status+'\n'+body
        write(root/target,text);modified.add(target)
    drafts=json.loads((ROOT/REL/'skills-r1/verification.json').read_bytes())
    for name in SKILLS:
        text=Path(drafts['drafts'][name]['path']).read_text('utf8')
        text=text.replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        text += ('\n\nA continuous source clock cache intentionally keeps an empty `audio.pcm` '
            'because the original media remains the audio input. Queue reuse binds that '
            'derived file\'s zero byte size and empty SHA; it must reject later changes '
            'or truncation of nonempty artifacts. Authored sources, tools and committed '
            'outputs must still be nonempty. Do not delete the empty placeholder or '
            'disable dependency verification to make a queue succeed.\n')
        target='skills/'+name+'/SKILL.md';write(root/target,text);modified.add(target)
    path=root/'.gitattributes';text=path.read_text('utf8');marker='# V91 immutable native source-audio media and execution evidence.'
    assert marker not in text
    write(path,text+'\n'+marker+'\n'+REL+'/** -text -whitespace\n'+ASSETS+'/** -text -whitespace\n');modified.add('.gitattributes')
    return modified
