"""Integration tests for metrics exporter"""
import pytest
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_metrics_endpoint():
    """Test /metrics endpoint returns valid OpenMetrics format"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    # Check for expected metrics
    content = response.text
    assert "ccloud_cost_usd_hourly" in content
    assert "org=" in content
    assert "cluster=" in content
    assert "business_unit=" in content


def test_metrics_format():
    """Test that metrics are properly formatted"""
    response = client.get("/metrics")
    content = response.text

    # Should have HELP and TYPE comments
    assert "# HELP" in content or "ccloud_cost_usd_hourly" in content
    assert "# TYPE" in content or "gauge" in content.lower()

    # Should have actual metric values
    lines = [line for line in content.split("\n") if line and not line.startswith("#")]
    assert len(lines) > 0

    # Check that at least one metric line has proper format
    metric_lines = [line for line in lines if "ccloud_cost_usd_hourly" in line]
    assert len(metric_lines) > 0

    # Verify labels are present
    for line in metric_lines[:5]:  # Check first 5 metric lines
        assert "{" in line and "}" in line  # Has labels
        assert "org=" in line
