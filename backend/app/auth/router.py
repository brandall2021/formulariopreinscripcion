from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.auth import service
from app.infra.config import get_settings
from app.infra.db import get_db
from app.infra.email import EmailSender

router = APIRouter(prefix="/auth", tags=["auth"])

class OtpRequest(BaseModel):
    email: EmailStr

class OtpVerify(OtpRequest):
    code: str

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

@router.post("/request-otp", status_code=202)
def request_otp(data: OtpRequest, db: Session = Depends(get_db)):
    service.request_otp(db, data.email, EmailSender(get_settings()))
    return {"detail": "código enviado"}

@router.post("/verify-otp")
def verify_otp(data: OtpVerify, db: Session = Depends(get_db)):
    try:
        token = service.verify_otp(db, data.email, data.code)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"access_token": token, "token_type": "bearer"}

@router.post("/admin/login")
def admin_login(data: AdminLogin, db: Session = Depends(get_db)):
    try:
        token = service.authenticate_admin(db, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"access_token": token, "token_type": "bearer"}
