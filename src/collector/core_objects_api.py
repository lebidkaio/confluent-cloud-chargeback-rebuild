"""Confluent Cloud Core Objects API client"""
from typing import Any, Dict, List, Optional

from src.collector.confluent_client import ConfluentCloudClient
from src.common.logging import get_logger

logger = get_logger(__name__)


class CoreObjectsAPIClient:
    """
    Client for Confluent Cloud Core Objects APIs
    
    Fetches organizations, environments, clusters, and service accounts.
    API Documentation: https://docs.confluent.io/cloud/current/api.html
    """
    
    def __init__(self, client: Optional[ConfluentCloudClient] = None):
        """
        Initialize Core Objects API client
        
        Args:
            client: Optional ConfluentCloudClient instance
        """
        self.client = client or ConfluentCloudClient()
    
    def get_organizations(self) -> List[Dict[str, Any]]:
        """
        Fetch all organizations
        
        Returns:
            List of organizations:
            [
                {
                    "id": "org-123",
                    "display_name": "Production Org",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                }
            ]
        """
        logger.info("Fetching organizations")
        
        try:
            response = self.client.get("/org/v2/organizations")
            orgs = response.get("data") or []
            
            logger.info(f"Retrieved {len(orgs)} organizations")
            return orgs
            
        except Exception as e:
            logger.error(f"Failed to fetch organizations: {e}")
            raise
    
    def get_environments(self, organization_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch environments, optionally filtered by organization
        
        Args:
            organization_id: Optional filter by organization
            
        Returns:
            List of environments:
            [
                {
                    "id": "env-abc",
                    "display_name": "Production",
                    "organization_id": "org-123",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            ]
        """
        logger.info("Fetching environments", extra={"org_id": organization_id})
        
        params = {}
        if organization_id:
            params["organization"] = organization_id
        
        try:
            response = self.client.get("/org/v2/environments", params=params)
            envs = response.get("data") or []
            
            logger.info(f"Retrieved {len(envs)} environments")
            return envs
            
        except Exception as e:
            logger.error(f"Failed to fetch environments: {e}")
            raise
    
    def get_clusters(
        self,
        environment_id: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch Kafka clusters
        
        Args:
            environment_id: Optional filter by environment
            organization_id: Optional filter by organization
            
        Returns:
            List of clusters:
            [
                {
                    "id": "lkc-xyz",
                    "display_name": "prod-kafka-01",
                    "environment_id": "env-abc",
                    "provider": "aws",
                    "region": "us-east-1",
                    "availability": "multi-zone",
                    "cluster_type": "dedicated",
                    "status": "running"
                }
            ]
        """
        logger.info(
            "Fetching clusters",
            extra={"env_id": environment_id, "org_id": organization_id}
        )
        
        params = {}
        if environment_id:
            params["environment"] = environment_id
        
        try:
            response = self.client.get("/cmk/v2/clusters", params=params)
            clusters = response.get("data") or []
            
            logger.info(f"Retrieved {len(clusters)} clusters")
            return clusters
            
        except Exception as e:
            logger.error(f"Failed to fetch clusters: {e}")
            raise
    
    def get_service_accounts(
        self,
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch service accounts
        
        Args:
            organization_id: Optional filter by organization
            
        Returns:
            List of service accounts:
            [
                {
                    "id": "sa-123",
                    "display_name": "kafka-producer-sa",
                    "description": "Service account for Kafka producer",
                    "created_at": "2024-01-01T00:00:00Z"
                }
            ]
        """
        logger.info("Fetching service accounts", extra={"org_id": organization_id})
        
        params = {}
        if organization_id:
            params["organization"] = organization_id
        
        try:
            response = self.client.get("/iam/v2/service-accounts", params=params)
            sas = response.get("data") or []
            
            logger.info(f"Retrieved {len(sas)} service accounts")
            return sas
            
        except Exception as e:
            logger.error(f"Failed to fetch service accounts: {e}")
            raise
    
    def get_all_core_objects(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch all core objects in a single call
        
        Returns:
            Dictionary with all core objects:
            {
                "organizations": [...],
                "environments": [...],
                "clusters": [...],
                "service_accounts": [...]
            }
        """
        logger.info("Fetching all core objects")
        
        # 1. Fetch Organizations
        orgs = self.get_organizations()
        
        # 2. Fetch Environments (iterate orgs to ensure context)
        envs = []
        for org in orgs:
            org_id = org.get("id")
            if org_id:
                try:
                    org_envs = self.get_environments(organization_id=org_id)
                    # Enrich with org_id ensure it's present
                    for env in org_envs:
                        if not env.get("organization_id"):
                            env["organization_id"] = org_id
                    envs.extend(org_envs)
                except Exception as e:
                    logger.error(f"Failed to fetch envs for org {org_id}: {e}")
        
        # 3. Fetch Clusters (requires environment_id)
        clusters = []
        for env in envs:
            env_id = env.get("id")
            if env_id:
                try:
                    env_clusters = self.get_clusters(environment_id=env_id)
                    # Enrich clusters with org_id and env_id
                    for cluster in env_clusters:
                         if not cluster.get("organization_id") and env.get("organization_id"):
                             cluster["organization_id"] = env.get("organization_id")
                         
                         if not cluster.get("environment_id"):
                             cluster["environment_id"] = env_id
                    clusters.extend(env_clusters)
                except Exception as e:
                    logger.error(f"Failed to fetch clusters for env {env_id}: {e}")
        
        # 4. Fetch Service Accounts (iterate orgs)
        service_accounts = []
        for org in orgs:
             org_id = org.get("id")
             if org_id:
                 try:
                     org_sas = self.get_service_accounts(organization_id=org_id)
                     for sa in org_sas:
                         if not sa.get("organization_id"):
                             sa["organization_id"] = org_id
                     service_accounts.extend(org_sas)
                 except Exception as e:
                     logger.error(f"Failed to fetch service accounts for org {org_id}: {e}")
        
        return {
            "organizations": orgs,
            "environments": envs,
            "clusters": clusters,
            "service_accounts": service_accounts,
        }
