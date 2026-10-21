"""Prepare an unpublished README review; never mutates the main checkout."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/color-precision-20261021-lab'
ASSETS='docs/assets/color-precision-20261021-lab'
REPORT='docs/validation/浮点表面合成与高精度边界独立实测_2026-10-22.md'
CONTRACT='docs/specs/浮点表面合成与高精度边界_实验_v0.1_2026-10-22.md'

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    evidence=ROOT/REL;output=evidence/'readme-preview-r1.json'
    path=ROOT/'product/.runtime/color-precision-20261021/readme-preview-r1/README.md'
    assert not output.exists() and not path.parent.exists();path.parent.mkdir(parents=True)
    kernel=json.loads((evidence/'kernel-r4.json').read_bytes());media=json.loads((evidence/'geometry-media-r1/verification.json').read_bytes())
    assert kernel['result']['terminal_success'] and kernel['result']['methods']==22 and not kernel['result']['skipped']
    assert len(kernel['result']['native_calls'])==40 and media['status']=='passed-native-float-geometry-media-not-editor-integration'
    parent=(MAIN/'README.md').read_bytes();seconds=format(kernel['result']['suite_seconds'],'.3f')
    text=f'''<!-- FLOAT-PRECISION-INDEPENDENT-LAB-20261022 -->
### 浮点合成与几何：尚未接入编辑器的独立实验

目标覆盖差异 #112 /#114。以下是实际原片与独立核心的结果；编辑器CLI/预览/缓存/发行接入、统一色彩管理、HDR、完整回归与剪映等价仍待完成。没有把实验模块当作正式产品能力。

| 编号 | 核验内容 | 实际结果与边界 | 证据 |
|---|---|---|---|
| F32-01 | 原编辑器精度失败 | 同原片全幅蒙版，8 CLI＋14其他原生命令；10/16-bit都只余220灰阶。原尺寸直通/crop对照约10-bit精度保留 | [修复前]({REL}/before-r5/verification.json) |
| F32-02 | 当前浮点合成/几何专项 | 22方法/{seconds}s/0失败/0错误/0跳过；其中40次实际FFmpeg，另有NumPy与独立标量几何参考。不是完整回归 | [当前r4]({REL}/kernel-r4.json) |
| F32-03 | 同原片无损码值回写 | 18条原生命令/16检查；两组各786432通道样本全部相同，保留1024/65536灰阶；尚非编辑器CLI的after | [真实媒体]({REL}/float-media-r2/verification.json) |
| F32-04 | 透明度、蒙版与32模式 | straight公共边界、预乘合成，FFmpeg透明度标记明确；常规最大绝对误差1.617e-7，负/高值数值专项不代表HDR | [约束]({CONTRACT}) |
| F32-05 | 几何与运动 | 分块点/双线性仿射，旋转/缩放/位移，透明边缘不串色；预算/取消门禁。20帧实际动画，3个整帧逐通道对独立标量参考 | [实际动画]({REL}/geometry-media-r1/verification.json) |
| F32-06 | 实际浏览视频与GIF | 几何14原生命令/13检查/13资产；每个MP4 PTS与GIF100ms逐帧检查，16-bit精度另对无损码值 | [原始/输出/SHA]({REL}/geometry-media-r1/verification.json) |
| F32-07 | 格式协商问题 | 默认swscale会损16-bit值；scale/pad/rotate/perspective也会经整数；含alpha直接转RGB可能先预乘。探针按本机8.1版本留证 | [全部失败和对照]({REPORT}) |
| F32-08 | 接入与发行状态 | 当前271输入、165资源；复制的V91父版还需队列修复迁移，暂无编辑器/安装/全量/主线发布验收；4张静态PNG目检，未播放/试听 | [范围及原片]({REPORT}) |

[10-bit原片]({ASSETS}/before-r5/10bit-original.mkv) · [16-bit原片]({ASSETS}/before-r5/16bit-original.mkv) · [16-bit无损结果]({ASSETS}/float-media-r2/16bit-float-master.mkv) · [原几何MP4]({ASSETS}/geometry-media-r1/original.mp4) · [实际仿射MP4]({ASSETS}/geometry-media-r1/affine.mp4)

![原创原图实际浏览输出]({ASSETS}/geometry-media-r1/original.gif)

![实际独立浮点仿射合成，未接入编辑器]({ASSETS}/geometry-media-r1/affine.gif)

![实际16-bit原始/浮点结果和码差诊断；误差显示增益64倍]({ASSETS}/float-media-r2/16bit-comparison.png)
<!-- /FLOAT-PRECISION-INDEPENDENT-LAB-20261022 -->'''
    first,body=parent.decode('utf8').split('\n',1);path.write_text(first+'\n\n'+text+'\n'+body,encoding='utf8',newline='\n')
    links=[]
    for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',text):
        assert not re.match(r'^[A-Za-z][\w+.-]*:',token)
        target=ROOT/token;assert target.resolve().is_relative_to(ROOT) and target.is_file(),token
        links.append({'target':token,'sha256':sha(target)})
    candidate=path.read_text('utf8');original=parent.decode('utf8')
    for marker in ('OPENFILM-R15-INCREMENTAL','R14-CURRENT'):
        pattern='<!-- '+re.escape(marker)+' -->.*?<!-- /'+re.escape(marker)+' -->'
        assert re.search(pattern,original,re.S).group()==re.search(pattern,candidate,re.S).group()
    assert (MAIN/'README.md').read_bytes()==parent
    output.write_text(json.dumps({'status':'passed-unpublished-README-preview','prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'path':str(path),'sha256':sha(path),'main_readme_sha256':sha(MAIN/'README.md'),'new_block_links':links,
        'OpenFilm_R14_R15_preserved':True,'main_modified':False,'editor_integrated':False,'published':False,
        'script_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':'passed-unpublished-README-preview','links':len(links),'main_modified':False}))

if __name__=='__main__':main()
