"""Unit tests for normalizer module"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from src.enricher.normalizer import (
    normalize_billing_data,
    allocate_daily_to_hourly,
    normalize_organization,
    normalize_cluster,
)


def test_normalize_billing_data():
    """Test normalizing raw billing API response"""
    raw_costs = [
        {
            "date": "2024-01-15",
            "organization_id": "org-123",
            "environment_id": "env-abc",
            "resource_id": "lkc-xyz",
            "resource_type": "kafka_cluster",
            "product": "kafka",
            "amount": 125.50,
            "quantity": 24.0,
            "price": 5.23,
        }
    ]
    
    normalized = normalize_billing_data(raw_costs)
    
    assert len(normalized) == 1
    assert normalized[0]["organization_id"] == "org-123"
    assert normalized[0]["amount_usd"] == Decimal("125.50")
    assert normalized[0]["product"] == "kafka"


def test_allocate_daily_to_hourly():
    """Test daily-to-hourly cost allocation"""
    daily_cost = {
        "date": "2024-01-15",
        "organization_id": "org-123",
        "environment_id": "env-abc",
        "resource_id": "lkc-xyz",
        "product": "kafka",
        "amount_usd": Decimal("24.00"),
    }
    
    hourly_costs = allocate_daily_to_hourly(daily_cost)
    
    # Should produce 24 hourly records
    assert len(hourly_costs) == 24
    
    # Each hour should have cost of $1.00 (24 / 24)
    for cost in hourly_costs:
        assert cost["cost_usd"] == 1.0
        assert cost["allocation_confidence"] == "medium"
        assert cost["org_id"] == "org-123"
        assert cost["product"] == "kafka"


def test_normalize_organization():
    """Test organization normalization"""
    org_data = {
        "id": "org-123",
        "name": "My Org",
        "display_name": "My Organization",
        "created_at": "2024-01-01T00:00:00Z",
    }
    
    normalized = normalize_organization(org_data)
    
    assert normalized["id"] == "org-123"
    assert normalized["name"] == "My Org"
    assert normalized["display_name"] == "My Organization"
    assert "created_at" in normalized["meta_data"]


def test_normalize_cluster():
    """Test cluster normalization"""
    cluster_data = {
        "id": "lkc-xyz",
        "name": "prod-cluster",
        "environment": {"id": "env-abc"},
        "spec": {
            "cloud": "aws",
            "region": "us-east-1",
            "availability": "multi-zone",
        },
        "status": "running",
    }
    
    normalized = normalize_cluster(cluster_data)
    
    assert normalized["id"] == "lkc-xyz"
    assert normalized["name"] == "prod-cluster"
    assert normalized["env_id"] == "env-abc"
    assert normalized["cloud_provider"] == "aws"
    assert normalized["region"] == "us-east-1"
