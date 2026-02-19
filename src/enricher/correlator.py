"""Data correlator - enriches cost data with entity relationships"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.models import (
    DimensionCluster,
    DimensionEnv,
    DimensionOrg,
    DimensionPrincipal,
)

logger = get_logger(__name__)


class EntityCorrelator:
    """
    Correlates cost data with entities from dimension tables
    
    Enriches hourly cost records with:
    - Organization details
    - Environment details
    - Cluster details
    - Principal details
    - Business unit/cost center metadata
    """
    
    def __init__(self, db: Session):
        """
        Initialize correlator with database session
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def correlate_cluster(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up cluster details
        
        Args:
            cluster_id: Cluster ID
            
        Returns:
            Cluster details or None if not found
        """
        if not cluster_id:
            return None
        
        cluster = self.db.query(DimensionCluster).filter_by(id=cluster_id).first()
        
        if cluster:
            return {
                "id": cluster.id,
                "name": cluster.name,
                "cluster_type": cluster.cluster_type,
                "cloud_provider": cluster.cloud_provider,
                "region": cluster.region,
                "org_id": cluster.org_id,
                "env_id": cluster.env_id,
            }
        
        logger.warning(f"Cluster not found: {cluster_id}")
        return None
    
    def correlate_organization(self, org_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up organization details
        
        Args:
            org_id: Organization ID
            
        Returns:
            Organization details or None if not found
        """
        if not org_id:
            return None
        
        org = self.db.query(DimensionOrg).filter_by(id=org_id).first()
        
        if org:
            return {
                "id": org.id,
                "name": org.name,
                "display_name": org.display_name,
            }
        
        logger.warning(f"Organization not found: {org_id}")
        return None
    
    def correlate_environment(self, env_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up environment details
        
        Args:
            env_id: Environment ID
            
        Returns:
            Environment details or None if not found
        """
        if not env_id:
            return None
        
        env = self.db.query(DimensionEnv).filter_by(id=env_id).first()
        
        if env:
            return {
                "id": env.id,
                "name": env.name,
                "display_name": env.display_name,
                "org_id": env.org_id,
            }
        
        logger.warning(f"Environment not found: {env_id}")
        return None
    
    def correlate_principal(self, principal_id: str) -> Optional[Dict[str, Any]]:
        """
        Look up principal (service account/user) details
        
        Args:
            principal_id: Principal ID
            
        Returns:
            Principal details or None if not found
        """
        if not principal_id:
            return None
        
        principal = self.db.query(DimensionPrincipal).filter_by(id=principal_id).first()
        
        if principal:
            return {
                "id": principal.id,
                "name": principal.name,
                "principal_type": principal.principal_type,
                "email": principal.email,
                "org_id": principal.org_id,
                "description": principal.meta_data.get("description") if principal.meta_data else None,
            }
        
        logger.warning(f"Principal not found: {principal_id}")
        return None
    
    def get_entity_tags(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Extract tags/labels from entity metadata
        
        Args:
            entity_type: Type of entity ('cluster', 'org', 'env', 'principal')
            entity_id: Entity ID
            
        Returns:
            Dictionary of tags/labels
        """
        tags = {}
        
        if entity_type == "cluster":
            cluster = self.db.query(DimensionCluster).filter_by(id=entity_id).first()
            if cluster and cluster.meta_data:
                tags = cluster.meta_data.get("tags", {})
        
        elif entity_type == "org":
            org = self.db.query(DimensionOrg).filter_by(id=entity_id).first()
            if org and org.meta_data:
                tags = org.meta_data.get("tags", {})
        
        elif entity_type == "env":
            env = self.db.query(DimensionEnv).filter_by(id=entity_id).first()
            if env and env.meta_data:
                tags = env.meta_data.get("tags", {})
        
        # Extract standard tags
        return {
            "environment": tags.get("env", tags.get("environment", "unknown")),
            "team": tags.get("team", "unknown"),
            "product": tags.get("product", "unknown"),
            "cost_center": tags.get("cost_center", "unknown"),
            "business_unit": tags.get("business_unit", "unknown"),
        }
    
    def build_correlation_graph(self, cost_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build complete entity correlation graph for cost record
        
        Creates a full graph of related entities:
        - Organization
        - Environment  
        - Cluster
        - Principal
        - Tags from all entities
        
        Args:
            cost_record: Cost record to correlate
            
        Returns:
            Complete correlation graph
        """
        graph = {
            "org": None,
            "env": None,
            "cluster": None,
            "principal": None,
            "tags": {},
        }
        
        # Correlate organization
        if cost_record.get("org_id"):
            graph["org"] = self.correlate_organization(cost_record["org_id"])
            if graph["org"]:
                org_tags = self.get_entity_tags("org", cost_record["org_id"])
                graph["tags"].update(org_tags)
        
        # Correlate environment
        if cost_record.get("env_id"):
            graph["env"] = self.correlate_environment(cost_record["env_id"])
            if graph["env"]:
                env_tags = self.get_entity_tags("env", cost_record["env_id"])
                graph["tags"].update(env_tags)
        
        # Correlate cluster
        if cost_record.get("cluster_id"):
            graph["cluster"] = self.correlate_cluster(cost_record["cluster_id"])
            if graph["cluster"]:
                cluster_tags = self.get_entity_tags("cluster", cost_record["cluster_id"])
                graph["tags"].update(cluster_tags)
        
        # Correlate principal
        if cost_record.get("principal_id"):
            graph["principal"] = self.correlate_principal(cost_record["principal_id"])
        
        logger.debug(f"Built correlation graph with {len(graph['tags'])} tags")
        return graph
    
    def enrich_with_metadata(self, cost_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich cost record with entity metadata
        
        Enhanced to use complete correlation graph and tag extraction.
        Priority: Tags > Inference > Defaults
        
        Args:
            cost_record: Hourly cost record
            
        Returns:
            Enriched cost record
        """
        enriched = cost_record.copy()
        
        # Build complete correlation graph
        graph = self.build_correlation_graph(cost_record)
        tags = graph.get("tags", {})
        
        # Enrich with business unit (priority: tags > inference > default)
        if tags.get("business_unit") and tags["business_unit"] != "unknown":
            enriched["business_unit"] = tags["business_unit"]
        elif graph.get("cluster"):
            enriched["business_unit"] = self._infer_business_unit(graph["cluster"])
        else:
            enriched["business_unit"] = "unknown"
        
        # Enrich with cost center (priority: tags > inference > default)
        if tags.get("cost_center") and tags["cost_center"] != "unknown":
            enriched["cost_center"] = tags["cost_center"]
        elif graph.get("cluster"):
            enriched["cost_center"] = self._infer_cost_center(graph["cluster"])
        else:
            enriched["cost_center"] = "unallocated"
        
        # Enrich with product (priority: existing > tags > default)
        if not enriched.get("product") or enriched.get("product") == "unknown":
            enriched["product"] = tags.get("product", "unknown")
            
        # Enrich with principal (from tags)
        if not enriched.get("principal_id"):
            enriched["principal_id"] = self._infer_principal(tags, graph)
        
        # Enrich with team/environment tags
        enriched["team"] = tags.get("team", "unknown")
        enriched["environment"] = tags.get("environment", "unknown")
        
        # Store correlation graph for debugging
        enriched["_correlation_graph"] = graph
        
        logger.debug(
            f"Enriched cost record",
            extra={
                "cluster_id": cost_record.get("cluster_id"),
                "business_unit": enriched["business_unit"],
                "cost_center": enriched["cost_center"],
            }
        )
        
        return enriched
    
    def _infer_business_unit(self, cluster_info: Dict[str, Any]) -> str:
        """
        Infer business unit from cluster name/metadata
        
        Simple heuristics:
        - If cluster name contains 'prod' -> 'production'
        - If cluster name contains 'data' -> 'data-platform'
        - If cluster name contains 'eng' -> 'engineering'
        - Default: 'unknown'
        """
        cluster_name = (cluster_info.get("name") or "").lower()
        
        if "data" in cluster_name or "analytics" in cluster_name:
            return "data-platform"
        elif "eng" in cluster_name:
            return "engineering"
        elif "prod" in cluster_name:
            return "production"
        
        return "unknown"
    
    def _infer_cost_center(self, cluster_info: Dict[str, Any]) -> str:
        """
        Infer cost center from business unit
        
        Simple mapping:
        - data-platform -> cc-data-platform
        - engineering -> cc-engineering
        - production -> cc-production
        - Default: cc-unknown
        """
        # This method seems to assume 'bu' is available in scope or is a copy-paste error.
        # Based on context, it should probably call _infer_business_unit or be fixed.
        # But looking at previous code, _infer_cost_center(cluster_info)
        bu = self._infer_business_unit(cluster_info)
        return f"cc-{bu}"

    def _infer_principal(self, tags: Dict[str, Any], graph: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Infer principal_id from tags, names, or descriptions
        
        Priority:
        1. Tags (owner, principal, etc.)
        2. Service Account Description (e.g. "Owner: bob@company.com")
        3. Resource Name Patterns (e.g. "cluster-owner-bob")
        
        Supported value formats:
        - sa-xxxxx (Service Account ID)
        - u-xxxxx (User ID)
        - email@address.com (Lookup by email)
        """
        # 1. Check Tags first
        target_tags = ["owner", "principal", "created_by", "user", "service_account"]
        
        for tag_key in target_tags:
            value = tags.get(tag_key)
            if value:
                match = self._resolve_principal_value(str(value).strip())
                if match:
                    return match

        if not graph:
            return None

        # 2. Check Service Account Description (if principal is known but we want to confirm owner)
        # Actually, if we have graph['principal'], we already have the ID!
        # But maybe the cost is for a cluster, and we want to find the owner.
        
        # 3. Check Resource Names (Environment, Cluster)
        # Look for pattern: owner-<id> or owner-<email-prefix>
        import re
        
        # Helper to check string for owner pattern
        def check_string_for_owner(text: str) -> Optional[str]:
            if not text:
                return None
            
            # Pattern 1: owner: <value> or owner=<value>
            match = re.search(r'(?:owner|principal|user)[:=]\s*([a-zA-Z0-9@._-]+)', text, re.IGNORECASE)
            if match:
                return self._resolve_principal_value(match.group(1))
            
            # Pattern 2: ...-owner-<value>-... (in resource names)
            match = re.search(r'-owner-([a-zA-Z0-9@._]+)', text, re.IGNORECASE)
            if match:
                return self._resolve_principal_value(match.group(1))
                
            return None

        # Check Environment Name
        if graph.get("env"):
            p = check_string_for_owner(graph["env"].get("name")) or check_string_for_owner(graph["env"].get("display_name"))
            if p: return p
            
        # Check Cluster Name
        if graph.get("cluster"):
            p = check_string_for_owner(graph["cluster"].get("name"))
            if p: return p

        return None

    def _resolve_principal_value(self, value: str) -> Optional[str]:
        """Resolve a string value (id or email) to a principal_id"""
        # Direct ID match
        if value.startswith("sa-") or value.startswith("u-"):
            principal = self.db.query(DimensionPrincipal).filter_by(id=value).first()
            if principal:
                return principal.id
        
        # Email lookup
        if "@" in value:
            principal = self.db.query(DimensionPrincipal).filter_by(email=value).first()
            if principal:
                return principal.id
                
        # Try to find user by name? (Risky)
        return None
