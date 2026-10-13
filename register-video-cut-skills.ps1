param()
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifestPath = Join-Path $projectRoot 'video-cut-install-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$canonicalRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'skills')).TrimEnd('\') + '\'
$discoveryRoot = [IO.Path]::GetFullPath($manifest.codex_skills_directory)

# Verify all targets before creating junctions. Existing unrelated directories are preserved.
foreach ($skillEntry in $manifest.skills) {
    if ($skillEntry.name -notmatch '^video-cut-[a-z0-9-]+$') {
        throw "Invalid prefixed Skill name: $($skillEntry.name)"
    }
    $canonicalPath = [IO.Path]::GetFullPath($skillEntry.canonical_directory)
    if (-not $canonicalPath.StartsWith($canonicalRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Skill target is outside the project library: $canonicalPath"
    }
    if (-not (Test-Path -LiteralPath (Join-Path $canonicalPath 'SKILL.md') -PathType Leaf)) {
        throw "SKILL.md missing: $canonicalPath"
    }
    $registrationPath = [IO.Path]::GetFullPath((Join-Path $discoveryRoot $skillEntry.name))
    if ($registrationPath -ne [IO.Path]::GetFullPath($skillEntry.registration_directory)) {
        throw "Unexpected registration path: $registrationPath"
    }
    if (Test-Path -LiteralPath $registrationPath) {
        $existing = Get-Item -LiteralPath $registrationPath -Force
        if ($existing.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$existing.Target).TrimEnd('\') -ne $canonicalPath.TrimEnd('\')) {
            throw "Existing unrelated Skill will not be overwritten: $registrationPath"
        }
    }
}

foreach ($skillEntry in $manifest.skills) {
    if (-not (Test-Path -LiteralPath $skillEntry.registration_directory)) {
        New-Item -ItemType Junction -Path $skillEntry.registration_directory -Target $skillEntry.canonical_directory | Out-Null
    }
    if (-not (Test-Path -LiteralPath (Join-Path $skillEntry.registration_directory 'SKILL.md') -PathType Leaf)) {
        throw "Registration is unreadable: $($skillEntry.name)"
    }
    $skillEntry | Add-Member -NotePropertyName registration_verified -NotePropertyValue $true -Force
}
$manifest.status = 'registered'
$manifest | Add-Member -NotePropertyName registered_at_utc -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 100) + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Registered $($manifest.skill_count) prefixed Skills via Windows directory junctions."
Write-Output "Canonical content: $canonicalRoot"
Write-Output "Codex discovery: $discoveryRoot"
