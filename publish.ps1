param(
  [Parameter(Mandatory=$true)][string]$User,
  [Parameter(Mandatory=$true)][string]$Repo,
  [switch]$UseSSH
)

$ErrorActionPreference = "Stop"

Write-Host "Publishing GXOST X6 to GitHub" -ForegroundColor Cyan
$cwd = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $cwd

if (-not (Test-Path ".git")) {
  git init
}

git add -A
try {
  git commit -m "GXOST X6 initial release"
} catch {
  Write-Host "Commit skipped (no changes or already committed)" -ForegroundColor Yellow
}

git branch -M main

if ($UseSSH) {
  $remote = "git@github.com:$User/$Repo.git"
} else {
  $remote = "https://github.com/$User/$Repo.git"
}

if ((git remote) -notcontains "origin") {
  git remote add origin $remote
} else {
  git remote set-url origin $remote
}

Write-Host "Remote set to: $remote" -ForegroundColor Green
Write-Host "Attempting to push..." -ForegroundColor Yellow
git push -u origin main

Write-Host "Done. If you saw 'repository not found', create the repo on GitHub and re-run." -ForegroundColor Cyan
