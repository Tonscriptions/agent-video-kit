# macOS 剪映 / CapCut 常见路径

草稿目录名多为 `com.lveditor.draft`，其下每个子目录通常对应一个草稿。

## 常见位置

1. `~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft`
2. `~/Movies/CapCut/User Data/Projects/com.lveditor.draft`
3. `~/Library/Application Support/JianyingPro/User Data/Projects/com.lveditor.draft`
4. 若从 Mac App Store / 沙箱安装：`~/Library/Containers/<AppBundle>/Data/Movies/JianyingPro/...`

以本 Skill 的 `python3 scripts/capcut_paths.py` 实际输出为准。

## 环境变量

- `CAPCUT_DRAFT_ROOT` 或 `JIANYING_DRAFT_ROOT`：强制指定单一草稿根目录（用于非标准安装路径）。
