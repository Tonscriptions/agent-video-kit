"""Refresh installed/full status only from actual terminal receipts."""
from datetime import datetime,timezone
import argparse,json,re,shutil
from pathlib import Path
from float_release_docs import ROOT,MAIN,REL,REPORT,CONTRACT,GUIDE
from run_frozen_regression import frozen,sha

def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['install','full'],required=True);args=parser.parse_args()
    base=ROOT/REL;output=base/('finalize-'+args.stage+'-r1.json');assert not output.exists()
    installed=json.loads((base/'installed-r1/verification.json').read_bytes())
    assert installed['status'].startswith('passed-fresh-eight-wheel') and installed['isolated_methods']['methods']==117
    current=frozen();assert current==installed['frozen_before']==installed['frozen_after'] and len(current)==282
    status='完整2234项原生回归仍在运行，尚未取得通过终态；未合入、未推送。'
    full=None
    if args.stage=='full':
        owner=ROOT/'product/.runtime/color-precision-20261021/complete-r1/run.json'
        state=json.loads(owner.read_bytes());full=json.loads((base/'full-r1.json').read_bytes())
        assert state['status']=='passed-complete-native-suite-not-published'
        assert full['status']=='passed' and full['terminal_ok'] and full['methods']==2234 and full['skipped']==0
        assert full['frozen_before']==full['frozen_after']==current and full['external_fixtures_equal'] and full['verification_scripts_equal']
        assert state['full_receipt_sha256']==sha(base/'full-r1.json')
        for key in ('verification_scripts','dependency_artifact_inputs','bound_evidence'):
            for name,digest in state[key].items():assert sha(ROOT/name)==digest,name
        assert len(state['verification_scripts'])==17 and len(state['dependency_artifact_inputs'])==9
        for name,row in full['external_fixtures_expected'].items():assert sha(ROOT/name)==row['sha256']
        gate={**state,'status':'passed-complete-extra-frozen-inputs','owner_receipt_sha256':sha(owner),
            'script_sha256':sha(Path(__file__)),'complete_methods':2234,'skipped':0,'published':False}
        save(base/'complete-gate-r1.json',gate)
        status='完整原生回归 **2234方法 /'+format(full['suite_seconds'],'.3f')+'秒 /0跳过**；282产品输入、8外部夹具、17启动脚本和9依赖文件相同，终态OK。尚未合入或推送。'
    backup=base/('before-finalize-'+args.stage+'-r1');backup.mkdir()
    originals={}
    for name in (REPORT,CONTRACT):
        p=ROOT/name;originals[name]=sha(p);shutil.copyfile(p,backup/p.name)
    marker='FLOAT-CLI-RELEASE-GATES'
    block=('<!-- '+marker+' -->\n'+status+'\n\n新八轮离线安装：**117项 /288.585秒 /0跳过**，171资源source/wheel/site一致、NumPy931原文件及许可相同；213个运行模块来自安装site，18次子进程CLI。四份安装版帧包的像素/时钟与开发版逐字节一致，独立线性合成RGBA相同。普通时间线render/preview/cache尚未采用浮点核心。\n<!-- /'+marker+' -->')
    for name in (REPORT,CONTRACT):
        p=ROOT/name;t=p.read_text('utf8')
        pattern=re.escape('<!-- '+marker+' -->')+'.*?'+re.escape('<!-- /'+marker+' -->')
        if re.search(pattern,t,re.S):t=re.sub(pattern,lambda _:block,t,flags=re.S)
        else:first,body=t.split('\n',1);t=first+'\n\n'+block+'\n'+body
        if args.stage=='full':
            t=t.replace('**2234项完整原生回归已启动，尚未取得通过终态。**',status)
            t=t.replace('完整2234项正在执行，未宣称通过、合入或推送。','完整2234项已取得实际终态，通过；合入与推送另由发布审计核验。')
            t=t.replace('V91实际发布父版已对齐；完整2234已启动，隔离安装/文档/Skills/推送须取得各自终态','V91父版已对齐；完整2234与独立安装117已实际通过，文档/Skills及普通推送由发布审计核验')
        t=t.replace('以独立安装收据终态为准，不能借宿主site-packages替代','新八轮安装117项/0跳过、213模块来源与171资源及931 NumPy文件相同；未借宿主包替代')
        if name==REPORT and args.stage=='install':
            point=t.index('\n\n',t.index('| CPF-31 |'))
            row='\n| CPF-32 | 当前全新八轮离线安装 | 117项/288.585秒/0跳过；171产品资源、931 NumPy原文件/许可逐字节相同，213模块来自安装site；18次子进程CLI，另进程内调用单独记录。四包像素/时钟和两组线性合成RGBA与开发版相同。[实际安装](evidence/color-precision-20261021-lab/installed-r1/verification.json)、[安装版新生成媒体](evidence/color-precision-20261021-lab/surface-cli-media-installed-r1/verification.json) |'
            t=t[:point]+row+t[point:]
        if args.stage=='full':
            prefix='../' if name==REPORT else '../validation/'
            t+='\n完整终态：[2234项原始收据]('+prefix+'evidence/color-precision-20261021-lab/full-r1.json)、[额外冻结门禁]('+prefix+'evidence/color-precision-20261021-lab/complete-gate-r1.json)。\n' if name==CONTRACT else '\n完整终态：[2234项原始收据](evidence/color-precision-20261021-lab/full-r1.json)、[额外冻结门禁](evidence/color-precision-20261021-lab/complete-gate-r1.json)。\n'
        p.write_text(t.rstrip()+'\n',encoding='utf8',newline='\n')
    rows=[]
    asset_root=ROOT/'docs/assets/color-precision-20261021-lab'
    for p in sorted(asset_root.rglob('*')):
        if p.is_file():rows.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)})
    inventory={'status':'actual-generated-media-inventory','at_utc':datetime.now(timezone.utc).isoformat(),
        'files':rows,'files_count':len(rows),'bytes_total':sum(r['bytes'] for r in rows),'script_sha256':sha(Path(__file__)),
        'rights':'Original deterministic procedural media, CC0-1.0. No outside media/font/model.',
        'includes_historical_and_failed_experiments':True,'new_current_media_only_is_not_inventory_total':True,
        'continuous_playback_reviewed':False,'HDR_accepted':False,'natural_quality_accepted':False}
    save(base/('media-inventory-'+args.stage+'-r1.json'),inventory)
    assert frozen()==current
    save(backup/'manifest.json',{'reason':args.stage+' actual terminal status projection','documents':originals})
    save(output,{'status':'passed-actual-'+args.stage+'-document-projection','at_utc':datetime.now(timezone.utc).isoformat(),
        'documents':{name:sha(ROOT/name) for name in (REPORT,CONTRACT,GUIDE)},'frozen_equal':True,'published':False,
        'installed_methods':117,'complete_methods':full['methods'] if full else None,
        'asset_files':len(rows),'asset_bytes':inventory['bytes_total'],'script_sha256':sha(Path(__file__))})
    output.with_suffix('.executed.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'stage':args.stage,'status':'passed','asset_files':len(rows),'asset_bytes':inventory['bytes_total']}))

if __name__=='__main__':main()
