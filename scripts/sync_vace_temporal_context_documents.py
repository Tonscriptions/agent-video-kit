"""Publish V68's measured engineering scope without accepting unrun quality gates."""
from __future__ import annotations

import json
import os
from pathlib import Path

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/vace-temporal-context-20261020-v68'
REPORT=ROOT/'docs/validation/VACE前窗生成上下文实测_2026-10-20.md'
CONTRACT=ROOT/'docs/specs/VACE前窗生成上下文与连续输出契约_v0.1_2026-10-20.md'


def read(path):return json.loads(path.read_bytes())
def relative(source,target):return Path(os.path.relpath(target,source.parent)).as_posix()


def insert(path,marker,content):
    text=path.read_text(encoding='utf8');start='<!-- '+marker+' -->';end='<!-- /'+marker+' -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1);text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    current=frozen();full=read(BASE/'full-r1.json');target=read(BASE/'target-r3.json')
    actual=read(BASE/'previous-r1/verification.json');dev=read(BASE/'lama-r1/verification.json')
    installed=read(BASE/'installed-r1/verification.json');skills=read(BASE/'skills-r1.json')
    for value in (full,target,dev,installed):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert full['terminal_ok'] and full['methods']==1520 and not full['skipped'] and full['exit_code']==0
    assert target['terminal_ok'] and target['methods']==65 and not target['skipped'] and target['exit_code']==0
    assert len(current)==204 and actual['status']!='running'
    assert installed['status']=='passed' and installed['packaged_files']==135 and installed['isolated_cli_calls']==28
    assert dev['frames']==dev['model_calls']==8 and dev['cli_calls']==23 and all(c['passed'] for c in dev['checks'])
    assert skills['skill_count']==17 and skills['local_links_checked']==250
    runtime=lambda values:{k:v for k,v in values.items() if not k.startswith('product/tests/')}
    revision=read(BASE/'test-only-revision.json')
    assert actual['frozen_equal'] is False and revision['changed_inputs']==['product/tests/test_vace_context.py']
    assert actual['frozen_before']==revision['frozen_before'] and actual['frozen_after']==revision['frozen_after']==current
    assert runtime(actual['frozen_before'])==runtime(actual['frozen_after'])==runtime(current)
    if actual['status']=='failed':
        failed=read(BASE/'previous-r1/failure-r1/verification.json')
        assert failed['status']=='passed' and failed['accepted_vace_forwards']==0
        admission=failed['gpu_admission_failure']
        actual_note=(f'真实 VACE previous 在文本权重准入阶段拒绝：物理可用 {admission["physical_free_bytes"]/1024**2:.0f} MiB，'
            f'要求 {admission["required_free_bytes"]/1024**2:.0f} MiB；CLI 退出码 6，**0 有效 VACE 前向/无成片**，原错误和诊断保留。')
        quality_note='当前 none/previous 的真实成片对照及自然质量仍未验收。'
    else:
        q=actual['quality'];actual_note=(f'真实 VACE previous 交付 {actual["frames"]} 帧/{actual["model_calls"]} 次模型调用，'
            f'受控生成区 {q["psnr_db"]:.9f} dB，预先 ≥30 dB {"通过" if q["passed"] else "未通过"}；时间误差另计。')
        quality_note='本轮 previous 成片不能替代同版 none 成片对照、自然质量和连续播放/听审。'
    summary=(f'2026-10-20 **V68（CLI/协议/发行限定核验）**：显式 `media inpaint|outpaint --temporal-context previous`，'
        '把同场景、同一全局帧已经正式输出的生成选区交给后窗，保留已输出前缀；默认/`none` 保持旧路径。'
        f'完整 **1520/1520、{full["suite_seconds"]:.3f} 秒、0 跳过、204 输入冻结**；65 项 VACE 定向是子集，新增 24 方法。'
        '**135 包内资源/7 wheels/28 隔离 CLI**，另 1 次安装模块契约调用；开发/安装各 8 帧真实 LaMa 控制，全部 RGBA/PCM 相同；'
        '**17 Skills/250 引用**。'+actual_note+' '+quality_note+' **完整剪映等价未验收**。')
    table='''| 编号 | 核验内容 | 实际结果与边界 |
|---|---|---|
| VTC-V01 | 前窗条件、输出时序和身份 | 两窗、21 窗/极高重叠、移动选区、Alpha、harmonic/feather/量化后的真实前缀；协议回调不当作 VACE 推理 |
| VTC-V02 | 负对照、切点和预算 | 擦除颜色不泄漏、倍率 1/2/4、场景清空、空窗口/无新增选区旁路；额外 W×H×4×overlap 在读帧/模型前准入 |
| VTC-V03 | 默认兼容 | 7 类受控配置，与封存 V67 完整输出、调用输入/采样及写出时序逐字节对照 |
| VTC-V04 | 报告与资产事务 | 控制器/模型侧实际 RGB/mask 摘要一致；坏报告拒绝并回滚；配方/生成参数随工程包和片段组保留 |
| VTC-V05 | 完整回归与发行 | 1520 项包含 65 项定向；135 资源、28 隔离 CLI、1 次安装模块契约调用；不能累加中间轮次 |
| VTC-V06 | 真实模型与质量 | 真实 VACE 命令单独留证；LaMa 控制不代替 previous、30 dB、自然结构或完整剪映效果 |
'''
    report=f'''# VACE 前窗生成上下文实测

{summary}

[实现契约](../specs/VACE前窗生成上下文与连续输出契约_v0.1_2026-10-20.md)。当前通过范围是显式模式的规划、受控数据流、身份校验、资产事务、默认兼容和原生发行；真实 VACE 条件有效性与生成质量继续单独开放。生成内容不是独立真值，不能用条件摘要或测试数证明视觉效果。

{table}

## 冻结范围和原始收据

| 证据 | 范围 |
|---|---|
| [完整回归](evidence/vace-temporal-context-20261020-v68/full-r1.json) /[原日志](evidence/vace-temporal-context-20261020-v68/full-r1.log) | 1520/1520，0 跳过；当前 204 份 source/test/schema/native installer 输入相同 |
| [最终定向](evidence/vace-temporal-context-20261020-v68/target-r3.json) | 65/65，含新增 24 方法；不是额外 65 个独立产品功能 |
| [真实 VACE previous](evidence/vace-temporal-context-20261020-v68/previous-r1/verification.json) | {actual_note} 采样为原 30 steps、seed 0、window 5/overlap 2、scale 1、flow 3、harmonic；显式 text GPU/CPU 7168/8192 MiB |
| [实际失败独立核验](evidence/vace-temporal-context-20261020-v68/previous-r1/failure-r1/verification.json) /[原诊断 ZIP](evidence/vace-temporal-context-20261020-v68/previous-r1/failure-r1/failure.zip) | 另 4 次真实诊断/策略 CLI；没有登记失败资产、输出、缓存或事务。只读查询前后作者元数据相同，但未事先捕获 outpaint 前字节，不能把库存检查写成真实失败前后逐字节回滚证明 |
| [真实 LaMa 控制](evidence/vace-temporal-context-20261020-v68/lama-r1/verification.json) | 开发 23 CLI、8 次实际前向/8 帧；当前共享管道不改变默认输出，受控 {dev['quality']['psnr_db']:.9f} dB，30 dB 单项通过 |
| [原生安装](evidence/vace-temporal-context-20261020-v68/installed-r1/verification.json) /[媒体细节](evidence/vace-temporal-context-20261020-v68/installed-r1/base/media/verification.json) | 135 资源；28 次隔离 CLI、1 次隔离模块契约调用；另 8 次 LaMa 前向；全部 RGBA/PCM 与开发同一；没有安装版 VACE 推理 |
| [Skills](evidence/vace-temporal-context-20261020-v68/skills-r1.json) | 17 个 `video-cut-`，250 处本地引用，C 盘发现目录仍联接 E 盘 |

真实 previous 首轮在测试断言修订前启动。[测试修订前后清单](evidence/vace-temporal-context-20261020-v68/test-only-revision.json)明确记录期间只有 `product/tests/test_vace_context.py` 变化，原始收据因此诚实保留 `frozen_equal=false`；全部运行时源码、schema、installer 和 36 项 adapter 执行闭包不变。它与最终回归运行时代码同一，但不能称两份 204 项清单完全相同。每份收据保留原脚本/命令/退出值/stdout/stderr；gzip stdout 为原字节无损压缩。

开发真实命令分计为 23 次 LaMa、4 次 VACE（含失败 outpaint）和 4 次诊断/策略，共 31 次 CLI。单元测试中的 CLI 调用不重复累加。当前诊断 `response.json` 是限长白名单摘要，只保留 worker_error 等字段；GPU 明细来自原始 CLI `errors[0].cause` 中仍完整保留的对象，独立核验记录该段 SHA，没有伪造完整 worker 响应。

此次 `first_failure_roles=[decoder]` 是首次观测；worker 的结构化错误明确指向显存准入，不能用 Broken pipe 或退出先后来推断根因。三个管道角色记录均为已自然观测退出、未请求清理终止；[5 个抽样自有进程的身份复核](evidence/vace-temporal-context-20261020-v68/previous-r1/owned-process-cleanup-r1.json)均已退出，检查器停止 0 个进程，不触碰其它任务。没有新 Torch 访问冲突。

## CLI 与资产语义

```powershell
python -X utf8 -m ai_ad_editor media outpaint --project <project> --asset-id <source> --adapter-id <fresh-vace> --derived-asset-id expanded --width 256 --height 160 --offset-x 32 --offset-y 16 --prompt '<原文提示词>' --inference-steps 30 --window-frames 5 --window-overlap 2 --temporal-context previous --repair-blend harmonic --dry-run
```

positive overlap 是必需条件；LaMa 拒绝 VACE 专属参数。默认和显式 `none` canonical generation 不增加模式字段。previous 每帧仅输出一次，后窗不替换已发出的前缀；新场景清空上下文。原 Alpha、选区外 RGB、每个 PTS 和完整 PCM 保留，扩图继续保护完整原矩形。最多保留 overlap 帧实际合成/量化后的 RGBA，额外 owned-array 上界为 `width×height×4×overlap`，并非 Torch/RSS/显存保证。

`temporal_context.input_trace` 和模型调用侧 `conditioning_trace` 绑定实际 RGB/mask 的全部调用，窗口明细最多首 16 份。全空选区或仅剩已知前缀无需再调用模型。摘要不等于正确结构。新 `vace_context.py` 纳入 adapter 闭包，改实现必须重新登记。

扩图保留完整 `source.outpainting`；修复的已编码视频保存 canonical `source.vace_generation` 并验证输出帧范围。工程包和片段组保留采样，历史 source/mask 来源 ID 不是新工程可执行引用；权利依赖按片段组规则重新绑定。导入、复用和播放不启动模型，不复制模型权重；重新推理需显式给源、mask 和有效 adapter。

## 原片、实际输出与保留失败

以下是当前共享管道的 **LaMa 控制样例，不是 VACE previous 效果**。

[原创原视频](../assets/vace-temporal-context-20261020-v68-lama-r1/source.mp4) /[实际 LaMa 输出](../assets/vace-temporal-context-20261020-v68-lama-r1/expanded.mp4) /[无损 MOV](../assets/vace-temporal-context-20261020-v68-lama-r1/expanded.mov) /[文件与采样来源](../assets/vace-temporal-context-20261020-v68-lama-r1/provenance.json)。

![当前 LaMa 控制：输入填充、真实输出、独立受控真值；无声 GIF](../assets/vace-temporal-context-20261020-v68-lama-r1/comparison.gif)

同一 V66 CC0 程序化输入：8 fps/1 秒/8 帧，192×128→256×160，部分 Alpha、48,000 帧立体声 PCM。GIF 为预览，不是全质量真值或听审。{quality_note}

已[静态查看实际 0/3/4/7 帧](evidence/vace-temporal-context-20261020-v68/static-review-r1.json)：生成外部大体延续横向墙面/桌面色带，与真值仍有细纹和边界差异。没有连续播放或听审；精确原区域保护由独立解码字节检查判定。

| 编号 | 保留记录 | 处理与边界 |
|---|---|---|
| VTC-F01 | [首轮 22 项](evidence/vace-temporal-context-20261020-v68/target-r1.json) | 早期版本全部通过；后补生成参数持久化和 2 方法，不累加为最终通过数 |
| VTC-F02 | [65 项失败轮](evidence/vace-temporal-context-20261020-v68/target-r2.json) /[源封存](evidence/vace-temporal-context-20261020-v68/pre-assertion-fix-source.json) | 64 通过、1 失败；断言把历史来源 ID 当成新工程执行引用，改为保留历史来源并核验重新绑定的完整权利依赖 |
| VTC-F03 | [真实 previous 首轮](evidence/vace-temporal-context-20261020-v68/previous-r1/verification.json) | {actual_note} 原错误、设备预算与任何未达门槛继续保留，不用 LaMa 或协议回调代替 |
| VTC-F04 | [V66 历史真实 VACE](evidence/video-outpainting-20261019-v66/vace-harmonic-r4/verification.json) | 19.227695470 dB，仍低于事先 30 dB；桌沿/暗带与原生访问冲突历史仍保留，不冒称本轮已解决 |

当前同参数 none/previous 双成片、独立自然素材、连续播放/听审、长片压力、所有平台和完整剪映功能/效果仍未验收。资源不足不会停止其它 GPU 任务，也不自动降低预算、采样或使用在线替代。

## 发行和复现

[当前原生离线 ZIP](../assets/vace-temporal-context-20261020-v68-installed/release/agent-video-kit-cp313-win_amd64.zip) /[manifest](../assets/vace-temporal-context-20261020-v68-installed/release/manifest.json)。覆盖本机原生 CPython 3.13/Windows 与已有外部工具；没有 Docker/WSL、新虚拟环境、模型下载或在线 provider。摘要是内容完整性，不是作者签名或另一台机器认证。

复现脚本为 `scripts/run_frozen_regression.py`、`scripts/smoke_video_outpainting.py`、`scripts/verify_vace_temporal_context_install.py`。OpenFilm 的模块拆取仍按 [R09 报告](../OpenFilm最新复用评估与成本取舍_2026-10-20.md)，其批次/HTML 子帧候选不当作本轮已实现能力。
'''
    REPORT.write_text(report,encoding='utf8',newline='\n')
    paths=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
        'docs/specs/AgentCLI契约_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md',
        'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    for name in paths:
        path=ROOT/name;body=summary+f' [编号核验、原片/GIF、失败及发行]({relative(path,REPORT)})。'
        if name=='README.md':
            text=path.read_text(encoding='utf8')
            if '<!-- V68-WIP -->' in text:
                a=text.index('<!-- V68-WIP -->');b=text.index('<!-- /V68-WIP -->',a)+len('<!-- /V68-WIP -->')
                path.write_text(text[:a]+text[b:],encoding='utf8',newline='\n')
            body+='\n\n'+table+'\n![当前 LaMa 控制样例，非 VACE previous](docs/assets/vace-temporal-context-20261020-v68-lama-r1/comparison.gif)\n\n[原片](docs/assets/vace-temporal-context-20261020-v68-lama-r1/source.mp4) /[真实 LaMa 输出](docs/assets/vace-temporal-context-20261020-v68-lama-r1/expanded.mp4)。'
        insert(path,'V68-CURRENT',body)
    matrix=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md'
    insert(matrix,'V68-CONTEXT','| 子项 | 当前核验 | 状态 |\n|---|---|---|\n'
        '| 前窗生成条件/一次输出/可追溯采样/协议与发行 | 24 新方法、65 定向、1520 完整、135 资源、28 隔离 CLI | 工程与协议限定通过 |\n'
        '| 真 VACE 条件画质/自然结构/长片/完整剪映效果 | 单独保留模型命令及未过门槛，不以 LaMa 控制替代 | 未验收 |')
    text=CONTRACT.read_text(encoding='utf8').replace('状态：V68 设计及实现中，尚未验收。','状态：V68 CLI、协议及发行完成限定核验；真实 VACE 条件画质和自然质量未验收。')
    CONTRACT.write_text(text,encoding='utf8',newline='\n')
    readme=ROOT/'README.md';lines=readme.read_text(encoding='utf8').splitlines()
    for index,line in enumerate(lines):
        if line.startswith('- 当前模块进度见'):
            lines[index]='- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：V68 工程/协议完整 1520/1520，65 定向为子集，135 包内资源/28 隔离 CLI；真实 VACE 条件质量与完整剪映等价仍未验收。'
    readme.write_text('\n'.join(lines)+'\n',encoding='utf8',newline='\n')
    manifest=ROOT/'video-cut-install-manifest.json';mapping=read(manifest)
    assert mapping['current_audit']['record'].endswith('vace-temporal-context-20261020-v68/skills-r1.json')
    mapping['current_audit']['semantics']='V68: explicit previous generated conditions, CLI/protocol/native-package limited verification; generated context is not truth; real VACE quality, natural quality and full CapCut parity unaccepted'
    manifest.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'documents_updated':len(paths)+2,'full_methods':full['methods'],'source_files':len(current)}))


if __name__=='__main__':main()
