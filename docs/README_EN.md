# Confluent Billing Portal — Complete Documentation

> Chargeback/Showback platform for Confluent Cloud with Grafana dashboards, automated cost collection, and REST API.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Setup & Running](#setup--running)
5. [Environment Variables](#environment-variables)
6. [Project Structure](#project-structure)
7. [REST API](#rest-api)
8. [Data Collection](#data-collection)
9. [Grafana Dashboards](#grafana-dashboards)
10. [Useful Commands](#useful-commands)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The **Confluent Billing Portal** is a solution for monitoring, analyzing, and allocating Confluent Cloud costs. The platform:

- **Automatically collects** billing data from the Confluent Cloud REST API
- **Normalizes and enriches** data with organizational dimensions (org, env, cluster)
- **Stores historically** in PostgreSQL for long-term queries (30+ days)
- **Exports metrics** to Prometheus for real-time alerting
- **Visualizes** everything across 6 Grafana dashboards using SQL queries for historical data

### Technology Stack

| Component | Technology |
|---|---|
| Backend/API | Python 3.11 + FastAPI |
| Database | PostgreSQL 15 |
| Metrics | Prometheus |
| Dashboards | Grafana |
| Containerization | Docker + Docker Compose |
| Dependency Mgmt | Poetry |

### Data Flow

1. **Collector** fetches cost data from the Confluent Cloud billing REST API
2. **Enricher** normalizes raw API responses, distributes daily costs into hourly records, and maps `resource_id` to `cluster_id`
3. **Storage** persists data into PostgreSQL in `hourly_cost_facts` and dimension tables
4. **Exporter** reads the last 30 days from the database and exposes a Prometheus Gauge (`ccloud_cost_usd_hourly`)
5. **Grafana** queries **PostgreSQL directly** via SQL for historical dashboards, and Prometheus for real-time alerts

---

## Prerequisites

| Software | Minimum Version |
|---|---|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Git | 2.30+ |

> **Note:** Python and Poetry are only required for local development without Docker.

---

## Setup & Running

### Step 1 — Clone the repository

```bash
git clone <repository-url>
cd confluent-billing-portal
```

### Step 2 — Configure environment variables

```bash
# Copy the example file
cp .env.example docker/.env

# Edit with your Confluent API credentials
notepad docker/.env     # Windows
nano docker/.env        # Linux/Mac
```

**Required fields for data collection:**

```env
CONFLUENT_API_KEY=your_api_key_here
CONFLUENT_API_SECRET=your_api_secret_here
```

### Step 3 — Start the application

```bash
# Using Makefile
make docker-up

# Or directly
docker compose -f docker/docker-compose.yml up -d
```

### Step 4 — Verify everything is running

```bash
docker ps --filter "name=billing" --format "table {{.Names}}\t{{.Status}}"
```

Expected output:

```
NAMES                STATUS
billing-grafana      Up X minutes (healthy)
billing-prometheus   Up X minutes (healthy)
billing-app          Up X minutes (healthy)
billing-postgres     Up X minutes (healthy)
```

### Step 5 — Access the services

| Service | URL | Credentials |
|---|---|---|
| **Grafana** (Dashboards) | http://localhost:3000 | admin / admin |
| **REST API** (Swagger) | http://localhost:8000/docs | — |
| **Prometheus** | http://localhost:9090 | — |
| **PostgreSQL** | localhost:5432 | billing_user / billing_password |

### Step 6 — Collect data (first time)

Data collection can be triggered manually via the API:

```bash
# Collect costs for the current month
curl -X POST http://localhost:8000/api/v1/costs/collect

# Check data in the database
curl http://localhost:8000/api/v1/costs/summary
```

### Step 7 — View Dashboards

1. Open http://localhost:3000
2. Log in with `admin` / `admin`
3. Navigate to **Dashboards** in the side menu
4. All 6 dashboards will be available automatically

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `CONFLUENT_API_KEY` | Confluent Cloud API Key | — |
| `CONFLUENT_API_SECRET` | Confluent Cloud API Secret | — |
| `CONFLUENT_CLOUD_URL` | Base API URL | `https://api.confluent.cloud` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://billing_user:billing_password@postgres:5432/billing_db` |
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `ENVIRONMENT` | Environment (development, production) | `development` |
| `SCHEDULER_ENABLED` | Enable task scheduler | `false` |
| `HOURLY_JOB_ENABLED` | Enable hourly collection job | `false` |
| `DAILY_JOB_ENABLED` | Enable daily collection job | `false` |
| `API_HOST` | Server host | `0.0.0.0` |
| `API_PORT` | Server port | `8000` |

---

## Project Structure

```
confluent-billing-portal/
├── docker/
│   ├── Dockerfile                  # Multi-stage Python 3.11 build
│   ├── docker-compose.yml          # Full stack (4 services)
│   └── docker-compose.prod.yml     # Production configuration
│
├── src/
│   ├── main.py                     # FastAPI entrypoint
│   ├── api/                        # REST endpoints
│   │   ├── costs.py                #   /api/v1/costs/*
│   │   ├── dimensions.py           #   /api/v1/dimensions/*
│   │   └── health.py               #   /healthz
│   ├── collector/                  # Confluent API integration
│   │   ├── client.py               #   HTTP client for billing API
│   │   └── service.py              #   Orchestration logic
│   ├── enricher/                   # Normalization & enrichment
│   │   └── normalizer.py           #   Raw data transformation
│   ├── exporter/                   # Prometheus export
│   │   └── metrics.py              #   Gauge ccloud_cost_usd_hourly
│   ├── jobs/                       # Task scheduling
│   │   └── scheduler.py            #   APScheduler (cron)
│   ├── storage/                    # Persistence layer
│   │   ├── database.py             #   SQLAlchemy engine
│   │   ├── models.py               #   ORM models
│   │   └── repository.py           #   Data access layer
│   └── common/                     # Utilities
│       ├── config.py               #   Pydantic settings
│       └── logging.py              #   Structured logging
│
├── grafana/
│   ├── dashboards/                 # 6 JSON dashboards (provisioned)
│   └── provisioning/
│       ├── datasources/            # PostgreSQL + Prometheus config
│       └── dashboards/             # Provisioning configuration
│
├── config/
│   └── prometheus.yml              # Prometheus scrape config
│
├── migrations/
│   └── versions/                   # Schema creation SQL
│
├── tests/                          # Unit and integration tests
├── docs/                           # This documentation
├── Makefile                        # Development shortcuts
└── pyproject.toml                  # Python dependencies (Poetry)
```

---

## REST API

The API exposes the following endpoints (interactive documentation at `/docs`):

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service information |
| `GET` | `/healthz` | Health check |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/api/v1/costs/summary` | Cost summary |
| `POST` | `/api/v1/costs/collect` | Trigger manual collection |
| `GET` | `/api/v1/dimensions/orgs` | List organizations |
| `GET` | `/api/v1/dimensions/envs` | List environments |
| `GET` | `/api/v1/dimensions/clusters` | List clusters |

---

## Data Collection

### Automated Process

When enabled (`SCHEDULER_ENABLED=true`), the scheduler runs:

- **Hourly collection**: Fetches incremental costs every hour
- **Daily collection**: Full reconciliation of the previous day

### Data Model

The core table is `hourly_cost_facts`:

| Column | Type | Description |
|---|---|---|
| `timestamp` | `TIMESTAMP` | Record date/time |
| `org_id` | `VARCHAR` | Confluent organization ID |
| `env_id` | `VARCHAR` | Environment ID (e.g., `env-abc123`) |
| `cluster_id` | `VARCHAR` | Resource ID (e.g., `lkc-abc123`) |
| `product` | `VARCHAR` | Product (KAFKA, CONNECT, FLINK, etc.) |
| `cost_usd` | `DECIMAL` | Cost in USD (negative = credits) |
| `business_unit` | `VARCHAR` | Business unit |
| `cost_center` | `VARCHAR` | Cost center |
| `allocation_confidence` | `ENUM` | Allocation confidence (high, medium, low) |
| `allocation_method` | `VARCHAR` | Allocation method used |

### Dimension Tables

| Table | Purpose |
|---|---|
| `dimensions_orgs` | Organizations with names and metadata |
| `dimensions_envs` | Environments with `display_name` (e.g., "Production", "DEV") |
| `dimensions_clusters` | Clusters with type, region, cloud provider |

---

## Grafana Dashboards

All dashboards use **direct PostgreSQL SQL queries** for 30+ day historical coverage. The default time range is `now-30d` to `now`.

### 1. C-Level — Confluent Cloud Cost

**File:** `clevel-cost-overview.json`
**Audience:** Executives, management, decision-makers

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| Total Spend | Stat | Sum of all positive costs in the period |
| Total Credits | Stat | Total credits/discounts applied |
| Net Cost | Stat | Net cost (spend - credits) |
| Daily Cost Trend | Time Series | Daily cost timeline with trend |
| Cost by Environment | Pie Chart | Cost distribution by environment (Production, DEV, etc.) |
| Top 10 Clusters | Bar Gauge | Top 10 highest-cost clusters |
| Cost by Product | Bar Gauge | Costs by product (Kafka, Connect, Flink, Schema Registry) |
| Organization Overview | Table | Summary per org with total, clusters, active days |

**Key insights:**
- How much are we spending on Confluent Cloud in total?
- Which environment consumes the most resources?
- Which clusters are the most expensive?
- How do costs trend day-over-day?

---

### 2. Confluent Cloud Chargeback

**File:** `ccloud_chargeback.json`
**Audience:** FinOps, cost managers, infrastructure teams

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| Data Coverage | Time Series | Record count per day (coverage validation) |
| Overall Cost Breakdown | Stat | Total Cost, Usage Cost, and Credits as separate cards |
| Cost per Environment | Pie Chart | Cost distribution with human-readable environment names |
| Cost per Kafka Cluster | Pie Chart | Kafka cluster costs (filtered by `lkc-*`) |
| Cost per Product Group | Pie Chart | Distribution by product |
| Cost per Resource Type | Pie Chart | Resource classification (Kafka, Connector, Flink, Schema Registry) |
| Cost by Cluster | Bar Gauge | Top 15 clusters ranked horizontally with gradient |
| Environment Details | Row (collapsible) | Expandable stat breakdown per environment |
| Kafka Cluster Details | Row (collapsible) | Expandable stat breakdown per Kafka cluster |
| Resource Details | Row (collapsible) | Expandable stat breakdown per resource |
| Product Details | Row (collapsible) | Expandable stat breakdown per product |
| Chargeback Detail Table | Row (collapsible) | Full table with Environment, Resource, Product, Total Cost, Avg Hourly, Days Active, and Share % |

**Key insights:**
- How should costs be allocated across teams/environments?
- What percentage of total cost does each cluster represent?
- Which resources are active and for how many days?
- What is the average hourly cost per resource?

---

### 3. Cost by Business Unit

**File:** `cost-by-business-unit.json`
**Audience:** Business managers, controllers

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| Cost by Product | Pie Chart | Cost distribution across products |
| Cost by Environment | Pie Chart | Cost distribution across environments |
| Summary Statistics | Stat | Total Spend, Active Clusters, Active Environments, Average Daily Cost |
| Daily Cost by Product | Time Series | Stacked daily trend by product |
| Product × Environment Matrix | Table | Cross-tab showing average daily costs for each product in each environment |

**Key insights:**
- Which product consumes the most budget?
- How do costs split between production and non-production?
- Are cost trends increasing or stabilizing?
- Which environment has the most product diversity?

---

### 4. Cost by Cluster

**File:** `cost-by-cluster.json`
**Audience:** Platform engineers, SREs, DevOps

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| Total Cluster Cost | Stat | Sum of all cluster costs |
| Active Clusters | Stat | Count of distinct clusters |
| Avg Daily Cost | Stat | Average daily cost per cluster |
| Active Environments | Stat | Number of environments with clusters |
| Daily Cost by Cluster | Time Series | Stacked time trend by cluster |
| Cluster Ranking Table | Table | Cluster ranking with Environment, Product, Total Cost, Avg Daily, Days Active |
| Cost by Product | Pie Chart | Cluster cost distribution by product |
| Environment × Cluster Matrix | Table | Cross-tab: Kafka, Connectors, Flink, Schema Registry costs per environment |

**Key insights:**
- Which clusters represent the highest costs?
- Are there idle or underutilized clusters?
- How do costs distribute across resource types per environment?
- Which environment has the most cluster diversity?

---

### 5. Historical Costs (SQL)

**File:** `historical_costs.json`
**Audience:** Financial analysts, data engineers, audit teams

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| 30-Day Cost Trend by Product | Time Series | Stacked timeline of costs by product |
| Product Cost Summary | Bar Gauge | Total costs per product in horizontal bars |
| Organization Overview | Table | Summary per org: Total Spend, Credits, Net Cost, Active Clusters, Active Envs |
| Environment Health | Table | Costs per environment with breakdown: Kafka, Connectors, Flink, Schema Registry |
| Cost Optimization Insights | Table | **Advanced CTE analysis**: identifies inactive, high-variance, and high-cost clusters |
| Credits & Discounts Tracking | Time Series | Credit and discount evolution over time |
| Daily Audit Table | Table | Daily table with date, product, records, total cost, avg hourly, min/max cost for audit |

**Key insights:**
- How have costs evolved over the last 30 days?
- Are there clusters with anomalous costs (high variance)?
- Which clusters are inactive but still generating costs?
- How were credits/discounts applied over time?
- Granular data for financial auditing

---

### 6. Confidence Metrics

**File:** `confidence-metrics.json`
**Audience:** Data engineers, FinOps team, data quality

**Available views:**

| Panel | Type | What it shows |
|---|---|---|
| Allocation Confidence Distribution | Pie Chart (donut) | Percentage distribution of records by confidence level (High, Medium, Low) |
| Cost by Confidence Level | Bar Gauge | Costs associated with each confidence level |
| Data Quality Score | Stat | Percentage of records with High or Medium confidence (quality indicator) |
| Total Records | Stat | Total record count in the period |
| Confidence over Time | Time Series (stacked bars) | Daily evolution of confidence distribution |
| Allocation Method Breakdown | Table | Breakdown by allocation method: records, clusters, tracked cost, share % |
| Confidence by Environment | Table | Confidence quality per environment with High/Medium/Low breakdown and Quality % |

**Key insights:**
- What is the overall quality of cost allocation?
- Are there environments with low allocation confidence?
- How does allocation quality evolve over time?
- Which allocation methods are most commonly used?

---

## Useful Commands

### Makefile

```bash
make help             # List all available commands
make docker-up        # Start the full stack
make docker-down      # Tear down the full stack
make docker-logs      # View real-time logs
make docker-rebuild   # Rebuild and restart
make install          # Install dependencies (local dev)
make dev              # Run local development server
make test             # Run tests
make lint             # Check code quality
make format           # Format code
make migrate          # Run database migrations
```

### Docker

```bash
# Check container status
docker ps --filter "name=billing"

# Restart a specific container
docker restart billing-grafana

# View container logs
docker logs billing-app --tail 50 -f

# Access PostgreSQL via CLI
docker exec -it billing-postgres psql -U billing_user -d billing_db

# Query data directly
docker exec -it billing-postgres psql -U billing_user -d billing_db -c \
  "SELECT product, ROUND(SUM(cost_usd)::numeric, 2) FROM hourly_cost_facts GROUP BY 1 ORDER BY 2 DESC;"
```

---

## Troubleshooting

### Empty dashboards

1. **Check the time range** — default is 30 days. If data is older, adjust the range in the top-right corner of Grafana
2. **Verify data exists** — run: `curl http://localhost:8000/api/v1/costs/summary`
3. **Verify the PostgreSQL datasource** — in Grafana → Configuration → Data Sources → PostgreSQL → Test

### Containers won't start

```bash
# Check error logs
docker compose -f docker/docker-compose.yml logs --tail 20

# Force rebuild
docker compose -f docker/docker-compose.yml up -d --build --force-recreate
```

### Data collection not working

1. Verify `CONFLUENT_API_KEY` and `CONFLUENT_API_SECRET` are correct in `docker/.env`
2. Test connectivity: `curl -u "KEY:SECRET" https://api.confluent.cloud/billing/v1/costs`
3. Check app logs: `docker logs billing-app --tail 50`

### Grafana lost login/dashboards

If Grafana's internal database gets corrupted:

```bash
# Clean and recreate Grafana DB
docker exec billing-grafana sh -c "rm -f /var/lib/grafana/grafana.db"
docker restart billing-grafana
# Default login: admin / admin
```
