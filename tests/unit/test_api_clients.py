"""Unit tests for API clients"""
import pytest
from unittest.mock import Mock, patch
from datetime import date

from src.collector.billing_api import BillingAPIClient
from src.collector.core_objects_api import CoreObjectsAPIClient


@patch("src.collector.billing_api.ConfluentCloudClient")
def test_billing_api_get_costs(mock_client):
    """Test billing API cost retrieval"""
    # Mock the response
    mock_instance = Mock()
    mock_instance.get.return_value = {
        "data": [
            {
                "date": "2024-01-15",
                "organization_id": "org-123",
                "amount": 125.50,
                "product": "kafka",
            }
        ]
    }
    mock_client.return_value = mock_instance
    
    # Create client and fetch costs
    client = BillingAPIClient()
    costs = client.get_costs(date(2024, 1, 15), date(2024, 1, 15))
    
    assert len(costs) == 1
    assert costs[0]["amount"] == 125.50


@patch("src.collector.core_objects_api.ConfluentCloudClient")
def test_core_objects_api_get_organizations(mock_client):
    """Test core objects API organization retrieval"""
    # Mock the response
    mock_instance = Mock()
    mock_instance.get.return_value = {
        "data": [
            {"id": "org-123", "display_name": "Test Org"},
            {"id": "org-456", "display_name": "Another Org"},
        ]
    }
    mock_client.return_value = mock_instance
    
    # Create client and fetch orgs
    client = CoreObjectsAPIClient()
    orgs = client.get_organizations()
    
    assert len(orgs) == 2
    assert orgs[0]["id"] == "org-123"


@patch("src.collector.core_objects_api.ConfluentCloudClient")
def test_core_objects_api_get_all(mock_client):
    """Test fetching all core objects"""
    # Mock the response
    mock_instance = Mock()
    mock_instance.get.side_effect = [
        {"data": [{"id": "org-123"}]},  # organizations
        {"data": [{"id": "env-abc"}]},  # environments
        {"data": [{"id": "lkc-xyz"}]},  # clusters
        {"data": [{"id": "sa-001"}]},   # service accounts
    ]
    mock_client.return_value = mock_instance
    
    # Create client and fetch all
    client = CoreObjectsAPIClient()
    all_objects = client.get_all_core_objects()
    
    assert "organizations" in all_objects
    assert "environments" in all_objects
    assert "clusters" in all_objects
    assert "service_accounts" in all_objects
    assert len(all_objects["organizations"]) == 1
