# Local installation rules

Source: [luoluoluo22/jianying-editor-skill](https://github.com/luoluoluo22/jianying-editor-skill); source commit
`32c56928ded4f9e2c2b80e099dc7abb793d2c30b`. Original Skill: `jianying-editor`.
Local invocation: `$video-cut-jianying-editor`.

Apply these installation rules to the upstream examples in this package:

- Work in `E:\dev\sandbox\AI广告剪辑` or a task subdirectory below it. Keep new project content there.
- Use native Windows PowerShell, Python, Node.js and FFmpeg. Never launch local Docker,
  WSL, containers or another virtualization environment. Translate Bash-only commands
  into native Windows commands; do not run Unix installers on this machine.
- After browser work, close every unused tab to release memory.
- Use the locally registered `video-cut-` names for cross-Skill calls. Executable names,
  npm packages, API identifiers and engine flags keep their upstream names.
- Framework Skill refresh/install examples must preserve this namespace. Do not let a
  framework command replace these adapted packages or register unprefixed duplicates.
  The original repository snapshots remain in `AI广告剪辑/sources/` for review and updates.
- These packages install instructions and bundled resources. Before running a workflow,
  check its actual runtime dependencies and configured provider tools/credentials.

The installed Python helpers locate the prefixed Skill via the global Codex discovery folder.
For a copied business script, initialize it in native PowerShell with:

```powershell
$env:JY_SKILL_ROOT = 'E:\dev\sandbox\AI广告剪辑\skills\video-cut-jianying-editor'
```

Then follow `rules/setup.md`. Put new edit scripts in the user's project under `AI广告剪辑`,
not inside this reusable Skill. A usable JianYing installation, FFmpeg and the Python packages
in `requirements.txt` are separate runtime dependencies.
