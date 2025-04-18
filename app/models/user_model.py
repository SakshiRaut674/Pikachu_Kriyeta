from pydantic import BaseModel, Field
from typing import List, Optional
from bson import ObjectId

class User(BaseModel):
    id: Optional[ObjectId] = Field(alias="_id")
    name: str
    phone: str
    email: Optional[str] = None
    profile_photo: Optional[str] = None
    age: Optional[int] = None
    weight: Optional[int] = None
    gender: Optional[str] = None
    location: Optional[str] = None
    education: Optional[List[dict]] = []
    experience: Optional[List[dict]] = []
    certifications: Optional[List[dict]] = []
    projects: Optional[List[dict]] = []
    skills: Optional[List[str]] = []
    preferences: Optional[dict] = {}
      # Appointments
    active_appointments: Optional[List[str]] = []  # List of appointment IDs

    class Config:
        arbitrary_types_allowed = True
        populate_by_name = True
        json_encoders = {
            ObjectId: lambda oid: str(oid),
        }
