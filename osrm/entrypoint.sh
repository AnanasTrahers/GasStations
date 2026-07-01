#!/bin/bash
set -e

DATA_DIR="/data"
OSM_FILE="ukraine-latest.osm.pbf"
OSRM_FILE="ukraine-latest.osrm"

cd $DATA_DIR

if [ ! -f "$OSM_FILE" ]; then
    echo "Downloading Ukraine OSM data..."
    apt-get update && apt-get install -y wget
    wget -O "$OSM_FILE" https://download.geofabrik.de/europe/ukraine-latest.osm.pbf
fi

if [ ! -f "$OSRM_FILE" ]; then
    echo "Extracting map data using car profile..."
    osrm-extract -p /opt/car.lua "$OSM_FILE"

    echo "Contracting the graph (CH algorithm)..."
    osrm-contract "$OSRM_FILE"

    echo "OSRM data processing complete."
else
    echo "Processed OSRM data already exists. Skipping pre-processing."
fi