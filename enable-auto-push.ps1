[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$gitDir = (git -C $repoRoot rev-parse --git-dir).Trim()
if (-not [System.IO.Path]::IsPathRooted($gitDir)) {
    $gitDir = Join-Path $repoRoot $gitDir
}
$hookDir = Join-Path $gitDir "hooks"
New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
$hookPath = Join-Path $hookDir "post-commit"
$hook = @'
#!/bin/sh
set -e
REPO_ROOT="$(git rev-parse --show-toplevel)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$REPO_ROOT\git-auto-push.ps1"
'@
Set-Content -LiteralPath $hookPath -Value $hook -Encoding ascii
Write-Output "Installed post-commit auto-push hook: $hookPath"

