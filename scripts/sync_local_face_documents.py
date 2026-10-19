"""Reflect terminal native receipts and distinguish candidate from release docs."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/local-face-beauty-20261020-v69'
REPORT=ROOT/'docs/validation/离线人脸锚点与局部修饰实测_2026-10-20.md'
CONTRACT=ROOT/'docs/specs/离线人脸锚点与局部修饰契约_v0.1_2026-10-20.md'
DOCUMENTS=['README.md','docs/README.md','docs/构建进度总表_2026-10-16.md',
           'docs/产品需求与开发路线基线_2026-10-12.md','docs/specs/AgentCLI契约_v0.1_2026-10-13.md',
           'docs/validation/README功能核验与实测演示_2026-10-16.md','docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md']


def read(path):return json.loads(path.read_bytes())
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def relative(source,target):return Path(os.path.relpath(target,source.parent)).as_posix()


def insert(path,content):
    text=path.read_text(encoding='utf8');start='<!-- V69-CURRENT -->';end='<!-- /V69-CURRENT -->'
    block=start+'\n'+content.rstrip()+'\n'+end
    if start in text:
        a=text.index(start);b=text.index(end,a)+len(end);text=text[:a]+block+text[b:]
    else:
        first,rest=text.split('\n',1);text=first+'\n\n'+block+'\n'+rest
    path.write_text(text,encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',action='store_true');args=parser.parse_args()
    current=frozen();full=read(BASE/'full-r1.json');dev=read(BASE/'native-r5/verification.json')
    install=read(BASE/'installed-r1/verification.json');controls=read(BASE/'controls-r1/verification.json');skills=read(BASE/'skills-r1.json')
    cancel=read(BASE/'worker-cancel-r2/verification.json')
    for value in (dev,install,controls,cancel):
        assert value['frozen_equal'] and value['frozen_before']==value['frozen_after']==current
    assert cancel['status']=='passed_worker_started_then_cancelled' and len(cancel['calls'])==2
    assert len(current)==212 and dev['status']=='passed_native_cli_contract_quality_separate' and len(dev['checks'])==39
    assert install['status']=='passed' and install['packaged_files']==142 and install['isolated_cli_calls']==19 and install['isolated_module_calls']==1
    assert install['all_rgba_and_pcm_equal_development'] and len(controls['checks'])==20
    assert all(c['passed'] for value in (dev,controls) for c in value['checks'])
    assert skills['skill_count']==17 and skills['local_links_checked']==256
    for value in (dev,install):assert (value['detector_forwards'],value['landmark_forwards'])==(24,20)
    if not args.candidate:
        assert full['terminal_ok'] and full['exit_code']==0 and full['methods']==1536 and full['skipped']==0
        assert full['frozen_equal'] and full['frozen_before']==full['frozen_after']==current
    status='候选，完整回归运行中' if args.candidate else 'CPU 人脸契约限定验收'
    full_note=('完整回归尚未验收，最近已发布 V68 为 1520/1520。' if args.candidate else
               f'完整 **{full["methods"]}/{full["methods"]}、{full["suite_seconds"]:.3f} 秒、0 跳过、212 输入冻结**；16 新契约方法为子集。')
    summary=(f'2026-10-20 **V69（{status}）**：本地 OpenSeeFace 66 点逐帧锚点，显式磨皮/曝光/瘦脸/眼部放大；'
             '默认零强度，缺失/切点清空几何关联，保存完整地标配方并显式重放。'+full_note+
             '开发 **16 次基础 CLI/39 条原检查/24 帧，24 次真实检测＋20 次地标**；四项独立控制另 20 检查、0 新模型前向。'
             '**142 包内资源/7 wheels/19 次基础隔离 CLI＋1 模块来源检查**；开发/安装另各 1 次 worker 启动后取消核验。安装版另 24 检测/20 地标，全部 RGBA/PCM 与开发相同。'
             '**17 Skills/256 引用**。原 Alpha、范围外 RGB、中性输出、逐帧 PTS/PCM、取消/超时回滚通过；'
             'PNG 中文路径和 FFV1 色彩标签失败保留。素材为 NASA 静照生成的平移/空脸段，静看 3 帧和控制联系图，未连续播放/听审；'
             '**自然动态美颜、透明人脸边缘、美妆/身体及完整剪映等价未验收**。')
    publication_failure=BASE/'publication-r1-failure.json'
    if publication_failure.exists():
        summary+='暂存 CRLF 检查曾中止；已保留日志并修正规则，源码与实测文件原字节保留。'
    table='''| 编号 | 核验 | 结果与范围 |
|---|---|---|
| FACE-V01 | 模型/坐标 | 固定 OpenSeeFace，作者预处理与解码对照；66 点不是身份或皮肤精分 |
| FACE-V02 | 真实视频 | 24 帧、4 帧无脸、切点/缺失重置；24 检测/20 地标，不以回调计推理 |
| FACE-V03 | 四项修饰/重放 | 中性 RGBA、原 Alpha、范围外样本、PTS/PCM；保存地标配方重放 0 模型前向 |
| FACE-V04 | 回滚与退出 | 坏选择 2、取消 8、真实超时 6；额外各 1 次证明 worker 启动后取消；作者字节恢复、无半成品、自有进程回收 |
| FACE-V05 | 逐控制 | 4 项独立实际输出、20 检查；不接受自然纹理/遮挡质量 |
| FACE-V06 | 原生发行 | 142 资源、19 基础隔离 CLI＋1 次 worker 取消、1 模块来源检查，全部 RGBA/PCM 与开发相同 |
| FACE-V07 | 完整回归 | FULL_NOTE |
| FACE-V08 | 开放质量 | 静照平移与静帧不能验收自然动态、美妆/身体或完整剪映质量 |
'''.replace('FULL_NOTE',full_note.replace('**',''))
    for name in DOCUMENTS:
        path=ROOT/name;content=summary+' [原片/GIF/失败与发行]('+relative(path,REPORT)+')。'
        if name=='README.md':
            content+='\n\n'+table+'\n原片：[MP4](docs/assets/local-face-beauty-20261020-v69-native-r5/source.mp4)；实际输出：[MP4](docs/assets/local-face-beauty-20261020-v69-native-r5/retouched.mp4)。GIF 左原片、右组合控制；实际 23 帧/2.88 秒/无声，是静照平移技术样例，不代替完整 24 帧视频检查。\n\n![实际局部修饰对照](docs/assets/local-face-beauty-20261020-v69-native-r5/comparison.gif)'
        insert(path,content)
    insert(REPORT,summary)
    report=REPORT.read_text(encoding='utf8')
    report=re.sub(r'^\| FACE-V07 \| 完整回归 \|.*$',
                  '| FACE-V07 | 完整回归 | '+full_note.replace('**','')+' |',report,flags=re.M)
    REPORT.write_text(report,encoding='utf8',newline='\n')
    if publication_failure.exists() and '<!-- V69-PUBLICATION-FAILURE -->' not in report:
        with REPORT.open('a',encoding='utf8',newline='\n') as handle:
            handle.write('\n<!-- V69-PUBLICATION-FAILURE -->\n暂存核验首次因 5 个原生 CRLF 文件的行尾误报而中止，未提交或推送。'
                '仅为这些路径声明 CR 行尾语义，保留空格检查及全部原始字节；无需重跑未变化的 1536 项功能回归。'
                '原始记录：['+publication_failure.name+']('+relative(REPORT,publication_failure)+')。\n')
    contract=CONTRACT.read_text(encoding='utf8')
    contract=re.sub(r'^状态：.*$',('状态：V69 候选；完整回归运行中，真实 CPU 视频契约和原生安装对照通过；自然效果与剪映等价未验收。'
                   if args.candidate else '状态：V69 CPU 人脸契约、原生发行与完整回归限定通过；自然效果与完整剪映等价未验收。'),contract,count=1,flags=re.M)
    CONTRACT.write_text(contract,encoding='utf8',newline='\n')
    path=ROOT/'video-cut-install-manifest.json';mapping=read(path)
    for row in mapping['skills']:
        source=ROOT/'skills'/row['name']/'SKILL.md';checked=next(v for v in skills['results'] if v['skill']==row['name'])
        assert sha(source)==checked['sha256']
        value=checked['sha256'][7:]
        if row['skill_md_sha256']!=value:
            row.setdefault('skill_md_sha256_history',[]).append({'sha256':row['skill_md_sha256'],
                'replaced_at_utc':datetime.now(timezone.utc).isoformat(),'reason':'V69 local face landmarks and bounded CPU retouch'})
            row['skill_md_sha256']=value
        row['description']=re.search(r'^description: (.+)$',source.read_text(encoding='utf8'),re.M)[1].strip('"')
    old=mapping['current_audit'];history=mapping.setdefault('audit_history',[])
    if old.get('record')!=(BASE/'skills-r1.json').relative_to(ROOT).as_posix() and old not in history:history.append(old)
    mapping['current_audit']={'record':(BASE/'skills-r1.json').relative_to(ROOT).as_posix(),'record_sha256':sha(BASE/'skills-r1.json'),
        'checked_at_utc':skills['checked_at_utc'],'skills':17,'local_links_checked':256,
        'semantics':'V69 explicit local face landmarks/CPU retouch; actual source and isolated install contracts; natural quality and full parity unaccepted',
        'candidate':args.candidate}
    path.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({'status':'candidate_documents' if args.candidate else 'terminal_documents','skills':17,'links':256,
                      'full_methods':full.get('methods'),'full_accepted':not args.candidate}))


if __name__=='__main__':main()
