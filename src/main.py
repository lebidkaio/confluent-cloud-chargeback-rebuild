"""Main FastAPI application"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import collect, costs, dimensions, health
from src.common.config import get_settings
from src.common.logging import get_logger, setup_logging
from src.exporter import metrics
from src.storage.database import check_db_connection, init_db
from src.jobs.scheduler import start_scheduler, shutdown_scheduler

# Setup logging
setup_logging()
logger = get_logger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup and shutdown
    """
    # Startup
    logger.info(f"Starting {settings.service_name} v{settings.service_version}")
    logger.info(f"Environment: {settings.environment}")

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't fail startup in MVP, just log the error

    # Check database connection
    if check_db_connection():
        logger.info("Database connection verified")
    else:
        logger.warning("Database connection check failed")
    
    # Start scheduler
    try:
        start_scheduler()
        logger.info("Job scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")

    yield

    # Shutdown
    logger.info(f"Shutting down {settings.service_name}")
    shutdown_scheduler()


# Create FastAPI app
app = FastAPI(
    title="Confluent Billing Portal",
    description="Chargeback/Showback platform for Confluent Cloud",
    version=settings.service_version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(costs.router)
app.include_router(dimensions.router)
app.include_router(collect.router)
app.include_router(metrics.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "docs": "/docs",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
    )
