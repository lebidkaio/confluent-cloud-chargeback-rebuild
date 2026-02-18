"""Job scheduler using APScheduler"""
import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.common.config import get_settings
from src.common.logging import get_logger
from src.jobs.collector_job import run_billing_collection, run_core_objects_collection
from src.storage.database import get_db

logger = get_logger(__name__)
settings = get_settings()

# Global scheduler instance
scheduler = None


def _run_hourly_job():
    """Wrapper for hourly core objects collection job"""
    logger.info("Running hourly core objects collection job")
    
    try:
        db = next(get_db())
        result = run_core_objects_collection(db)
        logger.info(f"Hourly job completed: {result}")
    except Exception as e:
        logger.error(f"Hourly job failed: {e}")
    finally:
        db.close()


def _run_daily_job():
    """Wrapper for daily billing collection job"""
    logger.info("Running daily billing collection job")
    
    try:
        db = next(get_db())
        result = run_billing_collection(db)
        logger.info(f"Daily job completed: {result}")
    except Exception as e:
        logger.error(f"Daily job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    """
    Start the APScheduler background scheduler
    
    Schedules:
    - Hourly job: Top of every hour (collects core objects)
    - Daily job: 2 AM every day (collects previous day's billing data)
    """
    global scheduler
    
    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled in configuration")
        return
    
    if scheduler is not None:
        logger.warning("Scheduler already running")
        return
    
    logger.info("Starting job scheduler")
    
    scheduler = BackgroundScheduler()
    
    # Hourly job: collect core objects
    if settings.hourly_job_enabled:
        scheduler.add_job(

            func=_run_hourly_job,
            trigger=CronTrigger(minute=0),  # Top of every hour
            id="hourly_core_objects",
            name="Hourly Core Objects Collection",
            replace_existing=True,
        )
        logger.info("Scheduled hourly core objects collection (0 * * * *)")
    
    # Daily job: collect billing data
    if settings.daily_job_enabled:
        scheduler.add_job(
            func=_run_daily_job,
            trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
            id="daily_billing",
            name="Daily Billing Collection",
            replace_existing=True,
        )
        logger.info("Scheduled daily billing collection (0 2 * * *)")
    
    # Start scheduler
    scheduler.start()
    logger.info("Job scheduler started")
    
    # Shutdown hook
    atexit.register(lambda: shutdown_scheduler())


def shutdown_scheduler():
    """Stop the scheduler gracefully"""
    global scheduler
    
    if scheduler is not None:
        logger.info("Shutting down job scheduler")
        scheduler.shutdown()
        scheduler = None


def get_scheduler_status():
    """
    Get scheduler status and job information
    
    Returns:
        Dict with scheduler status and job details
    """
    if scheduler is None:
        return {
            "running": False,
            "jobs": [],
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    
    return {
        "running": True,
        "jobs": jobs,
    }
