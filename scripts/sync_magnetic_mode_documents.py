"""Synchronize V56 documentation with the actual frozen receipts; retain history."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/magnetic-mode-20261018-v56'
REPORT='主轨磁吸模式与跨剪口同步拆分实测_2026-10-18.md'
CONTRACT='主轨磁吸模式与跨剪口同步拆分契约_v0.1_2026-10-18.md'
PUBLIC='magnetic-mode-final-20261018-v56'
DOCS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
      'docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
      'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
      'docs/产品需求与开发路线基线_2026-10-12.md',
      'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
      'docs/validation/README功能核验与实测演示_2026-10-16.md']


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def replace_line(text,prefix,value):
    assert sum(s.startswith(prefix) for s in text.splitlines())==1,prefix
    return '\n'.join(value if s.startswith(prefix) else s for s in text.splitlines())+'\n'


def run(final):
    current=frozen();integration=read(EVIDENCE/'magnetic-integration-final.json')
    full=read(EVIDENCE/'full-final.json');smoke=read(ROOT/f'docs/assets/{PUBLIC}/verification.json')
    native=read(ROOT/'docs/validation/evidence/magnetic-mode-native-final-20261018-v56/verification.json')
    skills=read(EVIDENCE/'skills.json')
    assert len(current)==181
    for record in (integration,smoke,native):assert record['frozen_before']==record['frozen_after']==current
    assert integration['terminal_ok'] and integration['methods']==66 and integration['skipped']==0
    assert skills['skill_count']==14 and skills['local_links_checked']==198
    assert smoke['main_frames']==236 and native['installed_package_files']==121
    assert full['frozen_before']==current
    if final:
        assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0
        assert full['frozen_after']==current and full['methods']==1289
        complete=f"完整 **1289/1289，{full['suite_seconds']:.3f} 秒**、0 跳过、**181 文件**冻结"
        complete_plain=f"1289/1289、{full['suite_seconds']:.3f} 秒、0 跳过、181 文件冻结"
    else:
        assert not full.get('terminal_ok')
        complete='最终完整回归运行中，181 文件冻结；最近已发布 V55 1263/1263 为历史结果'
        complete_plain='完整回归运行中，181 文件冻结（历史 V55 1263/1263）'
    for name in DOCS:
        path=ROOT/name;text=path.read_text(encoding='utf-8-sig')
        report=('docs/validation/' if name=='README.md' else '' if name.startswith('docs/validation/') else '../validation/' if name.startswith('docs/specs/') else 'validation/')+REPORT
        contract=('docs/specs/' if name=='README.md' else '../specs/' if name.startswith('docs/validation/') else '' if name.startswith('docs/specs/') else 'specs/')+CONTRACT
        summary=('2026-10-18 **V56（产品）**：持久主轨磁吸、剪口吸附及 append/remove/shift/trim 联动，'
            '跨不同位移剪口的连续音频/字幕/嵌套输出自动分段。'+complete+
            ('；66 磁吸专项含 26 新增与 40 旧重排，为完整子集。' if final else
             '；66 磁吸专项含 26 新增与 40 旧重排，完整终态另行记录。')+
            '**44 CLI /236 主帧 /1,132,800 立体声采样帧**，RGB 最大差 1、PCM 0；'
            '**121 包内文件 /39 隔离 CLI /316 安装帧 /1,516,800 采样帧**，开发版与安装版解码一致；'
            '**14 Skills /198 引用**通过。局部片段组真实失败与旧回归中断保留；'
            '复杂音频/字形参考使用同版完整作者图，独立原源参考另计。'
            '未连续播放/听审；速度/曲线/定格长度自动随动、全手势、自然质量、长片/HDR、另一台机器及完整剪映等价未验收。'
            f'[契约]({contract})、[原输入/MP4/GIF/失败/发行]({report})。')
        if any(s.startswith('2026-10-18 **V56（产品）**') for s in text.splitlines()):
            text=replace_line(text,'2026-10-18 **V56（产品）**',summary)
        else:
            head,rest=text.split('\n',1)
            rest=rest.replace('2026-10-18 **V55（产品）**','历史产品 2026-10-18 **V55（产品）**',1)
            text=head+'\n\n'+summary+'\n\n'+rest.lstrip('\n')
        if name=='README.md':
            text=replace_line(text,'| V13 |',f'| V13 | 产品自动回归 | 最近 V56 {complete_plain}；66 磁吸集成含 26 新增 | 开发/安装/研究与历史分计；全手势/自然质量/完整剪映仍开放 | [完整日志](docs/validation/evidence/magnetic-mode-20261018-v56/full-final.log)、[冻结终态](docs/validation/evidence/magnetic-mode-20261018-v56/full-final.json) |')
            row=(f'| V56 | 持久主轨磁吸与跨剪口同步拆分 | 66 集成含 26 新增；{complete_plain}；44 CLI/236 主帧/1,132,800 采样帧，RGB 1/PCM 0；121 文件/39 隔离 CLI/316 安装帧；14 Skills/198 引用 | 原帧/PCM 独立参考与复杂作者图参考分计；片段组失败和旧回归中断保留；未连续播放/听审，全手势及完整等价未验 | [契约]({contract})、[原输入/成片/GIF/片段组/发行与失败]({report}) |')
            if '| V56 |' in text:text=replace_line(text,'| V56 |',row)
            else:
                lines=text.splitlines();i=next(i for i,s in enumerate(lines) if s.startswith('| V55 |'));lines.insert(i+1,row);text='\n'.join(lines)+'\n'
            demo=('**V56 实际磁吸演示**：C 移到头部后，连续副音轨随 C/A/B/D 自动分段；GIF 来自真实输出且无声音。'
                f'[原 MKV](docs/assets/{PUBLIC}/source.mkv)、[原输入 MP4](docs/assets/{PUBLIC}/source-preview.mp4)、'
                f'[原 WAV](docs/assets/{PUBLIC}/source.wav)、[实际 MP4](docs/assets/{PUBLIC}/MM01.mp4)、'
                f'[六组/失败/安装记录]({report})。\n\n'
                f'![V56 实际主轨磁吸输出](docs/assets/{PUBLIC}/magnetic-mode.gif)\n\n')
            if '**V56 实际磁吸演示**' not in text:text=text.replace('**V55 实际音频路由演示**',demo+'**V55 实际音频路由演示**',1)
            text=replace_line(text,'- 当前模块进度见',f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近 V56 {complete_plain}；持久磁吸与连续副轨自动分段已受控实现，原输入/复杂作者图参考分计。速度/曲线/定格长度自动跟随、全手势、CTC 精度、自然修复/声音、长片/HDR、另一台机器、内容库及完整剪映等价继续开放。')
        if name=='docs/构建进度总表_2026-10-16.md':
            rows={
                '| 本次状态快照 |':f'| 本次状态快照 | 2026-10-18，README V56；{complete_plain}；66 集成含 26 新增；原始失败保留 |',
                '| 最近产品增量 |':'| 最近产品增量 | V56 持久磁吸/整数剪口/主轨插删裁切/跨剪口音频字幕和嵌套自动分段；片段组完整选择闭包；V55 命名路由保留 |',
                '| 研究状态与历史快照 |':'| 研究状态与历史快照 | OpenFilm R04 固定 main 5c2000b8、713 文件比较，914 stars/95 forks 为 API 时点；已采用模块去重；V56 无新模型前向，完整剪映仍开放 |',
                '| 核对范围 |':f'| 核对范围 | V56 {complete_plain}；44 当前 CLI/236 主帧/1,132,800 采样帧；121 文件/39 隔离 CLI/316 安装帧/1,516,800 采样帧；独立原源与同版作者图参考分计 |',
                '| 06 |':'| 06 | 时间线与基础剪辑 | 已实现，有边界 | V56 持久磁吸、最近剪口和主轨插删裁切；不同位移同步片段自动分段/共享关联分区；V53 重排、作者窗、范围/源编辑保持 | 速度/曲线/定格长度自动跟随、全手势/屏幕吸附仍待实现；全局自动化/跟踪重规划/自然/VFR/HDR/长片未验 |',
                '| 24 |':'| 24 | Agent Skills | 已实现，持续扩展 | 14 个 video-cut- Skill；磁吸模式/sync_span_policy/片段组闭包及实际失败边界同步；14 项格式/联接/SHA 与 198 引用通过 | 实际内容和自然质量持续验收，技能数不代表覆盖率 |',
                '| 25 |':f'| 25 | 质量、性能与发行 | 本机隔离发行已核验，整体未完成 | V56 {complete_plain}；121 包内文件/七个本地 wheel/39 隔离 CLI/316 安装帧；与开发版 RGB/PCM 一致 | 两张实际静态合成图已查看，无连续播放/听审；其他机器/平台、自然对齐/AI/声音、长片/HDR 与完整剪映待验 |',
                '| 当前生产代码 |':'| 当前生产代码 | 产品/测试/Schema/发行输入共 181 文件；66 集成/公开媒体/安装前后冻结一致，完整终态单列 | 原始失败和旧轮记录保留；181 不是纯运行时数，发行包内为 121 |',
                '| 最近完整产品回归 |':f'| 最近完整产品回归 | V56 {complete_plain} | [完整日志](validation/evidence/magnetic-mode-20261018-v56/full-final.log)；耗时不是性能基准 |',
                '| 最近产品新增子集 |':'| 最近产品新增子集 | V56 新增 26 方法；66 磁吸集成包含既有 40 重排 | 全量通过后为完整子集，研究/安装与历史不相加 |',
                '| 最近产品实际核验 |':f'| 最近产品实际核验 | V56 44 CLI/236 主帧/1,132,800 采样帧，另 39 隔离 CLI/316 安装帧/1,516,800 采样帧 | [原输入/成片/GIF/失败/发行]({report})；独立原源与同版复杂作者参考分计，无连续播放/听审 |',
                '| Skill 审计 |':'| Skill 审计 | 14 Skills、198 引用，目录联接/格式/SHA 通过 | [本轮记录](validation/evidence/magnetic-mode-20261018-v56/skills.json)；引用检查不证明自然质量 |',
                '| 文档 |':'| 文档 | README/进度/契约/矩阵/基线/原片 GIF 同步，修正旧当前状态行 | [当前审计](validation/evidence/magnetic-mode-20261018-v56/release.json)；不证明外链、锚点、自然质量或许可 |'}
            for prefix,value in rows.items():text=replace_line(text,prefix,value)
            text=replace_line(text,'“已实现”表示',f'“已实现”表示列出的实现和验证，不表示完整剪映等价。当前 V56 {complete_plain}；上游研究、原媒体和安装计数分别记录，自然质量/来源链及 CTC/声音缺口继续保留。')
        if name.startswith('docs/validation/能力覆盖'):
            row=(f'| 持久磁吸与同步分段（V56） | 模式开关、最近原剪口、主轨插删移裁、不同位移的音频/字幕/嵌套作者窗、关联分区、全片段组闭包 | [66 集成/26 新增、六组与原生安装]({report})；{complete_plain}，236 主帧/1,132,800 采样帧，RGB 1/PCM 0 | 速度/曲线/定格长度自动跟随、全手势/屏幕吸附、全局自动化、跟踪重规划/自然质量/长片未验；转场端点等拒绝自动分段 |')
            if '| 持久磁吸与同步分段（V56） |' in text:text=replace_line(text,'| 持久磁吸与同步分段（V56） |',row)
            else:text=text.replace('| 命名音频路由（V55） |',row+'\n| 命名音频路由（V55） |',1)
            text=replace_line(text,'| 主轨整片段重排（V53） |',f'| 主轨整片段重排（V53） | 稳定多选插入块、全主轨闭隙、关联配音/sync/rider、字幕补偿、轨道引用和转场策略 | [V53 历史 40 专项/1223 完整、媒体及安装](./主轨磁吸重排与关联附着实测_2026-10-18.md)；独立原 PCM 和作者块参考分计 | V56 已补持久模式和不同位移跨剪口分段，见上行；屏幕吸附/全拖拽、全局总线新时钟、自然质量/听审/长片仍未验 |')
        path.write_text(text,encoding='utf-8',newline='\n')
    report_path=ROOT/'docs/validation'/REPORT;text=report_path.read_text(encoding='utf-8')
    if final:
        text=replace_line(text,'| CHECK-02 |',f"| CHECK-02 | 最终完整产品回归 | **1289/1289、{full['suite_seconds']:.3f} 秒、0 跳过**；181 文件前后冻结一致。[终态](evidence/magnetic-mode-20261018-v56/full-final.json)、[日志](evidence/magnetic-mode-20261018-v56/full-final.log)。66 集成/26 新增为全量子集，历史及安装不相加 |")
    text=replace_line(text,'| CHECK-06 |','| CHECK-06 | Skills 与发行绑定 | **14 Skills /198 本地引用**及目录联接/格式/SHA 通过。[技能记录](evidence/magnetic-mode-20261018-v56/skills.json)；[最终发行审计](evidence/magnetic-mode-20261018-v56/release.json)绑定全量终态后发布，不将安装调用、研究或历史测试相加 |')
    report_path.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'documents':len(DOCS)+1,'final':final,'full_methods':full.get('methods'),'skill_links':198}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--final',action='store_true');a=p.parse_args();run(a.final)
