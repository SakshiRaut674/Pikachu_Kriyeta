from fastapi import APIRouter, Depends, Query, Body
from typing import Dict, List, Optional
from app.controllers.doctorController import (
    update_doctor_profile, 
    send_doctor_user_details,
    get_active_patients,ProfileUpdateModel,upload_emr_record,get_emr_records_for_doctor
)
from app.middlewares.authMiddleware import get_current_doctor
router = APIRouter(tags=["Doctor"])

# ✅ Inject authenticated user
router.post("/upload-emr")(upload_emr_record)
router.put("/update-doctor-profile")(update_doctor_profile)
router.get("/emr/records-for-doctor")(get_emr_records_for_doctor)
router.get("/doctor-me", dependencies=[Depends(get_current_doctor)])(send_doctor_user_details)
# Get active patients route - requires doctor authentication
@router.get("/active-patients")
async def active_patients(current_doctor=Depends(get_current_doctor)):
    return await get_active_patients(current_doctor)

# Doctor scheduling routes
@router.put("/update-schedule")
async def update_schedule(
    schedule_data: Dict[str, List[str]] = Body(..., 
        example={
            "monday": ["09:00-12:00", "15:00-18:00"],
            "tuesday": ["09:00-12:00"],
            "wednesday": [],
            "thursday": ["10:00-14:00"],
            "friday": ["09:00-12:00", "13:00-15:00"],
            "saturday": ["10:00-13:00"],
            "sunday": []
        },
        description="Weekly schedule with time ranges in HH:MM-HH:MM format"
    ),
    current_doctor=Depends(get_current_doctor)
):
    from app.controllers.appointmentController import update_doctor_availability
    return await update_doctor_availability(schedule_data, current_doctor)

@router.put("/slot-duration")
async def update_slot_duration(
    duration: int = Body(..., ge=5, le=60, description="Duration of each appointment slot in minutes"),
    current_doctor=Depends(get_current_doctor)
):
    from app.database.database import get_db
    from pymongo import ReturnDocument
    
    db = get_db()
    doctor_id = current_doctor["_id"]
    
    updated_doctor = await db["doctors"].find_one_and_update(
        {"_id": doctor_id},
        {"$set": {"time_slot_duration_minutes": duration}},
        return_document=ReturnDocument.AFTER
    )
    
    return {
        "message": f"Appointment slot duration updated to {duration} minutes",
        "time_slot_duration_minutes": updated_doctor.get("time_slot_duration_minutes", duration)
    }

@router.put("/max-patients")
async def update_max_patients(
    max_patients: int = Body(..., ge=1, le=100, description="Maximum number of patients per day"),
    current_doctor=Depends(get_current_doctor)
):
    from app.database.database import get_db
    from pymongo import ReturnDocument
    
    db = get_db()
    doctor_id = current_doctor["_id"]
    
    updated_doctor = await db["doctors"].find_one_and_update(
        {"_id": doctor_id},
        {"$set": {"max_patients_per_day": max_patients}},
        return_document=ReturnDocument.AFTER
    )
    
    return {
        "message": f"Maximum patients per day updated to {max_patients}",
        "max_patients_per_day": updated_doctor.get("max_patients_per_day", max_patients)
    }