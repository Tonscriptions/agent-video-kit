"""Publish V47 documentation only from a completed, frozen native regression."""
from __future__ import annotations
import argparse,hashlib,json,os,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def write(path,text):path.write_text(text,encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def run(full_path):
    full=json.loads(full_path.read_bytes());log=full_path.with_suffix('.log')
    assert full['exit_code']==0 and full['terminal_ok'] and full['skipped']==0 and full['frozen_equal']
    assert full['frozen_before']==full['frozen_after'] and full['log_sha256']==sha(log)
    assert all(sha(ROOT/name)==digest for name,digest in full['frozen_after'].items())
    assert full['methods']==1084 and len(full['frozen_after'])==160
    real=json.loads((ROOT/'docs/validation/evidence/offline-release-final-real-20261018/verification.json').read_bytes())
    assert real['frozen_before']==full['frozen_after'] and real['status']=='passed' and real['nonperiodic_audio_distinguishes_slip']
    target=ROOT/'docs/validation/evidence/offline-release-tests-20261018'
    for name,data in [('full.json',full_path.read_bytes()),('full.log',log.read_bytes())]:
        path=target/name;assert not path.exists();path.write_bytes(data)
    n,seconds,files=full['methods'],full['suite_seconds'],len(full['frozen_after'])
    report=ROOT/'docs/validation/离线发行与随包Schema实测_2026-10-18.md';text=report.read_text(encoding='utf-8')
    artifact=real['public_files']['agent-video-kit-cp313-win_amd64.zip']
    text=text.replace('@@ZIP_BYTES@@',f"{artifact['bytes']:,}").replace('@@ZIP_SHA@@',artifact['sha256']).replace('@@MANIFEST_SHA@@',real['bundle']['manifest_sha256'])
    text=text.replace('状态：V47 发行/功能专项已通过，完整回归仍在运行，终态未发布前不宣称全量通过。',f'状态：V47 所列本机离线发行与功能核验通过。完整 **{n}/{n}，{seconds} 秒**，0 跳过；{files} 文件（含测试、随包资源、原生构建/安装代码）前后冻结。')
    text=text.replace('| SR09 | 完整产品回归 | 等待本轮冻结终态，不能用历史 1051 代替 |',f'| SR09 | 完整产品回归 | **{n}/{n}，{seconds} 秒**；{files} 文件前后冻结、0 跳过。[终态](evidence/offline-release-tests-20261018/full.json)、[日志](evidence/offline-release-tests-20261018/full.log) |')
    write(report,text)
    core=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    def relative(document,path):return Path(os.path.relpath(ROOT/path,document.parent)).as_posix()
    for name in core:
        path=ROOT/name;text=path.read_text(encoding='utf-8-sig');assert '**V47（产品）**' not in text
        def link(label,target):return '['+label+']('+relative(path,target)+')'
        summary=(f'2026-10-18 **V47（产品）**：固定 Schema 随 wheel 分发，声明本地校验依赖及显式日期检查，缺资源/执行器或摘要不符拒绝成功降级；新增 `schema show/export` 和原生 Windows CPython 3.13 x64 离线安装入口。完整 **{n}/{n}，{seconds} 秒**，0 跳过，**{files} 文件（含测试/发行代码）**冻结；33 新增专项为全量子集。实际安装 **108 包内文件 / 22 隔离 CLI**，关联音画源滑移与工程包往返共 90 新帧、432,000 立体声采样帧；独立源帧身份一致、RGB 最大差 1、PCM 差 0，重建 RGB/PCM 一致。**14 Skills /162 引用**通过，日期夹具层级失败和周期音频弱观察保留。三时刻静帧，未连续播放/听审，0 新模型推理；本机独立安装及 Schema 随包已验，其他机器/平台、自然 AI/声音、复杂 HTML、长片/HDR、内容库及完整剪映功能/效果仍未验收。 '+link('契约','docs/specs/离线发行与随包Schema契约_v0.1_2026-10-18.md')+'、'+link('发行包/原片/GIF/实测','docs/validation/离线发行与随包Schema实测_2026-10-18.md')+'。')
        text=text.replace('2026-10-18 **V46（产品）**：','历史产品 2026-10-18 **V46（产品）**：',1)
        if name=='README.md':
            marker='## 功能核验与真实实测\n\n';assert marker in text;text=text.replace(marker,marker+summary+'\n\n',1)
        else:
            title,rest=text.split('\n',1);text=title+'\n\n'+summary+'\n'+rest
        text=text.replace('当前 README 已扩展至 V46','当前 README 已扩展至 V47')
        if name=='README.md':
            row='| V47 | 原生离线发行与随包 Schema | 108 包内文件/五个固定依赖；22 隔离 CLI、90 编码帧、432,000 立体声采样帧；独立源帧/PCM及工程包一致；完整 '+f'{n}/{n}、{files} 文件冻结；14 Skills/162 引用'+' | 日期层级负例修正及周期音频弱观察保留；三静帧，无连续播放/听审；其他机器/完整剪映等价未验 | [安装包/原片/GIF/实测](docs/validation/离线发行与随包Schema实测_2026-10-18.md)、[机器证据](docs/validation/evidence/offline-release-final-real-20261018/verification.json)、[全量](docs/validation/evidence/offline-release-tests-20261018/full.json) |'
            text,count=re.subn(r'^(\| V46 \|.*)$',lambda match:match[0]+'\n'+row,text,count=1,flags=re.M);assert count==1
            text=re.sub(r'^\| V13 \|.*$',f'| V13 | 产品自动回归 | 最近 V47 完整 **{n}/{n}**、0 跳过；{files} 文件冻结，33 新增专项为完整子集 | 22 隔离 CLI、安装流程、上游研究与历史结果分计；自然质量和完整剪映未验 | [完整日志](docs/validation/evidence/offline-release-tests-20261018/full.log)、[冻结与终态](docs/validation/evidence/offline-release-tests-20261018/full.json) |',text,count=1,flags=re.M)
            current='本次 OpenFilm 复核：**853 stars /91 forks**（请求时间见原始证据），main 仍为 `eefd6a8d`；702 原文件及五类已采用 MIT 代码复核通过。推荐复用官方参考片/录屏/长转短流程，XML 按实际互操作需求开展；未安装新上游 Skill 或新增模型内核。[编号复用决策/成本边界](docs/OpenFilm当前复用决策_2026-10-18.md)、[十份官方 Skill 的本地能力映射](docs/OpenFilm官方Skill本地能力映射_2026-10-18.md)、[配套示例的描线/文字/后处理内核](docs/OpenFilm示例与动效内核复用评估_2026-10-18.md)、[本次 API/字节证据](docs/validation/evidence/openfilm-release-review-20261018/verification.json)。配套示例仅审读目录和文本，没有下载媒体或接入新内核。V47 另补离线发行，不把它算作新 OpenFilm 算法采用。\n\n'
            assert 'V46 继续提取固定' in text;text=text.replace('V46 继续提取固定',current+'V46 继续提取固定',1)
            gallery='**V47 安装版实际剪辑**：左为源 1–4 秒，右为关联音画滑移后的 2–5 秒；各 30 帧/10 fps/3 秒，非周期立体声逐采样验证；GIF 无音频。原视频、原音频、编码结果和实测发行 ZIP均可复查。\n\n![V47 安装版剪辑前后](docs/assets/offline-release-final-20261018/comparison.gif)\n\n[原视频](docs/assets/offline-release-final-20261018/source-a.mp4) · [原音频探针](docs/assets/offline-release-final-20261018/sound-a.wav) · [实际结果](docs/assets/offline-release-final-20261018/after.mp4) · [已测试离线发行包](docs/assets/offline-release-final-20261018/agent-video-kit-cp313-win_amd64.zip) · [安装/边界/证据](docs/validation/离线发行与随包Schema实测_2026-10-18.md)\n\n'
            assert '**V46 布局诊断与修复**' in text;text=text.replace('**V46 布局诊断与修复**',gallery+'**V46 布局诊断与修复**',1)
            text=re.sub(r'^- 当前模块进度见.*$',f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近产品 V47 完整 **{n}/{n}**、0 跳过，{files} 文件冻结；Schema 随包及本机独立离线安装、实际源滑移和工程包音画重建通过。V44 FGT 仍未接入产品；另一台干净机器、自然 AI/声音/听审、复杂 HTML、长片/HDR、内容库和完整剪映等价仍未验收。',text,count=1,flags=re.M)
        if name=='docs/构建进度总表_2026-10-16.md':
            replacements={'本次状态快照':f'2026-10-18，README V47；{n} 完整/33 新增子集，{files} 文件冻结；历史失败保留','最近产品增量':'V47 随包 Schema/显式日期检查和新目录原生离线安装；五个固定依赖、实际关联源滑移与工程包音画往返','本轮研究增量':'OpenFilm main 无新增源码，853 stars/91 forks 时点、702 文件/五类采用字节复核；V44 FGT 自然画质/来源链仍未关闭','核对范围':f'完整 {n}/{n}、0 跳过；108 包内文件/22 隔离 CLI、29 主体进程、90 编码帧/432,000 立体声采样帧；非周期独立 PCM 差 0'}
            for label,value in replacements.items():text,count=re.subn(r'^\| '+re.escape(label)+r' \|.*$',f'| {label} | {value} |',text,count=1,flags=re.M);assert count==1,label
            text=re.sub(r'^\| 24 \|.*$','| 24 | Agent Skills | 已实现，持续扩展 | 14 个 video-cut- Skill；editor/project-ops/quality 增补离线发行/Schema/证据边界；14 项格式/联接/162 引用通过 | 实际内容和自然质量持续验收，技能数不代表覆盖率 |',text,count=1,flags=re.M)
            text=re.sub(r'^\| 25 \|.*$',f'| 25 | 质量、性能与发行 | 本机独立发行核验通过，其他产品验收未完成 | V47 完整 {n}/{n}、{files} 文件冻结；108 文件 wheel及五个依赖/22 隔离 CLI；90 帧/432,000 立体声采样帧与工程包一致 | Schema 随包已验；三静帧、未连续播放/听审；其他干净机器/平台、长片/HDR、自然 AI/完整剪映等价待验 |',text,count=1,flags=re.M)
            text=re.sub(r'^\| 最近完整产品回归 \|.*$',f'| 最近完整产品回归 | V47 **{n}/{n}，{seconds} 秒**，0 跳过；{files} 文件冻结 | [完整日志](validation/evidence/offline-release-tests-20261018/full.log)；耗时不是性能基准 |',text,count=1,flags=re.M)
            text=re.sub(r'^\| 最近产品新增子集 \|.*$','| 最近产品新增子集 | V47 的 33 方法，包含在本轮完整中 | 16 Schema/17 安装器；旧轮与研究计数不相加 |',text,count=1,flags=re.M)
            text=re.sub(r'^\| 最近产品实际核验 \|.*$','| 最近产品实际核验 | V47 108 包内文件/22 隔离 CLI、90 帧/432,000 立体声采样帧，工程包往返 | [原片/发行/失败](validation/离线发行与随包Schema实测_2026-10-18.md)；三静帧、未连续播放/听审 |',text,count=1,flags=re.M)
            text=re.sub(r'^“已实现”表示.*$',f'“已实现”表示列出的实现和验证，不表示完整剪映等价。最近产品 V47 为 {n}/{n}、{files} 文件冻结；上游研究与历史/实际 CLI 分计，V42/V44 的自然质量/来源链缺口继续保留。',text,count=1,flags=re.M)
        if name=='docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md':
            extra='| 离线发行与随包 Schema（V47） | 固定随包合同、显式日期/执行器、六 wheel 原生离线新目标安装；实际源滑移/工程包及完整冻结通过 | [108 包内文件/22 隔离 CLI、90 帧和非周期 PCM](./离线发行与随包Schema实测_2026-10-18.md)；33 新增方法属全量子集 | 本机不同目录已验；其他机器/ABI、升级覆盖、自然质量及完整剪映等价未验 |'
            text,count=re.subn(r'^(\| HTML 动效/模板/诊断.*)$',lambda match:match[0]+'\n'+extra,text,count=1,flags=re.M);assert count==1
        write(path,text)
    index=ROOT/'docs/README.md';text=index.read_text(encoding='utf-8')
    text+='\n## V47 发行与当前 OpenFilm 决策\n\n- [离线发行与随包 Schema 契约](./specs/离线发行与随包Schema契约_v0.1_2026-10-18.md)\n- [安装包、原片/GIF、独立音画与失败记录](./validation/离线发行与随包Schema实测_2026-10-18.md)\n- [固定 Python 依赖与日期检查器许可](./third-party/离线Python依赖与日期检查器许可说明_2026-10-18.md)\n- [OpenFilm 当前编号复用决策](./OpenFilm当前复用决策_2026-10-18.md)\n- [十份官方 Skill 的本地 CLI 与能力缺口](./OpenFilm官方Skill本地能力映射_2026-10-18.md)\n- [配套示例与描线/文字/后处理内核](./OpenFilm示例与动效内核复用评估_2026-10-18.md)\n';write(index,text)
    research=ROOT/'docs/OpenFilm_v0.2增量复用与接入建议_2026-10-18.md';text=research.read_text(encoding='utf-8')
    marker='**当前结论（V46）**';assert marker in text
    text=text.replace(marker,'本轮后续复核：main 仍为 `eefd6a8d`；**853 stars/91 forks** 是新 API 时点，702 文件与五类已采用代码再次核对。没有新增上游代码、模型推理或安装官方 Skill。见[当前编号决策表](OpenFilm当前复用决策_2026-10-18.md)及[原 API/采用字节](validation/evidence/openfilm-release-review-20261018/verification.json)。V47 仅另补本机离线发行与随包 Schema，[实际发行](validation/离线发行与随包Schema实测_2026-10-18.md)不计为新 OpenFilm 算法。\n\n**当前结论（V46 功能采用；V47 另补发行）**',1);write(research,text)
    contract=ROOT/'docs/specs/离线发行与随包Schema契约_v0.1_2026-10-18.md';text=contract.read_text(encoding='utf-8');text=text.replace('状态：V47 开发前声明。','状态：V47 开发前声明；所列本机范围已按[本轮实测](../validation/离线发行与随包Schema实测_2026-10-18.md)核验，其他机器/全部平台仍未接受。',1);write(contract,text)
    print(json.dumps({'published':'V47','methods':n,'seconds':seconds,'frozen_files':files,'core_documents':len(core)},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full',type=Path,required=True);args=p.parse_args();run(args.full.resolve())
