-- Migration: Add source_api_version and raw_api_response to hourly_cost_facts
-- Version: 002
-- Description: Extend hourly_cost_facts table for Milestone B real data collection

-- Add new columns for API integration tracking
ALTER TABLE hourly_cost_facts ADD COLUMN IF NOT EXISTS source_api_version VARCHAR(20);
ALTER TABLE hourly_cost_facts ADD COLUMN IF NOT EXISTS raw_api_response JSONB;

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_cost_facts_timestamp ON hourly_cost_facts(timestamp_hour);
CREATE INDEX IF NOT EXISTS idx_cost_facts_org_cluster ON hourly_cost_facts(org_id, cluster_id);
CREATE INDEX IF NOT EXISTS idx_cost_facts_business_unit ON hourly_cost_facts(business_unit);
CREATE INDEX IF NOT EXISTS idx_cost_facts_product ON hourly_cost_facts(product);

-- Add indexes on dimension tables
CREATE INDEX IF NOT EXISTS idx_dims_orgs_name ON dimensions_orgs(name);
CREATE INDEX IF NOT EXISTS idx_dims_clusters_org ON dimensions_clusters(org_id);
CREATE INDEX IF NOT EXISTS idx_dims_clusters_env ON dimensions_clusters(env_id);
CREATE INDEX IF NOT EXISTS idx_dims_envs_org ON dimensions_envs(org_id);
CREATE INDEX IF NOT EXISTS idx_dims_principals_org ON dimensions_principals(org_id);

-- Add check constraint for allocation_confidence
ALTER TABLE hourly_cost_facts 
DROP CONSTRAINT IF EXISTS check_allocation_confidence;

ALTER TABLE hourly_cost_facts
ADD CONSTRAINT check_allocation_confidence 
CHECK (allocation_confidence IN ('low', 'medium', 'high'));

COMMENT ON TABLE hourly_cost_facts IS 'Hourly cost facts with real data from Confluent Cloud Billing API';
COMMENT ON COLUMN hourly_cost_facts.source_api_version IS 'Version of the Billing API that provided this data';
COMMENT ON COLUMN hourly_cost_facts.raw_api_response IS 'Raw JSON response from API for debugging';
COMMENT ON COLUMN hourly_cost_facts.allocation_confidence IS 'Confidence level of the hourly allocation: low (no metrics), medium (even split), high (metrics-based)';
