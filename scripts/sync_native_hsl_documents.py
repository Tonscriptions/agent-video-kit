"""Synchronize V77 native HSL proof, historical failures and separate timing scopes."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/native-hsl-20261020-v77'
BASE=ROOT/REL
CONTRACT=ROOT/'docs/specs/八色HSL原生像素内核与表达式DAG契约_v0.1_2026-10-20.md'
REPORT=ROOT/'docs/validation/八色HSL原生提速与离线发行实测_2026-10-20.md'
NATIVE='docs/assets/native-hsl-20261020-v77-native-r3'
INSTALLED='docs/assets/native-hsl-20261020-v77-installed-r3'
CLI='docs/assets/native-hsl-20261020-v77-cli-r2'
DOCUMENTS=('README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md')

def read(path):return json.loads(Path(path).read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')
def relative(path,target):return os.path.relpath(target,path.parent).replace('\\','/')
def link(path,label,target):return f'[{label}]({relative(path,target)})'
def block(path,marker,body):
    text=path.read_text(encoding='utf8');section=f'<!-- {marker} -->\n{body.rstrip()}\n<!-- /{marker} -->'
    pattern=r'<!-- '+re.escape(marker)+r' -->.*?<!-- /'+re.escape(marker)+r' -->'
    if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:section,text,count=1,flags=re.S)
    else:
        title,rest=text.split('\n',1);text=title+'\n\n'+section+'\n'+rest
    write(path,text)
def span(case,key='frames_per_wall_second'):
    values=[x[key] for x in case['samples']];return f'{min(values):.2f}–{max(values):.2f}'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true');args=parser.parse_args()
    native=read(BASE/'native-targeted-r4.json');hsl=read(BASE/'hsl-targeted-r4.json');offline=read(BASE/'offline-targeted-r3.json')
    dev=read(BASE/'native-r3/verification.json');install=read(BASE/'installed-r3/verification.json')
    media=read(BASE/'installed-r3/media/verification.json');perf=read(BASE/'fastpath-r5.json');cli=read(BASE/'cli-r2/verification.json')
    full=read(BASE/'full-r3.json')
    for value,count in ((native,19),(hsl,29),(offline,22)):
        assert value['terminal_ok'] and value['methods']==count and value['skipped']==0
    current=native['frozen_after'];assert len(current)==233
    for value in (native,hsl,offline,dev,install,media,perf,cli):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    for value in (dev,install,media):assert value['status']=='passed' and all(x['ok'] for x in value['checks'])
    for value in (perf,cli):assert value['status']=='passed-execution-probe'
    final=not args.candidate
    if final:
        assert full['terminal_ok'] and full['status']=='passed' and full['methods']==1746 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_before']==full['frozen_after']==current
        skills=read(BASE/'skills-r1.json');skill_text=f"{skills['skill_count']} Skills／{skills['local_links_checked']} 本地引用与发现联接均核对"
        full_text=f"完整原生回归 **1746/1746、{full['suite_seconds']:.3f} 秒、0 跳过、233 冻结输入＋8 外部夹具前后相同**"
    else:
        skill_text='4 份相关 Skill 已更新，17 份发现联接待 main 发行核对'
        full_text='完整回归运行中，**当前候选尚未完成 main 全量发行验收**'
    filter_values=[s['frames_per_wall_second'] for c in perf['cases'] if c['name']!='control' for s in c['samples']]
    filter_span=f'{min(filter_values):.2f}–{max(filter_values):.2f}'
    whole={x['name']:x for x in cli['cases']}
    summary=(f'2026-10-20 **V77（八色 HSL 原生提速与离线发行限定验收）**：catalog **0.8.1／46 项**；'
        '本地 C11 frei0r 像素内核＋有界作者表达式 DAG，保留原八色 HSL、25 表达式通道和作者模型；既有 **10 类／34 命令通道**不增计。'
        '默认校验摘要后选原生模块，可显式 native／expression；完整性错误拒绝。'
        f'{full_text}；本轮新增 19 内核＋2 安装方法，原 HSL 29 和安装 22 专项均为全量子集。'
        f'最终专项 **19/19（{native["suite_seconds"]:.3f}s）、29/29（{hsl["suite_seconds"]:.3f}s）、22/22（{offline["suite_seconds"]:.3f}s）**，均无跳过。'
        f'原生 **{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查**，四组各 24 帧，独立 colorsys＋source-over RGB 最大差均 **1/255**；'
        'Alpha、每组完整 **96,000 帧立体声 PCM**、全部 PTS 和包重建分别核验。'
        f'离线 **{len(install["resource_hashes"])} 资源／7 wheels／{install["isolated_cli_calls"]} 隔离 CLI＋1 来源探针／{len(install["checks"])} 检查**，'
        f'源／平台 wheel／安装逐字节一致，安装成片与开发解码和内核元数据一致；{skill_text}。'
        f'**1080p 最终滤镜探针 {filter_span}fps（60 帧×3，null 输出，最多 3 后台线程＋调用线程）；'
        f'完整 CLI 静态八色 {span(whole["eight-band"])}fps、强度动画 {span(whole["animated-intensity"])}fps，未达 30fps。**'
        '完整 CLI 包含校验、解码、合成、H.264/AAC 编码和清单，且并发回归；不能把滤镜吞吐当实时预览。'
        '保留构建／夹具失败、安装器标签缺口、漏打包 HTML 脚本及两次停止全量。'
        '未连续审片／听审；自然质量、HDR、交互预览和完整剪映等价未验收。')
    rows=[
        ('V77-01','原生内核与程序','19/19；RGBA／geq 对照、六插值、非线性时钟、奇数步幅、并发、惰性分支、非法程序与完整性','native-targeted-r4.json'),
        ('V77-02','既有作者模型','29/29；保留八色定义、窗口／反转、区间、预算、工程包／片段和中性旁路','hsl-targeted-r4.json'),
        ('V77-03','真实 CLI 四组色彩','24 CLI／50 检查；每组24帧，独立 RGB 最大差1、Alpha／完整PCM／PTS分别核验','native-r3/verification.json'),
        ('V77-04','平台 wheel 与离线','153资源／7wheels，py3-none-win_amd64；27隔离CLI＋1来源探针／13检查，安装成片相同','installed-r3/verification.json'),
        ('V77-05','安装平台限制','22/22；接受无 CPython C ABI 的 Windows x64，仍拒绝 ARM／Linux／win32／错误 Python ABI','offline-targeted-r3.json'),
        ('V77-06','1080p 滤镜吞吐',f'{filter_span}fps；各60帧×3；filter_threads=1，C内核另有最多3后台线程＋调用线程','fastpath-r5.json'),
        ('V77-07','完整 CLI 速度',f'静态八色 {span(whole["eight-band"])}fps；强度动画 {span(whole["animated-intensity"])}fps；均未达30fps','cli-r2/verification.json'),
        ('V77-08','完整回归',f'1746/1746；{full["suite_seconds"]:.3f}秒；0跳过；233输入＋8夹具' if final else '最终版本运行中，未取得终态通过','full-r3.json'),
        ('V77-09','历史拒绝与修复','安装器拒绝新平台标签；修复后仍检查平台边界；失败收据保留','installed-r1/verification.json'),
        ('V77-10','打包遗漏与修正','实际安装152项，补回既有openfilm_text_bounds.mjs；核验器兼容wheel标准purelib布局','installed-r2/verification.json'),
        ('V77-11','中止的全量','full-r1、full-r2均停止自有unittest树并保留失败终态，不纳入通过计数','full-r2-stop.json'),
        ('V77-12','静态目检边界','只静看最终开发／安装两张PNG；未连续播放、听审或验收自然质量','static-review-r1.json'),
        ('V77-13','完整 CLI 有界诊断','另1次带cProfile的实际渲染；FFmpeg指纹及子进程等待可见，不把受扰动计时当fps基准','profile-r1/verification.json'),
    ]
    def table(path):
        return '| 编号 | 功能性核验／实测 | 实际结果 | 证据 |\n|---|---|---|---|\n'+'\n'.join(
            '| '+' | '.join((a,b,c,link(path,'记录',BASE/d)))+' |' for a,b,c,d in rows)
    def media_block(path):
        text=('四组输入为自制 CC0 静态色带／透明区、棋盘和合成双声道声音，非自然实拍。'+
            link(path,'前景 PNG',ROOT/NATIVE/'foreground-original.png')+' · '+link(path,'棋盘 PNG',ROOT/NATIVE/'background-original.png')+' · '+
            link(path,'原始 WAV',ROOT/NATIVE/'audio-original.wav')+' · '+link(path,'原输入视频预览',ROOT/NATIVE/'source-preview.mp4')+'。\n\n')
        for label,title in [('red-orange','红橙色相'),('blue-saturation','蓝色饱和度'),('magenta-lightness','洋红明度'),('grade-intensity','八色强度')]:
            text+=link(path,title+' MP4',ROOT/NATIVE/(label+'.mp4'))+' · '+link(path,'精确 FFV1／PCM',ROOT/NATIVE/(label+'-lossless.mkv'))+'\n\n'
            text+='!'+link(path,title+'（实际原生 CLI 成片 GIF，有损预览）',ROOT/NATIVE/(label+'.gif'))+'\n\n'
        text+='完整 1080p CLI 的移动测试图与实际成片（均为合成测试素材）：'+link(path,'原视频',ROOT/CLI/'source-testsrc2.mp4')+' · '+link(path,'无 HSL 对照',ROOT/CLI/'control.mp4')+' · '+link(path,'静态八色',ROOT/CLI/'eight-band.mp4')+' · '+link(path,'强度动画',ROOT/CLI/'animated-intensity.mp4')+'。\n'
        return text
    for name in DOCUMENTS:
        path=ROOT/name;body=summary+'\n\n'+link(path,'原生契约',CONTRACT)+' · '+link(path,'实测与失败',REPORT)+' · '+link(path,'最终回归',BASE/'full-r3.json')
        if name=='README.md':body+='\n\n'+table(path)+'\n\n'+media_block(path)
        block(path,'V77-CURRENT',body)
    performance_table='| 探针范围 | 项目 | 帧数×重复 | 实测 fps | 范围限制 |\n|---|---|---|---|---|\n'
    for c in perf['cases']:
        performance_table+=f'| 最终滤镜输出 null | {c["name"]} | 60×3 | {span(c)} | 无编码；最多3后台线程＋调用线程 |\n'
    for c in cli['cases']:
        performance_table+=f'| 完整 CLI | {c["name"]} | 60×3 | {span(c)} | 含进程启动、校验、合成、编码和清单；并发full-r3 |\n'
    detail=summary+'\n\n'+table(REPORT)+'\n\n'+performance_table+'\n'+media_block(REPORT)
    detail+='\n'+link(REPORT,'全部安装检查',BASE/'installed-r3/verification.json')+' · '+link(REPORT,'安装成片核验',BASE/'installed-r3/media/verification.json')+' · '+link(REPORT,'静态 PNG 审查',BASE/'static-review-r1.json')
    block(REPORT,'V77-DETAIL',detail)
    block(CONTRACT,'V77-STATE',full_text+'；'+skill_text+'。原生滤镜提速已测，完整 CLI 未达30fps，交互预览未验收。')
    matrix=ROOT/DOCUMENTS[-1];text=matrix.read_text(encoding='utf8')
    text=text.replace('`effects.py` 0.8.0/46 项；34 原生命令通道＋25 八色 HSL 表达式通道分别发现，参数、许可和共享预算可查询',
        '`effects.py` 0.8.1/46 项；34 原生命令通道＋25 八色 HSL 表达式通道分别发现；校验原生 C/DLL、DAG、geq 回退、参数、许可和共享预算可查询')
    write(matrix,text)
    print(json.dumps({'status':'candidate-documents-synchronized' if args.candidate else 'documents-synchronized','documents':len(DOCUMENTS)+2,'full_terminal':bool(full.get('terminal_ok'))}))

if __name__=='__main__':main()
