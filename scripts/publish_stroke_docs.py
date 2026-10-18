"""Publish this increment after matching an actually completed frozen regression."""
import argparse,hashlib,json,os,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CORE=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md','docs/产品需求与开发路线基线_2026-10-12.md',
 'docs/产品实现入口与P0使用说明_v0.1_2026-10-13.md','docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']
REPORT='docs/validation/离线逐笔描线动效实测_2026-10-18.md'
CONTRACT='docs/specs/离线逐笔描线动效契约_v0.1_2026-10-18.md'

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,t):p.write_text(t,encoding='utf-8',newline='\n')


def run(full_path):
    full=json.loads(full_path.read_bytes())
    assert full['terminal_ok'] and full['exit_code']==0 and full['skipped']==0 and full['frozen_equal']
    assert full['frozen_before']==full['frozen_after']
    assert all(sha(ROOT/k)==v for k,v in full['frozen_after'].items())
    real=json.loads((ROOT/'docs/validation/evidence/stroke-real-verified-20261018/verification.json').read_bytes())
    assert real['status']=='passed' and real['frozen_after']==full['frozen_after']
    n,seconds,files=full['methods'],full['suite_seconds'],len(full['frozen_after'])
    assert n==1107 and files==165
    for name in CORE:
        p=ROOT/name;t=p.read_text(encoding='utf-8-sig');assert '**V48（产品）**' not in t
        def link(label,target):return '['+label+']('+Path(os.path.relpath(ROOT/target,p.parent)).as_posix()+')'
        summary=(f'2026-10-18 **V48（产品）**：拆取 OpenFilm 示例两个原描线函数，新增 `motion stroke-source`，'
            f'显式字符时间/折线转为可编辑离线源并沿用透明编码和工程包；完整 **{n}/{n}，{seconds} 秒**，0 跳过，'
            f'**{files} 文件**冻结，23 新增专项为全量子集。开发版 **17 CLI /108 HTML 帧**，另 216 次乱序重绘、36 时间线主帧；'
            '独立几何 36 帧覆盖 100%，颜色切换 alpha 与工程包重建 RGBA 一致。'
            '**112 包内文件 /12 独立 CLI**；实际原生离线安装另 **6 CLI /36 帧**，五个固定依赖，均与开发版 RGBA 一致。'
            '**14 Skills /164 引用**通过；浏览器页面/子进程全回收。三时刻静帧，未连续播放/听审，0 新模型推理。'
            '只处理明确输入的笔画，不提供自动汉字笔顺、字体生成或语音对齐；自然 AI/声音、复杂 HTML、长片/HDR、干净机器、'
            'FGT 自然画质、内容库和完整剪映等价仍未验收。 '+link('契约',CONTRACT)+'、'+link('原输入/原视频/GIF/发行包与失败',REPORT)+'。')
        t=t.replace('2026-10-18 **V47（产品）**：','历史产品 2026-10-18 **V47（产品）**：',1)
        at=t.index('历史产品 2026-10-18 **V47') if name=='README.md' else t.index('\n')+1
        write(p,t[:at]+summary+'\n\n'+t[at:])
    p=ROOT/'README.md';t=p.read_text(encoding='utf-8')
    row=f'| V48 | OpenFilm 离线逐笔描线内核 | 原 1,417 字节函数；17 CLI/108 HTML 帧，独立几何 100%、工程包 RGBA 一致；112 文件 wheel/12 新进程、原生安装 6 CLI/36 帧；完整 {n}/{n}、165 文件冻结；14 Skills/164 引用 | 明确笔画和时间；无自动字形/汉字笔顺/强制对齐；三静帧无连续播放，失败保留，完整剪映未验收 | [原片/GIF/发行包/实测]({REPORT})、[全量](docs/validation/evidence/stroke-tests-20261018/full.json) |'
    t=re.sub(r'(?m)^(\| V47 \|.*)$',lambda m:m[0]+'\n'+row,t)
    t=re.sub(r'(?m)^\| V13 \|.*$',f'| V13 | 产品自动回归 | 最近 V48 完整 **{n}/{n}**、0 跳过；165 文件冻结，23 新增专项为完整子集 | 开发/独立 wheel/安装实测与历史结果分计；自然质量和完整剪映未验 | [完整日志](docs/validation/evidence/stroke-tests-20261018/full.log)、[冻结与终态](docs/validation/evidence/stroke-tests-20261018/full.json) |',t)
    t=t.replace('最近产品 V47 完整 **1084/1084**、0 跳过，160 文件冻结；Schema 随包及本机独立离线安装、实际源滑移和工程包音画重建通过。',f'最近产品 V48 完整 **{n}/{n}**、0 跳过，165 文件冻结；OpenFilm 原描线函数、独立几何、工程包/安装版 RGBA 重建通过。')
    t=t.replace('配套示例仅审读目录和文本，没有下载媒体或接入新内核。V47 另补离线发行，不把它算作新 OpenFilm 算法采用。','该次配套示例审读没有下载媒体或接入内核；后续 V48 已采用 EX02 两个纯函数，见新增核验行。V47 离线发行不计作 OpenFilm 算法。')
    gallery=('\n**V48 OpenFilm 描线复用**：左为原创背景，右为实际 CLI 编码的逐笔 A/I；384×216、12 fps、36 帧/3 秒。'
        'GIF 实际 16 帧/2,970 ms，无声，停留帧已合并；原输入为显式笔画和时间，无自动字体或语音对齐。\n\n'
        '![实际逐笔描线](docs/assets/stroke-motion-verified-20261018/comparison.gif)\n\n'
        '[原视频](docs/assets/stroke-motion-verified-20261018/source.mp4) · [原笔画](docs/assets/stroke-motion-verified-20261018/authored-plan.json) · '
        '[实际成片](docs/assets/stroke-motion-verified-20261018/result.mp4) · [可编辑源码](docs/assets/stroke-motion-verified-20261018/editable-source.zip) · '
        '[更新安装包](docs/assets/stroke-motion-verified-20261018/agent-video-kit-cp313-win_amd64.zip) · '+f'[实测/失败]({REPORT})\n')
    t=t.replace('## 实测演示素材\n','## 实测演示素材\n'+gallery,1);write(p,t)
    p=ROOT/REPORT;t=p.read_text(encoding='utf-8')
    t=t.replace('状态：V48 描线专项、真实编码、wheel 与原生安装验证通过，完整回归仍在运行，终态发布前不宣称全量通过。',
        f'状态：V48 所列受控描线能力核验通过。完整 **{n}/{n}，{seconds} 秒**，0 跳过；165 文件前后字节冻结。')
    t=t.replace('| ST10 | 完整产品回归 | 等待本轮冻结终态；不能用历史 1084 项代替 |',
        f'| ST10 | 完整产品回归 | **{n}/{n}，{seconds} 秒**，165 文件冻结、0 跳过；23 新增专项为子集。[终态](evidence/stroke-tests-20261018/full.json)、[日志](evidence/stroke-tests-20261018/full.log) |')
    write(p,t)
    p=ROOT/'docs/构建进度总表_2026-10-16.md';t=p.read_text(encoding='utf-8')
    t=t.replace('真实 Whisper 5→9、CER 2% |','真实 Whisper 5→9、CER 2%；V48 显式字符折线描线 |')
    t=t.replace('再入普通时间线 |','再入普通时间线；V48 离线描线源码与参数重建 |');write(p,t)
    p=ROOT/'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md';t=p.read_text(encoding='utf-8')
    row='| 显式逐笔描线（V48） | 原 OpenFilm 两函数、字符时间/折线、透明源/参数重建与工程包 | [17 CLI、独立几何 36 帧 100%、wheel/安装版 RGBA 一致](./离线逐笔描线动效实测_2026-10-18.md)；23 专项为完整 '+str(n)+' 子集 | 无自动字形/笔顺/强制对齐/塑形；自然画质与完整剪映未验收 |'
    t=re.sub(r'(?m)^(\| HTML 动效/模板.*)$',lambda m:row+'\n'+m[0],t,count=1);write(p,t)
    p=ROOT/'docs/README.md';t=p.read_text(encoding='utf-8');t+='\n- [V48 离线逐笔描线契约](specs/离线逐笔描线动效契约_v0.1_2026-10-18.md)与[实测/原片/失败](validation/离线逐笔描线动效实测_2026-10-18.md)。\n- [OpenFilm 描线复用归属](third-party/OpenFilm示例描线函数复用声明_2026-10-18.md)。\n- [CTC 对齐来源预研](CTC对齐模型来源预研_2026-10-18.md)：仅元数据，0 权重下载/推理，不属于 V48 能力。\n';write(p,t)
    print(json.dumps({'status':'published_locally','full_methods':n,'frozen':files,'core_docs':len(CORE)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--full',type=Path,required=True);a=p.parse_args();run(a.full.resolve())
