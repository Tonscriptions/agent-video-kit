# HTML 子帧快门采样与预乘透明合成契约 v0.1

状态：V72 子帧快门、预乘透明、时钟、结构化复用、离线安装和相同输入的隔离完整回归限定通过；自然/HDR/连续质量/完整剪映等价未验收。

## 来源与适用范围

采用 [OpenFilm 固定版本 render.mjs](https://github.com/openfilm/openfilm/blob/71922644da5d6b67db2cc796d4e057f98999944f/packages/openfilm/src/render.mjs) 的子帧重新绘制组织思路。原始 MIT 版本和算术控制保存在 [R10 研究证据](../validation/evidence/openfilm-shutter-20261020-r10/verification.json)。产品代码自行实现中心中点采样、显式切点、预乘 Alpha、预算和现有事务/清理链；本次没有逐字复制上游函数，不宣称与上游像素等价。

仅适用于已注册的本地 HTML 可编辑源。每个子帧都完整执行冻结时钟、源代码绘制、模板还原/覆盖与截图。既有视频 `tmix` 不会产生源代码的新时刻，本功能也不会为普通素材估计光流或补帧。

所有执行使用原生 Windows、既有本地 Node/playwright-core/Chromium 和 FFmpeg。没有下载、GUI 自动化、模型前向、Docker、WSL、容器或虚拟环境。受控浏览器仅处理本项目源和已声明本地资源；终态必须关闭全部自有页面、上下文、浏览器和进程树。

## CLI 与保存的配方

```powershell
python -m ai_ad_editor motion html-render --project E:/video-project `
  --source-asset-id editable --asset-id blurred `
  --shutter-samples 4 --shutter-fraction 1 `
  --shutter-cut-tick 89100 --layout-check strict --dry-run
```

按计划移除 `--dry-run` 执行，使用新的资产 ID。单次期限仍包含布局与渲染。

| 字段 | 约束及含义 |
|---|---|
| `--shutter-samples` | 整数 1–16；布尔、字符串配方、浮点和越界值拒绝 |
| `--shutter-fraction` | 有限数 0–1；NaN/Infinity 拒绝；首次默认 0.5 |
| `--shutter-cut-tick` | 可重复；源时钟内部整数 tick，严格递增且唯一，最多 256 个 |
| `--shutter-clear-cuts` | 显式清空继承切点；与新切点参数互斥 |
| 无参数或 samples=1 | 原始 `frame/fps` 截图路径；不做 Alpha 规范化，不改变原隐藏 RGB |
| fraction=0 | 有效样本数 1；保持原帧路径，避免重复截图 |
| `--from-asset-id` | 继承保存配方，再应用显式选项；不隐式清除已有切点 |

资产 `html_motion.shutter` 保存 `version=1`、`samples`、`fraction`、`cut_ticks`、`sampling_phase=midpoint_centered`、`composite_domain=premultiplied_encoded_srgb_8bit`。字段集合、版本、类型、范围均校验，未知配方字段不静默忽略。项目 Schema 增加该可选对象，原有 0.1.0 项目仍可读；随包 Schema 与编译摘要必须一致。

## 时间、切点与输出时钟

启用时，对输出帧 f 和样本 k：

```text
t = (f + ((k + 0.5) / N - 0.5) * fraction) / fps
```

内部无 clamp 时，平均采样时刻等于 f/fps。OpenFilm 研究版本采用左端点相位，本实现明确采用中点，不能混称同一公式。

f/fps 所在的半开切点区间决定该帧可见片段。请求时刻先截到该区间，尾部留 `min(1 微秒, 区间一半)`，避免落到下一场。未声明内部切点时，报告明确只检查已声明 anchors，不推断自动镜头检测已完成。独立 HTML 源之间不会跨源采样。

报告逐项保留请求/裁剪的精确有理数、实际发送给 JS 的 binary64 时刻及其精确有理数、区间上下界、输出帧/子样本索引与 clamp 标记。JS 的绘制和 CSS 布局仍有浏览器精度限制。有理 FPS 的输出保持原 CFR；编码后逐帧读取整数 PTS 与时基，不能只比较容器时长。

## Alpha 与色彩

对 N 个等权 8-bit RGBA 样本，累计 `A=Σalpha` 和 `C=Σ(channel×alpha)`。还原 RGB 为 C/A，Alpha 为 A/N，均采用非负整数 half-up；A=0 时 RGB=0。每帧四个 int32 累积平面，最大 N=16 时不会超出 int32；Pillow 的原生 ImageMath 内核执行运算。没有新增 NumPy 或在线依赖。

这是编码域 sRGB 8-bit 平均，不是线性光曝光、HDR、16-bit 合成或真实相机快门模拟。samples=1 直接通过原 PNG，不把历史透明 RGB 规范化成零。

## 预算、确定性与失败

工作量为 `宽×高×输出帧×有效样本×(3 个渲染遍历＋strict 时 2 个布局遍历)`。启用快门时上限 20 亿像素，超限在运行时验证/浏览器启动前拒绝。默认原帧路径保留既有边界；这里不是进程总 RAM 或总磁盘配额承诺。

单子帧 ACK 背压、单输出帧流式累积；不在内存保存全片 PNG。源码、worker、Pillow ImageMath 和原生核心/数学模块以实际文件摘要绑定，执行时复核并持有现有 Windows 只读锁。该绑定不覆盖全部系统 DLL。

每个实际子帧须在原顺序、逆序和交错重排的三个新鲜上下文得到相同 PNG 摘要。strict 布局另在两个新鲜上下文检查每个实际子帧，不只看输出锚点。Canvas/SVG 语义文字布局继续标为未核验；不能通过增加快门解除门禁。

编码、运行时、取消、超时、布局失败均保留报告，清理自有进程并回滚作者数据和未提交资产。`progress.encoded_output_frames` 表示已送入编码器的合成帧，不能把进度写入当成成片成功。成功仍须验证编码终态与精确 PTS。

## 验收与未验收边界

当前专项与原生/安装/完整回归的独立记录、原输入和实际输出集中于 [实测报告](../validation/HTML子帧快门与透明混合实测_2026-10-20.md)。历史失败保留，不以重跑相加增大通过数。

合成几何像素、确定性、布局、时钟和可移植性各自验收；自然动效的连续观感、滚动快门、镜头曝光模型、HDR、4K/长片吞吐、任意模板兼容和完整剪映等价仍未验收。静态图或 GIF 不能代替连续播放审片。
