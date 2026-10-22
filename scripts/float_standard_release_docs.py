"""Project actual R96 receipts into README and the existing requirements index."""
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = 'docs/validation/evidence/float-standard-20261022-lab'
ASSETS = 'docs/assets/float-standard-20261022-r4'
REPORT = 'docs/validation/标准CLI浮点交付实测_2026-10-22.md'
CONTRACT = 'docs/specs/标准CLI浮点渲染接入契约_v0.1_2026-10-22.md'
MARKER = 'V96-STANDARD-NATIVE-FLOAT-RENDER'
LATEST_DOCS = ('README.md', 'docs/README.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md', 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md', 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path):
    return json.loads(path.read_bytes())


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip()+'\n', encoding='utf8', newline='\n')


def current():
    inputs = frozen(); assert len(inputs) == 298
    native = read(ROOT/REL/'standard-r5/verification.json')
    media = read(ROOT/REL/'media-r4/verification.json')
    assert native['status'] == 'passed' and native['methods'] == 17 and not native['skipped']
    assert native['frozen_before'] == native['frozen_after'] == inputs
    assert media['status'] == 'passed-public-CLI-original-and-edited-native-float-media'
    assert media['frozen_before'] == media['frozen_after'] == inputs
    assert media['frames_each'] == 20 and media['stereo_sample_frames_each'] == 96000
    assert len(media['calls']) == 12 and len(media['checks']) == 16 and all(c['ok'] for c in media['checks'])
    for name, row in media['assets'].items():
        assert sha(ROOT/name) == row['sha256']
    installed_path = ROOT/REL/'installed-r1/verification.json'
    installed = read(installed_path) if installed_path.exists() else None
    return inputs, native, media, installed


