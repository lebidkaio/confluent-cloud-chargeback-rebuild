# Setup Real Data Collection / Configuracao para Coleta de Dados Reais

This guide shows how to set up the portal to collect real billing data from Confluent Cloud.

Este guia mostra como configurar o portal para coletar dados reais do Confluent Cloud.

---

## Prerequisites / Pre-requisitos

1. Active Confluent Cloud account / Conta ativa no Confluent Cloud
2. Administrator permissions (to create API keys) / Permissoes de administrador
3. Docker & Docker Compose installed / Docker & Docker Compose instalados

---

## Step 1: Create API Key in Confluent Cloud

### 1.1 Access Confluent Cloud

```
https://confluent.cloud
```

### 1.2 Create a Cloud API Key

1. Go to **Administration** → **Cloud API keys**
2. Click **Add key**
3. Select the following permissions:
   - `BillingAdmin` — Access billing data
   - `OrganizationAdmin` — Access organization/environment/cluster metadata
   - `MetricsViewer` — Access usage metrics
4. Click **Create**
5. **IMPORTANT**: Copy the **API Key** and **API Secret** immediately
   - The secret is only displayed once

---

## Step 2: Configure the Portal

### 2.1 Create the `.env` file

```bash
cd confluent-billing-portal
cp .env.example docker/.env
```

### 2.2 Edit `docker/.env` with your credentials

```env
# Database (pre-configured)
DATABASE_URL=postgresql://billing_user:billing_password@postgres:5432/billing_db

# Confluent Cloud API (paste your credentials here)
CONFLUENT_API_KEY=YOUR_API_KEY_HERE
CONFLUENT_API_SECRET=YOUR_API_SECRET_HERE
CONFLUENT_CLOUD_URL=https://api.confluent.cloud

# Enable Scheduler
SCHEDULER_ENABLED=true
HOURLY_JOB_ENABLED=true
DAILY_JOB_ENABLED=true

# Service metadata
SERVICE_NAME=confluent-billing-portal
SERVICE_VERSION=0.1.0
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## Step 3: Start the Portal

### 3.1 Start the Docker Stack

```bash
cd docker
docker compose up -d
```

### 3.2 Verify services are running

```bash
docker compose ps
```

Expected output:

```
NAME                    STATUS
billing-app             Up (healthy)
billing-postgres        Up (healthy)
billing-prometheus      Up (healthy)
billing-grafana         Up (healthy)
```

### 3.3 View scheduler logs

```bash
docker compose logs -f app
```

You should see messages like:

```
INFO - Scheduler initialized
INFO - Hourly job scheduled
INFO - Daily job scheduled
```

---

## Step 4: Collect Data (First Time)

### Option A: Wait for the Scheduler (Automatic)

The scheduler will automatically run:
- **Hourly Job**: Every hour (collects core objects)
- **Daily Job**: At 00:00 UTC (collects billing data)

### Option B: Manual Trigger (Immediate) — Recommended

Use the manual collection script:

```bash
# Inside the container
docker exec -it billing-app python scripts/trigger_collection.py --all
```

Or locally:

```bash
# Install dependencies
poetry install

# Collect everything (core objects + billing for the last 7 days)
poetry run python scripts/trigger_collection.py --all

# Or separately:
poetry run python scripts/trigger_collection.py --core-objects
poetry run python scripts/trigger_collection.py --billing --days 30
```

Expected output:

```
Collecting core objects...
Core objects collected successfully
Collecting billing data for last 7 days...
Billing data collected successfully (2024-02-04 to 2024-02-11)

Data collection complete!
```

---

## Step 5: Verify Data

### 5.1 Verify via API

```bash
# Check that costs have been collected
curl "http://localhost:8000/v1/costs?from_ts=2024-02-01T00:00:00Z&to_ts=2024-02-11T23:59:59Z&limit=10"

# Verify dimensions
curl "http://localhost:8000/v1/dimensions/clusters"
curl "http://localhost:8000/v1/dimensions/organizations"
```

### 5.2 Verify via Prometheus

```bash
# Open Prometheus: http://localhost:9090
# Execute query:
sum(ccloud_cost_usd_hourly)
```

### 5.3 Verify via Grafana

```
# Open Grafana: http://localhost:3000
# Login: admin / admin

1. Go to "Dashboards"
2. Open "Cost by Cluster"
3. Verify that data appears in the charts
```

---

## Troubleshooting

### Problem: "401 Unauthorized"

**Cause**: Incorrect API credentials

**Solution**:
1. Verify that the API Key and Secret were copied correctly
2. Verify that the API Key has the correct permissions
3. Test credentials directly:
   ```bash
   curl -u "API_KEY:API_SECRET" \
     https://api.confluent.cloud/billing/v1/costs
   ```

---

### Problem: "No data in Prometheus"

**Cause**: Data has not been collected or processed yet

**Solution**:
1. Check scheduler logs:
   ```bash
   docker compose logs app | grep -i "job"
   ```
2. Trigger manual collection:
   ```bash
   docker exec -it billing-app python scripts/trigger_collection.py --all
   ```
3. Wait a few minutes for processing

---

### Problem: "Empty response from API"

**Cause**: No billing data exists for the queried period

**Solution**:
1. Verify that your cluster has activity in the period
2. Try a longer period (last 30 days):
   ```bash
   poetry run python scripts/trigger_collection.py --billing --days 30
   ```

---

## Collection Schedule

After setup, automatic collection works as follows:

| Job | Frequency | What it collects | When |
|-----|-----------|------------------|------|
| **Hourly** | Every hour | Core objects (orgs, envs, clusters, principals) | :00 of each hour |
| **Daily** | Daily | Billing data (previous day costs) | 00:00 UTC |

---

## Next Steps

After collecting real data:

1. **Create allocation rules**
   - Edit `src/enricher/allocation_rules.py`
   - Add rules based on your tags/principals

2. **Configure alerts**
   - Edit `prometheus/alerts/portal-alerts.yml`
   - Adjust thresholds for your environment

3. **Customize dashboards**
   - Grafana allows editing dashboards via the UI
   - Save them for future versions

---

## Support

- **App logs**: `docker compose logs -f app`
- **Scheduler status**: Check logs for `APScheduler`
- **Database**: Connect to `localhost:5432` with `billing_user/billing_password`

**Official documentation:**
- [Confluent Cloud API](https://docs.confluent.io/cloud/current/api.html)
- [Billing API](https://docs.confluent.io/cloud/current/billing/overview.html)
