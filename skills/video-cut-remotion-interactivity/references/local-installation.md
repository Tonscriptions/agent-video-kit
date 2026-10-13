# Local installation rules

Source: [remotion-dev/skills](https://github.com/remotion-dev/skills); source commit
`32b241b97f4e0e4ab61fe9a41b05e6e64503f8c5`. Original Skill: `remotion-interactivity`.
Local invocation: `$video-cut-remotion-interactivity`.

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


