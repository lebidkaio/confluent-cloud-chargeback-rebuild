"""Collection trigger API endpoints"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.common.logging import get_logger
from src.storage.database import get_db
from src.jobs.collector_job import (
    run_billing_collection,
    run_core_objects_collection,
    run_catalog_tags_collection,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/collect", tags=["collection"])


@router.post("/billing")
async def trigger_billing_collection(db: Session = Depends(get_db)):
    """
    Trigger billing data collection from Confluent Cloud API.
    Fetches daily costs and allocates to hourly records.
    """
    logger.info("API trigger: billing collection")
    result = run_billing_collection(db)

    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result)

    return result


@router.post("/core-objects")
async def trigger_core_objects_collection(db: Session = Depends(get_db)):
    """
    Trigger core objects collection from Confluent Cloud API.
    Fetches organizations, environments, clusters, and service accounts.
    """
    logger.info("API trigger: core objects collection")
    result = run_core_objects_collection(db)

    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result)

    return result


@router.post("/catalog-tags")
async def trigger_catalog_tags_collection(db: Session = Depends(get_db)):
    """
    Trigger entity tag collection from Stream Governance Catalog API.
    Fetches tags for all known clusters and stores in dimension metadata.
    Requires SCHEMA_REGISTRY_URL, SCHEMA_REGISTRY_API_KEY, SCHEMA_REGISTRY_API_SECRET.
    """
    logger.info("API trigger: catalog tags collection")
    result = run_catalog_tags_collection(db)

    if result.get("status") == "failed":
        raise HTTPException(status_code=500, detail=result)

    return result


@router.post("/full")
async def trigger_full_collection(db: Session = Depends(get_db)):
    """
    Trigger full collection pipeline:
    1. Core objects (orgs, envs, clusters, service accounts)
    2. Catalog tags (if configured)
    3. Billing data (with enrichment from tags)
    """
    logger.info("API trigger: full collection pipeline")
    results = {}

    # Step 1: Core objects
    results["core_objects"] = run_core_objects_collection(db)

    # Step 2: Catalog tags (optional, won't fail if not configured)
    results["catalog_tags"] = run_catalog_tags_collection(db)

    # Step 3: Billing
    results["billing"] = run_billing_collection(db)

    # Determine overall status
    statuses = [r.get("status") for r in results.values()]
    overall = "success" if "failed" not in statuses else "partial"

    return {
        "status": overall,
        "steps": results,
    }
