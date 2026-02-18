"""Dimensions endpoints"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.storage.database import get_db
from src.storage.repository import DimensionRepository

router = APIRouter(prefix="/v1", tags=["dimensions"])


class DimensionResponse(BaseModel):
    """Response model for dimension queries"""

    dimension_type: str = Field(..., description="Type of dimension")
    dimensions: List[Dict[str, Any]] = Field(..., description="List of dimension records")
    total_count: int = Field(..., description="Total number of dimensions")


def _get_mock_dimensions(dimension_type: str) -> List[Dict[str, Any]]:
    """Generate mock dimension data for Milestone A"""

    mock_data = {
        "orgs": [
            {"id": "org-prod", "name": "Production Org", "display_name": "Production"},
            {"id": "org-dev", "name": "Development Org", "display_name": "Development"},
            {"id": "org-staging", "name": "Staging Org", "display_name": "Staging"},
        ],
        "envs": [
            {"id": "env-prod-us", "name": "prod-us-east-1", "display_name": "Production US East"},
            {"id": "env-prod-eu", "name": "prod-eu-west-1", "display_name": "Production EU West"},
            {"id": "env-dev", "name": "development", "display_name": "Development"},
        ],
        "clusters": [
            {
                "id": "lkc-prod-01",
                "name": "prod-kafka-cluster-01",
                "display_name": "Production Primary",
                "cluster_type": "dedicated",
                "cloud_provider": "aws",
                "region": "us-east-1",
            },
            {
                "id": "lkc-prod-02",
                "name": "prod-kafka-cluster-02",
                "display_name": "Production Secondary",
                "cluster_type": "dedicated",
                "cloud_provider": "aws",
                "region": "us-west-2",
            },
            {
                "id": "lkc-dev-01",
                "name": "dev-kafka-cluster",
                "display_name": "Development",
                "cluster_type": "basic",
                "cloud_provider": "aws",
                "region": "us-east-1",
            },
        ],
        "principals": [
            {
                "id": "sa-prod-app-01",
                "name": "prod-application-service-account",
                "principal_type": "service_account",
                "display_name": "Production App SA",
            },
            {
                "id": "sa-analytics-01",
                "name": "analytics-service-account",
                "principal_type": "service_account",
                "display_name": "Analytics SA",
            },
            {
                "id": "user-admin-01",
                "name": "admin@example.com",
                "principal_type": "user",
                "display_name": "Admin User",
                "email": "admin@example.com",
            },
        ],
        "business_units": [
            {"id": "engineering", "name": "Engineering", "display_name": "Engineering"},
            {"id": "data-platform", "name": "Data Platform", "display_name": "Data Platform"},
            {"id": "analytics", "name": "Analytics", "display_name": "Analytics"},
        ],
        "products": [
            {"id": "customer-data", "name": "Customer Data Platform", "display_name": "CDP"},
            {"id": "real-time-analytics", "name": "Real-Time Analytics", "display_name": "RTA"},
            {"id": "event-streaming", "name": "Event Streaming", "display_name": "Event Streaming"},
        ],
    }

    return mock_data.get(dimension_type, [])


@router.get("/dimensions", response_model=DimensionResponse)
async def get_all_dimensions(
    dimension_type: str = "orgs",
    db: Session = Depends(get_db),
):
    """
    Get all dimensions of a specific type

    Valid dimension types:
    - orgs: Organizations
    - envs: Environments
    - clusters: Kafka clusters
    - principals: Service accounts and users
    - business_units: Business units for allocation
    - products: Products for allocation

    For Milestone A, this returns mocked data.
    """
    # Get mock data for now
    dimensions = _get_mock_dimensions(dimension_type)

    return DimensionResponse(
        dimension_type=dimension_type,
        dimensions=dimensions,
        total_count=len(dimensions),
    )
