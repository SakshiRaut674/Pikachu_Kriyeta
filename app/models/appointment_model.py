from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from bson import ObjectId
from datetime import datetime

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