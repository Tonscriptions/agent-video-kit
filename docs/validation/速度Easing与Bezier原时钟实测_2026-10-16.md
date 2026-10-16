# 速度 Easing 与 Bezier 原时钟实测

| 字段 | 内容 |
|---|---|
| 状态 | 有效 |
| 日期 | 2026-10-16 |
| 对应 README | V20；V13 更新为本轮完整回归 |
| 运行 | 原生 Windows、Python、本机 FFmpeg；无 Docker/WSL/线上服务/新模型实测推理 |
| 固定旧版 | `b0d0f42e394bb11f95cfec2f2d187e7fb9af7445`，本地 Git 归档真实执行 |
| 契约与实现 | [速度曲线契约](../specs/速度曲线Easing与Bezier契约_v0.1_2026-10-16.md)、[编译器](../../product/src/ai_ad_editor/speed_curves.py) |
| 证据 | [公开逐帧/调用记录](../assets/speed-easing-20261016/evidence.json)、[独立积分/解码与源码冻结](./evidence/speed-easing-20261016.json)、[交付质量](./evidence/speed-easing-quality-20261016.json) |

## 1. 原问题及实现

此前格式允许 ease_in/out/in_out/Bezier，但速度渲染器只连接端点速率，曲线含义没有执行。本轮补入真实 easing、二元/四元句柄、正速度检查及有界源积分编译；直接片段、嵌套视频、原作者动画及音频累计边界共用同一源时钟。没有新增 CLI 参数。

编译器对 Bernstein 控制差值建立保守积分误差界，单条未归一化源积分上界为 250 μs；达到 1024 段或细分预算仍不能满足时明确拒绝。归一化层的上界另计为 2×源界×curve_scale，外层组合又会改变误差，不能把 250 μs 当成整条成片的统一保证。单条属性时钟中间表达式另有 4 MiB 门限。真正的群组语义和广泛自然画质继续未验收。

## 2. 七组实际前后成片

自制输入为 512×288、24 fps、3 秒、72 帧，含可读源帧号和 7 位编码。七份新输出合计 **336 帧**，全部解码核对；源帧门槛保持≤1、动画宽度门槛≤3 px。本批新成片实测恰为 0 源帧误差，不将零误差推广到 VFR、其他帧率或任意项目。

| 编号 | 场景 | 新帧数 | 最大源帧误差：旧→新 | 脉冲窗口不匹配：旧→新 | 动画宽度最大误差 | 正式发布成片 |
|---|---|---:|---:|---:|---|---|
| E01 | ease_in 正放 | 59 | 4→0 | 3→0 | — | [旧](../assets/speed-easing-20261016/before-forward.mp4) / [新](../assets/speed-easing-20261016/after-forward.mp4) |
| E02 | ease_out 倒放 | 31 | 3→0 | 1→0 | — | [旧](../assets/speed-easing-20261016/before-ease_out_reverse.mp4) / [新](../assets/speed-easing-20261016/after-ease_out_reverse.mp4) |
| E03 | ease_in_out | 48 | 7→0 | 8→0 | — | [旧](../assets/speed-easing-20261016/before-in_out.mp4) / [新](../assets/speed-easing-20261016/after-in_out.mp4) |
| E04 | 二元 Bezier 句柄 | 46 | 4→0 | 2→0 | — | [旧](../assets/speed-easing-20261016/before-bezier_two.mp4) / [新](../assets/speed-easing-20261016/after-bezier_two.mp4) |
| E05 | 四元 Bezier 句柄 | 57 | 2→0 | 0→0 | — | [旧](../assets/speed-easing-20261016/before-bezier_four.mp4) / [新](../assets/speed-easing-20261016/after-bezier_four.mp4) |
| E06 | Bezier 与子层缩放动画 | 57 | 2→0 | 0→0 | 8.1369→0.9911 px | [旧](../assets/speed-easing-20261016/before-animated.mp4) / [新](../assets/speed-easing-20261016/after-animated.mp4) |
| E07 | 两层非线性曲线与双倒放 | 38 | 2→0 | 0→0 | — | [旧](../assets/speed-easing-20261016/before-compound.mp4) / [新](../assets/speed-easing-20261016/after-compound.mp4) |

bezier_four、animated 和 compound 的旧音频本来就没有检出脉冲包络不匹配，不能宣传成这些音频指标改善。幅度脉冲不代表自然音乐、相位、音色或口型同步；没有听审。

