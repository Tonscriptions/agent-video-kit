"""Synchronize measured V72 docs from terminal evidence without changing history."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/html-shutter-20261020-v72'
REPORT=ROOT/'docs/validation/HTML子帧快门与透明混合实测_2026-10-20.md'
CONTRACT=ROOT/'docs/specs/HTML子帧快门采样与预乘透明合成契约_v0.1_2026-10-20.md'
RESEARCH=ROOT/'docs/specs/HTML子帧快门采样增量设计_v0.1_2026-10-20.md'
DOCUMENTS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
    'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
    'docs/validation/README功能核验与实测演示_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def relative(source,target):return Path(os.path.relpath(target,source.parent)).as_posix()


def insert(path,content,marker='V72-CURRENT'):
    text=path.read_text(encoding='utf8');start='<!-- '+marker+' -->';end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1);text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--candidate',action='store_true')
    args=parser.parse_args();current=frozen();assert len(current)==218
    focus=read(BASE/'focus-r3.json');dev=read(BASE/'native-r2/verification.json')
    install=read(BASE/'installed-r1/verification.json');actual=read(BASE/'installed-r1/media/verification.json')
    old=read(BASE/'default-compat-r1/verification.json');media=read(BASE/'media-inventory-r1.json')
    static=read(BASE/'static-review-r1.json');full=read(BASE/'full-r1.json')
    for value in (focus,dev,install,actual,old,media):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert focus['terminal_ok'] and focus['methods']==21 and focus['skipped']==0
    assert all(x['status']=='passed' for x in (dev,install,actual,old,media))
    assert len(install['resource_hashes'])==145 and install['bundle']['wheels']==7
    assert install['module_origin_probes']==1
    assert media['actual_video_probes']==14
    assert old['isolated_older_cli_calls']==4
    assert not any(static[k] for k in ('continuous_playback_reviewed','natural_quality_accepted','full_capcut_parity'))
    for row in static['files']:assert sha(ROOT/row['path'])==row['sha256']
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1610 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
        assert full['external_fixtures_equal'] and full['external_fixture_count']==5 and full['external_fixture_manifest_unchanged'] and full['verification_scripts_equal']
    full_note=('完整回归运行中，尚未验收；不将预期方法数计为通过。' if args.candidate else
        f'隔离分支完整 **1610/1610、{full["suite_seconds"]:.3f} 秒、0 跳过、218 源码输入＋5 外部夹具前后相同**；发布路径字节逐项匹配，21 新方法为其子集。')
    skill_path=BASE/'skills-r1.json';skills=read(skill_path) if skill_path.exists() else None
    if not args.candidate:assert skills and skills['skill_count']==17 and skills['local_links_checked']==270
    skills_note=('**17 Skills/270 本地引用**。' if skills else '3 份 Skill 已补操作/验收说明，待主工作区发现联接和全部本地引用核验。')
    summary=('2026-10-20 **V72（'+('隔离候选，尚未发行' if args.candidate else 'HTML 子帧快门限定验收')+'）**：'
        '采用 OpenFilm 子帧重绘思路，新增可选 `motion html-render --shutter-samples/--shutter-fraction`、源切点与配方重放。'
        '中心中点采样＋预乘编码域 sRGB 8-bit；默认/零快门保留原帧路径。'+full_note+
        f'专项 **21/21、{focus["suite_seconds"]:.3f} 秒、0 跳过**；公开原生 **{dev["cli_calls"]} CLI/{len(dev["checks"])} 检查**，'
        '整片 RGBA 对照独立 Python 参考；strict 检查每个实际子帧，打包和片段跨项目重建像素相同。'
        f'**145 资源/7 wheels/{install["isolated_cli_calls"]} 隔离 CLI＋1 模块来源/{len(install["checks"])} 安装检查**，开发/安装全部公开输入输出字节一致。'
        '**4 次旧安装 CLI**另验默认 PNG、整片 RGBA 与 PTS；不与新安装操作合并。'
        +skills_note+f'**{media["public_file_count"]} 公开文件/14 次实际视频探测**。'
        '保留旧 Schema 摘要、Canvas 严格布局测试设置和演示验证命令失败；只静看图片，未连续审片或听审。'
        '本轮无模型/GPU 前向、GUI、网络媒体、Docker/WSL/虚拟环境；自然运动、HDR、4K 长片性能和完整剪映等价未验收。')
    table='''| 编号 | 功能性核验 | 本轮实际结果与边界 |
|---|---|---|
| V72-01 | 子帧重绘与确定性 | 4 个真实时刻/输出帧，三次新鲜上下文逐子帧相同；中心中点相位 |
| V72-02 | 透明与整片像素 | 锐利/无切点/显式切点各 16 帧，独立 Python 逐像素参考；默认、零快门、半透明和隐藏 RGB 控制 |
| V72-03 | 时间与场景边界 | 8fps/2s/16 帧精确 PTS；cut_tick=89100 防止声明切点跨场；不自动推断未声明切点 |
| V72-04 | strict 与取消 | 所有实际子帧的 DOM 门禁；Canvas 语义文字继续拒绝；首合成帧后实际取消及进程回收 |
| V72-05 | 结构化复用 | 原生 NATIVE_CLI CLI/NATIVE_CHECKS 检查；项目打包/导入和片段跨项目重建整片 RGBA 相同 |
| V72-06 | 独立离线安装 | 145 资源/7 wheels/INSTALL_CLI 隔离 CLI＋1 模块来源/INSTALL_CHECKS 检查；全部公开产物字节相同 |
| V72-07 | 历史默认兼容 | 4 次旧安装 CLI；旧/新默认 PNG、RGBA、PTS 相同，容器摘要实际记录；不是所有模板兼容声明 |
| V72-08 | 完整回归 | FULL_NOTE |
| V72-09 | 公开证据与限制 | PUBLIC_FILES 文件/14 视频探测；输入 HTML、实际 NUT/MP4/GIF、失败原记录；未连续审片或接受自然/HDR/剪映完整效果 |
'''
    for key,value in {'NATIVE_CLI':dev['cli_calls'],'NATIVE_CHECKS':len(dev['checks']),
                       'INSTALL_CLI':install['isolated_cli_calls'],'INSTALL_CHECKS':len(install['checks']),
                       'FULL_NOTE':full_note.replace('**',''),'PUBLIC_FILES':media['public_file_count']}.items():table=table.replace(key,str(value))
    for name in DOCUMENTS:
        path=ROOT/name;content=summary+' [契约、原输入、实际输出及失败]('+relative(path,REPORT)+')。'
        if name=='README.md':
            content+='\n\n'+table+'\n原始输入：[可编辑 HTML](docs/assets/html-shutter-20261020-v72-native-r2/source/index.html)、[锐利预览 MP4](docs/assets/html-shutter-20261020-v72-native-r2/sharp.mp4)；'
            content+='实际输出：[透明 NUT](docs/assets/html-shutter-20261020-v72-native-r2/cut-alpha.nut)、[三列 MP4](docs/assets/html-shutter-20261020-v72-native-r2/comparison.mp4)。'
            content+='三列依次为锐利、未声明内部切点的快门、有显式切点的快门；均为实际输出，GIF 为量化预览。\n\n'
            content+='![HTML 实际子帧快门对照](docs/assets/html-shutter-20261020-v72-native-r2/comparison.gif)'
        insert(path,content)
    insert(ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',summary+' [实测]('+relative(ROOT/'docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md',REPORT)+')。原 3–5 人日仅为受限原型估算。')
    insert(RESEARCH,summary+' [已实现契约]('+relative(RESEARCH,CONTRACT)+')。以下 R10 状态及拟议文字保留为历史研究，不替代 V72 证据。')
    insert(REPORT,summary+'\n\n'+table,marker='V72-MEASURED')
    report_text=REPORT.read_text(encoding='utf8')
    report_text=report_text.replace('| V72-08 | 原生公开样例、打包/导入、片段跨项目复用 | 运行中，不计为通过 |',
        f'| V72-08 | 原生公开样例、打包/导入、片段跨项目复用 | {dev["cli_calls"]} CLI/{len(dev["checks"])} 检查通过；整片 RGBA 与独立参考/跨项目重建一致 |')
    report_text=report_text.replace('| V72-09 | 七 wheel 离线安装与独立解释器 | 待终态；Python/FFmpeg/Node/playwright-core/Chromium 为已有外部本地运行时 |',
        f'| V72-09 | 七 wheel 离线安装与独立解释器 | 145 资源/7 wheels/{install["isolated_cli_calls"]} 隔离 CLI＋1 来源/{len(install["checks"])} 检查通过；外部本地运行时另行登记 |')
    if not args.candidate:
        report_text=report_text.replace('| V72-10 | 完整回归及外部媒体夹具 | 运行中，不使用预期 1610 项作为通过数 |',
            '| V72-10 | 完整回归及外部媒体夹具 | '+full_note.replace('**','')+' |')
    report_text=report_text.replace('实际公开演示将保留原始 HTML/manifest、无 Alpha 丢失的 FFV1/BGRA NUT、棋盘格 MP4、锐利/无切点模糊/有切点模糊对照 GIF、接触图与来源摘要。',
        '已保留 [原始 HTML](../assets/html-shutter-20261020-v72-native-r2/source/index.html)、[锐利预览](../assets/html-shutter-20261020-v72-native-r2/sharp.mp4)、[有切点透明 NUT](../assets/html-shutter-20261020-v72-native-r2/cut-alpha.nut)、[三列 MP4](../assets/html-shutter-20261020-v72-native-r2/comparison.mp4)、[实际 GIF](../assets/html-shutter-20261020-v72-native-r2/comparison.gif) 和 [静态接触图](../assets/html-shutter-20261020-v72-native-r2/contact.png)。三列为锐利/无内部切点/有显式切点。来源与全部摘要见媒体清单。')
    REPORT.write_text(report_text,encoding='utf8',newline='\n')
    status=('状态：V72 隔离候选，专项/原生/离线安装通过，完整回归运行中；尚未发布。' if args.candidate else
        '状态：V72 子帧快门、预乘透明、时钟、结构化复用、离线安装和相同输入的隔离完整回归限定通过；自然/HDR/连续质量/完整剪映等价未验收。')
    for path in (REPORT,CONTRACT):
        text=path.read_text(encoding='utf8');text=re.sub(r'^状态：.*$',status,text,count=1,flags=re.M)
        path.write_text(text,encoding='utf8',newline='\n')
    if not args.candidate:
        path=ROOT/'video-cut-install-manifest.json';mapping=read(path)
        for row in mapping['skills']:
            source=ROOT/'skills'/row['name']/'SKILL.md';checked=next(x for x in skills['results'] if x['skill']==row['name'])
            assert sha(source)==checked['sha256'];value=checked['sha256'][7:]
            if row['skill_md_sha256']!=value:
                row.setdefault('skill_md_sha256_history',[]).append({'sha256':row['skill_md_sha256'],'replaced_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'V72 local HTML shutter and sample/Alpha quality scope'})
                row['skill_md_sha256']=value
            row['description']=re.search(r'^description: (.+)$',source.read_text(encoding='utf8'),re.M)[1].strip('"')
        previous=mapping['current_audit'];history=mapping.setdefault('audit_history',[]);name=skill_path.relative_to(ROOT).as_posix()
        if previous.get('record')!=name and previous not in history:history.append(previous)
        mapping['current_audit']={'record':name,'record_sha256':sha(skill_path),'checked_at_utc':skills['checked_at_utc'],'skills':17,'local_links_checked':270,
            'semantics':'V72 local HTML subframe redraws, explicit cuts and premultiplied encoded-sRGB; natural/HDR/complete CapCut quality unaccepted','candidate':False}
        path.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'candidate_documents' if args.candidate else 'terminal_documents','frozen_inputs':218,'full_methods':full.get('methods'),'full_accepted':not args.candidate}))


if __name__=='__main__':main()
