#!/usr/bin/env python3
"""
Script to populate the standardized exam database with common medical exams
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.exam_database import StandardExam, ExamCategory
from app.core.config import settings

# Database URL
DATABASE_URL = settings.database_url

async def populate_exam_database():
    """Populate the exam database with standard exams"""
    
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            # Create categories first
            categories = [
                {"name": "Laboratório", "description": "Exames laboratoriais", "color": "#3B82F6"},
                {"name": "Imagem", "description": "Exames de imagem", "color": "#10B981"},
                {"name": "Cardiologia", "description": "Exames cardiológicos", "color": "#EF4444"},
                {"name": "Neurologia", "description": "Exames neurológicos", "color": "#8B5CF6"},
                {"name": "Ginecologia", "description": "Exames ginecológicos", "color": "#EC4899"},
                {"name": "Urologia", "description": "Exames urológicos", "color": "#06B6D4"},
                {"name": "Oftalmologia", "description": "Exames oftalmológicos", "color": "#F59E0B"},
                {"name": "Ortopedia", "description": "Exames ortopédicos", "color": "#84CC16"},
                {"name": "Geral", "description": "Exames gerais", "color": "#6B7280"}
            ]
            
            for cat_data in categories:
                category = ExamCategory(**cat_data)
                session.add(category)
            
            await session.commit()
            print("✅ Categories created successfully")
            
            # Create standard exams
            exams = [
                # Laboratório
                {"name": "Hemograma completo", "tuss_code": "40301001", "category": "Laboratório", 
                 "description": "Contagem completa de células sanguíneas", "preparation_instructions": "Jejum não necessário"},
                {"name": "Glicemia de jejum", "tuss_code": "40301002", "category": "Laboratório",
                 "description": "Dosagem de glicose no sangue", "preparation_instructions": "Jejum de 8-12 horas"},
                {"name": "Colesterol total", "tuss_code": "40301003", "category": "Laboratório",
                 "description": "Dosagem do colesterol total", "preparation_instructions": "Jejum de 12 horas"},
                {"name": "HDL colesterol", "tuss_code": "40301004", "category": "Laboratório",
                 "description": "Colesterol de alta densidade", "preparation_instructions": "Jejum de 12 horas"},
                {"name": "LDL colesterol", "tuss_code": "40301005", "category": "Laboratório",
                 "description": "Colesterol de baixa densidade", "preparation_instructions": "Jejum de 12 horas"},
                {"name": "Triglicerídeos", "tuss_code": "40301006", "category": "Laboratório",
                 "description": "Dosagem de triglicerídeos", "preparation_instructions": "Jejum de 12 horas"},
                {"name": "Creatinina", "tuss_code": "40301007", "category": "Laboratório",
                 "description": "Função renal", "preparation_instructions": "Jejum não necessário"},
                {"name": "Ureia", "tuss_code": "40301008", "category": "Laboratório",
                 "description": "Função renal", "preparation_instructions": "Jejum não necessário"},
                {"name": "TGO (AST)", "tuss_code": "40301009", "category": "Laboratório",
                 "description": "Transaminase glutâmico-oxalacética", "preparation_instructions": "Jejum não necessário"},
                {"name": "TGP (ALT)", "tuss_code": "40301010", "category": "Laboratório",
                 "description": "Transaminase glutâmico-pirúvica", "preparation_instructions": "Jejum não necessário"},
                {"name": "TSH", "tuss_code": "40301011", "category": "Laboratório",
                 "description": "Hormônio estimulador da tireoide", "preparation_instructions": "Jejum não necessário"},
                {"name": "T4 livre", "tuss_code": "40301012", "category": "Laboratório",
                 "description": "Tiroxina livre", "preparation_instructions": "Jejum não necessário"},
                {"name": "T3", "tuss_code": "40301013", "category": "Laboratório",
                 "description": "Triiodotironina", "preparation_instructions": "Jejum não necessário"},
                {"name": "PSA", "tuss_code": "40301014", "category": "Laboratório",
                 "description": "Antígeno prostático específico", "preparation_instructions": "Jejum não necessário"},
                {"name": "Papanicolau", "tuss_code": "40301015", "category": "Laboratório",
                 "description": "Citologia oncótica", "preparation_instructions": "Evitar relações sexuais 48h antes"},
                
                # Imagem
                {"name": "Raio-X de tórax", "tuss_code": "40302001", "category": "Imagem",
                 "description": "Radiografia do tórax", "preparation_instructions": "Remover objetos metálicos"},
                {"name": "Raio-X de coluna", "tuss_code": "40302002", "category": "Imagem",
                 "description": "Radiografia da coluna vertebral", "preparation_instructions": "Remover objetos metálicos"},
                {"name": "Ultrassom abdominal", "tuss_code": "40302003", "category": "Imagem",
                 "description": "Ultrassonografia do abdome", "preparation_instructions": "Jejum de 6 horas"},
                {"name": "Ultrassom pélvico", "tuss_code": "40302004", "category": "Imagem",
                 "description": "Ultrassonografia pélvica", "preparation_instructions": "Bexiga cheia"},
                {"name": "Mamografia", "tuss_code": "40302005", "category": "Imagem",
                 "description": "Radiografia das mamas", "preparation_instructions": "Evitar desodorante"},
                {"name": "Tomografia computadorizada", "tuss_code": "40302006", "category": "Imagem",
                 "description": "TC do tórax/abdome", "preparation_instructions": "Jejum de 4 horas"},
                {"name": "Ressonância magnética", "tuss_code": "40302007", "category": "Imagem",
                 "description": "RM de crânio/coluna", "preparation_instructions": "Remover todos os objetos metálicos"},
                
                # Cardiologia
                {"name": "Eletrocardiograma", "tuss_code": "40303001", "category": "Cardiologia",
                 "description": "ECG de repouso", "preparation_instructions": "Repouso de 10 minutos"},
                {"name": "Teste ergométrico", "tuss_code": "40303002", "category": "Cardiologia",
                 "description": "Teste de esforço", "preparation_instructions": "Jejum de 2 horas, roupas confortáveis"},
                {"name": "Ecocardiograma", "tuss_code": "40303003", "category": "Cardiologia",
                 "description": "Ultrassom do coração", "preparation_instructions": "Jejum não necessário"},
                {"name": "Holter 24h", "tuss_code": "40303004", "category": "Cardiologia",
                 "description": "Monitoramento cardíaco", "preparation_instructions": "Manter atividades normais"},
                {"name": "MAPA 24h", "tuss_code": "40303005", "category": "Cardiologia",
                 "description": "Monitoramento da pressão arterial", "preparation_instructions": "Manter atividades normais"},
                
                # Neurologia
                {"name": "EEG", "tuss_code": "40304001", "category": "Neurologia",
                 "description": "Eletroencefalograma", "preparation_instructions": "Cabelo limpo, sem gel"},
                {"name": "EMG", "tuss_code": "40304002", "category": "Neurologia",
                 "description": "Eletromiografia", "preparation_instructions": "Evitar cremes na pele"},
                
                # Ginecologia
                {"name": "Ultrassom transvaginal", "tuss_code": "40305001", "category": "Ginecologia",
                 "description": "Ultrassom ginecológico", "preparation_instructions": "Bexiga vazia"},
                {"name": "Colposcopia", "tuss_code": "40305002", "category": "Ginecologia",
                 "description": "Exame do colo do útero", "preparation_instructions": "Evitar relações 48h antes"},
                
                # Urologia
                {"name": "Ultrassom de próstata", "tuss_code": "40306001", "category": "Urologia",
                 "description": "Ultrassom da próstata", "preparation_instructions": "Bexiga cheia"},
                {"name": "Urofluxometria", "tuss_code": "40306002", "category": "Urologia",
                 "description": "Teste de fluxo urinário", "preparation_instructions": "Bexiga cheia"},
                
                # Oftalmologia
                {"name": "Fundoscopia", "tuss_code": "40307001", "category": "Oftalmologia",
                 "description": "Exame de fundo de olho", "preparation_instructions": "Dilatação pupilar"},
                {"name": "Campo visual", "tuss_code": "40307002", "category": "Oftalmologia",
                 "description": "Perimetria", "preparation_instructions": "Não necessário"},
                
                # Ortopedia
                {"name": "Raio-X de joelho", "tuss_code": "40308001", "category": "Ortopedia",
                 "description": "Radiografia do joelho", "preparation_instructions": "Remover objetos metálicos"},
                {"name": "Raio-X de ombro", "tuss_code": "40308002", "category": "Ortopedia",
                 "description": "Radiografia do ombro", "preparation_instructions": "Remover objetos metálicos"},
                {"name": "Densitometria óssea", "tuss_code": "40308003", "category": "Ortopedia",
                 "description": "DEXA scan", "preparation_instructions": "Remover objetos metálicos"},
            ]
            
            for exam_data in exams:
                exam = StandardExam(**exam_data)
                session.add(exam)
            
            await session.commit()
            print("✅ Standard exams created successfully")
            print(f"📊 Created {len(exams)} exams across {len(categories)} categories")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Error populating database: {e}")
            raise
        finally:
            await engine.dispose()

if __name__ == "__main__":
    print("🚀 Starting exam database population...")
    asyncio.run(populate_exam_database())
    print("✅ Exam database population completed!")
