"""Publish measured V61 workflow scope without claiming a new editing kernel."""
import json
from pathlib import Path
from sync_color_automation_documents import marked,line
from audit_openfilm_workflow_delivery import ROOT,BASE,FINAL,DOCS,REPORT,CONTRACT


def read(path):return json.loads(path.read_bytes())


def run():
    media=read(BASE/'media.json')
    if media['status']!='passed_v61_controlled_media_audit' or media['caption_frames_with_safe_edges']!=94:
        raise ValueError('completed actual media audit required')
    short=read(ROOT/'docs/assets'/FINAL['shorts']/'verification.json')
    ref=read(ROOT/'docs/assets'/FINAL['reference']/'verification.json')
    screen=read(ROOT/'docs/assets'/FINAL['screen']/'verification.json')
    summary=(f'2026-10-19 **V61（Agent 工作流适配）**：将固定 OpenFilm 的参考片重建、长转短、录屏演示创作要求适配为 '
      '**3 个本地 `video-cut-` Skill，累计 17 个**；沿用现有编辑内核。'
      f'当前 **{media["current_cli_calls"]} 次真实 CLI、158 个最终编码帧/PTS、948,000 个立体声采样帧**；'
      '长转短另有 94 个中间基础帧，不叠加为最终产量。参考运镜中心最大差 '
      f'{ref["max_center_error_px"]:.3f} 像素；字幕前源帧最大差 2，三类 PCM 最大差 0；'
      f'录屏控件边缘最大差 {media["screen_max_edge_error_px"]:.3f} 像素，5 次回全景 RGB 最大差 '
      f'{media["screen_full_view_max_rgb_error"]}，94 帧字幕安全边缘通过。'
      '**188 产品输入与 V60 相同，沿用已完成的 1374/1374，未重跑完整回归**。'
      '首轮音频/时长失败、第二版出框/裁切及后续底边拒绝保留。'
      '公开原片、无音预览/GIF；生成语音仅内部使用、商业权利拒绝。'
      '未连续播放/听审；自动语义/点击识别、自然质量及完整剪映等价未验收。')
    report=f'''# OpenFilm 三套本地创作 Skill 与实片核验

{summary}

依据[先行契约及视觉检查后的 G61-13 补充](../specs/{CONTRACT})，对应[15 步适配设计](../OpenFilm创作流程本地适配设计_2026-10-19.md)。本轮增加可复用的 Agent 创作流程，没有新增语义模型、录屏识别算法或第二套编辑内核；三个入口驱动已有原生 Python/FFmpeg、字幕和时间线命令。

## 编号实现与实际结果

| 编号 | 流程/入口 | 实测与证据 | 范围 |
|---|---|---|---|
| V61-01 | `$video-cut-reference-remake` | 原创参考 3 段/24 帧重建，换为独立生产卡片；同剪口、二次缓动锚点最大差 {ref['max_center_error_px']:.6f} px，144,000 立体声采样帧误差 0 | 原参考 SHA 不在生产素材图；比较结构和运动，不宣称不同内容逐像素相等 |
| V61-02 | `$video-cut-long-to-short` | 提供完整已知条件/否定/结论原文，3 次本地 flite 合成后剪为 32 帧/4 秒、62 帧/7.75 秒两条；共 564,000 采样帧误差 0，字幕前原源 RGB 最大差 2 | 明确提供整句源时间，不是 ASR、字词声学精度或自动语义选择通过；字幕后音频与基础版完全一致 |
| V61-03 | 长转短显示 | 94 个最终字幕帧与基础版差分，字幕像素/背景框在声明的左右 16 px、底边大于 14 px 范围；已查看三时刻/两条片 | 当前横向受控画布，不代替竖屏讲话人重构图或任意语言/字体验收 |
| V61-04 | `$video-cut-screen-demo` | 原创受控页面真实执行选择、输入、预览、保存共 4 动作；48 张源截图采样为 6 秒；去掉首秒等待，生成 40 帧/5 秒 | 作者赋予的 8 fps 时钟，不是真实响应耗时；不是编辑器 GUI 或自然商业软件录屏 |
| V61-05 | 操作后展示结果 | 编码控件边缘独立投影最大差 {media['screen_max_edge_error_px']:.3f} px；每个动作聚焦后回到全景，5 帧 RGB 最大差 {media['screen_full_view_max_rgb_error']}；240,000 立体声采样帧误差 0 | 明确源锚点和位置/缩放关键帧，未运行 UI OCR、自动点击恢复或隐私发现 |
| V61-06 | 编辑与资源 | dry-run 后工程 SHA 不变，正式 compose、render、quality/policy/rights 与可编辑工程包；当前 {media['current_cli_calls']} 次 CLI 按下面三例分计 | 两条有生成语音的工程商业权利检查实际退出 7，内部渲染可用；未将其改成已验证 CC0 |
| V61-07 | 许可与发布 | 原创画面/文本/测试页 CC0；DejaVu/Bitstream 字体 notice 独立保存；固定 OpenFilm MIT notice 保留 | 生成语音的 WAV/AV 源和输出只保留本机，不进入 Git；公开 GIF/MP4 无音，不能代表听感验收 |
| V61-08 | 原生与清理 | 无 Docker/WSL/虚拟环境、网络或下载；三次页面捕获每次 1 页关闭，Windows Job 无残留 | 只回收自建进程；未操作其它用户服务或窗口 |
| V61-09 | 产品和回归 | 188 份产品/测试/Schema/发行输入与 V60 冻结字节相等 | 沿用 V60 已完成 1374/1374、2480.857 秒、0 跳过；没有新产品回归或新离线发行包 |
| V61-10 | Skill 注册 | 三个新入口使用 E 盘规范目录和同名 C 盘 junction，累计 17 个；逐项 `quick_validate` 与全部本地引用核对 | 数量不代表功能覆盖率，当前会话的技能目录不会自动回写已加载工具清单；后续调用可用相应入口 |

当前 CLI 分计：参考重建 {media['current_cli_by_case']['reference']}、长转短 {media['current_cli_by_case']['shorts']}、录屏 {media['current_cli_by_case']['screen']}；包含预期权利拒绝，和单元测试数不相加。当前新 flite 合成 3 次，前三版累计 9 次另计；0 新神经模型前向。最终 158 帧包括参考 24、两条短片 94、录屏 40；中间字幕前 94 帧另列。只有 3 组原创受控来源，重复复测不增加来源场景数。

## 原片、结果与 GIF

**参考片重建**：[原创参考视频](../assets/{FINAL['reference']}/reference-input.mp4)、[换内容后的重建视频](../assets/{FINAL['reference']}/remade-preview.mp4)、[可编辑工程包](../assets/{FINAL['reference']}/remade.aevpkg.zip)。

![参考节奏与运镜重建，内容为独立替换素材](../assets/{FINAL['reference']}/remade-preview.gif)

**长转短**：[原始长片无音预览](../assets/{FINAL['shorts']}/original-silent.mp4)、[完整已知原文/源区间](../assets/{FINAL['shorts']}/supplied-transcript.json)、[短片 1 无音](../assets/{FINAL['shorts']}/short-1-silent.mp4)、[短片 2 无音](../assets/{FINAL['shorts']}/short-2-silent.mp4)、[两条清单](../assets/{FINAL['shorts']}/shorts.json)。当前原始音视频及生成语音权利未验收，均留在本机；无音预览不能证明发音、自然听感或语音发布完成。

![保留完整条件句的短片，无音画面预览](../assets/{FINAL['shorts']}/short-1-silent.gif)

**录屏锚点**：[原始受控测试页录屏](../assets/{FINAL['screen']}/screen-input-preview.mp4)、[剪辑后无音预览](../assets/{FINAL['screen']}/screen-demo-preview.mp4)、[实际页面及源动作](../assets/{FINAL['screen']}/capture.stdout.json)、[独立几何与回全景](../assets/{FINAL['screen']}/action-anchors.json)、[可编辑工程包](../assets/{FINAL['screen']}/screen-demo.aevpkg.zip)。

![真实测试页操作的显式锚点聚焦并回全景，不是自动点击识别](../assets/{FINAL['screen']}/screen-demo-preview.gif)

已查看[参考片三时刻](../assets/openfilm-workflow-review-20261019-v61/reference-contact.png)、[修订后短片三时刻](../assets/openfilm-workflow-review-20261019-v61-r3/shorts-contact.png)、[修订后录屏三时刻](../assets/openfilm-workflow-review-20261019-v61-r3/screen-contact.png)。这些是静帧观察，未连续播放/听审；机器核对 PTS/PCM 不替代人类内容体验。

## 原始失败与观察后修订

| 编号 | 实际问题 | 处理 |
|---|---|---|
| DEV61-01 | 长转短首轮 RGB 最大差 2，但 PCM 最大差 0.42913818359375，输出静音 | 夹具只放视频。按当前内核补同源/同范围、共享 link_id 的音频片段，未修改内核或放宽误差；[原失败](../assets/openfilm-workflow-shorts-20261019-v61-r1/verification.json)保留 |
| DEV61-02 | 录屏首轮去掉 1 秒等待后，项目总长仍为 6 秒 | 将拟交付项目明确设为 5 秒；[原失败](../assets/openfilm-workflow-screen-20261019-v61-r1/verification.json)及浏览器清理收据保留 |
| DEV61-03 | 第二版技术检查通过，静帧发现长字幕左右出框 | 保留[第二版技术收据](../assets/openfilm-workflow-shorts-20261019-v61-r2/verification.json)，改显式 24 字号与安全位置；不把原技术通过回写成视觉验收 |
| DEV61-04 | 第二版锚点几何正确，持续缩放裁掉预览/保存状态 | 保留[原版](../assets/openfilm-workflow-screen-20261019-v61-r2/verification.json)，追加操作后回全景关键帧和实际 RGB 检查 |
| DEV61-05 | 后续逐帧检查发现字幕背景框距底边 12 px | [原拒绝](evidence/openfilm-workflows-20261019-v61/caption-safe-edge-failure.json)保留，上移 8 px，94 帧重新核对；没有减小边距门槛 |

三类技能的实现边界来自这些实际检查，而非把成功返回当成可交付。原生成器、执行日志、逐文件 SHA、实际媒体与失败版本均保留。

## 复现与后续

[媒体收据](evidence/openfilm-workflows-20261019-v61/media.json)、[静帧观察及历史摘要](evidence/openfilm-workflows-20261019-v61/visual-review-final.json)；最终发行范围核验另存同目录 `release.json`。各例目录的 `verification.json` 列出逐命令 stdout/stderr；大型原始 RGB stdout 用 gzip 原样压缩，同时保存解压后的字节数/SHA。不是模型推理输入的压缩降质。

```powershell
C:/Python313/python.exe -B -X utf8 scripts/smoke_openfilm_workflow_reference.py --work product/.runtime/<新目录> --output docs/assets/<新参考例>
C:/Python313/python.exe -B -X utf8 scripts/smoke_openfilm_workflow_shorts.py --work product/.runtime/<新目录> --output docs/assets/<新短片例>
C:/Python313/python.exe -B -X utf8 scripts/smoke_openfilm_workflow_screen.py --work product/.runtime/<新目录> --output docs/assets/<新录屏例>
```

录屏样例依赖本机已有、显式登记的原生 Node/Playwright/Chromium 工具链；脚本不会安装或下载它们。本地生成语音的技术结果不能自动公开。复用成本仅证明三套流程可以沿既有内核组织，未记录独立人时对照，不能量化整个项目节省百分比。

自动语义选段、自然转写/字词时间、讲话人跟踪、UI OCR/点击恢复、全隐私发现、任意参考片风格/相机理解、自然美学/听感、竖屏/长片/HDR、多设备及完整剪映等价继续开放；V60 修订版 VACE 真模型完整交付也仍待验。本轮没有用 Skill 或受控页面替代这些要求。
'''
    (ROOT/'docs/validation'/REPORT).write_text(report,encoding='utf-8',newline='\n')
    for name in DOCS:
        path=ROOT/name;text=path.read_text(encoding='utf-8')
        text=text.replace('\n2026-10-19 **V60（产品增量','\n历史产品 2026-10-19 **V60（产品增量')
        prefix='docs/validation/' if name=='README.md' else ('./' if name.startswith('docs/validation/') else 'validation/')
        block=summary+f' [原片/GIF/实测/失败/Skill]({prefix}{REPORT})。'
        if '<!-- V61-CURRENT -->' in text:text=marked(text,'V61-CURRENT',block)
        else:
            index=text.index('\n')+1;text=text[:index]+'\n<!-- V61-CURRENT -->\n'+block+'\n<!-- /V61-CURRENT -->\n'+text[index:]
        if name=='README.md':
            row=f'| V61 | OpenFilm 三套本地创作 Skill | 17 Skills；{media["current_cli_calls"]} CLI/158 最终帧/948,000 立体声采样帧；94 帧字幕边缘与全景回归 | 188 产品输入同 V60；语音仅内部，自动语义/点击与完整等价未验收 | [原片/GIF/失败/范围]({prefix}{REPORT}) |'
            if '| V61 |' in text:text=line(text,'| V61 |',row)
            else:
                lines=text.splitlines();index=next(i for i,x in enumerate(lines) if x.startswith('| V60 |'));lines.insert(index+1,row);text='\n'.join(lines)+'\n'
            demo=(f'**V61 OpenFilm 创作流程适配**：[参考重建/长转短/录屏原片与失败](docs/validation/{REPORT})；'
                  '下图是原创测试页真实操作的显式锚点演示，未自动识别点击。\n\n'
                  f'![真实测试页锚点聚焦后回到全景](docs/assets/{FINAL["screen"]}/screen-demo-preview.gif)')
            if '<!-- V61-DEMO -->' in text:text=marked(text,'V61-DEMO',demo)
            else:text=text.replace('<!-- V60-DEMO -->','<!-- V61-DEMO -->\n'+demo+'\n<!-- /V61-DEMO -->\n\n<!-- V60-DEMO -->',1)
        if name=='docs/构建进度总表_2026-10-16.md':
            text=line(text,'| 24 |','| 24 | Agent Skills | 已实现，持续扩展 | V61 共 17 个 video-cut- Skill；参考片重建、长转短、录屏显式锚点，实际媒体/失败/安全边缘核验 | 自动语义选段/字词精度/自然质量与完整等价继续开放；Skill 数不是覆盖率 |')
        if name.endswith('能力覆盖与验收矩阵_v0.1_2026-10-13.md'):
            row=f'| 三套本地创作工作流（V61） | 参考片独立重建、整句源范围长转短、真实测试页显式锚点聚焦/回全景 | [17 Skills/{media["current_cli_calls"]} CLI/158 帧与失败]({REPORT})；188 产品输入同 V60 | 未新增自动语义、讲话人、OCR/点击模型；语音权利/自然体验和完整等价未验收 |'
            if '| 三套本地创作工作流（V61） |' in text:text=line(text,'| 三套本地创作工作流（V61） |',row)
            else:text=text.replace('| VACE 物理 GPU 准入（V60） |',row+'\n| VACE 物理 GPU 准入（V60） |',1)
        path.write_text(text,encoding='utf-8',newline='\n')
    design=ROOT/'docs/OpenFilm创作流程本地适配设计_2026-10-19.md';text=design.read_text(encoding='utf-8')
    text=text.replace('这是 [R05 复用评估]','以下是原 [R05 复用评估]').replace('的设计补充，没有新增生产功能或安装 Skill。','的设计补充，当时没有新增生产功能或安装 Skill。')
    text=text.replace('拟安装名称为','R05 设计时拟安装名称为').replace('**当前三者均未创建、未注册**','**该设计时三者均未创建、未注册**')
    block=f'V61 后续实现：三个入口已完成本地适配与实片核验并注册，累计 17 Skills。见[当前原片/GIF/失败与实际范围](validation/{REPORT})；本页的 22 路由检查仍是原 R05 声明研究，不能当作实片核验。'
    if '<!-- V61-IMPLEMENTED -->' in text:text=marked(text,'V61-IMPLEMENTED',block)
    else:
        index=text.index('\n')+1;text=text[:index]+'\n<!-- V61-IMPLEMENTED -->\n'+block+'\n<!-- /V61-IMPLEMENTED -->\n'+text[index:]
    design.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'documents':9,'new_skills':3,'total_skills':17,'current_cli_calls':media['current_cli_calls']}))


if __name__=='__main__':run()
