"""Synchronize V75 numbered verification tables from retained real receipts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/spatial-automation-20261020-v75'
BASE=ROOT/REL
CONTRACT=ROOT/'docs/specs/空间滤镜与抠像参数关键帧契约_v0.1_2026-10-20.md'
REPORT=ROOT/'docs/validation/空间滤镜与抠像关键帧实测_2026-10-20.md'
NATIVE='docs/assets/spatial-automation-20261020-v75-native-r3'
INSTALLED='docs/assets/spatial-automation-20261020-v75-installed-r2'
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
    focus=read(BASE/'targeted-r5.json');dev=read(BASE/'native-r3/verification.json');install=read(BASE/'installed-r2/verification.json')
    media=read(BASE/'installed-r2/media/verification.json');full=read(BASE/'full-r2.json')
    assert focus['terminal_ok'] and focus['methods']==29 and focus['frozen_equal'] and focus['skipped']==0
    for d in (dev,install,media):assert d['status']=='passed' and d['frozen_equal'] and all(x['ok'] for x in d['checks'])
    assert all(d['frozen_before']==d['frozen_after']==focus['frozen_after'] for d in (dev,install,media))
    final=not args.candidate
    if final:
        assert full['terminal_ok'] and full['status']=='passed' and full['methods']==1696 and full['skipped']==0 and full['frozen_equal']
        assert full['frozen_after']==focus['frozen_after']
        skills=read(BASE/'skills-r1.json');skill_text=f"{skills['skill_count']} Skills／{skills['local_links_checked']} 本地引用，发行联接与正文均核对"
        full_text=f"完整原生回归 **{full['methods']}/{full['methods']}、{full['suite_seconds']:.3f} 秒、0 跳过、223 冻结输入＋8 外部夹具前后相同**"
    else:
        skill_text='4 份相关 Skill 已更新，17 份安装联接待发行时核对'
        full_text='完整原生回归仍在运行，**尚未作为 main 全量发行验收**'
    summary=(f'2026-10-20 **V75（空间／抠像效果关键帧限定验收）**：catalog **0.7.0**，45 项效果不增计；'
        '新增高斯模糊、颜色对比、镜头畸变、RGB 抠像 **4 类／14 数值通道**，累计 **10 类／34 原生命令通道**。'
        '支持作者时钟、六插值、窗口／拆分、完整输出反转、工程包／片段跨项目重建和递归预算。'
        '修复超大整数校验异常、静态及动态抠像覆盖原有 Alpha、颜色对比目录默认值；模糊零半径为精确中性。'
        f'{full_text}；29 新方法为全量子集。专项 **29/29、{focus["suite_seconds"]:.3f} 秒、0 跳过**。'
        f'开发 **{dev["cli_calls"]} CLI／{len(dev["checks"])} 检查**，四组各 24 帧，独立静态原生选项＋source-over 参照的全 RGB 最大差均 **0**，'
        '输出 Alpha 与每组完整 **96,000 帧立体声 PCM** 精确。'
        f'离线 **{len(install["resource_hashes"])} 资源／7 wheels／{install["isolated_cli_calls"]} 隔离 CLI＋1 模块来源探针／{len(install["checks"])} 安装检查**，'
        f'开发／安装全部解码摘要、作者参数、抠像覆盖元数据及每帧 PTS 一致；{skill_text}。'
        '保留全部失败和已停止的 full-r1；只静看最终开发／安装两张联系图，未连续审片或听审。'
        'gblur 会处理 Alpha，colorkey 的 RGB 距离覆盖乘以该阶段输入 Alpha，镜头采用原生采样；自然绿幕／去溢色、线性光／HDR、长片性能和完整剪映等价未验收。')
    rows=[
        ('V75-01','旧版本基线','5fcff32f 的四类动态曲线均未生成控制，10 个相同输入帧的输出仍恒定；222 旧输入不变','baseline-r1.json'),
        ('V75-02','作者与原生命令',f'29/29；14 通道、六插值、分数帧率、实例、边界、缓存、预算、窗口、反转、包／片段、静态／动态 Alpha 和独立预算','targeted-r5.json'),
        ('V75-03','模糊聚焦','24 帧；两轴半径动画；独立 RGB 最大差 0；Alpha／完整 PCM 一致','native-r3/verification.json'),
        ('V75-04','镜头畸变','24 帧；k1 动画；独立 RGB 最大差 0；Alpha／PCM 一致','native-r3/verification.json'),
        ('V75-05','RGB 绿幕','24 帧；similarity 动画；独立 RGB 最大差 0；透明输入保持不可见，覆盖乘积与 PCM 一致','native-r3/verification.json'),
        ('V75-06','颜色对比','24 帧；系数与静态权重实际生效；独立 RGB 最大差 0','native-r3/verification.json'),
        ('V75-07','原生离线安装',f'146 资源逐字节相同，7 wheels；27 隔离 CLI＋1 来源探针／{len(install["checks"])} 检查；四组成片一致','installed-r2/verification.json'),
        ('V75-08','完整回归',f'1696/1696；{full["suite_seconds"]:.3f} 秒；0 跳过；223 输入＋8 夹具' if final else '运行中；尚未取得终态通过','full-r2.json'),
        ('V75-09','检查与审片范围','自动检查全部 PTS／PCM，静看开发／安装 PNG；未连续播放、听审或验收自然素材','static-review-r2.json'),
        ('V75-10','错误与参照修正','24 方法首轮含 5 条失败／4 条子测试错误；真实整数溢出已修复，零权重／解析 Bezier 参照修正','targeted-r1.log'),
        ('V75-11','抠像原覆盖保护','修复前 27 方法中 2 项 Alpha 回归失败；修复后静态／动态／多实例均核验，不把原生覆盖写入当作正确语义','targeted-r3-alpha-before-fix.json'),
        ('V75-12','保留未完成全量','full-r1 为修改前主动停止，终态失败且无方法计数；不纳入通过统计','full-r1-stop.json'),
    ]
    def table(path):
        text='| 编号 | 功能性核验／实测 | 实际结果 | 证据 |\n|---|---|---|---|\n'
        return text+'\n'.join('| '+' | '.join((n,a,b,link(path,'记录',BASE/c)))+' |' for n,a,b,c in rows)
    def media_block(path):
        text=(link(path,'原始前景 PNG',ROOT/NATIVE/'foreground-original.png')+' · '+link(path,'原始棋盘 PNG',ROOT/NATIVE/'background-original.png')+' · '+
            link(path,'原始双声道 WAV',ROOT/NATIVE/'audio-original.wav')+' · '+link(path,'静态输入视频预览',ROOT/NATIVE/'source-preview.mp4')+'。\n\n')
        for label,title in [('blur-focus','模糊聚焦'),('lens-ramp','镜头畸变'),('key-ramp','RGB 抠像'),('contrast-ramp','颜色对比')]:
            text+=link(path,title+' MP4',ROOT/NATIVE/(label+'.mp4'))+' · '+link(path,'FFV1／PCM 精确参照',ROOT/NATIVE/(label+'-lossless.mkv'))+'\n\n'
            text+='!'+link(path,title+'（实际成片 GIF，有损预览）',ROOT/NATIVE/(label+'.gif'))+'\n\n'
        return text
    for name in DOCUMENTS:
        path=ROOT/name;body=summary+'\n\n'+link(path,'契约',CONTRACT)+' · '+link(path,'实测与失败',REPORT)+' · '+link(path,'当前回归',BASE/'full-r2.json')
        if name=='README.md':body+='\n\n'+table(path)+'\n\n'+media_block(path)
        block(path,'V75-CURRENT',body)
    detail=summary+'\n\n'+table(REPORT)+'\n\n'+media_block(REPORT)
    detail+='开发／安装公共文件清单、SHA-256、原生命令、每帧 RGB 差、完整解码摘要和 PTS 保存在两份样例收据中；MP4/GIF 不用于精确像素或 PCM 断言。\n\n'
    detail+=link(REPORT,'安装样例收据',BASE/'installed-r2/media/verification.json')+' · '+link(REPORT,'全部安装检查',BASE/'installed-r2/verification.json')+' · '+link(REPORT,'静态审查',BASE/'static-review-r2.json')
    block(REPORT,'V75-DETAIL',detail)
    block(CONTRACT,'V75-STATE',('发行限定验收：'+full_text+'；'+skill_text+'。') if final else '候选版本：专项、真实 CLI 和隔离安装通过；完整回归与 main 发行尚未完成。')
    print(json.dumps({'status':'candidate-documents-synchronized' if args.candidate else 'documents-synchronized','documents':len(DOCUMENTS)+2,'full_terminal':bool(full.get('terminal_ok'))}))


if __name__=='__main__':main()
