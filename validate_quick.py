"""Quick API validation - run inside container"""
import os
import requests
from requests.auth import HTTPBasicAuth

# Get credentials from environment
api_key = os.getenv("CONFLUENT_API_KEY")
api_secret = os.getenv("CONFLUENT_API_SECRET")
base_url = os.getenv("CONFLUENT_CLOUD_URL", "https://api.confluent.cloud")

print("=" * 60)
print("CONFLUENT CLOUD API VALIDATION")
print("=" * 60)

# Check config
print("\n1. Configuration:")
if not api_key or not api_secret:
    print("[FAIL] CONFLUENT_API_KEY or CONFLUENT_API_SECRET not set")
    print("       Configure them in your .env file")
    exit(1)
else:
    print(f"[OK] API Key: {api_key[:8]}***")
    print(f"[OK] API Secret: ***{api_secret[-4:]}")

# Test Billing API
print("\n2. Testing Billing API...")
try:
    url = f"{base_url}/billing/v1/costs"
    r = requests.get(url, auth=HTTPBasicAuth(api_key, api_secret), timeout=10)
    if r.status_code == 200:
        data = r.json()
        print(f"[OK] Billing API working! Found {len(data.get('data', []))} records")
    elif r.status_code == 401:
        print("[FAIL] Authentication failed (401) - Check credentials")
    elif r.status_code == 403:
        print("[FAIL] Access denied (403) - API Key needs BillingAdmin permission")
    else:
        print(f"[WARN] Status {r.status_code}: {r.text[:100]}")
except Exception as e:
    print(f"[FAIL] Error: {e}")

# Test Organizations API
print("\n3. Testing Organizations API...")
try:
    url = f"{base_url}/org/v2/organizations"
    r = requests.get(url, auth=HTTPBasicAuth(api_key, api_secret), timeout=10)
    if r.status_code == 200:
        orgs = r.json().get('data', [])
        print(f"[OK] Organizations API working! Found {len(orgs)} org(s)")
        if orgs:
            print(f"   > {orgs[0].get('id')}: {orgs[0].get('display_name', 'N/A')}")
    else:
        print(f"[WARN] Status {r.status_code}: {r.text[:100]}")
except Exception as e:
    print(f"[FAIL] Error: {e}")

# Test Metrics API
print("\n4. Testing Metrics API...")
try:
    url = f"{base_url}/v2/metrics/cloud/descriptors"
    r = requests.get(url, auth=HTTPBasicAuth(api_key, api_secret), timeout=10)
    if r.status_code == 200:
        metrics = r.json().get('data', [])
        print(f"[OK] Metrics API working! {len(metrics)} metrics available")
    else:
        print(f"[WARN] Status {r.status_code}: {r.text[:100]}")
except Exception as e:
    print(f"[FAIL] Error: {e}")

print("\n" + "=" * 60)
print("[OK] Validation complete!")
print("=" * 60)
