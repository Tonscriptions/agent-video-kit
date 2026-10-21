"""Document the actual eight-wheel installation and fresh media without claiming release."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
from PIL import Image
from run_frozen_regression import frozen

ROOT=Path(__file__).resolve().parents[1]
REL='docs/validation/evidence/offline-media-profile-20261021-lab'
ASSETS='docs/assets/offline-media-profile-20261021-lab'
REPORT='docs/validation/八轮离线媒体运行时独立实验_2026-10-21.md'
CONTRACT='docs/specs/离线媒体运行时与NumPy交付_实验_v0.1_2026-10-21.md'


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def read(path):return json.loads(Path(path).read_bytes())


def save(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    base=ROOT/REL;output=base/'media-audit-r1.json';assert not output.exists()
    current=frozen();development=read(base/'development-audit-r1.json')
    assert current==development['frozen_inputs'] and len(current)==260
    native=read(base/'native-r2/verification.json');installed=read(base/'installed-r1/verification.json')
    media=read(base/'installed-r1/media/verification.json')
    for row in (native,installed,media):
        assert row['status']=='passed' and row['frozen_before']==row['frozen_after']==current and row['frozen_equal']
        assert all(item['ok'] for item in row['checks'])
    for row in (native,media):
        assert row['cli_calls']==23 and row['native_commands']==32 and len(row['checks'])==39
        assert row['cases']==native['cases'] and set(row['cases'])=={'native','offset'}
        assert len(row['media'])==21 and len(row['GIF'])==7
        assert all(item['duration_ms']==3000 for item in row['GIF'].values())
        assert row['script_sha256']==sha(ROOT/'scripts/smoke_audio_source_origin.py')
    assert installed['bundle']['wheels']==8 and installed['installation']['wheels']==8
    assert len(installed['checks'])==20 and installed['isolated_cli_calls']==26 and installed['module_origin_probes']==1
    distribution=installed['numpy_distribution'];assert distribution['base_bundle_includes_numpy'] and not distribution['host_site_copied']
    assert len(distribution['original_wheel_files_except_rewritten_RECORD'])==931 and distribution['notices']
    assert len(installed['installation']['audit']['modules'])==8 and len(distribution['native_audit']['extensions'])==2
    assert len(installed['resource_hashes'])==161
    for name,digest in installed['resource_hashes'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
    first=read(base/'native-r1/verification.json')
    assert first['status']=='failed' and first['cli_calls']==0 and first['native_commands']==0 and first['frozen_equal']
    assets={}
    for row in (native,media):
        for name,details in row['media'].items():
            path=ROOT/name;assert path.resolve().is_relative_to(ROOT/ASSETS) and sha(path)==details['sha256'] and path.stat().st_size==details['bytes']
            assert name not in assets;assets[name]=details
    assert len(assets)==42
    plots={}
    for case in ('native','offset'):
        a=ROOT/ASSETS/'native-r2'/(case+'-decoded-PCM.png');b=ROOT/ASSETS/'installed-r1'/a.name
        with Image.open(a) as left,Image.open(b) as right:
            assert left.size==right.size==(320,160) and left.convert('RGBA').tobytes()==right.convert('RGBA').tobytes()
        plots[case]={'native_path':a.relative_to(ROOT).as_posix(),'native_sha256':sha(a),
            'installed_path':b.relative_to(ROOT).as_posix(),'installed_sha256':sha(b),'pixels_equal':True,
            'observed':'Both actual decoded channels silent for0..1s; original signal at1..3s. Static image review only.'}
    save(base/'static-review-r1.json',{'kind':'actual-decoded-PCM-static-review','plots':plots,
        'audio_listened':False,'continuous_playback_reviewed':False})
    save(base/'media-manifest-r1.json',{'status':'passed','assets':assets,'asset_count':42,'GIF_count':14,
        'new_current_runtime_media':True,'parent_media_reused':False,
        'native_sha256':sha(base/'native-r2/verification.json'),'installed_sha256':sha(base/'installed-r1/verification.json')})
    summary='''独立候选，未合入main、未注册Skill或发布。当前260冻结输入；12新控制及34相关检查通过。新原生和全新8-wheel离线安装的媒体均通过，安装阶段没有复制宿主NumPy。完整2043仅为预计方法数，须先绑定真实发布的V88/2031，尚未启动；完整剪映功能和效果仍未验收。'''
    rows=[
        ('MP-01','父版与改动','259父输入；只修改offline/build.py、offline/install.py和pyproject.toml，新增12方法。当前260输入，161运行时资源保持父版内容。',REL+'/foundation-r1.json'),
        ('MP-02','修复前同12方法','6FAIL、1ERROR、5控制通过；1.169秒/0跳过，保留原代码和原测试。',REL+'/before-r1.json'),
        ('MP-03','修复后与旧安装控制','同12方法1.004秒通过；连同22旧安装方法共34/2.161秒/0跳过，34是未来全量子集。',REL+'/related-offline-r1.json'),
        ('MP-04','固定官方wheel与许可','开发阶段从PyPI取NumPy2.4.2/cp313-win_amd64；932个RECORD文件核对。继承6个运行时依赖，加NumPy与产品共8wheels，原许可逐字保留。',REL+'/wheelhouse-r1.json'),
        ('MP-05','全新离线安装','8模块隔离依赖审计，实际dot=285、2×2求解和FFT；两个.pyd来源均在安装site。931原wheel文件除重写RECORD外全字节一致，原许可同时在包和安装中。',REL+'/installed-r1/verification.json'),
        ('MP-06','原生/安装实际CLI','开发23CLI＋32其他命令/39检查；安装26CLI＋1来源进程/14模块、20安装＋39媒体检查。161资源源码/wheel/site同字节。',REL+'/installed-r1/verification.json'),
        ('MP-07','真实时间戳和完整数据','容器原点0/5秒、音频首PTS1/6秒；每输出75帧/17,280,000RGBA字节、1,152,000float32PCM字节/每声道144000样本，与独立期望相同。',REL+'/native-r2/verification.json'),
        ('MP-08','实际MP4/GIF','42资产/14GIF来自两次新生成；MP4各75帧、PTS=n/25、身份色块最大误差1。AAC每声道144384含填充；不声明编码整帧/PCM一致。',REL+'/media-manifest-r1.json'),
        ('MP-09','复用脚本失败','首轮native-r1在0CLI/0其他命令时因旧实验内部audit路径缺失停止；保留原执行脚本，之后仅改audit路径和260输入绑定，以新目录重跑。',REL+'/media-preparation-r2.json'),
        ('MP-10','未完成及边界','Skill、相关音频/多机位扩大回归、完整2043、生产合入与普通推送待完成。NumPy2.4.2固定版本限定；不提供通用依赖解析器或模型权重。自然/HDR/长片/RSS/播放听审与完整剪映等价未验收。',CONTRACT),
    ]
    documents={}
    for name,title in (('README.md','八轮离线媒体运行时独立实验'),(REPORT,'八轮离线媒体运行时独立实验（2026-10-21）')):
        def link(target):return __import__('os').path.relpath(ROOT/target,(ROOT/name).parent).replace('\\','/')
        text='# '+title+'\n\n'+summary+'\n\n| 编号 | 核验 | 实际结果与边界 | 证据 |\n|---|---|---|---|\n'
        text+='\n'.join('| '+i+' | '+title+' | '+result+' | [记录]('+link(target)+') |' for i,title,result,target in rows)
        text+='\n\n[参考原片]('+link(ASSETS+'/native-r2/source-reference.mkv')+') · [延迟音频输入]('+link(ASSETS+'/native-r2/source-native.mkv')+') · [非零原点输入]('+link(ASSETS+'/native-r2/source-offset.mkv')+') · [实际输出MP4]('+link(ASSETS+'/native-r2/native-output.mp4')+') · [实际同步MP4]('+link(ASSETS+'/native-r2/native-synced.mp4')+')\n'
        text+='\n![真实同步输出]('+link(ASSETS+'/native-r2/native-synced.gif')+')\n\n![实际PCM采样图]('+link(ASSETS+'/native-r2/native-decoded-PCM.png')+')\n'
        text+='\nGIF各3000ms、不含声音。静态检查两张实际PCM图、安装图像素相同；没有播放或听审。原创CC0矩形字形/色卡/确定性音频，无外部字体或图片。\n'
        text+='\n[NumPy官方固定版本](https://pypi.org/project/numpy/2.4.2/)的许可表达式为BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0；逐wheel原通知保全见固定来源记录。源码准备有只读下载，产品构建/安装/运行使用本地wheel且无网络，不创建虚拟环境。\n'
        text+='\n复现：scripts/smoke_audio_source_origin.py、scripts/verify_media_profile_install.py；全部输入和输出须使用新目录，命令、SHA和失败执行副本均保留在对应证据内。\n'
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf8',newline='\n');documents[name]=sha(path)
    contract='''# 离线媒体运行时与NumPy交付（实验v0.1，2026-10-21）

'''+summary+'''

| 编号 | 契约 | 当前证据 |
|---|---|---|
| MP-C01 | core-v1六轮和font-text-v1七轮仅保留原产品包兼容；当前声明NumPy的产品必须media-analysis-v1八轮 | 旧22＋新12方法；真实八轮安装 |
| MP-C02 | wheelhouse目标、完整依赖集合、每个源字节/SHA先核对，再创建构建输出或调用pip | 缺NumPy及篡改源控制通过 |
| MP-C03 | 安装只使用--no-index/--no-deps/--require-hashes/--only-binary本地wheel；不创建venv或修改全局site | 实际构建/安装精确命令 |
| MP-C04 | NumPy及两个原生.pyd必须来自安装site，实际dot、solve和FFT通过后才原子发布安装目录 | 新进程8模块和原生运算收据 |
| MP-C05 | 所有NumPy原wheel文件除pip重写RECORD外字节一致，原许可同时保存在bundle/licenses和安装site | 931文件＋原通知核对 |
| MP-C06 | 宿主NumPy复制不能作为新media-analysis-v1依赖交付证据 | 新验证器删除复制函数；只有wheel路径 |
| MP-C07 | 产品161资源必须在源码/wheel/site中完全相同，切片与同步仍以完整帧/PCM核验 | 两次真实媒体39＋39检查 |
| MP-C08 | 官方NumPy2.4.2/cp313/Windows x64固定wheel；通用版本求解、其他ABI/平台和完整模型发行分别验收 | 当前限定安装；其他未验收 |
| MP-C09 | 开发来源下载与产品安装/运行分别记录；运行时不含下载服务 | wheelhouse来源与安装命令分开保全 |
| MP-C10 | Skill、全量套件、README生产接入及普通推送分别完成；不把34子集或八轮安装当作全部剪映验收 | 未完成 |

[原生、安装、原片/GIF及失败记录](../validation/八轮离线媒体运行时独立实验_2026-10-21.md)。
'''
    path=ROOT/CONTRACT;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(contract,encoding='utf8',newline='\n');documents[CONTRACT]=sha(path)
    assert frozen()==current
    record={'status':'passed-native-and-eight-wheel-isolated-media-awaiting-expanded-regression-and-skills',
        'at_utc':datetime.now(timezone.utc).isoformat(),'frozen_inputs':current,'targeted_methods':34,
        'development_audit_sha256':sha(base/'development-audit-r1.json'),'documents':documents,
        'media':assets,'asset_count':42,'GIF_count':14,'native_cli_calls':23,'native_checks':39,
        'isolated_cli_calls':26,'isolated_installer_checks':20,'isolated_media_checks':39,
        'runtime_resources':161,'base_wheels':8,'numpy_version':'2.4.2','host_numpy_copied':False,
        'original_numpy_files_byte_equal_except_RECORD':931,'native_sha256':sha(base/'native-r2/verification.json'),
        'installed_sha256':sha(base/'installed-r1/verification.json'),'media_manifest_sha256':sha(base/'media-manifest-r1.json'),
        'static_review_sha256':sha(base/'static-review-r1.json'),'wheelhouse_sha256':sha(base/'wheelhouse-r1.json'),
        'expected_future_full_methods':2043,'required_published_parent_methods':2031,'full_suite_started':False,
        'main_integrated':False,'skills_registered':False,'full_capcut_parity':False,'generator_sha256':sha(__file__)}
    save(output,record);links=[]
    for name in documents:
        path=ROOT/name
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',path.read_text('utf8')):
            target=unquote(token.strip('<>').split('#',1)[0])
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:',target):continue
            resolved=(path.parent/target).resolve();assert resolved.is_relative_to(ROOT) and resolved.exists(),(name,target)
            links.append({'document':name,'target':resolved.relative_to(ROOT).as_posix()})
    record['local_links']=links;save(output,record)
    (base/'finalize-media-r1.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':record['status'],'assets':42,'GIFs':14,'frozen_inputs':260,'document_links':len(links)}))


if __name__=='__main__':main()
