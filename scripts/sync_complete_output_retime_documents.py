"""Synchronize V57 current docs and skills mapping using actual receipts, without rewriting history."""
from __future__ import annotations
import argparse,hashlib,json,re
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/retime-edits-20261019-v57'
PUBLIC=ROOT/'docs/assets/retime-release-20261019-v57'
NATIVE=ROOT/'docs/validation/evidence/retime-native-release-20261019-v57'
CONTRACT='完整作者输出变速与磁吸联动契约_v0.1_2026-10-18.md'
REPORT='完整作者输出变速与磁吸联动实测_2026-10-19.md'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
 'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
 'docs/validation/README功能核验与实测演示_2026-10-16.md']

def read(p):return json.loads(p.read_bytes())
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def line(text,prefix,value):
    assert sum(x.startswith(prefix) for x in text.splitlines())==1,prefix
    return '\n'.join(value if x.startswith(prefix) else x for x in text.splitlines())+'\n'
def marked(text,name,value):
    a,b='<!-- '+name+' -->','<!-- /'+name+' -->'
    block=a+'\n'+value+'\n'+b
    if a in text:return text[:text.index(a)]+block+text[text.index(b)+len(b):]
    head,rest=text.split('\n',1);return head+'\n\n'+block+'\n\n'+rest.lstrip('\n')