def section(full=None, published=False):
    inputs, native, media, installed = current()
    installed_ok = installed and installed['status'] == 'passed-fresh-eight-wheel-179-resources-real-CLI-media-and-220-methods'
    install_text = ('**220 方法 /'+str(installed['isolated_methods']['suite_seconds'])+' 秒 /0 跳过**；179 资源 source/wheel/site 相同，8 个离线 wheel，NumPy 931 原文件和许可相同，安装版两次真实 CLI 媒体逐像素/PCM 与开发版相同。' if installed_ok else '**尚未结束，不计为通过**；正在全新原生离线安装中核验 179 资源、真实 CLI 媒体与 220 方法。')
    full_text = ('**2337 方法 /'+str(full['suite_seconds'])+' 秒 /0 跳过**；298 产品输入、8 外部夹具、启动时脚本和9依赖相同。' if full else '**尚未执行/未结束，不计为通过**；完整 2337 方法按 V95 与 R16 实际发布顺序串行，发现数量不等于已执行。')
    heading = 'V96 标准 CLI 原片浮点渲染' if published else 'V96 候选：标准 CLI 原片浮点渲染（未发布）'
    return f'''<!-- {MARKER} -->
### {heading}

`settings.pixel_pipeline.engine="float32-native-v1"` 将原片窗口与 Float32 线性光合成接入共同 `render`、持久队列及续跑。当前定向 **17 方法 /200.249 秒 /0 跳过**。显式选择此后端；尚未接入的操作会拒绝。默认后端迁移、所有效果/预览缓存、自然素材、HDR 和完整剪映等价仍需持续实现。

| 编号 | 功能性核验 | 实际执行内容与限制 | 证据 |
|---|---|---|---|
| V96-01 | 标准执行器 | 公共 `render`、持久 `queue run`、取消后的 `render --resume` 使用共同质量检查/指纹/记录；修改 CRF 的续跑被拒绝 | [17项真实测试]({REL}/standard-r5/verification.json) |
| V96-02 | 高精度交付 | 65,536 原始灰阶经正式 10-bit H.264/MKV；独立亮度参考误差≤1.5码且至少870级；合成到最终16-bit RGB交付前保留Float32 | [契约]({CONTRACT}) |
| V96-03 | 色彩边界反例 | 三组真实转换：旧 swscale 参数白点943而非940；zscale 全码最大误差0.499977、877级、Cb/Cr全512；参数/标签与实际转换绑定 | [独立原始对照]({REL}/color-boundary-r1/verification.json) |
| V96-04 | 透明度 | 全部256个alpha码值及量化边界附近值，经独立平面、lossless VP9/WebM逐码相同；实际透明画面不能默默丢到不透明输出 | [原始alpha反例]({REL}/alpha-boundary-r1/verification.json) · [实测]({REL}/standard-r5/unittest.log) |
| V96-05 | 作者视频/音频时钟 | 原始5秒起点VFR在嵌套倒放下逐帧匹配独立区间参考；倒放/定格PCM逐字节相同；分数作者末尾13视频帧和60001立体声采样分别保留 | [实际测试与命令]({REL}/standard-r5/verification.json) |
| V96-06 | 失败与资源清理 | 只读规划不写缓存/临时成片；源SHA、已知非方形源、未接操作拒绝；编码/质量/manifest暂存/替换失败保留旧文件并关闭自有进程线程。发布二文件不保证强退/断电原子性 | [失败/修复]({REPORT}) |
| V96-07 | 正式CLI原片与成片 | 两次独立子进程CLI；脚本级12次调用、16检查；原片/编辑片各20帧、10fps、2秒和96000立体声采样；作者IR不重写，PCM全样本相同 | [真实命令/SHA]({REL}/media-r4/verification.json) |
| V96-08 | 原视频/MP4/GIF | 自生成RGB16原片与音频；正式10-bit MKV；屏幕混合、圆蒙版、反向源与变换关键帧；MP4/GIF为这两段真实输出的预览 | [原片]({ASSETS}/original.native.mkv) · [原始MP4]({ASSETS}/original.mp4) · [编辑MP4]({ASSETS}/edited.mp4) · [正式10-bit成片]({ASSETS}/edited.mkv) |
| V96-09 | 实际抽帧目检 | 已查看原片/成片0/10/19共6帧；圆形位置/旋转与亮度混合可见，未见明显外围黑矩形；GIF20帧均100ms。未连续播放/试听 | [查看与GIF时钟]({REL}/static-review-r1.json) |
| V96-10 | 全新离线安装 | {install_text} | [安装收据]({REL}/installed-r1/verification.json) |
| V96-11 | 完整回归 | {full_text} | [当前实测报告]({REPORT}) |
| V96-12 | 保留失败 | r1摘要/夹具/色阶失败与收据序列化故障；r3只读/VFR夹具问题；r4取消清理丢失操作ID；媒体r1外部路径、r2缺插值、r3开发环境来源断言均保留 | [逐轮记录]({REPORT}) |

![原始输入与正式CLI编辑输出GIF]({ASSETS}/comparison.gif)

<!-- /{MARKER} -->
'''


def relink(text, name):
    prefix = '../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/', lambda m: m[1]+prefix+'docs/', text)


