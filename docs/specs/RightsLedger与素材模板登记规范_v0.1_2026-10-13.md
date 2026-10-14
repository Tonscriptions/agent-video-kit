# Rights Ledger 与素材模板登记规范 v0.2

| 项目 | 内容 |
|---|---|
| 文档编号 | SPEC-RIGHTS-001 |
| 状态 | 有效 |
| 版本 | 0.2.0 |
| 日期 | 2026-10-14 |
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
| `source_url` | 是 | 本地路径、`local://` 或 `file://` 来源引用；运行时禁止远程 URL |
| `source_version` | 否 | Git commit、发布版本、快照日期或 API 版本 |
| `retrieved_at` | 是 | 下载或取得授权的时间 |
| `creator` | 是 | 作者、机构或生成系统 |
| `license_spdx` | 是 | SPDX 标识；无法映射时使用 `LicenseRef-*` 并附原文 |
| `license_url` | 是 | 项目内许可证快照或 `local://` 授权条款引用 |
| `attribution` | 视许可证 | 发布时必须展示的归属文本 |
| `permitted_uses` | 是 | `commercial_ad`、`internal`、`research` 等 |
| `restrictions` | 是 | NC、ND、地域、平台、肖像、商标、再分发等限制 |
| `derived_from` | 否 | 生成、剪裁、混音或模板继承的父资产 ID |
| `evidence` | 是 | 保存许可证快照、网页存档、授权邮件或 API 响应的路径/哈希 |
| `verification_status` | 是 | 见第 2 节枚举 |
| `verified_by` | 否 | 人或自动检查器及版本 |
| `takedown_status` | 是 | `clear`、`notice`、`blocked` |
| `permitted_channels` | 否 | 允许发布的渠道；空数组表示沿用用途策略，`all` 表示所有本地声明渠道 |
| `expires_at` | 否 | ISO-8601 授权截止时间；过期自动阻断发布 |
| `record_id` / `record_version` | 系统 | 不可变修订 ID 和从 1 开始的版本号 |
| `active` / `supersedes` / `superseded_by` | 系统 | 当前版本标记和修订链 |
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

## 3. 版本化修订与 CLI

Rights Ledger 的关键许可字段不能原地覆盖。每次更新都会保留旧记录，写入新的 `record_id`、递增 `record_version`、`supersedes`、操作者、原因和时间，并在 `events` 中追加审计事件。`rights update` 在写入前自动创建项目快照；`--dry-run` 只返回计划，不修改项目。

```powershell
python -m ai_ad_editor rights list --project .\project
python -m ai_ad_editor rights history --project .\project --asset-id asset_001
python -m ai_ad_editor rights update --project .\project --asset-id asset_001 --status takedown --reason "notice received" --actor reviewer
python -m ai_ad_editor rights update --project .\project --asset-id asset_001 --status verified --reopen --reason "evidence cleared" --evidence local://rights/new-proof
python -m ai_ad_editor rights export --project .\project --target commercial_ad --output .\project\exports\release.json
python -m ai_ad_editor rights batch-update --project .\project --input .\rights-updates.json
python -m ai_ad_editor rights impact --project .\project --asset-id asset_001
python -m ai_ad_editor rights retract --project .\project --asset-id asset_001 --reason "license notice"
python -m ai_ad_editor rights decide --project .\project --asset-id asset_001 --action replace --replacement-asset-id asset_002 --status approved --reason "replace historical usage"
python -m ai_ad_editor rights decide --project .\project --asset-id asset_001 --action replace --replacement-asset-id asset_002 --status cancelled --supersedes-decision-id rightsdecision_... --reason "replacement withdrawn"
python -m ai_ad_editor rights apply --project .\project --decision-id rightsdecision_...
```

从 `disputed`、`expired`、`takedown` 或 `blocked` 恢复到 `verified/restricted` 必须同时提供 `--reopen` 和不同于旧记录的本地证据。撤下或争议状态会自动把 `takedown_status` 置为 `notice`；恢复时若未显式指定则清除为 `clear`。

