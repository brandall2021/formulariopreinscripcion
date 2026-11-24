from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.infra.db import get_db
from app.consentimientos.models import Consentimiento

router = APIRouter(prefix="/alumnos", tags=["consentimientos"])

class ConsentimientoIn(BaseModel):
    alumno_id: int
    canal: str
    aceptado: bool

@router.post("/{alumno_id}/consentimientos")
def registrar(alumno_id: int, data: ConsentimientoIn, db: Session = Depends(get_db)):
    fila = Consentimiento(alumno_id=alumno_id, canal=data.canal,
                          aceptado=data.aceptado)
    db.add(fila)
    db.commit()
    return {"alumno_id": alumno_id, "canal": data.canal, "aceptado": data.aceptado}
