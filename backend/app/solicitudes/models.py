from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Solicitud(Base):
    __tablename__ = "solicitudes"
    __table_args__ = (UniqueConstraint("convocatoria_id", "dni"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("alumnos.id"))
    convocatoria_id: Mapped[int] = mapped_column(ForeignKey("convocatorias.id"))
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))
    tipo_ingresante: Mapped[str] = mapped_column(String(40))
    dni: Mapped[str] = mapped_column(String(20))
    estado: Mapped[str] = mapped_column(String(40), default="BORRADOR")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
