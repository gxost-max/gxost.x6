$ErrorActionPreference = "Stop"

Write-Host "GXOST X6 installer (user level)" -ForegroundColor Cyan

$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $env:LocalAppData "Programs\GxostX6"

Write-Host "Target: $target" -ForegroundColor Yellow
New-Item -ItemType Directory -Path $target -Force | Out-Null

Copy-Item (Join-Path $source "gxost.py") $target -Force
Copy-Item (Join-Path $source "gxost.x6.py") $target -Force
Copy-Item (Join-Path $source "gxost.cmd") $target -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $source "README.md") $target -Force -ErrorAction SilentlyContinue

$current = [Environment]::GetEnvironmentVariable("Path","User")
if ($null -eq $current) { $current = "" }

if ($current -notlike "*$target*") {
  $newPath = ($current.TrimEnd(";") + ";" + $target)
  [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
  Write-Host "Added to PATH (User): $target" -ForegroundColor Green
} else {
  Write-Host "PATH already contains: $target" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done. Open a new PowerShell and run:" -ForegroundColor Cyan
Write-Host "  python gxost.x6.py --help" -ForegroundColor Cyan
Write-Host "or just:" -ForegroundColor Cyan
Write-Host "  gxost.cmd" -ForegroundColor Cyan
