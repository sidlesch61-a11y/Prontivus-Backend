"""
API endpoints for standardized exam database
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List, Optional
import uuid

from app.db.session import get_db_session
from app.core.auth import get_current_user
from app.models.exam_database import StandardExam, ExamCategory
from app.models.database import User

router = APIRouter(prefix="/exam-database", tags=["Exam Database"])

@router.get("/exams", response_model=List[dict])
async def search_exams(
    q: Optional[str] = Query(None, description="Search query for exam name or TUSS code"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, le=100, description="Maximum number of results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Search standardized exams by name or TUSS code"""
    try:
        query = select(StandardExam).where(StandardExam.is_active == True)
        
        if q:
            search_term = f"%{q}%"
            query = query.where(
                or_(
                    StandardExam.name.ilike(search_term),
                    StandardExam.tuss_code.ilike(search_term),
                    StandardExam.description.ilike(search_term)
                )
            )
        
        if category:
            query = query.where(StandardExam.category == category)
        
        query = query.limit(limit).order_by(StandardExam.name)
        
        result = await db.execute(query)
        exams = result.scalars().all()
        
        return [
            {
                "id": str(exam.id),
                "name": exam.name,
                "tuss_code": exam.tuss_code,
                "category": exam.category,
                "description": exam.description,
                "preparation_instructions": exam.preparation_instructions,
                "normal_values": exam.normal_values
            }
            for exam in exams
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching exams: {str(e)}")

@router.get("/categories", response_model=List[dict])
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all exam categories"""
    try:
        query = select(ExamCategory).where(ExamCategory.is_active == True).order_by(ExamCategory.name)
        result = await db.execute(query)
        categories = result.scalars().all()
        
        return [
            {
                "id": str(category.id),
                "name": category.name,
                "description": category.description,
                "color": category.color
            }
            for category in categories
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching categories: {str(e)}")

@router.get("/exams/{exam_id}", response_model=dict)
async def get_exam_details(
    exam_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get detailed information about a specific exam"""
    try:
        query = select(StandardExam).where(
            and_(
                StandardExam.id == uuid.UUID(exam_id),
                StandardExam.is_active == True
            )
        )
        result = await db.execute(query)
        exam = result.scalar_one_or_none()
        
        if not exam:
            raise HTTPException(status_code=404, detail="Exam not found")
        
        return {
            "id": str(exam.id),
            "name": exam.name,
            "tuss_code": exam.tuss_code,
            "category": exam.category,
            "description": exam.description,
            "preparation_instructions": exam.preparation_instructions,
            "normal_values": exam.normal_values
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exam ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching exam details: {str(e)}")

@router.post("/exams", response_model=dict)
async def create_exam(
    exam_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Create a new standardized exam (admin only)"""
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admins can create exams")
        
        exam = StandardExam(
            name=exam_data["name"],
            tuss_code=exam_data["tuss_code"],
            category=exam_data.get("category", "General"),
            description=exam_data.get("description"),
            preparation_instructions=exam_data.get("preparation_instructions"),
            normal_values=exam_data.get("normal_values")
        )
        
        db.add(exam)
        await db.commit()
        await db.refresh(exam)
        
        return {
            "id": str(exam.id),
            "name": exam.name,
            "tuss_code": exam.tuss_code,
            "category": exam.category,
            "message": "Exam created successfully"
        }
        
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating exam: {str(e)}")

@router.get("/popular", response_model=List[dict])
async def get_popular_exams(
    limit: int = Query(20, le=50, description="Maximum number of results"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Get most commonly used exams"""
    try:
        # This would typically be based on usage statistics
        # For now, return a curated list of common exams
        common_exams = [
            "Hemograma completo",
            "Glicemia de jejum",
            "Colesterol total",
            "Triglicerídeos",
            "Creatinina",
            "Ureia",
            "TGO (AST)",
            "TGP (ALT)",
            "TSH",
            "T4 livre",
            "Raio-X de tórax",
            "Ecocardiograma",
            "Eletrocardiograma",
            "Ultrassom abdominal",
            "Tomografia computadorizada",
            "Ressonância magnética",
            "Mamografia",
            "Papanicolau",
            "PSA",
            "Teste ergométrico"
        ]
        
        query = select(StandardExam).where(
            and_(
                StandardExam.is_active == True,
                StandardExam.name.in_(common_exams)
            )
        ).limit(limit)
        
        result = await db.execute(query)
        exams = result.scalars().all()
        
        return [
            {
                "id": str(exam.id),
                "name": exam.name,
                "tuss_code": exam.tuss_code,
                "category": exam.category
            }
            for exam in exams
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching popular exams: {str(e)}")
