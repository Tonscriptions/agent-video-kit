"""Freeze the actual passed native-source experiment, documents and lineage."""
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path
from urllib.parse import unquote
from run_frozen_regression import frozen,sha

ROOT=Path(__file__).resolve().parents[1]
REL=ROOT/'docs/validation/evidence/color-precision-20261021-lab'
REPORT=ROOT/'docs/validation/浮点表面合成与高精度边界独立实测_2026-10-22.md'
CONTRACT=ROOT/'docs/specs/浮点表面合成与高精度边界_实验_v0.1_2026-10-22.md'

def main():
    epoch=REL/'current-epoch-r2.json';assert not epoch.exists()
    current=frozen();kernel=json.loads((REL/'kernel-r8.json').read_bytes());media=json.loads((REL/'native-source-media-r1/verification.json').read_bytes())
    assert kernel['frozen_after']==current==media['frozen_after'] and len(current)==278
    assert kernel['result']['methods']==59 and kernel['result']['terminal_success'] and not kernel['result']['skipped']
    assert media['status']=='passed-native-RGB-YUV-readers-affine-float-media-not-editor-integration'
    resources=sum(k.startswith('product/src/') for k in current);assert resources==169
    backup=REL/'before-native-source-docs-r1';assert not backup.exists();backup.mkdir(parents=True)
    docs=[]
    for p in (REPORT,CONTRACT):
        data=p.read_bytes();(backup/p.name).write_bytes(data);docs.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)})
    (backup/'manifest.json').write_text(json.dumps({'documents':docs},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    snapshots=REL/'implementation-r2';assert not snapshots.exists()
    copied=[]
    for value in sorted(k for k in current if Path(k).name.startswith(('float_','test_float_'))):
        p=ROOT/value;q=snapshots/value;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes());assert sha(q)==current[value]
        copied.append({'path':value,'snapshot':q.relative_to(ROOT).as_posix(),'sha256':current[value]})
    assert len(copied)==11
    (snapshots/'manifest.json').write_text(json.dumps({'status':'exact-current-tested-experimental-implementation','editor_integrated':False,'files':copied},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    lineage=[]
    for name in ('kernel-r3.json','kernel-r4.json','kernel-r5.json','kernel-r6.json','kernel-r7.json','kernel-r8.json',
                 'float-media-r2/verification.json','geometry-media-r1/verification.json','native-source-media-r1/verification.json'):
        p=REL/name;d=json.loads(p.read_bytes());old=d['frozen_after']
        lineage.append({'receipt':name,'sha256':sha(p),'original_status':d['status'],
            'original_frozen_inputs':len(old),'added_since_original':sorted(set(current)-set(old)),
            'removed_since_original':sorted(set(old)-set(current)),
            'modified_common_since_original':[k for k in old if k in current and old[k]!=current[k]]})
    record={'status':'passed-current-native-source-experimental-epoch','created_at_utc':datetime.now(timezone.utc).isoformat(),
        'frozen_inputs':current,'resources':resources,'kernel_methods':59,'recorded_native_kernel_executions':58,
        'kernel_receipt':'kernel-r8.json','historical_lineage':lineage,'implementation_snapshot_sha256':sha(snapshots/'manifest.json'),
        'source_parent':'267 copied V91 inputs before the two-file queue repair; pending rebase to actually published V91',
        'editor_integrated':False,'installed_acceptance':False,'complete_suite_acceptance':False,'HDR_accepted':False,'published':False}
    assert all(not item['removed_since_original'] for item in lineage)
    # Raster/geometry/pixel kernels retain the bytes verified by old media.
    assert not lineage[0]['modified_common_since_original'] and not lineage[1]['modified_common_since_original'] and not lineage[2]['modified_common_since_original']
    epoch.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    text=CONTRACT.read_text('utf8')
    text=text.replace('当前只实现独立 Float32 表面合成核心，尚未接入编辑器、CLI、预览、缓存或离线发行。','当前实现独立 Float32 合成、几何、原生 RGB/灰度与明确 YCbCr 读取核心，尚未接入编辑器时间线、CLI、预览、缓存或离线发行。')
    text=text.replace('两组实际媒体已验证，通用透明源仍待做','历史两组不透明媒体已验证；新增原生 RGB/灰度 alpha 和 YUV/alpha 数值适配，产品接入仍待做')
    text=text.replace('仅图预算实现，宿主生命周期待接入','图/几何/像素预算及原生源取消、提前退出已实现；编辑器宿主生命周期待接入')
    text=text.replace('通用适配仍待接入','原生 RGB 同格式解码后自行归一化，alpha 独立；编辑器接入待做')
    rows='''| FPC-22 | 原生RGB/灰度8–16位整数及Float16/32按原格式解码；分量顺序、端序、MSB填充、alpha表示必须明确，禁止默认swscale归一化 | 原生RGBA16及65536码、格式族、所有权/预算/取消专项通过；不是所有FFmpeg像素格式覆盖 |
| FPC-23 | 原生视频读取须保留源帧PTS/时长、原始时间基；登记SHA、工具与实现字节在交付末帧前重新核验；前缀不能称整源已解码 | 4帧RGB VFR、2帧YUV VFR及20帧实际媒体通过；未自动旋转或CFR重建 |
| FPC-24 | YCbCr需显式矩阵、full/limited和六种色度位置；直接以浮点解算RGB，alpha独立全范围，色度边界复制且双线性；保留超黑/超白 | BT.709、BT.601系及BT.2020 NCL，planar420/422/444、NV12/NV21、P010/12/16数值专项通过 |
| FPC-25 | YCbCr转RGB不等于传递函数/色域转换；源与宿主仍须明确共同工作空间；逐行采样须由调用方声明，不能把未探测字段当成已验收 | 当前仅源RGB数值，scan为调用方声明，隔行、BT.2020 CL、PQ/HLG及显示参考仍待适配 |
| FPC-26 | “无损codec”原片必须逐码验证；仅强制输出色彩标签可能先触发自动YUV→RGB→YUV | 实际失败r7与两轮探针保留；完整输入标签对照65536级及全原码相同 |
| FPC-27 | 读管道4×64KiB stdout、2×64KiB stderr，取消轮询、超时和所属进程/线程清理；单帧工作区预算不代表整体峰值RSS | 实际取消、提前退出和完整读取验证；未验收长片、4K60或进程RSS |
| FPC-28 | 原生读取→仿射→合成→16位无损输出须真实生成样例，再验证浏览MP4/GIF；这仍不能替代编辑器时间线/安装/完整门禁 | 20帧真实媒体、26检查及实际抽帧目检通过；仍未接入编辑器 |
'''
    text=text.replace('\n算法参考：','\n'+rows+'\n算法参考：')
    text+='\nYCbCr来源：[ITU-R BT.709-6](https://www.itu.int/dms_pubrec/itu-r/rec/bt/r-rec-bt.709-6-201506-i!!pdf-e.pdf)、[BT.601-7](https://www.itu.int/dms_pubrec/itu-r/rec/bt/r-rec-bt.601-7-201103-i!!pdf-e.pdf)、[BT.2087的BT.2020 NCL系数](https://www.itu.int/dms_pubrec/itu-r/rec/bt/R-REC-BT.2087-0-201510-I!!PDF-E.pdf)；位置枚举见[FFmpeg pixfmt.h](https://ffmpeg.org/doxygen/7.1/pixfmt_8h.html)。色度边界/双线性是本适配器声明的重建策略，不代表所有codec或隔行格式的规范重建器。\n'
    CONTRACT.write_text(text,encoding='utf8',newline='\n')
    text=REPORT.read_text('utf8');paras=text.split('\n\n')
    paras[1]='本实验建立时主线为V90；V91音频时钟首轮2145完整回归因4个队列问题失败，另行修复后的2148门禁由原发布任务执行，状态以主线README真实收据为准。本实验复制的是V91队列修复前的267产品输入，287个基础文件逐一相等；接入前仍须迁移两个队列文件。不把未通过的父候选称为已发布。'
    seconds=kernel['result']['suite_seconds']
    paras[2]=f'当前六份浮点/原生读取模块和五份测试，278冻结输入、169包内资源；59方法/{seconds:.3f}s/0失败/0错误/0跳过，记录58次原生执行（列表不包含读取器内部的所有ffprobe/摘要检查）。旧12/22/34/44方法的纪元和失败r7分别保留，没有合并计数。[当前纪元及字节桥接](evidence/color-precision-20261021-lab/current-epoch-r2.json)、[11份精确实验源码快照](evidence/color-precision-20261021-lab/implementation-r2/manifest.json)、[完整实验约束](../specs/浮点表面合成与高精度边界_实验_v0.1_2026-10-22.md)。'
    text='\n\n'.join(paras).replace('| CPF-16 | 独立分块几何与合成当前专项 |','| CPF-16 | 历史r4分块几何与合成专项 |')
    rows='''| CPF-19 | 原生RGB/灰度像素边界 | 12个像素方法：原生RGBA16解码、65536码及独立alpha、端序/MSB、整数/Float16/32、分量排列、预算/所有权/取消；[历史34方法r5](evidence/color-precision-20261021-lab/kernel-r5.json)，当前被r8重跑。 |
| CPF-20 | 原生RGB读取与源时钟 | 10方法：4帧VFR绝对PTS=5、5.125、5.375、5.875；逐RGBA16码相同，前缀、取消、提前退出、实际源变化、缓存与共享索引验证；[历史44方法r6](evidence/color-precision-20261021-lab/kernel-r6.json)，当前被r8重跑。 |
| CPF-21 | 当前RGB/YUV/几何/合成专项 | 59方法/0失败/0错误/0跳过；15项YUV测试覆盖矩阵/量程/位深/采样位置/半平面/alpha/逐行声明、独立标量及实际zscale交叉参考；真实2帧YUV VFR保持65536码和源时钟。[当前r8](evidence/color-precision-20261021-lab/kernel-r8.json) |
| CPF-22 | 真实失败：原片生成时被隐式转换 | r7的59方法有1失败；问题在测试原片强制输出标签、输入矩阵未知，编码前自动YUV→RGB→YUV。只补量程仍有最多256码损失；输入标签完整后原生解码全码相同。不是通过放宽精度容差解决。[原失败](evidence/color-precision-20261021-lab/kernel-r7.json)、[r1控制](evidence/color-precision-20261021-lab/yuv-range-probe-r1/verification.json)、[r2控制](evidence/color-precision-20261021-lab/yuv-range-probe-r2/verification.json) |
| CPF-23 | 实际原生源→仿射→浮点合成 | 原生RGBA16及YUV444p16原片，各20帧/10fps/2s；两原片先逐码核验。16条脚本原生命令、另2次读取器解码、26检查、15资产；所有RGB样本对合成公式，3个完整仿射帧对独立标量，再验16-bit回写≤1码、MP4每PTS与GIF每100ms。[实际媒体](evidence/color-precision-20261021-lab/native-source-media-r1/verification.json) |
| CPF-24 | 新媒体目检与限制 | 实际查看一张六帧contact sheet：原始合成/仿射各帧0、9、19；旋转/缩放与透明棋盘符合预期。只作小尺寸抽帧目检，未连续播放、试听、自然素材/HDR验收；当前共同工作空间为作者声明的非线性BT.709。[目检记录](evidence/color-precision-20261021-lab/native-source-review-r1/reviewed.json) |
'''
    text=text.replace('\n\n| 源精度', '\n'+rows+'\n| 源精度')
    text+='\n新增原片：[原生RGBA16](../assets/color-precision-20261021-lab/native-source-media-r1/foreground-16bit.mkv)、[原生YUV16](../assets/color-precision-20261021-lab/native-source-media-r1/background-16bit.mkv)。实际浏览输出：[原始合成MP4](../assets/color-precision-20261021-lab/native-source-media-r1/original.mp4)、[仿射合成MP4](../assets/color-precision-20261021-lab/native-source-media-r1/affine.mp4)、[16位无损合成](../assets/color-precision-20261021-lab/native-source-media-r1/affine-composite-16bit.mkv)。\n\n![原生RGB/YUV源实际合成，浏览副本](../assets/color-precision-20261021-lab/native-source-media-r1/original.gif)\n\n![原生读取、浮点仿射及合成的实际输出；尚未接入编辑器](../assets/color-precision-20261021-lab/native-source-media-r1/affine.gif)\n\n![实际MP4的0/9/19抽帧：上为原始合成，下为仿射](../assets/color-precision-20261021-lab/native-source-review-r1/actual-MP4-frames-0-9-19.png)\n'
    REPORT.write_text(text,encoding='utf8',newline='\n')
    links=[]
    for p in (REPORT,CONTRACT):
        for token in re.findall(r'!?\[[^\]]*\]\(([^)\n]+)\)',p.read_text('utf8')):
            if re.match(r'^[A-Za-z][\w+.-]*:',token):continue
            q=(p.parent/unquote(token.split('#',1)[0])).resolve();assert q.is_relative_to(ROOT) and q.is_file(),token
            links.append({'document':p.relative_to(ROOT).as_posix(),'target':q.relative_to(ROOT).as_posix(),'sha256':sha(q)})
    (REL/'document-links-r3.json').write_text(json.dumps({'status':'passed-current-experimental-document-links','links':links,
        'documents':[{'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)} for p in (REPORT,CONTRACT)],'script_sha256':sha(Path(__file__)),
        'main_modified':False,'published':False},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (REL/'document-native-sources-r1.script.py.txt').write_bytes(Path(__file__).read_bytes())
    assert frozen()==current
    print(json.dumps({'status':'passed-experimental-documents-and-current-epoch','links':len(links),'frozen_inputs':len(current),'resources':resources,'methods':59,'exact_source_snapshots':len(copied)}))
if __name__=='__main__':main()
