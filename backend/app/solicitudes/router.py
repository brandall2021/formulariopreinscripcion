from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.models import Observacion
from app.auth.deps import get_current_claims, require_roles
from app.catalogos.models import Carrera, Convocatoria
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.router import get_store
from app.infra.storage import ObjectStore
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
    acepta_declaracion: bool = False
    convocatoria_id: int
    carrera_id: int
    tipo_ingresante: str

class ConfirmarIn(BaseModel):
    version: int

class ReenviarIn(BaseModel):
    version: int

@router.post("", response_model=SolicitudOut)
def crear(data: SolicitudIn, db: Session = Depends(get_db), claims: dict = Depends(require_roles("alumno"))):
    if not data.acepta_declaracion:
        raise HTTPException(422, "Aceptá las reglas y la declaración de autenticidad para continuar.")
    if db.get(Convocatoria, data.convocatoria_id) is None:
        raise HTTPException(422, "Seleccioná una convocatoria válida.")
    if db.get(Carrera, data.carrera_id) is None:
        raise HTTPException(422, "Seleccioná una carrera válida.")
    payload = data.model_dump()
    payload['declaracion_aceptada_en'] = datetime.utcnow()
    payload["email"] = claims.get("sub", str(data.email))
    try:
        return service.crear_borrador(db, payload["email"], payload)
    except IntegrityError as exc:
        db.rollback()
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) != "solicitudes_convocatoria_id_dni_key":
            raise
        email = payload["email"].strip().lower()
        existente = (db.query(Solicitud).join(Alumno)
                     .filter(Solicitud.convocatoria_id == data.convocatoria_id,
                             Alumno.email == email,
                             Solicitud.dni == Alumno.dni).first())
        if (existente is not None and existente.carrera_id == data.carrera_id
                and existente.tipo_ingresante == data.tipo_ingresante):
            return existente
        raise HTTPException(409, "Ya existe una preinscripción para ese DNI en esta convocatoria. "
                                 "Si necesitás modificarla, contactá a la Facultad.") from exc

@router.get("/mia", response_model=SolicitudOut)
def mia(db: Session = Depends(get_db), claims: dict = Depends(require_roles("alumno"))):
    email = claims.get("sub")
    sol = (db.query(Solicitud).join(Alumno)
           .filter(Alumno.email == email).order_by(Solicitud.id.desc()).first())
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    return sol

def _assert_solicitud_access(sol: Solicitud, claims: dict, db: Session) -> None:
    rol = claims.get("rol", "alumno")
    if rol in ("admin", "auditor"):
        return
    email = claims.get("sub")
    alumno = db.get(Alumno, sol.alumno_id)
    if alumno is None or alumno.email != email:
        raise HTTPException(403, "acceso denegado")


@router.get("/{solicitud_id}", response_model=SolicitudOut)
def obtener(solicitud_id: int, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    _assert_solicitud_access(sol, claims, db)
    return sol

@router.post("/{solicitud_id}/confirmar", response_model=ConfirmacionOut)
def confirmar(solicitud_id: int, data: ConfirmarIn, db: Session = Depends(get_db), claims: dict = Depends(require_roles("alumno"))):
    sol_pre = db.get(Solicitud, solicitud_id)
    if sol_pre is None:
        raise HTTPException(404, "solicitud no encontrada")
    _assert_solicitud_access(sol_pre, claims, db)
    try:
        sol = service.confirmar(db, solicitud_id, data.version,
                                on_confirm=validar_documentos_solicitud.delay)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"numero": sol.numero, "fecha": sol.updated_at,
            "estado": sol.estado, "comprobante": f"Recibido {sol.numero}"}

@router.get("/{solicitud_id}/documentos-observados")
def documentos_observados(solicitud_id: int, db: Session = Depends(get_db), claims: dict = Depends(get_current_claims)):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    _assert_solicitud_access(sol, claims, db)
    filas = (db.query(Observacion, Documento)
             .join(Documento, Observacion.documento_id == Documento.id)
             .filter(Documento.solicitud_id == solicitud_id,
                     Observacion.resuelta_en.is_(None)).all())
    return [{"documento_id": doc.id, "tipo_documento_id": doc.tipo_documento_id,
             "motivo": obs.motivo} for obs, doc in filas]

@router.get("/{solicitud_id}/carga")
def contexto_carga(solicitud_id: int, db: Session = Depends(get_db),
                   store: ObjectStore = Depends(get_store),
                   claims: dict = Depends(require_roles("alumno"))):
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise HTTPException(404, "Solicitud no encontrada.")
    _assert_solicitud_access(sol, claims, db)
    observaciones = documentos_observados(solicitud_id, db, claims)
    filas = (db.query(Documento, DocumentoVersion)
             .join(DocumentoVersion, (Documento.id == DocumentoVersion.documento_id)
                   & (Documento.version == DocumentoVersion.numero))
             .filter(Documento.solicitud_id == solicitud_id).all())
    cargados = [doc.tipo_documento_id for doc, version in filas
                if doc.estado in ("RECIBIDO", "REEMPLAZADO") and store.exists(version.object_key)]
    return {"convocatoria_id": sol.convocatoria_id, "carrera_id": sol.carrera_id,
            "tipo_ingresante": sol.tipo_ingresante, "estado": sol.estado,
            "version": sol.version, "cargados": cargados, "observaciones": observaciones}


@router.post("/{solicitud_id}/reenviar")
def reenviar(solicitud_id: int, payload: ReenviarIn, db: Session = Depends(get_db), claims: dict = Depends(require_roles("alumno"))):
    sol = db.execute(select(Solicitud).where(
        Solicitud.id == solicitud_id).with_for_update()).scalar_one_or_none()
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    _assert_solicitud_access(sol, claims, db)
    if sol.version != payload.version:
        raise HTTPException(409, "versión obsoleta")
    if sol.estado != "PENDIENTE_ALUMNO":
        raise HTTPException(409, "La solicitud no está pendiente de corrección.")
    pendientes = (db.query(Observacion.id).join(Documento)
                  .filter(Documento.solicitud_id == solicitud_id,
                          Documento.estado != "REEMPLAZADO",
                          Observacion.resuelta_en.is_(None)).first())
    if pendientes is not None:
        raise HTTPException(409, "Subí una nueva versión de cada documento observado antes de reenviar.")
    registrar_transicion(db, sol, "REENVIADA", claims.get("sub", "alumno"), commit=False)
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
