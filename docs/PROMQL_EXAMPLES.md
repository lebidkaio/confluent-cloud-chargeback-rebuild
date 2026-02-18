# PromQL Query Examples for Confluent Billing Portal

This document provides a curated set of PromQL queries for analyzing Confluent Cloud costs.

## Table of Contents
- [Basic Queries](#basic-queries)
- [Cost by Dimension](#cost-by-dimension)
- [Aggregations](#aggregations)
- [Alerting Queries](#alerting-queries)
- [Recording Rules](#recording-rules)

---

## Basic Queries

### Total hourly cost across all resources
```promql
sum(ccloud_cost_usd_hourly)
```

### Cost rate (per hour)
```promql
sum(rate(ccloud_cost_usd_hourly[1h]))
```

### Daily cost estimate
```promql
sum(rate(ccloud_cost_usd_hourly[24h]) * 24)
```

### Monthly cost projection
```promql
sum(rate(ccloud_cost_usd_hourly[7d]) * 24 * 30)
```

---

## Cost by Dimension

### Cost by cluster
```promql
sum by (cluster_id) (rate(ccloud_cost_usd_hourly[1h]))
```

### Cost by organization
```promql
sum by (org_id) (rate(ccloud_cost_usd_hourly[1h]))
```

### Cost by environment
```promql
sum by (env_id) (rate(ccloud_cost_usd_hourly[1h]))
```

### Cost by principal (service account/user)
```promql
sum by (principal_id) (rate(ccloud_cost_usd_hourly{principal_id!=""}[1h]))
```

### Cost by business unit
```promql
sum by (business_unit) (rate(ccloud_cost_usd_hourly[1h]))
```

### Cost by product
```promql
sum by (product) (rate(ccloud_cost_usd_hourly[1h]))
```

### Cost by cost center
```promql
sum by (cost_center) (rate(ccloud_cost_usd_hourly[1h]))
```

---

## Aggregations

### Top 10 most expensive clusters
```promql
topk(10, sum by (cluster_id) (rate(ccloud_cost_usd_hourly[24h]) * 24))
```

### Bottom 10 cheapest clusters
```promql
bottomk(10, sum by (cluster_id) (rate(ccloud_cost_usd_hourly[24h]) * 24))
```

### Average hourly cost per cluster
```promql
avg(sum by (cluster_id) (rate(ccloud_cost_usd_hourly[1h])))
```

### Cost distribution percentiles
```promql
# 50th percentile (median)
quantile(0.5, sum by (cluster_id) (rate(ccloud_cost_usd_hourly[1h])))

# 95th percentile
quantile(0.95, sum by (cluster_id) (rate(ccloud_cost_usd_hourly[1h])))

# 99th percentile
quantile(0.99, sum by (cluster_id) (rate(ccloud_cost_usd_hourly[1h])))
```

### Week-over-week cost change
```promql
(
  sum(rate(ccloud_cost_usd_hourly[7d]))
  -
  sum(rate(ccloud_cost_usd_hourly[7d] offset 7d))
) / sum(rate(ccloud_cost_usd_hourly[7d] offset 7d)) * 100
```

---

## Confidence & Quality

### High confidence costs only
```promql
sum(rate(ccloud_cost_usd_hourly{allocation_confidence="high"}[1h]))
```

### Confidence score (% of costs with high confidence)
```promql
(
  sum(ccloud_cost_usd_hourly{allocation_confidence="high"})
  /
  sum(ccloud_cost_usd_hourly)
) * 100
```

### Data quality score (weighted)
```promql
(
  sum(ccloud_cost_usd_hourly{allocation_confidence="high"}) +
  sum(ccloud_cost_usd_hourly{allocation_confidence="medium"}) * 0.5
) / sum(ccloud_cost_usd_hourly) * 100
```

### Proportional allocation coverage
```promql
(
  sum(ccloud_cost_usd_hourly{allocation_method="proportional"})
  /
  sum(ccloud_cost_usd_hourly)
) * 100
```

---

## Alerting Queries

### Cost spike detected (>50% increase vs 7-day avg)
```promql
(
  sum(rate(ccloud_cost_usd_hourly[1h]))
  /
  avg_over_time(sum(rate(ccloud_cost_usd_hourly[1h]))[7d:1h])
) > 1.5
```

### Cluster cost exceeds budget threshold
```promql
sum by (cluster_id) (rate(ccloud_cost_usd_hourly[24h]) * 24) > 500
```

### Missing cost data (no recent ingestion)
```promql
(time() - ingestion_last_success_timestamp_seconds) > 3600
```

### Low data quality (< 60% high confidence)
```promql
(
  sum(ccloud_cost_usd_hourly{allocation_confidence="high"})
  /
  sum(ccloud_cost_usd_hourly)
) < 0.6
```

---

## Recording Rules

These pre-computed queries improve dashboard performance:

### Daily cost by cluster (recording rule)
```yaml
- record: cluster:cost_usd:rate24h
  expr: sum by (cluster_id) (rate(ccloud_cost_usd_hourly[24h]) * 24)
```

### Hourly cost by business unit (recording rule)
```yaml
- record: business_unit:cost_usd:rate1h
  expr: sum by (business_unit) (rate(ccloud_cost_usd_hourly[1h]))
```

### Confidence score (recording rule)
```yaml
- record: portal:confidence_score:percent
  expr: |
    (
      sum(ccloud_cost_usd_hourly{allocation_confidence="high"})
      /
      sum(ccloud_cost_usd_hourly)
    ) * 100
```

---

## Advanced Queries

### Cost per GB processed (if metrics available)
```promql
sum(rate(ccloud_cost_usd_hourly[1h]))
/
sum(rate(cluster_bytes_processed_total[1h]))
```

### Multi-dimensional aggregation
```promql
sum by (org_id, env_id, business_unit) (rate(ccloud_cost_usd_hourly[1h]))
```

### Time-shifted comparison (this week vs last week)
```promql
# This week
sum(rate(ccloud_cost_usd_hourly[7d]))

# Last week
sum(rate(ccloud_cost_usd_hourly[7d] offset 7d))
```

### Cost forecast (linear regression)
```promql
predict_linear(sum(rate(ccloud_cost_usd_hourly[1h]))[7d:1h], 86400)
```

---

## Tips & Best Practices

1. **Use rate() for cost queries** - Always use `rate()` when querying costs over time ranges
2. **Choose appropriate time ranges** - Use `[1h]` for real-time, `[24h]` for daily, `[7d]` for weekly
3. **Filter early** - Add label filters early in the query to reduce computation
4. **Use recording rules** - Pre-compute expensive queries for dashboards
5. **Set appropriate retention** - Configure Prometheus `storage.tsdb.retention.time` based on needs

---

## Useful Label Combinations

```promql
# Cluster + Product
sum by (cluster_id, product) (rate(ccloud_cost_usd_hourly[1h]))

# BU + Cost Center
sum by (business_unit, cost_center) (rate(ccloud_cost_usd_hourly[1h]))

# Org + Environment + Cluster
sum by (org_id, env_id, cluster_id) (rate(ccloud_cost_usd_hourly[1h]))

# Principal + Cluster
sum by (principal_id, cluster_id) (rate(ccloud_cost_usd_hourly[1h]))
```
