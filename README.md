# ⛽ GasStation Route Optimizer & Fuel Price ETL

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688.svg)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.3-336791.svg)](https://postgis.net/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)

A high-performance backend service built with **FastAPI**, **PostgreSQL/PostGIS**, and **OSRM**. It provides advanced geospatial route optimization to find the most cost-effective gas stations along a driving route or near a location in Ukraine. It also features asynchronous ETL pipeline for scraping, normalizing, and ingesting fuel prices and station locations.

## ✨ Core Features

* **🗺️ Geospatial Route Optimization Engine**:
  * Integrates **Mapbox Directions API** and **OSRM (Open Source Routing Machine)** for lightning-fast distance matrix calculations.
  * Computes forward (start → stations) and backward (stations → end) matrices to determine the true travel overhead.
  * Employs spatial querying (`WKTElement`, SRID 4326) and utilizes Redis to cache available fuel types for rapid lookups without caching volatile route data.
* **🔄 Asynchronous Fuel-Price ETL Pipeline**:
  * Utilizes `arq` (Redis-based async queue) for scheduled background tasks.
  * Scrapes Ukrainian fuel-price platforms (`vseazs`, `minfin`) using dynamic thread-pool executors to prevent event-loop blocking.
  * Normalizes complex fuel networks into a canonical registry and performs spatial bulk-upserts (50m proximity matching).
  * Imports raw gas station locations directly from **OpenStreetMap** (Overpass API).

* **🏗️ Robust Software Architecture**:
  * Clean, domain-driven structure with dedicated Service, Repository, and Controller (Router) layers.
  * Full dependency injection (DB sessions, HTTP clients, Redis).
  * Structured JSON logging via `structlog` with request-scoped tracing.

## 🛠️ Technology Stack

| Category | Technologies |
| :--- | :--- |
| **Language & Core** | Python 3.13, FastAPI, Pydantic |
| **Database & Spatial** | PostgreSQL, PostGIS, SQLAlchemy (async), GeoAlchemy2, Alembic |
| **Caching & Queues** | Redis, `arq` (async job queues) |
| **Routing & Mapping** | Mapbox API, OSRM, Shapely |
| **Package Management**| `uv` (lightning-fast package installer) |
| **Infrastructure** | Docker, Docker Compose, GitHub Actions |

## 🏗️ Local Development Setup

### Prerequisites
- [Docker](https://www.docker.com/) and Docker Compose
- [uv](https://docs.astral.sh/uv/)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd GasStations
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your Mapbox API key
   ```

3. **Install Dependencies:**
   ```bash
   uv sync
   ```

4. **Process OSRM Data (First Time Only):**
   Run the preprocessor script to build the OSRM map data.
   * On **Windows (PowerShell)**:
     ```powershell
     .\.infra\osrm\preprocess_local.ps1
     ```
   * On **macOS / Linux**:
     ```bash
     chmod +x .infra/osrm/preprocess_local.sh
     ./.infra/osrm/preprocess_local.sh
     ```

5. **Boot Infrastructure:**
   Starts PostGIS, Redis, OSRM, the background worker, and the API server.
   ```bash
   docker compose up --build
   ```

6. **Run Database Migrations:**
   ```bash
   alembic upgrade head
   ```

## 🔄 Running the ETL Worker

The `arq` worker handles scheduled jobs for scraping fuel prices and updating OpenStreetMap data.

**Trigger jobs manually (CLI):**
If you need to run the jobs outside their scheduled cron times, you can trigger them manually:

```bash
# 1. Run the fuel prices ETL
uv run python -m src.worker.trigger fuel_prices_etl --now

# 2. Run the gas stations import from OSM
uv run python -m src.worker.trigger gas_stations_import --now
```

## 📱 Mobile Application

You can download the compiled Android application (`.apk`) from the **[Releases](https://github.com/Ananases/GasStations/releases)** section of this repository.

## 🧠 Architecture Highlights

* **Spatial Database Design**: All spatial entities reside in the `app` schema utilizing `GEOGRAPHY Point(4326)` for precise spherical distance calculations.
* **Idempotent Data Ingestion**: The data access layer (`dal.py`) leverages PostgreSQL's `ON CONFLICT DO NOTHING` and spatial similarity constraints to ensure idempotent bulk upserts.
* **Resilience & Rate Limiting**: Scrapers utilize `tenacity` for exponential backoff and semaphores to respect target rate limits.
