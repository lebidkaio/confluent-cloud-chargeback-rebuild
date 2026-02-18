"""Smoke tests - verify service starts and all endpoints respond"""
import time

import pytest
import requests
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_service_starts():
    """Verify service starts successfully"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "confluent-billing-portal"
    assert "version" in data


def test_all_endpoints_respond():
    """Smoke test: verify all main endpoints respond"""
    endpoints = [
        "/healthz",
        "/readyz",
        "/version",
        "/v1/costs?from_ts=2024-01-01T00:00:00Z&to_ts=2024-01-31T23:59:59Z",
        "/v1/dimensions?dimension_type=orgs",
        "/metrics",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        assert response.status_code == 200, f"Endpoint {endpoint} failed with {response.status_code}"


def test_api_docs_available():
    """Verify API documentation is accessible"""
    response = client.get("/docs")
    assert response.status_code == 200

    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "info" in data
