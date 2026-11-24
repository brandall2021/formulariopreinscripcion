from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.auditorias.models import Observacion
from app.auditorias.service import registrar_auditoria
from app.auth.models import Usuario
from app.documentos.models import Documento, DocumentoVersion
from app.infra.db import get_db
from app.notificaciones.events import publicar_evento
from app.solicitudes.models import Solicitud

router = APIRouter(prefix="/auditorias", tags=["auditorias"])

class Decision(BaseModel):
    documento_id: int
    resultado: str
    motivo: str | None = None

class AuditoriaIn(BaseModel):
    auditor_id: int
    decisiones: list[Decision]

@router.get("/solicitudes")
def listar(estado: str | None = None, carrera_id: int | None = None,
           db: Session = Depends(get_db)):
    query = db.query(Solicitud)
    if estado:
        query = query.filter_by(estado=estado)
    if carrera_id:
        query = query.filter_by(carrera_id=carrera_id)
    return query.all()

@router.get("/solicitudes/{solicitud_id}/documentos")
def documentos(solicitud_id: int, db: Session = Depends(get_db)):
    filas = (db.query(Documento, DocumentoVersion)
             .outerjoin(DocumentoVersion,
                        Documento.version_vigente_id == DocumentoVersion.id)
             .filter(Documento.solicitud_id == solicitud_id).all())
    return [{"documento_id": doc.id, "estado": doc.estado,
             "object_key": version.object_key if version else None,
             "observaciones": [o.motivo for o in db.query(Observacion).filter_by(
                 documento_id=doc.id, resuelta_en=None).all()]}
            for doc, version in filas]

@router.post("/solicitudes/{solicitud_id}")
def auditar(solicitud_id: int, data: AuditoriaIn, db: Session = Depends(get_db)):
    auditor = db.get(Usuario, data.auditor_id)
    if auditor is None or not auditor.activo or auditor.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")
    try:
        return registrar_auditoria(
            db, solicitud_id, data.auditor_id,
            [d.model_dump() for d in data.decisiones],
            on_event=lambda evento, datos: publicar_evento(
                db, solicitud_id, evento, datos,
                on_enqueue=lambda nid: None))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
