<!-- V96-STANDARD-NATIVE-FLOAT-RENDER -->
### V96 候选：标准 CLI 原片浮点渲染（未发布）

`settings.pixel_pipeline.engine="float32-native-v1"` 将原片窗口与 Float32 线性光合成接入共同 `render`、持久队列及续跑。当前定向 **17 方法 /200.249 秒 /0 跳过**。显式选择此后端；尚未接入的操作会拒绝。默认后端迁移、所有效果/预览缓存、自然素材、HDR 和完整剪映等价仍需持续实现。

| 编号 | 功能性核验 | 实际执行内容与限制 | 证据 |
|---|---|---|---|
| V96-01 | 标准执行器 | 公共 `render`、持久 `queue run`、取消后的 `render --resume` 使用共同质量检查/指纹/记录；修改 CRF 的续跑被拒绝 | [17项真实测试](docs/validation/evidence/float-standard-20261022-lab/standard-r5/verification.json) |
| V96-02 | 高精度交付 | 65,536 原始灰阶经正式 10-bit H.264/MKV；独立亮度参考误差≤1.5码且至少870级；合成到最终16-bit RGB交付前保留Float32 | [契约](docs/specs/标准CLI浮点渲染接入契约_v0.1_2026-10-22.md) |
| V96-03 | 色彩边界反例 | 三组真实转换：旧 swscale 参数白点943而非940；zscale 全码最大误差0.499977、877级、Cb/Cr全512；参数/标签与实际转换绑定 | [独立原始对照](docs/validation/evidence/float-standard-20261022-lab/color-boundary-r1/verification.json) |
| V96-04 | 透明度 | 全部256个alpha码值及量化边界附近值，经独立平面、lossless VP9/WebM逐码相同；实际透明画面不能默默丢到不透明输出 | [原始alpha反例](docs/validation/evidence/float-standard-20261022-lab/alpha-boundary-r1/verification.json) · [实测](docs/validation/evidence/float-standard-20261022-lab/standard-r5/unittest.log) |
| V96-05 | 作者视频/音频时钟 | 原始5秒起点VFR在嵌套倒放下逐帧匹配独立区间参考；倒放/定格PCM逐字节相同；分数作者末尾13视频帧和60001立体声采样分别保留 | [实际测试与命令](docs/validation/evidence/float-standard-20261022-lab/standard-r5/verification.json) |
| V96-06 | 失败与资源清理 | 只读规划不写缓存/临时成片；源SHA、已知非方形源、未接操作拒绝；编码/质量/manifest暂存/替换失败保留旧文件并关闭自有进程线程。发布二文件不保证强退/断电原子性 | [失败/修复](docs/validation/标准CLI浮点交付实测_2026-10-22.md) |
| V96-07 | 正式CLI原片与成片 | 两次独立子进程CLI；脚本级12次调用、16检查；原片/编辑片各20帧、10fps、2秒和96000立体声采样；作者IR不重写，PCM全样本相同 | [真实命令/SHA](docs/validation/evidence/float-standard-20261022-lab/media-r4/verification.json) |
| V96-08 | 原视频/MP4/GIF | 自生成RGB16原片与音频；正式10-bit MKV；屏幕混合、圆蒙版、反向源与变换关键帧；MP4/GIF为这两段真实输出的预览 | [原片](docs/assets/float-standard-20261022-r4/original.native.mkv) · [原始MP4](docs/assets/float-standard-20261022-r4/original.mp4) · [编辑MP4](docs/assets/float-standard-20261022-r4/edited.mp4) · [正式10-bit成片](docs/assets/float-standard-20261022-r4/edited.mkv) |
| V96-09 | 实际抽帧目检 | 已查看原片/成片0/10/19共6帧；圆形位置/旋转与亮度混合可见，未见明显外围黑矩形；GIF20帧均100ms。未连续播放/试听 | [查看与GIF时钟](docs/validation/evidence/float-standard-20261022-lab/static-review-r1.json) |
| V96-10 | 全新离线安装 | **220 方法 /580.36 秒 /0 跳过**；179 资源 source/wheel/site 相同，8 个离线 wheel，NumPy 931 原文件和许可相同，安装版两次真实 CLI 媒体逐像素/PCM 与开发版相同。 | [安装收据](docs/validation/evidence/float-standard-20261022-lab/installed-r1/verification.json) |
| V96-11 | 完整回归 | **尚未执行/未结束，不计为通过**；完整 2337 方法按 V95 与 R16 实际发布顺序串行，发现数量不等于已执行。 | [当前实测报告](docs/validation/标准CLI浮点交付实测_2026-10-22.md) |
| V96-12 | 保留失败 | r1摘要/夹具/色阶失败与收据序列化故障；r3只读/VFR夹具问题；r4取消清理丢失操作ID；媒体r1外部路径、r2缺插值、r3开发环境来源断言均保留 | [逐轮记录](docs/validation/标准CLI浮点交付实测_2026-10-22.md) |

![原始输入与正式CLI编辑输出GIF](docs/assets/float-standard-20261022-r4/comparison.gif)

<!-- /V96-STANDARD-NATIVE-FLOAT-RENDER -->
