from fastapi import HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from app.models.user_model import User
from app.middlewares.authMiddleware import get_current_user
from pydantic import BaseModel
from typing import Optional,List, Dict
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
import json
from datetime import datetime
import re  # Add this missing import

class ProfileUpdateModel(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    gender: Optional[str] = None
    profile_photo: Optional[str] = None
    query_message: Optional[str] = None

# Helper function to make MongoDB documents JSON serializable
def serialize_document(doc):
    if isinstance(doc, dict):
        return {k: serialize_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

async def update_profile(
    profile_data: ProfileUpdateModel,
    current_user: dict = Depends(get_current_user)
):
    # Get user ID from current authenticated user
    user_id = current_user["_id"]
    db = get_db()
    
    # Create update dictionary with only provided fields
    update_data = {k: v for k, v in profile_data.dict(exclude_unset=True).items() if v is not None}
    
    # If no fields to update, return early
    if not update_data:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "No fields to update"}
        )
    
    try:
        # Update user in database
        updated_user = await db["users"].find_one_and_update(
            {"_id": user_id},
            {"$set": update_data},
            return_document=ReturnDocument.AFTER
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Convert document to JSON serializable format
        serialized_user = serialize_document(updated_user)
        
        # Remove sensitive fields if any
        serialized_user.pop("otp", None)
        serialized_user.pop("otpExpiry", None)
        serialized_user.pop("password", None)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Profile updated successfully",
                "user": serialized_user
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )
# Send user details
async def send_user_details(current_user: dict = Depends(get_current_user)):
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "User found",
            "user": {
                "_id": str(current_user["_id"]),
                "mobile": current_user["mobile"],
                "verified": current_user.get("verified", False),
                "name": current_user.get("name"),
                "email": current_user.get("email"),
                "age": current_user.get("age"),
                "weight": current_user.get("weight"),
            }
        },
    )


# Helper function to make MongoDB documents JSON serializable
def serialize_document(doc):
    if isinstance(doc, dict):
        return {k: serialize_document(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [serialize_document(item) for item in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    elif isinstance(doc, datetime):
        return doc.isoformat()
    else:
        return doc

async def search_doctors_by_keyword(
    keyword: str = Query(..., description="Keyword to search in name, specialization, or symptoms"),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for doctors by keyword, matching against name, specialization, or symptoms.
    Returns a list of doctors matching the search criteria.
    """
    if not keyword or keyword.strip() == "":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": "Search keyword is required"}
        )
    
    db = get_db()
    keyword = keyword.strip()
    
    try:
        # Create a query that searches across name, specialization, and symptoms
        query = {
            "$or": [
                {"name": {"$regex": keyword, "$options": "i"}},
                {"specialization": {"$regex": keyword, "$options": "i"}},
                {"symptoms": {"$regex": keyword, "$options": "i"}}
            ]
        }
        
        # Execute the query
        doctors = []
        async for doc in db["doctors"].find(query).limit(100):
            doctors.append(doc)
        
        if not doctors:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "No doctors found matching your search criteria"}
            )
        
        # Use the serialize_document function to handle ObjectId conversion
        serialized_doctors = serialize_document(doctors)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Found {len(serialized_doctors)} doctor(s) matching '{keyword}'",
                "doctors": serialized_doctors
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search doctors: {str(e)}"
        )
    
