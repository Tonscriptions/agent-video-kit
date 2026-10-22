"""Project actual host evidence into numbered README/docs without main writes."""
from datetime import datetime,timezone
import argparse,json,re,shutil
from pathlib import Path
from urllib.parse import unquote
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1];MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/float-timeline-20261022-lab';ASSETS='docs/assets/float-timeline-20261022-lab'
REPORT='docs/validation/作者时钟浮点帧宿主与真实媒体独立实测_2026-10-22.md'
CONTRACT='docs/specs/作者时钟浮点帧宿主与缓存源边界_v0.1_2026-10-22.md'
MARKER='V93-AUTHOR-CLOCK-FLOAT-HOST'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')

def read(p):return json.loads(p.read_bytes())
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def write(p,t):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t.rstrip()+'\n',encoding='utf8',newline='\n')
def relative_links(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda m:m[1]+prefix+'docs/',text)
def local_links(destination,paths):
    rows=[]
    for name in paths:
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',(destination/name).read_text('utf8')):
            if value.startswith(('https:','http:','app:','codex:','#')):continue
            relative=(destination/name).parent/unquote(value.split('#',1)[0].strip('<>'));relative=relative.resolve().relative_to(destination)
            found=next((p for p in (destination/relative,ROOT/relative,MAIN/relative) if p.exists()),None);assert found is not None,(name,value)
            rows.append({'document':name,'target':relative.as_posix(),'checked_at':str(found)})
    return rows

def installed_gate():
    installed=read(ROOT/REL/'installed-r1/verification.json');current=frozen()
    assert installed['status']=='passed-fresh-eight-wheel-174-resources-real-media-and-163-methods' and installed['frozen_before']==installed['frozen_after']==current and len(current)==288
    assert installed['isolated_methods']['methods']==163 and installed['isolated_methods']['skipped']==0 and len(installed['resource_hashes'])==174
    return installed

def finalize_install():
    installed=installed_gate();p=ROOT/REPORT;text=p.read_text('utf8');line=next(v for v in text.splitlines() if v.startswith('新鲜隔离安装正在独立执行'))
    replacement=f'''新鲜隔离安装现已实际通过：**163 方法 /{installed['isolated_methods']['suite_seconds']:.3f} 秒 /0 跳过**，174 份 source/wheel/site 资源、931 份 NumPy 原始文件与许可字节一致，216 个实际测试运行模块均来自新安装目录。[安装终态](evidence/float-timeline-20261022-lab/installed-r1/verification.json)。另在 `-I -S` 进程中重做 20 帧真实媒体、14 次原生工具调用，Float32 输出与开发版逐字节相同，145 个媒体运行模块均来自安装目录；新增公开宿主 CLI 调用数为 0，仅另有 3 次既有发现 CLI。[安装版媒体](evidence/float-timeline-20261022-lab/media-installed-r1/verification.json)。

下一轮完整回归的拥有进程已启动并串行等待 V92 发布，`suite_launched=false`，**不能登记为完整 2,280 项通过**。默认 `render/preview`、音频、队列、缓存及统一精度策略仍待连接此宿主，完整对标未完成。'''
    write(p,text.replace(line,replacement,1))
    save(ROOT/REL/'finalize-install-r1.json',{'status':'passed-actual-install-document-projection','at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(Path(__file__)),
        'installed_receipt_sha256':sha(ROOT/REL/'installed-r1/verification.json'),'methods':163,'resources':174,'frozen_inputs':frozen(),'documents':{REPORT:sha(p),CONTRACT:sha(ROOT/CONTRACT)},'full_passed':False,'main_changed':False})