模板登记中的 `assets`/`dependencies`、项目资产的 `derived_from` 父资产会递归纳入发布检查。缺失依赖返回 `RIGHTS_TEMPLATE_DEPENDENCY_MISSING`，缺失父资产返回 `RIGHTS_RECORD_MISSING`，项目资产哈希与台账快照不一致返回 `RIGHTS_HASH_MISMATCH`。`rights batch-update` 先在内存中预检全部项目，再创建单个快照并提交；`rights retract` 只阻断新发布并生成 `rights impact` 报告，不擅自删除历史成片。`rights decide` 将历史成片的 `replace`、`delete` 或 `retain` 决策追加到 Ledger，保存受影响产物、替代资产、目标渠道、原因和操作者；`approved` 的 replace/delete 决策会以 `RIGHTS_DISPOSITION_BLOCKED` 阻断后续发布，命令不会删除或改写历史媒体，替换/删除动作由 Agent 根据影响清单执行并再次验证。

## 4. 许可证策略

### 4.1 默认允许但仍需核验

- 软件与工具：MIT、BSD、Apache-2.0、AGPL/GPL 等，按软件分发形态和动态/静态链接另行审查；
- 素材：CC0、Public Domain、CC BY；CC BY 必须生成归属文本；
- 字体：明确允许商业嵌入和再分发的许可证；
- 模板：项目自有协议，且模板内部每个资产的许可证都已登记。

### 4.2 默认阻断或需要人工批准

- 许可证缺失、网页只写“免费”、来源无法追溯或下载页面要求登录但没有授权记录；
- CC BY-NC、CC BY-ND、仅个人使用、仅社交平台使用等限制与目标广告渠道冲突；
- 人像、商标、产品外观、新闻或数据集存在独立的肖像权、商标权、隐私或数据许可问题；
- AI 模型或生成结果的权利条款不清，尤其是训练数据、输出商业使用和声音/人脸身份授权不清；
- 模板含第三方音乐、字体、效果插件或云端服务，但模板说明没有逐项列出。

“开源”只描述代码或模型的分发方式，不自动描述媒体内容的广告使用许可。

## 5. 模板登记

模板是可执行项目配方，不是一个单独的视频文件。每个模板必须有：

- `template_id`、版本、作者、许可证和变更日志；
- 画幅、帧率、时长范围、轨道结构、变量 schema 和默认值；
- 所有字体、音乐、SFX、图片、视频、效果包和模型的资产 ID 列表；
- 变量是否允许替换、素材长宽比/时长约束、缺失变量策略；
- 预览图、测试项目、golden render 的哈希和适用渠道；
- 模板升级时的迁移规则和不兼容说明。

模板实例化必须生成一份不可变的 `template_snapshot`，记录当时使用的模板版本和每个资产版本。后续模板更新不能悄悄改变已发布项目。

## 6. 发布门禁

`rights check --target <channel>` 必须依次检查：

1. 所有资产都有记录、哈希和来源证据；
2. `verification_status` 不是 `unverified`、`disputed`、`expired`、`takedown` 或 `blocked`，且 `takedown_status` 为 `clear`；
3. 许可证允许目标渠道、地域、商业用途和再分发方式；`permitted_channels` 非空时必须包含目标渠道或 `all`；
4. `expires_at` 缺失或尚未到期；
5. 归属文本、字体声明、商标/肖像审批和模型声明齐全；
6. 模板内部依赖和生成结果的父资产都通过检查；
7. 模板、`derived_from` 父资产和生成结果的全部依赖都能追溯到有效记录；
8. 项目、渲染清单和 Rights Ledger 使用同一资产哈希快照。
9. 当前有效历史处置决策中，没有对目标渠道和依赖资产生效的已批准 replace/delete。

任何一项失败都必须返回退出码 7，并指出资产 ID、失败字段、证据路径和修复建议。`--yes` 不得绕过该门禁。

