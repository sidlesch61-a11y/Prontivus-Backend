-- Create TISS-related tables that are missing from the database
-- This script creates the required tables for TISS functionality

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
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
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
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id),
    FOREIGN KEY (provider_id) REFERENCES tiss_providers(id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);

-- Create tiss_guides table (if it doesn't exist)
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
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id),
    FOREIGN KEY (consultation_id) REFERENCES consultations(id),
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (provider_id) REFERENCES tiss_providers(id)
);

-- Create insurance_providers table (if it doesn't exist)
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
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
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
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    FOREIGN KEY (clinic_id) REFERENCES clinics(id)
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

-- Insert some sample insurance providers
INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
SELECT 
    gen_random_uuid(),
    (SELECT id FROM clinics LIMIT 1),
    'Particular',
    'PARTICULAR',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'PARTICULAR');

INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
SELECT 
    gen_random_uuid(),
    (SELECT id FROM clinics LIMIT 1),
    'Unimed',
    'UNIMED',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'UNIMED');

INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
SELECT 
    gen_random_uuid(),
    (SELECT id FROM clinics LIMIT 1),
    'Bradesco Saúde',
    'BRADESCO',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'BRADESCO');

INSERT INTO insurance_providers (id, clinic_id, name, code, is_active) 
SELECT 
    gen_random_uuid(),
    (SELECT id FROM clinics LIMIT 1),
    'Amil',
    'AMIL',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM insurance_providers WHERE code = 'AMIL');

-- Insert some sample exams
INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL, -- Global exams available to all clinics
    'Hemograma Completo',
    '40301001',
    'Hematologia',
    'Exame de sangue completo incluindo contagem de células sanguíneas',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301001');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Glicemia de Jejum',
    '40301002',
    'Bioquímica',
    'Dosagem de glicose no sangue em jejum',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301002');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Colesterol Total',
    '40301003',
    'Bioquímica',
    'Dosagem do colesterol total no sangue',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301003');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Triglicerídeos',
    '40301004',
    'Bioquímica',
    'Dosagem de triglicerídeos no sangue',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301004');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Creatinina',
    '40301005',
    'Bioquímica',
    'Dosagem de creatinina para avaliação da função renal',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301005');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Uréia',
    '40301006',
    'Bioquímica',
    'Dosagem de uréia para avaliação da função renal',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301006');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'TSH',
    '40301007',
    'Hormônios',
    'Dosagem do hormônio estimulador da tireóide',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301007');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'T4 Livre',
    '40301008',
    'Hormônios',
    'Dosagem de tiroxina livre',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301008');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'T3 Livre',
    '40301009',
    'Hormônios',
    'Dosagem de triiodotironina livre',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301009');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Exame de Urina Completo',
    '40301010',
    'Urologia',
    'Análise completa da urina incluindo elementos anormais',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301010');

-- Add more common exams
INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Eletrocardiograma',
    '40301011',
    'Cardiologia',
    'Registro gráfico da atividade elétrica do coração',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301011');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ecocardiograma',
    '40301012',
    'Cardiologia',
    'Ultrassom do coração para avaliação da função cardíaca',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301012');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Raio-X de Tórax',
    '40301013',
    'Radiologia',
    'Imagem radiográfica do tórax em PA e perfil',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301013');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ultrassom Abdominal Total',
    '40301014',
    'Radiologia',
    'Ultrassom de abdome total incluindo fígado, vesícula, pâncreas, baço e rins',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301014');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Mamografia',
    '40301015',
    'Radiologia',
    'Exame radiológico das mamas para detecção precoce de câncer',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301015');

-- Add more exams to reach 38 total
INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Papanicolau',
    '40301016',
    'Ginecologia',
    'Exame citológico para detecção de alterações no colo do útero',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301016');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Teste Ergométrico',
    '40301017',
    'Cardiologia',
    'Teste de esforço para avaliação cardiovascular',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301017');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Holter 24h',
    '40301018',
    'Cardiologia',
    'Monitoramento contínuo do ritmo cardíaco por 24 horas',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301018');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'MAPA 24h',
    '40301019',
    'Cardiologia',
    'Monitorização Ambulatorial da Pressão Arterial por 24 horas',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301019');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Densitometria Óssea',
    '40301020',
    'Radiologia',
    'Exame para avaliação da densidade mineral óssea',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301020');

