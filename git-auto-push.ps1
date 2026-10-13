[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repoRoot

$branch = (git branch --show-current).Trim()
if ($branch -ne "main") {
    throw "自动推送只允许 main 分支，当前分支为 '$branch'。"
}

$remote = (git remote get-url origin 2>$null).Trim()
if (-not $remote) {
    throw "没有配置 origin 远端。"
}

$arguments = @("push", "origin", "main")
if ($Force) { $arguments += "--force" }
if ($DryRun) { $arguments += "--dry-run" }
& git @arguments
if ($LASTEXITCODE -ne 0) {
    throw "git push 失败，退出码 $LASTEXITCODE。"
}

