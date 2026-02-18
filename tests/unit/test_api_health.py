"""Unit tests for health endpoints"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health_check():
    """Test /healthz endpoint"""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["service"] == "confluent-billing-portal"


def test_version():
    """Test /version endpoint"""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "environment" in data
    assert data["version"] == "0.1.0"
