"""Publish V51 documentation only from completed frozen verification receipts."""
import json
from pathlib import Path
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]

def main():
    evidence=ROOT/'docs/validation/evidence'
    full=json.loads((evidence/'nested-freeze-tests-20261018/full-2.json').read_bytes())
    install=json.loads((evidence/'nested-freeze-native-install-final-20261018/verification.json').read_bytes())
    skills=json.loads((evidence/'nested-freeze-skills-final-20261018.json').read_bytes())
    smoke=json.loads((ROOT/'docs/assets/nested-freeze-v51-final-20261018/verification.json').read_bytes())
    assert full.get('terminal_ok') and full['exit_code']==0 and full['methods']==1161 and full['skipped']==0
    assert full['frozen_before']==full['frozen_after']==smoke['frozen_before']==frozen() and len(frozen())==172
    assert install['status']=='passed' and install['installed_package_files']==117 and install['isolated_cli_calls']==9
    assert smoke['status']=='core_passed_delivery_alpha_failed' and not smoke['all_delivery_gates_passed']
    assert skills['skill_count']==14 and skills['local_links_checked']==182
    seconds=f"{full['suite_seconds']:.3f}"
    report='复合片段定格与完整音画时钟实测_2026-10-18.md'
    contract='复合片段定格与完整音画时钟契约_v0.1_2026-10-18.md'
    files=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
        'docs/产品需求与开发路线基线_2026-10-12.md','docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md',
        'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
    for name in files:
        p=ROOT/name;t=p.read_text(encoding='utf-8-sig');assert '**V51（产品）**' not in t,name
        prefix='docs/' if name=='README.md' else ('' if name.startswith('docs/validation/') else 'validation/')
        summary=(f'2026-10-18 **V51（产品）**：复合片段先完成完整子画面/字幕/动画/转场与子音频总线，再统一定格；父动画继续。完整 **1161/1161，{seconds} 秒**，0 跳过，**172 文件**冻结；26 新增专项为全量子集，相同测试在固定 V50 上 22 失败/4 控制通过。'
            '九组 **30 CLI /327 主帧 /1,567,101 立体声采样帧**；曲线音频只验长度/有限性。**117 包内文件 /9 隔离 CLI /80 新安装帧**与开发版 RGB/PCM 一致；**14 Skills /182 引用**通过。'
            '**正式 VP9 精确 alpha 失败：326,400 像素最大差 1（128→129）**；另 3 CLI/41 帧门禁诊断中，10 fps /4.01 秒 MP4 被现有 80 ms AV 门禁拒绝。无损图精确不能替代交付通过。四时刻静帧、未连续播放/听审，0 新模型前向；自然声音/AI、长片/HDR与完整剪映等价仍未验收。 '
            f'[原片/GIF/安装包与失败]({prefix+report if prefix!="docs/" else "docs/validation/"+report})。')
        head,rest=t.split('\n',1)
        rest=rest.replace('2026-10-18 **V50（研究）**','历史研究 2026-10-18 **V50（研究）**',1)
        rest=rest.replace('2026-10-18 **V49（产品）**','历史产品 2026-10-18 **V49（产品）**',1)
        t=head+'\n\n'+summary+'\n\n'+rest.lstrip('\n')
        t=t.replace('历史产品 历史产品','历史产品').replace('历史研究 历史研究','历史研究')
        if name=='README.md':
            lines=t.splitlines();out=[]
            for line in lines:
                if line.startswith('| V13 |'):
                    line=f'| V13 | 产品自动回归 | 最近 V51 完整 **1161/1161**、{seconds} 秒、0 跳过；172 文件冻结，26 新增专项为完整子集 | 开发/安装/反事实与历史分计；VP9 精确 alpha 及自然质量仍失败/未验，完整剪映未验 | [完整日志](docs/validation/evidence/nested-freeze-tests-20261018/full-2.log)、[冻结终态](docs/validation/evidence/nested-freeze-tests-20261018/full-2.json) |'
                if line.startswith('- 当前模块进度见'):
                    line=f'- 当前模块进度见[构建进度总表](docs/构建进度总表_2026-10-16.md)：最近产品 V51 完整 **1161/1161**、0 跳过、172 文件冻结；完整复合定格与本机隔离安装已受控验证。正式 VP9 精确 alpha 仍失败，10 fps /4.01 秒 MP4 仍被 AV 门禁拒绝；CTC 声学边界、FGT 自然修复、声音/听审、另一台机器、长片/HDR、内容库及完整剪映等价仍未验收。'
                out.append(line)
                if line.startswith('| V50 |'):
                    out.append(f'| V51 | 完整复合片段定格与音画时钟 | 26 新增专项/完整 1161；30 CLI、327 主帧/156.7101 万采样帧；另 3 CLI/41 帧门禁诊断；117 包内文件/9 隔离 CLI/80 帧；14 Skills/182 引用 | 内核图 alpha 精确；正式 VP9 差 1 仍失败；10 fps /4.01 秒 MP4 被 AV 门禁拒绝；曲线音频、自然布局/听审及完整剪映未验 | [原片/GIF/失败/安装包](docs/validation/{report})、[完整回归](docs/validation/evidence/nested-freeze-tests-20261018/full-2.json) |')
            t='\n'.join(out)+'\n'
            marker='## 实测演示素材\n'
            demo=('\nV51 实际 CLI 输出：子运镜和字幕随复合片段暂停，父透明度继续。诊断文字与原片计数叠置，自然广告排版未验；仅四时刻静态目检，未连续播放/听审。'
                f' [原 A](docs/assets/nested-freeze-v51-final-20261018/source-a.mp4)、[原 B](docs/assets/nested-freeze-v51-final-20261018/source-b.mp4)、[实际 MP4](docs/assets/nested-freeze-v51-final-20261018/NF06.mp4)、[全部样例/透明编码失败](docs/validation/{report})。\n\n'
                '![V51 复合定格实际成片](docs/assets/nested-freeze-v51-final-20261018/NF06.gif)\n')
            assert marker in t;t=t.replace(marker,marker+demo,1)
        if '构建进度总表' in name:
            t=t.replace('祖先定格拒绝','V51 祖先定格受控支持；正式 VP9 精确 alpha 失败')
        if '能力覆盖与验收矩阵' in name:
            t=t.replace('深层 freeze/VFR','V51 复合定格已受控验证；VFR')
            t=t.replace('端点/祖先定格等限制见下一行','端点限制仍保留；V51 祖先定格见复合定格行')
            t=t.replace('祖先定格及端点限制保留','V51 祖先定格已扩展，端点限制保留')
            marker='| CTC 字词强制对齐（V49） |';assert marker in t
            row=f'| 完整复合片段定格（V51） | 子画面/字幕/子动画/转场/子总线先合成，再取窗/变速/倒放/定格；父动画继续，无中间媒体 | [26 专项/1161 完整、九组实测及独立安装](./{report})；327 主帧，曲线音频只验长度 | 内核 alpha 精确；正式 VP9 128→129、326,400 像素失败；10 fps /4.01 秒 MP4 被 AV 门禁拒绝；自然音频/布局、长片/VFR/HDR及整体等价仍未验 |\n'
            t=t.replace(marker,row+marker,1)
        if '产品实现入口' in name:
            t+=('\n## V51 复合片段定格入口\n\n'
                '对已建立的 `sequence_id` 容器使用现有 `timeline compose`；请求示例（ticks_per_second=90000）：\n\n'
                '```json\n{"operations":[{"op":"freeze_frame","clip_id":"container","at_tick":90000,"duration_tick":90000,"audio_mode":"silence"}]}\n```\n\n'
                f'先 `--dry-run` 核对，再按正常快照/幂等流程应用。子画面与子总线暂停，父动画继续；原作者工程保留。见 [契约](specs/{contract}) 与 [实测/透明交付失败](validation/{report})。\n')
        p.write_text(t,encoding='utf-8',newline='\n')
    p=ROOT/'docs/validation'/report;t=p.read_text(encoding='utf-8')
    t=t.replace('V51_FULL_SUITE_PENDING',f'**1161/1161，{seconds} 秒，0 跳过**；172 文件前后字节冻结')
    p.write_text(t,encoding='utf-8',newline='\n')
    print(json.dumps({'updated_documents':8,'full_methods':1161,'suite_seconds':full['suite_seconds'],'remaining_complete_parity':False}))

if __name__=='__main__':main()