def run(final):
    current=frozen();full=read(EVIDENCE/'full-final.json');targeted=read(EVIDENCE/'targeted-final.json')
    smoke=read(PUBLIC/'verification.json');native=read(NATIVE/'verification.json');skills=read(EVIDENCE/'skills.json')
    assert len(current)==184 and full['frozen_before']==current
    for r in (targeted,smoke,native):assert r['frozen_before']==r['frozen_after']==current
    assert targeted['methods']==40 and targeted['terminal_ok'] and targeted['skipped']==0
    assert len(smoke['cli_calls'])==62 and smoke['main_frames']==344 and smoke['stereo_sample_frames']==1651200
    assert native['isolated_cli_calls']==51 and native['installed_package_files']==123 and native['actual_new_frames']==454
    assert native['actual_new_stereo_sample_frames']==2179200
    assert skills['skill_count']==14 and skills['local_links_checked']==202
    if final:
        assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0
        assert full['methods']==1329 and full['frozen_after']==current
        complete=f"1329/1329、{full['suite_seconds']:.3f} 秒、0 跳过、184 文件冻结"
    else:complete='完整回归运行中、184 文件已冻结；最近发布 V56 1289/1289 为历史结果'
    for name in DOCS:
        path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
        report=('docs/validation/' if name=='README.md' else '' if name.startswith('docs/validation/') else '../validation/' if name.startswith('docs/specs/') else 'validation/')+REPORT
        contract=('docs/specs/' if name=='README.md' else '../specs/' if name.startswith('docs/validation/') else '' if name.startswith('docs/specs/') else 'specs/')+CONTRACT
        text=marked(text,'V57-CURRENT',
            '2026-10-19 **V57（产品）**：完整作者输出的相对变速、曲线、反向、定格与主轨自动随动，保留可编辑作者子序列；'
            '局部关联音画共用宿主时钟，连续 BGM 可选保持速度波纹或显式变速。**'+complete+'**；'
            '40 新增专项、66 旧磁吸集成为完整子集，不叠加。**62 CLI /344 主帧 /1,651,200 立体声采样帧**，RGB 最大差 1、PCM 0；'
            '**123 包内文件 /51 隔离 CLI /454 安装帧 /2,179,200 采样帧**；**14 Skills /202 引用**。'
            '原曲线 PCM 失败已修复；文件头部与总线尾部选样参考分开，开发失败全数保留。'
            '未连续播放/听审、自然质量、动态外部 blend、全手势、长片/HDR、另一台机器及完整剪映等价未验收。'
            f'[契约]({contract})、[原输入/MP4/GIF/失败/发行]({report})。')
        if name=='README.md':
            text=line(text,'| V13 |',f'| V13 | 产品自动回归 | 最近 V57 {complete}；40 新增为全量子集 | 历史、研究、安装和定向检查不相加；完整剪映仍未验收 | [完整日志](docs/validation/evidence/retime-edits-20261019-v57/full-final.log)、[终态](docs/validation/evidence/retime-edits-20261019-v57/full-final.json) |')
            row=(f'| V57 | 完整作者输出变速与磁吸联动 | 40 新增；{complete}；62 CLI/344 帧/1,651,200 采样帧；123 文件/51 隔离 CLI/454 安装帧；14 Skills/202 引用 | 原帧/原 PCM、同版作者图及原生 DSP 尾部参考分计；真实失败保留；未听审或完整等价 | [契约]({contract})、[原片/GIF/失败/安装]({report}) |')
            if '| V57 |' in text:text=line(text,'| V57 |',row)
            else:
                rows=text.splitlines();i=next(i for i,x in enumerate(rows) if x.startswith('| V56 |'));rows.insert(i+1,row);text='\n'.join(rows)+'\n'
            demo=('**V57 实际完整输出定格**：保持原第 24 帧与关联字幕 TWO 0.3 秒，再继续播放；GIF 来自真实 CLI 输出且无声音。'
                '[原 MKV](docs/assets/retime-release-20261019-v57/source.mkv)、[原输入 MP4](docs/assets/retime-release-20261019-v57/source-preview.mp4)、'
                '[原 WAV](docs/assets/retime-release-20261019-v57/source.wav)、[实际有声 MP4](docs/assets/retime-release-20261019-v57/RT04.mp4)、'
                '[可编辑工程](docs/assets/retime-release-20261019-v57/RT04.aevpkg.zip)、'
                '[原生离线包](docs/assets/retime-release-20261019-v57/agent-video-kit-cp313-win_amd64.zip)、'
                f'[全部 9 组/失败/离线包]({report})。\n\n![V57 真实定格与关联字幕](docs/assets/retime-release-20261019-v57/retime.gif)')
            marker='<!-- V57-DEMO -->'
            if marker in text:
                text=text[:text.index(marker)]+marker+'\n'+demo+'\n<!-- /V57-DEMO -->'+text[text.index('<!-- /V57-DEMO -->')+len('<!-- /V57-DEMO -->'):]
            else:text=text.replace('**V56 实际磁吸演示**',marker+'\n'+demo+'\n<!-- /V57-DEMO -->\n\n**V56 实际磁吸演示**',1)
            text=line(text,'- 当前模块进度见',f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近 V57 {complete}；相对完整输出变速与关联自动随动、持久磁吸均已受控实现。绝对源参数入口保持旧含义；动态外部混合、全手势、自然质量、CTC 精度、长片/HDR、另一台机器、完整内容库及完整剪映等价继续开放。')
        if name=='docs/构建进度总表_2026-10-16.md':
            changes={
                '| 核对日期 |':'| 核对日期 | 2026-10-19，Asia/Taipei；证据轮次从 10-17 开始 |',
                '| 本次状态快照 |':f'| 本次状态快照 | 2026-10-19，README V57；{complete}；40 新增与 66 旧磁吸集成分别为全量子集 |',
                '| 最近产品增量 |':'| 最近产品增量 | V57 相对完整输出变速/曲线/反向/定格、主轨随动、局部关联共同时钟、BGM 波纹/显式变速；完整总线跳点及 tempo 上下文修复 |',
                '| 研究状态与历史快照 |':'| 研究状态与历史快照 | OpenFilm R04 固定 main 5c2000b8/713 文件比较；914 stars/95 forks 是历史 API 时点；V57 为自研适配，不重复计作 OpenFilm 新算法或新模型前向 |',
                '| 核对范围 |':f'| 核对范围 | V57 {complete}；62 CLI/344 帧/1,651,200 采样帧；123 包内文件/51 隔离 CLI/454 帧/2,179,200 采样帧；独立原源与同版作者图及 DSP 参考分计 |',
                '| 当前生产代码 |':'| 当前生产代码 | 产品/测试/Schema/发行输入共 184 文件；专项/媒体/安装前后冻结一致，完整终态另列 | 184 不是纯运行时数量；发行包内 123 文件，失败保留 |',
                '| 最近完整产品回归 |':f'| 最近完整产品回归 | V57 {complete} | [完整日志](validation/evidence/retime-edits-20261019-v57/full-final.log)；耗时不是性能基准 |',
                '| 最近产品新增子集 |':'| 最近产品新增子集 | V57 新增 40 方法（36 编辑/CLI＋4 嵌套 tempo 时钟），66 既有磁吸集成也已重跑 | 为完整子集，研究/安装/旧回归不相加 |',
                '| 最近产品实际核验 |':f'| 最近产品实际核验 | V57 62 CLI/344 主帧/1,651,200 采样帧；另 51 隔离 CLI/454 帧/2,179,200 采样帧 | [原片/GIF/失败/发行](validation/{REPORT})；无连续播放/听审 |',
                '| Skill 审计 |':'| Skill 审计 | 14 Skills/202 引用；格式/目录联接/SHA 通过 | [当前记录](validation/evidence/retime-edits-20261019-v57/skills.json)；不证明自然质量 |',
                '| 文档 |':'| 文档 | README/进度/契约/矩阵/基线/原片 GIF 同步，当前行指向 V57 | [当前审计](validation/evidence/retime-edits-20261019-v57/release.json)；不证明外链、锚点、许可或自然质量 |'}
            for prefix,value in changes.items():text=line(text,prefix,value)
            text=line(text,'“已实现”表示',f'“已实现”表示列出的实现和验证，不表示完整剪映等价。当前 V57 {complete}；40 新增、研究、媒体和安装各自记录。自然质量、动态混合、CTC/声音和内容规模继续开放。')
        if name.startswith('docs/validation/能力覆盖'):
            row=(f'| 完整输出变速与磁吸联动（V57） | 恒速/曲线/反向/定格、可编辑作者图、多宿主、关联局部共同时钟、BGM ripple/retime、完整总线 tempo | [40 新增/9 组/原生安装]({report})；{complete}，344 帧/1,651,200 采样帧 | 动态外部 blend/直接跟踪与转场端点拒绝；根标记/总线绝对时钟、自然听感、全手势/长片/完整等价未验收 |')
            if '| 完整输出变速与磁吸联动（V57） |' in text:text=line(text,'| 完整输出变速与磁吸联动（V57） |',row)
            else:text=text.replace('| 持久磁吸与同步分段（V56） |',row+'\n| 持久磁吸与同步分段（V56） |',1)
        path.write_text(text,encoding='utf-8',newline='\n')
    path=ROOT/'docs/validation'/REPORT;text=path.read_text(encoding='utf-8')
    table=('| 编号 | 核验 | 实际结果与证据 |\n|---|---|---|\n'
        '| CHECK-01 | 新增专项与既有集成 | 40 新增（36 编辑/CLI＋4 原生 tempo 时钟），0 跳过；另 66 旧磁吸集成。'
        '[40 终态](evidence/retime-edits-20261019-v57/targeted-final.json)、[66 终态](evidence/retime-edits-20261019-v57/magnetic-final.json)；均为完整子集 |\n'
        f'| CHECK-02 | 完整产品回归 | **{complete}**。[完整 JSON](evidence/retime-edits-20261019-v57/full-final.json)、[日志](evidence/retime-edits-20261019-v57/full-final.log) |\n'
        '| CHECK-03 | 实际开发音画 | 62 CLI、9 组、344 帧/1,651,200 立体声采样帧；RGB 1/PCM 0；独立原源/同版作者图及原生 DSP 参考分计 |\n'
        '| CHECK-04 | 原生离线安装 | 7 个固定 wheel、123 包内文件原字节一致；51 个 -I -S 独立 CLI；454 新安装帧/2,179,200 采样帧；复现全部 9 组、真实新 retime、幂等、负例和片段组父/子。'
        '[机器证据](evidence/retime-native-release-20261019-v57/verification.json)、[发行 ZIP](../assets/retime-release-20261019-v57/agent-video-kit-cp313-win_amd64.zip)、[发行清单](../assets/retime-release-20261019-v57/release-manifest.json)。未捆绑 Python/FFmpeg、未验证另一台机器 |\n'
        '| CHECK-05 | 编码与静帧 | 九组实际 MP4 的视频 PTS/帧数/音频长度、原 MKV PCM 摘要通过；GIF 480×192、43 帧/4300 ms，无声。'
        '[媒体审计](evidence/retime-edits-20261019-v57/media-release.json)、[静帧记录](evidence/retime-edits-20261019-v57/static-review.json)。没有连续播放或听审 |\n'
        '| CHECK-06 | Skills | 14 Skills/202 本地引用；两项主要时间线技能同步新入口，格式/目录联接/SHA 通过。[审计](evidence/retime-edits-20261019-v57/skills.json) |\n'
        '| CHECK-07 | 失败保留 | 五次失败与第一次小字幕通过版的 628 文件、原源码和作者 PCM 探针保留。'
        '[归档索引](evidence/retime-edits-20261019-v57/development/index.json)、[原文件 ZIP](evidence/retime-edits-20261019-v57/development/pre-release-runs.zip)、[首次安装失败](evidence/retime-native-final-20261019-v57/failure.json)。不纳入通过计数 |\n'
        '| CHECK-08 | 发行绑定 | 最终审计绑定完整终态、冻结源码、媒体、安装、Skills、失败归档和当前文档。'
        '[发行审计](evidence/retime-edits-20261019-v57/release.json)在全量通过后生成 |')
    text=marked(text,'V57-CHECKS',table);path.write_text(text,encoding='utf-8',newline='\n')
    manifest_path=ROOT/'video-cut-install-manifest.json';manifest=read(manifest_path)
    audit_path=(EVIDENCE/'skills.json').relative_to(ROOT).as_posix()
    if manifest['current_audit']['record']!=audit_path:
        manifest.setdefault('audit_history',[]).append(manifest['current_audit'])
    manifest['current_audit']={'record':audit_path,'record_sha256':sha(EVIDENCE/'skills.json'),
        'checked_at_utc':skills['checked_at_utc'],'skills':14,'local_links_checked':202,
        'semantics':'V57 complete visible output retime; original sources, complete author graphs and native tempo references separate; full parity unaccepted'}
    for row in manifest['skills']:
        row['skill_md_sha256']=next(r['sha256'][7:] for r in skills['results'] if r['skill']==row['name'])
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'documents':len(DOCS)+1,'full_final':final,'frozen_files':184,'skill_links':202}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--final',action='store_true');a=p.parse_args();run(a.final)
