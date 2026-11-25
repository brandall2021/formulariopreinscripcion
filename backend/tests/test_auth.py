from datetime import datetime, timedelta
import re
import time
import jwt
import pytest
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

CODIGO_FIJO = 123456


def _pedir_otp(db: Session, monkeypatch, email: str):
    monkeypatch.setattr("app.auth.service.secrets.randbelow", lambda n: CODIGO_FIJO)
    sender = FakeSender()
    request_otp(db, email, sender)
    code = re.search(r"\b\d{6}\b", sender.mensajes[0][2]).group(0)
    return sender, code


def test_otp_ciclo_completo(db: Session, monkeypatch):
    sender, code = _pedir_otp(db, monkeypatch, "ana@example.com")
    assert len(sender.mensajes) == 1
    token = verify_otp(db, "ana@example.com", code)
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    assert payload["sub"] == "ana@example.com"
    assert time.time() < payload["exp"] <= time.time() + 3600 + 5


def test_otp_rechaza_codigo_incorrecto_y_normaliza_email(db: Session, monkeypatch):
    _, code = _pedir_otp(db, monkeypatch, "  Luis@Example.COM  ")
    assert code == f"{CODIGO_FIJO:06d}"
    fila = db.query(OtpCodigo).filter_by(email="luis@example.com").one()
    with pytest.raises(ValueError, match="inválido"):
        verify_otp(db, " LUIS@example.com ", "000000")
    assert fila.intentos == 1


def test_otp_vence_segun_ttl(db: Session, monkeypatch):
    _, code = _pedir_otp(db, monkeypatch, "ttl@example.com")
    fila = db.query(OtpCodigo).filter_by(email="ttl@example.com").one()
    assert 0 < (fila.expira_en - datetime.utcnow()).total_seconds() <= 600
    fila.expira_en = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    with pytest.raises(ValueError, match="vencido"):
        verify_otp(db, "ttl@example.com", code)


def test_otp_agota_intentos(db: Session, monkeypatch):
    _, code = _pedir_otp(db, monkeypatch, "intentos@example.com")
    assert code == f"{CODIGO_FIJO:06d}"
    for _ in range(5):
        with pytest.raises(ValueError, match="inválido"):
            verify_otp(db, "intentos@example.com", "000000")
    with pytest.raises(ValueError, match="inválido o vencido"):
        verify_otp(db, "intentos@example.com", code)


def test_otp_no_reutilizable(db: Session, monkeypatch):
    _, code = _pedir_otp(db, monkeypatch, "reuso@example.com")
    verify_otp(db, "reuso@example.com", code)
    with pytest.raises(ValueError, match="inválido o vencido"):
        verify_otp(db, "reuso@example.com", code)


def test_login_admin_valida_rol_clave_y_estado(db: Session):
    admin = Usuario(email="admin@face.unt.edu.ar",
                    password_hash=crypt.hash("clave-secreta"),
                    rol="admin", activo=True)
    auditor = Usuario(email="auditor@face.unt.edu.ar",
                      password_hash=crypt.hash("clave-secreta"),
                      rol="auditor", activo=True)
    db.add_all([admin, auditor])
    db.commit()
    token = authenticate_admin(db, " ADMIN@FACE.UNT.EDU.AR ", "clave-secreta")
    payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    assert payload["rol"] == "admin" and time.time() < payload["exp"] <= time.time() + 8 * 3600 + 5
    with pytest.raises(ValueError, match="credenciales inválidas"):
        authenticate_admin(db, "admin@face.unt.edu.ar", "clave-mala")
    token_auditor = authenticate_admin(db, "auditor@face.unt.edu.ar", "clave-secreta")
    payload_auditor = jwt.decode(token_auditor, get_settings().secret_key, algorithms=["HS256"])
    assert payload_auditor["rol"] == "auditor"
    admin.activo = False
    db.commit()
    with pytest.raises(ValueError, match="credenciales inválidas"):
        authenticate_admin(db, "admin@face.unt.edu.ar", "clave-secreta")
