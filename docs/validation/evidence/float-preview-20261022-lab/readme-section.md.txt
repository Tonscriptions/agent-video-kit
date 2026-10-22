<!-- V97-NATIVE-FLOAT-TIMELINE-PREVIEW -->
### V97 候选：原片 Float32 时间线预览与缓存（未发布）

显式浮点工程的 `preview frame` / `preview range` 使用标准渲染的原片窗口与 FloatTimeline，保留完整作者帧号。源码相关回归 **57 方法 /532.355 秒 /0 跳过**，包括18项新增预览、22项既有预览及17项标准浮点渲染；不将57项全算作新功能。默认迁移及未接入算子、自然/HDR质量和完整剪映功能仍需继续实现。

| 编号 | 功能性核验 | 实际内容与限制 | 证据 |
|---|---|---|---|
| V97-01 | 共同内核 | 原片SHA与原生PTS窗口、作者IR、变换/混合/基础蒙版及嵌套时钟复用正式浮点宿主；未接算子明确拒绝 | [契约](docs/specs/浮点时间线预览与缓存契约_v0.1_2026-10-22.md) |
| V97-02 | PNG16与alpha16 | 真实PNG逐码保留65,536灰阶和全部65,536透明度值；PNG独立16位交付，不当作Float32参考 | [57项实际命令/断言](docs/validation/evidence/float-preview-20261022-lab/native-r2/verification.json) |
| V97-03 | Float32区间参考 | `master.nut`为straight BT.709 linear GBRAP Float32；实际保存小于一个RGB16码阶的合成变化；格式对照包含相邻Float32、负值及超一值，作者范围策略另行执行 | [格式逐字节往返](docs/validation/evidence/float-preview-20261022-lab/formats-r1.json) |
| V97-04 | 作者视频时钟 | 5秒起点的真实VFR在嵌套倒放选帧中匹配独立区间参考，保留全片帧号；selected sequence canvas不改写全局作者画布 | [源码回归](docs/validation/evidence/float-preview-20261022-lab/native-r2/unittest.log) |
| V97-05 | PCM独立端点 | 非整数作者结束保留60001末样本端点；区间样本逐字节匹配；真实样例帧3..16共14帧，67200双声道PCM采样帧相同 | [实际CLI样例](docs/validation/evidence/float-preview-20261022-lab/media-r1/verification.json) |
| V97-06 | 线性预乘缩放 | 完整合成后按像素中心双线性缩放，独立2×2透明颜色加权参考通过；不是大比例缩小的面积抗锯齿 | [独立像素测试](docs/validation/evidence/float-preview-20261022-lab/native-r2/verification.json) |
| V97-07 | 持久内容缓存 | 作者/实际素材/信号/本地代码/NumPy原生依赖绑定SHA；同大小、恢复mtime的运行时变化仍失效。命中不新建图、provider、probe或编码器；真实第二CLI进程命中 | [真实复用与原始收据](docs/validation/evidence/float-preview-20261022-lab/media-r1/verification.json) |
| V97-08 | 只读与失败清理 | dry-run不打开provider或写缓存；真实中途取消及失败编码器清理线程/临时目录；损坏参考拒绝，原导出保留，显式导出可在prune后保留 | [失败边界及原始输出](docs/validation/evidence/float-preview-20261022-lab/native-r2/verification.json) |
| V97-09 | 真实公开CLI媒体 | 20个脚本级原生/CLI调用、27检查；2次正式render、3次preview（区间、单帧、复用）；原始/编辑完整片各20帧、2秒、96000双声道采样 | [生成器](docs/validation/evidence/float-preview-20261022-lab/media-r1/executed-script.py.txt) |
| V97-10 | 原视频与实际预览 | 原创RGB16输入；下方GIF左为原始CLI输出帧3..16，右为本轮真实CLI预览，共14×100ms；已查看3/10/16共6幅图，未连续播放或试听 | [原始选段](docs/assets/float-preview-20261022-r1/original-range.mp4) · [实际预览MP4](docs/assets/float-preview-20261022-r1/range.mp4) · [Float32参考](docs/assets/float-preview-20261022-r1/range.master.nut) · [PNG16帧11](docs/assets/float-preview-20261022-r1/frame.png) · [查看/GIF时钟](docs/validation/evidence/float-preview-20261022-lab/static-review-r1.json) |
| V97-11 | 全新离线安装 | **260 方法 /784.525 秒 /0 跳过**；180 资源 source/wheel/site 相同，8 个离线 wheel；NumPy 931 文件与许可相同。安装版原生 Float32/PCM/PNG16 与开发版真实 CLI 样例相同。 | [安装收据](docs/validation/evidence/float-preview-20261022-lab/installed-r1/verification.json) |
| V97-12 | 完整回归 | **尚未执行/未结束，不计通过**；预计2355方法，等待实际V96父提交发布后串行执行。 | [当前实测报告](docs/validation/浮点时间线预览与缓存实测_2026-10-22.md) |
| V97-13 | 保留失败与观看副本边界 | 首轮18项2失败已保留；显式OETF修复观看亮度。原生去alpha使观看副本减损精度，原理想半码探针仍保留失败；不影响独立Float32参考/PNG16的验收，不宣称MP4理想量化 | [失败与分段测量](docs/validation/浮点时间线预览与缓存实测_2026-10-22.md) |

![原始选段与真实CLI浮点时间线预览](docs/assets/float-preview-20261022-r1/comparison.gif)

<!-- /V97-NATIVE-FLOAT-TIMELINE-PREVIEW -->
