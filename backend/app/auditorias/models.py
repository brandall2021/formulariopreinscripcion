from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Auditoria(Base):
    __tablename__ = "auditorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    auditor_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    resultado: Mapped[str] = mapped_column(String(20))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

class Observacion(Base):
    __tablename__ = "observaciones"
    id: Mapped[int] = mapped_column(primary_key=True)
    auditoria_id: Mapped[int] = mapped_column(ForeignKey("auditorias.id"))
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id"))
    motivo: Mapped[str] = mapped_column(Text)
    resuelta_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
