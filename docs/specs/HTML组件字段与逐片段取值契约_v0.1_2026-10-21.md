# HTML 组件字段与逐片段取值契约 v0.1

状态：V79 已按下列限定契约验收；不表示完整剪映等价。

## 作者数据与命令

定义为 `component_fields` 数组，每项有稳定 `id`、唯一可读 `name`、`type=text|image|boolean|var`。文字 / 图片 / 显隐使用 `at` 与可选 `n`；图片另有 `kind=img|bg`；变量使用 `var=--name`。同一类型的相同目标不得重复；不同类型可以指向同一元素。改名保留 ID；更换类型或目标必须在一次明确的定义替换中完成。

`motion html-source` 输入清单可含 `component_fields`，保存在源资产 `html_source` 元数据，不把工程资产 ID 写入不可变的源码 ZIP。源 HTML、脚本和成员字节保持原样。已登记的旧源可在渲染时通过 `--component-fields <local.json>` 提供完整定义替换，不需要重写源 HTML。

`motion html-fields --project P (--source-asset-id S|--from-asset-id A) [--component-fields FILE]` 不执行浏览器，返回字段清单、逐片段当前值、有效默认值来源和可直接验证的 JSON Schema。与 `html-render` / `html-controls` / `html-quality` 共用字段和值校验。

上述三个绘制命令接受 `--component-fields FILE`、`--component-values FILE`、`--reset-components`。取值文件为字段 ID 到有类型值 / null 的对象；null 撤销该字段的显式值，全量重置清空组件值后再应用本次补丁。不删除原 `parameters` 或 `template_overrides`。未知字段、重复 JSON 键、非有限数、无效 Schema 和超预算必须报结构化错误。

每个新输出的 `html_motion` 保存定义快照和独立的 `component_values` 数组：`[{"field_id":"headline","value":"新的标题"}]`。数组形态避免用户字段名被误识别为工程资源引用。图片值为 `{"asset_id":"local_image"}`，便于包、片段库和队列沿用既有 ID 闭包与映射。重建默认继承原输出的定义和值；替换定义以相同 ID 保留值，仍有取值的字段被删除时须同时 null / reset，不能静默丢弃。

`html-render --from-asset-id A --replace-clip-id C` 可选择仅换指定片段的资产引用：保留原剪入剪出、速度、变换、特效、关键帧、轨道和其他片段；要求该片段引用 A、目标轨未锁定、沿用工程摘要与事务。与 `--apply` 新增入轨互斥。不改写旧输出或原源码。

## 类型、默认值和预算

字段可有 `schema` 子集：`type`、`minimum`、`maximum`、`minLength`、`maxLength`、`enum`，不支持可执行表达式或任意 `$ref`。text 为 string，image 为含单个 asset_id 的对象，boolean 为 boolean；var 可为 string / number / integer。数值变量可声明 `unit`（明确 CSS 单位），输出时附加单位；字符串变量沿用现有 CSS 安全值规则。范围、单位、选项、目标与默认值均出现在发现结果中。

text / image / var 可声明 `default`；省略 / null 表示原页面。boolean 的默认值只允许 null（原页面状态），true / false 仅为逐片段显式值。这样 boolean reset 一定恢复页面自身状态，而非把隐藏对象强制显示。空文字是有效覆盖；0 与 false 不能当作未设置。

最多 128 个字段；定义、取值与合并后有效覆盖各最多 64 KiB，组件与普通覆盖共用 128 项 / 64 KiB、64 个 CSS 变量、512 字符 selector、n=1..1024 及既有 1024 匹配总量。组件在普通覆盖之后应用，重置组件后普通覆盖仍生效。字段默认值也计入有效覆盖，不以拆成两份规避预算。

## 本地图片与显隐执行

图片值必须是源资产已声明资源闭包中的 image 资产 ID；核对源码内资源、当前登记资产和磁盘实际 SHA，并执行所选图片及其派生依赖的现有 strict `commercial_ad` 权利检查。缺失、内容变化、远程地址、闭包外图片和权利不满足时在启动浏览器前拒绝。新增素材须明确登记并建立新的源资源闭包，不把任意字符串变成 URL。默认图片与选择列表也须满足登记和闭包结构；实际使用的图片才执行逐次权利 gate。

每次绘制先恢复上一次覆盖，再执行原页面 `frame(t)`，最后普通覆盖、组件覆盖。false 以 CSS visibility 隐藏目标并保留布局；true 强制目标自身 visibility，临时移除其 hidden 属性，目标自身 display:none 时用 display:revert 恢复 UA 默认布局。恢复时还原属性的原值、样式及优先级，再由页面重绘。true 不能保证显示仍被祖先 display:none / 裁切隐藏的目标，也不改变祖先或隐藏子元素。重置时不写可见性，恢复原页面对该帧的决定。

不得增加任意 style / URL 写入能力，不改变现有可信本地模板执行边界。原生浏览器 Job 负责超时、取消、进程树 / 页面回收；不打开 Studio、GUI、网络资源或虚拟化环境。

## 发布验收

先验证定义 / Schema / typed 值 / 合并预算，再验证真实原生像素：原来隐藏 / 显示、逐帧显隐切换、空文字、变量范围 / 单位、已登记图片、单项 / 全量 reset 与混合普通覆盖。改名保值、失败无半写、锁与摘要、逐片段替换、包 / 片段 / 队列可编辑重建须实际执行。离线 wheel 与隔离入口的资源字节、能力发现和实际输出要与开发版分别核对。

完整回归、真实 CLI、公开原输入与 MP4 / GIF、失败记录、README 编号表、相关 `video-cut-` Skill 和发布字节核对完成前，不把本契约改为已实现或剪映等价。
