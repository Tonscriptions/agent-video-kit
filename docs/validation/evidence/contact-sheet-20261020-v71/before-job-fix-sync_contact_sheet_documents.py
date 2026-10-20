"""Synchronize V71 measured docs; never turn a running suite into acceptance."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/contact-sheet-20261020-v71'
REPORT=ROOT/'docs/validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md'
CONTRACT=ROOT/'docs/specs/透明视频多帧联系表与实际时间锚点契约_v0.1_2026-10-20.md'
DOCUMENTS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def relative(source,target):return Path(os.path.relpath(target,source.parent)).as_posix()


def insert(path,content,marker='V71-CURRENT'):
    value=path.read_text(encoding='utf8');start='<!-- '+marker+' -->';end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in value:
        a=value.index(start);b=value.index(end,a)+len(end);value=value[:a]+block+value[b:]
    else:
        first,rest=value.split('\n',1);value=first+'\n\n'+block+'\n'+rest
    path.write_text(value,encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true')
    args=parser.parse_args();current=frozen();assert len(current)==216
    focus=read(BASE/'focus-r3.json');dev=read(BASE/'native-r1/verification.json')
    install=read(BASE/'installed-r1/verification.json');actual=read(BASE/'installed-r1/media/verification.json')
    media=read(BASE/'media-inventory-r1.json');static=read(BASE/'static-review-r2.json')
    full=read(BASE/'full-r1.json')
    for value in (focus,dev,install,actual,media):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert focus['terminal_ok'] and focus['methods']==25 and focus['skipped']==0
    assert all(v['status']=='passed' for v in (dev,install,actual,media))
    assert dev['cli_calls']==actual['cli_calls']==7 and len(dev['checks'])==len(actual['checks'])==35
    assert len(install['resource_hashes'])==144 and install['bundle']['wheels']==7
    assert install['isolated_cli_calls']==10 and install['module_origin_probes']==1 and len(install['checks'])==38
    assert media['public_file_count']==33 and media['actual_video_probes']==6 and static['panels_per_run']==16
    for item in static['files']:assert sha(ROOT/item['path'])==item['sha256']
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1589 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
    full_note=('完整回归运行中，尚未验收；预计数不作为通过数。' if args.candidate else
        f'隔离分支完整 **1589/1589、{full["suite_seconds"]:.3f} 秒、0 跳过、216 输入冻结**，发布工作区相同相对路径字节逐项匹配；25 新方法为其子集。')
    skills_path=BASE/'skills-r1.json';skills=read(skills_path) if skills_path.exists() else None
    if not args.candidate:assert skills and skills['skill_count']==17 and skills['local_links_checked']==264
    skills_note=(f'**17 Skills/{skills["local_links_checked"]} 本地引用**。' if skills else
        '2 份 Skill 已补联系表操作说明，待主工作区发现联接与全部引用核验。')
    summary=('2026-10-20 **V71（'+('隔离候选，尚未发行' if args.candidate else '透明联系表限定验收')+'）**：'
        '参考 OpenFilm `lookMedia`，新增原生 `media contact-sheet`；透明视频按实际 PTS 输出棋盘格、浅底、深底、Alpha 四视图。'
        '显式锚点选择请求时刻或之后的首个可解码帧，0.17 秒样例实际为 0.25 秒，不伪造精确播放定位。'
        +full_note+f'针对性 **25/25、{focus["suite_seconds"]:.3f} 秒、0 跳过**。'
        '开发原生 **7 CLI/35 检查**；四锚点均与完整 24 帧解码对应帧逐字节一致，16 面板通过独立 Alpha 像素对照。'
        '**144 资源/7 wheels/10 隔离 CLI＋1 模块来源/38 安装检查**，安装联系表 PNG、来源帧、Alpha、PTS 和字体摘要与开发版一致。'
        +skills_note+'**33 公开文件、6 次实际视频探测**；静看开发/安装两张图，未连续播放或听审。'
        '本版无 GUI、浏览器、模型前向或网络媒体请求；8-bit 抽样预览不验收自然人像、HDR、长片性能或完整剪映等价。')
    table='''| 编号 | 功能性核验 | 本轮结果与边界 |
|---|---|---|
| V71-01 | 透明解码 | VP9/libvpx；4 帧与独立完整解码逐字节一致，各 Alpha 0..255 |
| V71-02 | 实际时间锚点 | 请求 0/0.17/0.75/1.5 秒→实际 0/0.25/0.75/1.5 秒；整数 PTS＋有理数时基 |
| V71-03 | 四种视图 | 4 锚点/16 面板独立逐像素 Alpha 对照；自动 count 是去重后的数量上限 |
| V71-04 | 时钟与失败 | VFR、非零起点、1200 秒偏移、SAR、缩放、图片、源变化、真实进程取消；超时与写盘故障注明测试替身 |
| V71-05 | 原生 CLI | 7 CLI/35 检查；9 次脚本直接进程调用已含 CLI，不是子进程树总计；创作字节不改写 |
| V71-06 | 独立安装 | 144 资源、7 wheels、10 隔离 CLI＋1 模块来源、38 检查；联系表原字节及解码证据相同 |
| V71-07 | 完整回归 | FULL_NOTE |
| V71-08 | 演示与质量 | 原始 MP4、透明 WebM、实际 2560×444 PNG；33 文件/6 探测；静看 2 图，未连续播放或听审 |
'''.replace('FULL_NOTE',full_note.replace('**',''))
    for name in DOCUMENTS:
        path=ROOT/name;content=summary+' [契约、原视频、实际图片及失败]('+relative(path,REPORT)+')。'
        if name=='README.md':
            content+='\n\n'+table+'\n原始输入：[MP4 预览](docs/assets/contact-sheet-20261020-v71-native-r1/source-preview.mp4)、'
            content+='[透明原始 MKV](docs/assets/contact-sheet-20261020-v71-native-r1/source.mkv)、'
            content+='[实际透明 WebM](docs/assets/contact-sheet-20261020-v71-native-r1/source-alpha.webm)；'
            content+='[安装版实际输出](docs/assets/contact-sheet-20261020-v71-installed-r1/contact/contact.png)。\n\n'
            content+='![四锚点与 Alpha 实际联系表](docs/assets/contact-sheet-20261020-v71-native-r1/contact/contact.png)'
        insert(path,content)
    insert(ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',
        '联系表后续实现：'+summary+' [实测]('+relative(ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',REPORT)+')。以下原型工时为当时估算，非本版生产投入统计。')
    insert(REPORT,summary,marker='V71-MEASURED')
    value=REPORT.read_text(encoding='utf8')
    value=re.sub(r'^\| V71-10 \| 完整回归 \|.*$', '| V71-10 | 完整回归 | '+full_note.replace('**','')+' |',value,flags=re.M)
    REPORT.write_text(value,encoding='utf8',newline='\n')
    status=('状态：V71 隔离分支候选；针对性、原生样例与离线安装通过，完整回归运行中，尚未发行。' if args.candidate else
        '状态：V71 原生联系表、实际 PTS、透明像素、离线安装与相同 216 输入的隔离完整回归限定通过；自然素材/HDR/连续质量/完整剪映等价未验收。')
    value=CONTRACT.read_text(encoding='utf8');value=re.sub(r'^状态：.*$',status,value,count=1,flags=re.M)
    CONTRACT.write_text(value,encoding='utf8',newline='\n')
    if not args.candidate:
        path=ROOT/'video-cut-install-manifest.json';mapping=read(path)
        for row in mapping['skills']:
            source=ROOT/'skills'/row['name']/'SKILL.md';checked=next(v for v in skills['results'] if v['skill']==row['name'])
            assert sha(source)==checked['sha256'];value=checked['sha256'][7:]
            if row['skill_md_sha256']!=value:
                row.setdefault('skill_md_sha256_history',[]).append({'sha256':row['skill_md_sha256'],
                    'replaced_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'V71 native alpha contact sheets and actual frame PTS'})
                row['skill_md_sha256']=value
            row['description']=re.search(r'^description: (.+)$',source.read_text(encoding='utf8'),re.M)[1].strip('"')
        previous=mapping['current_audit'];history=mapping.setdefault('audit_history',[])
        name=skills_path.relative_to(ROOT).as_posix()
        if previous.get('record')!=name and previous not in history:history.append(previous)
        mapping['current_audit']={'record':name,'record_sha256':sha(skills_path),
            'checked_at_utc':skills['checked_at_utc'],'skills':17,'local_links_checked':264,
            'semantics':'V71 native alpha contact sheets; actual PTS and independent pixel/installed contracts; natural/HDR/full CapCut quality unaccepted','candidate':False}
        path.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'candidate_documents' if args.candidate else 'terminal_documents',
        'frozen_inputs':len(current),'full_methods':full.get('methods'),'full_accepted':not args.candidate}))


if __name__=='__main__':main()
