[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$ApiBaseUrl = 'http://localhost:8200'
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$candidateManifest = Join-Path $repo 'data\manifests\dixie_fire_2021_visual_candidates.json'
$sentinelImages = @('pre', 'during', 'post') | ForEach-Object {
    Join-Path $repo "data\raw\sentinel2\dixie_fire_2021\gee\dixie_fire_2021_s2_10m_${_}_r01c01.tif"
}

if (-not (Test-Path -LiteralPath $candidateManifest -PathType Leaf)) {
    throw "Candidate manifest not found: $candidateManifest"
}
foreach ($sentinelImage in $sentinelImages) {
    if (-not (Test-Path -LiteralPath $sentinelImage -PathType Leaf)) {
        throw "Sentinel image not found: $sentinelImage"
    }
}

try {
    Invoke-RestMethod -Uri "$ApiBaseUrl/health" -TimeoutSec 10 | Out-Null
} catch {
    throw "Visual backend is unavailable at $ApiBaseUrl. Run docker compose up -d --build first."
}

$headers = @{'Content-Type' = 'application/json'}
$candidateJson = Get-Content -LiteralPath $candidateManifest -Raw -Encoding UTF8
$ingest = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/visual-verification/candidates/import" `
    -Headers $headers `
    -Body $candidateJson `
    -TimeoutSec 60

$pipelineBody = @{
    selection = @{
        start_at = '2021-07-14T09:11:00Z'
        end_at = '2021-07-14T09:11:00Z'
        time_window_minutes = 10
        spatial_radius_km = 2.0
        minimum_cluster_points = 2
        max_results = 1
        candidate_limit = 100
        require_imagery = $true
    }
    crop_radius_m = 1500.0
    band_indexes = @(3, 2, 1)
    detector_image_size = 640
} | ConvertTo-Json -Depth 6

$result = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/api/visual-verification/events/dixie_fire_2021/auto-confirm-fire-points" `
    -Headers $headers `
    -Body $pipelineBody `
    -TimeoutSec 600

$resultDirectory = Join-Path $repo 'data\local\results'
New-Item -ItemType Directory -Path $resultDirectory -Force | Out-Null
$resultPath = Join-Path $resultDirectory 'dixie_fire_2021_visual_confirmation_latest.json'
$result | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $resultPath -Encoding UTF8

if (@($result.confirmed_fire_points).Count -lt 1) {
    throw "Visual pipeline completed without a confirmed fire point. Inspect $resultPath"
}

$point = $result.confirmed_fire_points[0]
Write-Host "Candidate records imported: $(@($ingest.items).Count)"
Write-Host "Confirmed fire point: $($point.ignition_point.coordinates -join ', ')"
Write-Host "Confirmation method: $($point.confirmation_method)"
Write-Host "Full result: $resultPath"
