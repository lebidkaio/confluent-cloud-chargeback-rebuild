"""Repository pattern for data access"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.models import (
    AllocationRule,
    DimensionCluster,
    DimensionEnv,
    DimensionOrg,
    DimensionPrincipal,
    HourlyCostFact,
    HourlyCostFact,
    IngestionRun,
    IngestionStatus,
)

logger = get_logger(__name__)


class CostRepository:
    """Repository for cost-related operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_costs_aggregated(
        self,
        from_ts: datetime,
        to_ts: datetime,
        group_by: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated costs with optional grouping and filtering

        Args:
            from_ts: Start timestamp
            to_ts: End timestamp
            group_by: List of fields to group by (e.g., ['org_id', 'cluster_id'])
            filters: Dictionary of filters (e.g., {'org_id': 'org-123', 'business_unit': 'engineering'})
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of aggregated cost records
        """
        query = self.db.query(HourlyCostFact)

        # Apply time range filter
        query = query.filter(
            HourlyCostFact.timestamp >= from_ts, HourlyCostFact.timestamp < to_ts
        )

        # Apply additional filters
        if filters:
            for key, value in filters.items():
                if hasattr(HourlyCostFact, key):
                    query = query.filter(getattr(HourlyCostFact, key) == value)

        # Group by if specified
        if group_by:
            group_cols = [getattr(HourlyCostFact, col) for col in group_by if hasattr(HourlyCostFact, col)]
            query = query.with_entities(
                *group_cols, func.sum(HourlyCostFact.cost_usd).label("total_cost")
            )
            query = query.group_by(*group_cols)
        else:
            query = query.with_entities(
                HourlyCostFact.timestamp,
                HourlyCostFact.org_id,
                HourlyCostFact.cluster_id,
                HourlyCostFact.cost_usd,
            )

        # Apply pagination
        query = query.limit(limit).offset(offset)

        results = query.all()

        # Convert to dictionaries
        if group_by:
            return [
                {**{col: getattr(row, col) for col in group_by}, "total_cost": float(row.total_cost)}
                for row in results
            ]
        else:
            return [
                {
                    "timestamp": row.timestamp.isoformat(),
                    "org_id": row.org_id,
                    "cluster_id": row.cluster_id,
                    "cost_usd": float(row.cost_usd),
                }
                for row in results
            ]

    def insert_cost_facts(self, cost_records: List[Dict[str, Any]]) -> int:
        """
        Bulk insert hourly cost facts from normalized data

        Args:
            cost_records: List of normalized cost dictionaries

        Returns:
            Number of records saved
        """
        try:
            facts = [HourlyCostFact(**record) for record in cost_records]
            self.db.bulk_save_objects(facts)
            self.db.commit()
            logger.info(f"Inserted {len(facts)} hourly cost facts")
            return len(facts)
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to insert cost facts: {e}")
            raise

    def get_latest_hourly_costs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get latest hourly costs for metrics export

        Args:
            hours: Number of hours to look back (default 24)

        Returns:
            List of recent cost records
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        results = (
            self.db.query(HourlyCostFact)
            .filter(HourlyCostFact.timestamp >= cutoff_time)
            .all()
        )

        return [
            {
                "timestamp": row.timestamp.isoformat(),
                "org_id": row.org_id,
                "env_id": row.env_id,
                "cluster_id": row.cluster_id,
                "business_unit": row.business_unit,
                "product": row.product,
                "cost_center": row.cost_center,
                "cost_usd": float(row.cost_usd),
                "confidence": row.allocation_confidence,
            }
            for row in results
        ]


class DimensionRepository:
    """Repository for dimension operations"""

    def __init__(self, db: Session):
        self.db = db

    def get_dimensions(self, dimension_type: str) -> List[Dict[str, Any]]:
        """
        Get all dimensions of a specific type

        Args:
            dimension_type: Type of dimension ('orgs', 'envs', 'clusters', 'principals')

        Returns:
            List of dimension records
        """
        model_map = {
            "orgs": DimensionOrg,
            "envs": DimensionEnv,
            "clusters": DimensionCluster,
            "principals": DimensionPrincipal,
        }

        model = model_map.get(dimension_type)
        if not model:
            return []

        results = self.db.query(model).all()

        return [
            {
                "id": row.id,
                "name": row.name,
                "display_name": getattr(row, "display_name", None),
                "meta_data": getattr(row, "meta_data", {}),
            }
            for row in results
        ]

    def upsert_dimension(self, dimension_type: str, dimension_data: Dict[str, Any]) -> Any:
        """
        Insert or update a dimension

        Args:
            dimension_type: Type of dimension
            dimension_data: Dimension data

        Returns:
            Created or updated dimension instance
        """
        model_map = {
            "orgs": DimensionOrg,
            "envs": DimensionEnv,
            "clusters": DimensionCluster,
            "principals": DimensionPrincipal,
        }

        model = model_map.get(dimension_type)
        if not model:
            raise ValueError(f"Invalid dimension type: {dimension_type}")

        # Check if exists
        existing = self.db.query(model).filter_by(id=dimension_data["id"]).first()

        if existing:
            # Update
            for key, value in dimension_data.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            instance = existing
        else:
            # Insert
            instance = model(**dimension_data)
            self.db.add(instance)

        self.db.commit()
        return instance


class IngestionRepository:
    """Repository for ingestion run tracking"""

    def __init__(self, db: Session):
        self.db = db

    def create_ingestion_run(
        self,
        run_type: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionRun:
        """
        Create new ingestion run record

        Args:
            run_type: Type of ingestion ('billing', 'core_objects')
            period_start: Start of data period (default: now)
            period_end: End of data period (default: now)
            metadata: Optional metadata dict

        Returns:
            Created IngestionRun instance
        """
        now = datetime.utcnow()
        run = IngestionRun(
            run_type=run_type,
            status=IngestionStatus.running,
            period_start=period_start or now,
            period_end=period_end or now,
            started_at=now,
        )
        self.db.add(run)
        self.db.commit()
        logger.info(f"Created ingestion run {run.id} - {run_type}")
        return run

    def update_ingestion_run(
        self,
        run_id: str,
        status: str,
        records_processed: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> IngestionRun:
        """
        Update ingestion run status

        Args:
            run_id: Ingestion run ID
            status: New status ('running', 'completed', 'failed')
            records_processed: Number of records processed
            error_message: Error message if failed

        Returns:
            Updated IngestionRun instance
        """
        run = self.db.query(IngestionRun).filter_by(id=run_id).first()
        if not run:
            raise ValueError(f"Ingestion run not found: {run_id}")

        run.status = status
        if status in ("completed", "failed"):
            run.completed_at = datetime.utcnow()
        if records_processed is not None:
            run.records_processed = records_processed
        if error_message:
            run.error_message = error_message

        self.db.commit()
        logger.info(f"Updated ingestion run {run_id}: {status}")
        return run

    def get_ingestion_run_status(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get ingestion run status

        Args:
            run_id: Ingestion run ID

        Returns:
            Run status dict or None if not found
        """
        run = self.db.query(IngestionRun).filter_by(id=run_id).first()
        if not run:
            return None

        return {
            "id": run.id,
            "run_type": run.run_type,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "records_processed": run.records_processed,
            "error_message": run.error_message,
        }
