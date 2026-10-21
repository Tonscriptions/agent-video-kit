# V90 多机位仿射时钟独立实验

当前为独立实验，尚未合入产品或完成完整回归。主产品 V89 已通过 2043 方法并发布；R15 OpenFilm 增量研究已普通推送。这里新增显式 affine 时钟、校准速率和浮点音频重采样修复，后续完整数量预计 **2084**，不能当作已通过。

| 编号 | 核验 | 实际结果 / 边界 | 证据 |
|---|---|---|---|
| V90-01 | 时钟模型 | `source=b+a*reference`；显式 `--clock-model affine`，默认 offset 不变。最多600秒前缀，3–31锚点、4–60秒窗口和20000ppm参数上限，默认5000ppm | [契约](docs/specs/多机位仿射时钟与漂移校准_实验_v0.1_2026-10-21.md) |
| V90-02 | 拟合、绑定和规划方法 | 当前33方法通过，含±漂移、100ppm/600秒、坏锚点、歧义、SHA / ID / digest / inverse / ppm / duration 篡改与覆盖策略 | [记录](docs/validation/evidence/multicam-affine-clock-20261021-lab/after-validation-r2.json) |
| V90-03 | 音频重采样修复前后 | 同8个真实PCM方法：修复前6失败/2对照通过；修复后8通过，5.426秒，0跳过。初轮夹具缺视频导致8ERROR，另存为失败，未当作量化缺陷 | [修复后](docs/validation/evidence/multicam-affine-clock-20261021-lab/audio-precision-after-r2.json) |
| V90-04 | 当前相关回归 | 157个不同方法/283.522秒/0跳过，263输入前后相同；历史141与149是旧源码时点，不与157累计 | [记录](docs/validation/evidence/multicam-affine-clock-20261021-lab/related-r3.json) |
| V90-05 | 真实CLI与远距离选段 | 参考事件覆盖590秒；取0、295、586秒起各4秒。原生39CLI+21其他命令/52检查；两相机真值+1500ppm/-100ppm | [原生](docs/validation/evidence/multicam-affine-clock-20261021-lab/native-r3/verification.json) |
| V90-06 | 独立源帧覆盖 | 固定offset对照最大错21/1源帧，affine两例均0；每个无损输出300帧，24,883,200 RGBA字节，与独立的所选原始帧完全相同 | [实测](docs/validation/多机位仿射时钟与浮点音频独立实验_2026-10-21.md) |
| V90-07 | 参考主音轨 | 每输出每声道576000样本/共4,608,000字节，与先整源float重采样后取样的独立期望逐字节一致；修复8k单声道先s16上采样导致的二次量化 | [诊断](docs/validation/evidence/multicam-affine-clock-20261021-lab/native-r2-mono-format-controls.json) |
| V90-08 | 隔离交付 | 8轮离线包，162资源源码/轮/安装同字节；安装20检查及隔离媒体52检查已通过。wrapper末段字段误读保留failed，由补验闭合 | [原失败wrapper](docs/validation/evidence/multicam-affine-clock-20261021-lab/installed-r1/verification.json) |
| V90-09 | 隔离补验 | -I -S实跑41方法/7.075秒/0跳过；累计43次隔离CLI。补验不重复媒体或安装，不借用父版的成片 | [补验](docs/validation/evidence/multicam-affine-clock-20261021-lab/installed-postflight-r3/verification.json) |
| V90-10 | 媒体资产 | 33资产/9个实际GIF，含短原片、原生/安装输出、原始590秒区间素材和失败夹具；SHA/大小/帧率/时长见清单 | [清单](docs/validation/evidence/multicam-affine-clock-20261021-lab/media-manifest-r1.json) |
| V90-11 | 静态目检 | 实际GIF帧0/100/200，未连续播放或听审。相机采样相位不同，下行事件计数偶尔比参考少1，符合覆盖源帧契约 | [联系表](docs/assets/multicam-affine-clock-20261021-lab/review-r1/actual-frame-contact-sheet.png) |
| V90-12 | 未验收 | 非线性/不连续漂移、真实录制/房间回声/自然质量、完整长片/HDR/RSS与播放听审、全剪映功能等价均未验收。MP4只验PTS和身份码；AAC不宣称全PCM相同 | [报告](docs/validation/多机位仿射时钟与浮点音频独立实验_2026-10-21.md) |

[参考短MP4](docs/assets/multicam-affine-clock-20261021-lab/review-r1/source-selected-reference.mp4) · [参考完整MKV](docs/assets/multicam-affine-clock-20261021-lab/native-r2/source-reference.mkv) · [正漂移输入](docs/assets/multicam-affine-clock-20261021-lab/native-r2/source-positive.mkv) · [小负漂移输入](docs/assets/multicam-affine-clock-20261021-lab/native-r2/source-small-negative.mkv)

![参考三个原片区间](docs/assets/multicam-affine-clock-20261021-lab/review-r1/source-selected-reference.gif)

固定偏移对照与仿射结果（实际MP4解码制作）：

![正漂移固定偏移](docs/assets/multicam-affine-clock-20261021-lab/native-r3/positive-offset.gif)

![正漂移仿射校准](docs/assets/multicam-affine-clock-20261021-lab/native-r3/positive-affine.gif)

所有原创素材CC0；仅原生Windows，没有Docker/WSL/虚拟环境。源码冻结263输入；主分支仍为已发布产品，当前实验未发布。
