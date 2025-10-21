"""CID-10 code search API endpoints"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List
from app.db.session import get_db_session
from app.core.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(tags=["CID-10 Codes"])


class CID10Code(BaseModel):
    id: int
    code: str
    description: str
    category: str | None
    type: str | None

    class Config:
        from_attributes = True


class CID10SearchResponse(BaseModel):
    results: List[CID10Code]
    total: int


@router.get("/search", response_model=CID10SearchResponse)
async def search_cid10_codes(
    query: str = Query(..., min_length=1, description="Search query (code or description)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """
    Search CID-10 codes by code or description.
    
    - **query**: Search term (can be code like "J06" or text like "sinusite")
    - **limit**: Maximum results to return (1-100, default 20)
    
    Returns matching CID-10 codes sorted by relevance.
    """
    from app.models.database import CID10CodeDB
    
    # Normalize search query
    search_term = query.strip().upper()
    
    # Build search conditions
    # Priority: exact code match > code starts with > description contains
    stmt = select(CID10CodeDB).where(CID10CodeDB.active == True)
    
    if search_term:
        # Search in both code and description
        stmt = stmt.where(
            or_(
                CID10CodeDB.code.ilike(f"{search_term}%"),  # Code starts with
                CID10CodeDB.description.ilike(f"%{search_term}%"),  # Description contains
            )
        )
    
    # Order by relevance: exact match first, then by code
    stmt = stmt.order_by(
        # Exact code match first
        func.lower(CID10CodeDB.code) == search_term.lower(),
        # Then code starts with query
        CID10CodeDB.code.ilike(f"{search_term}%").desc(),
        # Then alphabetically by code
        CID10CodeDB.code
    ).limit(limit)
    
    result = await db.execute(stmt)
    codes = result.scalars().all()
    
    return CID10SearchResponse(
        results=[
            CID10Code(
                id=code.id,
                code=code.code,
                description=code.description,
                category=code.category,
                type=code.type
            )
            for code in codes
        ],
        total=len(codes)
    )


@router.get("/{code}", response_model=CID10Code)
async def get_cid10_by_code(
    code: str,
    db: AsyncSession = Depends(get_db_session),
    current_user = Depends(get_current_user),
):
    """
    Get a specific CID-10 code by its code.
    
    - **code**: The CID-10 code (e.g., "J06.9")
    """
    from app.models.database import CID10CodeDB
    
    stmt = select(CID10CodeDB).where(
        CID10CodeDB.code == code.upper(),
        CID10CodeDB.active == True
    )
    
    result = await db.execute(stmt)
    cid_code = result.scalar_one_or_none()
    
    if not cid_code:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"CID-10 code '{code}' not found")
    
    return CID10Code(
        id=cid_code.id,
        code=cid_code.code,
        description=cid_code.description,
        category=cid_code.category,
        type=cid_code.type
    )

