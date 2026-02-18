"""Collector jobs - orchestrate data collection workflows"""
from datetime import date, datetime, timedelta
from typing import Any, Dict

from sqlalchemy.orm import Session

from src.collector.billing_api import BillingAPIClient
from src.collector.core_objects_api import CoreObjectsAPIClient
from src.common.logging import get_logger
from src.enricher.normalizer import (
    allocate_daily_to_hourly,
    normalize_billing_data,
    normalize_cluster,
    normalize_environment,
    normalize_organization,
    normalize_principal,
)
from src.storage.models import IngestionStatus
from src.storage.database import get_db
from src.storage.repository import (
    CostRepository,
    DimensionRepository,
    IngestionRepository,
)

logger = get_logger(__name__)


def run_core_objects_collection(db: Session) -> Dict[str, Any]:
    """
    Run core objects collection job
    
    Fetches organizations, environments, clusters, and service accounts
    from Confluent Cloud API and persists to database.
    
    Args:
        db: Database session
        
    Returns:
        Job result with statistics
    """
    logger.info("Starting core objects collection")
    
    dim_repo = DimensionRepository(db)
    ing_repo = IngestionRepository(db)
    
    # Create ingestion run
    # Create ingestion run
    now = datetime.utcnow()
    run = ing_repo.create_ingestion_run(
        run_type="core_objects",
        period_start=now,
        period_end=now,
    )
    
    try:
        # Initialize API client
        client = CoreObjectsAPIClient()
        
        # Fetch all core objects
        logger.info("Fetching core objects from API")
        core_objects = client.get_all_core_objects()
        
        stats = {
            "organizations": 0,
            "environments": 0,
            "clusters": 0,
            "service_accounts": 0,
        }
        
        # Process organizations
        for org_data in core_objects.get("organizations", []):
            normalized = normalize_organization(org_data)
            dim_repo.upsert_dimension("orgs", normalized)
            stats["organizations"] += 1
        
        # Process environments
        for env_data in core_objects.get("environments", []):
            normalized = normalize_environment(env_data)
            dim_repo.upsert_dimension("envs", normalized)
            stats["environments"] += 1
        
        # Process clusters
        for cluster_data in core_objects.get("clusters", []):
            normalized = normalize_cluster(cluster_data)
            dim_repo.upsert_dimension("clusters", normalized)
            stats["clusters"] += 1
        
        # Process service accounts
        for principal_data in core_objects.get("service_accounts", []):
            normalized = normalize_principal(principal_data)
            dim_repo.upsert_dimension("principals", normalized)
            stats["service_accounts"] += 1
        
        total_records = sum(stats.values())
        
        # Update ingestion run
        ing_repo.update_ingestion_run(
            run_id=run.id,
            status="completed",
            records_processed=total_records,
        )
        
        logger.info(f"Core objects collection completed: {stats}")
        
        return {
            "status": "success",
            "run_id": run.id,
            "statistics": stats,
            "total_records": total_records,
        }
        
    except Exception as e:
        logger.error(f"Core objects collection failed: {e}")
        ing_repo.update_ingestion_run(
            run_id=run.id,
            status="failed",
            error_message=str(e),
        )
        
        return {
            "status": "failed",
            "run_id": run.id,
            "error": str(e),
        }


