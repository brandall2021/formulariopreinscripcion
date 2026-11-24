from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.infra.db import Base

class Convocatoria(Base):
    __tablename__ = "convocatorias"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    anio: Mapped[int] = mapped_column(Integer)
    fecha_apertura: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fecha_cierre: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

class Carrera(Base):
    __tablename__ = "carreras"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)

class TipoDocumento(Base):
    __tablename__ = "tipos_documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str | None] = mapped_column(String(300), nullable=True)
    formatos: Mapped[str] = mapped_column(String(120), default="pdf,jpg,png")
    tamano_maximo_bytes: Mapped[int] = mapped_column(Integer, default=10485760)

class RequisitoDocumental(Base):
    __tablename__ = "requisitos_documentales"
    __table_args__ = (UniqueConstraint("convocatoria_id", "carrera_id",
                                       "tipo_ingresante", "tipo_documento_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    convocatoria_id: Mapped[int] = mapped_column(ForeignKey("convocatorias.id"))
    carrera_id: Mapped[int] = mapped_column(ForeignKey("carreras.id"))
    tipo_ingresante: Mapped[str] = mapped_column(String(40))
    tipo_documento_id: Mapped[int] = mapped_column(ForeignKey("tipos_documentos.id"))
    obligatorio: Mapped[bool] = mapped_column(Boolean, default=True)
