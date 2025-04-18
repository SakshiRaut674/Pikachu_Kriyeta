from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.controllers.appointmentController import (
    get_available_slots,
    book_appointment,
    get_user_appointments,
    get_doctor_appointments,
    update_appointment_status,
    update_doctor_availability,
)
from app.middlewares.authMiddleware import get_current_user, get_current_doctor
from app.models.appointment_model import AppointmentCreateModel

# Create router with appointments tag
router = APIRouter(tags=["Appointments"])

# Routes for patients (regular users)
@router.get("/{doctor_id}/available-slots")
async def doctor_available_slots(
    doctor_id: str,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    current_user=Depends(get_current_user)
):
    return await get_available_slots(doctor_id, date, current_user)

@router.post("/book-appointment")
async def create_appointment(
    appointment_data: AppointmentCreateModel,
    current_user=Depends(get_current_user)
):
    return await book_appointment(appointment_data, current_user)

@router.get("/my-appointments")
async def user_appointments(
    status: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled)"),
    current_user=Depends(get_current_user)
):
    return await get_user_appointments(status, current_user)

@router.put("/appointments/{appointment_id}/status")
async def update_status(
    appointment_id: str,
    status: str = Query(..., description="New status (scheduled, completed, cancelled)"),
    current_user=Depends(get_current_user)
):
    return await update_appointment_status(appointment_id, status, current_user)

# Routes for doctors
@router.get("/doctor/appointments", dependencies=[Depends(get_current_doctor)])
async def doctor_appointments(
    date: Optional[str] = Query(None, description="Filter by date (YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (scheduled, completed, cancelled)"),
    current_doctor=Depends(get_current_doctor)
):
    return await get_doctor_appointments(date, status, current_doctor)

@router.put("/doctor/availability", dependencies=[Depends(get_current_doctor)])
async def doctor_availability(
    availability_data: dict,
    current_doctor=Depends(get_current_doctor)
):
    return await update_doctor_availability(availability_data, current_doctor)