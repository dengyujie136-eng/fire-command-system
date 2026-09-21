param(
    [Parameter(Mandatory = $true)]
    [string]$SeedPath,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$DbName = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'xinghuo' }),
    [string]$DbUser = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'xinghuo' })
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path $RepoRoot)
$resolvedSeed = (Resolve-Path $SeedPath).Path

Write-Host '[1/4] Starting PostGIS and the fire-agent API'
docker compose up -d --no-build --no-deps fire-agent-api
if ($LASTEXITCODE -ne 0) { throw 'Docker services failed to start.' }

Write-Host '[2/4] Waiting for the backend schema initialization'
docker compose exec -T postgis pg_isready -U $DbUser -d $DbName
if ($LASTEXITCODE -ne 0) { throw 'PostGIS is not ready.' }

Write-Host '[3/4] Replacing only member A realtime observation data'
@"
BEGIN;
DELETE FROM public.realtime_hotspots;
DELETE FROM public.realtime_observations;
COMMIT;
"@ | docker compose exec -T postgis psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f -
if ($LASTEXITCODE -ne 0) { throw 'Realtime table cleanup failed.' }

Get-Content -LiteralPath $resolvedSeed -Raw -Encoding UTF8 |
    docker compose exec -T postgis psql -U $DbUser -d $DbName -v ON_ERROR_STOP=1 -f -
if ($LASTEXITCODE -ne 0) { throw 'Realtime database seed restore failed.' }

Write-Host '[4/4] Verifying restored realtime rows'
$sql = @"
SELECT json_build_object(
  'realtime_observations', (SELECT count(*) FROM public.realtime_observations),
  'realtime_hotspots', (SELECT count(*) FROM public.realtime_hotspots)
);
"@
docker compose exec -T postgis psql -U $DbUser -d $DbName -At -c $sql
if ($LASTEXITCODE -ne 0) { throw 'Realtime database verification failed.' }

Write-Host 'Member A realtime data restore completed.'
