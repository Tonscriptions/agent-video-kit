"""Build reviewable numbered README and current docs from actual receipts."""
from datetime import datetime,timezone
import argparse,json,re
from pathlib import Path
from urllib.parse import unquote
from run_frozen_regression import frozen,sha
ROOT=Path(__file__).resolve().parents[1];MAIN=ROOT.parents[2]
REL='docs/validation/evidence/float-stream-20261022-lab';ASSETS='docs/assets/float-stream-20261022-lab'
CONTRACT='docs/specs/浮点视频有界编码与作者音频接入_实验_v0.1_2026-10-22.md'
REPORT='docs/validation/浮点视频流与作者音轨合成独立实测_2026-10-22.md';MARKER='V94-BOUNDED-FLOAT-VIDEO-AUDIO'
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
    'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md')

def read(path):return json.loads(path.read_bytes())
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text.rstrip()+'\n',encoding='utf8',newline='\n')
def save(path,value):write(path,json.dumps(value,ensure_ascii=False,indent=2))
def relink(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda match:match[1]+prefix+'docs/',text)

def current_evidence():
    current=frozen();audio=read(ROOT/REL/'audio-r3.json');stream=read(ROOT/REL/'stream-r2.json');media=read(ROOT/REL/'media-r4/verification.json')
    assert len(current)==292 and stream['status']=='passed-native-FFV1-stereo-and-owned-pipe-lifecycle' and stream['frozen_before']==stream['frozen_after']==current
    assert audio['status']=='passed-common-native-audio-adapter-only' and audio['result']['methods']==10 and audio['result']['skipped']==0
    for name in ('product/src/ai_ad_editor/float_audio_graph.py','product/tests/test_float_audio_graph.py'):
        assert audio['frozen_before'][name]==audio['frozen_after'][name]==current[name]
    assert stream['result']['methods']==9 and stream['result']['skipped']==0
    assert media['status']=='passed-real-bounded-FFV1-and-independent-authored-PCM' and media['frozen_before']==media['frozen_after']==current
    assert media['actual_native_launches']==20 and media['actual_encoder_processes']==2 and len(media['assets'])==20
    for name,row in media['assets'].items():assert sha(ROOT/name)==row['sha256'] and (ROOT/name).stat().st_size==row['bytes']
    path=ROOT/REL/'installed-r1/verification.json';installed=read(path) if path.exists() else None
    if installed is not None and installed['status'].startswith('passed'):
        assert installed['frozen_before']==installed['frozen_after']==current and installed['isolated_methods']['methods']==182 and installed['isolated_methods']['skipped']==0 and len(installed['resource_hashes'])==176
    return audio,stream,media,installed

