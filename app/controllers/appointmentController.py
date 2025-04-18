from fastapi import HTTPException, status, Depends, Query,status as http_status 
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from pymongo import ReturnDocument
from bson import ObjectId
from app.database.database import get_db
from app.middlewares.authMiddleware import get_current_user, get_current_doctor
from datetime import datetime, timedelta
import calendar

# Model for appointment creation
class AppointmentCreateModel(BaseModel):
    doctor_id: str
    appointment_date: str  # Format: YYYY-MM-DD
    appointment_time: str  # Format: HH:MM (24-hour format)
    reason: str
    
    @validator('appointment_date')
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError("Invalid date format. Use YYYY-MM-DD")
    
    @validator('appointment_time')
    def validate_time(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
            return v
        except ValueError:
            raise ValueError("Invalid time format. Use HH:MM (24-hour format)")

# Model for listing appointments
class AppointmentResponseModel(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    doctor_id: str
    doctor_name: Optional[str] = None
    user_name: Optional[str] = None
    appointment_date: str
    appointment_time: str
    reason: str
    status: str
    created_at: datetime
    
    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }

# Helper function to check if a time slot is available
async def is_slot_available(db, doctor_id, date_str, time_str):
    # Convert to ObjectId
    doctor_obj_id = ObjectId(doctor_id)
    
    # Get the doctor
    doctor = await db["doctors"].find_one({"_id": doctor_obj_id})
    if not doctor:
        return False, "Doctor not found"
    
    # Get day of week
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = calendar.day_name[date_obj.weekday()].lower()
    except ValueError:
        return False, "Invalid date format"
    
    # Check if doctor works on this day
    availability = doctor.get("availability_schedule", {}).get(day_of_week, [])
    if not availability:
        return False, f"Doctor is not available on {day_of_week.capitalize()}"
    
    # Check if the requested time is within available time slots
    time_obj = datetime.strptime(time_str, "%H:%M").time()
    slot_found = False
    
    for time_range in availability:
        start_str, end_str = time_range.split("-")
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        
        if start_time <= time_obj < end_time:
            slot_found = True
            break
    
    if not slot_found:
        return False, "Requested time is outside doctor's available hours"
    
    # Check if slot is already booked
    booked_slots = doctor.get("booked_slots", {})
    date_slots = booked_slots.get(date_str, [])
    
    if time_str in date_slots:
        return False, "This time slot is already booked"
    
    # Check if doctor has reached maximum patients for the day
    max_patients = doctor.get("max_patients_per_day", 20)
    if len(date_slots) >= max_patients:
        return False, f"Doctor has reached the maximum number of appointments ({max_patients}) for this day"
    
    # All checks passed
    return True, "Slot is available"

# Get all available time slots for a specific doctor on a specific date
async def get_available_slots(
    doctor_id: str = Query(..., description="Doctor ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    current_user: dict = Depends(get_current_user)
):
    try:
        db = get_db()
        doctor_obj_id = ObjectId(doctor_id)
        
        # Get the doctor
        doctor = await db["doctors"].find_one({"_id": doctor_obj_id})
        if not doctor:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Doctor not found"}
            )
        
        # Get day of week
        try:
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            day_of_week = calendar.day_name[date_obj.weekday()].lower()
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Invalid date format. Use YYYY-MM-DD"}
            )
        
        # Get available time ranges for this day
        availability = doctor.get("availability_schedule", {}).get(day_of_week, [])
        if not availability:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Doctor is not available on {day_of_week.capitalize()}",
                    "available_slots": []
                }
            )
        
        # Get already booked slots for this date
        booked_slots = doctor.get("booked_slots", {}).get(date, [])
        
        # Generate all possible time slots based on doctor's schedule
        all_slots = []
        slot_duration = doctor.get("time_slot_duration_minutes", 15)
        
        for time_range in availability:
            start_str, end_str = time_range.split("-")
            start_time = datetime.strptime(start_str, "%H:%M")
            end_time = datetime.strptime(end_str, "%H:%M")
            
            current_slot = start_time
            while current_slot < end_time:
                slot_str = current_slot.strftime("%H:%M")
                if slot_str not in booked_slots:
                    all_slots.append(slot_str)
                current_slot += timedelta(minutes=slot_duration)
        
        # Check if doctor has reached maximum patients
        max_patients = doctor.get("max_patients_per_day", 20)
        if len(booked_slots) >= max_patients:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": f"Doctor has reached maximum capacity ({max_patients}) for this day",
                    "available_slots": []
                }
            )
        
        # Sort slots
        all_slots.sort()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Available slots for {date}",
                "doctor_name": doctor.get("name", ""),
                "specialization": doctor.get("specialization", ""),
                "date": date,
                "day": day_of_week.capitalize(),
                "available_slots": all_slots
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get available slots: {str(e)}"
        )

