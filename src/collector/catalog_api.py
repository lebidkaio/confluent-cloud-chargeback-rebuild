"""Confluent Stream Governance Catalog API client

Fetches entity tags from the Stream Catalog for cost attribution.
Uses Schema Registry endpoint with separate credentials.

API Reference: https://docs.confluent.io/cloud/current/stream-governance/stream-catalog-rest-apis.html
"""
from typing import Any, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.common.config import get_settings
from src.common.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CatalogAPIClient:
    """
    Client for Confluent Stream Governance Catalog API

    Fetches entity tags (owner, team, cost-center, etc.) from the
    Stream Catalog to enrich cost data with business metadata.

    Requires:
    - Stream Governance package (ESSENTIALS or ADVANCED)
    - Schema Registry API Key/Secret
    - Schema Registry URL
    """

    # Tag keys relevant for cost attribution
    COST_ATTRIBUTION_TAGS = [
        "owner", "team", "cost_center", "business_unit",
        "project", "department", "environment",
    ]

    def __init__(
        self,
        sr_url: Optional[str] = None,
        sr_api_key: Optional[str] = None,
        sr_api_secret: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        Initialize Catalog API client

        Args:
            sr_url: Schema Registry URL
            sr_api_key: Schema Registry API key
            sr_api_secret: Schema Registry API secret
            timeout: Request timeout in seconds
        """
        self.sr_url = (sr_url or settings.schema_registry_url).rstrip("/")
        self.sr_api_key = sr_api_key or settings.schema_registry_api_key
        self.sr_api_secret = sr_api_secret or settings.schema_registry_api_secret
        self.timeout = timeout
        self._enabled = bool(self.sr_url and self.sr_api_key and self.sr_api_secret)

        if not self._enabled:
            logger.warning(
                "Catalog API not configured. Set SCHEMA_REGISTRY_URL, "
                "SCHEMA_REGISTRY_API_KEY, SCHEMA_REGISTRY_API_SECRET to enable."
            )
            return

        self.client = httpx.Client(
            auth=(self.sr_api_key, self.sr_api_secret),
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"{settings.service_name}/{settings.service_version}",
            },
        )

    @property
    def is_enabled(self) -> bool:
        """Check if Catalog API is configured and available"""
        return self._enabled

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        reraise=True,
    )
    def _request(self, method: str, path: str, params: Optional[Dict] = None) -> Any:
        """Make HTTP request to Catalog API"""
        if not self._enabled:
            return None

        url = f"{self.sr_url}{path}"

        logger.debug(f"Catalog API: {method} {url}", extra={"params": params})

        try:
            response = self.client.request(method=method, url=url, params=params)

            if response.status_code == 404:
                logger.debug(f"Entity not found: {path}")
                return None

            if response.status_code >= 400:
                logger.error(f"Catalog API error {response.status_code}: {response.text}")
                return None

            return response.json()

        except Exception as e:
            logger.error(f"Catalog API request failed: {e}")
            raise

    def get_entity_tags(
        self,
        entity_type: str,
        qualified_name: str,
    ) -> Dict[str, str]:
        """
        Fetch tags for a specific entity

        Args:
            entity_type: Entity type (e.g. 'kafka_cluster', 'kafka_topic', 'sr_schema')
            qualified_name: Fully qualified entity name
                For clusters: 'lkc-xxxxx'
                For topics: 'lkc-xxxxx:topic-name'

        Returns:
            Dictionary of tag_key -> tag_value
        """
        path = f"/catalog/v1/entity/type/{entity_type}/name/{qualified_name}/tags"
        result = self._request("GET", path)

        if not result:
            return {}

        # Parse tag response into simple key-value dict
        tags = {}
        for tag_entry in result:
            tag_name = tag_entry.get("typeName", "")
            # Tag attributes contain the actual values
            attributes = tag_entry.get("attributes", {})

            # Confluent tags have typeName as the tag category
            # and attributes for additional metadata
            if tag_name:
                # Store the tag name as-is for standard tags
                tags[tag_name.lower()] = attributes.get("value", tag_name)

                # Also check if tag attributes contain our target keys
                for attr_key, attr_value in attributes.items():
                    if attr_key.lower() in self.COST_ATTRIBUTION_TAGS:
                        tags[attr_key.lower()] = str(attr_value)

        return tags

    def get_cluster_tags(self, cluster_id: str) -> Dict[str, str]:
        """
        Fetch tags for a Kafka cluster

        Args:
            cluster_id: Cluster ID (e.g. 'lkc-xxxxx')

        Returns:
            Dictionary of tag_key -> tag_value
        """
        return self.get_entity_tags("kafka_cluster", cluster_id)

    def get_topic_tags(self, cluster_id: str, topic_name: str) -> Dict[str, str]:
        """
        Fetch tags for a Kafka topic

        Args:
            cluster_id: Cluster ID
            topic_name: Topic name

        Returns:
            Dictionary of tag_key -> tag_value
        """
        qualified_name = f"{cluster_id}:{topic_name}"
        return self.get_entity_tags("kafka_topic", qualified_name)

    def get_all_cluster_tags(
        self, cluster_ids: List[str]
    ) -> Dict[str, Dict[str, str]]:
        """
        Fetch tags for all given clusters

        Args:
            cluster_ids: List of cluster IDs

        Returns:
            Dictionary mapping cluster_id -> {tag_key: tag_value}
        """
        if not self._enabled:
            logger.info("Catalog API not configured, skipping tag collection")
            return {}

        results = {}
        for cluster_id in cluster_ids:
            try:
                tags = self.get_cluster_tags(cluster_id)
                if tags:
                    results[cluster_id] = tags
                    logger.info(
                        f"Found {len(tags)} tags for cluster {cluster_id}",
                        extra={"tags": tags},
                    )
            except Exception as e:
                logger.warning(f"Failed to fetch tags for cluster {cluster_id}: {e}")

        logger.info(
            f"Collected tags for {len(results)}/{len(cluster_ids)} clusters"
        )
        return results

    def search_entities(
        self,
        query: str = "*",
        entity_type: str = "kafka_cluster",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Search for entities in the catalog

        Args:
            query: Search query (default: all)
            entity_type: Entity type filter
            limit: Max results

        Returns:
            List of matching entities
        """
        params = {
            "query": query,
            "type": entity_type,
            "limit": limit,
        }
        result = self._request("GET", "/catalog/v1/search/basic", params=params)

        if not result:
            return []

        return result.get("entities", [])

    def close(self):
        """Close HTTP client"""
        if self._enabled and hasattr(self, "client"):
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
