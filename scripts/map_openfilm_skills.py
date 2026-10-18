"""Read-only mapping of pinned upstream playbooks to current local CLI names."""
import ast,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
REF='eefd6a8d379289102141359a4718dbab12170526'
ROWS=[
 ('S01','replicate',[('media','understand'),('timeline','compose'),('motion','apply'),('quality','golden'),('rights','check')],'参考片时刻/镜头/动作/声音对照和偏差报告','自动视觉语义拆解、完整风格复刻、自然广告质量；参考片不能自动成为可发布素材'),
 ('S02','screen-demo',[('media','smart-cut'),('media','track'),('media','reframe'),('motion','apply'),('timeline','compose')],'真实录屏裁剪、等待段计划、追焦/放大和速度披露','界面语义/点击自动定位、隐私逐帧审查、实时录屏入口；跟踪存在不等于理解操作'),
 ('S03','long-to-short',[('subtitle','transcribe'),('subtitle','segment'),('media','highlights'),('media','reframe'),('timeline','edit')],'完整意思的选段卡、问答/限定条件保留、竖屏重构图和字幕流程','稳定逐词强制对齐、语义完整性、通用说话人/高光选择质量；候选分数不能直接视为好内容'),
 ('S04','keynote',[('ad','plan'),('ad','apply'),('motion','html-source'),('motion','html-render'),('template','apply')],'一项主张配真实产品证据、可编辑标题/数字、品牌素材编排','真实产品素材、事实校核、完整发布片美学和品牌一致性；不用远程页面抓取补缺'),
 ('S05','motion-graphics',[('motion','html-controls'),('motion','html-render'),('motion','html-quality'),('fragment','apply')],'主题化图表/标题与参数替换、可重建动效和全帧质量报告','复杂字形/变换、Canvas语义、WebGL/完整媒体、品牌美学；不把门禁通过等同高级动效'),
 ('S06','presenter-pip',[('media','matting'),('media','track-bind'),('timeline','compose'),('subtitle','transcribe')],'讲解画中画、内容/字幕安全区、配合讲话切换信息','稳定词级同步、头发/手持物边缘、遮挡与自动内容重点理解，需自然长片验证'),
 ('S07','lyric-video',[('subtitle','normalize'),('subtitle','segment'),('timeline','compose'),('motion','apply')],'歌词原文/行次保持、字词动效与独立时间误差报告','上游要求歌词在两帧内落在歌声上；没有本轮独立强制对齐实测，不能靠估时满足'),
 ('S08','collage',[('media','ingest'),('media','mask-edit'),('timeline','compose'),('fragment','save')],'有来源的照片/纸片/文字拼贴、蒙版和可复用包装组','授权素材库、自然拼贴风格和人物真实性；模板库尚不等于版权素材商城'),
 ('S09','whiteboard',[('motion','html-source'),('motion','html-render'),('tts','synthesize'),('timeline','compose')],'逐笔绘制与解说节点的设计和误差报告','可解释的笔画路径、逐词/逐笔对齐和自然成片；整图淡入不能代替逐笔绘制'),
 ('S10','vintage-film',[('lut','register'),('timeline','compose'),('timeline','transition'),('audio','extract')],'保留人脸/事件的原貌、按授权时间顺序组织回忆片和调色','特定胶片材质/颗粒组合、自然美学、真实元数据；不自动修脸/扩图/生成人物动作'),
]


def run():
    output=ROOT/'docs/validation/evidence/openfilm-skill-local-mapping-20261018.json';assert not output.exists()
    cli=ROOT/'product/src/ai_ad_editor/cli.py';tree=ast.parse(cli.read_text(encoding='utf-8'))
    dispatch=next(node.value for node in tree.body if isinstance(node,ast.AnnAssign) and isinstance(node.target,ast.Name) and node.target.id=='COMMANDS')
    commands={ast.literal_eval(key) for key in dispatch.keys};archive=ROOT/'sources/upstream/openfilm-0.2.0/repo.zip';rows=[]
    digest=lambda raw:'sha256:'+hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(archive) as source:
        for number,name,mapped,reuse,gaps in ROWS:
            tail='/packages/openfilm/skills/'+name+'/SKILL.md';members=[n for n in source.namelist() if n.endswith(tail)];assert len(members)==1
            assert set(mapped)<=commands,(name,set(mapped)-commands);raw=source.read(members[0])
            rows.append({'id':number,'skill':name,'source_path':members[0].split('/',1)[1],'source_sha256':digest(raw),'source_lines':len(raw.splitlines()),'mapped_cli_dispatch_names':[' '.join(x) for x in mapped],'reusable_workflow':reuse,'unaccepted_capabilities':gaps,'new_skill_installed':False,'workflow_executed_this_research':False})
    record={'status':'static_mapping_verified','checked_at_utc':datetime.now(timezone.utc).isoformat(),'source_commit':REF,'archive_sha256':digest(archive.read_bytes()),'current_cli_source_sha256':digest(cli.read_bytes()),'dispatch_names_checked':len(commands),'upstream_skills_checked':len(rows),'rows':rows,'meaning':'Dispatch names and pinned source were read; not a claim that these workflows ran or their quality passed','runtime_network':False,'new_model_inference':0,'new_rendered_frames':0,'browser_tabs_opened':0,'virtualization':False,'generator_sha256':digest(Path(__file__).read_bytes())}
    output.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'skills':len(rows),'dispatch_names':len(commands),'status':record['status']}))


if __name__=='__main__':run()
