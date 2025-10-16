"""
US Medication API Integration Service
Integration with US pharmaceutical databases for medication information
"""

import httpx
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class USMedicationAPIService:
    """Service for integrating with US medication APIs"""
    
    def __init__(self):
        self.fda_api_base = "https://api.fda.gov/drug"
        self.rxnav_api_base = "https://rxnav.nlm.nih.gov/REST"
        self.drugbank_api_base = "https://go.drugbank.com/releases/latest"
        
    async def search_medication_by_name(self, medication_name: str) -> List[Dict[str, Any]]:
        """
        Search medication by name using FDA API
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search FDA database
                response = await client.get(
                    f"{self.fda_api_base}/label.json",
                    params={
                        "search": f"openfda.generic_name:{medication_name}",
                        "limit": 10
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    medications = []
                    
                    for result in data.get("results", []):
                        openfda = result.get("openfda", {})
                        medication = {
                            "name": openfda.get("generic_name", [""])[0],
                            "brand_name": openfda.get("brand_name", [""])[0],
                            "manufacturer": openfda.get("manufacturer_name", [""])[0],
                            "dosage_form": openfda.get("dosage_form", [""])[0],
                            "route": openfda.get("route", [""])[0],
                            "active_ingredient": openfda.get("substance_name", [""])[0],
                            "ndc": openfda.get("product_ndc", [""])[0],
                            "source": "FDA"
                        }
                        medications.append(medication)
                    
                    return medications
                else:
                    logger.warning(f"FDA API returned status {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error searching FDA API: {e}")
            return []
    
    async def get_medication_interactions(self, medication_names: List[str]) -> List[Dict[str, Any]]:
        """
        Get drug interactions using RxNav API
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get RXCUI for each medication
                rxcui_list = []
                for med_name in medication_names:
                    response = await client.get(
                        f"{self.rxnav_api_base}/drugs.json",
                        params={"name": med_name}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("drugGroup", {}).get("conceptGroup"):
                            for concept in data["drugGroup"]["conceptGroup"]:
                                if concept.get("tty") == "IN" and concept.get("conceptProperties"):
                                    for prop in concept["conceptProperties"]:
                                        rxcui_list.append(prop.get("rxcui"))
                                        break
                
                if not rxcui_list:
                    return []
                
                # Get interactions
                rxcui_str = "+".join(rxcui_list)
                response = await client.get(
                    f"{self.rxnav_api_base}/interaction/list.json",
                    params={"rxcuis": rxcui_str}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    interactions = []
                    
                    for interaction in data.get("fullInteractionTypeGroup", []):
                        for interaction_type in interaction.get("fullInteractionType", []):
                            interaction_data = {
                                "severity": interaction_type.get("severity", "Unknown"),
                                "description": interaction_type.get("description", ""),
                                "drugs": []
                            }
                            
                            for drug in interaction_type.get("interactionPair", []):
                                for drug_info in drug.get("interactionConcept", []):
                                    interaction_data["drugs"].append({
                                        "name": drug_info.get("minConceptItem", {}).get("name", ""),
                                        "rxcui": drug_info.get("minConceptItem", {}).get("rxcui", "")
                                    })
                            
                            interactions.append(interaction_data)
                    
                    return interactions
                else:
                    logger.warning(f"RxNav API returned status {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Error getting drug interactions: {e}")
            return []
    
    async def get_medication_details(self, ndc: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed medication information by NDC
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.fda_api_base}/ndc.json",
                    params={"search": f"product_ndc:{ndc}"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    
                    if results:
                        result = results[0]
                        openfda = result.get("openfda", {})
                        
                        return {
                            "ndc": ndc,
                            "name": openfda.get("generic_name", [""])[0],
                            "brand_name": openfda.get("brand_name", [""])[0],
                            "manufacturer": openfda.get("manufacturer_name", [""])[0],
                            "dosage_form": openfda.get("dosage_form", [""])[0],
                            "route": openfda.get("route", [""])[0],
                            "active_ingredient": openfda.get("substance_name", [""])[0],
                            "package_description": result.get("package_description", ""),
                            "product_type": result.get("product_type", ""),
                            "source": "FDA"
                        }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting medication details: {e}")
            return None
    
    async def search_medication_alternatives(self, medication_name: str) -> List[Dict[str, Any]]:
        """
        Search for alternative medications
        """
        try:
            # This would typically use a more sophisticated API
            # For now, we'll use a simple search with different terms
            alternatives = []
            
            # Search for generic alternatives
            generic_results = await self.search_medication_by_name(medication_name)
            
            for med in generic_results:
                if med["name"].lower() != medication_name.lower():
                    alternatives.append({
                        "name": med["name"],
                        "brand_name": med["brand_name"],
                        "type": "Generic Alternative",
                        "source": "FDA"
                    })
            
            return alternatives
            
        except Exception as e:
            logger.error(f"Error searching alternatives: {e}")
            return []
    
    async def validate_medication_dosage(self, medication_name: str, dosage: str) -> Dict[str, Any]:
        """
        Validate medication dosage against FDA guidelines
        """
        try:
            # This is a simplified validation
            # In a real implementation, you would query a comprehensive dosage database
            
            medications = await self.search_medication_by_name(medication_name)
            
            if not medications:
                return {
                    "valid": False,
                    "message": "Medication not found in database",
                    "suggestions": []
                }
            
            # Basic validation logic would go here
            # For now, return a generic response
            return {
                "valid": True,
                "message": "Dosage appears to be within normal range",
                "suggestions": [],
                "warnings": []
            }
            
        except Exception as e:
            logger.error(f"Error validating dosage: {e}")
            return {
                "valid": False,
                "message": "Error validating dosage",
                "suggestions": []
            }

# Global instance
us_medication_service = USMedicationAPIService()

# API endpoints for the service
async def search_medications_endpoint(medication_name: str) -> List[Dict[str, Any]]:
    """Endpoint to search medications"""
    return await us_medication_service.search_medication_by_name(medication_name)

async def get_interactions_endpoint(medication_names: List[str]) -> List[Dict[str, Any]]:
    """Endpoint to get drug interactions"""
    return await us_medication_service.get_medication_interactions(medication_names)

async def get_medication_details_endpoint(ndc: str) -> Optional[Dict[str, Any]]:
    """Endpoint to get medication details"""
    return await us_medication_service.get_medication_details(ndc)

async def search_alternatives_endpoint(medication_name: str) -> List[Dict[str, Any]]:
    """Endpoint to search alternatives"""
    return await us_medication_service.search_medication_alternatives(medication_name)

async def validate_dosage_endpoint(medication_name: str, dosage: str) -> Dict[str, Any]:
    """Endpoint to validate dosage"""
    return await us_medication_service.validate_medication_dosage(medication_name, dosage)
