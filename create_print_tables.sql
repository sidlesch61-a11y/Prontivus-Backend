-- Tabela para logs de impressão
CREATE TABLE IF NOT EXISTS print_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_id UUID NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    printed_by UUID NOT NULL,
    printed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    printer_name VARCHAR(255),
    pages_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    FOREIGN KEY (consultation_id) REFERENCES consultations(id),
    FOREIGN KEY (printed_by) REFERENCES users(id)
);

-- Tabela para regras de preço
CREATE TABLE IF NOT EXISTS price_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    convenio_id UUID,
    consulta_tipo VARCHAR(50) NOT NULL,
    valor NUMERIC(10,2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Adicionar campo altura na tabela de dados vitais (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'patient_vitals' AND column_name = 'altura') THEN
        ALTER TABLE patient_vitals ADD COLUMN altura NUMERIC(5,2);
    END IF;
END $$;

-- Adicionar campo cidade na tabela de pacientes (se não existir)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'patients' AND column_name = 'city') THEN
        ALTER TABLE patients ADD COLUMN city VARCHAR(100);
    END IF;
END $$;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_print_logs_consultation_id ON print_logs(consultation_id);
CREATE INDEX IF NOT EXISTS idx_print_logs_printed_at ON print_logs(printed_at);
CREATE INDEX IF NOT EXISTS idx_price_rules_convenio_tipo ON price_rules(convenio_id, consulta_tipo);
