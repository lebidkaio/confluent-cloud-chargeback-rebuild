"""Unit tests for dimensions endpoints"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_get_dimensions_orgs():
    """Test /v1/dimensions for orgs"""
    response = client.get("/v1/dimensions", params={"dimension_type": "orgs"})
    assert response.status_code == 200
    data = response.json()
    assert data["dimension_type"] == "orgs"
    assert len(data["dimensions"]) > 0
    assert data["total_count"] > 0


def test_get_dimensions_clusters():
    """Test /v1/dimensions for clusters"""
    response = client.get("/v1/dimensions", params={"dimension_type": "clusters"})
    assert response.status_code == 200
    data = response.json()
    assert data["dimension_type"] == "clusters"
    assert len(data["dimensions"]) > 0
    # Check cluster structure
    cluster = data["dimensions"][0]
    assert "id" in cluster
    assert "name" in cluster
    assert "cluster_type" in cluster
    assert "cloud_provider" in cluster


def test_get_dimensions_business_units():
    """Test /v1/dimensions for business units"""
    response = client.get("/v1/dimensions", params={"dimension_type": "business_units"})
    assert response.status_code == 200
    data = response.json()
    assert data["dimension_type"] == "business_units"
    assert len(data["dimensions"]) > 0
