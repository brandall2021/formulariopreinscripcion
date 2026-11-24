from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class HistorialEstado(Base):
    __tablename__ = "historial_estados"
    id: Mapped[int] = mapped_column(primary_key=True)
    solicitud_id: Mapped[int] = mapped_column(ForeignKey("solicitudes.id"))
    estado_anterior: Mapped[str | None] = mapped_column(String(40), nullable=True)
    estado_nuevo: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str] = mapped_column(String(255))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