def report(full=None):
    marker = 'R96-ACTUAL-RESULTS'
    path = ROOT/REPORT
    text = path.read_text('utf8')
    text = re.sub(r'\n?<!-- '+marker+r' -->.*?<!-- /'+marker+r' -->\n?', '\n', text, flags=re.S)
    text = text.replace('后续定向重测、真实公开 CLI/队列媒体、离线安装、完整回归与 README 编号行待按实际终态追加。', '当轮最新实际结果见下方编号表；安装和完整回归未结束时不计为通过。')
    block = f'''\n<!-- {marker} -->
## 3. 当前实际结果与保留失败

| 编号 | 实际执行 | 结果 |
|---|---|---|
| R96-A01 | 第一轮修复后17方法的完整定向重测 | [standard-r5](evidence/float-standard-20261022-lab/standard-r5/verification.json)：17方法 /200.249秒 /0跳过；298产品输入SHA前后相同。没有把重复轮次相加成新功能或方法数 |
| R96-A02 | 扩展夹具首轮失败 | [standard-r3](evidence/float-standard-20261022-lab/standard-r3/verification.json)：17方法、3失败。只读断言前的测试保存更新了作者时间；VFR表达式缺转义；NUT容器末帧PTS作为容器时长导致公开校验拒绝。改用真实完整时长MKV作普通CLI夹具，保留NUT作直接VFR时钟夹具，不伪造probe或放宽源范围 |
| R96-A03 | 真实取消续跑故障与修复 | [standard-r4](evidence/float-standard-20261022-lab/standard-r4/verification.json)：17方法、1失败。资源栈用close把异常退出当成功退出，源清理再次轮询取消并覆盖带操作ID的原错误。r5传递真实异常，公开续跑成功；CRF变更的续跑仍拒绝 |
| R96-A04 | 两次正式CLI媒体 | [media-r4](evidence/float-standard-20261022-lab/media-r4/verification.json)：12个脚本级真实调用、16检查，两次CLI render均完成。原始/编辑片各20帧/10fps/2秒、96000立体声采样；逐字节PCM相同，画面SHA不同，作者工程的设置/片段/源范围不重写 |
| R96-A05 | 媒体夹具与来源检查失败 | media-r1拒绝未授权工程外路径；其计数器在成功后递增，字段0表示完成0次，calls中实际发起1次CLI。media-r2缺4个关键帧的interpolation，被Schema与语义校验拒绝。media-r3的两次成片和像素/PCM检查完成，但错误要求开发环境NumPy/Pillow位于产品源码目录；r4只对产品强制源码来源，安装轮仍要求全部运行模块来自安装site。原失败和原执行代码均保留 |
| R96-A06 | 抽帧目检与GIF时钟 | [static-review-r1](evidence/float-standard-20261022-lab/static-review-r1.json)：实际查看0/10/19的原片/编辑片共6帧；GIF20帧、每帧100ms。没有连续播放、试听或自然素材/HDR质量验收 |

当前README编号预览如下，所有数字来自本轮对应收据；完整2337方法未结束前不标为通过。

{relink(section(full), REPORT)}

复现入口：[真实CLI媒体生成器](../../scripts/smoke_float_standard_media.py)、[17方法运行器](../../scripts/verify_float_standard.py)、[全新离线安装](../../scripts/verify_float_standard_install.py)、[串行完整回归](../../scripts/run_float_standard_complete.py)。源码、失败样例和派生素材均在E盘，未调用Docker、WSL、虚拟环境、云模型或交互浏览器tab。
<!-- /{marker} -->
'''
    write(path, text+block)


def documents(target, full=None, published=False):
    block = section(full, published)
    for name in LATEST_DOCS:
        source = target/name if (target/name).exists() else MAIN/name
        text = source.read_text('utf8')
        text = re.sub(r'\n?<!-- '+MARKER+r' -->.*?<!-- /'+MARKER+r' -->\n?', '\n', text, flags=re.S)
        first, separator, rest = text.partition('\n')
        write(target/name, first+'\n\n'+relink(block, name)+'\n'+rest.lstrip('\n'))
    write(ROOT/REL/'readme-section.md.txt', block)


def links(target):
    roots = [target, ROOT, ROOT.parent/'float-render-lab-20261022', ROOT.parent/'float-stream-lab-20261022',
             ROOT.parent/'float-timeline-lab-20261022', ROOT.parent/'openfilm-reuse-lab-20261022-r16', MAIN]
    found = []
    for name in (*LATEST_DOCS, REPORT, CONTRACT):
        path = target/name if (target/name).exists() else ROOT/name
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', path.read_text('utf8')):
            value = value.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value) or value.startswith('#'):
                continue
            part = unquote(value.split('#', 1)[0])
            candidates = [(base/Path(name).parent/part).resolve() for base in roots]
            assert any(p.exists() for p in candidates), (name, value)
            found.append({'document': name, 'link': value})
    return found


if __name__ == '__main__':
    target = ROOT/'product/.runtime/float-standard-20261022/readme-preview-r1'
    assert not target.exists()
    report()
    documents(target)
    checked = links(target)
    write(ROOT/REL/'readme-preview-r1.json', json.dumps({'status': 'passed-unpublished-numbered-readme-and-seven-document-preview',
        'documents': list(LATEST_DOCS), 'links_checked': len(checked), 'full_suite_claimed_passed': False,
        'target': str(target), 'generator_sha256': sha(Path(__file__))}, ensure_ascii=False, indent=2))
    print(json.dumps({'status': 'passed-preview', 'documents': len(LATEST_DOCS), 'links': len(checked)}))