def documents(destination,full=None):
    destination=Path(destination).resolve();assert destination==MAIN or destination.is_relative_to(ROOT/'product/.runtime')
    installed=installed_gate()
    if full is None:
        assert destination!=MAIN;status='待发布文档预览：2,280 项完整回归尚未取得完整通过结果。'
    else:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2280 and full['skipped']==0 and full['frozen_before']==full['frozen_after']==frozen()
        status=f"完整原生回归 **2280方法 /{full['suite_seconds']:.3f}秒 /0跳过**；288产品输入和8外部夹具保持相同。"
    large=f'''### V93 作者时钟 Float32 帧宿主与只读缓存源

{status} 新增库层 CPU 合成、作者时钟求值和本地帧包读取。默认 `render/preview`、音频、缓存和全部效果仍待迁移；当前不是剪映全功能等价结果。

| 编号 | 功能性核验 | 实际执行与边界 | 证据 |
|---|---|---|---|
| V93-01 | CPU 合成 | 32 模式、独立 alpha、Float64 分块计算与 Float32 表面；33 次实际 FFmpeg 交叉核验，65,536 灰阶、隐藏 RGB、Decimal、取消/预算检查 | [14项原始核验]({REL}/composite-r1.json) |
| V93-02 | 作者时间线 | VFR、超 2⁵³ PTS、有理数常速、倒放左右极限、冻结、窗口、曲线闭式积分、动画、源局部蒙版、嵌套透明组；当前库层 46 项/0 跳过 | [46项]({REL}/host-r3.json) · [边界]({CONTRACT}) |
| V93-03 | 缓存源 | 只读 mmap 及独立帧副本，配方/原片 SHA、原始帧号、显式容器起点，open/正常 close 复核，自有句柄关闭；部分包覆盖不能证明整片 EOF | [源与宿主报告]({REPORT}) |
| V93-04 | 失败留证 | 首轮 39 项中 1 项参考公式遗漏 Float32 输入舍入；修正参考式后 39 项通过。真实媒体首轮被 schema 拒绝缺 interpolation，补齐样例后通过 | [参考失败]({REL}/host-r1.json) · [schema失败]({REL}/media-r1/verification.json) |
| V93-05 | 真实原片与完整像素 | 两段原创 16 位视频，经原始时钟选帧、倒放/冻结、旋转/位移/圆形蒙版/opacity，全部 20 帧 RGBA 与独立参考相同，最大差 0 | [56项检查/14原生调用]({REL}/media-r2/verification.json) |
| V93-06 | 真实电影/GIF | 原始组合与编辑结果各 20帧/10FPS/2秒；无损 RGB16 每个通道字节相同，MP4/GIF 全部 PTS 和 100ms duration 核验；电影由独立脚本编码 | [原始前景]({ASSETS}/media-r2/inputs/foreground-16bit.mkv) · [原始背景]({ASSETS}/media-r2/inputs/background-16bit.mkv) · [original MP4]({ASSETS}/media-r2/original.mp4) · [timeline MP4]({ASSETS}/media-r2/timeline.mp4) |
| V93-07 | 目检范围 | 实际查看两段 MP4 各第 0/9/19 帧，共 6 张；未连续播放、未听审，未验收自然素材或 HDR | [查看收据]({REL}/media-r2/visual-reviewed.json) |
| V93-08 | 独立安装 | 新 8 轮安装，163项/{installed['isolated_methods']['suite_seconds']:.3f}秒/0跳过；174 资源、931 NumPy 文件一致；216 测试模块来源核验 | [安装终态]({REL}/installed-r1/verification.json) |
| V93-09 | 安装版真实媒体 | `-I -S` 重做 20 帧和 14 原生调用；145 模块来自新安装目录，Float32 输出与开发版逐字节一致。宿主新增公开 CLI 仍为 0 | [实际安装版媒体]({REL}/media-installed-r1/verification.json) |
| V93-10 | 剩余产品化 | 统一精度策略、流式视频编码/原生音频、render/preview/cache/队列/版权门禁、全部效果/转场/字幕/跟踪、ICC/PQ/HLG/HDR、抗混叠和自然素材质量仍待完成 | [契约 FTH-17/18]({CONTRACT}) |

原始组合：

![原始组合，实际 MP4 转 GIF]({ASSETS}/media-r2/original.gif)

作者编辑：

![倒放冻结和作者变换，实际 MP4 转 GIF]({ASSETS}/media-r2/timeline.gif)
'''
    small=f'''V93 新增作者时钟 Float32 帧宿主和只读帧包源。{status}

| 编号 | 已实际执行 | 产品边界 |
|---|---|---|
| FTH-01 | CPU/作者时钟/缓存源 46 项专项；33 次实际 FFmpeg 交叉核验 | 库层，未连接默认渲染、音频、预览与缓存 |
| FTH-02 | 原创 16 位媒体 20 帧，全部像素与独立参考相同；原始/编辑 MP4/GIF 与 16 位无损核验 | SDR 演示，未连续播放/听审、未验收自然素材或 HDR |
| FTH-03 | 新安装 163 项/0跳过，174资源、931 NumPy文件、216模块来源；安装媒体 Float32 与开发版相同 | 全部效果、统一精度策略与完整剪映对标继续实施 |

[规格]({CONTRACT}) · [实际核验/原视频/GIF/失败]({REPORT}) · [安装]({REL}/installed-r1/verification.json)。'''
    originals={}
    for name in LATEST_DOCS:
        p=destination/name;source=MAIN/name;originals[name]=sha(source);text=source.read_text('utf8')
        fragment='<!-- '+MARKER+' -->\n'+relative_links(large if name=='README.md' else small,name)+'\n<!-- /'+MARKER+' -->'
        pattern=re.escape('<!-- '+MARKER+' -->')+'.*?'+re.escape('<!-- /'+MARKER+' -->')
        if re.search(pattern,text,re.S):text=re.sub(pattern,lambda m:fragment,text,flags=re.S)
        else:first,rest=text.split('\n',1);text=first+'\n\n'+fragment+'\n'+rest
        write(p,text)
    if destination!=MAIN:assert all(sha(MAIN/n)==v for n,v in originals.items()),'Base docs changed during preview'
    return originals

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',type=Path,required=True);parser.add_argument('--revision',required=True);args=parser.parse_args();preview=args.preview.resolve()
    assert re.fullmatch(r'r[1-9][0-9]*',args.revision)
    assert preview.is_relative_to(ROOT/'product/.runtime') and not preview.exists();preview.mkdir(parents=True)
    before=frozen()
    if not (ROOT/REL/'finalize-install-r1.json').exists():finalize_install()
    else:installed_gate()
    base=documents(preview)
    names=[*LATEST_DOCS,REPORT,CONTRACT]
    for name in (REPORT,CONTRACT):p=preview/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    links=local_links(preview,names);assert before==frozen()
    output=ROOT/REL/('readme-preview-'+args.revision+'.json');assert not output.exists()
    save(output,{'status':'passed-unpublished-numbered-README-and-nine-document-preview','at_utc':datetime.now(timezone.utc).isoformat(),
        'preview':str(preview),'script_sha256':sha(Path(__file__)),'base_document_hashes':base,'documents':{n:sha(preview/n) for n in names},
        'local_links_checked':len(links),'frozen_inputs_unchanged':True,'main_changed':False,'full_passed':False,'published':False})
    print(json.dumps({'status':'passed-unpublished-README-preview','documents':len(names),'local_links':len(links),'main_changed':False}))

if __name__=='__main__':main()
