from fastapi import APIRouter
from app.controllers.authcontroller import (
    send_otp_controller,
    verify_otp,
    resend_otp,
    verify_otp_doctor
)

router = APIRouter(tags=["Auth"])

router.post("/send-otp")(send_otp_controller)
router.post("/verify-otp")(verify_otp)
router.post("/resend-otp")(resend_otp)
router.post("/verify-otp-doctor")(verify_otp_doctor)

