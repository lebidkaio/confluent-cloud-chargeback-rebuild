"""Allocation rules engine for cost distribution"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.models import DimensionCluster, DimensionOrg

logger = get_logger(__name__)


class RuleType(str, Enum):
    """Types of allocation rules"""
    TAG = "tag"
    PRINCIPAL = "principal"
    HYBRID = "hybrid"


class AllocationStrategy(str, Enum):
    """Allocation strategies"""
    EVEN = "even"
    PROPORTIONAL = "proportional"
    WEIGHTED = "weighted"


@dataclass
class AllocationRule:
    """
    Allocation rule definition
    
    Rules determine how costs are allocated based on business logic
    """
    rule_id: str
    rule_type: RuleType
    priority: int
    conditions: Dict[str, Any]
    allocation_strategy: AllocationStrategy
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def matches(self, cost_record: Dict[str, Any], db: Session) -> bool:
        """
        Check if this rule matches the given cost record
        
        Args:
            cost_record: Cost record to check
            db: Database session for entity lookups
            
        Returns:
            True if rule matches, False otherwise
        """
        if not self.enabled:
            return False
        
        if self.rule_type == RuleType.TAG:
            return self._match_tag_conditions(cost_record, db)
        elif self.rule_type == RuleType.PRINCIPAL:
            return self._match_principal_conditions(cost_record, db)
        elif self.rule_type == RuleType.HYBRID:
            return (
                self._match_tag_conditions(cost_record, db) and
                self._match_principal_conditions(cost_record, db)
            )
        
        return False
    
    def _match_tag_conditions(self, cost_record: Dict[str, Any], db: Session) -> bool:
        """Match tag-based conditions"""
        cluster_id = cost_record.get("cluster_id")
        if not cluster_id:
            return False
        
        cluster = db.query(DimensionCluster).filter_by(id=cluster_id).first()
        if not cluster or not cluster.meta_data:
            return False
        
        # Check if cluster tags match rule conditions
        cluster_tags = cluster.meta_data.get("tags", {})
        required_tags = self.conditions.get("cluster_tags", {})
        
        for tag_key, tag_value in required_tags.items():
            if cluster_tags.get(tag_key) != tag_value:
                return False
        
        return True
    
    def _match_principal_conditions(self, cost_record: Dict[str, Any], db: Session) -> bool:
        """Match principal-based conditions"""
        principal_id = cost_record.get("principal_id")
        if not principal_id:
            return False
        
        required_principals = self.conditions.get("principals", [])
        if not required_principals:
            return True  # No specific principal required
        
        return principal_id in required_principals
    
    def apply(self, cost_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply rule to enrich cost record with metadata
        
        Args:
            cost_record: Cost record to enrich
            
        Returns:
            Enriched cost record
        """
        enriched = cost_record.copy()
        
        # Apply metadata from rule
        for key, value in self.metadata.items():
            if key not in enriched or enriched[key] is None:
                enriched[key] = value
        
        # Mark which rule was applied
        enriched["applied_rule_id"] = self.rule_id
        enriched["allocation_strategy"] = self.allocation_strategy.value
        
        return enriched


class AllocationRulesEngine:
    """
    Engine to manage and apply allocation rules
    
    Rules are evaluated by priority (higher = more important)
    """
    
    def __init__(self, db: Session):
        """
        Initialize allocation rules engine
        
        Args:
            db: Database session
        """
        self.db = db
        self.rules: List[AllocationRule] = []
    
    def add_rule(self, rule: AllocationRule):
        """Add a rule to the engine"""
        self.rules.append(rule)
        # Sort by priority (descending)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
        logger.info(f"Added rule {rule.rule_id} with priority {rule.priority}")
    
    def remove_rule(self, rule_id: str):
        """Remove a rule from the engine"""
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
        logger.info(f"Removed rule {rule_id}")
    
    def get_rule(self, rule_id: str) -> Optional[AllocationRule]:
        """Get a rule by ID"""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def find_matching_rule(self, cost_record: Dict[str, Any]) -> Optional[AllocationRule]:
        """
        Find the highest-priority matching rule for a cost record
        
        Args:
            cost_record: Cost record to match
            
        Returns:
            Matching rule or None
        """
        for rule in self.rules:
            if rule.matches(cost_record, self.db):
                logger.debug(f"Rule {rule.rule_id} matched cost record")
                return rule
        
        logger.debug("No matching rule found for cost record")
        return None
    
    def apply_rules(self, cost_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply rules to a batch of cost records
        
        Args:
            cost_records: List of cost records
            
        Returns:
            List of enriched cost records
        """
        enriched_records = []
        
        for record in cost_records:
            matching_rule = self.find_matching_rule(record)
            
            if matching_rule:
                enriched = matching_rule.apply(record)
                enriched_records.append(enriched)
            else:
                # No matching rule, use record as-is with default metadata
                enriched = self._apply_default_metadata(record)
                enriched_records.append(enriched)
        
        logger.info(f"Applied rules to {len(cost_records)} cost records")
        return enriched_records
    
    def _apply_default_metadata(self, cost_record: Dict[str, Any]) -> Dict[str, Any]:
        """Apply default metadata when no rule matches"""
        enriched = cost_record.copy()
        
        # Set defaults if not already present
        if not enriched.get("business_unit"):
            enriched["business_unit"] = "unknown"
        if not enriched.get("cost_center"):
            enriched["cost_center"] = "unallocated"
        if not enriched.get("product"):
            enriched["product"] = "unknown"
        
        enriched["applied_rule_id"] = None
        enriched["allocation_strategy"] = "default"
        
        return enriched
    
    def load_rules_from_config(self, rules_config: List[Dict[str, Any]]):
        """
        Load rules from configuration
        
        Args:
            rules_config: List of rule definitions
        """
        for rule_dict in rules_config:
            try:
                rule = AllocationRule(
                    rule_id=rule_dict["rule_id"],
                    rule_type=RuleType(rule_dict["rule_type"]),
                    priority=rule_dict["priority"],
                    conditions=rule_dict.get("conditions", {}),
                    allocation_strategy=AllocationStrategy(
                        rule_dict.get("allocation_strategy", "even")
                    ),
                    metadata=rule_dict.get("metadata", {}),
                    enabled=rule_dict.get("enabled", True),
                )
                self.add_rule(rule)
            except Exception as e:
                logger.error(f"Failed to load rule {rule_dict.get('rule_id')}: {e}")
        
        logger.info(f"Loaded {len(self.rules)} rules from configuration")


# Example default rules
DEFAULT_RULES = [
    {
        "rule_id": "data-platform-rule",
        "rule_type": "tag",
        "priority": 10,
        "conditions": {
            "cluster_tags": {
                "team": "data-platform"
            }
        },
        "allocation_strategy": "proportional",
        "metadata": {
            "business_unit": "data-platform",
            "cost_center": "cc-data-platform",
            "product": "analytics"
        }
    },
    {
        "rule_id": "engineering-rule",
        "rule_type": "tag",
        "priority": 9,
        "conditions": {
            "cluster_tags": {
                "team": "engineering"
            }
        },
        "allocation_strategy": "proportional",
        "metadata": {
            "business_unit": "engineering",
            "cost_center": "cc-engineering",
            "product": "platform"
        }
    },
    {
        "rule_id": "prod-rule",
        "rule_type": "tag",
        "priority": 8,
        "conditions": {
            "cluster_tags": {
                "env": "prod"
            }
        },
        "allocation_strategy": "proportional",
        "metadata": {
            "environment": "production"
        }
    }
]
