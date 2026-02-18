-- Initial database schema for Confluent Billing Portal
-- Version: 001
-- Description: Core tables for cost facts, dimensions, and allocation rules

-- Enums
CREATE TYPE confidence_level AS ENUM ('low', 'medium', 'high');
CREATE TYPE ingestion_status AS ENUM ('pending', 'running', 'completed', 'failed');

-- Dimension: Organizations
CREATE TABLE dimensions_orgs (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dimension: Environments
CREATE TABLE dimensions_envs (
    id VARCHAR(100) PRIMARY KEY,
    org_id VARCHAR(100) NOT NULL REFERENCES dimensions_orgs(id),
    name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dimension: Clusters
CREATE TABLE dimensions_clusters (
    id VARCHAR(100) PRIMARY KEY,
    org_id VARCHAR(100) NOT NULL REFERENCES dimensions_orgs(id),
    env_id VARCHAR(100) NOT NULL REFERENCES dimensions_envs(id),
    name VARCHAR(255) NOT NULL,
    cluster_type VARCHAR(50),
    cloud_provider VARCHAR(50),
    region VARCHAR(100),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Dimension: Principals (Service Accounts and Users)
CREATE TABLE dimensions_principals (
    id VARCHAR(100) PRIMARY KEY,
    org_id VARCHAR(100) NOT NULL REFERENCES dimensions_orgs(id),
    principal_type VARCHAR(50) NOT NULL, -- 'service_account' or 'user'
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Fact Table: Hourly Cost Facts
CREATE TABLE hourly_cost_facts (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    org_id VARCHAR(100) NOT NULL REFERENCES dimensions_orgs(id),
    env_id VARCHAR(100) REFERENCES dimensions_envs(id),
    cluster_id VARCHAR(100) REFERENCES dimensions_clusters(id),
    principal_id VARCHAR(100) REFERENCES dimensions_principals(id),
    
    -- Cost data
    cost_usd DECIMAL(12, 4) NOT NULL,
    cost_source VARCHAR(50) NOT NULL, -- 'billing_api', 'estimated', etc.
    
    -- Business metadata for allocation
    business_unit VARCHAR(100),
    product VARCHAR(100),
    cost_center VARCHAR(100),
    team VARCHAR(100),
    tags JSONB DEFAULT '{}',
    
    -- Quality indicators
    allocation_confidence confidence_level NOT NULL DEFAULT 'medium',
    allocation_method VARCHAR(100), -- 'proportional', 'usage_based', 'manual'
    
    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT unique_hourly_cost UNIQUE (timestamp, org_id, env_id, cluster_id, principal_id)
);

-- Allocation Rules
CREATE TABLE allocation_rules (
    id SERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL, -- 'proportional', 'fixed', 'usage_based'
    priority INTEGER NOT NULL DEFAULT 100,
    
    -- Rule conditions (JSONB for flexibility)
    conditions JSONB NOT NULL, -- e.g., {"cluster_id": "lkc-12345", "env_id": "env-abc"}
    
    -- Rule actions
    allocation_weights JSONB, -- e.g., {"bu": "engineering", "weight": 0.7}
    metadata JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    valid_from TIMESTAMP WITH TIME ZONE,
    valid_to TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ingestion Runs (for tracking ETL jobs)
CREATE TABLE ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    run_type VARCHAR(50) NOT NULL, -- 'hourly', 'daily', 'backfill'
    status ingestion_status NOT NULL DEFAULT 'pending',
    
    -- Time range processed
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Execution tracking
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    
    -- Metrics
    records_processed INTEGER DEFAULT 0,
    records_inserted INTEGER DEFAULT 0,
    records_updated INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    error_details JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_hourly_cost_timestamp ON hourly_cost_facts(timestamp DESC);
CREATE INDEX idx_hourly_cost_org ON hourly_cost_facts(org_id, timestamp DESC);
CREATE INDEX idx_hourly_cost_cluster ON hourly_cost_facts(cluster_id, timestamp DESC);
CREATE INDEX idx_hourly_cost_principal ON hourly_cost_facts(principal_id);
CREATE INDEX idx_hourly_cost_bu ON hourly_cost_facts(business_unit);
CREATE INDEX idx_hourly_cost_product ON hourly_cost_facts(product);

CREATE INDEX idx_dims_envs_org ON dimensions_envs(org_id);
CREATE INDEX idx_dims_clusters_org_env ON dimensions_clusters(org_id, env_id);
CREATE INDEX idx_dims_principals_org ON dimensions_principals(org_id);

CREATE INDEX idx_ingestion_runs_status ON ingestion_runs(status, created_at DESC);
CREATE INDEX idx_ingestion_runs_period ON ingestion_runs(period_start, period_end);

-- Comments for documentation
COMMENT ON TABLE hourly_cost_facts IS 'Main fact table storing hourly cost allocations';
COMMENT ON TABLE dimensions_orgs IS 'Confluent Cloud organizations';
COMMENT ON TABLE dimensions_envs IS 'Confluent Cloud environments within organizations';
COMMENT ON TABLE dimensions_clusters IS 'Kafka clusters';
COMMENT ON TABLE dimensions_principals IS 'Service accounts and users';
COMMENT ON TABLE allocation_rules IS 'Business rules for cost allocation';
COMMENT ON TABLE ingestion_runs IS 'Audit log for ETL job executions';