`rights export` 将上述检查结果、项目资产哈希、模板快照、全部父资产/模板依赖的有效记录 ID/版本、许可证、归属和允许渠道写入项目内发布清单，并附确定性 `manifest_sha256`。检查失败仍可导出清单供修复审查，但命令返回退出码 7。

Ledger 顶层可选 `decisions` 数组保存历史处置决策。每项至少包含 `decision_id`、`asset_id`、`action`、`status`、`replacement_asset_id`、`target`、`reason`、`actor`、`affected_artifacts` 和 `created_at`，状态修订还要包含 `supersedes`。`proposed` 只产生警告，`approved` 对当前项目引用生效，`cancelled` 保留历史但不参与阻断。状态变更必须追加新决策，并用 `supersedes` 指向当前有效的 `decision_id`；不能跳过当前决策、回退已取消决策或改变原资产/动作/目标/替代资产范围。批准替换前会再次检查替代资产和其依赖的 Rights Ledger 门禁。决策本身是追加式证据，不是文件删除授权；任何外部删除、替换或重新渲染必须形成新的项目变更、快照和质量/权利报告。

| 当前状态 | 可追加的状态 | 门禁行为 |
|---|---|---|
| 无前序决策 | proposed、approved | 新建独立处置范围 |
| proposed | proposed、approved、cancelled | 最新有效记录替代原警告；批准后阻断 |
| approved | approved、cancelled | 保持阻断或显式撤销；不能降回 proposed |
| cancelled | 无 | 历史链终止；新的处置必须创建独立决策 |

并行独立决策分别生效。撤销一条决策不会解除另一条已批准决策，也不会解除资产自身的撤下、争议、过期或许可证限制。新修订继承原 `affected_artifacts` 快照，`rights history` 的 `effective_decisions` 用于定位当前 `decision_id`。`rights apply` 是单独的执行步骤：只接受当前有效的 approved replace/delete，先创建快照，再更新/移除当前项目的时间线引用和资产记录，完成结构校验后追加 `disposition_applied` 事件；历史导出 JSON 和媒体文件不会被删除或覆盖。错误包括 `RIGHTS_DISPOSITION_MISSING`、`RIGHTS_DISPOSITION_STALE`、`RIGHTS_DISPOSITION_SCOPE_MISMATCH`、`RIGHTS_DISPOSITION_TRANSITION_INVALID`、`RIGHTS_DISPOSITION_PREDECESSOR_REQUIRED`、`RIGHTS_DISPOSITION_NOT_APPROVED`、`RIGHTS_DISPOSITION_REFERENCES_REMAIN` 和替代资产依赖不完整的 `RIGHTS_REPLACEMENT_NOT_PUBLISHABLE`；全部在项目写入前返回。

## 7. 记录示例

```json
{
  "asset_id": "audio.sfx.click.001",
  "kind": "audio",
  "sha256": "sha256:…",
  "source_url": "local://rights/sources/open-sfx/click",
  "source_version": "2026-01-03",
  "retrieved_at": "2026-10-13T00:00:00Z",
  "creator": "Example Author",
  "license_spdx": "CC0-1.0",
  "license_url": "local://rights/licenses/CC0-1.0.txt",
  "attribution": "",
  "permitted_uses": ["commercial_ad", "redistribution"],
  "restrictions": [],
  "evidence": [{"path": "rights/evidence/audio.sfx.click.001.html", "sha256": "sha256:…"}],
  "verification_status": "verified",
  "verified_by": "rights-checker/0.1.0",
  "takedown_status": "clear",
  "permitted_channels": ["commercial_ad"],
  "record_id": "rights_20261014000000_ab12cd34",
  "record_version": 1,
  "active": true
}
```

## 8. 变更与撤下

Rights Ledger 记录不允许原地覆盖关键许可字段。修订应生成新版本，引用 `supersedes`，保留旧证据和审计人。收到撤下、争议或许可证变更通知时，先把资产标记为 `takedown` 或 `disputed`，阻断新发布，再评估历史成片是否需要下架或替换。

