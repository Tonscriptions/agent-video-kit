"""Publish V78 preview evidence without conflating research, tests and delivery."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/timeline-preview-20261020-v78'
BASE=ROOT/REL
NATIVE='docs/assets/timeline-preview-20261020-v78-r6'
INSTALLED='docs/assets/timeline-preview-20261020-v78-installed-r3'
CONTRACT=ROOT/'docs/specs/时间线帧区间预览与内容缓存契约_v0.1_2026-10-20.md'
REPORT=ROOT/'docs/validation/时间线帧区间预览与离线发行实测_2026-10-20.md'
DOCUMENTS=('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')
FOLLOWUPS=('docs/OpenFilm_0.2.3增量复用与开发成本评估_2026-10-20.md',
    'docs/specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md')
SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-project-ops','video-cut-quality')
SCRIPTS=('smoke_timeline_preview','verify_timeline_preview_install','sync_timeline_preview_documents',
    'audit_timeline_preview_release','publish_timeline_preview','probe_timeline_preview_contexts','probe_timeline_preview_lut')

def read(path):return json.loads(Path(path).read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')
def link(path,label,target):return f'[{label}]({os.path.relpath(target,path.parent).replace(chr(92),"/")})'
def block(path,marker,body):
    text=path.read_text(encoding='utf8');section=f'<!-- {marker} -->\n{body.rstrip()}\n<!-- /{marker} -->'
    pattern=r'<!-- '+re.escape(marker)+r' -->.*?<!-- /'+re.escape(marker)+r' -->'
    if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:section,text,count=1,flags=re.S)
    else:
        title,rest=text.split('\n',1);text=title+'\n\n'+section+'\n'+rest
    write(path,text)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true');args=parser.parse_args()
    focus=read(BASE/'targeted-r7.json');dev=read(BASE/'native-r6/verification.json')
    install=read(BASE/'installed-r3/verification.json');media=read(BASE/'installed-r3/media/verification.json')
    context=read(BASE/'contexts-native-r3/verification.json');isolated_context=read(BASE/'contexts-installed-r2/verification.json')
    lut=read(BASE/'lut-native-r1/verification.json');isolated_lut=read(BASE/'lut-installed-r1/verification.json')
    full=read(BASE/'full-r2.json');current=focus['frozen_after']
    assert focus['terminal_ok'] and focus['methods']==22 and focus['skipped']==0 and len(current)==235
    for value in (focus,dev,install,media,context,isolated_context):assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media,context,isolated_context):assert value['status']=='passed' and all(x['ok'] for x in value['checks'])
    for value in (lut,isolated_lut):assert value['status']=='passed' and value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current and value['cli_calls']==12
    if args.candidate:
        full_text='完整回归正在运行；**候选尚未完成 main 全量发行验收**'
        skill_text='4 份相关 Skill 已更新；main 上的 17 份发现联接待发行核对'
    else:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==1768 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_before']==full['frozen_after']==current
        full_text=f'完整原生回归 **1768/1768、{full["suite_seconds"]:.3f} 秒、0 跳过、235 冻结输入＋8 外部夹具前后相同**'
        audit=read(BASE/'skills-r1.json');skill_text=f'{audit["skill_count"]} Skills／{audit["local_links_checked"]} 本地引用与发现联接已核对'
    summary=('2026-10-20 **V78（时间线帧/区间预览与内容缓存限定验收）**：新增 '
        '`preview frame/range/cache-list/cache-prune`，完整作者图合成后按输出帧截取；'
        'RGBA PNG、FFV1 BGRA＋float32 PCM NUT、H.264/AAC MP4；有理数显示帧率、末帧音频端点与全部 PTS 核验。'
        '持久缓存以实际源/派生/运行时 SHA 验证，不能沿用上游路径＋大小＋mtime 命中；新目录导出、取消、损坏拒绝、配额及工程引用保护。'
        f'{full_text}；22 新方法为全量子集，专项 **22/22、{focus["suite_seconds"]:.3f} 秒、0 跳过**。'
        f'开发 **{dev["cli_calls"]} 次 CLI／{len(dev["checks"])} 项检查**，四组共37帧；'
        '移动 HSL、缩小、实际透明作者输出及 NTSC 不完整末帧，全部 RGBA／每个 PCM 样本与独立完整图参考逐字节一致，包重放一致。'
        f'离线 **{len(install["resource_hashes"])} 资源／7 wheels／{install["isolated_cli_calls"]} 次隔离 CLI＋1 来源探针／{len(install["checks"])} 项检查**，'
        f'源码／平台 wheel／安装资源逐字节相同，安装解码结果与开发一致；{skill_text}。'
        '另作跨转场及本地R3伸缩两组上下文探针：开发/同一隔离安装各22次CLI／15检查，24帧与完整PCM及包重放一致，独立于主四组计数。'
        'LUT三种字段再以开发/隔离入口各12次CLI验证同大小/mtime替换失效与新像素；不与上述次数混合。'
        '保留早期探测字段、像素转换和演示夹具失败。软件预览从作者起点累计解码，命中仍需内容校验；'
        '未验收实时播放、连续审片／听审、自然质量、HDR或完整剪映等价。')
    rows=[
        ('V78-01','帧与区间语义',f'22/22；{focus["suite_seconds"]:.3f}s；全图RGBA／完整PCM、透明、NTSC末端、调整区间与嵌套倒放','targeted-r7.json'),
        ('V78-02','缓存与故障','同大小/mtime素材及三种LUT别名内容失效；命中不编图/探测/编码；损坏拒绝；取消、复制失败、引用保护与Windows junction','targeted-r7.json'),
        ('V78-03','实际开发CLI',f'{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查；四组37帧，RGBA和每个PCM样本与完整图一致，包重放一致','native-r6/verification.json'),
        ('V78-04','离线平台发行',f'154资源／7wheels；{install["isolated_cli_calls"]} 隔离CLI＋1来源探针／{len(install["checks"])} 检查；开发/安装解码相同','installed-r3/verification.json'),
        ('V78-05','完整原生回归',f'1768/1768；{full["suite_seconds"]:.3f}s；235输入＋8夹具；0跳过' if not args.candidate else '现有冻结输入正在运行；未取得全量终态通过','full-r2.json'),
        ('V78-06','早期产品核验失败','r1：2失败/7错误；r2：3像素失败；修正探测字段、字符串噪声旁路与BGRA/scale转换，阈值未放宽','targeted-r1.json'),
        ('V78-07','实际演示夹具失败','源尾端/原生插件路径/NTSC关键帧/极短GIF四类失败均保留；未改产品通过阈值','native-r4/verification.json'),
        ('V78-08','安装演示失败','首次安装资源已正确，单帧NTSC转8fps GIF输出0帧；修正演示为PNG和MP4，原失败保留','installed-r1/verification.json'),
        ('V78-09','静态审查边界','只静看最终开发/安装PNG；完整播放、声音、自然质量、HDR与实时延迟未验收','static-review-r2.json')]
    rows.append(('V78-10','跨转场/真实音频衍生任务','开发与隔离安装各22 CLI／15检查；两组各12帧，跨剪切点与R3 0.5倍速，完整参考RGBA/PCM及包重放一致','contexts-native-r3/verification.json'))
    rows.append(('V78-11','LUT兼容别名失效修复','额外测试先复现lut入口旧命中再修复；path/file/lut三字段实际新像素与完整参考相同；旧全量停止并保留','targeted-r6.json'))
    rows.append(('V78-12','LUT别名实际CLI','开发/隔离入口各12次CLI；三字段内容替换后拒绝旧命中，像素变化且新内容可重复命中','lut-native-r1/verification.json'))
    def table(path):return '| 编号 | 功能性核验／实测 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'+'\n'.join('| '+' | '.join((a,b,c,link(path,'记录',BASE/d)))+' |' for a,b,c,d in rows)
    def media_block(path):
        body=('自制 CC0 合成移动图、RGBA 图和立体声声音；'+link(path,'原视频',ROOT/NATIVE/'moving-original.mp4')+' · '+
            link(path,'原无损视频',ROOT/NATIVE/'moving-original.nut')+' · '+link(path,'原透明PNG',ROOT/NATIVE/'alpha-original.png')+' · '+
            link(path,'原WAV',ROOT/NATIVE/'audio-original.wav')+'。\n\n')
        for name,title in [('motion','动画时间线区间'),('scaled','合成后缩小'),('alpha','透明作者图的观看副本')]:
            body+=link(path,title+' MP4',ROOT/NATIVE/(name+'-preview.mp4'))+' · '+link(path,'无损RGBA/PCM',ROOT/NATIVE/(name+'-reference.nut'))+'\n\n'
            body+='!'+link(path,title+' GIF（有损不透明预览）',ROOT/NATIVE/(name+'-preview.gif'))+'\n\n'
        body+=link(path,'NTSC末帧 PNG',ROOT/NATIVE/'ntsc-frame.png')+' · '+link(path,'NTSC单帧 MP4',ROOT/NATIVE/'ntsc-preview.mp4')+' · '+link(path,'可编辑工程包',ROOT/NATIVE/'editable-project.zip')+'。单帧不足8fps GIF一步，未人为延长动画。\n'
        extra=ROOT/'docs/assets/timeline-preview-20261020-v78-contexts-r3'
        body+='\n上下文探针：'+link(path,'跨转场 MP4',extra/'transition-preview.mp4')+' · '+link(path,'R3伸缩区间 MP4',extra/'rubberband-preview.mp4')+' · '+link(path,'隔离安装探针',BASE/'contexts-installed-r2/verification.json')+'。\n'
        return body
    for name in DOCUMENTS:
        path=ROOT/name;body=summary+'\n\n'+link(path,'CLI与缓存契约',CONTRACT)+' · '+link(path,'实测、失败与时延边界',REPORT)+' · '+link(path,'完整回归',BASE/'full-r2.json')
        if name=='README.md':body+='\n\n'+table(path)+'\n\n'+media_block(path)
        block(path,'V78-CURRENT',body)
    for name in FOLLOWUPS:
        path=ROOT/name
        body=('R12 后续 V78：时间线帧/区间预览已有独立本地 CLI 限定实现；'+link(path,'实现契约',CONTRACT)+'、'+link(path,'实际核验与未验收项',REPORT)+'。'
            '借鉴任务形态，重写内容身份与现有完整作者图接入；没有复制上游mtime缓存或GUI。组件参数CP-01..06、开放NLE交换及实时播放目标仍独立待办。'+full_text+'。')
        block(path,'V78-FOLLOWUP',body)
    if not REPORT.exists():write(REPORT,'# 时间线帧区间预览与离线发行实测\n')
    body=summary+'\n\n'+table(REPORT)+'\n\n'+media_block(REPORT)
    body+='\n\n| 实际场景 | 尺寸／帧率 | 帧数／PCM采样帧 | 冷执行秒 | 验证命中秒 |\n|---|---|---|---|---|\n'
    for c in dev['cases']:
        body+=f'| {c["name"]} | {c["width"]}×{c["height"]}／{c["fps"]["num"]}/{c["fps"]["den"]} | {c["frames"]}／{c["pcm_samples"]} | {c["cold_seconds"]:.3f} | {c["hit_seconds"]:.3f} |\n'
    body+='\n上述为合成小图的单次实际CLI内部耗时，运行时有并行回归/安装负载；不能换算1080p实时播放承诺。命中仍读源和运行资源做SHA检查。\n\n'
    body+='早期专项r1的2 failures/7 errors来自嵌套尺寸字段与噪声字符串旁路；r2的3项精确像素失败来自YUV/RGB/scale插值顺序。最终先物化BGRA，尺寸不变时不插入scale，没有调整像素或PCM阈值。r3为17项通过、r4为20项通过，r5新增真实透明作者输出至21项；随后r6以三种LUT别名复现1项失败，r7修复后22项通过。旧结果不累加。\n\n'
    body+='LUT依赖复查先记录同大小/mtime下兼容字段lut身份不变，再以真实渲染复现旧缓存命中；修正为收集lut/lut_uri。full-r1停止于该发现，保留终态失败、停止原因与当时5份源文件字节快照；full-r2才是修正后版本的全量验收。旧成功CLI、安装及上下文结果也保留，最终分别以新目录重跑。\n\n'
    body+='真实演示r1拒绝超出NUT可探测源尾端的区间；r2独立参考进程未传frei0r路径；r3把2秒关键帧留在约1秒NTSC片段；r4及首轮安装在把不足1/8秒的单帧转成8fps GIF时输出0帧。修正生成器后使用新输出位置；全部旧日志/生成器副本与不完整公开文件仍保留，不纳入成功计数。\n\n'
    body+='额外上下文探针确认完整图中实际存在xfade，及真实执行的本地Rubber Band R3 0.5倍速任务和100ms源上下文；开发与既有隔离安装各22次CLI/15检查，全部RGBA、PCM和包重放一致。R3为显式登记SHA和许可证的现有本地工具，不是新下载或7个wheels内新附带的程序。首轮上下文参考探针漏传scratch参数而失败，原生成器和错误输出保留；修正后没有改变产品输入。\n\n'
    body+='所有素材为本项目脚本原创合成，CC0-1.0声明只覆盖这些输入。RGBA/PCM/PTS比对使用完整作者图独立无损渲染；不是对自然剪辑效果的审片。透明工程的NUT/PNG有非平凡Alpha，MP4/GIF看起来为不透明副本。模型推理次数为0。\n\n'
    body+='复现：原生运行 `scripts/smoke_timeline_preview.py --work <new product/.runtime/path> --evidence <new docs/path> --assets <new docs/assets/path>`；离线验证使用 `scripts/verify_timeline_preview_install.py` 并传本地wheelhouse与开发收据，拒绝覆盖已有目录。完整回归使用8个固定外部夹具的wrapper。无Docker/WSL/容器/虚拟环境；本轮预览/安装不打开交互浏览器tab；完整回归的原有浏览器夹具需按其所有权清理。\n'
    block(REPORT,'V78-DETAIL',body)
    print(json.dumps({'status':'candidate-documents-synchronized' if args.candidate else 'documents-synchronized','documents':len(DOCUMENTS)+len(FOLLOWUPS)+1}))

if __name__=='__main__':main()
