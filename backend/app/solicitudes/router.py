from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.infra.db import get_db
from app.solicitudes import service
from app.solicitudes.models import Solicitud
from app.solicitudes.schemas import ConfirmacionOut, SolicitudOut

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])

class SolicitudIn(BaseModel):
    apellido: str
    nombres: str
    dni: str
    email: EmailStr
    celular: str
    fecha_nacimiento: str | None = None
    domicilio: str | None = None
    discapacidad: bool = False
    convocatoria_id: int
    carrera_id: int
    tipo_ingresante: str

class ConfirmarIn(BaseModel):
    version: int

@router.post("", response_model=SolicitudOut)
def crear(data: SolicitudIn, db: Session = Depends(get_db)):
    return service.crear_borrador(db, data.email, data.model_dump())

@router.get("/mia", response_model=SolicitudOut)
def mia(email: EmailStr, db: Session = Depends(get_db)):
    sol = (db.query(Solicitud).join(Alumno)
           .filter(Alumno.email == email).order_by(Solicitud.id.desc()).first())
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    return sol

@router.get("/{solicitud_id}", response_model=SolicitudOut)
def obtener(solicitud_id: int, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    return sol

@router.post("/{solicitud_id}/confirmar", response_model=ConfirmacionOut)
def confirmar(solicitud_id: int, data: ConfirmarIn, db: Session = Depends(get_db)):
    try:
        sol = service.confirmar(db, solicitud_id, data.version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"numero": sol.numero, "fecha": sol.updated_at,
            "estado": sol.estado, "comprobante": f"Recibido {sol.numero}"}
