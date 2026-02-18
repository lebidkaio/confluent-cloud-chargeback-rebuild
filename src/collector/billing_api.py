"""Confluent Cloud Billing API client"""
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from src.collector.confluent_client import ConfluentCloudClient
from src.common.logging import get_logger

logger = get_logger(__name__)


class BillingAPIClient:
    """
    Client for Confluent Cloud Billing API
    
    Fetches cost data for organizations.
    API Documentation: https://docs.confluent.io/cloud/current/billing/overview.html
    """
    
    def __init__(self, client: Optional[ConfluentCloudClient] = None):
        """
        Initialize Billing API client
        
        Args:
            client: Optional ConfluentCloudClient instance (creates new if not provided)
        """
        self.client = client or ConfluentCloudClient()
    
    def get_costs(
        self,
        start_date: date,
        end_date: date,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch cost data for a date range
        
        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            organization_id: Optional filter by organization
            
        Returns:
            List of cost records:
            [
                {
                    "date": "2024-01-15",
                    "organization_id": "org-123",
                    "environment_id": "env-abc",
                    "resource_id": "lkc-xyz",
                    "resource_type": "kafka_cluster",
                    "product": "kafka",
                    "amount": 125.50,
                    "unit": "USD",
                    "quantity": 24.0,
                    "price": 5.23
                }
            ]
        """
        logger.info(
            f"Fetching costs from {start_date} to {end_date}",
            extra={"org_id": organization_id}
        )
        
        params = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
        
        if organization_id:
            params["organization.id"] = organization_id
        
        try:
            response = self.client.get("/billing/v1/costs", params=params)
            
            costs = response.get("data", [])
            logger.info(f"Retrieved {len(costs)} cost records")
            
            return costs
            
        except Exception as e:
            logger.error(f"Failed to fetch costs: {e}")
            raise
    
    def get_costs_for_yesterday(
        self,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to fetch yesterday's costs
        
        Args:
            organization_id: Optional filter by organization
            
        Returns:
            List of cost records for yesterday
        """
        yesterday = date.today() - timedelta(days=1)
        return self.get_costs(yesterday, yesterday, organization_id)
    
    def get_costs_for_month(
        self,
        year: int,
        month: int,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch costs for an entire month
        
        Args:
            year: Year (e.g., 2024)
            month: Month (1-12)
            organization_id: Optional filter by organization
            
        Returns:
            List of cost records for the month
        """
        # First day of month
        start_date = date(year, month, 1)
        
        # Last day of month
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        return self.get_costs(start_date, end_date, organization_id)
