import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext
from app.auth.models import OtpCodigo, Usuario
from app.infra.config import get_settings

crypt = CryptContext(schemes=["bcrypt"])

OTP_SESSION_TTL_SECONDS = 3600
ADMIN_TOKEN_TTL_SECONDS = 8 * 3600

def _hash(code: str) -> str:
    return hashlib.sha256(f"{get_settings().secret_key}:{code}".encode()).hexdigest()

def request_otp(db: Session, email: str, sender) -> None:
    email = email.strip().lower()
    code = f"{secrets.randbelow(1000000):06d}"
    s = get_settings()
    db.add(OtpCodigo(email=email, hash_codigo=_hash(code),
                     expira_en=datetime.utcnow() + timedelta(seconds=s.otp_ttl_seconds)))
    db.commit()
    sender.send(email, "Código de verificación FACE",
                f"Su código de verificación es {code}. Vence en {s.otp_ttl_seconds} segundos.")

def verify_otp(db: Session, email: str, code: str) -> str:
    email = email.strip().lower()
    row = db.query(OtpCodigo).filter_by(email=email).order_by(OtpCodigo.id.desc()).first()
    if row is None or row.usado_en or row.expira_en < datetime.utcnow() \
            or row.intentos >= get_settings().otp_max_intentos:
        raise ValueError("código inválido o vencido")
    if not hmac.compare_digest(row.hash_codigo, _hash(code)):
        row.intentos += 1
        db.commit()
        raise ValueError("código inválido")
    row.usado_en = datetime.utcnow()
    db.commit()
    s = get_settings()
    exp = int(time.time()) + OTP_SESSION_TTL_SECONDS
    return jwt.encode({"sub": email, "exp": exp}, s.secret_key, algorithm="HS256")

def authenticate_admin(db: Session, email: str, password: str) -> str:
    email = email.strip().lower()
    user = db.query(Usuario).filter_by(email=email, activo=True).first()
    if user is None or user.rol not in ("admin", "auditor") or not crypt.verify(password, user.password_hash):
        raise ValueError("credenciales inválidas")
    s = get_settings()
    exp = int(time.time()) + ADMIN_TOKEN_TTL_SECONDS
    return jwt.encode({"sub": email, "rol": user.rol, "exp": exp},
                      s.secret_key, algorithm="HS256")
