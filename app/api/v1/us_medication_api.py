"""
US Medication API Endpoints
Integration with US pharmaceutical databases
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
import asyncio

from app.core.auth import get_current_user
from app.models.database import User
from app.services.us_medication_api import (
    search_medications_endpoint,
    get_interactions_endpoint,
    get_medication_details_endpoint,
    search_alternatives_endpoint,
    validate_dosage_endpoint
)

router = APIRouter(prefix="/us-medication", tags=["US Medication API"])

@router.get("/search")
async def search_medications(
    name: str = Query(..., description="Medication name to search"),
    current_user: User = Depends(get_current_user)
):
    """Search medications in US FDA database"""
    try:
        results = await search_medications_endpoint(name)
        return {
            "medications": results,
            "total": len(results),
            "search_term": name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching medications: {str(e)}")

@router.get("/interactions")
async def get_drug_interactions(
    medications: str = Query(..., description="Comma-separated list of medication names"),
    current_user: User = Depends(get_current_user)
):
    """Get drug interactions for a list of medications"""
    try:
        medication_list = [med.strip() for med in medications.split(",")]
        interactions = await get_interactions_endpoint(medication_list)
        return {
            "interactions": interactions,
            "medications": medication_list,
            "total_interactions": len(interactions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting interactions: {str(e)}")

@router.get("/details/{ndc}")
async def get_medication_details(
    ndc: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed medication information by NDC"""
    try:
        details = await get_medication_details_endpoint(ndc)
        if not details:
            raise HTTPException(status_code=404, detail="Medication not found")
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting medication details: {str(e)}")

@router.get("/alternatives")
async def search_medication_alternatives(
    name: str = Query(..., description="Medication name to find alternatives for"),
    current_user: User = Depends(get_current_user)
):
    """Search for alternative medications"""
    try:
        alternatives = await search_alternatives_endpoint(name)
        return {
            "alternatives": alternatives,
            "original_medication": name,
            "total_alternatives": len(alternatives)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching alternatives: {str(e)}")

@router.get("/validate-dosage")
async def validate_medication_dosage(
    medication: str = Query(..., description="Medication name"),
    dosage: str = Query(..., description="Dosage to validate"),
    current_user: User = Depends(get_current_user)
):
    """Validate medication dosage against FDA guidelines"""
    try:
        validation = await validate_dosage_endpoint(medication, dosage)
        return validation
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating dosage: {str(e)}")

@router.get("/health")
async def check_api_health():
    """Check if US medication APIs are accessible"""
    try:
        # Test FDA API connectivity
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://api.fda.gov/drug/label.json?limit=1")
            fda_status = "online" if response.status_code == 200 else "offline"
        
        # Test RxNav API connectivity
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://rxnav.nlm.nih.gov/REST/drugs.json?name=aspirin")
            rxnav_status = "online" if response.status_code == 200 else "offline"
        
        return {
            "status": "healthy" if fda_status == "online" and rxnav_status == "online" else "degraded",
            "apis": {
                "fda": fda_status,
                "rxnav": rxnav_status
            },
            "timestamp": "2024-01-01T00:00:00Z"  # This would be actual timestamp
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "apis": {
                "fda": "offline",
                "rxnav": "offline"
            }
        }
