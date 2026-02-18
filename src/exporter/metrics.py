"""Prometheus metrics exporter"""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Response
from prometheus_client import REGISTRY, Gauge, generate_latest
from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.database import get_db
from src.storage.repository import CostRepository

logger = get_logger(__name__)
router = APIRouter(tags=["metrics"])

# Define Prometheus metrics
ccloud_cost_usd_hourly = Gauge(
    "ccloud_cost_usd_hourly",
    "Hourly cost in USD for Confluent Cloud resources",
    [
        "org_id",
        "env_id",
        "cluster_id",
        "principal_id",
        "business_unit",
        "product",
        "cost_center",
        "allocation_confidence",
    ],
)


def _generate_real_metrics(db: Session):
    """
    Generate metrics from real database data
    
    Replaces mock data with actual hourly costs from the repository.
    Falls back to mock data if no real data is available.
    """
    # Clear existing metrics
    ccloud_cost_usd_hourly.clear()
    
    try:
        # Get real cost data from repository
        cost_repo = CostRepository(db)
        recent_costs = cost_repo.get_latest_hourly_costs(hours=720)
        
        if not recent_costs:
            logger.warning("No cost data in database")
            return
        
        # Set metrics from real data
        for cost in recent_costs:
            # Handle confidence enum - extract .value if it's an enum
            conf = cost.get("confidence", "low")
            if hasattr(conf, "value"):
                conf = conf.value
            
            ccloud_cost_usd_hourly.labels(
                org_id=cost.get("org_id") or "unknown",
                env_id=cost.get("env_id") or "unknown",
                cluster_id=cost.get("cluster_id") or "unknown",
                principal_id=cost.get("principal_id") or "unknown",
                business_unit=cost.get("business_unit") or "unknown",
                product=cost.get("product") or "unknown",
                cost_center=cost.get("cost_center") or "unknown",
                allocation_confidence=str(conf),
            ).set(cost.get("cost_usd", 0.0))
        
        logger.info(f"Generated metrics from {len(recent_costs)} cost records")
        
    except Exception as e:
        logger.error(f"Failed to generate metrics from database: {e}")


@router.get("/metrics")
async def metrics(db: Session = Depends(get_db)):
    """
    Prometheus metrics endpoint in OpenMetrics format

    Returns metrics in a format that can be scraped by Prometheus.
    Uses real data from database if available, otherwise falls back to mock data.
    """
    # Generate metrics from real data (or fallback to mocks)
    _generate_real_metrics(db)

    # Generate metrics in OpenMetrics format
    metrics_output = generate_latest(REGISTRY)

    return Response(
        content=metrics_output,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
