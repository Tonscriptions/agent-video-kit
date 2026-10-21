"""Build a concrete README review from the passed native-source receipts."""
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MAIN=Path('E:/dev/sandbox/AI广告剪辑')
REL='docs/validation/evidence/color-precision-20261021-lab'
ASSETS='docs/assets/color-precision-20261021-lab'
REPORT='docs/validation/浮点表面合成与高精度边界独立实测_2026-10-22.md'
CONTRACT='docs/specs/浮点表面合成与高精度边界_实验_v0.1_2026-10-22.md'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    evidence=ROOT/REL;output=evidence/'readme-preview-r2.json'
    target=ROOT/'product/.runtime/color-precision-20261021/readme-preview-r2/README.md'
    assert not output.exists() and not target.parent.exists();target.parent.mkdir(parents=True)
    kernel=json.loads((evidence/'kernel-r8.json').read_bytes());native=json.loads((evidence/'native-source-media-r1/verification.json').read_bytes())
    assert kernel['result']['methods']==59 and kernel['result']['terminal_success'] and not kernel['result']['skipped']
    assert len(kernel['result']['native_calls'])==58 and native['status'].startswith('passed-') and len(native['checks'])==26
    parent=(MAIN/'README.md').read_bytes();seconds=f"{kernel['result']['suite_seconds']:.3f}"
    block=f'''<!-- FLOAT-PRECISION-INDEPENDENT-LAB-20261022 -->
### 浮点合成、几何与原生 RGB/YUV：独立实验

这组原片、代码与结果面向差异 #112 /#114。当前尚未接入编辑器时间线、CLI、预览、缓存或离线发行；共同工作空间、传递函数/色域转换、HDR、完整回归与剪映等价仍待完成。

| 编号 | 核验内容 | 实际结果与边界 | 证据 |
|---|---|---|---|
| F32-01 | 原编辑器精度失败 | 同原片全幅蒙版，8 CLI＋14其他原生命令；10/16-bit都只余220灰阶。原尺寸直通/crop对照保留约10-bit精度 | [实际before]({REL}/before-r5/verification.json) |
| F32-02 | 当前浮点/原生读取专项 | 59方法/{seconds}s/0失败/0错误/0跳过；58条原生执行记录（内部全部探测未计入），另有独立NumPy/标量参考；不是完整回归 | [当前r8]({REL}/kernel-r8.json) |
| F32-03 | 同原片无损码值回写 | 18条原生命令/16检查；两组各786432通道样本全部相同，保留1024/65536灰阶；尚非编辑器CLI的after | [真实媒体]({REL}/float-media-r2/verification.json) |
| F32-04 | 透明度、蒙版与32模式 | straight公共边界、预乘合成；28可分离/4非分离模式；常规最大绝对误差1.617e-7，负/高数值专项不代表HDR | [约束]({CONTRACT}) |
| F32-05 | 几何与运动 | 分块点/双线性仿射，旋转/缩放/位移，透明边缘不串色；预算/取消门禁；3个完整帧对独立标量参考 | [历史几何实测]({REL}/geometry-media-r1/verification.json) |
| F32-06 | 原生RGB/灰度像素 | 8–16位整数、Float16/32，端序/MSB/分量顺序与独立alpha明确，65536码及真实RGBA16解码验证；不宣称全部像素格式 | [当前精确源码]({REL}/implementation-r2/manifest.json) |
| F32-07 | 原生源时钟与生命周期 | 4帧RGB VFR与2帧YUV VFR原PTS保留；源/工具/实现SHA、取消、提前退出、前缀、索引复用验证 | [实际r8]({REL}/kernel-r8.json) |
| F32-08 | 明确YCbCr边界 | 显式矩阵/量程/六种色度位置，直接浮点解码；planar420/422/444、NV12/21、P010/12/16；逐行为调用方声明，未作传递函数/色域转换 | [规范与限制]({CONTRACT}) |
| F32-09 | 原片生成的真实失败 | 强制输出标签、缺少输入标签会自动YUV→RGB→YUV，造成码值丢失；r7有1失败。修正输入标签并先逐码核验原片后通过 | [失败/完整对照]({REL}/yuv-range-probe-r2/verification.json) |
| F32-10 | 原生读取→仿射→合成→编码 | 原生RGB/YUV原片各20帧；16条脚本原生命令、另2次源解码、26检查、15资产。所有合成通道、16-bit≤1码及每MP4 PTS/GIF时长验证 | [真实链路]({REL}/native-source-media-r1/verification.json) |
| F32-11 | 抽帧目检 | 实际MP4的0/9/19共6帧；旋转/缩放与透明棋盘符合预期。未连续播放、试听或自然素材/HDR验收 | [实际目检]({REL}/native-source-review-r1/reviewed.json) |
| F32-12 | 源码和发行状态 | 当前278冻结输入、169资源；各历史纪元/失败保留；复制父版的两个队列文件待迁移，暂无编辑器/安装/全量/主线发布验收 | [纪元桥接]({REL}/current-epoch-r2.json) |

[原生RGBA16原片]({ASSETS}/native-source-media-r1/foreground-16bit.mkv) · [原生YUV16原片]({ASSETS}/native-source-media-r1/background-16bit.mkv) · [原始合成MP4]({ASSETS}/native-source-media-r1/original.mp4) · [实际仿射MP4]({ASSETS}/native-source-media-r1/affine.mp4) · [16-bit无损结果]({ASSETS}/native-source-media-r1/affine-composite-16bit.mkv) · [完整原片/失败与限制]({REPORT})

![原生RGB/YUV原始合成的实际浏览输出]({ASSETS}/native-source-media-r1/original.gif)

![原生读取、浮点仿射和合成，尚未接入编辑器]({ASSETS}/native-source-media-r1/affine.gif)

![实际MP4抽帧：上方原始合成，下方仿射；列为0/9/19帧]({ASSETS}/native-source-review-r1/actual-MP4-frames-0-9-19.png)
<!-- /FLOAT-PRECISION-INDEPENDENT-LAB-20261022 -->'''
    original=parent.decode('utf8');assert '<!-- FLOAT-PRECISION-INDEPENDENT-LAB-20261022 -->' not in original
    first,body=original.split('\n',1);target.write_text(first+'\n\n'+block+'\n'+body,encoding='utf8',newline='\n')
    candidate=target.read_text('utf8');links=[]
    for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',block):
        p=ROOT/token;assert p.resolve().is_relative_to(ROOT) and p.is_file(),token
        links.append({'target':token,'sha256':sha(p)})
    for marker in ('OPENFILM-R15-INCREMENTAL','R14-CURRENT'):
        pattern='<!-- '+re.escape(marker)+' -->.*?<!-- /'+re.escape(marker)+' -->'
        assert re.search(pattern,original,re.S).group()==re.search(pattern,candidate,re.S).group()
    assert (MAIN/'README.md').read_bytes()==parent
    output.write_text(json.dumps({'status':'passed-unpublished-native-source-README-preview','prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'path':str(target),'sha256':sha(target),'main_readme_sha256':sha(MAIN/'README.md'),'new_block_links':links,
        'OpenFilm_R14_R15_preserved':True,'main_modified':False,'editor_integrated':False,'published':False,
        'script_sha256':sha(Path(__file__))},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    output.with_suffix('.script.py.txt').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({'status':'passed-unpublished-native-source-README-preview','links':len(links),'main_modified':False}))
if __name__=='__main__':main()
