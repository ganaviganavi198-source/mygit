# demo.ps1: a short tour of mygit. Run it with:  .\demo.ps1
$mygitPath = Join-Path $PSScriptRoot "mygit.py"
function mygit { python $mygitPath @args }

$demo = Join-Path $env:TEMP "mygit-demo"
if (Test-Path $demo) { Remove-Item $demo -Recurse -Force }
New-Item -ItemType Directory $demo | Out-Null
Set-Location $demo

Write-Host "`n== 1. Create a repository and first commit ==" -ForegroundColor Cyan
mygit init
"hello" | Out-File hello.txt -Encoding utf8
mygit add hello.txt
mygit commit -m "first commit"

Write-Host "`n== 2. Branch, change, and fast-forward merge ==" -ForegroundColor Cyan
mygit branch feature
mygit checkout feature
"feature work" | Out-File feature.txt -Encoding utf8
mygit add feature.txt
mygit commit -m "add feature"
mygit checkout main
mygit merge feature

Write-Host "`n== 3. Tag, history, and integrity check ==" -ForegroundColor Cyan
mygit tag -a v1.0 -m "first release"
mygit reflog
mygit fsck

Set-Location $PSScriptRoot
Write-Host "`nDemo finished." -ForegroundColor Green