-- Continue adding more exams...
INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Tomografia Computadorizada',
    '40301021',
    'Radiologia',
    'Exame de imagem por tomografia computadorizada',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301021');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ressonância Magnética',
    '40301022',
    'Radiologia',
    'Exame de imagem por ressonância magnética',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301022');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Endoscopia Digestiva Alta',
    '40301023',
    'Gastroenterologia',
    'Exame endoscópico do esôfago, estômago e duodeno',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301023');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Colonoscopia',
    '40301024',
    'Gastroenterologia',
    'Exame endoscópico do intestino grosso',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301024');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Biópsia de Pele',
    '40301025',
    'Dermatologia',
    'Coleta de fragmento de pele para análise histológica',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301025');

-- Add remaining exams to reach 38
INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Audiometria',
    '40301026',
    'Otorrinolaringologia',
    'Exame de audição para avaliação da capacidade auditiva',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301026');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Espirometria',
    '40301027',
    'Pneumologia',
    'Exame de função pulmonar',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301027');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Teste de Alergia',
    '40301028',
    'Alergologia',
    'Teste cutâneo para identificação de alergias',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301028');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Raio-X de Coluna',
    '40301029',
    'Ortopedia',
    'Imagem radiográfica da coluna vertebral',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301029');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ultrassom de Tireóide',
    '40301030',
    'Endocrinologia',
    'Ultrassom da glândula tireóide',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301030');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Raio-X de Articulações',
    '40301031',
    'Ortopedia',
    'Imagem radiográfica das articulações',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301031');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ultrassom de Próstata',
    '40301032',
    'Urologia',
    'Ultrassom da próstata via abdominal',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301032');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ultrassom Transvaginal',
    '40301033',
    'Ginecologia',
    'Ultrassom ginecológico via transvaginal',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301033');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Teste de Glicemia Pós-Prandial',
    '40301034',
    'Endocrinologia',
    'Dosagem de glicose 2 horas após refeição',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301034');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Hemoglobina Glicada',
    '40301035',
    'Endocrinologia',
    'Dosagem de hemoglobina glicada (HbA1c)',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301035');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Vitamina D',
    '40301036',
    'Bioquímica',
    'Dosagem de 25-hidroxivitamina D',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301036');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Ácido Úrico',
    '40301037',
    'Bioquímica',
    'Dosagem de ácido úrico no sangue',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301037');

INSERT INTO exam_database (id, clinic_id, name, tuss_code, category, description, is_active)
SELECT 
    gen_random_uuid(),
    NULL,
    'Raio-X de Pelve',
    '40301038',
    'Radiologia',
    'Imagem radiográfica da pelve',
    TRUE
WHERE NOT EXISTS (SELECT 1 FROM exam_database WHERE tuss_code = '40301038');

-- Update the updated_at timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
DROP TRIGGER IF EXISTS update_tiss_providers_updated_at ON tiss_providers;
CREATE TRIGGER update_tiss_providers_updated_at BEFORE UPDATE ON tiss_providers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tiss_jobs_updated_at ON tiss_jobs;
CREATE TRIGGER update_tiss_jobs_updated_at BEFORE UPDATE ON tiss_jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_tiss_guides_updated_at ON tiss_guides;
CREATE TRIGGER update_tiss_guides_updated_at BEFORE UPDATE ON tiss_guides FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_insurance_providers_updated_at ON insurance_providers;
CREATE TRIGGER update_insurance_providers_updated_at BEFORE UPDATE ON insurance_providers FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_exam_database_updated_at ON exam_database;
CREATE TRIGGER update_exam_database_updated_at BEFORE UPDATE ON exam_database FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant necessary permissions
GRANT ALL ON tiss_providers TO PUBLIC;
GRANT ALL ON tiss_jobs TO PUBLIC;
GRANT ALL ON tiss_guides TO PUBLIC;
GRANT ALL ON insurance_providers TO PUBLIC;
GRANT ALL ON exam_database TO PUBLIC;
