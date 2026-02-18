"""SQLAlchemy models for the billing portal"""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.storage.database import Base


class ConfidenceLevel(str, PyEnum):
    """Allocation confidence levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# Alias for backward compatibility/clarity
AllocationConfidence = ConfidenceLevel


class IngestionStatus(str, PyEnum):
    """Status of ingestion runs"""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class DimensionOrg(Base):
    """Confluent Cloud Organization dimension"""

    __tablename__ = "dimensions_orgs"

    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    meta_data = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    environments = relationship("DimensionEnv", back_populates="organization")
    clusters = relationship("DimensionCluster", back_populates="organization")
    principals = relationship("DimensionPrincipal", back_populates="organization")


class DimensionEnv(Base):
    """Confluent Cloud Environment dimension"""

    __tablename__ = "dimensions_envs"

    id = Column(String(100), primary_key=True)
    org_id = Column(String(100), ForeignKey("dimensions_orgs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    display_name = Column(String(255))
    meta_data = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("DimensionOrg", back_populates="environments")
    clusters = relationship("DimensionCluster", back_populates="environment")


class DimensionCluster(Base):
    """Kafka Cluster dimension"""

    __tablename__ = "dimensions_clusters"

    id = Column(String(100), primary_key=True)
    org_id = Column(String(100), ForeignKey("dimensions_orgs.id"), nullable=False)
    env_id = Column(String(100), ForeignKey("dimensions_envs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    cluster_type = Column(String(50))  # 'basic', 'standard', 'dedicated'
    cloud_provider = Column(String(50))  # 'aws', 'gcp', 'azure'
    region = Column(String(100))
    meta_data = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("DimensionOrg", back_populates="clusters")
    environment = relationship("DimensionEnv", back_populates="clusters")


class DimensionPrincipal(Base):
    """Principal (Service Account or User) dimension"""

    __tablename__ = "dimensions_principals"

    id = Column(String(100), primary_key=True)
    org_id = Column(String(100), ForeignKey("dimensions_orgs.id"), nullable=False)
    principal_type = Column(String(50), nullable=False)  # 'service_account' or 'user'
    name = Column(String(255), nullable=False)
    email = Column(String(255))
    meta_data = Column("metadata", JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("DimensionOrg", back_populates="principals")


class HourlyCostFact(Base):
    """Main fact table for hourly cost allocations"""

    __tablename__ = "hourly_cost_facts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    org_id = Column(String(100), ForeignKey("dimensions_orgs.id"), nullable=False, index=True)
    env_id = Column(String(100), ForeignKey("dimensions_envs.id"))
    cluster_id = Column(String(100), ForeignKey("dimensions_clusters.id"), index=True)
    principal_id = Column(String(100), ForeignKey("dimensions_principals.id"), index=True)

    # Cost data
    cost_usd = Column(Numeric(12, 4), nullable=False)
    cost_source = Column(String(50), nullable=False)  # 'billing_api', 'estimated', etc.

    # Business metadata for allocation
    business_unit = Column(String(100), index=True)
    product = Column(String(100), index=True)
    cost_center = Column(String(100))
    team = Column(String(100))
    tags = Column(JSON, default={})

    # Quality indicators
    allocation_confidence = Column(
        Enum(ConfidenceLevel, values_callable=lambda e: [x.value for x in e]),
        nullable=False, default=ConfidenceLevel.MEDIUM
    )
    allocation_method = Column(String(100))  # 'proportional', 'usage_based', 'manual'

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique constraint
    __table_args__ = (
        UniqueConstraint(
            "timestamp", "org_id", "env_id", "cluster_id", "principal_id", name="unique_hourly_cost"
        ),
    )


class AllocationRule(Base):
    """Business rules for cost allocation"""

    __tablename__ = "allocation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(255), nullable=False, unique=True)
    rule_type = Column(String(50), nullable=False)  # 'proportional', 'fixed', 'usage_based'
    priority = Column(Integer, nullable=False, default=100)

    # Rule conditions and actions (JSONB for flexibility)
    conditions = Column(JSON, nullable=False)
    allocation_weights = Column(JSON)
    meta_data = Column(JSON, default={})

    # Status
    is_active = Column(Boolean, default=True)
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IngestionRun(Base):
    """Audit log for ETL job executions"""

    __tablename__ = "ingestion_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_type = Column(String(50), nullable=False)  # 'hourly', 'daily', 'backfill'
    status = Column(Enum(IngestionStatus), nullable=False, default=IngestionStatus.pending)

    # Time range processed
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Execution tracking
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    # Metrics
    records_processed = Column(Integer, default=0)
    records_inserted = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)

    # Error tracking
    error_message = Column(Text)
    error_details = Column(JSON)

    created_at = Column(DateTime, default=datetime.utcnow)
