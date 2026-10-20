"""Publish R12 research pointers; preserve all earlier product evidence blocks."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = 'OpenFilm_0.2.3增量复用与开发成本评估_2026-10-20.md'


def insert(path, block):
    text = path.read_text(encoding='utf8')
    assert '<!-- R12-CURRENT -->' not in text
    at = text.index('\n\n') + 2
    path.write_text(text[:at] + block + '\n\n' + text[at:], encoding='utf8', newline='\n')


def main():
    report = 'docs/' + REPORT
    block = f'''<!-- R12-CURRENT -->
2026-10-20 **R12（OpenFilm 0.2.3 源码复核，产品仍为 V77）**：固定 `284f8bd3d6850ceaa773043e2ecb90e13640f547`；社区快照 **1524 stars/153 forks，22:12:10 Asia/Taipei**。757→781 文件中 **616 不变、27 新增、138 修改、3 删除**。本轮为源码研究，完整 [复用清单、成本和接入边界]({report}) 已更新；没有新增产品 CLI/成片验收或再次累计 V77 的 1746 项历史回归。

| 编号 | 实际核验 /新发现 | 结果与证据 |
|---|---|---|
| R12-01 | 全树、MIT 与 14 个候选入口 | MIT 不变；8 不变/4 修改/2 新增。[全树与命令收据](docs/validation/evidence/openfilm-023-20261020-r12/run-r1/verification.json) |
| R12-02 | 五份上游原始纯函数测试 | **46/46，0 跳过**：工程文档 30、帧率 1、组件参数 3、模板控制 9、撤销栈 3；原生 Node 类型擦除，不代表完整上游安装或渲染验收 |
| R12-03 | 缓存正确性和组件输入 | **4 组观察/8 断言**：素材 SHA 改变而大小+mtime 相同时 key 不变；组件接入仍须本地资产、变量名与匹配序号预算。[真实观察和原片段](docs/validation/evidence/openfilm-023-20261020-r12/probe-r1/verification.json) |
| R12-04 | 可复用内容与工程量 | 组件字段：原型 1–2 /生产化 3–5 人日；内容缓存：2–4 /7–12；NLE 基础导出：3–6 /8–15。均为限定范围估计，未宣称已实现或实际节省 |
| R12-05 | Skill/providers 与产品完整性 | 10 套/31 个 Skill 文件不变，**0 新安装**；29 provider 文件中 6 修改，与离线模型分开计数。两次研究的 **233 个产品输入 SHA 均未变** |

新增价值是可命名/重置的组件参数与保调音频预览；FCPXML、预览缓存和诊断核心不变。沿用本项目工程与本地执行链；不接入上游 GUI、安装器和云 provider。[未实现的接入设计](docs/specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md)。本轮没有新视频/GIF；已有原输入及实际输出见 [V70](docs/validation/OpenFilm同批次结果复用实测_2026-10-20.md)、[V71](docs/validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md)、[V72](docs/validation/HTML子帧快门与透明混合实测_2026-10-20.md)。
<!-- /R12-CURRENT -->'''
    insert(ROOT / 'README.md', block)
    compact = f'''<!-- R12-CURRENT -->
2026-10-20 **R12：OpenFilm 0.2.3 增量研究，产品仍为 V77**。固定 `284f8bd3d6850ceaa773043e2ecb90e13640f547`，1524 stars/153 forks（22:12:10 Asia/Taipei）；全树 **757→781，616 不变/27 新增/138 修改/3 删除**。五份原始纯函数测试 **46/46**；另有 **4 组观察/8 断言**，复现同大小+同 mtime 内容替换仍命中相同预览 key。10 套/31 个 Skill 文件不变，0 新安装；233 个产品输入摘要不变。本轮不增加产品回归或画质验收计数。优先评估组件暴露字段、重写内容 key 的预览缓存及 NLE 薄导出适配；GUI/云 provider 不进入运行时。[模块、成本、证据与复现]({REPORT})；[接入边界，尚未实现](specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md)。
<!-- /R12-CURRENT -->'''
    for name in ('README.md', '构建进度总表_2026-10-16.md',
                 'OpenFilm最新复用评估与成本取舍_2026-10-20.md',
                 'OpenFilm_0.2.2差异复核与复用取舍_2026-10-20.md'):
        insert(ROOT / 'docs' / name, compact)
    print('Updated five README/progress/research documents; product files unchanged.')


if __name__ == '__main__':
    main()
