$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

& $PSScriptRoot\setup-dev.ps1
docker compose --env-file .env -f license-issuer\compose.yaml up -d --build
docker compose up -d --build --remove-orphans

Write-Host "Emisor: http://localhost:8001/"
Write-Host "CRM:    http://localhost/"
