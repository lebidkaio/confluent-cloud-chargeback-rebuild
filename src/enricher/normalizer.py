"""Data normalizer - transforms API responses into internal models"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List
from uuid import uuid4

from src.common.logging import get_logger
from src.storage.models import AllocationConfidence

logger = get_logger(__name__)


def normalize_billing_data(raw_costs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalize raw billing API responses to internal cost format
    
    Args:
        raw_costs: Raw cost records from Billing API
        
    Returns:
        Normalized cost records ready for database insertion
    """
    normalized = []
    
    for cost in raw_costs:
        try:
            # Check for date in multiple fields
            date_val = cost.get("date") or cost.get("start_date")
            if not date_val:
                logger.warning(f"Skipping cost record with missing date. CONTENT: {cost}")
                continue

            # Extract IDs from nested resource dict if present
            resource_data = cost.get("resource") or {}
            
            # Extract fields with fallbacks
            normalized_cost = {
                "id": str(uuid4()),
                "date": date_val,
                "organization_id": cost.get("organization_id") or cost.get("organization", {}).get("id"),
                "environment_id": cost.get("environment_id") or cost.get("environment", {}).get("id") or resource_data.get("environment", {}).get("id"),
                "resource_id": cost.get("resource_id") or resource_data.get("id"),
                "resource_type": cost.get("resource_type") or cost.get("product"),
                "product": cost.get("product"),
                "amount_usd": Decimal(str(cost.get("amount", 0))),
                "quantity": cost.get("quantity"),
                "unit_price": Decimal(str(cost.get("price", 0))) if cost.get("price") else None,
                "raw_api_response": cost,  # Keep original for debugging
            }
            
            normalized.append(normalized_cost)
            
        except Exception as e:
            logger.error(f"Failed to normalize cost record: {e}", extra={"cost": cost})
            continue
    
    logger.info(f"Normalized {len(normalized)}/{len(raw_costs)} cost records")
    return normalized


