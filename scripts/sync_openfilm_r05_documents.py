"""Keep R05 source research separate from product and historical verification counts."""
from pathlib import Path
import json
from sync_color_automation_documents import ROOT, marked, line

def run():
    source = json.loads((ROOT/'docs/validation/evidence/openfilm-reuse-final-20261019-r05/verification.json').read_bytes())
    assert source['totals'] == {'tests': 64, 'pass': 63, 'fail': 0, 'skipped': 1}
    for name in ('README.md', 'docs/README.md'):
        path = ROOT/name; text = path.read_text(encoding='utf-8'); prefix = 'docs/' if name == 'README.md' else ''
        block = ('2026-10-19 **R05（OpenFilm 源码研究）**：最新固定 `7a64d1fe`，API **947 stars /99 forks** 为 02:21:46 Asia/Taipei 时点；'
            '713→727 文件，14 新增/41 修改，148 个既有 CLI/渲染/服务端文件原字节不变。选定原测试 **63 通过、1 跳过**，'
            '窗口仅 mock，无 GUI/服务商/新模型。现有拆取方案继续适用；新增主要为桌面会话/设置，不新增本地 AI 剪辑内核。'
            '[编号复用决策、剩余人日和原始证据]('+prefix+'OpenFilm复用复核与开发成本更新_2026-10-19.md)。研究结果与 V58 产品回归分别计数。')
        text = marked(text, 'R05-RESEARCH', block)
        if name == 'README.md':
            history = '| R04 | OpenFilm 5c2000b8 源码与模板修复 | 历史 713 文件；上游 38 通过/1 跳过；V54 产品定向 73/73 另列 | 不算完整产品回归；XML 为合成数据、无真实目标软件导入 | [17 项复用/成本](docs/OpenFilm最新源码复核与降本清单_2026-10-18.md) |'
            row = '| R05 | OpenFilm 新 main 及可拆模块复核 | 固定 7a64d1fe；727 原文件；148 核心未变；63 通过/1 DTD 跳过；10 类复用决策 | 原窗口为 mock；无 GUI/模型/新运行时/新 Skill；不计作产品回归 | [成本/范围](docs/OpenFilm复用复核与开发成本更新_2026-10-19.md)、[原证据](docs/validation/evidence/openfilm-reuse-final-20261019-r05/verification.json) |'
            for key, value, previous in (('| R04 |', history, '| R03 |'), ('| R05 |', row, '| R04 |')):
                if key in text: text = line(text, key, value)
                else:
                    rows = text.splitlines(); i = next(i for i, x in enumerate(rows) if x.startswith(previous))
                    rows.insert(i+1, value); text = '\n'.join(rows)+'\n'
        path.write_text(text, encoding='utf-8', newline='\n')
    path = ROOT/'docs/OpenFilm最新源码复核与降本清单_2026-10-18.md'; text = path.read_text(encoding='utf-8')
    text = marked(text, 'R05-UPDATE', '本页保留 R04 固定版本研究；2026-10-19 更新见[R05 新版本及成本复核](OpenFilm复用复核与开发成本更新_2026-10-19.md)。')
    text = text.replace('本轮也没有重新查询其 stars、升级上游快照或安装新的官方 Skill。',
        'V58 产品核验不作为上游源码更新证据；同日另做[R05 只读版本复核](OpenFilm复用复核与开发成本更新_2026-10-19.md)，没有因此安装新 Skill 或引入新运行时。')
    path.write_text(text, encoding='utf-8', newline='\n')
    print(json.dumps({'documents': 3, 'research_pass': 63, 'research_skipped': 1, 'new_runtime': False}))

if __name__ == '__main__': run()
