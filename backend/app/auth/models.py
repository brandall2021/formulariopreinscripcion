from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.infra.db import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))  # auditor | admin
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

class OtpCodigo(Base):
    __tablename__ = "otp_codigos"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    hash_codigo: Mapped[str] = mapped_column(String(255))
    expira_en: Mapped[datetime] = mapped_column(DateTime)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    usado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
