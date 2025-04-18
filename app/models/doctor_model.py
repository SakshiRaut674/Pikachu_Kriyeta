# from pydantic import BaseModel, Field
# from typing import List, Optional
# from bson import ObjectId

# class Doctor(BaseModel):
#     id: Optional[ObjectId] = Field(alias="_id")
#     name: str
#     phone: str
#     email: Optional[str] = None
#     specialization: Optional[str] = None
#     symptoms: Optional[List[str]] = []  # Use strings instead of ObjectId
#     profile_photo: Optional[str] = None
#     verified_by_admin: bool = False
#     active_patients: Optional[List[str]] = []  # Use strings instead of ObjectId

#     class Config:
#         arbitrary_types_allowed = True
#         populate_by_name = True
#         json_encoders = {
#             ObjectId: lambda oid: str(oid),
#         }
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from bson import ObjectId
from datetime import datetime

class Doctor(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    name: str
    mobile: str
    email: Optional[str] = None
    specialization: Optional[str] = None
    symptoms: Optional[List[str]] = []
    profile_photo: Optional[str] = None
    verified: bool = False
    verified_by_admin: bool = False
    active_patients: Optional[List[str]] = []
    
    # Availability and scheduling
    availability_schedule: Optional[Dict[str, List[str]]] = {
        "monday": [],
        "tuesday": [],
        "wednesday": [],
        "thursday": [],
        "friday": [],
        "saturday": [],
        "sunday": []
    }
    max_patients_per_day: Optional[int] = 20
    time_slot_duration_minutes: Optional[int] = 15
    
    # Keep track of booked slots
    booked_slots: Optional[Dict[str, List[str]]] = {}

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }