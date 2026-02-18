"""Unit tests for cost endpoints"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_query_costs():
    """Test /v1/costs endpoint"""
    response = client.get(
        "/v1/costs",
        params={
            "from_ts": "2024-01-01T00:00:00Z",
            "to_ts": "2024-01-31T23:59:59Z",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total_records" in data
    assert "from_timestamp" in data
    assert "to_timestamp" in data
    assert isinstance(data["data"], list)


def test_query_costs_with_filters():
    """Test /v1/costs endpoint with filters"""
    response = client.get(
        "/v1/costs",
        params={
            "from_ts": "2024-01-01T00:00:00Z",
            "to_ts": "2024-01-31T23:59:59Z",
            "org_id": "org-prod",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) > 0


def test_query_costs_with_group_by():
    """Test /v1/costs endpoint with grouping"""
    response = client.get(
        "/v1/costs",
        params={
            "from_ts": "2024-01-01T00:00:00Z",
            "to_ts": "2024-01-31T23:59:59Z",
            "group_by": "cluster_id,business_unit",
            "limit": 10,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["group_by"] == ["cluster_id", "business_unit"]