## 3. 两种独立数学与实际像素核对

生成器/专项使用源坐标复合 Simpson 积分，以二分法反算 Bezier x；产品使用控制曲线细分和对数积分，二者没有互相导入。独立交付核对再从实际 CLI authoring operations 重建曲线，改在参数 u 中用 64 节点 Gauss 积分计算 x′(u)/v(u)，并重新解码全部输出的帧号、几何和音频。

对本批 8 条曲线映射分别核对 513 个位置：未归一化积分最大观察误差 **73.1235 μs**，时长归一化后最大观察误差 **33.1145 μs**，均在各自 certificate 上界内。这是这批位置上的独立测量；数学界来自编译器的保守控制差值，并非用离散最大值替代全域界。

音频为 3 秒、48 kHz、双声道 PCM16 的 400 Hz 高/低幅原 WAV。编码输出以 RMS 0.15 分类，排除距 0.6/0.9/1.8/2.1 源秒边界不足 0.10 **源秒**的窗口；七组新结果均无不匹配。源帧选择按公共 CFR 网格核对，数值边界留 20 μs 的既有比较容差，不改变≤1 源帧门槛。

## 4. 原输入与可视演示

![原视频前缀、旧版线性化与真实速度 easing](../assets/speed-easing-20261016/speed-easing-comparison.gif)

[完整原视频](../assets/speed-easing-20261016/source.mp4) · [原始脉冲 WAV](../assets/speed-easing-20261016/pulses.wav) · [对比 MP4](../assets/speed-easing-20261016/speed-easing-comparison.mp4) · [作者时间线](../assets/speed-easing-20261016/authored-timelines.json) · [来源与许可](../assets/speed-easing-20261016/fixture-provenance.json) · [DejaVu 许可原文](../assets/speed-easing-20261016/font-license.txt)

原片是 72 帧/3 秒；演示源面板只展示前 59 帧。对比 MP4 为 **59 帧、24 fps、2.458333 秒**；GIF 同 59 帧，40/50 ms 量化后为 **2.460 秒**，约多 1.667 ms，无声并降低色数。14 份真实前后 MP4 含 AAC 脉冲音轨；原视频及对比 MP4 无音轨。

共 16 份 MP4 和 39 个公开文件，原始摘要/媒体探测已记录。自制图形和音频为 CC0，帧号栅格使用有独立许可证的本地 DejaVuSans，不分发字体二进制，不将字体重标为 CC0。未公开私有人物素材。已静态查看对比第 0/29/58 帧，未连续播放或听审。

## 5. 实际 CLI、质量与项目原子性

生成批次 **31 次正式 CLI，全部 exit 0**：init 1、ingest 2、compose 7、strict validate 7、旧/新 `render --publish` 14。另对七份新成片执行 **7 次** `quality check --require-audio --expensive --fail-on-black --max-true-peak-dbfs -1`，全部通过；不与回归数量相加。

| 成片 | 视频时长秒 | 音画流时长差 ms | 真峰值 dBFS | 检出黑帧区间 | 质量调用 |
|---|---:|---:|---:|---:|---|
| forward | 2.458008 | 5.992 | -3.5 | 0 | exit 0 |
| ease_out_reverse | 1.291667 | 11.333 | -3.6 | 0 | exit 0 |
| in_out | 2.000000 | 15.000 | -4.0 | 0 | exit 0 |
| bezier_two | 1.916667 | 20.667 | -4.1 | 0 | exit 0 |
| bezier_four | 2.375000 | 20.000 | -4.1 | 0 | exit 0 |
| animated | 2.375000 | 20.000 | -4.1 | 0 | exit 0 |
| compound | 1.583333 | 11.667 | -3.8 | 0 | exit 0 |

音画流时长差门槛保持 80 ms；未设目标 LUFS，脉冲数据不能验收广告响度。每组渲染前后 assets/settings/sequences 规范摘要和 Rights Ledger 原始摘要相同；正常 outputs/provenance 登记允许变化，内部编译段只保留在渲染计划与 manifest。

## 6. 冻结回归与保留的失败

