import hashlib
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import jwt
from passlib.context import CryptContext
from app.auth.models import OtpCodigo, Usuario
from app.infra.config import get_settings

crypt = CryptContext(schemes=["bcrypt"])

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
    if row.hash_codigo != _hash(code):
        row.intentos += 1
        db.commit()
        raise ValueError("código inválido")
    row.usado_en = datetime.utcnow()
    db.commit()
    s = get_settings()
    return jwt.encode({"sub": email}, s.secret_key, algorithm="HS256")

def authenticate_admin(db: Session, email: str, password: str) -> str:
    user = db.query(Usuario).filter_by(email=email.strip().lower(), activo=True).first()
    if user is None or not crypt.verify(password, user.password_hash):
        raise ValueError("credenciales inválidas")
    s = get_settings()
    return jwt.encode({"sub": user.email, "rol": user.rol}, s.secret_key, algorithm="HS256")
