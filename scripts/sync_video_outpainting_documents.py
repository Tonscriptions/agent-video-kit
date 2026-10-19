"""Publish V66 documentation only from terminal model, test and install receipts."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from run_frozen_regression import frozen
from audit_video_outpainting_release import BASE, REPORT, CONTRACT, NATIVE_CONTRACT, ROOT


def read(p):return json.loads(p.read_bytes())
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def insert(path,marker,content):
    text=path.read_text(encoding='utf8');start='<!-- '+marker+' -->';end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1);text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    current=frozen();full=read(BASE/'full-r2.json');subset=read(BASE/'subset-r2.json');reader=read(BASE/'vace-reader-r1.json')
    media=[read(BASE/folder/'verification.json') for folder in ('lama-direct-r3','lama-harmonic-r2','vace-harmonic-r4','installed-r2/media')]
    installed=read(BASE/'installed-r2/verification.json');skills=read(BASE/'skills-r2.json')
    for v in (full,subset,reader,*media,installed):assert v['frozen_equal'] and v['frozen_before']==v['frozen_after']==current
    assert len(current)==200 and full['terminal_ok'] and full['methods']==1462 and full['skipped']==0 and full['exit_code']==0
    assert subset['terminal_ok'] and subset['methods']==24 and subset['skipped']==0 and subset['exit_code']==0
    assert reader['terminal_ok'] and reader['methods']==41 and reader['skipped']==0 and reader['exit_code']==0
    assert all(v['status']=='passed_execution_quality_separate' and all(c['passed'] for c in v['checks']) for v in media)
    assert installed['status']=='passed' and installed['packaged_files']==133 and all(c['equal'] for c in installed['comparisons'])
    assert skills['skill_count']==17 and skills['local_links_checked']==238
    development_cli=sum(v['cli_calls'] for v in media[:3]);frames=sum(v['frames'] for v in media[:3])
    quality='；'.join(f"{v['engine']}/{v['blend']} {v['quality']['psnr_db']:.3f} dB（{'通过' if v['quality']['passed'] else '未通过'}）" for v in media[:3])
    summary=(f'2026-10-20 **V66（产品，10-19 开始的跨日验收）**：新增 `media outpaint`，本地 LaMa/VACE 向更大画布生成背景；显式放置、同源蒙版、'
        f'归一化原区域 RGBA/PTS/PCM 保护、可编辑配方、工程包与片段组跨项目重绑定。完整 **1462/1462、{full["suite_seconds"]:.3f} 秒、'
        f'0 跳过、200 输入冻结**；24 扩图专项、41 VACE 专项均为子集，后者含 8 个新增读取方法。开发 **{development_cli} CLI/3 次模型交付/{frames} 帧**；'
        f'原生离线 **133 包内文件/{installed["isolated_cli_calls"]} 隔离 CLI**，LaMa harmonic 的全部 RGBA/PCM 与开发版相同；'
        f'**17 Skills/238 引用**。生成区预先声明 ≥30 dB，实测 {quality}。'
        f'原画面保护通过不替代生成质量；**自然扩图、安装版 VACE 推理与完整剪映等价仍未验收**。')
    summary+=' VACE 两次原生文本加载访问冲突保留；组件内 `pread` 后本例实际交付通过，**底层根因与长期稳定性仍未确认**。'
    vace_quality=media[2]['quality']
    vace_gate='通过' if vace_quality['passed'] else '未通过'
    report=ROOT/'docs/validation'/REPORT
    asset_names=['video-outpainting-20261019-v66-'+x for x in ('lama-direct-r3','lama-harmonic-r2','vace-harmonic-r4','installed-r2/media')]
    rows=[]
    for i,v in enumerate(media):
        elapsed=next(c['seconds'] for c in v['calls'] if c['name']=='outpaint')
        folder=('lama-direct-r3','lama-harmonic-r2','vace-harmonic-r4','installed-r2/media')[i]
        worker_seconds=read(BASE/folder/'actual-result.json')['outpainting']['worker']['elapsed_seconds']
        rows.append(f'| OUT-Q{i+1:02} | {"安装" if v["installed"] else "开发"} {v["engine"]}/{v["blend"]} | '
            f'{v["frames"]} 帧 / {v["model_calls"]} 次模型调用 | {elapsed:.3f} / {worker_seconds:.3f} 秒 | {v["quality"]["psnr_db"]:.6f} dB / '
            f'{v["quality"]["consecutive_error_delta_mae"]:.6f} | {"通过该单项" if v["quality"]["passed"] else "未通过该单项"} |')
    legacy=read(ROOT/'docs/validation/evidence/vace-delivery-20261019-v66-r1/verification.json')
    legacy_text=('旧接口受控 VACE 复测尚未形成通过的交付收据，仍保留原拒绝/失败，不能以扩图结果冒充原场景通过。')
    if legacy['status'].startswith('passed_'):
        legacy_text=(f'合入扩图之前，用封存的 **198 份 V65 输入**复测同一旧修复场景，原片/选区摘要未变；'
            f'30 步、5 帧窗口、2 帧重叠和 direct 保持不变。交付 8 帧@8 fps；原 Alpha、区外 RGBA、每帧 PTS 和 '
            f'48,000 个单声道采样帧独立核对。受控 PSNR **{legacy["controlled_reconstruction"]["masked_psnr_after_db"]:.6f} dB**，'
            f'≥30 dB 单项 **{"通过" if legacy["controlled_psnr_at_least_30"] else "未通过"}。'
            f'[旧接口实测/源码封存](VACE物理显卡准入与真实交付实测_2026-10-19.md)；该 8 帧与当前 24 帧扩图分计，不证明新接口或自然质量。')
    text=f'''# 本地视频扩图与原画面保护实测

{summary}

## 生成区质量，单独评分

以下为同一原创受控棚拍图样：蓝灰墙面、桌面、移动色块、帧标识、半透明区域和立体声正弦。原片 192×128，新画布 256×160，8 帧@8 fps/1 秒。LaMa 居中放置，VACE 的放置见实际配方；生成区每帧 16,384 像素。隐藏真值只给独立评分器，未传入模型。阈值在执行前写入契约，未因结果改变。模型调用次数与 CLI 次数分别统计，失败质量不改写成通过。

| 编号 | 实际执行 | 数量 | 正式 outpaint CLI / worker 耗时 | 生成区 PSNR / 相邻误差变化 MAE | 预先声明 ≥30 dB |
|---|---|---|---|---|---|
{chr(10).join(rows)}

相邻误差变化 MAE 是本受控场景的描述指标，未另设自然时序通过门槛。LaMa 逐帧生成，VACE 联合窗口生成；harmonic 只修正空间色差。结构、纹理、画外对象、接缝、自然运动和真实隐藏背景仍需独立审查，单例 PSNR 不关闭 #56/#95 的广泛画质差距。

VACE 使用靠左放置，LaMa 使用居中放置，生成区域对应的世界坐标与外推距离不同。本表核对各案例自己的门槛，不能据此作模型质量排名。

本次 VACE 生成区为 **{vace_quality['psnr_db']:.6f} dB，{vace_gate}预声明的 30 dB**。[静帧观察](evidence/video-outpainting-20261019-v66/static-review.json)记录了右侧桌面边界斜切，以及第 4/7 帧底部暗色横带；执行与原区域保护通过，不关闭这些可见的生成缺陷。

表内耗时直接读取原调用和 worker 收据：正式 CLI 包含登记后的完整性检查、加载、推理与编码，worker 为其子范围；模型登记本身另计，不能把两个时间相加。VACE 权重约 19.04 GB（17 个文件），冷校验和本机当时的磁盘/并发负载会影响耗时；本表不是纯推理测速，也不证明交互延迟或长片性能达标。

## 编号功能核验

| 编号 | 本轮实际内容 | 结果与边界 |
|---|---|---|
| OUT-F01 | 大画布、整数放置、居中/靠边、单轴扩展、奇数尺寸 | 24 专项中的几何与真实 FFmpeg 协议检查；拒绝裁切、原尺寸、越界、非整数及像素超预算 |
| OUT-F02 | 旋转 90°、SAR 2:1、显式 max-edge 叠加 | 原生源归一化后逐样本比较；保护的是归一化 SDR 8-bit CFR，不是任意原生高精度格式 |
| OUT-F03 | 同一个解码流生成外部蒙版 | 不读取外部蒙版或隐藏真值；原矩形内部 0、外部 255，帧数与 PTS 同源 |
| OUT-F04 | 完整原区域 RGBA 与生成区 Alpha | 四次开发/安装实测均逐帧比对，包括原半透明区；新区域为不透明；QTRLE 全输出回读摘要核验 |
| OUT-F05 | 原声、选区与时钟 | 真实案例每例 48,000 立体声采样帧精确保留；专项另覆盖非零源范围和禁用音频；GIF/有损 MP4 仅为预览 |
| OUT-F06 | dry-run、预取消、坏响应、改几何/摘要、GPU 拒绝、缺少实现 | 专项无半成品登记；真实 LaMa dry-run/预取消通过；GPU/坏报告的可控协议测试不计为真实权重推理 |
| OUT-F07 | 配方语义 | 重算摘要仍不能掩盖错源、自引用、画幅、归一化尺寸、范围、帧率/帧数或未知字段；源/权利记录摘要不符拒绝 |
| OUT-F08 | 工程包往返 | 真实生成 MOV 字节与配方完整保留，导入工程验证通过；不复制模型/Python |
| OUT-F09 | 片段组跨项目复用 | 自动收集源依赖，验证旧配方后重绑新源 ID/摘要，目标语义校验、输出字节和权利拒绝通过 |
| OUT-F10 | 原生离线安装 | 7 wheel、133 产品资源逐字节比对；隔离启动器真实 LaMa harmonic；所有 RGBA、PCM 和该质量分数与开发版相同 |
| OUT-F11 | 真模型与许可 | 本地 TorchScript LaMa/CPU、Wan-VACE/CUDA；网络关闭且事件为 0；模型商业许可未接受，rights check 继续返回 7 |
| OUT-F12 | 全量、专项和 Skills | 完整 1462 方法；24 扩图、41 VACE 为子集，后者含 8 个新读取方法；200 输入前后相同；17 个 video-cut- 联接及 238 本地引用通过 |
| OUT-F13 | 查看范围 | 查看四份接触表中第 0/3/4/7 帧，共 16 个静帧视图；没有连续播放或听审，不据此验收自然画音质量 |
| OUT-F14 | 原生 safetensors 读取 | 三组件/六文件实际 pread 记录、严格清单/计数和失败回滚；两次旧崩溃、200 份旧源码封存与改后同参数交付分开，未编辑共享依赖；不宣称长期稳定性或底层根因已确认 |

## 原片与实际生成

| 内容 | 实际文件 |
|---|---|
| 原创原片 | [源 MOV](../assets/{asset_names[0]}/source.mov) /[预览 MP4](../assets/{asset_names[0]}/source.mp4) |
| LaMa direct | [实际 MOV](../assets/{asset_names[0]}/expanded.mov) /[MP4](../assets/{asset_names[0]}/expanded.mp4) /[接触表](../assets/{asset_names[0]}/contact-sheet.png) |
| LaMa harmonic | [实际 MOV](../assets/{asset_names[1]}/expanded.mov) /[MP4](../assets/{asset_names[1]}/expanded.mp4) /[接触表](../assets/{asset_names[1]}/contact-sheet.png) |
| VACE harmonic | [实际 MOV](../assets/{asset_names[2]}/expanded.mov) /[MP4](../assets/{asset_names[2]}/expanded.mp4) /[接触表](../assets/{asset_names[2]}/contact-sheet.png) |
| 安装版 LaMa harmonic | [实际 MOV](../assets/{asset_names[3]}/expanded.mov) /[接触表](../assets/{asset_names[3]}/contact-sheet.png) |
| 编辑工程 | [LaMa 包](../assets/{asset_names[1]}/project.aevpkg.zip) /[VACE 包](../assets/{asset_names[2]}/project.aevpkg.zip)，模型和原生 Python 外置 |

![实际 LaMa harmonic 扩图](../assets/{asset_names[1]}/comparison.gif)

![实际 VACE harmonic 扩图](../assets/{asset_names[2]}/comparison.gif)

每份 GIF 都为实际结果的 8 帧/1,000 ms、无声；三列依次为未生成的灰色扩展输入、真实模型输出、受控隐藏真值。透明源区域只在预览中叠加棋盘；精确 RGBA 证据使用 MOV。真值列不能称为模型结果。

## 失败、历史范围与复现

最初独立草稿的 19 方法运行有两个夹具错误：导入参数误用 --project，以及 FFmpeg 不接受 -t .5；保留原错误与执行副本。修正后独立 21 方法通过，后续补配方语义、权利及片段组专项，最终 24 方法纳入当前完整回归；这些历史运行不叠加成当前测试数。真实模型生成区未通过的质量项同样保留原视频、真值和指标。

首轮真实 LaMa direct 已生成 8 帧并通过像素/音频保护，但片段组复制进来的旧模型证据包含历史网址，策略审计按规则返回 2；[原拒绝](evidence/video-outpainting-20261019-v66/lama-direct-r1/fragment-policy.stdout.log)和[该轮实际视频](../assets/video-outpainting-20261019-v66-lama-direct-r1/expanded.mp4)保留。首轮扩图 VACE 在登记散列阶段主动停止，0 模型前向，原因见[原生预检停止记录](evidence/video-outpainting-20261019-v66/vace-harmonic-r1/preflight-stop.json)。正式复测使用新工程和新本地证明：完整历史证据原字节保存在运行记录，便携证明只将检索网址换成其 SHA-256，并保留权重身份、全部许可字段与 unverified 状态；实际片段组 policy audit 返回 0，rights check 仍为 7。未修改策略、权重或原质量门槛。上述首轮不并入当前 24 开发帧。

第二轮 VACE 扩图在文本权重加载 71/242 项附近失败，尚无扩图前向/输出；[原失败](evidence/video-outpainting-20261019-v66/vace-harmonic-r2/verification.json)、[Windows 原始事件](evidence/video-outpainting-20261019-v66/vace-harmonic-r2/windows-native-crash-events.json)和[现场核对](evidence/video-outpainting-20261019-v66/vace-harmonic-r2/native-crash-analysis.json)保留。事件 1000/1001 将 PID 0x5E90 绑定到本次原生 worker，报告 torch_cpu.dll 的 0xc0000005 访问冲突。第三轮以同一源、权重、原生 Python、提示词、seed、30 步、5/2 窗口和融合参数重试，在 72/242 附近出现同模块/同偏移原生崩溃：PID 0x865C、报告 03b8b551-5e2b-4fc4-926d-a15540c97cdd；[原失败](evidence/video-outpainting-20261019-v66/vace-harmonic-r3/verification.json)、[Windows 事件](evidence/video-outpainting-20261019-v66/vace-harmonic-r3/windows-native-crash-events.json)和[现场核对](evidence/video-outpainting-20261019-v66/vace-harmonic-r3/native-crash-analysis.json)。两轮均只有源素材，无扩图输出/资产，临时管道已回收；不将其归类为 CUDA OOM，也不归因于扩图几何。这两轮 0 生成帧不并入正式交付数。

随后参考[上游相似报告](https://github.com/Comfy-Org/ComfyUI/issues/15424)、[官方后端 API](https://huggingface.co/docs/safetensors/api/torch)和[本机接口核对](evidence/video-outpainting-20261019-v66/vace-harmonic-r2/loading-candidate.json)，按[先行读取约束](../specs/{NATIVE_CONTRACT})仅在隔离 worker 的组件加载调用内选择原生 pread。两个模块的局部 reader 引用在调用后恢复；固定六权重清单、已有完整性散列/只读锁、精度、设备与所有采样参数保留，不改共享依赖，不读取整片 bytes 作为回退。实际记录验证三组件/六文件采用 pread，第四轮才有当前 8 帧正式交付。本轮仅证明该受控案例可执行；没有原生崩溃转储栈、重复压力和跨设备对照，底层根因与长期稳定性仍未确认，内存峰值改善也未独立测速。

读取修改前的 **1454/1454、5943.235 秒、200 份输入**完整回归与[逐字节源码封存](evidence/video-outpainting-20261019-v66/pre-pread-source/source-snapshot.json)保留；[源码 ZIP](evidence/video-outpainting-20261019-v66/pre-pread-source/source-snapshot.zip)包含当时全部测试与实现。之后只改三个已登记输入并新增 8 个读取方法，重新执行当前 1462 项、相关专项、真实模型和离线安装；旧 1454 项不与当前通过数相加。先前 LaMa direct/harmonic 与安装版的输出另有旧收据，当前新源码三例的全部 RGBA、PCM 和质量分数均与各自旧例一致。独立候选的 [8 个协议检查](evidence/video-outpainting-20261019-v66/reader-candidate-r1/verification-r1.json)不冒充真实权重读取。

独立 CPU 权重读取探针在首个结果文件出现前达到 300 秒预算，其自有子进程已回收；未运行到有效的两后端对照。[未完成收据](evidence/video-outpainting-20261019-v66/storage-prefix-r1/verification.json)和执行副本保留；0 个张量样本得到证实，该探针不计模型交付、推理或完整回归通过数，也不作为 pread 有效性证据。当前实际完整加载/前向由 OUT-F14 的正式 worker 收据另行证明。

{legacy_text}

- [先行契约](../specs/{CONTRACT}) /[全量冻结回归](evidence/video-outpainting-20261019-v66/full-r2.json) /[24 扩图专项](evidence/video-outpainting-20261019-v66/subset-r2.json) /[41 VACE 专项](evidence/video-outpainting-20261019-v66/vace-reader-r1.json)。
- [LaMa direct](evidence/video-outpainting-20261019-v66/lama-direct-r3/verification.json) /[LaMa harmonic](evidence/video-outpainting-20261019-v66/lama-harmonic-r2/verification.json) /[VACE harmonic](evidence/video-outpainting-20261019-v66/vace-harmonic-r4/verification.json)。
- [原生安装/逐文件比对](evidence/video-outpainting-20261019-v66/installed-r2/verification.json) /[安装版真实输出](evidence/video-outpainting-20261019-v66/installed-r2/media/verification.json) /[安装包](../assets/video-outpainting-20261019-v66-installed-r2/release/agent-video-kit-cp313-win_amd64.zip)。
- [静帧观察](evidence/video-outpainting-20261019-v66/static-review.json) /[Skills](evidence/video-outpainting-20261019-v66/skills-r2.json) /[发行绑定](evidence/video-outpainting-20261019-v66/release-r1.json)。
- [原始灰画布/蒙版几何核验和草稿失败](evidence/outpaint-geometry-20261019-v66-r1/verification.json)。
- [OpenFilm 诊断辅助模块的具体复用范围与下一轮待办](../OpenFilm诊断模块复用与原生模型故障后续项_2026-10-20.md)：静态研究，自动诊断尚未接入。

```powershell
ai-ad-editor media outpaint --project E:/your-project --asset-id source --adapter-id local_lama --derived-asset-id expanded --width 256 --height 160 --offset-x 32 --offset-y 16 --repair-blend harmonic --dry-run
# 用新目录重复真实模型核验；需要已登记证据、现有原生 Python 和权重，不创建虚拟环境、不下载。
C:/Python313/python.exe -B -X utf8 scripts/smoke_video_outpainting.py --work product/.runtime/<new-work> --evidence docs/validation/evidence/<new-evidence> --public docs/assets/<new-assets> --engine lama --blend harmonic --model-python D:/existing-native-python/python.exe
```

扩图几何、保护和配方是本项目新增，复用既有 LaMa/VACE、FFmpeg、事务、权利和工程包链路；没有把 OpenFilm 的在线 provider 当成本地生成模型。安装包不含 Python、FFmpeg、Torch、驱动或权重。其它设备/机器、长片、HDR、自然广告素材、生成区广泛画质、安装版 VACE 真推理、持续播放/听感和完整剪映功能/效果均未验收。
'''
    report.write_text(text,encoding='utf8',newline='\n')
    manifest_path=ROOT/'video-cut-install-manifest.json';manifest=read(manifest_path)
    old=manifest.get('current_audit');history=manifest.setdefault('audit_history',[])
    if old and old not in history:history.append(old)
    for entry in manifest['skills']:
        digest=sha(ROOT/'skills'/entry['name']/'SKILL.md').split(':',1)[1]
        if digest!=entry['skill_md_sha256']:
            entry.setdefault('skill_md_sha256_history',[]).append({'sha256':entry['skill_md_sha256'],
                'replaced_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'V66 local outpainting and independent generated-region quality'})
            entry['skill_md_sha256']=digest
    manifest['current_audit']={'record':(BASE/'skills-r2.json').relative_to(ROOT).as_posix(),
        'record_sha256':sha(BASE/'skills-r2.json'),'checked_at_utc':skills['checked_at_utc'],
        'skills':17,'local_links_checked':238,'semantics':'V66 local outpainting and component-scoped native pread; generated-region quality separate; no full CapCut parity'}
    save(manifest_path,manifest)
    insert(ROOT/'README.md','V66-CURRENT',summary+f' [原片/GIF/编号核验/失败/发行](docs/validation/{REPORT})。\n\n'
        f'![实际 LaMa harmonic 扩图](docs/assets/{asset_names[1]}/comparison.gif)\n\n'
        f'[原视频](docs/assets/{asset_names[1]}/source.mp4) /[实际 LaMa 输出](docs/assets/{asset_names[1]}/expanded.mp4)；图中真值为独立受控背景。\n\n'
        f'VACE 实际生成区 **{vace_quality["psnr_db"]:.3f} dB，{vace_gate} 30 dB 门槛**；保留桌面边界和底部暗带缺陷：\n\n'
        f'![实际 VACE 扩图与质量缺陷](docs/assets/{asset_names[2]}/comparison.gif)\n\n'
        f'[VACE 原视频](docs/assets/{asset_names[2]}/source.mp4) /[实际 VACE 输出](docs/assets/{asset_names[2]}/expanded.mp4)。\n\n'
        'OpenFilm 同步补查：字幕/HTML/模板规则、三套本地创作 Skill 和限定硬件编解码已有采用记录；'
        '下一优先候选为诊断辅助逻辑。上游日志 tail 先读完整文件，保留本项目已有的有界读取并补进程归因；'
        '本次诊断补查为静态研究，尚未接入，也不增加产品测试数。'
        '[当前采用/待办/成本边界](docs/OpenFilm当前复用决策_2026-10-18.md) /'
        '[两模块 SHA 与原生故障缺口](docs/OpenFilm诊断模块复用与原生模型故障后续项_2026-10-20.md)。')
    relatives=['docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    for relative in relatives:
        path=ROOT/relative;target=Path(os.path.relpath(report,path.parent)).as_posix()
        insert(path,'V66-CURRENT',summary+f' [原片/GIF/编号核验/失败和发行]({target})。')
    path=ROOT/'README.md';text=path.read_text(encoding='utf8')
    if '| V66 |' not in text:
        row=f'| V66 | 本地视频扩图、原画面保护与可编辑配方 | 1462/1462；{development_cli} CLI/24 开发帧；133 文件/{installed["isolated_cli_calls"]} 隔离 CLI；17 Skills；原生 pread 实际交付 | VACE 生成区 {vace_quality["psnr_db"]:.3f} dB，{vace_gate} 30 dB；两次原生崩溃/长期稳定性与自然质量仍开放 | [原片/GIF/质量/发行](docs/validation/{REPORT}) |\n'
        text=text.replace('| V65 |',row+'| V65 |',1)
    text=text.replace('**V65（产品）**','**V65（历史产品验收）**',1)
    lines=text.splitlines()
    current=[i for i,line in enumerate(lines) if line.startswith('- 当前模块进度见')]
    assert len(current)==1
    lines[current[0]]=(f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：V66 完整 1462/1462、'
        f'{full["suite_seconds"]:.3f} 秒、0 跳过、200 输入冻结；本地扩图与原画面保护、工程/片段组复用已实测。'
        f'生成区质量按独立门槛逐例报告；自然画音质量、CTC 精度、长片/HDR、其它机器、内容库规模和完整剪映等价继续开放。')
    text='\n'.join(lines)+'\n'
    path.write_text(text,encoding='utf8',newline='\n')
    progress=ROOT/'docs/构建进度总表_2026-10-16.md'
    rows={
        '| 15 | 离线模型接入 |': '| 15 | 离线模型接入 | 部分实现，本轮真实扩图交付完成 | V66 本地 LaMa/CPU、VACE/CUDA；物理显存分阶段准入、8 帧实际交付及原 RGBA/PTS/PCM 保护；旧 inpaint 同场景另以 198 源码封存核验 | 生成质量逐例评分；安装版 VACE、其它引擎/机器、长片和自然质量未验 |',
        '| 23 | 高级 AI 特效 |': '| 23 | 高级 AI 特效 | 部分实现 | RVM/SAM2 抠像和提示修正、LaMa/VACE 修复与 harmonic；V66 新增真正画外生成、整数放置、完整原区域保护及可编辑配方 | 修复残影/纹理、发丝/遮挡、姿态/美颜及广泛自然扩图质量仍开放；VACE 见 26 |',
        '| 24 | Agent Skills |': '| 24 | Agent Skills | 已实现，持续扩展 | V66 仍为 17 个 video-cut- Skill；补本地扩图、原画面保护和独立生成区评分，238 本地引用通过 | Skill 编排不替代模型质量、点击/语义能力或完整剪映等价验收 |',
        '| 25 | 质量、性能与发行 |': f'| 25 | 质量、性能与发行 | 当前回归与单机原生安装已核验，整体未完成 | V66 1462/1462、{full["suite_seconds"]:.3f} 秒、0 跳过、200 冻结；133 包内文件/25 隔离 CLI；安装版 LaMa harmonic 的 RGBA/PCM 与开发版一致 | 其它机器、安装版 VACE 真推理、自然画音质量、长片/HDR、内容库规模和完整剪映待验 |',
        '| 26 | VACE 多帧联合编辑与生成填充 |': f'| 26 | VACE 多帧联合编辑与生成填充 | pread 后实际案例交付，长期稳定性未验收 | 本轮六权重原生 pread、两个 5 帧窗口/30 步，原 RGBA/PTS/PCM 精确保留；生成区 {vace_quality["psnr_db"]:.3f} dB，{vace_gate} 30 dB；合入前旧 inpaint 25.171 dB 亦未过线 | 两次旧原生访问冲突保留，底层根因与长期稳定性未确认；自然结构/纹理/时序仍未验；不同放置不作模型排名 |',
    }
    lines=progress.read_text(encoding='utf8').splitlines()
    for prefix,row in rows.items():
        indices=[i for i,line in enumerate(lines) if line.startswith(prefix)]
        assert len(indices)==1,prefix
        lines[indices[0]]=row
    progress.write_text('\n'.join(lines)+'\n',encoding='utf8',newline='\n')
    matrix=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md'
    insert(matrix,'V66-OUTPAINT',f'| 子项 | 实现与核验 | 状态 |\n|---|---|---|\n'
        f'| #36/#56/#95 生成式扩图 | 本地 LaMa/VACE、大画布/整数放置、完整原 RGBA/PCM/PTS 保护、配方和跨项目复用 | '
        f'执行与保留子项通过；生成区按 ≥30 dB 单例评分，广泛自然质量仍 degraded；[实测]({REPORT}) |')
    print(json.dumps({'full':1462,'new_outpaint_subset':24,'vace_subset':41,'added_reader_methods':8,'frozen':200,'development_cli':development_cli,'packaged':133,'skills':17,'links':238},ensure_ascii=False))


if __name__=='__main__':main()
