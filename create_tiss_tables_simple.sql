-- Create TISS-related tables that are missing from the database
-- This script creates the required tables for TISS functionality without foreign key constraints

-- Create tiss_providers table
CREATE TABLE IF NOT EXISTS tiss_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL,
    cnpj VARCHAR(18),
    endpoint_url TEXT,
    environment VARCHAR(20) DEFAULT 'production',
    username VARCHAR(255),
    password_encrypted TEXT,
    certificate_path TEXT,
    timeout_seconds INTEGER DEFAULT 30,
    max_retries INTEGER DEFAULT 3,
    retry_delay_seconds INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'active',
    last_test_result TEXT,
    last_tested_at TIMESTAMP WITHOUT TIME ZONE,
    last_successful_request TIMESTAMP WITHOUT TIME ZONE,
    config_meta JSONB,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create tiss_jobs table
CREATE TABLE IF NOT EXISTS tiss_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    provider_id UUID,
    job_type VARCHAR(100) NOT NULL,
    invoice_id UUID,
    procedure_code VARCHAR(50),
    payload JSONB,
    response_data JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    scheduled_at TIMESTAMP WITHOUT TIME ZONE,
    processed_at TIMESTAMP WITHOUT TIME ZONE,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    last_error TEXT,
    last_error_at TIMESTAMP WITHOUT TIME ZONE,
    next_retry_at TIMESTAMP WITHOUT TIME ZONE,
    ethical_lock_type VARCHAR(100),
    ethical_lock_reason TEXT,
    manual_review_required BOOLEAN DEFAULT FALSE,
    job_meta JSONB,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create tiss_guides table
CREATE TABLE IF NOT EXISTS tiss_guides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    consultation_id UUID,
    patient_id UUID NOT NULL,
    provider_id UUID,
    guide_type VARCHAR(100) NOT NULL,
    procedure_code VARCHAR(50),
    procedure_name VARCHAR(255),
    quantity INTEGER DEFAULT 1,
    unit_value DECIMAL(10,2),
    total_value DECIMAL(10,2),
    authorization_number VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    xml_content TEXT,
    pdf_path TEXT,
    submitted_at TIMESTAMP WITHOUT TIME ZONE,
    approved_at TIMESTAMP WITHOUT TIME ZONE,
    rejected_at TIMESTAMP WITHOUT TIME ZONE,
    rejection_reason TEXT,
    notes TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create insurance_providers table
CREATE TABLE IF NOT EXISTS insurance_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL,
    cnpj VARCHAR(18),
    contact_email VARCHAR(255),
    contact_phone VARCHAR(20),
    address TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create exam_database table for standardized exams
CREATE TABLE IF NOT EXISTS exam_database (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id UUID,
    name VARCHAR(255) NOT NULL,
    tuss_code VARCHAR(50) NOT NULL,
    category VARCHAR(100),
    description TEXT,
    preparation_instructions TEXT,
    fasting_required BOOLEAN DEFAULT FALSE,
    fasting_hours INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_tiss_providers_clinic_id ON tiss_providers(clinic_id);
CREATE INDEX IF NOT EXISTS idx_tiss_jobs_clinic_id ON tiss_jobs(clinic_id);
CREATE INDEX IF NOT EXISTS idx_tiss_jobs_status ON tiss_jobs(status);
CREATE INDEX IF NOT EXISTS idx_tiss_jobs_created_at ON tiss_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_tiss_guides_clinic_id ON tiss_guides(clinic_id);
CREATE INDEX IF NOT EXISTS idx_tiss_guides_consultation_id ON tiss_guides(consultation_id);
CREATE INDEX IF NOT EXISTS idx_tiss_guides_patient_id ON tiss_guides(patient_id);
CREATE INDEX IF NOT EXISTS idx_insurance_providers_clinic_id ON insurance_providers(clinic_id);
CREATE INDEX IF NOT EXISTS idx_exam_database_tuss_code ON exam_database(tuss_code);
CREATE INDEX IF NOT EXISTS idx_exam_database_category ON exam_database(category);