def allocate_daily_to_hourly(
    daily_cost: Dict[str, Any],
    allocation_method: str = "even_split",
    hourly_metrics: List[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Allocate daily costs into hourly records
    
    Args:
        daily_cost: Daily cost record with 'date' and 'amount_usd'
        allocation_method: Method for allocation ('even_split' or 'proportional')
        hourly_metrics: Optional list of hourly metrics for proportional allocation
        
    Returns:
        List of 24 hourly cost records (one per hour)
    """
    hourly_costs = []
    
    # Parse the date
    cost_date = datetime.fromisoformat(daily_cost["date"].replace("Z", "+00:00"))
    
    # Total daily cost
    total_cost = Decimal(str(daily_cost["amount_usd"]))
    
    if allocation_method == "even_split":
        # Simple: divide by 24
        hourly_cost = total_cost / 24
        confidence = AllocationConfidence.MEDIUM
        
        for hour in range(24):
            timestamp_hour = cost_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            hourly_record = {
                "timestamp": timestamp_hour,
                "org_id": daily_cost.get("organization_id"),
                "env_id": daily_cost.get("environment_id"),
                "cluster_id": daily_cost.get("resource_id"),  # Assuming resource is cluster
                "principal_id": None,  # Will be enriched later
                "product": daily_cost.get("product") or daily_cost.get("resource_type"),
                "cost_usd": float(hourly_cost),
                "cost_source": "billing_api",
                "allocation_confidence": confidence.value,
                "allocation_method": "even_split",
                "business_unit": None,  # Will be enriched
                "cost_center": None,  # Will be enriched
            }
            
            hourly_costs.append(hourly_record)
    
    elif allocation_method == "proportional" and hourly_metrics:
        # Proportional: allocate based on usage metrics
        confidence = AllocationConfidence.HIGH
        
        # Calculate total metric value across all hours
        total_metric_value = sum(Decimal(str(m.get("value", 0))) for m in hourly_metrics)
        
        if total_metric_value == 0:
            # Fallback to even split if no metrics data
            logger.warning("No metric values found, falling back to even split")
            return allocate_daily_to_hourly(daily_cost, "even_split")
        
        # Create lookup for metrics by hour
        metrics_by_hour = {}
        for metric in hourly_metrics:
            timestamp = datetime.fromisoformat(metric["timestamp"].replace("Z", "+00:00"))
            hour = timestamp.hour
            metrics_by_hour[hour] = metric
        
        for hour in range(24):
            timestamp_hour = cost_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            
            # Get metric value for this hour
            metric_data = metrics_by_hour.get(hour, {})
            metric_value = Decimal(str(metric_data.get("value", 0)))
            
            # Calculate proportional cost
            if total_metric_value > 0:
                ratio = metric_value / total_metric_value
                hourly_cost = total_cost * ratio
            else:
                hourly_cost = Decimal(0)
            
            hourly_record = {
                "timestamp": timestamp_hour,
                "org_id": daily_cost.get("organization_id"),
                "env_id": daily_cost.get("environment_id"),
                "cluster_id": daily_cost.get("resource_id"),
                "principal_id": None,  # Will be enriched later
                "product": daily_cost.get("product") or daily_cost.get("resource_type"),
                "cost_usd": float(hourly_cost),
                "cost_source": "billing_api",
                "allocation_confidence": confidence.value,
                "allocation_method": "proportional",
                "business_unit": None,  # Will be enriched
                "cost_center": None,  # Will be enriched
            }
            
            hourly_costs.append(hourly_record)
    
    else:
        raise ValueError(
            f"Invalid allocation method '{allocation_method}' or missing metrics data"
        )
    
    logger.debug(
        f"Allocated ${total_cost} into {len(hourly_costs)} hourly records",
        extra={"date": daily_cost["date"], "method": allocation_method}
    )
    
    return hourly_costs


def normalize_organization(org_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize organization data from API"""
    return {
        "id": org_data.get("id"),
        "name": org_data.get("name") or org_data.get("display_name"),
        "display_name": org_data.get("display_name"),
        "meta_data": {
            "created_at": org_data.get("created_at"),
            "updated_at": org_data.get("updated_at"),
        },
    }


def normalize_environment(env_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize environment data from API"""
    # Extract org_id from nested structure or direct field
    org_id = env_data.get("organization_id")
    if not org_id and "organization" in env_data:
        org_id = env_data["organization"].get("id")
    
    # Try to extract from resource_name if available (crn://.../organization=org-xxx/...)
    if not org_id and "resource_name" in env_data:
        try:
            parts = env_data["resource_name"].split(":")
            for part in parts:
                if part.startswith("organization="):
                    org_id = part.split("=")[1]
                    break
        except Exception:
            pass

    if not org_id:
        logger.error(f"Missing org_id for environment: {env_data.get('id')}", extra={"env_data": env_data})
        # Try to find a default or fail gracefully? 
        # For now let it fail but at least we have the log. 
        # Or better: set a placeholder if strictly needed for debugging flow to proceed?
        # No, DB constraint is strict.
    
    return {
        "id": env_data.get("id"),
        "org_id": org_id,
        "name": env_data.get("name") or env_data.get("display_name"),
        "display_name": env_data.get("display_name"),
        "meta_data": {
            "created_at": env_data.get("created_at"),
            "stream_governance_package": env_data.get("stream_governance_package"),
        },
    }


def normalize_cluster(cluster_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize cluster data from API"""
    # Extract IDs from nested structures
    org_id = cluster_data.get("organization_id")
    env_id = cluster_data.get("environment_id")
    
    if not env_id and "environment" in cluster_data:
        env_id = cluster_data["environment"].get("id")
    
    spec = cluster_data.get("spec", {})
    
    return {
        "id": cluster_data.get("id"),
        "org_id": org_id,
        "env_id": env_id,
        "name": cluster_data.get("name") or cluster_data.get("display_name") or spec.get("display_name") or cluster_data.get("id"),
        "cluster_type": spec.get("availability") or cluster_data.get("cluster_type"),
        "cloud_provider": spec.get("cloud") or cluster_data.get("provider"),
        "region": spec.get("region") or cluster_data.get("region"),
        "meta_data": {
            "status": cluster_data.get("status"),
            "api_endpoint": spec.get("kafka_bootstrap_endpoint"),
            "config": spec.get("config"),
        },
    }


def normalize_principal(principal_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize service account/principal data from API"""
    org_id = principal_data.get("organization_id")
    if not org_id and "resource_id" in principal_data:
        # Extract from resource_id format: "org/{org-id}"
        resource_id = principal_data["resource_id"]
        if resource_id.startswith("org/"):
            org_id = resource_id.split("/")[1]
    
    return {
        "id": principal_data.get("id"),
        "org_id": org_id,
        "principal_type": "service_account",  # Default type
        "name": principal_data.get("name") or principal_data.get("display_name"),
        "email": principal_data.get("email"),
        "meta_data": {
            "description": principal_data.get("description"),
            "created_at": principal_data.get("created_at"),
        },
    }
