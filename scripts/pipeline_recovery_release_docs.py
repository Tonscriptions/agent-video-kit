"""Generate final-snapshot documentation from actual, separately bound receipts."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote

from run_frozen_regression import frozen, sha

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/pipeline-recovery-20261023'
KREL=ROOT/'docs/validation/evidence/float-keyer-20261023-lab'
REPORT='docs/validation/浮点调色抠像合并验收与诊断恢复_2026-10-23.md'
CONTRACT='docs/specs/浮点调色抠像合并交付与诊断恢复契约_v0.1_2026-10-23.md'
MARKER='R111-FLOAT-COLOR-KEYER-DIAGNOSTICS'
COMMON=['docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/specs/AgentCLI契约_v0.1_2026-10-13.md']


def read(path):return json.loads(path.read_bytes())


def optional(path):
    return read(path) if path.exists() else {'status':'not-created'}


def accepted(require_full=False):
    inputs=frozen();assert len(inputs)==330
    paths={'source':REL/'native-r3/verification.json','installed':REL/'installed-r1/verification.json',
        'media':KREL/'media-recovery-source-r2/verification.json','4K':KREL/'4k-r3/verification.json',
        'full':REL/'full-r2.json'}
    values={name:optional(path) for name,path in paths.items()}
    if require_full:
        assert values['source']['status']=='passed' and values['source']['methods']==8 and values['source']['skipped']==0
        assert values['installed']['status']=='passed-fresh-eight-wheel-197-resources-real-previews-and-804-methods'
        assert values['installed']['isolated_methods']['methods']==804 and values['installed']['isolated_methods']['skipped']==0
        assert values['media']['status']=='passed-public-CLI-floating-keyer-and-native-float-previews'
        assert values['4K']['status']=='passed-actual-default-budget-4K-formal-preview-and-independent-pixels'
        full=values['full']
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2897 and full['skipped']==0
        assert full['external_fixtures_equal'] and full['verification_scripts_equal']
        for value in values.values():assert value['frozen_before']==value['frozen_after']==inputs
    return inputs,paths,values


def status_line(value, methods=None):
    if value.get('status') in ('passed','passed-fresh-eight-wheel-197-resources-real-previews-and-804-methods'):
        if 'isolated_methods' in value:
            row=value['isolated_methods'];return f"实际 {row['methods']} 项，{row['suite_seconds']:.3f} 秒，{row['skipped']} 跳过"
        elapsed=value.get('seconds',value.get('suite_seconds',0))
        return f"实际 {value['methods']} 项，{elapsed:.3f} 秒，{value['skipped']} 跳过"
    return f"{value.get('status','not-created')}；{methods} 项为已发现清单，尚不记为通过" if methods else value.get('status','not-created')


def documents(destination,require_full=False):
    inputs,paths,values=accepted(require_full)
    discovery=read(REL/'discovery-r2.json')
    assert discovery['full_methods']==2897 and discovery['installed_methods']==804 and discovery['frozen_inputs']==inputs
    source=status_line(values['source'],8)
    install=status_line(values['installed'],804)
    full=status_line(values['full'],2897)
    media=values['media'];fourk=values['4K']
    media_text=(f"{len(media.get('calls',[]))} 调用/{len(media.get('checks',[]))} 核验，{media['keyer_oracle']['RGB_values']:,} RGB 值"
                if media.get('status','').startswith('passed-') else media.get('status','not-created'))
    fourk_text=(f"{len(fourk.get('calls',[]))} 调用/{len(fourk.get('checks',[]))} 核验，99,532,800 RGBA 分量"
                if fourk.get('status','').startswith('passed-') else fourk.get('status','not-created'))
    section=f'''<!-- {MARKER} -->
### R111 共同浮点调色、抠像与诊断恢复：最终快照核验

合并色阶/动态曝光、三向色轮/色温、分区 HSL、基础调色、Gaussian/均值/方框模糊、4K 自适应转换、YCbCr 锐化和 RGB/色度抠像/去溢色；原片 `render` 与浮点 `preview` 共用效果链和作者时钟。显式选择 `float32-native-v1`。完整剪映功能及观感等价仍未完成。

| 编号 | 功能性核验 | 本快照实际状态 | 证据 |
|---|---|---|---|
| MR111-01 | 准备期限、取消、事务后诊断、真实浏览器后代清理 | {source}；保留此前 156 项的 1 错误与首次 0 方法加载失败 | [最终源码](docs/validation/evidence/pipeline-recovery-20261023/native-r3/verification.json) · [保留失败](docs/validation/evidence/pipeline-recovery-20261023/native-r2/verification.json) |
| MR111-02 | 本地八轮包、197 资源逐字节一致，隔离安装态执行 | {install} | [安装核验](docs/validation/evidence/pipeline-recovery-20261023/installed-r1/verification.json) |
| MR111-03 | 最终同一 330 输入、完整原生回归和八项外部夹具 | {full} | [全量收据](docs/validation/evidence/pipeline-recovery-20261023/full-r2.json) |
| MR111-04 | 当前 CLI 两秒五场景、原片/输出、PCM/PNG16/缓存 | {media_text}；两次正式 render、三次 preview | [实片收据](docs/validation/evidence/float-keyer-20261023-lab/media-recovery-source-r2/verification.json) |
| MR111-05 | 默认 768 MiB 算子预算下的 4K 三组单帧 | {fourk_text}；不代表长片或峰值 RSS 验收 | [4K 收据](docs/validation/evidence/float-keyer-20261023-lab/4k-r3/verification.json) |
| MR111-06 | 分项历史及未执行回归 | V103 全量实际 2,537 项/1 失败/1 错误；后续旧完整回归未启动，均不补登记通过 | [保留来源](docs/validation/evidence/pipeline-recovery-20261023/lineage-r1.json) · [分项与限制](docs/validation/浮点调色抠像合并验收与诊断恢复_2026-10-23.md) |

[当前输入 MP4](docs/assets/float-keyer-20261023-recovery-source-r2/original.mp4) · [输出 MP4](docs/assets/float-keyer-20261023-recovery-source-r2/edited.mp4) · [作者契约及失败口径](docs/specs/浮点调色抠像合并交付与诊断恢复契约_v0.1_2026-10-23.md)。以下为程序生成的实际选定帧，不能替代自然人物、HDR、连续播放或听音验收。

![当前 CLI 原片与输出](docs/assets/float-keyer-20261023-recovery-source-r2/comparison.gif)

<!-- /{MARKER} -->
'''
    root_text=(MAIN/'README.md').read_text('utf8');assert MARKER not in root_text
    title,rest=root_text.split('\n',1)
    generated={'README.md':title+'\n\n'+section+'\n'+rest,CONTRACT:(ROOT/CONTRACT).read_text('utf8')}
    report=f'''# 浮点调色抠像合并验收与诊断恢复

本页覆盖最终共同 Float32 候选及诊断恢复，基线为已发布 V102 与 R17 研究提交 `f3c81ab`。所有历史原生方法、素材、安装和失败收据各自绑定执行时 SHA；不将分项数量相加当成完整通过数。[合并交付契约](../specs/{Path(CONTRACT).name})。

| 编号 | 当前快照核验 | 实际状态 |
|---|---|---|
| MR111-01 | 准备诊断、取消、布局证据嵌入及真实无限帧清理 | {source} |
| MR111-02 | 八个离线轮包、197 资源、931 NumPy 文件与许可；安装态方法 | {install} |
| MR111-03 | 330 产品输入、2,897 项最终完整回归及八项媒体/字体夹具 | {full} |
| MR111-04 | 同一源码 CLI 的实际原片/输出/PCM/PNG16 | {media_text} |
| MR111-05 | 同一源码 CLI 的实际默认预算 4K | {fourk_text} |

## 历史功能和证据

'''
    lineage=read(REL/'lineage-r1.json')
    old_reports=sorted(name for name in lineage['artifacts'] if name.startswith('docs/validation/')
                       and name.count('/')==2 and name.endswith('.md'))
    assert len(old_reports)>=8,len(old_reports)
    for index,name in enumerate(old_reports,1):
        report+=f"{index}. [{Path(name).stem}]({Path(name).name})：原始分项结果，使用各自冻结收据；不是最终组合重跑。\n"
    report+='''
## 失败与修复

原始 V103 的 2,537 项完整回归有 1 失败/1 错误。受控复现确认了两种不同情况：准备工作先耗尽总期限且未创建 HTML 失败报告；模拟抠像 worker 在 NumPy 导入之后才写取消请求，可能晚于总期限。本轮保留生产总期限，修复准备阶段的诊断，并使用真实 worker 启动事件控制测试中的取消时点。

第一轮恢复验证因新增测试缩进错误未执行方法，已保留原始执行副本。第二轮实际 156 项、0 失败/1 错误/0 跳过，又发现成功布局报告会被事务回滚删除。最终方案把布局成功事实及原始 SHA 嵌入被保留的失败报告，清楚标示渲染进程尚未启动；不伪造浏览器已启动或把成功布局标成失败。

[原始两类复现](evidence/pipeline-recovery-20261023/reproduction-r1/verification.json) · [第二轮原始日志](evidence/pipeline-recovery-20261023/native-r2/unittest.log) · [最终针对性复验](evidence/pipeline-recovery-20261023/native-r3/verification.json)。未启动的旧 V104–R109 完整回归继续登记为未执行。 本轮第一次完整回归的原生进程中途消失，没有终结结果；原状态和部分日志保存在[中断记录](evidence/pipeline-recovery-20261023/execution-interruption-r1/verification.json)。其通过数未知，不登记为成功；使用同一产品输入另开完整回归，不重跑已有安装成功证明。

## 原片和范围

[当前原片](../assets/float-keyer-20261023-recovery-source-r2/original.native.mkv) · [输入 MP4](../assets/float-keyer-20261023-recovery-source-r2/original.mp4) · [输出 MP4](../assets/float-keyer-20261023-recovery-source-r2/edited.mp4) · [实际工程](../assets/float-keyer-20261023-recovery-source-r2/author-project.json) · [版权账](../assets/float-keyer-20261023-recovery-source-r2/rights-ledger.json)。素材为原创 CC0 合成图和正弦音频。R110 的十幅静态图曾实际查看；本页当前组合结果依靠新的像素/音频核验，未登记连续播放或听音通过。

![当前选定帧对照](../assets/float-keyer-20261023-recovery-source-r2/comparison.gif)

全部为原生 Windows、本地文件和固定依赖，没有 Docker、WSL、虚拟环境或云模型。HTML 测试只启动所属 headless Chromium，结束清理全部自有后代；没有交互浏览器 tab。自然人物/头发质量、HDR、长片、实时性能、峰值 RSS、完整开放素材和模板库及剪映全部功能和观感等价仍未完成。默认后端迁移继续单独保留为开发目标。
'''
    generated[REPORT]=report
    common_summary=f"\n<!-- {MARKER} -->\nR111 最终共同浮点调色/模糊/锐化/抠像与 HTML 准备诊断：源码 {source}；离线安装 {install}；完整 {full}。旧 V103 2,537 项失败及未执行的中间全量保留，不以分项累加为完成率。自然素材、HDR、长片与剪映全部等价仍未验收。\n"
    for name in [*COMMON,'docs/README.md']:
        text=(MAIN/name).read_text('utf8');assert MARKER not in text
        title,rest=text.split('\n',1)
        reference=Path(os.path.relpath(REPORT,Path(name).parent)).as_posix()
        generated[name]=title+'\n'+common_summary+f'[编号证据、原片与限制]({reference})。\n<!-- /{MARKER} -->\n'+rest
    attributes=(MAIN/'.gitattributes').read_text('utf8')
    assert '# R111 final snapshot' not in attributes
    generated['.gitattributes']=attributes.rstrip()+'''\n\n# R111 final snapshot: preserve source, native failures, raw media and drivers.
product/** -text whitespace=cr-at-eol
docs/specs/agent-project.schema.json -text whitespace=cr-at-eol
scripts/* -text whitespace=cr-at-eol
docs/validation/evidence/float-*/** -text -whitespace
docs/validation/evidence/pipeline-recovery-20261023/** -text -whitespace
docs/assets/float-*/** -text -whitespace
'''
    for name,text in generated.items():
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding='utf8',newline='\n')
    return list(generated)


def check_links(destination,names):
    rows=[]
    for name in names:
        if not name.endswith('.md'):continue
        source=destination/name if (destination/name).exists() else ROOT/name
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',source.read_text('utf8')):
            if link.startswith(('https:','http:','app:','codex:','#')):continue
            path=Path(os.path.abspath((destination/name).parent/unquote(link.split('#',1)[0].strip('<>'))))
            relative=path.relative_to(destination)
            assert any((base/relative).exists() for base in (destination,ROOT,MAIN)),(name,link)
            rows.append({'document':name,'target':relative.as_posix()})
    return rows