# Book an appointment
async def book_appointment(
    appointment_data: AppointmentCreateModel,
    current_user: dict = Depends(get_current_user)
):
    try:
        db = get_db()
        user_id = current_user["_id"]
        
        # Check if doctor exists
        try:
            doctor_obj_id = ObjectId(appointment_data.doctor_id)
        except:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Invalid doctor ID format"}
            )
        
        doctor = await db["doctors"].find_one({"_id": doctor_obj_id})
        if not doctor:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Doctor not found"}
            )
        
        # Verify that the doctor is approved by admin
        if not doctor.get("verified_by_admin", False):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "This doctor is not verified by admin and cannot accept appointments"}
            )
        
        # Check if slot is available
        is_available, message = await is_slot_available(
            db, 
            appointment_data.doctor_id, 
            appointment_data.appointment_date, 
            appointment_data.appointment_time
        )
        
        if not is_available:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": message}
            )
        
        # Create appointment object
        appointment_id = ObjectId()
        appointment = {
            "_id": appointment_id,
            "user_id": user_id,
            "doctor_id": doctor_obj_id,
            "appointment_date": appointment_data.appointment_date,
            "appointment_time": appointment_data.appointment_time,
            "reason": appointment_data.reason,
            "status": "scheduled",  # scheduled, completed, cancelled
            "created_at": datetime.now()
        }
        
        # Insert appointment
        await db["appointments"].insert_one(appointment)
        
        # Update user's active_appointments
        await db["users"].update_one(
            {"_id": user_id},
            {"$push": {"active_appointments": str(appointment_id)}}
        )
        
        # Update doctor's active_patients and booked_slots
        date_key = f"booked_slots.{appointment_data.appointment_date}"
        await db["doctors"].update_one(
            {"_id": doctor_obj_id},
            {
                "$addToSet": {
                    "active_patients": str(user_id),
                    date_key: appointment_data.appointment_time
                }
            }
        )
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "message": "Appointment booked successfully",
                "appointment_id": str(appointment_id),
                "doctor_name": doctor.get("name", ""),
                "appointment_date": appointment_data.appointment_date,
                "appointment_time": appointment_data.appointment_time
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book appointment: {str(e)}"
        )

# Get user's appointments
# Get user's appointments
async def get_user_appointments(
    status_filter: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled)"),
    current_user: dict = Depends(get_current_user)
):
    try:
        db = get_db()
        user_id = current_user["_id"]
        
        # Build query
        query = {"user_id": user_id}
        if status_filter:
            query["status"] = status_filter
        
        # Fetch appointments
        appointments = []
        async for appt in db["appointments"].find(query).sort("appointment_date", 1):
            doctor = await db["doctors"].find_one({"_id": appt["doctor_id"]})
            doctor_name = doctor.get("name", "Unknown") if doctor else "Unknown"
            appt_with_name = {**appt, "doctor_name": doctor_name}
            appointments.append(serialize_document(appt_with_name))
        
        return JSONResponse(
            status_code=http_status.HTTP_200_OK,
            content={
                "message": f"Found {len(appointments)} appointment(s)",
                "appointments": appointments
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get appointments: {str(e)}"
        )   
# Get doctor's appointments
async def get_doctor_appointments(
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    appointment_status: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled)"),
    current_doctor: dict = Depends(get_current_doctor)
):
    try:
        db = get_db()
        doctor_id = current_doctor["_id"]
        
        # Build query
        query = {"doctor_id": doctor_id}
        if appointment_status:
            query["status"] = appointment_status
        if date:
            query["appointment_date"] = date
        
        # Fetch appointments
        appointments = []
        async for appt in db["appointments"].find(query).sort("appointment_date", 1):
            user = await db["users"].find_one({"_id": appt["user_id"]})
            user_name = user.get("name", "Unknown") if user else "Unknown"
            appt_with_name = {**appt, "user_name": user_name}
            appointments.append(serialize_document(appt_with_name))
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Found {len(appointments)} appointment(s)",
                "appointments": appointments
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get appointments: {str(e)}"
        )

