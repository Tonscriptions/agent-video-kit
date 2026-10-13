param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgumentList
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$sourceRoot = Join-Path $projectRoot 'product\src'
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$sourceRoot;$env:PYTHONPATH" } else { $sourceRoot }
$runtimeRoot = Join-Path $projectRoot 'product\.runtime'
$runtimeTemp = Join-Path $runtimeRoot 'temp'
New-Item -ItemType Directory -Path $runtimeTemp -Force | Out-Null
$env:AI_AD_EDITOR_RUNTIME_DIR = $runtimeRoot
$env:TEMP = $runtimeTemp
$env:TMP = $runtimeTemp
$env:TMPDIR = $runtimeTemp
$env:PYTHONPYCACHEPREFIX = Join-Path $runtimeRoot 'cache\python'
$env:PYTHONUTF8 = '1'

& python -m ai_ad_editor @ArgumentList
exit $LASTEXITCODE
