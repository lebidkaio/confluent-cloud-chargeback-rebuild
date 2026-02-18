# Grafana Dashboard Fix

## Issue
The Grafana dashboard was not loading due to incorrect JSON format.

## Changes Made
1. Fixed `costs-overview.json` - removed nested "dashboard" wrapper and added required fields:
   - Added `uid: "confluent-costs-overview"`
   - Updated `schemaVersion: 38` (latest)
   - Added `editable: true`
   - Added proper `time` and `timepicker` configs
   - Changed panels from `graph` type to `timeseries` (modern Grafana)
   - Added datasource references with UID in each panel

2. Fixed `datasources.yml` - added UID to match dashboard references:
   - Added `uid: prometheus`
   - Added `jsonData.timeInterval: "15s"`

## How to Apply the Fix

### Option 1: Restart Grafana Container
```powershell
# Restart just the Grafana container
docker compose -f docker/docker-compose.yml restart grafana

# Wait a few seconds, then check
docker compose -f docker/docker-compose.yml logs grafana
```

### Option 2: Full Stack Restart (Recommended)
```powershell
# Stop the stack
docker compose -f docker/docker-compose.yml down

# Remove Grafana volume to force reload
docker volume rm confluent-billing-portal_grafana_data

# Start fresh
docker compose -f docker/docker-compose.yml up -d

# Check logs
docker compose -f docker/docker-compose.yml logs -f grafana
```

## Verify the Dashboard

1. Open Grafana: http://localhost:3000
2. Login: admin/admin
3. Navigate to: Dashboards → "Confluent Cloud Costs Overview"
4. You should see 5 panels:
   - Total Hourly Cost (USD)
   - Cost by Organization
   - Cost by Cluster
   - Cost by Business Unit (pie chart)
   - Cost by Product (pie chart)

All panels should display data from the mock metrics.
