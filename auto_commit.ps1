$ErrorActionPreference = "Stop"

$repo = "D:\reverse"
$branch = "github-main-sync"
$logDir = Join-Path $repo "logs"
$logFile = Join-Path $logDir "auto_commit.log"

$trackedPaths = @(
    "00_docs",
    "01_scripts",
    "04_artifacts/docker_receiver_3939_dev",
    "README.md"
)

$excludedPatterns = @(
    "^02_captures/",
    "^03_packages/",
    "^logs/",
    "^\\.edge-headless-profile/",
    "^04_artifacts/temp_outputs/",
    "^04_artifacts/web_refs/",
    "__pycache__/",
    "\\.tar$",
    "\\.zip$"
)

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "$ts $Message"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    Add-Content -Path $logFile -Value $line -Encoding UTF8
    Write-Output $line
}

function Is-AllowedPath {
    param([string]$Path)
    foreach ($base in $trackedPaths) {
        if ($Path -eq $base -or $Path.StartsWith("$base/")) {
            foreach ($pattern in $excludedPatterns) {
                if ($Path -match $pattern) {
                    return $false
                }
            }
            return $true
        }
    }
    return $false
}

Set-Location $repo

$currentBranch = (git -C $repo branch --show-current).Trim()
if ($currentBranch -ne $branch) {
    throw "Current branch is '$currentBranch', expected '$branch'."
}

$statusLines = git -C $repo status --porcelain=v1
$allowed = @()
foreach ($line in $statusLines) {
    if (-not $line) {
        continue
    }
    $pathPart = $line.Substring(3)
    if ($pathPart.Contains(" -> ")) {
        $pathPart = $pathPart.Split(" -> ")[-1]
    }
    if (Is-AllowedPath $pathPart) {
        $allowed += $pathPart
    }
}

if ($allowed.Count -eq 0) {
    Write-Log "No allowed changes detected."
    exit 0
}

$uniqueAllowed = $allowed | Sort-Object -Unique
Write-Log ("Staging paths: " + ($uniqueAllowed -join ", "))

foreach ($path in $trackedPaths) {
    git -C $repo add -- $path
}

if ($LASTEXITCODE -ne 0) {
    throw "git add failed."
}

$cached = git -C $repo diff --cached --name-only
$kept = @()
foreach ($path in $cached) {
    if (Is-AllowedPath $path) {
        $kept += $path
    } else {
        git -C $repo reset -q HEAD -- $path
    }
}

if ($kept.Count -eq 0) {
    Write-Log "No staged changes remain after filtering."
    exit 0
}

git -C $repo diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Log "No diff to commit."
    exit 0
}

$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$message = "auto: sync workspace changes ($stamp)"

git -C $repo commit -m $message
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed."
}

git -C $repo push origin $branch
if ($LASTEXITCODE -ne 0) {
    throw "git push failed."
}

Write-Log "Auto commit and push completed."
