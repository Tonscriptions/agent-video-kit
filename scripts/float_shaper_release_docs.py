"""Generate honest candidate previews and final V112 documentation from receipts."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import urllib.parse
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/float-shaper-20261023-lab'
ASSETS='docs/assets/float-shaper-20261023-r1'
REPORT='docs/validation/连续浮点1D-LUT与组合shaper实测_2026-10-23.md'
CONTRACT='docs/specs/连续浮点1D-LUT与组合shaper契约_v0.1_2026-10-23.md'
COMMON=['docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/specs/AgentCLI契约_v0.1_2026-10-13.md']

def read(name):
    path=ROOT/name
    return json.loads(path.read_bytes()) if path.is_file() else None

def accepted(require_full=True):
    before=frozen();assert len(before)==331
    paths=[REL+'/native-r2/verification.json',REL+'/media-r1/verification.json',REL+'/4k-r1/verification.json',REL+'/installed-r1/verification.json']
    if require_full:paths.append(REL+'/full-r1.json')
    records={name:read(name) for name in paths}
    for name,item in records.items():
        assert item is not None and (item.get('status','').startswith('passed') or item.get('terminal_ok') is True),name
        assert item['frozen_before']==item['frozen_after']==before,name
    n=records[paths[0]];assert n['methods']==118 and n['failures']==n['errors']==n['skipped']==0
    m=records[paths[1]];assert m['actual_public_render_CLI_processes']==2 and m['actual_public_preview_CLI_processes']==3
    assert all(row['ok'] for row in m['checks']) and m['shaper_oracle']['maximum_linear_absolute_error']<=2e-6
    k=records[paths[2]];assert k['public_CLI_processes']==8 and len(k['cases'])==3 and all(v['ok'] for v in k['checks'])
    i=records[paths[3]];assert i['isolated_methods']['methods']==118 and i['isolated_methods']['skipped']==0 and len(i['resource_hashes'])==197
    if require_full:
        f=records[paths[4]];assert f['methods']==2930 and f['skipped']==0 and f['terminal_ok']
        assert f['external_fixtures_equal'] and f['verification_scripts_equal']
    return records

def link(source,name,label=None):
    if name not in {REPORT,CONTRACT,*COMMON,'README.md','docs/README.md'} and not (ROOT/name).exists() and not (MAIN/name).exists():return (label or name)+'（待实际生成）'
    path=os.path.relpath(name,os.path.dirname(source) or '.').replace('\\','/')
    return '['+(label or Path(name).name)+']('+path+')'

def status(item,methods=False):
    if item is None:return '尚未执行'
    s=item.get('status','unknown')
    if s.startswith('passed') or item.get('terminal_ok'):
        if methods:return f"通过：{item.get('methods',item.get('isolated_methods',{}).get('methods','?'))} 项"
        return '通过'
    if s.startswith('failed'):return '失败，原证据保留'
    return '执行中'

def documents(destination,require_full=False):
    if require_full:accepted(True)
    n=read(REL+'/native-r2/verification.json');m=read(REL+'/media-r1/verification.json')
    k=read(REL+'/4k-r1/verification.json');i=read(REL+'/installed-r1/verification.json');f=read(REL+'/full-r1.json')
    r1=read(REL+'/native-r1/verification.json');review=read(REL+'/static-review-r1/verification.json')
    source='README.md'
    rows=[
        ('V112.1','1D 五种插值、25 个 1D/3D 原生对照、注册、时钟及正式/预览/PCM/PNG16',status(n,True),REL+'/native-r2/verification.json'),
        ('V112.2','首轮源码回归：118 项，2 失败、0 错误、0 跳过；用例修正后 3 项边界复核通过','历史失败保留',REL+'/fixture-correction-r1/verification.json'),
        ('V112.3','原创 20 帧/2 秒、320×180，2 个正式渲染和 3 个独立预览 CLI；完整与选区 PCM、PNG16',status(m),REL+'/media-r1/verification.json'),
        ('V112.4','3 个 3840×2160 单帧、8 次公开 CLI；每项正式输入与预览、独立行参考',status(k),REL+'/4k-r1/verification.json'),
        ('V112.5','8 个离线 wheel、197 源码/包/安装资源及 NumPy 原始文件，安装后 118 项相关回归',status(i,True),REL+'/installed-r1/verification.json'),
        ('V112.6','完整回归目标 2,930；发现方法数与实际运行通过数分别记录',status(f,True),REL+'/full-r1.json'),
        ('V112.7','5 个时刻/10 面板静态目检；未连续播放或听审','已静态查看' if review and review.get('panels_viewed')==10 else '待静态查看',REL+'/static-review-r1/verification.json'),
    ]
    table='| 编号 | 实际核验内容 | 状态 | 证据 |\n|---|---|---|---|\n'
    table+=''.join('| '+no+' | '+what+' | '+result+' | '+link(source,path,'记录')+' |\n' for no,what,result,path in rows)
    headline='V112：本地 Float32 1D LUT 与组合 shaper'+('（完整验收候选）' if require_full else '（独立候选，验收未完成）')
    section='\n## '+headline+'\n\n'
    intro='新增独立 1D CUBE（每通道 2–65,536 点）与 Resolve 1D→3D 组合 shaper，复用项目 LUT 注册、明确输入/输出信号、原作者强度关键帧、线性混合及共享正式/预览内核。支持 1D nearest/linear/cosine/cubic/spline，3D 保留原五种插值；输入范围明确归一化，输出保留 Float32 过冲与 alpha 位。'
    section+=intro+'\n\n'
    section+=table+'\n'
    if (ROOT/ASSETS/'comparison.gif').is_file():
        section+='![原创原片与实际 CLI 预览对照]('+ASSETS+'/comparison.gif)\n\n'
        section+=link(source,ASSETS+'/original.mp4','原片')+' · '+link(source,ASSETS+'/edited.mp4','正式结果')+' · '+link(source,ASSETS+'/range.mp4','预览选区')+' · '+link(source,ASSETS+'/author-project.json','可编辑项目')+'\n\n'
    section+='`.3dl/.csp/.dat`、逆 LUT、ICC/PQ/HLG/nits、自然审美、连续 4K 性能与峰值 RSS 仍未验收。旧编码渲染路径不新增 1D 能力；单帧 4K、静态目检、编码成功和方法通过数均不代表完整剪映等价。\n\n'
    section+=link(source,REPORT,'当轮实测')+' · '+link(source,CONTRACT,'参数/格式契约')+'\n'
    parent=(MAIN/'README.md').read_text(encoding='utf-8-sig');first,separator,rest=parent.partition('\n')
    assert '## V112：' not in parent
    output={'README.md':first+'\n'+section+'\n'+rest}
    index=(MAIN/'docs/README.md').read_text(encoding='utf-8-sig');first,sep,rest=index.partition('\n')
    output['docs/README.md']=first+'\n\n- '+link('docs/README.md',REPORT,'V112：连续浮点 1D LUT 与组合 shaper 实测')+'\n- '+link('docs/README.md',CONTRACT,'1D/组合 shaper 参数与格式契约')+'\n'+rest
    for name in COMMON:
        text=(MAIN/name).read_text(encoding='utf-8-sig')
        output[name]=text+'\n\n## V112：1D LUT 与组合 shaper\n\n'+intro+'\n\n'+link(name,REPORT,'本轮实际状态与证据')+'；'+link(name,CONTRACT,'契约')+'。独立 1D、明确两级范围、五种 1D 插值和共享正式/预览能力纳入当前候选；未验收项继续保留，不以编码或方法数量宣称剪映等价。\n'
    report='# 连续浮点 1D LUT 与组合 shaper 实测\n\n日期：2026-10-23。'+('本轮通过发布前完整门禁；仍有下列能力/质量边界。' if require_full else '独立候选检查进行中；未发布，不能用发现数替代通过数。')+'\n\n'
    report+='## 1. 实现\n\n'+intro+'\n\n'
    report+='## 2. 实际证据\n\n'
    for no,what,result,path in rows:report+='- **'+no+'** '+what+'。'+result+'；'+link(REPORT,path,'原始记录')+'。\n'
    if n and n.get('methods') is not None:report+=f"\n当前源码：{n['methods']} 项、{n.get('seconds',0):.3f} 秒、{n.get('failures','?')} 失败/{n.get('errors','?')} 错误/{n.get('skipped','?')} 跳过；冻结输入 {len(n['frozen_before'])} 项。\n"
    if m and m.get('shaper_oracle'):
        q=m['shaper_oracle'];report+=f"\n真实 CLI：{len(m['calls'])} 次子进程调用，{len(m['checks'])} 项检查；{q['RGB_values']:,} 个选区 RGB 值最大绝对误差 {q['maximum_linear_absolute_error']:.12g}，预设上限 2e-6。完整 96,000 与选区 67,200 个立体声采样帧按字节核验；PNG16 按既有 1 码上限核验。\n"
    if k and k.get('cases'):
        cases=k['cases'];report+=f"\n4K：实际完成 {len(cases)} 个单帧案例，比较 {sum(c['compared_components'] for c in cases):,} 个 RGBA 分量；最大误差 {max(c['maximum_absolute_error'] for c in cases):.12g}。这不是连续 4K 动画、吞吐或总 RSS 验收。\n"
    report+='\n## 3. 原片、成片与来源\n\n'
    for name,label in [('original.mp4','原片'),('edited.mp4','正式成片'),('range.mp4','实际预览'),('comparison.gif','GIF'),('author-project.json','作者项目'),('rights-ledger.json','版权记录'),('LICENSE.txt','原创素材声明')]:report+='- '+link(REPORT,ASSETS+'/'+name,label)+'\n'
    report+='\n所有新 LUT、图像、合成音频均由当轮本地脚本原创生成，声明 CC0-1.0；未调用模型或线上推理。'+link(REPORT,'scripts/shaper_media_oracle.py','独立数学与表生成')+'、'+link(REPORT,'scripts/smoke_float_shaper_media.py','CLI 复现')+'、'+link(REPORT,'scripts/smoke_float_shaper_4k.py','4K 复现')+'。\n'
    report+='\n## 4. 失败保留与边界\n\n首轮实际 118 项、803.659 秒、2 失败、0 错误、0 跳过，331 输入前后相同。极值十进制超出解析范围，以及把采样式 Bezier 误作精确中点，均为当轮新用例设置错误；修正用例后先独立核验三项边界，再从头执行相关套件。运行时和像素误差阈值没有为修正用例而改变。原日志、执行源码与'+link(REPORT,REL+'/fixture-correction-r1/verification.json','修正说明')+'保留。\n\n'
    report+='注册库元数据仅为保守计数/范围信息；严格渲染准入仍由有界 CUBE 解析器完成。DOMAIN 与 Resolve INPUT_RANGE 混用、组合文件 DOMAIN、缺失/多余/非有限数据和预算超限明确拒绝。完整 4K 连续播放/自然质量/听审、HDR、ICC、逆 LUT、非均匀表、`.3dl/.csp/.dat` 和剪映等价均未验收。\n\n'
    report+='\n本轮旧 R2 完整回归与发布 owner 在套件启动前消失，尚未执行完整方法；保留'+link(REPORT,REL+'/execution-interruption-r1/verification.json','原状态与中断记录')+'。源码 118 和安装 118 的成功证据不变；新 owner 仍等待实际父版本发布后才执行完整回归。\n'
    report+='\n恢复 owner 首次仍引用旧父 owner 名称，因旧记录已封存而在启动套件前被拒绝；'+link(REPORT,REL+'/owner-reference-r1/verification.json','R3 原状态与引用修正')+'保留，实际方法数为零。产品源码及已通过的源码/安装收据不变。\n'
    report+=link(REPORT,CONTRACT,'完整契约与一手格式来源')+'；'+link(REPORT,REL+'/source-reference-r2/verification.json','固定 tag/blob SHA、文件哈希与许可证')+'。上游 C/C++ 为参考快照，没有复制进入运行时。\n'
    output[REPORT]=report
    output[CONTRACT]=(ROOT/CONTRACT).read_text(encoding='utf8')
    for name,text in output.items():
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf8',newline='\n')
    return output

def check_links(files,destination):
    checked=0;missing=[]
    for name,text in files.items():
        for raw in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',text):
            raw=raw.split(' "',1)[0].strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',raw) or raw.startswith('#'):continue
            raw=urllib.parse.unquote(raw.split('#',1)[0]);relative=Path(os.path.normpath(str(Path(name).parent/raw)))
            if not any((base/relative).exists() for base in (destination,ROOT,MAIN)):missing.append((name,raw))
            checked+=1
    assert not missing,missing[:20]
    return checked
