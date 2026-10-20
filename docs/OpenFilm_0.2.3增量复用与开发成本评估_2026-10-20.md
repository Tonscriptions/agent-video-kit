# OpenFilm 0.2.3 增量复用与开发成本评估

**可以继续降低部分开发成本。优先拆纯函数、工程交换规则和测试夹具；沿用本项目已有的 Agent CLI、工程模型及本地执行链。** 这轮新增价值集中于组件参数和保调音频预览，并未出现可替代剪映全部功能与 AI 效果的开源内核。

这是 R12 源码研究与接入设计。产品仍为已发布的 V77，本轮没有把上游模块或测试结果计作新增产品能力。

## 固定来源

- 检索仓库：[openfilm/openfilm](https://github.com/openfilm/openfilm)。GitHub API 快照为 **1524 stars /153 forks，2026-10-20 22:12:10 Asia/Taipei**；星数只标明采集时点。
- 新固定提交：[284f8bd3d6850ceaa773043e2ecb90e13640f547](https://github.com/openfilm/openfilm/commit/284f8bd3d6850ceaa773043e2ecb90e13640f547)，CLI/desktop 均 **0.2.3**，提交时间为 2026-10-20 13:08:21 UTC。
- 对照：[0.2.2，695f4a8](https://github.com/openfilm/openfilm/commit/695f4a887a97258d45ffe5715eadf537b6d2579b)，见 [R11](OpenFilm_0.2.2差异复核与复用取舍_2026-10-20.md)。GitHub compare 为前进 **29 个提交**；本轮固定此提交，不把后续 main 当作同一版本。
- [完整新源码 ZIP](../sources/upstream/openfilm-023-20261020-r12/repo.zip)：**11,650,806 字节**，SHA-256 `5ee1665981831493dd776d2f667da728e0521812c9748e946c99b442ed708e57`。ZIP 只作为源码研究输入，没有安装上游产品。
- [获取记录](validation/evidence/openfilm-023-20261020-r12/acquisition.json)、[社区快照](validation/evidence/openfilm-023-20261020-r12/snapshot.json)、[原始仓库 API](validation/evidence/openfilm-023-20261020-r12/repository.json)、[原始 head API](validation/evidence/openfilm-023-20261020-r12/head.json)、[原始 compare API](validation/evidence/openfilm-023-20261020-r12/compare.json)。记录中的采集时间来自保留文件的本地写入时间，未保存 HTTP 响应头。

## 编号实查结果

| 编号 | 实际执行或核对 | 结果与边界 |
|---|---|---|
| R12-01 | 两版 ZIP 全树字节比较 | **757→781 文件；616 不变、27 新增、138 修改、3 删除**。见 [全树 SHA](validation/evidence/openfilm-023-20261020-r12/run-r1/new-tree.json) 与 [完整文本差异](validation/evidence/openfilm-023-20261020-r12/run-r1/source.diff)；不是只读 README |
| R12-02 | MIT 原文与 14 个候选入口 | [LICENSE](validation/evidence/openfilm-023-20261020-r12/run-r1/LICENSE.txt) 原文不变；**8 个候选入口不变、4 个修改、2 个新增**。逐文件摘要在 [主收据](validation/evidence/openfilm-023-20261020-r12/run-r1/verification.json) |
| R12-03 | 五份原始纯函数测试 | **46/46 方法通过，0 跳过**：film-doc 30、rate 1、component-props 3、template-controls 9、steps 3。原文件未改写，使用现有原生 Node **22.14.0** 的实验性类型擦除运行；见 [逐次命令与原文件 SHA](validation/evidence/openfilm-023-20261020-r12/run-r1/verification.json) 及 [原输出 1](validation/evidence/openfilm-023-20261020-r12/run-r1/test-1.stdout.log)、[2](validation/evidence/openfilm-023-20261020-r12/run-r1/test-2.stdout.log)、[3](validation/evidence/openfilm-023-20261020-r12/run-r1/test-3.stdout.log)、[4](validation/evidence/openfilm-023-20261020-r12/run-r1/test-4.stdout.log)、[5](validation/evidence/openfilm-023-20261020-r12/run-r1/test-5.stdout.log) |
| R12-04 | 新版缓存 key 的内容失效反例 | 实际把同一路径 SVG 从红色改为蓝色，SHA 不同、字节数和 mtime 相同，**key 仍相同**。用连续原函数片段及必要原常量执行；没有执行上游完整缓存模块、浏览器或渲染器。见 [片段/观察值/命令](validation/evidence/openfilm-023-20261020-r12/probe-r1/verification.json) |
| R12-05 | 组件参数三项边界观察 | 原函数接受图片 `https://example.invalid/hero.png` 并只格式化为 CSS，接受变量名 `--`、匹配序号 `1e20`。这是宿主负责校验的边界，不是发起了网络请求或认定整个产品有漏洞。四组观察共 **8 个断言**，不与 46 个原始测试相加 |
| R12-06 | 创作 Skill 和 providers 分开比较 | **10 份 SKILL.md /31 个 Skill 文件全部不变**；29 个 provider 文件中 23 不变、6 修改，集中于 Azure/Google 及其索引/测试。这些不是 29 个离线模型，也不是新增本地能力；本轮新增安装 Skill 为 **0** |
| R12-07 | 源码冻结与既有产品 | 两次研究前后各 **233 个产品输入 SHA 完全相同**。V77 的 1746 项全量收据是既有产品证据，本轮没有重跑或重新累计；没有新增成片验收 |
| R12-08 | 执行环境 | Windows 原生 Python/Node、E 盘源码与 scratch；没有安装依赖、运行上游 CLI/Studio/provider 或模型，没有 Docker/WSL/容器/虚拟环境，没有打开本地浏览器 tab |

上述纯函数测试不依赖上游整个 monorepo 的安装。Node 22.14 满足 CLI 的 `>=22.2` 声明，低于根工作区的 `>=22.18`，因此不能推断完整上游工作区兼容或完整渲染通过。

## 可拆模块、当前差距与接入成本

下列为**熟悉本项目的一名工程师的规划估计，不是实测耗时**。原型只覆盖表内范围；生产化列包含输入预算、取消/原子提交、包重放与一次离线安装验证。不同项共享事务与执行链，不应把各行机械累加为完整项目预算。

| 编号/优先级 | 源码入口与可复用内容 | 本项目现状与适配要点 | 限定原型 /生产化估计 | 决策 |
|---|---|---|---|---|
| A01 /高 | [`component-props.ts`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/ui/src/lib/component-props.ts)：命名、去重、重命名、单项/全部重置、text/image/boolean/var 四类字段 | 已有通用类型变量和 HTML 文字/图片/CSS 覆盖；新增价值是**明确暴露的组件字段清单与显隐语义**。Agent 可用 JSON 字段名操作；图片接资产 ID，接回本地路径、权利、数量/长度预算，不接受任意 URL | **1–2 /3–5 人日** | 借纯函数规则及 3 个原始测试；不拆组件 GUI。新边界见 [接入契约](specs/OpenFilm组件参数与预览缓存接入边界_v0.1_2026-10-20.md) |
| A02 /高 | [`preview-cache.mjs`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/server/preview-cache.mjs)：区间任务、去重、完成/取消状态 | 当前有最终渲染、同批复用与素材联系表；**工程时间线帧/区间的持久预览仍待构建**。重写为内容寻址 key，绑定工程、素材、字体/LUT/模型/运行时及有效设置，复用现有锁与进程取消 | **2–4 /7–12 人日** | 借状态设计；不照搬大小+mtime key 或 UI 卡帧调度。生产化不包含实时播放性能或 GPU 新渲染器 |
| A03 /中 | [`derived.mjs#L170`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/server/derived.mjs#L170)：按速度缓存保调音频，复用 `atempo` 链 | 本项目已有离线变速/保调及原 PCM 核验；价值是给预览建立音频衍生物，而不是再次实现音频引擎。上游范围为 1/16..16，速度取四位小数，仍用源路径/大小/mtime key | **1–2 /3–5 人日** | 与 A02 共用缓存、取消、配额；保留本项目精确作者时钟，不默认照搬四位小数量化。当前只审读差异，未执行新音频预览 |
| A04 /中 | [`nle.mjs`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/server/nle.mjs) + [`fcpxml.mjs`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/server/fcpxml.mjs)：轨道分配、基本剪切、源区间、XML、字幕夹具 | 值得作为**导出适配器**参考，不能替换中立 Agent Project；目标开源 NLE 的实际支持须另验。不同工程模型、帧取整和复杂效果要明确报告损失/烘焙，不能由导出器推断双向无损导入 | **3–6 /8–15 人日** | 优先满足明确的开源 NLE 交换需求；不引入剪映/CapCut 安装目录探测与写入。复杂效果无损互通不在此估计内 |
| A05 /维护 | HTML `frame(t)`、字幕分句、模板字段、诊断/编解码探测 | 已有限定接入；0.2.3 的 look/render/rate/problems/diagnostics 本轮候选文件均未变。`film-doc` 新 JSON 属性引号回写测试值得保留作互操作夹具 | 不新增迁移预算 | 保持现有离线实现；不要重复造第二套执行器或再次统计降本 |
| A06 /维护 | 十套创作 Skill：参考片、长转短、录屏、拼贴、讲解 PIP、白板等 | 三套主线已有本地 `$video-cut-reference-remake`、`$video-cut-long-to-short`、`$video-cut-screen-demo`；其余可在已有 Skill 内补创作流程，不能算作特效算法 | 未变，**0 次新安装** | 保留 `video-cut-` 前缀；保留本地输入、可编辑工程和权利校验；不引入在线下载与 providers |
| A07 /低 | [`steps.ts`](https://github.com/openfilm/openfilm/blob/284f8bd3d6850ceaa773043e2ecb90e13640f547/packages/openfilm/studio/ui/src/editor/steps.ts)：100 步内存撤销/重做，Agent 删除对象后丢弃失效操作 | 本项目已有持久操作日志、工程快照和事务恢复。36 行内存栈不能替代跨进程恢复、锁、重放和资产引用处理 | **0.5–1 人日审查**，不计划移植 | 只借其“外部编辑使撤销失效”的测试场景 |
| A08 /不采用 | Studio/desktop、快捷键、多语言菜单、Agent 安装器、云语音/转写 providers | 这些占此次差异的较大部分；无 GUI 的纯本地 CLI 不需要另一套桌面宿主或在线服务 | 不计为节省本地内核研发 | 不进入产品运行时；“Azure/Gemini 新接入”不当作本地声音/转写模型 |

**实际降本优先级：先复用测试与规则，再做薄适配。** A01 可减少组件字段语义设计；A02 可参考任务生命周期，但需要重写缓存正确性；A04 能减少交换格式资料整理。对于目前已经实现的字段解析、变速、字幕和事务，再复制一遍上游代码会增加维护面。未做同条件从零/移植对照，不能据此宣称节省了某个已实现百分比或已经减少多少实际人日。

## 如何拆取

1. **组件参数**：只选 `component-props` 的纯规则及其小型 `template-controls/film-overrides` 依赖，沿用 MIT 声明；宿主输出统一 JSON 契约。先证明字段清单、重命名/重置、显隐和包重放，再接时间线。不要引入 React 面板、任意 CSS 样式写入或第二套 film.html 工程模型。
2. **时间线预览**：以当前 `build_filter_graph` 为唯一画面/音频语义来源。截取作者输出的区间，保留关键帧、嵌套、转场与音频上下文；缓存命中不等于重新执行模型。先验证正确性及失效，再独立测量冷启动/缓存命中速度。联系表只用于素材检查，不能冒充时间线预览。
3. **工程交换**：独立 `Agent Project → 中立导出计划 → XML/FCPXML`；明确每个字段的保留/烘焙/丢失。上游 XML 字符串测试和本项目结构核对都不能替代目标开源 NLE 实际打开和回渲验证。
4. **许可证与资源**：保留所复制代码的 OpenFilm MIT 原文和固定提交；素材、字体、模型与模板继续走现有 Rights Ledger，代码许可证不作为这些资产的登记证据。

`0.2.3` 的剪映/CapCut 导出权限回退主要在 `exports.mjs`：默认草稿目录拒绝写入时，回退到 exports 并报告位置。它不是新增通用开放工程内核，也不是解决全部私有草稿/素材格式的双向转换方案。本项目可借“显式失败或回退须告知”的原则，继续按本地转换契约处理。

## 复现与后续验收

在本项目根目录使用原生工具，并为每次复现指定**全新的输出位置**：

```powershell
C:/Python313/python.exe -E -B -X utf8 scripts/review_openfilm_r12.py `
  --output docs/validation/evidence/openfilm-023-20261020-r12/reproduction-r2/verification.json

C:/Python313/python.exe -E -B -X utf8 scripts/probe_openfilm_r12_boundaries.py `
  --output docs/validation/evidence/openfilm-023-20261020-r12/boundary-reproduction-r2/verification.json
```

两个脚本均校验固定 ZIP SHA，不下载、不安装、不启动浏览器，拒绝覆盖历史结果。[研究执行脚本](../scripts/review_openfilm_r12.py)、[边界探针](../scripts/probe_openfilm_r12_boundaries.py) 与各自执行副本均保留。后续接入才新增产品测试、实际 CLI/离线安装和可公开的原输入/MP4/GIF，本轮不借用旧成片作为新测试。

采集收据整理首轮误以为 GitHub compare 含 `head_commit` 字段，在生成 snapshot 前失败；[失败记录与当时脚本](validation/evidence/openfilm-023-20261020-r12/acquisition-r1/failure.json) 保留。修正为核对完整 29 个提交列表的最后 SHA 后才生成最终获取记录，未覆盖原始 API，也未重跑或改写原测试结果。

首轮暂存发布核对被原始 unified diff 的上下文空格和源片段末尾空行挡下，见 [发布核对失败记录](validation/evidence/openfilm-023-20261020-r12/staged-r1-failure.json)。按现有证据规则为 R12 原始证据增加 Git 字节保全属性后重新核对，保留原始空白字节，没有清洗原代码、diff 或日志来改写证据。

第二轮进一步发现首次暂存已把一份原始 CRLF JSON 规范化为 LF；[字节核对失败](validation/evidence/openfilm-023-20261020-r12/staged-r2-failure.json) 保留。随后仅在 R12 目录按字节保全属性重新索引，仍保留工作区原字节，再执行正式暂存核对。

既有复用对应的真实演示继续见 [V70 同批结果复用](validation/OpenFilm同批次结果复用实测_2026-10-20.md)、[V71 透明联系表](validation/透明视频多帧联系表与Alpha核验实测_2026-10-20.md)、[V72 HTML 子帧快门](validation/HTML子帧快门与透明混合实测_2026-10-20.md)。自然视频抠像、美颜美体、重光照、完整素材权利库和剪映全部效果的质量目标仍按 [覆盖矩阵](validation/能力覆盖与验收矩阵_v0.1_2026-10-13.md)逐项开发验收。
