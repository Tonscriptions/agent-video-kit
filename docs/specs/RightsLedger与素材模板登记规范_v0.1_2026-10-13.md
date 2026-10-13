# Rights Ledger 与素材模板登记规范 v0.1

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-RIGHTS-001 |
| 状态 | 评审中 |
| 版本 | 0.1.0 |
| 日期 | 2026-10-13 |
| 关联需求 | PRD-005、PRD-003 |
| 适用对象 | 视频、图片、音频、字体、模板、效果包、模型和生成结果 |

Rights Ledger 是发布资格的事实来源。开源软件、开放许可素材、可商用模板和 AI 生成结果是四类不同对象，不能因为仓库开源或网页可下载就自动获得广告商用资格。

## 1. 记录模型

每个资产一条稳定记录，推荐保存为 JSON/SQLite，并可导出 CSV。以下字段为最小集合：

| 字段 | 必须 | 说明 |
|---|---|---|
| `asset_id` | 是 | 项目内稳定 ID |
| `kind` | 是 | `video`、`image`、`audio`、`font`、`template`、`effect`、`model`、`generated` |
| `sha256` | 是 | 实际使用文件内容哈希 |
| `source_url` | 是 | 原始页面、仓库、API 或授权方地址 |
| `source_version` | 否 | Git commit、发布版本、快照日期或 API 版本 |
| `retrieved_at` | 是 | 下载或取得授权的时间 |
| `creator` | 是 | 作者、机构或生成系统 |
| `license_spdx` | 是 | SPDX 标识；无法映射时使用 `LicenseRef-*` 并附原文 |
| `license_url` | 是 | 许可证原文或授权条款 |
| `attribution` | 视许可证 | 发布时必须展示的归属文本 |
| `permitted_uses` | 是 | `commercial_ad`、`internal`、`research` 等 |
| `restrictions` | 是 | NC、ND、地域、平台、肖像、商标、再分发等限制 |
| `derived_from` | 否 | 生成、剪裁、混音或模板继承的父资产 ID |
| `evidence` | 是 | 保存许可证快照、网页存档、授权邮件或 API 响应的路径/哈希 |
| `verification_status` | 是 | 见第 2 节枚举 |
| `verified_by` | 否 | 人或自动检查器及版本 |
| `takedown_status` | 是 | `clear`、`notice`、`blocked` |
| `notes` | 否 | 争议、适用范围和人工判断 |

## 2. 状态机

`verification_status` 只能取以下值：

| 状态 | 含义 | 是否可进入预览 | 是否可发布 |
|---|---|---:|---:|
| `unverified` | 只有来源或文件，没有完成许可核验 | 是 | 否 |
| `verified` | 许可证、来源、哈希和用途已经核对 | 是 | 是，仍需渠道检查 |
| `restricted` | 仅允许指定项目、地域、平台或非商业用途 | 是 | 只有策略明确允许时 |
| `disputed` | 许可证、作者或投诉存在争议 | 否 | 否 |
| `expired` | 授权期限或订阅期限已结束 | 否 | 否 |
| `takedown` | 已收到撤下或侵权通知 | 否 | 否 |
| `blocked` | 策略或人工审核主动阻断 | 否 | 否 |

状态只能沿着以下方向变化：`unverified → verified/restricted/disputed/blocked`；`verified/restricted → expired/takedown/blocked`。恢复需要新的证据和审计记录，不能直接覆盖原记录。

## 3. 许可证策略

### 3.1 默认允许但仍需核验

- 软件与工具：MIT、BSD、Apache-2.0、AGPL/GPL 等，按软件分发形态和动态/静态链接另行审查；
- 素材：CC0、Public Domain、CC BY；CC BY 必须生成归属文本；
- 字体：明确允许商业嵌入和再分发的许可证；
- 模板：项目自有协议，且模板内部每个资产的许可证都已登记。

### 3.2 默认阻断或需要人工批准

- 许可证缺失、网页只写“免费”、来源无法追溯或下载页面要求登录但没有授权记录；
- CC BY-NC、CC BY-ND、仅个人使用、仅社交平台使用等限制与目标广告渠道冲突；
- 人像、商标、产品外观、新闻或数据集存在独立的肖像权、商标权、隐私或数据许可问题；
- AI 模型或生成结果的权利条款不清，尤其是训练数据、输出商业使用和声音/人脸身份授权不清；
- 模板含第三方音乐、字体、效果插件或云端服务，但模板说明没有逐项列出。

“开源”只描述代码或模型的分发方式，不自动描述媒体内容的广告使用许可。

## 4. 模板登记

模板是可执行项目配方，不是一个单独的视频文件。每个模板必须有：

- `template_id`、版本、作者、许可证和变更日志；
- 画幅、帧率、时长范围、轨道结构、变量 schema 和默认值；
- 所有字体、音乐、SFX、图片、视频、效果包和模型的资产 ID 列表；
- 变量是否允许替换、素材长宽比/时长约束、缺失变量策略；
- 预览图、测试项目、golden render 的哈希和适用渠道；
- 模板升级时的迁移规则和不兼容说明。

模板实例化必须生成一份不可变的 `template_snapshot`，记录当时使用的模板版本和每个资产版本。后续模板更新不能悄悄改变已发布项目。

## 5. 发布门禁

`rights check --target <channel>` 必须依次检查：

1. 所有资产都有记录、哈希和来源证据；
2. `verification_status` 不是 `unverified`、`disputed`、`expired`、`takedown` 或 `blocked`；
3. 许可证允许目标渠道、地域、商业用途和再分发方式；
4. 归属文本、字体声明、商标/肖像审批和模型声明齐全；
5. 模板内部依赖和生成结果的父资产都通过检查；
6. 项目、渲染清单和 Rights Ledger 使用同一资产哈希快照。

任何一项失败都必须返回退出码 7，并指出资产 ID、失败字段、证据路径和修复建议。`--yes` 不得绕过该门禁。

## 6. 记录示例

```json
{
  "asset_id": "audio.sfx.click.001",
  "kind": "audio",
  "sha256": "sha256:…",
  "source_url": "https://example.invalid/open-sfx/click",
  "source_version": "2026-01-03",
  "retrieved_at": "2026-10-13T00:00:00Z",
  "creator": "Example Author",
  "license_spdx": "CC0-1.0",
  "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
  "attribution": "",
  "permitted_uses": ["commercial_ad", "redistribution"],
  "restrictions": [],
  "evidence": [{"path": "rights/evidence/audio.sfx.click.001.html", "sha256": "sha256:…"}],
  "verification_status": "verified",
  "verified_by": "rights-checker/0.1.0",
  "takedown_status": "clear"
}
```

## 7. 变更与撤下

Rights Ledger 记录不允许原地覆盖关键许可字段。修订应生成新版本，引用 `supersedes`，保留旧证据和审计人。收到撤下、争议或许可证变更通知时，先把资产标记为 `takedown` 或 `disputed`，阻断新发布，再评估历史成片是否需要下架或替换。

