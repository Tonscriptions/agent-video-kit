"""Publish a concise research-only R13 entry without rewriting historical claims."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
REPORT = 'OpenFilm_0.2.4复用复核与成本更新_2026-10-21.md'
EVIDENCE = 'validation/evidence/openfilm-024-20261021-r13'


def prepend(path, block):
    data = path.read_bytes()
    marker = b'<!-- R13-CURRENT -->'
    assert marker not in data, str(path)
    newline = b'\r\n' if b'\r\n' in data else b'\n'
    title, rest = data.split(newline, 1)
    encoded = block.strip().replace('\n', newline.decode()).encode('utf8')
    path.write_bytes(title + newline * 2 + encoded + newline * 2 + rest.lstrip(b'\r\n'))


def main():
    r = json.loads((ROOT / 'docs' / EVIDENCE / 'run-r1/verification.json').read_text(encoding='utf8'))
    assert r['status'] == 'passed_research_only' and r['original_upstream_test_methods'] == 65
    assert r['frozen_equal'] and len(r['frozen_before']) == 235
    block = '''<!-- R13-CURRENT -->
2026-10-21 **R13（OpenFilm 0.2.4 固定源码复用检查；产品保持 V78）**：固定 `53156ac5818d8bad3f2c356043b376b3eebd95ba`；1546 stars/154 forks（00:31:16 Asia/Taipei）。对照 0.2.3，781 文件中756不变、25修改、0新增/删除；7份原始纯函数测试 **65/65，0跳过**，不与既有产品回归累计。发现新版撤掉服务端按速度预编码，改用浏览器保调播放；该路径不作为纯 CLI 音频内核。新增可借鉴的 `fitImages` 图片上下文裁剪，组件字段及基础NLE交换仍为优先候选；已有HTML、字幕、模板与V78内容缓存保持现有实现。[完整编号清单、源码与限定人日](docs/REPORT)。

| 编号 | 本轮核验 / 实际发现 | 结果与边界 | 证据 |
|---|---|---|---|
| R13-01 | 固定源码及发行区别 | main/package为0.2.4；采集时GitHub latest release为v0.2.2；保留HTTP日期、响应及ZIP SHA | [获取收据](docs/EVIDENCE/acquisition-r1/verification.json) |
| R13-02 | 完整源码 / 许可 | 781文件比较；7份MIT/商标/第三方说明不变；16候选中13不变、3修改 | [全树与逐模块摘要](docs/EVIDENCE/run-r1/verification.json) |
| R13-03 | 上游原始纯函数 | 文档30、帧率1、组件3、模板9、撤销3、播放规则6、配置13，共65/65、0跳过；未构造播放器或运行SDK | [命令和原始输出](docs/EVIDENCE/run-r1/verification.json) |
| R13-04 | 音频接入建议修正 | 新版soundOf不再按速度生成音频；浏览器preservesPitch不替代离线PCM/保调验收 | [差异原文](docs/EVIDENCE/run-r1/source.diff) |
| R13-05 | 降本候选 | 组件字段原型1–2/生产化3–5人日；新基础NLE适配3–6/8–15；图片上下文裁剪0.5–1/2–4；均为规划估计 | [范围与取舍](docs/REPORT) |
| R13-06 | Skill / providers | 10套/31个Skill文件、29个provider文件均不变；0新增安装；不导入云执行链 | [逐组比较](docs/EVIDENCE/run-r1/verification.json) |
| R13-07 | 当前产品完整性 | 获取与研究各235产品输入前后相同；与V78全量冻结输入一致；本轮0新增产品方法/模型执行/成片 | [研究收据](docs/EVIDENCE/run-r1/verification.json) |

本轮没有新MP4/GIF；已有采用结果见[HTML原片与透明合成](docs/validation/离线HTML动效源码与透明合成实测_2026-10-18.md)、[模板覆盖恢复](docs/validation/离线HTML模板控件与覆盖恢复实测_2026-10-18.md)、[V78帧/区间预览](docs/validation/时间线帧区间预览与离线发行实测_2026-10-20.md)。65项仅是源码纯函数测试，不证明完整上游渲染、自然质量或剪映全部功能效果等价。
<!-- /R13-CURRENT -->'''.replace('docs/REPORT', 'docs/' + REPORT).replace('docs/EVIDENCE', 'docs/' + EVIDENCE)
    prepend(ROOT / 'README.md', block)
    for name, report_path in (
        ('docs/OpenFilm当前复用决策_2026-10-18.md', REPORT),
        ('docs/OpenFilm最新复用评估与成本取舍_2026-10-20.md', REPORT),
        ('docs/产品需求与开发路线基线_2026-10-12.md', REPORT),
        ('docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md', '../' + REPORT),
        ('docs/specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md', '../' + REPORT),
    ):
        note = ('<!-- R13-CURRENT -->\n'
                '2026-10-21 R13 后续：固定 OpenFilm `53156ac5` /package 0.2.4；781文件中756不变、25修改。'
                '7份原始纯函数测试65/65、0跳过，235产品输入未变；研究不增加产品能力验收。'
                '新版撤掉服务端按速度音频缓存，改为浏览器播放；纯CLI继续现有本地音频处理。'
                '优先候选为组件字段（CP-01..06仍待实现）、限定基础NLE适配及本地Agent图片上下文裁剪；'
                '帧/区间内容缓存已在V78限定实现，完整剪映功能与效果目标保持不变。'
                f'[本轮模块、成本、实际执行与历史采用边界]({report_path})。\n'
                '<!-- /R13-CURRENT -->')
        prepend(ROOT / name, note)
    print('Updated README and 5 related documents with research-only R13 entries')


if __name__ == '__main__':
    main()