def run_billing_collection(db: Session, target_date: date = None) -> Dict[str, Any]:
    """
    Run billing data collection job
    
    Fetches billing data for target date, normalizes to hourly costs,
    and persists to database.
    
    Args:
        db: Database session
        target_date: Date to collect (defaults to yesterday)
        
    Returns:
        Job result with statistics
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)
    
    logger.info(f"Starting billing collection for {target_date}")
    
    cost_repo = CostRepository(db)
    ing_repo = IngestionRepository(db)
    dim_repo = DimensionRepository(db)
    
    # Create ingestion run
    # Create ingestion run
    period_start = datetime.combine(target_date, datetime.min.time())
    period_end = period_start + timedelta(days=1) - timedelta(microseconds=1)
    
    run = ing_repo.create_ingestion_run(
        run_type="billing",
        period_start=period_start,
        period_end=period_end,
        metadata={"target_date": target_date.isoformat()},
    )
    
    try:
        # Initialize API client
        client = BillingAPIClient()
        
        # Fetch costs for target date
        # API requires start_date < end_date, so we use next day as end
        request_end_date = target_date + timedelta(days=1)
        logger.info(f"Fetching costs from API for {target_date} to {request_end_date}")
        raw_costs = client.get_costs(target_date, request_end_date)
        
        if not raw_costs:
            logger.warning(f"No costs found for {target_date}")
            ing_repo.update_ingestion_run(
                run_id=run.id,
                status=IngestionStatus.completed,
                records_processed=0,
            )
            return {
                "status": "success",
                "run_id": run.id,
                "message": "No costs to process",
                "total_records": 0,
            }
        
        # Normalize billing data
        logger.info(f"Normalizing {len(raw_costs)} cost records")
        print(f"DEBUG: Raw costs count: {len(raw_costs)}")
        normalized_costs = normalize_billing_data(raw_costs)
        print(f"DEBUG: Normalized costs count: {len(normalized_costs)}")
        if len(normalized_costs) > 0:
             print(f"DEBUG: Sample normalized: {normalized_costs[0]}")
        
        # Allocate daily to hourly
        hourly_costs = []
        for daily_cost in normalized_costs:
            try:
                hourly_records = allocate_daily_to_hourly(daily_cost)
                hourly_costs.extend(hourly_records)
            except Exception as e:
                print(f"DEBUG: Allocation failed for {daily_cost}: {e}")
                logger.error(f"Allocation failed: {e}")
        
        print(f"DEBUG: Hourly costs count: {len(hourly_costs)}")

        # Resolve org_id and ensure FK dimension entries exist
        from src.storage.models import DimensionEnv, DimensionCluster, DimensionOrg
        
        # Build env→org lookup
        env_org_map = {}
        envs = db.query(DimensionEnv.id, DimensionEnv.org_id).all()
        for env in envs:
            env_org_map[env.id] = env.org_id
        
        # Get fallback org_id (first org in DB)
        default_org = db.query(DimensionOrg.id).first()
        fallback_org_id = default_org.id if default_org else None
        
        # Get known cluster ids
        known_clusters = set(r.id for r in db.query(DimensionCluster.id).all())
        known_envs = set(env_org_map.keys())
        
        valid_records = []
        for record in hourly_costs:
            # Resolve org_id
            if not record.get("org_id") and record.get("env_id"):
                record["org_id"] = env_org_map.get(record["env_id"])
            if not record.get("org_id"):
                record["org_id"] = fallback_org_id
            
            # Skip if still no org_id
            if not record.get("org_id"):
                logger.warning(f"Skipping record: no org_id resolvable")
                continue
            
            # Create placeholder env if needed
            env_id = record.get("env_id")
            if env_id and env_id not in known_envs:
                dim_repo.upsert_dimension("envs", {
                    "id": env_id,
                    "org_id": record["org_id"],
                    "name": env_id,
                })
                known_envs.add(env_id)
                env_org_map[env_id] = record["org_id"]
            
            # Create placeholder cluster if needed
            cluster_id = record.get("cluster_id")
            if cluster_id and cluster_id not in known_clusters:
                dim_repo.upsert_dimension("clusters", {
                    "id": cluster_id,
                    "org_id": record["org_id"],
                    "env_id": env_id or "unknown",
                    "name": cluster_id,
                })
                known_clusters.add(cluster_id)
            
            valid_records.append(record)
        
        logger.info(f"Valid records: {len(valid_records)}/{len(hourly_costs)}")

        # Persist hourly costs
        logger.info(f"Persisting {len(valid_records)} hourly cost records")
        saved_count = cost_repo.insert_cost_facts(valid_records)
        
        # Update ingestion run
        ing_repo.update_ingestion_run(
            run_id=run.id,
            status="completed",
            records_processed=saved_count,
        )
        
        logger.info(
            f"Billing collection completed: {len(raw_costs)} daily → {saved_count} hourly"
        )
        
        return {
            "status": "success",
            "run_id": run.id,
            "target_date": target_date.isoformat(),
            "daily_records": len(raw_costs),
            "hourly_records": saved_count,
        }
        
    except Exception as e:
        logger.error(f"Billing collection failed: {e}")
        ing_repo.update_ingestion_run(
            run_id=run.id,
            status="failed",
            error_message=str(e),
        )
        
        return {
            "status": "failed",
            "run_id": run.id,
            "error": str(e),
        }
