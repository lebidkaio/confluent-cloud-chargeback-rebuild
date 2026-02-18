#!/usr/bin/env python3
"""
Manual data collection trigger script

Usage:
    python scripts/trigger_collection.py --core-objects
    python scripts/trigger_collection.py --billing --days 15
    python scripts/trigger_collection.py --all
"""
import argparse
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import time

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.common.config import get_settings
from src.jobs.collector_job import (
    run_billing_collection,
    run_core_objects_collection,
)


def get_db_session():
    """Create database session"""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def collect_core_objects():
    """Collect core objects (orgs, envs, clusters, principals)"""
    print("Collecting core objects...")
    db = get_db_session()
    try:
        result = run_core_objects_collection(db)
        if result.get("status") == "success":
            print(f"Core objects collected successfully: {result.get('statistics')}")
        else:
            print(f"Core objects collection failed: {result.get('error')}")
    except Exception as e:
        print(f"Failed to collect core objects: {e}")
        raise
    finally:
        db.close()


def collect_billing(days: int = 30):
    """Collect billing data for last N days"""
    print(f"Collecting billing data for last {days} days...")
    db = get_db_session()
    try:
        today = datetime.utcnow().date()
        
        for i in range(days):
            target_date = today - timedelta(days=i+1)
            print(f"   Processing {target_date}...")
            time.sleep(5) # Rate limit protection
            
            result = run_billing_collection(db, target_date)
            
            if result.get("status") == "success":
                records = result.get("hourly_records", 0)
                print(f"   {target_date}: {records} records")
            else:
                print(f"   {target_date}: Failed - {result.get('error')}")
                
    except Exception as e:
        print(f"Failed to collect billing data: {e}")
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Trigger data collection manually")
    parser.add_argument(
        "--core-objects",
        action="store_true",
        help="Collect core objects (orgs, envs, clusters, principals)"
    )
    parser.add_argument(
        "--billing",
        action="store_true",
        help="Collect billing data"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to collect billing data (default: 15)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Collect everything (core objects + billing)"
    )
    
    args = parser.parse_args()
    
    if args.all:
        args.core_objects = True
        args.billing = True
    
    if not (args.core_objects or args.billing):
        parser.print_help()
        return
    
    # Collect core objects first (they're needed for correlation)
    if args.core_objects:
        collect_core_objects()
    
    # Then collect billing
    if args.billing:
        collect_billing(args.days)
    
    print("\nData collection complete!")


if __name__ == "__main__":
    main()
