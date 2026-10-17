# 离线 HTML 动效与可编辑源码契约 v0.1

状态：受控实现通过，37 专项与完整 975 项均通过；[正式实测](../validation/离线HTML动效源码与透明合成实测_2026-10-18.md)保留全部失败和未验收边界。主工程仍是 Agent Project 的整数 tick 时间线和 FFmpeg 合成图。

## 1. 接口与资源

在既有 `motion list/inspect/apply` 之外增加 `motion html-register/html-source/html-inspect/html-render`。注册使用明确存在的本地 Node、playwright-core 和 Chromium headless shell；禁止自动安装、下载、Docker、WSL。路径、版本、包和浏览器目录内的发行文件摘要均登记（仅排除根目录可变诊断 debug.log，新日志指向 E 盘临时目录），正式运行前重新核对。原机环境注册不替代另一台机器上的注册。

`html-source --input manifest.json --asset-id <id>` 将明确列出的 HTML/CSS/JS/SVG 文件及已登记 image/font 资源封成不可变 ZIP generated 资产。清单包含 `entry/width/height/fps/duration_tick/files/resources/variables`；资源项为 `path/asset_id`，包内只存路径与内容摘要，项目元数据保留可重映射的 asset_id。相对路径、大小写重复、目录穿越、符号链接/目录联接、超额资源及未登记资源拒绝。代码许可与图片/字体许可分别记录；源码默认未核验，不把 MIT 算法许可授予模板内容。

`html-inspect --source-asset-id <id>` 验证归档及资源摘要并显示清单。`html-render --source-asset-id <id> --params params.json --asset-id <new-id>` 产生带直通 alpha 的 FFV1/BGRA NUT 与真实执行报告。NUT 用于保留有理 CFR 帧时钟，正式运行逐帧检查 PTS；开发中 MKV 毫秒时基曾导致 12 fps 入轨错位，不能仅检查画面数量。`--from-asset-id` 可从已有输出恢复同一源码与已用参数，显式参数覆盖后生成新版本；不覆盖历史输出。可选 `--apply --track-id` 以普通视频片段入轨，之后沿用现有裁切、变速、关键帧、蒙版与混合能力。源码包和资源依赖必须随工程包及片段组搬运，不能只保留烘焙视频。

## 2. 页面与时间契约

页面提供 `window.film = {frame(t, params), ready?, width?, height?, duration?}`。尺寸和时长若声明，必须与清单一致。`t` 是精确 CFR 帧号除以有理 FPS 的秒数；画面由该时刻及参数确定，不能依赖先前 frame 调用。`window.motionParams` 在脚本前可用。变量复用现有模板的 string/number/integer/boolean/color/enum 校验与默认值；拒绝未知变量、非有限数值和 asset/any 类型。替换图片先登记并新建源码包。

提取固定 OpenFilm `eefd6a8d379289102141359a4718dbab12170526` 的 `FILM_CLOCK` 原算法，保留 MIT 原文；不导入其 Studio、服务商或默认联网的 host/render 执行器。每帧设置虚拟 Date/performance/random 时钟，调用 frame、固定 CSS/WebAnimation 时刻、等待字体与栅格提交后截图 PNG。全帧渲染后，用两个全新 page/context 按反序与奇偶乱序重绘每帧并核对 PNG 摘要。只证明该固定工具链与该次输入的一致性，不承诺跨 Chromium/显卡/字体版本逐字节一致。

## 3. 本地执行与回收

页面的逻辑同源请求由 Playwright route 直接返回归档的白名单字节，不启 HTTP 服务。未声明路径、外源、非 GET、子框架、弹窗、WebSocket、WebRTC、Service Worker、Worker、视频/音频标签、WebGL 和页面错误导致失败；没有在线 allowlist 或隐式 fallback。此入口用于受信任本地模板，不宣称是恶意 JS 的通用安全沙箱。

原生 Windows Job Object 在 worker 收到请求前约束 Node，并约束 FFmpeg；浏览器子进程继承。总超时、逐帧超时、取消文件和异常均清理整个 Job；正常路径先关闭全部 page/context/browser，再清理 Job。PNG 单帧经有背压的管道交 FFmpeg，不缓存整段 RGBA；限制帧数、单次正序像素工作量（两次验证重绘另计）、文件数、归档字节及输出文件大小。当前限制为 1800 帧、单次正序 20 亿像素、256 个文件及 64 MiB 素材闭包；编码过程中检查 512 MiB 输出门限。两次全帧验证的重绘工作另计。worker Job 超时可设 1–1800 秒，探测/逐帧时钟核验另有局部超时；不承诺整个命令严格在同一墙钟期限结束。该工作量门限不等同于浏览器进程 RSS 的数学上界。

## 4. 事务与权利

dry-run 只规划，不启动浏览器、不写源码/输出。正式操作沿用项目锁、元数据事务、幂等键、快照和可选 expected_project_sha256；失败不增加资产或片段，诊断保留。新文件使用独占创建并在错误时撤销，不覆盖已有文件。派生视频权利依赖源码，源码依赖每个图片/字体；已有全局发布门禁继续生效。没有核验许可时只能内部使用。

## 5. 本轮验收目标和开放项

必须真实执行本地浏览器、任意帧/两次全帧乱序核对、透明编码/现有时间线叠加、文字/颜色参数重建、跨工程/片段组源码保留、失败回滚、外源拒绝、死循环超时及取消回收，并公开原创源文件、MP4/GIF、逐帧证据和实际运行限制。不能用 mock、仅返回码或源码存在代替上述结果。

完整 OpenFilm film.html 时间线/iframe/视频声音、WebGL、HTML 原生字幕编辑、模板控件自动提取、运动模糊、HDR/线性光、系统字体跨机器一致性、大型模板库、自然广告美学及完整剪映等价不在本批已验范围。
