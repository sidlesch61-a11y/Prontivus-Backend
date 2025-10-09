"""CID-10 codes table

Revision ID: 0012_cid10_codes
Revises: 0011_comprehensive_clinicore_schema
Create Date: 2025-10-09 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0012_cid10_codes'
down_revision = '0011_comprehensive_clinicore_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create CID-10 codes table
    op.create_table(
        'cid10_codes',
        sa.Column('id', sa.Integer(), nullable=False, primary_key=True),
        sa.Column('code', sa.String(10), nullable=False, index=True, unique=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(10), nullable=True),
        sa.Column('type', sa.String(20), nullable=True),  # 'CID-10' or 'CID-11'
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Create index for full-text search
    op.create_index('idx_cid10_description_trgm', 'cid10_codes', ['description'], postgresql_using='gin', postgresql_ops={'description': 'gin_trgm_ops'})
    
    # Insert sample CID-10 codes (common ones)
    op.execute("""
        INSERT INTO cid10_codes (code, description, category, type) VALUES
        -- Infectious diseases
        ('A09', 'Diarreia e gastroenterite de origem infecciosa presumível', 'A00-A09', 'CID-10'),
        ('A09.0', 'Outras gastroenterites e colites de origem infecciosa e não especificada', 'A00-A09', 'CID-10'),
        
        -- Respiratory diseases
        ('J00', 'Nasofaringite aguda (resfriado comum)', 'J00-J06', 'CID-10'),
        ('J01', 'Sinusite aguda', 'J00-J06', 'CID-10'),
        ('J01.0', 'Sinusite maxilar aguda', 'J00-J06', 'CID-10'),
        ('J01.1', 'Sinusite frontal aguda', 'J00-J06', 'CID-10'),
        ('J01.9', 'Sinusite aguda não especificada', 'J00-J06', 'CID-10'),
        ('J02', 'Faringite aguda', 'J00-J06', 'CID-10'),
        ('J02.9', 'Faringite aguda não especificada', 'J00-J06', 'CID-10'),
        ('J03', 'Amigdalite aguda', 'J00-J06', 'CID-10'),
        ('J03.9', 'Amigdalite aguda não especificada', 'J00-J06', 'CID-10'),
        ('J06', 'Infecções agudas das vias aéreas superiores de localizações múltiplas e não especificadas', 'J00-J06', 'CID-10'),
        ('J06.9', 'Infecção aguda das vias aéreas superiores não especificada', 'J00-J06', 'CID-10'),
        ('J18', 'Pneumonia por microorganismo não especificado', 'J09-J18', 'CID-10'),
        ('J18.9', 'Pneumonia não especificada', 'J09-J18', 'CID-10'),
        ('J20', 'Bronquite aguda', 'J20-J22', 'CID-10'),
        ('J20.9', 'Bronquite aguda não especificada', 'J20-J22', 'CID-10'),
        ('J40', 'Bronquite não especificada como aguda ou crônica', 'J40-J47', 'CID-10'),
        ('J45', 'Asma', 'J40-J47', 'CID-10'),
        ('J45.0', 'Asma predominantemente alérgica', 'J40-J47', 'CID-10'),
        ('J45.9', 'Asma não especificada', 'J40-J47', 'CID-10'),
        
        -- Circulatory diseases
        ('I10', 'Hipertensão essencial (primária)', 'I10-I15', 'CID-10'),
        ('I11', 'Doença cardíaca hipertensiva', 'I10-I15', 'CID-10'),
        ('I11.9', 'Doença cardíaca hipertensiva sem insuficiência cardíaca (congestiva)', 'I10-I15', 'CID-10'),
        ('I25', 'Doença isquêmica crônica do coração', 'I20-I25', 'CID-10'),
        ('I25.1', 'Doença aterosclerótica do coração', 'I20-I25', 'CID-10'),
        ('I50', 'Insuficiência cardíaca', 'I50', 'CID-10'),
        ('I50.0', 'Insuficiência cardíaca congestiva', 'I50', 'CID-10'),
        ('I50.9', 'Insuficiência cardíaca não especificada', 'I50', 'CID-10'),
        
        -- Endocrine diseases
        ('E11', 'Diabetes mellitus não-insulino-dependente', 'E10-E14', 'CID-10'),
        ('E11.9', 'Diabetes mellitus não-insulino-dependente - sem complicações', 'E10-E14', 'CID-10'),
        ('E66', 'Obesidade', 'E65-E68', 'CID-10'),
        ('E66.0', 'Obesidade devida a excesso de calorias', 'E65-E68', 'CID-10'),
        ('E66.9', 'Obesidade não especificada', 'E65-E68', 'CID-10'),
        ('E78', 'Distúrbios do metabolismo de lipoproteínas e outras lipidemias', 'E70-E90', 'CID-10'),
        ('E78.0', 'Hipercolesterolemia pura', 'E70-E90', 'CID-10'),
        ('E78.5', 'Hiperlipidemia não especificada', 'E70-E90', 'CID-10'),
        
        -- Digestive diseases
        ('K21', 'Doença de refluxo gastroesofágico', 'K20-K31', 'CID-10'),
        ('K21.0', 'Doença de refluxo gastroesofágico com esofagite', 'K20-K31', 'CID-10'),
        ('K21.9', 'Doença de refluxo gastroesofágico sem esofagite', 'K20-K31', 'CID-10'),
        ('K29', 'Gastrite e duodenite', 'K20-K31', 'CID-10'),
        ('K29.7', 'Gastrite não especificada', 'K20-K31', 'CID-10'),
        ('K30', 'Dispepsia', 'K20-K31', 'CID-10'),
        ('K59', 'Outros transtornos funcionais do intestino', 'K55-K63', 'CID-10'),
        ('K59.0', 'Constipação', 'K55-K63', 'CID-10'),
        
        -- Musculoskeletal diseases
        ('M15', 'Poliartrose', 'M15-M19', 'CID-10'),
        ('M15.9', 'Poliartrose não especificada', 'M15-M19', 'CID-10'),
        ('M16', 'Coxartrose [artrose do quadril]', 'M15-M19', 'CID-10'),
        ('M17', 'Gonartrose [artrose do joelho]', 'M15-M19', 'CID-10'),
        ('M19', 'Outras artroses', 'M15-M19', 'CID-10'),
        ('M19.9', 'Artrose não especificada', 'M15-M19', 'CID-10'),
        ('M25', 'Outros transtornos articulares não classificados em outra parte', 'M20-M25', 'CID-10'),
        ('M25.5', 'Dor articular', 'M20-M25', 'CID-10'),
        ('M54', 'Dorsalgia', 'M50-M54', 'CID-10'),
        ('M54.5', 'Dor lombar baixa', 'M50-M54', 'CID-10'),
        ('M54.9', 'Dorsalgia não especificada', 'M50-M54', 'CID-10'),
        ('M79', 'Outros transtornos dos tecidos moles não classificados em outra parte', 'M70-M79', 'CID-10'),
        ('M79.1', 'Mialgia', 'M70-M79', 'CID-10'),
        
        -- Mental and behavioral disorders
        ('F32', 'Episódios depressivos', 'F30-F39', 'CID-10'),
        ('F32.0', 'Episódio depressivo leve', 'F30-F39', 'CID-10'),
        ('F32.1', 'Episódio depressivo moderado', 'F30-F39', 'CID-10'),
        ('F32.9', 'Episódio depressivo não especificado', 'F30-F39', 'CID-10'),
        ('F41', 'Outros transtornos ansiosos', 'F40-F48', 'CID-10'),
        ('F41.1', 'Ansiedade generalizada', 'F40-F48', 'CID-10'),
        ('F41.9', 'Transtorno ansioso não especificado', 'F40-F48', 'CID-10'),
        
        -- Symptoms and signs
        ('R05', 'Tosse', 'R00-R09', 'CID-10'),
        ('R10', 'Dor abdominal e pélvica', 'R10-R19', 'CID-10'),
        ('R10.0', 'Abdome agudo', 'R10-R19', 'CID-10'),
        ('R10.4', 'Outras dores abdominais e as não especificadas', 'R10-R19', 'CID-10'),
        ('R50', 'Febre de origem desconhecida e de outras origens', 'R50-R69', 'CID-10'),
        ('R50.9', 'Febre não especificada', 'R50-R69', 'CID-10'),
        ('R51', 'Cefaleia', 'R50-R69', 'CID-10'),
        ('R53', 'Mal estar e fadiga', 'R50-R69', 'CID-10'),
        
        -- Pregnancy, childbirth
        ('O80', 'Parto único espontâneo', 'O80-O84', 'CID-10'),
        ('O80.0', 'Parto único espontâneo, apresentação cefálica de vértice', 'O80-O84', 'CID-10'),
        
        -- Injuries
        ('S06', 'Traumatismo intracraniano', 'S00-S09', 'CID-10'),
        ('S06.0', 'Concussão cerebral', 'S00-S09', 'CID-10'),
        ('S93', 'Luxação, entorse e distensão das articulações e dos ligamentos do nível do tornozelo e do pé', 'S90-S99', 'CID-10'),
        ('S93.4', 'Entorse e distensão do tornozelo', 'S90-S99', 'CID-10'),
        
        -- Other common codes
        ('Z00', 'Exame geral e investigação de pessoas sem queixas ou diagnóstico relatado', 'Z00-Z13', 'CID-10'),
        ('Z00.0', 'Exame médico geral', 'Z00-Z13', 'CID-10'),
        ('Z01', 'Outros exames e investigações especiais de pessoas sem queixa ou diagnóstico relatado', 'Z00-Z13', 'CID-10'),
        ('Z01.6', 'Exame radiológico não classificado em outra parte', 'Z00-Z13', 'CID-10'),
        ('Z23', 'Necessidade de imunização contra doença bacteriana única', 'Z20-Z29', 'CID-10'),
        ('Z23.8', 'Necessidade de imunização contra outras doenças bacterianas únicas', 'Z20-Z29', 'CID-10')
    """)


def downgrade() -> None:
    op.drop_table('cid10_codes')

