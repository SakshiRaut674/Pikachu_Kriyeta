from fastapi import APIRouter, Depends
from app.controllers.userController import update_profile, send_user_details,search_doctors_by_keyword
from app.middlewares.authMiddleware import get_current_user
from app.controllers.doctorController import get_emr_records_for_user


router = APIRouter(tags=["User"])

# ✅ Inject authenticated user
router.put("/update-profile")(update_profile)
router.get("/me", dependencies=[Depends(get_current_user)])(send_user_details)
router.get("/search")(search_doctors_by_keyword)
router.get("/emr/records-for-user")(get_emr_records_for_user)  # Alias for backward compatibility