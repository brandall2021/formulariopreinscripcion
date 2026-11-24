from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.infra.db import Base

class Alumno(Base):
    __tablename__ = "alumnos"
    id: Mapped[int] = mapped_column(primary_key=True)
    apellido: Mapped[str] = mapped_column(String(100))
    nombres: Mapped[str] = mapped_column(String(100))
    dni: Mapped[str] = mapped_column(String(20), index=True)
    fecha_nacimiento: Mapped[str | None] = mapped_column(String(10), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    celular: Mapped[str | None] = mapped_column(String(30), nullable=True)
    domicilio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    discapacidad: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