最终完整 **452/452，738.867 秒**；90 份 product/src 与 product/tests 文件、项目 Schema 在执行前后摘要一致。新增 17 项专项为完整套件子集，最终独立运行 **17/17、13.942 秒**；固定旧版同 17 方法中 **16 方法语义失败、1 个既有 hold/linear 对照通过，13.787 秒**，无 ERROR 导入/夹具异常。subTest 会产生额外 FAIL 条目，按方法计数。专项、前后 CLI、质量检查和历史回归不相加。

专项覆盖三类 easing、两种句柄、静止 x 切线、正速率 overshoot、内部非正速度拒绝、非法/布尔/无限句柄、自动时长、直接/倒放/裁切、两层曲线、原动画、音频脉冲、1024 段门限及失败项目/台账不变。第 17 项补充接近常速的解析积分和实际 FFmpeg PTS，见下表。

中间一次完整 451/451 已经正常结束并通过，之后额外的长时低速复核发现真实缺陷：绝对速差小于 1e-8 被当成常速，导致约 6.185 ms 误差，超过该样例报告的约 130.208 μs 上界。保留该次[完整日志](./evidence/speed-easing-pre-stability-full-20261016.log)、源文件摘要/两个关键模块原文及[新增测试的真实失败](./evidence/speed-easing-nearly-constant-before-20261016.log)，不能把中间 451 项通过当作最终验收。修复为仅相等时按常速，并使用 log1p/expm1 和小相对速差的稳定级数，再冻结运行当前 452 项。

| 数值边界样例 | 修复前 | 修复后 | 判断范围 |
|---|---:|---:|---|
| 10000 源秒、0.01→0.010000004 ease_in，解析总积分误差 | 6184.893 μs | 65.104 μs | 修复后在该样例 130.208 μs 数学界内 |
| 实际 FFmpeg 三个 PTS 的最大误差 | 6177.746 μs | 66.699 μs | 核对 1/90000 时间基量化，非长片性能测试 |

[三帧诊断、解析基准、前后 PTS/argv 与源摘要](./evidence/speed-easing-stability-20261016.json)没有编码 10000 秒视频：只生成三帧 16×16 lavfi，经实际 setpts/showinfo 后空输出，不据此宣称长视频运行性能。这个中间源码快照与 Git 固定旧版 b0d0f42e 分开记录。

稳定表达式改动还使一个旧测试的 `/4.00000000` 文本断言遇到等价的 `/4`。保留[四项旧测试中一次格式断言失败](./evidence/speed-easing-legacy-render-20261016.log)，替换为原作者 50625 tick（0.5625 秒）、实际 17 编码帧及与作者时长相差≤1/30 秒的行为核验，并保留[四项复核通过](./evidence/speed-easing-legacy-render-final-20261016.log)。原倒放分段方向断言保留，没有放宽帧数/时长标准。

早期 15/15、16/16 是补充边界前的开发结果；前轮 435/435 和历史模型/研究结果分别保留。最终 452 项与 17 项子集均在同一 90 份产品/测试源码及同一 Schema 下执行，运行中未修改。

## 7. 原生复现

在仓库根目录，使用现有含 NumPy/Pillow 的原生 Python、PATH 中的 FFmpeg/FFprobe，显式提供本地字体和原许可证。输出/工作目录必须不存在；固定旧版提交必须在本地 Git 可读，不下载依赖或模型。

```powershell
& $nativePython -I -B -X utf8 .\scripts\smoke_speed_easing.py `
  --output-dir .\docs\assets\speed-easing-repro `
  --work-dir .\product\.runtime\speed-easing-repro `
  --font-file $localDejaVuSans --font-license-file $localDejaVuLicense
```

实际脚本、源码、Schema、旧版归档、argv、媒体探测和 SHA-256 均有证据。本批使用本机 ComfyUI 附带 Python 执行独立脚本，没有启动其服务。跨 FFmpeg 构建须重新核验，不能承诺编码字节相同。

## 8. 剩余差异

端点/常速最低 0.01 归一化仍存在；极端速率/句柄、长曲线与深层动画可能明确超预算。源仍先规范为 CFR，VFR 原始时间戳等效未验收。音频仍为有接缝可能的 atempo 短窗。容器/叶片定格、字幕 cue/逐字时钟、父级枢轴、群组 mask/混合/音频总线、自然广告观感和 4K 性能继续待补。RVM/SAM2 漏抠、LaMa/VACE 自然修复缺陷、开放内容库规模、发行与完整剪映效果对标保持未验收。
