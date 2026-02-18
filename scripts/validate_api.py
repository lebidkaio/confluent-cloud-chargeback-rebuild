#!/usr/bin/env python3
"""
Diagnostic script to validate Confluent Cloud API connection and metrics

Usage:
    python scripts/validate_api.py
"""
import os
import sys
from pathlib import Path
import requests
from requests.auth import HTTPBasicAuth

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.common.config import get_settings


def check_config():
    """Check if required environment variables are set"""
    print("=" * 60)
    print("1. CHECKING CONFIGURATION")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        # Check API credentials
        if not settings.confluent_api_key:
            print("CONFLUENT_API_KEY not set")
            return False
        else:
            print(f"CONFLUENT_API_KEY: {settings.confluent_api_key[:8]}***")
        
        if not settings.confluent_api_secret:
            print("CONFLUENT_API_SECRET not set")
            return False
        else:
            print(f"CONFLUENT_API_SECRET: ***{settings.confluent_api_secret[-8:]}")
        
        print(f"CONFLUENT_CLOUD_URL: {settings.confluent_cloud_url}")
        print(f"DATABASE_URL: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'configured'}")
        
        return True
    except Exception as e:
        print(f"Configuration error: {e}")
        return False


def test_billing_api():
    """Test Billing API connection"""
    print("\n" + "=" * 60)
    print("2. TESTING BILLING API")
    print("=" * 60)
    
    try:
        settings = get_settings()
        url = f"{settings.confluent_cloud_url}/billing/v1/costs"
        
        print(f"Requesting: {url}")
        response = requests.get(
            url,
            auth=HTTPBasicAuth(settings.confluent_api_key, settings.confluent_api_secret),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Billing API connected successfully")
            print(f"   Response contains {len(data.get('data', []))} cost records")
            return True
        elif response.status_code == 401:
            print(f"Authentication failed (401)")
            print(f"   Check your API Key and Secret")
            return False
        elif response.status_code == 403:
            print(f"Access forbidden (403)")
            print(f"   Your API Key may not have BillingAdmin permissions")
            return False
        else:
            print(f"Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"Billing API test failed: {e}")
        return False


def test_core_objects_api():
    """Test Core Objects API connection"""
    print("\n" + "=" * 60)
    print("3. TESTING CORE OBJECTS API")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        # Test organizations endpoint
        url = f"{settings.confluent_cloud_url}/org/v2/organizations"
        print(f"Requesting: {url}")
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(settings.confluent_api_key, settings.confluent_api_secret),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            orgs = data.get('data', [])
            print(f"Core Objects API connected successfully")
            print(f"   Found {len(orgs)} organization(s)")
            
            if orgs:
                print(f"   First org: {orgs[0].get('id')} - {orgs[0].get('display_name', 'N/A')}")
            
            return True
        else:
            print(f"Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"Core Objects API test failed: {e}")
        return False


def test_metrics_api():
    """Test Metrics API connection"""
    print("\n" + "=" * 60)
    print("4. TESTING METRICS API")
    print("=" * 60)
    
    try:
        settings = get_settings()
        
        # Test metrics query endpoint (generic test)
        url = f"{settings.confluent_cloud_url}/v2/metrics/cloud/descriptors"
        print(f"Requesting: {url}")
        
        response = requests.get(
            url,
            auth=HTTPBasicAuth(settings.confluent_api_key, settings.confluent_api_secret),
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Metrics API connected successfully")
            print(f"   Available metrics: {len(data.get('data', []))}")
            return True
        else:
            print(f"Request failed with status {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"Metrics API test failed: {e}")
        return False


def check_portal_health():
    """Check if the portal is running"""
    print("\n" + "=" * 60)
    print("5. CHECKING PORTAL HEALTH")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:8000/healthz", timeout=5)
        if response.status_code == 200:
            print("Portal API is running")
            return True
        else:
            print(f"Portal API returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("Portal API is not reachable")
        print("   Make sure Docker Compose is running:")
        print("   cd docker && docker-compose up -d")
        return False
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def check_prometheus_metrics():
    """Check if Prometheus is receiving metrics"""
    print("\n" + "=" * 60)
    print("6. CHECKING PROMETHEUS METRICS")
    print("=" * 60)
    
    try:
        # Check if Prometheus is up
        response = requests.get("http://localhost:9090/-/healthy", timeout=5)
        if response.status_code != 200:
            print("Prometheus is not healthy")
            return False
        
        print("Prometheus is running")
        
        # Query for cost metrics
        query_url = "http://localhost:9090/api/v1/query"
        query = "ccloud_cost_usd_hourly"
        
        response = requests.get(
            query_url,
            params={"query": query},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            result = data.get('data', {}).get('result', [])
            
            if result:
                print(f"Found {len(result)} cost metric series")
                print(f"   Example metric: {result[0].get('metric', {})}")
                return True
            else:
                print("No cost metrics found yet")
                print("   This is normal if data collection hasn't run")
                print("   Run: docker exec -it billing-app python scripts/trigger_collection.py --all")
                return False
        else:
            print(f"Prometheus query failed with status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("Prometheus is not reachable")
        return False
    except Exception as e:
        print(f"Prometheus check failed: {e}")
        return False


def main():
    print("\nCONFLUENT BILLING PORTAL - API VALIDATION")
    print("=" * 60)
    
    results = {
        "config": check_config(),
        "billing_api": test_billing_api(),
        "core_objects_api": test_core_objects_api(),
        "metrics_api": test_metrics_api(),
        "portal_health": check_portal_health(),
        "prometheus_metrics": check_prometheus_metrics(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for check, status in results.items():
        icon = "" if status else ""
        print(f"{icon} {check.replace('_', ' ').title()}")
    
    print(f"\nPassed: {passed}/{total}")
    
    # Recommendations
    print("\n" + "=" * 60)
    print("RECOMMENDATIONS")
    print("=" * 60)
    
    if not results["config"]:
        print("1. Set up your .env file with Confluent Cloud credentials")
        print("   cp .env.example .env")
        print("   Edit .env and add CONFLUENT_API_KEY and CONFLUENT_API_SECRET")
    
    if not results["billing_api"]:
        print("2. Verify your API Key has BillingAdmin permissions")
        print("   https://confluent.cloud → Administration → Cloud API keys")
    
    if not results["portal_health"]:
        print("3. Start the Docker Compose stack:")
        print("   cd docker && docker-compose up -d")
    
    if not results["prometheus_metrics"]:
        print("4. Collect data to populate metrics:")
        print("   docker exec -it billing-app python scripts/trigger_collection.py --all")
    
    if all(results.values()):
        print("Everything is working correctly!")
        print("\nNext steps:")
        print("- View dashboards: http://localhost:3000 (admin/admin)")
        print("- Query API: http://localhost:8000/docs")
        print("- Check Prometheus: http://localhost:9090")
    
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
