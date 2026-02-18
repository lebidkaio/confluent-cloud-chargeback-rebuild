"""Test configuration and fixtures"""
import pytest


@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture"""
    return {
        "database_url": "postgresql://billing_user:billing_password@localhost:5432/billing_db_test",
        "log_level": "DEBUG",
    }