def report():
    audio,stream,media,installed=current_evidence();status=installed['status'] if installed is not None else 'not-started'
    installed_line=(f"全新隔离安装 **182方法 /{installed['isolated_methods']['suite_seconds']:.3f}秒 /0跳过**，176资源与source/wheel/site相同，931份NumPy文件及许可相同。"
        if status.startswith('passed') else f'隔离安装当前状态：`{status}`；尚不能登记182方法通过。')
    body=f'''# 浮点视频流与作者音轨合成独立实测

新增 `float_audio_graph` 与 `float_stream` 独立库层，实际将 Float32 作者视频和原有音频时钟合成16位FFV1/Float32 PCM MKV。**默认render、preview、queue、缓存及全部作者效果尚未迁移；完整剪映等价未完成。** 本轮没有新增OpenFilm原码、模型前向或公开CLI命令。

| 编号 | 实际核验 | 结果与限制 |
|---|---|---|
| V94-01 | 现有音频适配器 | 10方法 /{audio['result']['seconds']:.6f}秒 /0失败错误跳过；19次测试脚本FFmpeg调用。覆盖裁切/空音轨、逐采样倒放/冻结、嵌套窗口/冻结/父组音量及volume/pan合法别名 |
| V94-02 | 有界编码与事务 | 9方法 /{stream['result']['seconds']:.6f}秒 /0失败错误跳过；9条脚本原生命令与5个成功编码收据分别记录。实际阻塞stdin子进程的取消/超时、源变更和已有输出保护通过 |
| V94-03 | 全码值及透明度 | 实际FFV1回读全部65,536级码值；独立alpha及零透明隐藏RGB规范化通过。量化仅在显式16位整数交付边界；不据此宣称HDR |
| V94-04 | 作者音视频末尾 | 1秒倒放/冻结成片全部PCM一致；112501/90000秒作者长度得到13帧/1.3秒视频和60001音频采样，两个终点单独保留 |
| V94-05 | 原片与剪辑实片 | 两组各20帧/10FPS/2秒，全部16位分量与原有已独立核验参考一致；每组96000立体声采样帧逐字节一致。2个实际管道编码、16条脚本原生命令；Python审计共20次原生工具启动，包含内部音频时钟探测 |
| V94-06 | 媒体与裁剪 | 当前开发样例20资产/19检查；两次编码RGB裁剪分量均0。含原始视频/PCM、原片与剪辑MKV、含AAC的MP4、实际MP4解码GIF和帧/PCM联系图；MP4/AAC和GIF不是无损证据 |
| V94-07 | 新鲜离线安装 | {installed_line} [独立安装收据](evidence/float-stream-20261022-lab/installed-r1/verification.json) |
| V94-08 | 真实完整回归 | 仅完成实际发现2299方法，执行数0；不能把10、9、182或父版历史通过数累计为本轮完整通过。后续须绑定实际发布的V93父版再串行执行 |
| V94-09 | 保留失败 | audio-r1为1FAIL/1ERROR：错误volume_db夹具和真实嵌套空画面编译缺口；stream-r1为1FAIL/5ERROR：误用gbr编码器枚举。媒体r1漏算半透明原片source-over；r2/r3暴露Windows审计executable=None且command为字符串，当前r4已覆盖20次启动 |
| V94-10 | 尚未验收 | 文件型stretch Job、源转场、默认CLI接入、全部效果及预览/队列/缓存；自然广告、连续播放、声音试听、HDR/ICC/PQ/HLG、4K长片与峰值RSS、完整剪映功能效果等价 |

专项收据：[音频](evidence/float-stream-20261022-lab/audio-r3.json)、[编码](evidence/float-stream-20261022-lab/stream-r2.json)、[媒体](evidence/float-stream-20261022-lab/media-r4/verification.json)、[发现而非执行](evidence/float-stream-20261022-lab/discovery-r1.json)。[实验契约](../specs/浮点视频有界编码与作者音频接入_实验_v0.1_2026-10-22.md)。

[原始RGB16视频](../assets/float-stream-20261022-lab/media-r4/inputs/foreground-16bit.mkv) · [原始PCM](../assets/float-stream-20261022-lab/media-r4/original-audio.wav) · [原片MKV](../assets/float-stream-20261022-lab/media-r4/original-16bit.mkv) · [原片MP4](../assets/float-stream-20261022-lab/media-r4/original.mp4) · [剪辑MKV](../assets/float-stream-20261022-lab/media-r4/timeline-16bit.mkv) · [剪辑MP4](../assets/float-stream-20261022-lab/media-r4/timeline.mp4)。来源与原创CC0说明见[origin](../assets/float-stream-20261022-lab/media-r4/origin-and-rights.json)。

![原片实际MP4解码GIF](../assets/float-stream-20261022-lab/media-r4/original.gif)

![剪辑实际MP4解码GIF](../assets/float-stream-20261022-lab/media-r4/timeline.gif)

![实际帧与PCM诊断](../assets/float-stream-20261022-lab/media-r4/actual-frames-and-PCM.png)

只目检实际MP4的0、9、19帧与对应PCM诊断图；未连续播放，未试听。新素材为程序生成技术样例，不代表自然素材的广告美学或AI特效质量。剪辑参考是此前固定SHA的独立验收结果，本轮没有新写第二套时间线对照实现。

复现使用原生Windows命令，所有路径均在E盘；没有Docker/WSL、虚拟环境、在线依赖下载或交互浏览器tab：

```powershell
C:/Python313/python.exe -E -B -X utf8 scripts/run_float_audio_tests.py --revision <新编号> --expected-inputs 292
C:/Python313/python.exe -E -B -X utf8 scripts/run_float_stream_tests.py --revision <新编号>
C:/Python313/python.exe -E -B -X utf8 scripts/smoke_float_stream_media.py --revision <新编号> --source-root <包含V93固定样例的仓库根>
C:/Python313/python.exe -E -B -X utf8 scripts/verify_float_stream_install.py
```

安装脚本保留独占的`installed-r1`目录；重复整套安装须另立证据目录，不能覆盖当前原收据。安装版媒体在`-I -S`重新编码并比较全部无损像素及PCM摘要，不能复用开发版输出冒充安装执行。
'''
    write(ROOT/REPORT,body)