# Update appointment status (for both doctor and patient)
async def update_appointment_status(
    appointment_id: str,
    status: str = Query(..., description="New status (scheduled, completed, cancelled)"),
    current_user: dict = Depends(get_current_user)
):
    try:
        db = get_db()
        user_id = current_user["_id"]
        
        # Validate status
        valid_statuses = ["scheduled", "completed", "cancelled"]
        if status not in valid_statuses:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": f"Invalid status. Must be one of: {', '.join(valid_statuses)}"}
            )
        
        # Convert to ObjectId
        try:
            appt_obj_id = ObjectId(appointment_id)
        except:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": "Invalid appointment ID format"}
            )
        
        # Get the appointment
        appointment = await db["appointments"].find_one({"_id": appt_obj_id})
        if not appointment:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"message": "Appointment not found"}
            )
        
        # Check if user is authorized (either the patient or the doctor)
        is_patient = str(appointment["user_id"]) == str(user_id)
        
        # Get doctor ID for later use
        doctor_id = appointment["doctor_id"]
        
        # If not patient, check if user is a doctor
        is_doctor = False
        if not is_patient:
            doctor = await db["doctors"].find_one({"_id": user_id})
            is_doctor = doctor is not None and str(doctor["_id"]) == str(doctor_id)
        
        if not (is_patient or is_doctor):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"message": "You are not authorized to modify this appointment"}
            )
        
        # Update appointment status
        updated_appointment = await db["appointments"].find_one_and_update(
            {"_id": appt_obj_id},
            {"$set": {"status": status}},
            return_document=ReturnDocument.AFTER
        )
        
        # If cancelled, free up the slot in doctor's booked_slots
        if status == "cancelled" and appointment["status"] != "cancelled":
            date_key = f"booked_slots.{appointment['appointment_date']}"
            await db["doctors"].update_one(
                {"_id": doctor_id},
                {"$pull": {date_key: appointment["appointment_time"]}}
            )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": f"Appointment status updated to '{status}'",
                "appointment": serialize_document(updated_appointment)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update appointment status: {str(e)}"
        )

# Update doctor's availability schedule
async def update_doctor_availability(
    availability: Dict[str, List[str]],
    current_doctor: dict = Depends(get_current_doctor)
):
    try:
        db = get_db()
        doctor_id = current_doctor["_id"]
        
        # Validate format
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day, slots in availability.items():
            if day not in days:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"message": f"Invalid day: {day}. Must be one of: {', '.join(days)}"}
                )
            
            # Validate time slots format
            for slot in slots:
                if not isinstance(slot, str) or "-" not in slot:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"message": f"Invalid time slot format: {slot}. Must be in format 'HH:MM-HH:MM'"}
                    )
                
                try:
                    start_str, end_str = slot.split("-")
                    datetime.strptime(start_str, "%H:%M")
                    datetime.strptime(end_str, "%H:%M")
                except ValueError:
                    return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"message": f"Invalid time format in slot: {slot}. Use HH:MM-HH:MM (24-hour format)"}
                    )
        
        # Update doctor's availability
        updated_doctor = await db["doctors"].find_one_and_update(
            {"_id": doctor_id},
            {"$set": {"availability_schedule": availability}},
            return_document=ReturnDocument.AFTER
        )
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Availability schedule updated successfully",
                "availability_schedule": updated_doctor.get("availability_schedule", {})
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update availability: {str(e)}"
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