"""Synchronize numbered V76 evidence, media and remaining performance gates."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/selective-hsl-20261020-v76'
BASE=ROOT/REL
CONTRACT=ROOT/'docs/specs/八色分区HSL与关键帧契约_v0.1_2026-10-20.md'
REPORT=ROOT/'docs/validation/八色分区HSL与离线发行实测_2026-10-20.md'
NATIVE='docs/assets/selective-hsl-20261020-v76-native-r2'
INSTALLED='docs/assets/selective-hsl-20261020-v76-installed-r1'
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


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true');args=parser.parse_args()
    focus=read(BASE/'targeted-r4.json');dev=read(BASE/'native-r2/verification.json');install=read(BASE/'installed-r1/verification.json')
    media=read(BASE/'installed-r1/media/verification.json');full=read(BASE/'full-r1.json');perf=read(BASE/'performance-r1.json')
    assert focus['terminal_ok'] and focus['methods']==29 and focus['frozen_equal'] and focus['skipped']==0
    for d in (dev,install,media):assert d['status']=='passed' and d['frozen_equal'] and all(x['ok'] for x in d['checks'])
    assert all(d['frozen_before']==d['frozen_after']==focus['frozen_after'] for d in (dev,install,media,perf))
    assert perf['status']=='passed-execution-probe' and len(perf['cases'])==3
    slow=[x for x in perf['cases'] if x['name']!='control']
    costs='／'.join(f'{x["seconds_per_frame"]:.3f}' for x in slow)
    final=not args.candidate
    if final:
        assert full['terminal_ok'] and full['status']=='passed' and full['methods']==1725 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_after']==focus['frozen_after']
        skills=read(BASE/'skills-r1.json');skill_text=f"{skills['skill_count']} Skills／{skills['local_links_checked']} 本地引用，发行联接与正文均核对"
        full_text=f"完整原生回归 **{full['methods']}/{full['methods']}、{full['suite_seconds']:.3f} 秒、0 跳过、225 冻结输入＋8 外部夹具前后相同**"
    else:
        skill_text='4 份相关 Skill 已更新，17 份安装联接待发行时核对'
        full_text='完整原生回归仍在运行，**尚未作为 main 全量发行验收**'
    summary=(f'2026-10-20 **V76（八色分区 HSL 限定功能验收）**：catalog **0.8.0／46 项**；'
        '新增八色各 H/S/L＋最终 RGB 强度 **25 个表达式通道**，原生命令仍为 **10 类／34 通道**。'
        '按原始色相相邻权重同时分区，灰阶与输入 Alpha 保留；作者时钟、六插值、拆分／反转、区间、工程包／片段重建均核验。'
        '修复片段／区间效果超大整数校验，静态中性／零强度旁路不消耗执行配额。'
        f'{full_text}；29 新方法为全量子集。专项 **29/29、{focus["suite_seconds"]:.3f} 秒、0 跳过**。'
        f'开发 **{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查**，四组各 24 帧，独立 colorsys＋source-over 参照的 RGB 最大差均 **1/255**，'
        '输出 Alpha、每组完整 **96,000 帧立体声 PCM** 和每帧 PTS 分别检查。'
        f'离线 **{len(install["resource_hashes"])} 资源／7 wheels／{install["isolated_cli_calls"]} 隔离 CLI＋1 模块来源探针／{len(install["checks"])} 安装检查**，'
        f'开发／安装全部解码摘要、参数／内核元数据和 PTS 一致；{skill_text}。'
        f'**1080p 单滤镜线程、各 3 帧探针：单色区／八色约 {costs} 秒/帧，未达 30fps；性能仍是明确缺口。**'
        '保留首轮 1 failure／2 errors 和参照修正；仅静看最终两张 PNG，未连续审片／听审。'
        '本轮为 8 位编码 RGB 算法验收；自然质量、实时预览、线性光／HDR及完整剪映等价未验收。')
    rows=[
        ('V76-01','旧版本缺口','ea232b9 未发现八色效果、没有生成滤镜；六帧解码与输入相同，223 旧输入不变','baseline-r1.json'),
        ('V76-02','25 通道与作者时钟','29/29；正负值、六插值、灰阶、Alpha、线程、实例、共享预算、旁路、包／片段、拆分／反转／区间','targeted-r4.json'),
        ('V76-03','红橙色相','24 帧动画；独立全 RGB 最大差 1；Alpha／完整 PCM／PTS 分别检查','native-r2/verification.json'),
        ('V76-04','蓝色饱和度','24 帧；蓝色去饱和＋静态青色明度；RGB 最大差 1，灰阶中性','native-r2/verification.json'),
        ('V76-05','洋红明度','24 帧；明度动画＋静态紫色色相；RGB 最大差 1','native-r2/verification.json'),
        ('V76-06','八色强度动画','24 帧；最终编码 RGB 强度混合；RGB 最大差 1，工程包解码逐字节重建','native-r2/verification.json'),
        ('V76-07','原生离线安装','147 资源逐字节一致、7 wheels；27 隔离 CLI＋1 来源探针／12 检查，四组解码相同','installed-r1/verification.json'),
        ('V76-08','完整回归',f'1725/1725；{full["suite_seconds"]:.3f} 秒；0 跳过；225 输入＋8 夹具' if final else '运行中；尚未取得终态通过','full-r1.json'),
        ('V76-09','静态审查范围','查看开发／安装 PNG；未连续播放、听审或验收自然素材','static-review-r1.json'),
        ('V76-10','首轮失败与参照修正','24 方法含 1 failure／2 errors；真实整数溢出修复，发现读取路径和 ease_in_out 参照修正','targeted-r1.log'),
        ('V76-11','中间检查边界','26 方法阶段的区间测试覆盖不足已纠正；最终 29 方法直接要求实际区间结构化错误','targeted-r2.json'),
        ('V76-12','1080p 性能缺口',f'单线程单色区／八色 {costs} 秒/帧；3 帧、各一次、含启动且并发回归，不能实时预览','performance-r1.json'),
    ]
    def table(path):
        text='| 编号 | 功能性核验／实测 | 实际结果 | 证据 |\n|---|---|---|---|\n'
        return text+'\n'.join('| '+' | '.join((n,a,b,link(path,'记录',BASE/c)))+' |' for n,a,b,c in rows)
    def media_block(path):
        text=('原输入是自制 CC0 静态色带／透明区域和双声道正弦，**不是自然实拍视频**。'+
            link(path,'前景 PNG',ROOT/NATIVE/'foreground-original.png')+' · '+link(path,'棋盘 PNG',ROOT/NATIVE/'background-original.png')+' · '+
            link(path,'双声道 WAV',ROOT/NATIVE/'audio-original.wav')+' · '+link(path,'静态输入视频预览',ROOT/NATIVE/'source-preview.mp4')+'。\n\n')
        for label,title in [('red-orange','红橙色相'),('blue-saturation','蓝色饱和度'),('magenta-lightness','洋红明度'),('grade-intensity','八色强度')]:
            text+=link(path,title+' MP4',ROOT/NATIVE/(label+'.mp4'))+' · '+link(path,'FFV1／PCM 精确参照',ROOT/NATIVE/(label+'-lossless.mkv'))+'\n\n'
            text+='!'+link(path,title+'（真实 CLI 成片 GIF，有损预览）',ROOT/NATIVE/(label+'.gif'))+'\n\n'
        return text
    for name in DOCUMENTS:
        path=ROOT/name;body=summary+'\n\n'+link(path,'契约',CONTRACT)+' · '+link(path,'实测与失败',REPORT)+' · '+link(path,'当前回归',BASE/'full-r1.json')
        if name=='README.md':body+='\n\n'+table(path)+'\n\n'+media_block(path)
        block(path,'V76-CURRENT',body)
    detail=summary+'\n\n'+table(REPORT)+'\n\n'+media_block(REPORT)
    detail+='原生执行、参数、SHA-256、逐帧 RGB 差、PCM 摘要和 PTS 见收据；MP4/GIF 不用于精确像素或声音断言。\n\n'
    detail+=link(REPORT,'安装样例收据',BASE/'installed-r1/media/verification.json')+' · '+link(REPORT,'全部安装检查',BASE/'installed-r1/verification.json')+' · '+link(REPORT,'静态审查',BASE/'static-review-r1.json')+' · '+link(REPORT,'CPU 探针',BASE/'performance-r1.json')
    block(REPORT,'V76-DETAIL',detail)
    block(CONTRACT,'V76-STATE',('发行限定功能验收：'+full_text+'；'+skill_text+'。性能未达到实时目标。') if final else '候选版本：专项、真实 CLI 和隔离安装通过；完整回归与 main 发行尚未完成。1080p CPU 性能未达实时目标。')
    matrix=ROOT/DOCUMENTS[-1];text=matrix.read_text(encoding='utf8')
    old='| 本地效果目录 | `effects.py` 0.7.0/45 项；参数、别名、许可、34 原生命令数值通道及共享预算可查询 |'
    new='| 本地效果目录 | `effects.py` 0.8.0/46 项；34 原生命令通道＋25 八色 HSL 表达式通道分别发现，参数、许可和共享预算可查询 |'
    text=text.replace(old,new);write(matrix,text)
    readme=ROOT/'README.md';text=readme.read_text(encoding='utf8')
    text=text.replace('通过 `effects list/inspect` 可发现的 45 项本地 FFmpeg 效果目录','通过 `effects list/inspect` 可发现的 46 项本地 FFmpeg 效果目录')
    write(readme,text)
    print(json.dumps({'status':'candidate-documents-synchronized' if args.candidate else 'documents-synchronized','documents':len(DOCUMENTS)+2,'full_terminal':bool(full.get('terminal_ok'))}))


if __name__=='__main__':main()
