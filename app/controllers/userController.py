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
from datetime import datetime,timedelta
import calendar
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
                "gender": current_user.get("gender"),
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
    
async def search_doctors_by_keyword_with_availability(
    keyword: str = Query(..., description="Keyword to search in name, specialization, or symptoms"),
    date: Optional[str] = Query(None, description="Date to check availability (YYYY-MM-DD)"),
    time: Optional[str] = Query(None, description="Time to check availability (HH:MM)"),
    current_user: dict = Depends(get_current_user)
):
    """
    Search for doctors by keyword, matching against name, specialization, or symptoms.
    Optionally filters by availability on specified date and time.
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
        
        # Add verification filter to ensure we only return verified doctors
        query["verified_by_admin"] = True
        
        # Execute the query
        doctors = []
        async for doc in db["doctors"].find(query).limit(100):
            doctors.append(doc)
        
        if not doctors:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "No doctors found matching your search criteria"}
            )
        
        # Filter by availability if date and time are provided
        if date and time:
            try:
                # Validate date format
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                day_of_week = calendar.day_name[date_obj.weekday()].lower()
                
                # Validate time format
                time_obj = datetime.strptime(time, "%H:%M").time()
                
                # Filter doctors by availability
                available_doctors = []
                for doctor in doctors:
                    # Check if doctor works on this day
                    availability = doctor.get("availability_schedule", {}).get(day_of_week, [])
                    if not availability:
                        continue
                    
                    # Check if the requested time is within available time slots
                    is_available = False
                    for time_range in availability:
                        start_str, end_str = time_range.split("-")
                        start_time = datetime.strptime(start_str, "%H:%M").time()
                        end_time = datetime.strptime(end_str, "%H:%M").time()
                        
                        if start_time <= time_obj < end_time:
                            is_available = True
                            break
                    
                    if not is_available:
                        continue
                    
                    # Check if slot is already booked
                    booked_slots = doctor.get("booked_slots", {})
                    date_slots = booked_slots.get(date, [])
                    
                    if time in date_slots:
                        continue
                    
                    # Check if doctor has reached maximum patients for the day
                    max_patients = doctor.get("max_patients_per_day", 20)
                    if len(date_slots) >= max_patients:
                        continue
                    
                    # Doctor is available, add to result
                    available_doctors.append(doctor)
                
                # Replace the doctors list with available doctors
                doctors = available_doctors
                
                if not doctors:
                    return JSONResponse(
                        status_code=status.HTTP_404_NOT_FOUND,
                        content={"message": f"No doctors found matching your search criteria available on {date} at {time}"}
                    )
            except ValueError as e:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"message": f"Invalid date or time format: {str(e)}. Use YYYY-MM-DD for date and HH:MM for time."}
                )
        
        # Add availability information to each doctor
        for doctor in doctors:
            # Add a flag indicating if availability data was requested
            doctor["availability_checked"] = bool(date and time)
            
            # If date was provided but no specific time, get all available slots for that date
            if date and not time:
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    day_of_week = calendar.day_name[date_obj.weekday()].lower()
                    
                    # Get available time ranges for this day
                    availability = doctor.get("availability_schedule", {}).get(day_of_week, [])
                    
                    # Get already booked slots for this date
                    booked_slots = doctor.get("booked_slots", {}).get(date, [])
                    
                    # Generate all possible time slots based on doctor's schedule
                    available_slots = []
                    slot_duration = doctor.get("time_slot_duration_minutes", 15)
                    
                    for time_range in availability:
                        start_str, end_str = time_range.split("-")
                        start_time = datetime.strptime(start_str, "%H:%M")
                        end_time = datetime.strptime(end_str, "%H:%M")
                        
                        current_slot = start_time
                        while current_slot < end_time:
                            slot_str = current_slot.strftime("%H:%M")
                            if slot_str not in booked_slots:
                                available_slots.append(slot_str)
                            current_slot += timedelta(minutes=slot_duration)
                    
                    # Check if doctor has reached maximum patients
                    max_patients = doctor.get("max_patients_per_day", 20)
                    if len(booked_slots) >= max_patients:
                        available_slots = []
                    
                    # Add available slots to doctor
                    doctor["available_slots"] = sorted(available_slots)
                    doctor["available_on_date"] = bool(available_slots)
                    
                except ValueError:
                    doctor["available_slots"] = []
                    doctor["available_on_date"] = False
            
            # Remove sensitive or unnecessary fields
            doctor.pop("booked_slots", None)
            doctor.pop("active_patients", None)
        
        # Use the serialize_document function to handle ObjectId conversion
        serialized_doctors = serialize_document(doctors)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Found {len(serialized_doctors)} doctor(s) matching '{keyword}'",
                "availability_filter_applied": bool(date and time),
                "date_filter": date if date else None,
                "time_filter": time if time else None,
                "doctors": serialized_doctors
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search doctors: {str(e)}"
        )