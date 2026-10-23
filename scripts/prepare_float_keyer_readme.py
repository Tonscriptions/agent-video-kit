"""Prepare an honest candidate README and verify its virtual publication links."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL=ROOT/'docs/validation/evidence/float-keyer-20261023-lab'
WORK=ROOT/'product/.runtime/float-keyer-20261023/readme-preview-r1'
REPORT='docs/validation/连续浮点色度抠像与去溢色实测_2026-10-23.md'
CONTRACT='docs/specs/连续浮点色度抠像与去溢色契约_v0.1_2026-10-23.md'


def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    WORK.mkdir(parents=True,exist_ok=False)
    native=json.loads((REL/'native-r2/verification.json').read_bytes())
    media=json.loads((REL/'media-r1/verification.json').read_bytes())
    fourk=json.loads((REL/'4k-r1/verification.json').read_bytes())
    assert native['status']=='passed' and native['methods']==177 and native['skipped']==0
    assert media['status']=='passed-public-CLI-floating-keyer-and-native-float-previews'
    assert fourk['status']=='passed-actual-default-budget-4K-formal-preview-and-independent-pixels'
    assert native['frozen_before']==native['frozen_after']==media['frozen_before']==media['frozen_after']==fourk['frozen_before']==fourk['frozen_after']
    section='''<!-- R110-FLOAT-KEYER-CANDIDATE -->
### R110 色度抠像候选：源码与实际媒体已核验

共同 Float32 效果链新增 RGB/色度抠像、连续软边、分数羽化、去溢色和八个作者动画通道。候选尚未独立安装、完整回归或发布；前序 2,537 项完整回归的 1 失败/1 错误已保留，后续采用新冻结快照恢复，不能把推导目标登记为通过。

| 编号 | 实际功能性核验 | 结果 | 原始证据 |
|---|---|---|---|
| K110-01 | 独立数学、原生 RGB8/16/YUV8/16、作者时钟、alpha、取消与预算 | 55 新方法，177 项关联回归通过，0 跳过；330 输入前后 SHA 相同 | [收据](docs/validation/evidence/float-keyer-20261023-lab/native-r2/verification.json) |
| K110-02 | 五种场景两秒原创素材，经公开 CLI render/preview | 20 调用/31 核验；2,419,200 RGB 值最大绝对误差 1.49e-8；原片、输出与音频可下载 | [编号实测及原片](docs/validation/连续浮点色度抠像与去溢色实测_2026-10-23.md) |
| K110-03 | 默认预算 4K RGB/色度/去溢色各单帧 | 19 调用/33 核验；99,532,800 RGBA 分量最大误差 0；不代表长片或 RSS 验收 | [4K 收据](docs/validation/evidence/float-keyer-20261023-lab/4k-r1/verification.json) |
| K110-04 | 五场景静态查看及失败公开 | 10 面板已查看；有残色，未验收自然人物/HDR、连续播放或听音；首轮 2 失败/1 错误保留 | [查看记录](docs/validation/evidence/float-keyer-20261023-lab/static-review-r2.json) · [首轮失败](docs/validation/evidence/float-keyer-20261023-lab/native-r1/verification.json) |

![选定帧的原片与输出对照](docs/assets/float-keyer-20261023-r1/comparison.gif)

[输入 MP4](docs/assets/float-keyer-20261023-r1/original.mp4) · [输出 MP4](docs/assets/float-keyer-20261023-r1/edited.mp4) · [作者契约](docs/specs/连续浮点色度抠像与去溢色契约_v0.1_2026-10-23.md)。需显式选择 `float32-native-v1`；完整剪映功能和观感等价仍未完成。
<!-- /R110-FLOAT-KEYER-CANDIDATE -->
'''
    content=(MAIN/'README.md').read_text('utf8');assert 'R110-FLOAT-KEYER-CANDIDATE' not in content
    title,rest=content.split('\n',1)
    docs={'README.md':title+'\n\n'+section+'\n'+rest,REPORT:(ROOT/REPORT).read_text('utf8'),CONTRACT:(ROOT/CONTRACT).read_text('utf8')}
    content=(MAIN/'docs/README.md').read_text('utf8');title,rest=content.split('\n',1)
    docs['docs/README.md']=title+'\n\nR110 色度抠像候选：[实测、原片与失败](validation/连续浮点色度抠像与去溢色实测_2026-10-23.md) · [作者契约](specs/连续浮点色度抠像与去溢色契约_v0.1_2026-10-23.md)。独立安装/完整回归/发布尚未完成。\n'+rest
    for name,text in docs.items():
        path=WORK/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf8',newline='\n')
    references=[]
    for name,text in docs.items():
        for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            if link.startswith(('https:','http:','codex:','app:','#')):continue
            destination=Path(os.path.abspath((WORK/name).parent/unquote(link.split('#',1)[0].strip('<>'))))
            relative=destination.relative_to(WORK)
            assert any((base/relative).exists() for base in (WORK,ROOT,MAIN)),(name,link)
            references.append({'document':name,'target':relative.as_posix()})
    receipt=dict(status='passed-unpublished-candidate-documents-and-virtual-links',
        at_utc=datetime.now(timezone.utc).isoformat(),documents={n:sha(WORK/n) for n in docs},
        virtual_publication_links=len(references),source_methods=177,installed_run=False,
        full_run=False,published=False,main_mutated=False,new_tests_executed=0,
        actual_source_receipt_sha256=sha(REL/'native-r2/verification.json'),full_capcut_parity=False)
    (WORK/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:receipt[k] for k in ['status','virtual_publication_links','published']},ensure_ascii=False))


if __name__=='__main__':main()
