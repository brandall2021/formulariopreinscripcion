from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.models import Observacion
from app.documentos.models import Documento
from app.infra.db import get_db
from app.notificaciones.models import Notificacion
from app.solicitudes import service
from app.solicitudes.models import Solicitud
from app.solicitudes.schemas import ConfirmacionOut, SolicitudOut
from app.solicitudes.service import registrar_transicion
from worker.tasks import validar_documentos_solicitud

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

class ReenviarIn(BaseModel):
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
        sol = service.confirmar(db, solicitud_id, data.version,
                                on_confirm=validar_documentos_solicitud.delay)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"numero": sol.numero, "fecha": sol.updated_at,
            "estado": sol.estado, "comprobante": f"Recibido {sol.numero}"}

@router.get("/{solicitud_id}/documentos-observados")
def documentos_observados(solicitud_id: int, db: Session = Depends(get_db)):
    filas = (db.query(Observacion, Documento)
             .join(Documento, Observacion.documento_id == Documento.id)
             .filter(Documento.solicitud_id == solicitud_id,
                     Observacion.resuelta_en.is_(None)).all())
    return [{"documento_id": doc.id, "tipo_documento_id": doc.tipo_documento_id,
             "motivo": obs.motivo} for obs, doc in filas]

@router.post("/{solicitud_id}/reenviar")
def reenviar(solicitud_id: int, payload: ReenviarIn, db: Session = Depends(get_db)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    if sol.version != payload.version:
        raise HTTPException(409, "versión obsoleta")
    from worker.tasks import validar_documentos_solicitud
    registrar_transicion(db, sol, "REENVIADA", "alumno")
    db.add(Notificacion(
        solicitud_id=solicitud_id, evento="REENVIADA", canal="email",
        destinatario="auditores@face.unt.edu.ar", estado="PENDIENTE",
        asunto="Reenvío de documentación – Preinscripción FACE",
        cuerpo=f"La solicitud {sol.numero} fue reenviada por el alumno.",
        idempotency_key=f"reenviada|{solicitud_id}|{sol.version}"))
    db.commit()
    validar_documentos_solicitud.delay(solicitud_id)
    from worker.tasks import enviar_notificacion
    enviar_notificacion.delay(db.query(Notificacion).filter_by(
        idempotency_key=f"reenviada|{solicitud_id}|{sol.version}").one().id)
    return {"estado": sol.estado}
