from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.catalogos.models import Carrera, Convocatoria, RequisitoDocumental, TipoDocumento
from app.infra.db import get_db

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

class ConvocatoriaOut(BaseModel):
    id: int
    nombre: str
    anio: int
    activa: bool
    model_config = {"from_attributes": True}

class CarreraOut(BaseModel):
    id: int
    nombre: str
    codigo: str
    activa: bool
    model_config = {"from_attributes": True}

class TipoDocumentoOut(BaseModel):
    id: int
    codigo: str
    nombre: str
    descripcion: str | None
    formatos: str
    tamano_maximo_bytes: int
    model_config = {"from_attributes": True}

class RequisitoOut(BaseModel):
    id: int
    convocatoria_id: int
    carrera_id: int
    tipo_ingresante: str
    tipo_documento_id: int
    obligatorio: bool
    model_config = {"from_attributes": True}

@router.get("/convocatorias", response_model=list[ConvocatoriaOut])
def convocatorias(db: Session = Depends(get_db)):
    return db.query(Convocatoria).filter_by(activa=True).all()

@router.get("/carreras", response_model=list[CarreraOut])
def carreras(db: Session = Depends(get_db)):
    return db.query(Carrera).filter_by(activa=True).order_by(Carrera.id).all()

@router.get("/tipos-documentos", response_model=list[TipoDocumentoOut])
def tipos_documentos(db: Session = Depends(get_db)):
    return db.query(TipoDocumento).all()

@router.get("/requisitos", response_model=list[RequisitoOut])
def requisitos(convocatoria_id: int, carrera_id: int,
               tipo_ingresante: str, db: Session = Depends(get_db)):
    return db.query(RequisitoDocumental).filter_by(
        convocatoria_id=convocatoria_id, carrera_id=carrera_id,
        tipo_ingresante=tipo_ingresante).all()
