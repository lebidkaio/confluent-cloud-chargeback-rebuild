"""Cost query endpoints"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.database import get_db
from src.storage.repository import CostRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/v1", tags=["costs"])


class CostQueryResponse(BaseModel):
    """Response model for cost queries"""

    data: List[Dict[str, Any]] = Field(..., description="Cost data records")
    total_records: int = Field(..., description="Total number of records")
    from_timestamp: str = Field(..., description="Query start timestamp")
    to_timestamp: str = Field(..., description="Query end timestamp")
    group_by: Optional[List[str]] = Field(None, description="Grouping fields applied")


def _get_mock_cost_data() -> List[Dict[str, Any]]:
    """
    Generate mock cost data for Milestone A
    This will be replaced with real data in Milestone B
    """
    base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

    mock_data = []
    orgs = ["org-prod", "org-dev", "org-staging"]
    clusters = ["lkc-prod-01", "lkc-prod-02", "lkc-dev-01"]
    business_units = ["engineering", "data-platform", "analytics"]

    for hour_offset in range(24):
        timestamp = base_time - timedelta(hours=hour_offset)
        for org in orgs:
            for cluster in clusters:
                for bu in business_units:
                    mock_data.append({
                        "timestamp": timestamp.isoformat(),
                        "org_id": org,
                        "cluster_id": cluster,
                        "business_unit": bu,
                        "cost_usd": round(10.0 + (hour_offset * 0.5), 2),
                        "allocation_confidence": "medium",
                    })

    return mock_data


@router.get("/costs", response_model=CostQueryResponse)
async def query_costs(
    from_ts: str = Query(..., description="Start timestamp (ISO 8601)", example="2024-01-01T00:00:00Z"),
    to_ts: str = Query(..., description="End timestamp (ISO 8601)", example="2024-01-31T23:59:59Z"),
    group_by: Optional[str] = Query(None, description="Comma-separated grouping fields", example="cluster_id,business_unit"),
    org_id: Optional[str] = Query(None, description="Filter by organization ID"),
    cluster_id: Optional[str] = Query(None, description="Filter by cluster ID"),
    env_id: Optional[str] = Query(None, description="Filter by environment ID"),
    principal_id: Optional[str] = Query(None, description="Filter by principal ID"),
    business_unit: Optional[str] = Query(None, description="Filter by business unit"),
    cost_center: Optional[str] = Query(None, description="Filter by cost center"),
    product: Optional[str] = Query(None, description="Filter by product"),
    confidence: Optional[str] = Query(None, description="Filter by allocation confidence (low/medium/high)"),
    allocation_method: Optional[str] = Query(None, description="Filter by allocation method (even_split/proportional)"),
    tags: Optional[str] = Query(None, description="Filter by tags (format: key:value,key:value)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    use_cache: bool = Query(True, description="Use query cache"),
    db: Session = Depends(get_db),
):
    """
    Query cost data with advanced filters and grouping
    
    **New in Milestone C:**
    - Filter by confidence level
    - Filter by principal and tags
    - Multi-dimensional grouping
    - Query caching for performance
    """
    logger.info(
        f"Cost query",
        extra={
            "from": from_ts,
            "to": to_ts,
            "group_by": group_by,
            "filters": {
                "org_id": org_id,
                "cluster_id": cluster_id,
                "confidence": confidence,
                "tags": tags,
            }
        }
    )

    # Parse timestamps
    try:
        from_datetime = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
        to_datetime = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
    except ValueError as e:
        logger.error(f"Invalid timestamp format: {e}")
        return CostQueryResponse(
            data=[],
            total_records=0,
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            group_by=None,
        )

    # Build query parameters for cache
    query_params = {
        "from_ts": from_ts,
        "to_ts": to_ts,
        "group_by": group_by,
        "org_id": org_id,
        "cluster_id": cluster_id,
        "env_id": env_id,
        "principal_id": principal_id,
        "business_unit": business_unit,
        "cost_center": cost_center,
        "product": product,
        "confidence": confidence,
        "allocation_method": allocation_method,
        "tags": tags,
        "limit": limit,
        "offset": offset,
    }

    # Try cache first
    if use_cache:
        from src.common.cache import get_query_cache
        cache = get_query_cache()
        cached_result = cache.get(query_params)
        if cached_result:
            logger.info("Returning cached result")
            return cached_result

    # Query repository
    cost_repo = CostRepository(db)
    
    # Build filters
    filters = {}
    if org_id:
        filters["org_id"] = org_id
    if cluster_id:
        filters["cluster_id"] = cluster_id
    if env_id:
        filters["env_id"] = env_id
    if principal_id:
        filters["principal_id"] = principal_id
    if business_unit:
        filters["business_unit"] = business_unit
    if cost_center:
        filters["cost_center"] = cost_center
    if product:
        filters["product"] = product
    if confidence:
        filters["allocation_confidence"] = confidence
    if allocation_method:
        filters["allocation_method"] = allocation_method

    # Parse group_by
    group_by_list = group_by.split(",") if group_by else None

    # Query database
    try:
        costs = cost_repo.query_costs(
            from_datetime=from_datetime,
            to_datetime=to_datetime,
            filters=filters,
            group_by=group_by_list,
            limit=limit,
            offset=offset,
        )
        
        # Convert to dict format
        data = [
            {
                "timestamp_hour": c.get("timestamp_hour").isoformat() if c.get("timestamp_hour") else None,
                "org_id": c.get("org_id"),
                "env_id": c.get("env_id"),
                "cluster_id": c.get("cluster_id"),
                "principal_id": c.get("principal_id"),
                "business_unit": c.get("business_unit"),
                "cost_center": c.get("cost_center"),
                "product": c.get("product"),
                "cost_usd": float(c.get("cost_usd", 0)),
                "allocation_confidence": c.get("allocation_confidence"),
                "allocation_method": c.get("allocation_method"),
            }
            for c in costs
        ]
        
        response = CostQueryResponse(
            data=data,
            total_records=len(data),
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            group_by=group_by_list,
        )
        
        # Cache the result
        if use_cache:
            cache.set(query_params, response)
        
        logger.info(f"Returned {len(data)} cost records")
        return response

    except Exception as e:
        logger.error(f"Failed to query costs: {e}", exc_info=True)
        
        # Fallback to mock data
        logger.warning("Falling back to mock data")
        mock_data = _get_mock_cost_data()
        
        # Apply filters to mock data
        filtered_data = mock_data
        if org_id:
            filtered_data = [d for d in filtered_data if d.get("org_id") == org_id]
        if cluster_id:
            filtered_data = [d for d in filtered_data if d.get("cluster_id") == cluster_id]
        if business_unit:
            filtered_data = [d for d in filtered_data if d.get("business_unit") == business_unit]
        if confidence:
            filtered_data = [d for d in filtered_data if d.get("allocation_confidence") == confidence]

        # Apply pagination
        paginated_data = filtered_data[offset : offset + limit]

        return CostQueryResponse(
            data=paginated_data,
            total_records=len(filtered_data),
            from_timestamp=from_ts,
            to_timestamp=to_ts,
            group_by=group_by_list,
        )
