"""Production document projection; an unfinished preview can never write to main."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/multicam-affine-clock-20261021-lab'
ASSETS='docs/assets/multicam-affine-clock-20261021-lab'
REPORT='docs/validation/多机位仿射时钟与浮点音频实测_2026-10-21.md'
CONTRACT='docs/specs/多机位仿射时钟与漂移校准_v0.1_2026-10-21.md'
HISTORICAL_REPORT='docs/validation/多机位仿射时钟与浮点音频独立实验_2026-10-21.md'
HISTORICAL_CONTRACT='docs/specs/多机位仿射时钟与漂移校准_实验_v0.1_2026-10-21.md'
MARKER='V90-MULTICAM-AFFINE-CLOCK'
SKILLS=('video-cut-agent-editor','video-cut-timeline','video-cut-quality','video-cut-video-understand')
LATEST_DOCS=('README.md','docs/README.md','docs/产品需求与开发路线基线_2026-10-12.md','docs/构建进度总表_2026-10-16.md',
 'docs/validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md','docs/Concat与剪映功能差异矩阵_2026-10-12.md')

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(value.rstrip()+'\n',encoding='utf8',newline='\n')

def block(path,value):
    path=Path(path);text=path.read_text('utf8')
    replacement='<!-- '+MARKER+' -->\n'+value.rstrip()+'\n<!-- /'+MARKER+' -->'
    pattern=re.escape('<!-- '+MARKER+' -->')+'.*?'+re.escape('<!-- /'+MARKER+' -->')
    if re.search(pattern,text,re.S):text=re.sub(pattern,lambda _:replacement,text,flags=re.S)
    else:
        at=text.index('\n');text=text[:at]+'\n\n'+replacement+'\n'+text[at:]
    write(path,text)

def relative_links(text,name):
    prefix='../'*(len(Path(name).parts)-1)
    return re.sub(r'(!?\[[^\]]*\]\()docs/',lambda m:m[1]+prefix+'docs/',text)

def documents(root,full):
    root=Path(root).resolve()
    if full is None:
        assert root!=MAIN and root.is_relative_to(ROOT/'product/.runtime')
        summary='文档预览：独立原生/隔离专项已通过；2084完整回归仍待实际终态，未合入main、未注册Skill。'
        full_row='待实际2084完整收据；本预览没有伪造方法数/秒数或通过收据'
    else:
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2084 and full['skipped']==0
        summary=('V90 完整原生回归 **2084 方法/'+format(full['suite_seconds'],'.3f')+'秒/0跳过**；'
            '263产品输入、8外部夹具、14验证脚本和9依赖文件前后相同。'
            '新增显式仿射设备时钟和scalar音频float上采样；默认offset保持不变。合入与注册以发布审计收据为准。')
        full_row='2084方法/'+format(full['suite_seconds'],'.3f')+'秒/0跳过；专项157为其子集，不累计'
    source=(ROOT/'README.md').read_text('utf8')
    body=source[source.index('| 编号'):].split('\n所有原创素材')[0].rstrip()
    old='\n\n[参考短MP4]';assert body.count(old)==1
    rows=('\n| V90-13 | 完整回归 | '+full_row+' | [完整记录]('+REL+'/full-r1.json) |'
        '\n| V90-14 | 生产发布与Skill | 4份变更与原父版逐项校验；发布时再审全部17份注册、链接和源码SHA，保留历史失败。 | [规格]('+CONTRACT+') |')
    body=body.replace(old,rows+old)
    content='### V90 多机位仿射时钟与浮点PCM\n\n'+summary+'\n\n'+body
    modified=set()
    for name in LATEST_DOCS:
        block(root/name,relative_links(content,name));modified.add(name)
    for origin,target in ((HISTORICAL_REPORT,REPORT),(HISTORICAL_CONTRACT,CONTRACT)):
        text=(ROOT/origin).read_text('utf8')
        text=re.sub(r'<!-- MULTICAM-AFFINE-FULL-R1 -->.*?<!-- /MULTICAM-AFFINE-FULL-R1 -->\s*','',text,flags=re.S)
        text=text.replace('本实验另目录推进，不能把其未发布源码当成已安装 Skill 的当前能力。',
            '当前发布产物和注册状态以main字节审计及Skill审计收据为准。')
        text=text.replace(HISTORICAL_CONTRACT.split('/')[-1],CONTRACT.split('/')[-1])
        text=text.replace(HISTORICAL_REPORT.split('/')[-1],REPORT.split('/')[-1])
        first,tail=text.split('\n',1);write(root/target,first+'\n\n'+summary+'\n'+tail)
        modified.add(target)
    drafts=json.loads((ROOT/REL/'skills-draft-r1.json').read_bytes())
    for name in SKILLS:
        row=drafts['skills'][name];text=(ROOT/row['path']).read_text('utf8')
        text=text.replace(HISTORICAL_CONTRACT,CONTRACT).replace(HISTORICAL_REPORT,REPORT)
        text=text.replace('MULTICAM-AFFINE-CLOCK-LAB-20261021',MARKER)
        target='skills/'+name+'/SKILL.md';write(root/target,text);modified.add(target)
    attributes=root/'.gitattributes';text=attributes.read_text('utf8')
    marker='# V90 immutable affine-clock media and execution receipts.'
    assert marker not in text
    text+='\n'+marker+'\n'+REL+'/** -text -whitespace\n'+ASSETS+'/** -text -whitespace\n'
    write(attributes,text);modified.add('.gitattributes')
    return modified
