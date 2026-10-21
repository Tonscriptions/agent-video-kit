# 离线媒体运行时与NumPy交付（实验v0.1，2026-10-21）

<!-- OFFLINE-MEDIA-FULL-R1 -->
完整原生回归 **2043 方法、3988.673 秒、0 跳过**；260 产品输入及 8 外部夹具不变。尚未合入 main 或推送此实验。
早期MP表保留当时专项记录，当前完整回归状态以本段为准。
<!-- /OFFLINE-MEDIA-FULL-R1 -->


<!-- OFFLINE-MEDIA-STANDALONE-AUDIT-R1 -->
当前独立审计：260产品输入，**260个不同相关方法、708.130秒、0跳过**（父226＋22旧安装＋12新安装）。先前34、12是本次子集，不能重复累计。新原生23CLI/39检查、新隔离26CLI/20安装＋39媒体检查均通过；42资产/14GIF。
四份Skill增量已基于真实发布V87父版验证，**未注册**；将来只合入新块与记录的精确V88父版条款更新，不以旧V87全文覆盖后续指导。
完整回归执行状态见文首，已绑定实际发布V88/2031；当前没有生产合入或推送。NumPy已在本候选八轮包真实交付，不应把此结果写成main当前已发布能力，也不代表全部剪映功能/效果。
[独立审计](../validation/evidence/offline-media-profile-20261021-lab/audit-r1.json) · [260当前相关方法](../validation/evidence/offline-media-profile-20261021-lab/related-r1.json) · [四份未注册增量](../validation/evidence/offline-media-profile-20261021-lab/skills-draft-r1.json)。下面较早阶段“待完成”保留当时状态，当前以本段为准。
<!-- /OFFLINE-MEDIA-STANDALONE-AUDIT-R1 -->


独立候选，未合入main、未注册Skill或发布。当前260冻结输入；12新控制及34相关检查通过。新原生和全新8-wheel离线安装的媒体均通过，安装阶段没有复制宿主NumPy。完整回归执行状态见文首；完整剪映功能和效果仍未验收。

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
