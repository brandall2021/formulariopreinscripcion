from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.documentos.models import Documento
from app.infra.db import get_db
from app.notificaciones.models import Notificacion
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion
from app.solicitudes.state import InvalidTransition

router = APIRouter(prefix="/reportes", tags=["reportes"])

@router.get("/resumen")
def resumen(db: Session = Depends(get_db)):
    filas = db.query(Solicitud.estado, func.count(Solicitud.id)).group_by(Solicitud.estado).all()
    por_estado = {estado: total for estado, total in filas}
    return {
        "total": sum(por_estado.values()),
        "por_estado": por_estado,
        "notificaciones_enviadas": db.query(Notificacion).filter_by(estado="ENVIADA").count(),
        "notificaciones_fallidas": db.query(Notificacion).filter_by(estado="FALLIDA").count(),
    }

@router.get("/observaciones-por-documento")
def observaciones_por_documento(db: Session = Depends(get_db)):
    filas = (db.query(Documento.tipo_documento_id, func.count(Documento.id))
             .filter(Documento.estado == "OBSERVADO")
             .group_by(Documento.tipo_documento_id).all())
    return [{"tipo_documento_id": tipo, "cantidad": n} for tipo, n in filas]

admin_router = APIRouter(prefix="/admin", tags=["admin"])

class CierreIn(BaseModel):
    actor: str
    motivo: str | None = None

@admin_router.post("/solicitudes/{solicitud_id}/finalizar")
def finalizar(solicitud_id: int, data: CierreIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    try:
        registrar_transicion(db, sol, "FINALIZADA", data.actor, data.motivo)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"estado": sol.estado}

@admin_router.post("/solicitudes/{solicitud_id}/rechazar")
def rechazar(solicitud_id: int, data: CierreIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    if not data.motivo:
        raise HTTPException(422, "motivo obligatorio para rechazar")
    registrar_transicion(db, sol, "RECHAZADA", data.actor, data.motivo)
    return {"estado": sol.estado}
