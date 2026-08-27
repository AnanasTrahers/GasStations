#!/bin/bash
set -e

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data/osrm"
OSM_FILE="ukraine-latest.osm.pbf"
OSRM_FILE="ukraine-latest.osrm"

OSM_URL="https://download.geofabrik.de/europe/ukraine-latest.osm.pbf"
OSM_PATH="$DATA_DIR/$OSM_FILE"
OSRM_PATH="$DATA_DIR/$OSRM_FILE"

mkdir -p "$DATA_DIR"

if [ ! -f "$OSM_PATH" ]; then
    echo -e "\033[0;36mDownloading Ukraine OSM data...\033[0m"
    curl -L "$OSM_URL" -o "$OSM_PATH"
else
    echo -e "\033[0;32mOSM data already exists locally.\033[0m"
fi

if [ ! -f "$OSRM_PATH" ]; then
    echo -e "\033[0;36mExtracting map data using car profile...\033[0m"
    cd "$PROJECT_ROOT"
    docker run -t --rm -v "${PWD}/data/osrm:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-extract -p /opt/car.lua /data/$OSM_FILE

    echo -e "\033[0;36mContracting the graph (CH algorithm)...\033[0m"
    docker run -t --rm -v "${PWD}/data/osrm:/data" ghcr.io/project-osrm/osrm-backend:v5.27.1 osrm-contract /data/$OSRM_FILE

    echo -e "\033[0;32mOSRM data processing complete.\033[0m"
else
    echo -e "\033[0;33mProcessed OSRM data already exists. Skipping pre-processing.\033[0m"
fi

echo ""
echo "=========================================================================="
echo -e "\033[0;36mTo upload the processed files to your VPS, run the following command:\033[0m"
echo "scp -r ./data/osrm user@your_vps_ip:/path/to/project/data/"
echo "(Make sure to replace 'user@your_vps_ip' and the remote destination path)"
echo "=========================================================================="
