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
    throw "Auto-push is only allowed on the main branch; current branch is '$branch'."
}

$remote = (git remote get-url origin 2>$null).Trim()
if (-not $remote) {
    throw "The origin remote is not configured."
}

$arguments = @("push", "origin", "main")
if ($Force) { $arguments += "--force" }
if ($DryRun) { $arguments += "--dry-run" }
& git @arguments
if ($LASTEXITCODE -ne 0) {
    throw "git push failed with exit code $LASTEXITCODE."
}

