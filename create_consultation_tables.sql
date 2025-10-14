-- Create consultation extended tables for Atendimento Médico module
-- Run this SQL script directly on the PostgreSQL database

-- 1. Vitals table
CREATE TABLE IF NOT EXISTS vitals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    recorded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    blood_pressure VARCHAR,
    heart_rate INTEGER,
    temperature FLOAT,
    weight FLOAT,
    height FLOAT,
    respiratory_rate INTEGER,
    oxygen_saturation INTEGER,
    notes TEXT,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 2. Attachments table
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR NOT NULL,
    file_type VARCHAR NOT NULL,
    file_size INTEGER NOT NULL,
    file_url VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR,
    uploaded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 3. Queue Status table
CREATE TABLE IF NOT EXISTS queue_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    clinic_id UUID NOT NULL REFERENCES clinics(id) ON DELETE CASCADE,
    status VARCHAR NOT NULL DEFAULT 'waiting',
    priority INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    called_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 4. Consultation Notes table
CREATE TABLE IF NOT EXISTS consultation_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL UNIQUE REFERENCES consultations(id) ON DELETE CASCADE,
    anamnese TEXT,
    physical_exam TEXT,
    evolution TEXT,
    diagnosis TEXT,
    treatment_plan TEXT,
    allergies VARCHAR,
    chronic_conditions VARCHAR,
    auto_saved_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 5. Prescription Items table
CREATE TABLE IF NOT EXISTS prescription_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescription_id UUID NOT NULL REFERENCES prescriptions(id) ON DELETE CASCADE,
    medication_name VARCHAR NOT NULL,
    dosage VARCHAR NOT NULL,
    frequency VARCHAR NOT NULL,
    duration VARCHAR NOT NULL,
    route VARCHAR NOT NULL DEFAULT 'oral',
    instructions TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 6. Medical Certificates table
CREATE TABLE IF NOT EXISTS medical_certificates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    certificate_type VARCHAR NOT NULL,
    content TEXT NOT NULL,
    days_off INTEGER,
    cid10_code VARCHAR,
    pdf_url VARCHAR,
    icp_signature_hash VARCHAR,
    issued_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 7. Exam Requests table
CREATE TABLE IF NOT EXISTS exam_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tiss_guide_id UUID REFERENCES tiss_guides(id) ON DELETE SET NULL,
    exam_type VARCHAR NOT NULL,
    exam_name VARCHAR NOT NULL,
    clinical_indication TEXT NOT NULL,
    urgency VARCHAR NOT NULL DEFAULT 'routine',
    pdf_url VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 8. Referrals table
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    specialty VARCHAR NOT NULL,
    reason TEXT NOT NULL,
    urgency VARCHAR NOT NULL DEFAULT 'routine',
    referred_to_doctor VARCHAR,
    referred_to_clinic VARCHAR,
    pdf_url VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'pending',
    referred_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 9. Voice Notes table
CREATE TABLE IF NOT EXISTS voice_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    recorded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    audio_url VARCHAR NOT NULL,
    duration_seconds INTEGER NOT NULL,
    transcription TEXT,
    note_type VARCHAR NOT NULL DEFAULT 'anamnese',
    transcribed_at TIMESTAMP,
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_vitals_consultation ON vitals(consultation_id);
CREATE INDEX IF NOT EXISTS idx_attachments_consultation ON attachments(consultation_id);
CREATE INDEX IF NOT EXISTS idx_queue_status_doctor ON queue_status(doctor_id, status);
CREATE INDEX IF NOT EXISTS idx_queue_status_appointment ON queue_status(appointment_id);
CREATE INDEX IF NOT EXISTS idx_consultation_notes_consultation ON consultation_notes(consultation_id);
CREATE INDEX IF NOT EXISTS idx_prescription_items_prescription ON prescription_items(prescription_id);
CREATE INDEX IF NOT EXISTS idx_exam_requests_consultation ON exam_requests(consultation_id);
CREATE INDEX IF NOT EXISTS idx_referrals_consultation ON referrals(consultation_id);
CREATE INDEX IF NOT EXISTS idx_voice_notes_consultation ON voice_notes(consultation_id);

-- Create updated_at trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
DROP TRIGGER IF EXISTS update_vitals_updated_at ON vitals;
CREATE TRIGGER update_vitals_updated_at BEFORE UPDATE ON vitals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_queue_status_updated_at ON queue_status;
CREATE TRIGGER update_queue_status_updated_at BEFORE UPDATE ON queue_status FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_consultation_notes_updated_at ON consultation_notes;
CREATE TRIGGER update_consultation_notes_updated_at BEFORE UPDATE ON consultation_notes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'All consultation extended tables created successfully!';
END $$;

