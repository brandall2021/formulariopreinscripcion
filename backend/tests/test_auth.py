from datetime import datetime, timedelta
import jwt
from sqlalchemy.orm import Session
from app.auth.models import OtpCodigo, Usuario
from app.auth.service import request_otp, verify_otp, authenticate_admin
from app.infra.config import get_settings

class FakeSender:
    def __init__(self):
        self.mensajes = []
    def send(self, to, subject, body):
        self.mensajes.append((to, subject, body))

from passlib.context import CryptContext
crypt = CryptContext(schemes=["bcrypt"])


def test_otp_ciclo_completo(db: Session):
    sender = FakeSender()
    request_otp(db, "ana@example.com", sender)
    assert len(sender.mensajes) == 1
    fila = db.query(OtpCodigo).filter_by(email="ana@example.com").one()
    fila.expira_en = datetime.utcnow() + timedelta(minutes=10)
    db.commit()
    import re
    code = re.search(r"\b\d{6}\b", sender.mensajes[0][2]).group(0)
    token = verify_otp(db, "ana@example.com", code)
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    assert payload["sub"] == "ana@example.com"


def test_otp_rechaza_codigo_incorrecto(db: Session):
    sender = FakeSender()
    request_otp(db, " Luis@example.com ".strip().lower(), sender)
    try:
        verify_otp(db, "luis@example.com", "000000")
    except ValueError as exc:
        assert "inválido" in str(exc)
    else:
        raise AssertionError("debió fallar")


def test_login_admin(db: Session):
    db.add(Usuario(email="admin@face.unt.edu.ar",
                   password_hash=crypt.hash("clave-secreta"),
                   rol="admin", activo=True))
    db.commit()
    token = authenticate_admin(db, "admin@face.unt.edu.ar", "clave-secreta")
    assert jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])["rol"] == "admin"
