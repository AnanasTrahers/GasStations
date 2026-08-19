$ErrorActionPreference = "Stop"

# Get the project root directory
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$DataDir = Join-Path $ProjectRoot "data\osrm"
$OsmFile = "ukraine-latest.osm.pbf"
$OsrmFile = "ukraine-latest.osrm"

$OsmUrl = "https://download.geofabrik.de/europe/ukraine-latest.osm.pbf"
$OsmPath = Join-Path $DataDir $OsmFile
$OsrmPath = Join-Path $DataDir $OsrmFile

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

if (-not (Test-Path $OsmPath)) {
    Write-Host "Downloading Ukraine OSM data..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $OsmUrl -OutFile $OsmPath
} else {
    Write-Host "OSM data already exists locally." -ForegroundColor Green
}

if (-not (Test-Path $OsrmPath)) {
    Write-Host "Extracting map data using car profile..." -ForegroundColor Cyan
    Set-Location $ProjectRoot
    docker run -t --rm -v "${PWD}/data/osrm:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/car.lua /data/$OsmFile

    Write-Host "Contracting the graph (CH algorithm)..." -ForegroundColor Cyan
    docker run -t --rm -v "${PWD}/data/osrm:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-contract /data/$OsrmFile

    Write-Host "OSRM data processing complete." -ForegroundColor Green
} else {
    Write-Host "Processed OSRM data already exists. Skipping pre-processing." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=========================================================================="
Write-Host "To upload the processed files to your VPS, run the following command:" -ForegroundColor Cyan
Write-Host "scp -r ./data/osrm user@your_vps_ip:/path/to/project/data/"
Write-Host "(Make sure to replace 'user@your_vps_ip' and the remote destination path)"
Write-Host "=========================================================================="