def documents(destination,full=None):
    destination=Path(destination).resolve();assert destination==MAIN or destination.is_relative_to(ROOT/'product/.runtime')
    audio,stream,media,installed=current_evidence();report()
    if full is None:
        assert destination!=MAIN;status='实验候选文档预览：完整2299方法尚未执行通过，尚未发布。'
    else:
        assert full['terminal_ok'] and full['methods']==2299 and full['skipped']==0 and full['frozen_before']==full['frozen_after']==frozen()
        assert installed is not None and installed['status'].startswith('passed')
        status=f"实际完整原生回归 **2299方法 /{full['suite_seconds']:.3f}秒 /0跳过**，292产品输入和8外部夹具不变。"
    install_status=(f"182方法 /{installed['isolated_methods']['suite_seconds']:.3f}秒 /0跳过；176资源、931份NumPy文件/许可一致" if installed is not None and installed['status'].startswith('passed') else '全新离线安装正在执行；不登记182方法通过')
    section=f'''### V94 有界浮点视频与作者音轨合成

{status} 当前为独立库层；默认render/preview/queue/cache、全部效果及完整剪映等价仍待完成。

| 编号 | 功能性核验 | 实际结果与边界 | 证据 |
|---|---|---|---|
| V94-01 | 音频适配 | 10方法通过；沿用原生音频时钟；嵌套窗口/冻结/父组音量、倒放、裁切及合法volume/pan别名逐样本检查 | [音频收据]({REL}/audio-r3.json) |
| V94-02 | 编码管道 | 9方法通过；4×64KiB独立分块、2帧输入队列、stderr有界；实际阻塞写入的取消和超时回收、输入变化、原子输出保护 | [编码收据]({REL}/stream-r2.json) |
| V94-03 | 精度及作者末尾 | 65536级码值及独立alpha无损回读；分数作者末尾13帧与60001音频采样分开保留 | [契约]({CONTRACT}) |
| V94-04 | 原片/剪辑实际成片 | 两组各20帧及96000立体声样本帧全部核验；20原生工具启动，2个真实管道编码，RGB裁剪分量均0；20资产/19检查 | [媒体与SHA]({REL}/media-r4/verification.json) |
| V94-05 | 新鲜离线交付 | {install_status}；安装版媒体独立重做，公开新增CLI为0 | [安装收据]({REL}/installed-r1/verification.json) |
| V94-06 | 失败与未验收 | 原字段夹具、嵌套空画面、编码器枚举与Windows审计失败保留；未连续播放/听审，未验收自然广告、HDR、长片RSS和完整剪映效果 | [完整报告]({REPORT}) |

[原片MKV]({ASSETS}/media-r4/original-16bit.mkv) · [原片MP4]({ASSETS}/media-r4/original.mp4) · [原始PCM]({ASSETS}/media-r4/original-audio.wav) · [剪辑MKV]({ASSETS}/media-r4/timeline-16bit.mkv) · [剪辑MP4]({ASSETS}/media-r4/timeline.mp4)

![原片实际GIF]({ASSETS}/media-r4/original.gif)

![剪辑实际GIF]({ASSETS}/media-r4/timeline.gif)
'''
    paths=[]
    for name in LATEST_DOCS:
        existing=(MAIN/name).read_text('utf8');assert f'<!-- {MARKER} -->' not in existing
        block=section if name=='README.md' else f'''### V94 浮点编码独立库层进度

{status} 10音频方法与9编码方法分别通过，真实两组20帧/96000立体声采样帧核验完成。{install_status}。默认CLI、preview/queue/cache、全部效果及完整剪映等价仍待验收。

[实测/失败/媒体]({REPORT}) · [实验契约]({CONTRACT}) · [媒体收据]({REL}/media-r4/verification.json)
'''
        head,separator,rest=existing.partition('\n');write(destination/name,head+'\n\n'+relink(f'<!-- {MARKER} -->\n'+block+f'\n<!-- /{MARKER} -->',name)+'\n\n'+rest.lstrip());paths.append(name)
    for name in (REPORT,CONTRACT):write(destination/name,(ROOT/name).read_text('utf8'));paths.append(name)
    return paths

def local_links(destination,paths):
    rows=[]
    for name in paths:
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',(destination/name).read_text('utf8')):
            if value.startswith(('https:','http:','app:','codex:','#')):continue
            relative=((destination/name).parent/unquote(value.split('#',1)[0].strip('<>'))).resolve().relative_to(destination)
            actual=next((p for p in (destination/relative,ROOT/relative,MAIN/relative) if p.exists()),None);assert actual is not None,(name,value)
            rows.append({'document':name,'target':relative.as_posix(),'checked_at':str(actual)})
    return rows

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview',type=Path,required=True);parser.add_argument('--revision',required=True);args=parser.parse_args()
    assert args.preview.resolve()!=MAIN and not args.preview.exists();paths=documents(args.preview);links=local_links(args.preview,paths)
    save(ROOT/REL/('readme-preview-'+args.revision+'.json'),{'status':'passed-unpublished-nine-document-and-numbered-README-preview','at_utc':datetime.now(timezone.utc).isoformat(),
        'generator_sha256':sha(Path(__file__)),'preview':str(args.preview.resolve()),'main_changed':False,'published':False,
        'documents':{name:sha(args.preview/name) for name in paths},'verified_local_links':len(links),'links':links,'frozen_inputs':frozen()})
    print(json.dumps({'status':'passed-unpublished-preview','documents':len(paths),'verified_links':len(links),'main_changed':False}),flush=True)

if __name__=='__main__':main()
