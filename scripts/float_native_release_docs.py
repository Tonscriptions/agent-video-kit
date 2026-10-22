"""Project actual native-window evidence into numbered README and current docs."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote
from run_frozen_regression import frozen, sha

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[2]
REL = 'docs/validation/evidence/float-render-20261022-lab'
ASSETS = 'docs/assets/float-render-20261022-lab'
CONTRACT = 'docs/specs/原生素材窗口浮点源_实验_v0.1_2026-10-22.md'
REPORT = 'docs/validation/原生素材窗口解码与浮点音画合成实测_2026-10-22.md'
MARKER = 'V95-NATIVE-WINDOW-FLOAT-SOURCE'
LATEST_DOCS = ('README.md', 'docs/README.md', 'docs/产品需求与开发路线基线_2026-10-12.md',
    'docs/构建进度总表_2026-10-16.md', 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md',
    'docs/Concat与剪映功能差异矩阵_2026-10-12.md', 'docs/specs/AgentCLI契约_v0.1_2026-10-13.md')


def read(path): return json.loads(path.read_bytes())
def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + '\n', encoding='utf8', newline='\n')
def save(path, value): write(path, json.dumps(value, ensure_ascii=False, indent=2))


def relink(text, name):
    prefix = '../' * (len(Path(name).parts) - 1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/', lambda match: match[1] + prefix + 'docs/', text)


def current_evidence():
    current = frozen()
    focus = read(ROOT / REL / 'native-r2.json')
    media = read(ROOT / REL / 'media-r1/verification.json')
    assert len(current) == 296
    assert focus['status'] == 'passed-native-clock-window-source-and-owned-pipe'
    assert focus['frozen_before'] == focus['frozen_after'] == current
    assert focus['result']['methods'] == 21 and focus['result']['successful'] and focus['result']['skipped'] == 0
    assert len(focus['result']['audited_native_launches']) == 58
    assert media['status'] == 'passed-real-native-window-FFV1-and-independent-authored-PCM'
    assert media['frozen_before'] == media['frozen_after'] == current
    assert media['actual_native_launches'] == 86 and media['actual_encoder_processes'] == 2
    assert len(media['assets']) == 16 and len(media['checks']) == 21
    for name, row in media['assets'].items():
        assert sha(ROOT / name) == row['sha256'] and (ROOT / name).stat().st_size == row['bytes']
    installed_path = ROOT / REL / 'installed-r1/verification.json'
    installed = read(installed_path) if installed_path.exists() else None
    if installed is not None and installed['status'].startswith('passed'):
        assert installed['frozen_before'] == installed['frozen_after'] == current
        assert installed['isolated_methods']['methods'] == 203 and installed['isolated_methods']['skipped'] == 0
        assert len(installed['resource_hashes']) == 178
    return focus, media, installed


def installed_gate():
    _, _, installed = current_evidence()
    assert installed is not None and installed['status'] == 'passed-fresh-eight-wheel-178-resources-real-media-and-203-methods'
    return installed


def install_line(installed):
    if installed is not None and installed['status'].startswith('passed'):
        return f"实际203方法 /{installed['isolated_methods']['suite_seconds']:.3f}秒 /0跳过；178资源与source/wheel/site相同，931份NumPy文件/许可相同"
    return f"全新隔离安装状态：{installed['status'] if installed else 'not-started'}；尚不登记203方法通过"


def full_line(full):
    if full is not None:
        assert full['terminal_ok'] and full['methods'] == 2320 and full['skipped'] == 0
        assert full['frozen_before'] == full['frozen_after'] == frozen()
        return f"实际完整2320方法 /{full['suite_seconds']:.3f}秒 /0跳过；296产品输入、8外部夹具和9依赖保持相同"
    return '已实际发现2320方法；本候选完整回归尚未通过，发现数不代表执行数。完整执行须等待已调度的V94父版发布后串行进行'


def report(full=None):
    focus, media, installed = current_evidence()
    body = f'''# 原生素材窗口解码与浮点音画合成实测

新增 `float_native_pipe` 和 `float_native_source`：已登记原片按原生时间戳和关键帧解码局部窗口，向现有 Float32 时间线返回独立表面。本次真实成片输入直接使用 RGB16/YCbCr16 原片，**不使用整片 Float32 帧包作为解码输入**。标准 render/preview/queue/cache、全部效果和完整剪映功能效果等价仍未完成。

| 编号 | 实际核验 | 结果与边界 |
|---|---|---|
| V95-01 | 原生管道与来源专项 | 21方法 /{focus['result']['seconds']:.6f}秒 /0失败错误跳过；58次审计原生工具启动、7个实际Python子进程管道收据、13份成功打开来源的关闭收据分别保留 |
| V95-02 | 时钟及16位像素 | 8帧随机RGBA16，VFR、容器起点5秒、独立透明/不透明像素及随机取帧；每个分量精确回读，右边界/原生末帧duration检查通过 |
| V95-03 | B帧与关键帧跳读 | 120帧H.264、24帧GOP、3个B帧配置；远距离随机窗口与独立全片原生YCbCr解码及独立矩阵公式对照。不是长片实时/线性复杂度证明 |
| V95-04 | 有界缓存及所有权 | 两帧预算实际缩小200帧请求；修改返回副本不污染缓存；4×64KiB队列、2×64KiB stderr，实际阻塞/满队列/取消/超时子进程和线程回收通过 |
| V95-05 | 生命周期读锁 | 原片写入、删除和3个持久化索引写入被Windows真实拒绝；独立两源关闭顺序、关闭后允许写入/删除、错误SHA失败释放锁均通过 |
| V95-06 | 隔行与静态图 | 实际隔行MPEG2源拒绝冒充逐行；真实PNG按显式起点重复取帧并返回独立副本。JPEG/yuvj分支未作本轮实片验收 |
| V95-07 | 直接原片音画成片 | 两组各20帧/10FPS/2秒；每个16位分量与既有独立核验参考一致，两组各96000立体声采样帧逐字节一致；2次实际管道编码、86次原生工具启动、16资产/21检查 |
| V95-08 | 实际窗口统计 | 四来源生命周期合计58次窗口解码；每来源最大缓存491520字节=2个160×96 RGBA Float32帧。原片对照在编码后另作一次逐帧参考读取，统计包括该读取；不将缓存字节当峰值RSS或把58当实际codec解码帧数 |
| V95-09 | 全新离线安装 | {install_line(installed)}；安装版原片重新解码/编码并比较无损像素及PCM SHA，未复用开发版输出冒充执行 |
| V95-10 | 完整回归 | {full_line(full)}；专项、隔离和父版历史计数不相加 |
| V95-11 | 保留失败 | native-r1实际21方法/60.667秒/1失败：全部RGB16分量先通过，但仅首帧关键帧的FFV1夹具错误要求出现正数seek。r2夹具显式使用-g 1，保留原断言；同时完善异常清理的finally锁释放 |
| V95-12 | 未验收 | 默认CLI/preview/queue/cache、完整作者效果、方向/SAR显示适配、HDR/ICC/PQ/HLG、自然广告与AI质量、连续播放/试听、4K长片RSS和长GOP倒放性能；未宣称完整剪映等价 |

[专项收据](evidence/float-render-20261022-lab/native-r2.json) · [失败原记录](evidence/float-render-20261022-lab/native-r1.json) · [真实媒体](evidence/float-render-20261022-lab/media-r1/verification.json) · [隔离安装](evidence/float-render-20261022-lab/installed-r1/verification.json) · [仅发现](evidence/float-render-20261022-lab/discovery-r1.json) · [契约](../specs/原生素材窗口浮点源_实验_v0.1_2026-10-22.md)。

[原始RGB16](../assets/float-render-20261022-lab/media-r1/inputs/foreground-16bit.mkv) · [原始YCbCr16](../assets/float-render-20261022-lab/media-r1/inputs/background-16bit.mkv) · [原始PCM](../assets/float-render-20261022-lab/media-r1/original-audio.wav) · [原片MKV](../assets/float-render-20261022-lab/media-r1/original-16bit.mkv) · [原片MP4](../assets/float-render-20261022-lab/media-r1/original.mp4) · [剪辑MKV](../assets/float-render-20261022-lab/media-r1/timeline-16bit.mkv) · [剪辑MP4](../assets/float-render-20261022-lab/media-r1/timeline.mp4)。

![原片实际MP4解码GIF](../assets/float-render-20261022-lab/media-r1/original.gif)

![剪辑实际MP4解码GIF](../assets/float-render-20261022-lab/media-r1/timeline.gif)

![实际帧与PCM诊断](../assets/float-render-20261022-lab/media-r1/actual-frames-and-PCM.png)

实际目检MP4的0、9、19帧与对应PCM诊断图；未连续播放，未试听。程序生成原片和新写立体声正弦/扫频音为CC0技术样例，不代表自然广告和AI特效质量。MP4/AAC和GIF为有损预览；无损核验使用FFV1及Float32 PCM。Float32参考文件只作为既有固定SHA像素对照，不是运行内核输入；本次没有新写第二套时间线参考实现。

```powershell
C:/Python313/python.exe -E -B -X utf8 scripts/run_float_native_tests.py --revision <新编号>
C:/Python313/python.exe -E -B -X utf8 scripts/smoke_float_native_media.py --revision <新编号> --source-root <含V93原片与固定参考的仓库根>
C:/Python313/python.exe -E -B -X utf8 scripts/verify_float_native_install.py
```

安装验证使用固定的全新installed-r1目录；再次整套执行须另立目录，保留既有原收据。全程原生Windows、E盘、已有离线依赖，无Docker/WSL、虚拟环境、在线下载或新增交互浏览器tab。
'''
    write(ROOT / REPORT, body)


def documents(destination, full=None):
    destination = Path(destination).resolve()
    assert destination == MAIN or destination.is_relative_to(ROOT / 'product/.runtime')
    focus, media, installed = current_evidence()
    report(full)
    if full is None:
        assert destination != MAIN
        status = '未发布候选文档预览；完整2320方法尚未通过。'
    else:
        installed_gate()
        status = full_line(full) + '。'
    section = f'''### V95 原生素材窗口与浮点时间线直连

{status} 当前为库层接入；标准render/preview/queue/cache、全部效果及完整剪映等价仍待完成。

| 编号 | 功能性核验 | 实际结果与限制 | 证据 |
|---|---|---|---|
| V95-01 | 原片窗口解码 | 21方法通过；RGB16/VFR/非零起点、120帧H.264 B帧跳读与独立全片解码对照；58次原生工具启动 | [专项]({REL}/native-r2.json) |
| V95-02 | 缓存与清理 | 有界像素窗口、独立帧副本；读锁禁止源/索引临时改写；实际满队列、取消、超时、自有进程/线程回收 | [31条契约]({CONTRACT}) |
| V95-03 | 原片直接成片 | 各20帧/96000立体声采样帧与参考全部核验；86原生启动、2管道编码；16资产/21检查，无输入浮点帧包 | [媒体/SHA]({REL}/media-r1/verification.json) |
| V95-04 | 实际缓存 | 每来源最多491520字节=2个160×96 Float32帧；长GOP跳读仍可能重复前滚，缓存上限不代表RSS上限 | [窗口收据]({REL}/media-r1/verification.json) |
| V95-05 | 新鲜隔离交付 | {install_line(installed)}；安装版独立重做媒体，新增公开CLI为0 | [安装]({REL}/installed-r1/verification.json) |
| V95-06 | 失败与限制 | 首轮关键帧夹具断言失败保留；未连续播放/试听、未验收自然广告/HDR/4K长片/完整剪映效果；标准入口尚未迁移 | [报告]({REPORT}) |

[原始RGB16]({ASSETS}/media-r1/inputs/foreground-16bit.mkv) · [原始YCbCr16]({ASSETS}/media-r1/inputs/background-16bit.mkv) · [原片MP4]({ASSETS}/media-r1/original.mp4) · [原始PCM]({ASSETS}/media-r1/original-audio.wav) · [剪辑MKV]({ASSETS}/media-r1/timeline-16bit.mkv) · [剪辑MP4]({ASSETS}/media-r1/timeline.mp4)

![原片实际GIF]({ASSETS}/media-r1/original.gif)

![剪辑实际GIF]({ASSETS}/media-r1/timeline.gif)
'''
    paths = []
    for name in LATEST_DOCS:
        existing = (MAIN / name).read_text('utf8')
        assert f'<!-- {MARKER} -->' not in existing
        block = section if name == 'README.md' else f'''### V95 原片窗口浮点接入进度

{status} 21专项方法通过，直接原片两组20帧/96000立体声采样帧核验完成。{install_line(installed)}。标准render/preview/queue/cache、全部效果、HDR/长片质量及完整剪映等价仍待验收。

[实测/失败/原片/GIF]({REPORT}) · [实验契约]({CONTRACT}) · [媒体收据]({REL}/media-r1/verification.json)
'''
        head, _, rest = existing.partition('\n')
        write(destination / name, head + '\n\n' + relink(f'<!-- {MARKER} -->\n' + block + f'\n<!-- /{MARKER} -->', name) + '\n\n' + rest.lstrip())
        paths.append(name)
    for name in (REPORT, CONTRACT):
        write(destination / name, (ROOT / name).read_text('utf8'))
        paths.append(name)
    return paths


def local_links(destination, paths):
    destination = Path(destination).resolve()
    rows = []
    for name in paths:
        for value in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', (destination / name).read_text('utf8')):
            if value.startswith(('https:', 'http:', 'app:', 'codex:', '#')):
                continue
            relative = ((destination / name).parent / unquote(value.split('#', 1)[0].strip('<>'))).resolve().relative_to(destination)
            actual = next((p for p in (destination / relative, ROOT / relative, MAIN / relative) if p.exists()), None)
            assert actual is not None, (name, value)
            rows.append({'document': name, 'target': relative.as_posix(), 'checked_at': str(actual)})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    assert args.preview.resolve() != MAIN and not args.preview.exists()
    paths = documents(args.preview)
    links = local_links(args.preview, paths)
    save(ROOT / REL / ('readme-preview-' + args.revision + '.json'),
        {'status': 'passed-unpublished-nine-document-and-numbered-README-preview',
         'at_utc': datetime.now(timezone.utc).isoformat(), 'generator_sha256': sha(Path(__file__)),
         'preview': str(args.preview.resolve()), 'main_changed': False, 'published': False,
         'documents': {name: sha(args.preview / name) for name in paths},
         'verified_local_links': len(links), 'links': links, 'frozen_inputs': frozen()})
    print(json.dumps({'status': 'passed-unpublished-preview', 'documents': len(paths),
                      'verified_links': len(links), 'main_changed': False}), flush=True)


if __name__ == '__main__':
    main()
