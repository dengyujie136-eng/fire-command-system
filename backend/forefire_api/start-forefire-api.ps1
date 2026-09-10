$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root

docker compose --project-name xinghuo -f docker-compose.forefire.yml up --build forefire-api
