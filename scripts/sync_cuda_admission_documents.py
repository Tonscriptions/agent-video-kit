"""Publish V60 regression/native admission and explicitly unfinished model delivery."""
import json
from pathlib import Path
from sync_color_automation_documents import marked,line

ROOT=Path(__file__).resolve().parents[1]
REPORT='VACE物理显卡准入与真实交付实测_2026-10-19.md'
CONTRACT='VACE物理显卡准入与分阶段资源检查契约_v0.1_2026-10-19.md'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
 'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
 'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
BASE='docs/validation/evidence/cuda-admission-20261019-v60/'
INSTALL='docs/validation/evidence/cuda-admission-install-20261019-v60-r3/'
FIRST='docs/validation/evidence/cuda-admission-vace-20261019-v60/'
ASSETS='cuda-admission-source-20261019-v60'
PACKAGE='cuda-admission-20261019-v60-r3'
def read(name):return json.loads((ROOT/name).read_bytes())

def run():
    full=read(BASE+'full-r2.json');unit=read(BASE+'unit-r2.json');vace=read(BASE+'vace-r2.json')
    install=read(INSTALL+'verification.json');native=read(BASE+'native-r3.json')
    failure=read(FIRST+'r1-worker-response.json');review=read(BASE+'source-contact-review.json')
    if not full.get('terminal_ok') or full['exit_code'] or full['skipped'] or not full['frozen_equal'] or full['methods']!=1374:
        raise ValueError('completed current frozen 1374-method regression required')
    if (install['status']!='passed_native_install_and_cuda_admission'
            or native['status']!='passed_native_cuda_sampling_allocation_and_loader_rejection'
            or native['actual_allocation_bytes']!=128*1024**2 or not native['allocation_released']):
        raise ValueError('completed native/installed admission required; model delivery remains pending')
    reject=read(BASE+'native-r2.json')['admission_failure'];first=failure['gpu_admission_failure']
    summary=(f"2026-10-19 **V60（产品增量，GPU 完整交付待验）**：VACE 用完整 GPU UUID 对齐物理/Torch free，"
      '在文本加载、视频上卡和每个非空窗口准入；补充文本卸载钩子清理及当前 worker 空闲缓存的前后记录。'
      f"**{full['methods']}/{full['methods']}、{full['suite_seconds']:.3f} 秒、0 跳过、188 文件冻结**；"
      '16 新资源专项和 33 VACE 专项属于全量子集。'
      '本机原生离线安装 **125 包内文件/2 隔离 CLI/安装版 CUDA 准入** 通过，当前源码原生 **128 MiB** 有效分配/自身空闲缓存释放通过。'
      f"首轮模型在窗口 1 前因 Torch free {first['torch_free_bytes']/1024**2:.3f} MiB 拒绝；"
      f"修订版小额探测在分配前因物理 free {reject['physical_free_bytes']/1024**2:.3f} MiB 拒绝，"
      '该次未执行分配，资源回升后的复测通过。**本轮无新修复成片**；保留原片/选区/真值及失败。'
      '不预约显存、不保证无 OOM，当前真模型整链、自然质量和完整剪映等价待验。')
    report=f'''# VACE 物理显卡准入：回归和原生准入通过，模型交付待验

{summary}

依据[先行契约及首轮拒绝后的 G60-12 补充](../specs/{CONTRACT})。本轮没有关闭自然修复差异 #56。首轮拒绝与后续资源观测只能确认共享资源不足，不能把原因单独归于 allocator 缓存。未停止、卸载或改变其他原生服务/配音进程，未使用云服务、虚拟化或质量降级。

## 编号状态

| 编号 | 实现或实测 | 状态与范围 |
|---|---|---|
| V60-01 | Torch `_CUuuid` 完整 UUID 对应本地 `nvidia-smi --id=GPU-…` | 代码、资源单元及真实原生通过/拒绝；缺失、MIG、非 0 逻辑设备、错设备和非法 CSV 明确拒绝 |
| V60-02 | 两个 free 取较小值，加载/窗口分阶段检查 | 分时采样，不是原子快照、显存预约或 OOM 保证 |
| V60-03 | 文本显式预算＋768 MiB；视频实际参数/缓冲区与嵌入＋768 MiB；窗口 768 MiB | 已实现；修订版真模型全过程待验，768 MiB 不是激活峰值估计 |
| V60-04 | 当前 worker 同步、自身空闲缓存释放及 allocated/reserved 前后计数 | 16 专项含 4 个清理/保留/拒绝新方法；当前原生 128 MiB 有效张量在清缓存时保持，删除后自身 reserved 128→0 MiB，allocated 归零；不清理其它用户进程 |
| V60-05 | 文本编码完成后移除 Accelerate offload hooks，再删除编码器 | 本地原生 API 已核对，代码及成功元数据门禁已接入；真实新版本执行待验，不据此宣称解决首轮原因 |
| V60-06 | 旧清单需新 adapter ID 显式登记；新 helper 纳入摘要闭包 | 33 VACE 专项含旧控制与新摘要/八种新增坏报告回滚子例，为 {full['methods']} 方法子集，不能相加扩大测试数 |
| V60-07 | 首版完整回归 1370/1370，0 跳过，188 输入冻结 | 首版真实模型仍在首个视频窗口前拒绝；全部首版代码、日志和失败响应保留，不计成功交付 |
| V60-08 | 修订版完整回归 {full['methods']}/{full['methods']}，{full['suite_seconds']:.3f} 秒 | 0 跳过，188 输入冻结；完整回归含原生 HTML 浏览器生命周期测试，页面与自建子进程由原门禁回收 |
| V60-09 | 修订版原生离线安装，7 个本地 wheel、125 包内文件逐字节一致、2 个 `-I -S` CLI 及安装版驱动准入 | **本机原生安装/准入通过**；安装版小额量为 0 MiB，128 MiB 有效张量另由当前源码探测；外部 Torch/驱动/模型未随包分发，无模型前向 |
| V60-10 | 失败诊断与权利 | 首轮未生成/登记 repaired 成片。旧模型/素材权利门禁保留；没有新交付，未执行新的商业发布或用技术样例充当许可通过 |
| V60-11 | 原始 8 帧@8 fps 输入、选区和隐藏背景真值公开 | 原创 CC0-1.0 既有受控夹具，0 新来源场景。只发布输入预览，**没有本轮修复输出、PSNR 或 Alpha/PCM 保留通过结果** |
| V60-12 | 待完成项 | 修订版固定 VACE 30 步/5 帧窗口/2 帧重叠完整正式交付，包括真实文本钩子卸载和视频全过程；仍按 ≥30 dB 单项和独立 Alpha/区外/音频/PTS 门槛验收 |

## 两次真实拒绝

| 采样 | required MiB | Torch free MiB | 物理 free MiB | 原因 |
|---|---:|---:|---:|---|
| 首版真模型，首个视频窗口 | {first['required_free_bytes']/1024**2:.3f} | {first['torch_free_bytes']/1024**2:.3f} | {first['physical_free_bytes']/1024**2:.3f} | `INSUFFICIENT_TORCH_FREE`，0 个视频去噪窗口 |
| 修订版，计划小额分配之前 | {reject['required_free_bytes']/1024**2:.3f} | {reject['torch_free_bytes']/1024**2:.3f} | {reject['physical_free_bytes']/1024**2:.3f} | `INSUFFICIENT_PHYSICAL_FREE`，未执行 128 MiB 分配 |

[修订版真实失败](evidence/cuda-admission-20261019-v60/native-r2.json)保存当前代码摘要与自身 cache 前后 0 字节，不能把 Torch 的较大 free 当作真实整卡可用量。[首轮只读资源观察](evidence/cuda-admission-20261019-v60/resources-r1.json)及[后续资源回升](evidence/cuda-admission-20261019-v60/resources-r3.json)保留驱动计数及脱敏进程日期/ID；WDDM 未提供各进程占用量，未归因某个进程，也未修改它们。完整回归与共享机器任务并行，耗时仅描述本次运行，跨轮性能需单独测量。

资源回升后，[当前源码原生复测](evidence/cuda-admission-20261019-v60/native-r3.json)在 {native['elapsed_seconds']:.3f} 秒通过。分配前物理 free {native['before_allocation']['physical_free_bytes']/1024**2:.0f} MiB；有效 allocated 128 MiB 在 `empty_cache` 前后不变；删除有效张量后自身 reserved 128→0 MiB，记录实际释放 128 MiB。另用不可能的文本预算验证组件导入/权重访问前拒绝，0 权重加载/0 模型前向。该结果完成小额原生准入验收，不能证明固定模型可用、无 OOM 或自然质量通过。

首轮沿用旧输入与固定 17 文件模型，已加载组件并编码提示词，在视频去噪前停止。[失败后的工程状态观察](evidence/cuda-admission-20261019-v60/failure-project-state.json)及对应原始工程快照确认：仅保留两份原输入，0 个时间线片段、0 个项目输出，没有登记修复成片。生成设置见[原始失败响应](evidence/cuda-admission-vace-20261019-v60/r1-worker-response.json)；旧摘要未存的 `flow_shift=3.0` 与 `model_input_scale=1` 是后来显式字段，本轮不做跨版本质量 A/B，也不与 ROSE/FGT 的另一条 32 帧纹理场景直接排名。

## 原输入预览，未交付修复输出

![只展示原片、请求选区、隐藏背景真值；无新修复成片](../assets/{ASSETS}/input-only.gif)

[原视频预览](../assets/{ASSETS}/source-preview.mp4)、[原始 MOV](../assets/{ASSETS}/source.mov)、[选区 MOV](../assets/{ASSETS}/mask.mov)、[隐藏背景数组](../assets/{ASSETS}/ground-truth.npz)、[来源/显示边界](../assets/{ASSETS}/provenance.json)。GIF/MP4 是 RGB 显示衍生，不证明透明度或 PCM 保留；真值列不是模型结果。

已查看第 0、4、7 帧[原输入接触表](../assets/{ASSETS}/input-contact.png)：{'；'.join(review['observations'])}。[静帧观察记录](evidence/cuda-admission-20261019-v60/source-contact-review.json)不包含连续播放、听审或模型画质验收。

## 原始证据与复测条件

- [16 个资源专项](evidence/cuda-admission-20261019-v60/unit-r2.json)、[33 个 VACE 专项](evidence/cuda-admission-20261019-v60/vace-r2.json)、[当前完整回归](evidence/cuda-admission-20261019-v60/full-r2.json)。
- [首版完整回归](evidence/cuda-admission-20261019-v60/full-r1.json)、[188 输入封存](evidence/cuda-admission-20261019-v60/r1-frozen-inputs.zip)、[封存清单](evidence/cuda-admission-20261019-v60/r1-source-snapshot.json)、[首轮实际失败](evidence/cuda-admission-vace-20261019-v60/verification.json)。
- [旧源码的真实 128 MiB 探测](evidence/cuda-admission-20261019-v60/native-r1.json)是首版历史证据，不能替代修订版的原生活跃张量验证。
- [当前安装/2 CLI/驱动准入收据](evidence/cuda-admission-install-20261019-v60-r3/verification.json)、[安装版原生探测](evidence/cuda-admission-install-20261019-v60-r3/native-installed.json)、[离线包](../assets/{PACKAGE}/agent-video-kit-cp313-win_amd64.zip)、[manifest](../assets/{PACKAGE}/release-manifest.json)、[安装收据](../assets/{PACKAGE}/install-receipt.json)。
- [较早 CPU-only 安装](evidence/cuda-admission-install-20261019-v60-r2-cpu/verification.json)保留其当时 CUDA 待验标记，不覆写历史收据。
- [原输入发布摘要与原命令](evidence/cuda-admission-20261019-v60/source-publication.json)。

固定 VACE 文本阶段要求同一设备 Torch/物理 free 均至少 7,936 MiB，之后仍须阶段检查。本次小额复测前的物理 free 尚低于此值，没有启动第二次完整模型运行。资源可用时，使用已有本地原生 CUDA Python、固定权重和来源证据，在新目录复测，不覆写以上首轮。`scripts/probe_vace_cuda_admission.py` 做小额分配/拒绝；`scripts/run_cuda_admission_vace.py` 重建既有场景并正式交付，依赖本机历史摘要和 `.runtime` 权重，干净克隆不含这些权重。旧适配器应以新 ID 显式重新登记，禁止手改旧 SHA。

资源准入只覆盖 VACE。其他引擎、全局调度/预约、自然背景/纹理/阴影反射、字词对齐精度、开放内容库、长片/HDR、干净机器和完整剪映功能/效果仍按各自证据推进。

独立的 [OpenFilm 三套创作流程本地适配设计](../OpenFilm创作流程本地适配设计_2026-10-19.md)补充固定上游来源和本地 22 个命令声明映射，未执行编辑/模型、未新增 Skill 或整片，不计入以上产品回归或交付通过。
'''
    (ROOT/'docs/validation'/REPORT).write_text(report,encoding='utf-8',newline='\n')
    for name in DOCS:
        path=ROOT/name;text=path.read_text(encoding='utf-8')
        text=text.replace('\n2026-10-19 **V59（研究）**','\n历史研究 2026-10-19 **V59（研究）**').replace('\n2026-10-19 **V58（产品）**','\n历史产品 2026-10-19 **V58（产品）**')
        text=text.replace('最近完整产品回归仍为 V58 1357/1357','该轮最近完整产品回归为 V58 1357/1357')
        prefix='docs/validation/' if name=='README.md' else ('./' if name.startswith('docs/validation/') else 'validation/')
        block=summary+f' [原片/拒绝/范围/安装证据]({prefix}{REPORT})。'
        if name in ('README.md','docs/README.md'):
            design_prefix='docs/' if name=='README.md' else './'
            block+=f' 另有 [OpenFilm 三套创作流程适配设计]({design_prefix}OpenFilm创作流程本地适配设计_2026-10-19.md)：22 命令声明映射，未新增 Skill 或整片。'
        if '<!-- V60-CURRENT -->' in text:text=marked(text,'V60-CURRENT',block)
        else:
            position=text.index('\n')+1;text=text[:position]+'\n<!-- V60-CURRENT -->\n'+block+'\n<!-- /V60-CURRENT -->\n'+text[position:]
        if name=='README.md':
            row=(f'| V60 | VACE 物理显存准入与 worker 清理 | {full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、188 冻结；125 包内文件/2 隔离 CLI/安装版 CUDA；原生 128 MiB | 两轮拒绝保留，小额复测通过；当前 GPU 完整交付待验，无新修复成片 | [原片/GIF/失败/安装]({prefix}{REPORT}) |')
            if '| V60 |' in text:text=line(text,'| V60 |',row)
            else:
                rows=text.splitlines();index=next(i for i,x in enumerate(rows) if x.startswith('| V59 |'));rows.insert(index+1,row);text='\n'.join(rows)+'\n'
            demo=(f'**V60 原始输入夹具，无本轮新修复成片**：原片、请求选区、隐藏背景真值；修订版 GPU 完整交付待验。'
                  f'[原视频](docs/assets/{ASSETS}/source-preview.mp4)、[实际拒绝与范围](docs/validation/{REPORT})。\n\n'
                  f'![V60 输入原片；不是模型修复结果](docs/assets/{ASSETS}/input-only.gif)')
            if '<!-- V60-DEMO -->' in text:text=marked(text,'V60-DEMO',demo)
            else:text=text.replace('<!-- V59-DEMO -->','<!-- V60-DEMO -->\n'+demo+'\n<!-- /V60-DEMO -->\n\n<!-- V59-DEMO -->',1)
        if name=='docs/构建进度总表_2026-10-16.md':
            text=line(text,'| 15 |','| 15 | 离线模型接入 | 部分实现，V60 原生准入通过，模型交付待验 | VACE UUID 绑定物理/Torch free、分阶段检查、当前 worker 清理和结构化拒绝；128 MiB/安装版准入通过；真实失败与源码保留 | 当前修订版模型整链交付、其他引擎、自然画质与跨设备待验 |')
            text=line(text,'| 24 |','| 24 | Agent Skills | 已实现，持续扩展 | 14 个 video-cut- Skill；同步 VACE 清理/准入/重新登记及 GPU 验收待完成边界 | 技能数量不代表功能或质量覆盖率 |')
            text=line(text,'| 25 |',f'| 25 | 质量、性能与发行 | 回归/安装/原生准入已核验，整体未完成 | V60 {full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、188 冻结；125 包内文件/2 隔离 CLI/安装版 CUDA；原生 128 MiB | 当前 GPU 模型完整交付、另一台机器、自然质量、长片/HDR、完整剪映待验 |')
        if name.endswith('能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
            row=f'| VACE 物理 GPU 准入（V60） | UUID/两种 free；文本、视频、每个窗口；自身 cache 和文本 offload hooks 清理；父进程验证 | [当前 {full["methods"]} 回归/188 冻结与真实拒绝]({REPORT})；125 包内文件/2 隔离 CLI/安装版 CUDA；原生 128 MiB | 当前 GPU 模型完整交付待验；无预约/OOM 保证；自然与完整等价待验 |'
            if '| VACE 物理 GPU 准入（V60） |' in text:text=line(text,'| VACE 物理 GPU 准入（V60） |',row)
            else:text=text.replace('| ROSE 离线修复候选（V59 研究） |',row+'\n| ROSE 离线修复候选（V59 研究） |',1)
        path.write_text(text,encoding='utf-8',newline='\n')
    path=ROOT/'skills/video-cut-local-models/SKILL.md';text=path.read_text(encoding='utf-8')
    block=(f'Follow the [V60 device contract](../../docs/specs/{CONTRACT}) and\n'
      f'[measured failures and pending GPU delivery](../../docs/validation/{REPORT}).\n'
      'VACE maps logical CUDA 0 to its full GPU UUID and admits against the\n'
      'smaller physical/Torch free count. Before each admission it synchronizes\n'
      'this worker and releases its unused allocator cache, preserving active\n'
      'allocation counts; it removes text offload hooks after encoding. Text\n'
      'requires its GPU budget plus 768 MiB; video weights/embeddings are checked\n'
      'before transfer; every nonempty window requires 768 MiB free. These are\n'
      'observations, not reservations or activation/OOM guarantees. Current CPU\n'
      'regression, native 128 MiB active allocation/cache release, package/CLI\n'
      'and installed CUDA admission checks passed. Complete revised trained-model\n'
      'delivery remains pending. Never stop unrelated jobs, lower quality or switch to CPU/cloud\n'
      'to conceal a rejection. Re-register with a new adapter ID; retain old\n'
      'receipts and never edit old hashes. Other engines keep existing policies.\n')
    if '<!-- V60-CUDA -->' in text:text=marked(text,'V60-CUDA',block)
    else:text=text.replace('For prompted joint video editing, read the','<!-- V60-CUDA -->\n'+block+'<!-- /V60-CUDA -->\n\nFor prompted joint video editing, read the',1)
    path.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'documents':8,'skills':1,'full_methods':full['methods'],'gpu_delivery':'pending'}))

if __name__=='__main__':run()
