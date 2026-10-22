"""Project actual R97 source, media and installation evidence into existing docs."""
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
PARENT = ROOT.parent/'float-standard-render-lab-20261022'
REL = 'docs/validation/evidence/float-preview-20261022-lab'
ASSETS = 'docs/assets/float-preview-20261022-r1'
REPORT = 'docs/validation/浮点时间线预览与缓存实测_2026-10-22.md'
CONTRACT = 'docs/specs/浮点时间线预览与缓存契约_v0.1_2026-10-22.md'
MARKER = 'V97-NATIVE-FLOAT-TIMELINE-PREVIEW'
LATEST_DOCS = ('README.md', 'docs/README.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md', 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md', 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):
    return json.loads(path.read_bytes())


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip()+'\n', encoding='utf8', newline='\n')


def current():
    inputs = frozen(); assert len(inputs) == 300
    native = read(ROOT/REL/'native-r2/verification.json')
    media = read(ROOT/REL/'media-r1/verification.json')
    assert native['status'] == 'passed' and native['methods'] == 57 and not native['skipped']
    assert native['frozen_before'] == native['frozen_after'] == inputs
    assert media['status'] == 'passed-public-CLI-original-edited-and-native-float-previews'
    assert media['frozen_before'] == media['frozen_after'] == inputs
    assert media['actual_public_render_CLI_processes'] == 2 and media['actual_public_preview_CLI_processes'] == 3
    assert len(media['calls']) == 20 and len(media['checks']) == 27 and all(c['ok'] for c in media['checks'])
    for name, row in media['assets'].items():
        assert sha(ROOT/name) == row['sha256']
    path = ROOT/REL/'installed-r1/verification.json'
    installed = read(path) if path.exists() else None
    return inputs, native, media, installed


