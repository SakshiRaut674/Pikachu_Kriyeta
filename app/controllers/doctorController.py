from fastapi import HTTPException, status, Depends,UploadFile, File, Form
from fastapi.responses import JSONResponse
from app.models.doctor_model import Doctor
from app.middlewares.authMiddleware import get_current_doctor,get_current_user
from pydantic import BaseModel
from typing import Optional, List, Dict
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
import json
from datetime import datetime
from fastapi import Response
import cloudinary.uploader

# ✅ Profile Update Model with string IDs for active_patients
class ProfileUpdateModel(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    gender: Optional[str] = None
    specialization: Optional[str] = None
    profile_photo: Optional[str] = None
    education: Optional[List[Dict]] = None
    experience: Optional[List[Dict]] = None
    certifications: Optional[List[Dict]] = None
    projects: Optional[List[Dict]] = None
    skills: Optional[List[str]] = None
    preferences: Optional[Dict] = None
    verified_by_admin: Optional[bool] = None
    symptoms: Optional[List[str]] = None
    active_patients: Optional[List[str]] = None  # Using string IDs



async def update_doctor_profile(
    profile_data: ProfileUpdateModel,
    current_user: dict = Depends(get_current_doctor)
):
    # Get user ID from current authenticated user
    doctor_user_id = current_user["_id"]
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
        updated_user = await db["doctors"].find_one_and_update(
            {"_id": doctor_user_id},
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
async def send_doctor_user_details(current_user: dict = Depends(get_current_doctor)):
    # No need for conversion, just use the active_patients as they are
    # If they're already strings, great. If they're ObjectIds, convert them.
    active_patients = current_user.get("active_patients", [])
    
    # Ensure all active_patients are strings
    active_patients_str = []
    for pid in active_patients:
        if isinstance(pid, ObjectId):
            active_patients_str.append(str(pid))
        elif isinstance(pid, str):
            active_patients_str.append(pid)
    
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
                "active_patients": active_patients_str,  # Use the string list
                "verified_by_admin": current_user.get("verified_by_admin"),
                "specialization": current_user.get("specialization"),
                "symptoms":current_user.get("symptoms",[])
            }
        },
    )

async def get_active_patients(current_doctor: dict = Depends(get_current_doctor)):
    """
    Get all active patients of the currently logged-in doctor.
    """
    try:
        db = get_db()
        doctor_id = current_doctor["_id"]
        
        # Get the list of patient IDs from the doctor record
        patient_ids = current_doctor.get("active_patients", [])
        
        if not patient_ids:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "No active patients found",
                    "patients": []
                }
            )
        
        # Convert string IDs to ObjectId if they're stored as strings
        object_ids = [ObjectId(pid) if isinstance(pid, str) else pid for pid in patient_ids]
        
        # Fetch all patients from the database
        patients = []
        async for patient in db["users"].find({"_id": {"$in": object_ids}}):
            patients.append(patient)
        
        # Serialize the patient records to make them JSON serializable
        serialized_patients = serialize_document(patients)
        
        # Remove sensitive fields from each patient record
        for patient in serialized_patients:
            patient.pop("password", None)
            patient.pop("otp", None)
            patient.pop("otpExpiry", None)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Found {len(serialized_patients)} active patient(s)",
                "patients": serialized_patients
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve active patients: {str(e)}"
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


async def upload_emr_record(
    user_id: str = Form(...),
    appointment_id: str = Form(None),
    notes: str = Form(""),
    file: UploadFile = File(...),
    current_doctor: dict = Depends(get_current_doctor)
):
    db = get_db()
    
    # Check patient is in doctor's active list
    if user_id not in current_doctor.get("active_patients", []):
        raise HTTPException(status_code=403, detail="Patient not in your active list")
    
    # Upload to Cloudinary
    upload_result = cloudinary.uploader.upload(file.file, resource_type="auto")
    
    record = {
        "user_id": user_id,
        "doctor_id": current_doctor["_id"],
        "appointment_id": appointment_id if appointment_id else None,
        "file_url": upload_result["secure_url"],
        "file_type": upload_result["format"],
        "notes": notes,
        "created_at": datetime.utcnow()
    }
    
    result = await db["emr_records"].insert_one(record)
    
    # Get the inserted record and serialize it
    inserted_record = await db["emr_records"].find_one({"_id": result.inserted_id})
    serialized_record = serialize_document(inserted_record)
    
    return {"message": "EMR record uploaded", "record": serialized_record}



async def get_emr_records_for_user(
    user_id: str,
    current_user=Depends(get_current_user)  # or get_current_doctor depending on route
):
    db = get_db()
    
    is_doctor = "specialization" in current_user
    requester_id = current_user["_id"]
    
    if is_doctor:
        # Validate patient is in active list
        doctor = current_user
        if user_id not in doctor.get("active_patients", []):
            raise HTTPException(status_code=403, detail="Access denied to patient's records")
    else:
        if str(requester_id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied to another user's EMR")
    
    # Convert user_id to ObjectId for querying
    try:
        user_object_id = ObjectId(user_id)
    except:
        # Handle invalid ObjectId format
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    emrs = []
    async for doc in db["emr_records"].find({"user_id": user_id}).sort("created_at", -1):
        emrs.append(doc)
    
    # Serialize the EMR records to make them JSON serializable
    serialized_emrs = serialize_document(emrs)
    
    return {"records": serialized_emrs}


async def get_emr_records_for_doctor(
    user_id: str,
    current_user=Depends(get_current_doctor)  # or get_current_doctor depending on route
):
    db = get_db()
    
    is_doctor = "specialization" in current_user
    requester_id = current_user["_id"]
    
    if is_doctor:
        # Validate patient is in active list
        doctor = current_user
        if user_id not in doctor.get("active_patients", []):
            raise HTTPException(status_code=403, detail="Access denied to patient's records")
    else:
        if str(requester_id) != user_id:
            raise HTTPException(status_code=403, detail="Access denied to another user's EMR")
    
    # Convert user_id to ObjectId for querying
    try:
        user_object_id = ObjectId(user_id)
    except:
        # Handle invalid ObjectId format
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    emrs = []
    async for doc in db["emr_records"].find({"user_id": user_id}).sort("created_at", -1):
        emrs.append(doc)
    
    # Serialize the EMR records to make them JSON serializable
    serialized_emrs = serialize_document(emrs)
    
    return {"records": serialized_emrs}