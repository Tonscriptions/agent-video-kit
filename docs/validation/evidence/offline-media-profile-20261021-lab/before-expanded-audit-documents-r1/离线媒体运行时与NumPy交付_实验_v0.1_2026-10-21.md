# 离线媒体运行时与NumPy交付（实验v0.1，2026-10-21）

独立候选，未合入main、未注册Skill或发布。当前260冻结输入；12新控制及34相关检查通过。新原生和全新8-wheel离线安装的媒体均通过，安装阶段没有复制宿主NumPy。完整2043仅为预计方法数，须先绑定真实发布的V88/2031，尚未启动；完整剪映功能和效果仍未验收。

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
