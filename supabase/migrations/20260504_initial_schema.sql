-- Supabase Database Schema for Nursing Labor KPI Platform
-- Copy and paste this into the Supabase SQL Editor to initialize the database

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    email TEXT UNIQUE NOT NULL,
    role TEXT DEFAULT 'viewer',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. upload_batches
CREATE TABLE upload_batches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    filename TEXT NOT NULL,
    uploaded_by UUID REFERENCES users(id),
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT DEFAULT 'processing',
    version_number INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    notes TEXT,
    detected_pay_periods INTEGER DEFAULT 0,
    rows_parsed INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0
);

-- 4. uploaded_files
CREATE TABLE uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    storage_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size BIGINT,
    checksum TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. pay_periods
CREATE TABLE pay_periods (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    pay_period_date DATE NOT NULL,
    pay_cycle_group TEXT,
    source_upload_batch_id UUID REFERENCES upload_batches(id),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. facilities
CREATE TABLE facilities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    facility_name TEXT NOT NULL,
    normalized_facility_name TEXT NOT NULL,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. facility_aliases
CREATE TABLE facility_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES facilities(id),
    alias_name TEXT NOT NULL,
    source_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. regions
CREATE TABLE regions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    region_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. acquisition_groups
CREATE TABLE acquisition_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    acquisition_group_name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. facility_dimension_history
CREATE TABLE facility_dimension_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES facilities(id),
    region_id UUID REFERENCES regions(id),
    acquisition_group_id UUID REFERENCES acquisition_groups(id),
    effective_from DATE,
    effective_to DATE,
    source_upload_batch_id UUID REFERENCES upload_batches(id)
);

-- 11. payroll_schedule_groups
CREATE TABLE payroll_schedule_groups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    schedule_name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 12. facility_pay_cycle_mapping
CREATE TABLE facility_pay_cycle_mapping (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES facilities(id),
    inferred_pay_cycle TEXT,
    manual_pay_cycle_override TEXT,
    final_pay_cycle TEXT,
    current_pay_period_id UUID REFERENCES pay_periods(id),
    prior_matching_pay_period_id UUID REFERENCES pay_periods(id),
    comparable_status TEXT,
    missing_prior_flag BOOLEAN DEFAULT false,
    new_facility_flag BOOLEAN DEFAULT false,
    dropped_facility_flag BOOLEAN DEFAULT false,
    notes TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 13. facility_period_metrics
CREATE TABLE facility_period_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    facility_id UUID REFERENCES facilities(id),
    region_id UUID REFERENCES regions(id),
    acquisition_group_id UUID REFERENCES acquisition_groups(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    pay_cycle_group TEXT,
    ot_dollars NUMERIC,
    ot_hours NUMERIC,
    ot_percent_labor_dollars NUMERIC,
    ot_percent_hours NUMERIC,
    bonus_dollars NUMERIC,
    direct_care_hppd NUMERIC,
    direct_care_ppd NUMERIC,
    overall_labor_ppd NUMERIC,
    labor_pressure_score NUMERIC,
    risk_category TEXT,
    data_quality_status TEXT
);

-- 14. ot_detail_lines
CREATE TABLE ot_detail_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    facility_id UUID REFERENCES facilities(id),
    region_id UUID REFERENCES regions(id),
    acquisition_group_id UUID REFERENCES acquisition_groups(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    department TEXT,
    position TEXT,
    employee_name TEXT,
    ot_dollars NUMERIC,
    ot_hours NUMERIC,
    ot_percent_labor_dollars NUMERIC,
    ot_percent_hours NUMERIC,
    source_sheet TEXT,
    source_row INTEGER
);

-- 15. bonus_detail_lines
CREATE TABLE bonus_detail_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    facility_id UUID REFERENCES facilities(id),
    region_id UUID REFERENCES regions(id),
    acquisition_group_id UUID REFERENCES acquisition_groups(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    bonus_type TEXT,
    department TEXT,
    position TEXT,
    employee_name TEXT,
    bonus_dollars NUMERIC,
    source_sheet TEXT,
    source_row INTEGER
);

-- 16. ppd_metric_lines
CREATE TABLE ppd_metric_lines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    facility_id UUID REFERENCES facilities(id),
    region_id UUID REFERENCES regions(id),
    acquisition_group_id UUID REFERENCES acquisition_groups(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    metric_type TEXT,
    metric_value NUMERIC,
    source_sheet TEXT,
    source_row INTEGER
);

-- 17. reported_total_trends
CREATE TABLE reported_total_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    level_type TEXT,
    level_id UUID,
    metric_name TEXT,
    pay_period_id UUID REFERENCES pay_periods(id),
    value NUMERIC,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 18. same_facility_comparable_trends
CREATE TABLE same_facility_comparable_trends (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    level_type TEXT,
    level_id UUID,
    metric_name TEXT,
    pay_cycle_group TEXT,
    current_pay_period_id UUID REFERENCES pay_periods(id),
    prior_pay_period_id UUID REFERENCES pay_periods(id),
    current_value NUMERIC,
    prior_value NUMERIC,
    delta NUMERIC,
    delta_percent NUMERIC,
    comparable_status TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 19. labor_pressure_scores
CREATE TABLE labor_pressure_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    facility_id UUID REFERENCES facilities(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    pay_cycle_group TEXT,
    score NUMERIC,
    risk_category TEXT,
    main_driver TEXT,
    recommended_follow_up TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 20. data_quality_issues
CREATE TABLE data_quality_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    issue_type TEXT,
    severity TEXT,
    sheet_name TEXT,
    row_number INTEGER,
    facility_id UUID REFERENCES facilities(id),
    pay_period_id UUID REFERENCES pay_periods(id),
    description TEXT,
    recommended_fix TEXT,
    status TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 21. reconciliation_results
CREATE TABLE reconciliation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_batch_id UUID REFERENCES upload_batches(id),
    reconciliation_type TEXT,
    metric_name TEXT,
    source_a TEXT,
    source_b TEXT,
    source_a_value NUMERIC,
    source_b_value NUMERIC,
    difference NUMERIC,
    severity TEXT,
    status TEXT,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 22. export_jobs
CREATE TABLE export_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    requested_by UUID REFERENCES users(id),
    export_type TEXT,
    filter_json JSONB,
    status TEXT DEFAULT 'pending',
    file_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

-- 23. audit_logs
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    organization_id UUID REFERENCES organizations(id),
    user_id UUID REFERENCES users(id),
    action TEXT,
    entity_type TEXT,
    entity_id UUID,
    details_json JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
