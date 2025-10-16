-- Create exam_categories table
CREATE TABLE IF NOT EXISTS exam_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    description VARCHAR,
    color VARCHAR DEFAULT '#3B82F6',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_exam_categories_name ON exam_categories (name);

-- Create standard_exams table
CREATE TABLE IF NOT EXISTS standard_exams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    tuss_code VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    description VARCHAR,
    preparation_instructions VARCHAR,
    normal_values VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_standard_exams_name ON standard_exams (name);
CREATE INDEX IF NOT EXISTS ix_standard_exams_tuss_code ON standard_exams (tuss_code);

-- Create insurance_providers table
CREATE TABLE IF NOT EXISTS insurance_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL UNIQUE,
    code VARCHAR NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_insurance_providers_name ON insurance_providers (name);
CREATE INDEX IF NOT EXISTS ix_insurance_providers_code ON insurance_providers (code);

-- Create service_pricing table
CREATE TABLE IF NOT EXISTS service_pricing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insurance_provider_id UUID NOT NULL REFERENCES insurance_providers(id),
    service_type VARCHAR NOT NULL,
    service_name VARCHAR NOT NULL,
    base_price DECIMAL(10,2) NOT NULL,
    insurance_price DECIMAL(10,2) NOT NULL,
    discount_percentage DECIMAL(5,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create pricing_rules table
CREATE TABLE IF NOT EXISTS pricing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insurance_provider_id UUID NOT NULL REFERENCES insurance_providers(id),
    rule_type VARCHAR NOT NULL,
    rule_value DECIMAL(10,2) NOT NULL,
    min_amount DECIMAL(10,2),
    max_amount DECIMAL(10,2),
    service_type VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