def section(full=None, published=False):
    _, native, media, installed = current()
    installed_ok = installed and installed['status'] == 'passed-fresh-eight-wheel-180-resources-real-previews-and-260-methods'
    install_text = ('**260 方法 /'+str(installed['isolated_methods']['suite_seconds'])+' 秒 /0 跳过**；180 资源 source/wheel/site 相同，8 个离线 wheel；NumPy 931 文件与许可相同。安装版原生 Float32/PCM/PNG16 与开发版真实 CLI 样例相同。' if installed_ok else '**尚未结束，不计通过**；新原生安装目录中核验180资源、260方法和真实CLI预览。')
    full_text = ('**2355 方法 /'+str(full['suite_seconds'])+' 秒 /0 跳过**；300产品输入、8外部夹具、9依赖及冻结运行器一致。' if full else '**尚未执行/未结束，不计通过**；预计2355方法，等待实际V96父提交发布后串行执行。')
    heading = 'V97 原片 Float32 时间线预览与缓存' if published else 'V97 候选：原片 Float32 时间线预览与缓存（未发布）'
    return f'''<!-- {MARKER} -->
### {heading}

显式浮点工程的 `preview frame` / `preview range` 使用标准渲染的原片窗口与 FloatTimeline，保留完整作者帧号。源码相关回归 **57 方法 /532.355 秒 /0 跳过**，包括18项新增预览、22项既有预览及17项标准浮点渲染；不将57项全算作新功能。默认迁移及未接入算子、自然/HDR质量和完整剪映功能仍需继续实现。

| 编号 | 功能性核验 | 实际内容与限制 | 证据 |
|---|---|---|---|
| V97-01 | 共同内核 | 原片SHA与原生PTS窗口、作者IR、变换/混合/基础蒙版及嵌套时钟复用正式浮点宿主；未接算子明确拒绝 | [契约]({CONTRACT}) |
| V97-02 | PNG16与alpha16 | 真实PNG逐码保留65,536灰阶和全部65,536透明度值；PNG独立16位交付，不当作Float32参考 | [57项实际命令/断言]({REL}/native-r2/verification.json) |
| V97-03 | Float32区间参考 | `master.nut`为straight BT.709 linear GBRAP Float32；实际保存小于一个RGB16码阶的合成变化；格式对照包含相邻Float32、负值及超一值，作者范围策略另行执行 | [格式逐字节往返]({REL}/formats-r1.json) |
| V97-04 | 作者视频时钟 | 5秒起点的真实VFR在嵌套倒放选帧中匹配独立区间参考，保留全片帧号；selected sequence canvas不改写全局作者画布 | [源码回归]({REL}/native-r2/unittest.log) |
| V97-05 | PCM独立端点 | 非整数作者结束保留60001末样本端点；区间样本逐字节匹配；真实样例帧3..16共14帧，67200双声道PCM采样帧相同 | [实际CLI样例]({REL}/media-r1/verification.json) |
| V97-06 | 线性预乘缩放 | 完整合成后按像素中心双线性缩放，独立2×2透明颜色加权参考通过；不是大比例缩小的面积抗锯齿 | [独立像素测试]({REL}/native-r2/verification.json) |
| V97-07 | 持久内容缓存 | 作者/实际素材/信号/本地代码/NumPy原生依赖绑定SHA；同大小、恢复mtime的运行时变化仍失效。命中不新建图、provider、probe或编码器；真实第二CLI进程命中 | [真实复用与原始收据]({REL}/media-r1/verification.json) |
| V97-08 | 只读与失败清理 | dry-run不打开provider或写缓存；真实中途取消及失败编码器清理线程/临时目录；损坏参考拒绝，原导出保留，显式导出可在prune后保留 | [失败边界及原始输出]({REL}/native-r2/verification.json) |
| V97-09 | 真实公开CLI媒体 | 20个脚本级原生/CLI调用、27检查；2次正式render、3次preview（区间、单帧、复用）；原始/编辑完整片各20帧、2秒、96000双声道采样 | [生成器]({REL}/media-r1/executed-script.py.txt) |
| V97-10 | 原视频与实际预览 | 原创RGB16输入；下方GIF左为原始CLI输出帧3..16，右为本轮真实CLI预览，共14×100ms；已查看3/10/16共6幅图，未连续播放或试听 | [原始选段]({ASSETS}/original-range.mp4) · [实际预览MP4]({ASSETS}/range.mp4) · [Float32参考]({ASSETS}/range.master.nut) · [PNG16帧11]({ASSETS}/frame.png) · [查看/GIF时钟]({REL}/static-review-r1.json) |
| V97-11 | 全新离线安装 | {install_text} | [安装收据]({REL}/installed-r1/verification.json) |
| V97-12 | 完整回归 | {full_text} | [当前实测报告]({REPORT}) |
| V97-13 | 保留失败与观看副本边界 | 首轮18项2失败已保留；显式OETF修复观看亮度。原生去alpha使观看副本减损精度，原理想半码探针仍保留失败；不影响独立Float32参考/PNG16的验收，不宣称MP4理想量化 | [失败与分段测量]({REPORT}) |

![原始选段与真实CLI浮点时间线预览]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text, name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/', lambda m: m[1]+prefix+'docs/', text)


def report(full=None):
    path = ROOT/REPORT; marker = 'R97-ACTUAL-RESULTS'
    text = re.sub(r'\n?<!-- '+marker+r' -->.*?<!-- /'+marker+r' -->\n?', '\n', path.read_text('utf8'), flags=re.S)
    block = '\n<!-- '+marker+' -->\n## 5. 当前实际结果与README编号表\n\n'+relink(section(full), REPORT)+'\n<!-- /'+marker+' -->\n'
    write(path, text+block)


def documents(target, full=None, published=False):
    block = section(full, published)
    parent_preview = PARENT/'product/.runtime/float-standard-20261022/readme-preview-r2'
    for name in LATEST_DOCS:
        source = target/name if (target/name).exists() else (parent_preview/name if (parent_preview/name).exists() else MAIN/name)
        text = re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?', '\n', source.read_text('utf8'), flags=re.S)
        first, _, rest = text.partition('\n')
        write(target/name, first+'\n\n'+relink(block, name)+'\n'+rest.lstrip('\n'))
    write(ROOT/REL/'readme-section.md.txt', block)


def links(target):
    roots = [target, ROOT, PARENT, ROOT.parent/'float-render-lab-20261022', ROOT.parent/'float-stream-lab-20261022',
             ROOT.parent/'float-timeline-lab-20261022', ROOT.parent/'openfilm-reuse-lab-20261022-r16', MAIN]
    result = []
    for name in (*LATEST_DOCS, REPORT, CONTRACT):
        path = target/name if (target/name).exists() else ROOT/name
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', path.read_text('utf8')):
            value = value.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value) or value.startswith('#'):
                continue
            part = unquote(value.split('#', 1)[0])
            assert any((base/Path(name).parent/part).resolve().exists() for base in roots), (name, value)
            result.append({'document': name, 'link': value})
    return result


if __name__ == '__main__':
    target = ROOT/'product/.runtime/float-preview-20261022/readme-preview-r1'; assert not target.exists()
    report(); documents(target); found = links(target)
    write(ROOT/REL/'readme-preview-r1.json', json.dumps({'status': 'passed-unpublished-numbered-readme-and-seven-document-preview',
        'documents': list(LATEST_DOCS), 'links_checked': len(found), 'full_suite_claimed_passed': False,
        'target': str(target), 'generator_sha256': sha(Path(__file__))}, ensure_ascii=False, indent=2))
    print(json.dumps({'status': 'passed-preview', 'documents': len(LATEST_DOCS), 'links': len(found)}))
