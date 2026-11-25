import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auth.deps import get_current_claims, require_roles
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento, validar_version
from app.infra.config import get_settings
from app.infra.db import get_db
from app.infra.storage import ObjectStore
from app.solicitudes.models import Solicitud

router = APIRouter(prefix="/documentos", tags=["documentos"])
logger = logging.getLogger("acceso-documentos")

class UploadUrlIn(BaseModel):
    solicitud_id: int
    tipo_documento_id: int
    filename: str
    content_type: str
    size: int
    checksum: str

def get_store():
    return ObjectStore(get_settings())

def _assert_solicitud_access(sol: Solicitud, claims: dict, db: Session) -> None:
    rol = claims.get("rol", "alumno")
    if rol in ("admin", "auditor"):
        return
    alumno = db.get(Alumno, sol.alumno_id)
    if alumno is None or alumno.email != claims.get("sub"):
        raise HTTPException(403, "acceso denegado")


@router.post("/upload-url")
def upload_url(data: UploadUrlIn, db: Session = Depends(get_db),
               store: ObjectStore = Depends(get_store), claims: dict = Depends(require_roles("alumno"))):
    sol = db.get(Solicitud, data.solicitud_id)
    if sol is None:
        raise HTTPException(404, "solicitud no encontrada")
    _assert_solicitud_access(sol, claims, db)
    try:
        doc = registrar_documento(db, data.solicitud_id, data.tipo_documento_id,
                                  data.filename, data.content_type, data.size,
                                  data.checksum, claims.get("sub", "alumno"), store)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    version = db.query(DocumentoVersion).filter_by(
        documento_id=doc.id, numero=doc.version).one()
    url = store.presigned_put(version.object_key, data.content_type,
                              get_settings().upload_url_ttl)
    return {"url": url, "expires_in": get_settings().upload_url_ttl,
            "documento_id": doc.id}

@router.get("/{documento_id}/download-url")
def download_url(documento_id: int, db: Session = Depends(get_db),
                 store: ObjectStore = Depends(get_store), claims: dict = Depends(get_current_claims)):
    doc = db.get(Documento, documento_id)
    if doc is None or doc.version_vigente_id is None:
        raise HTTPException(404, "versión vigente no encontrada")
    sol = db.get(Solicitud, doc.solicitud_id)
    if sol is not None:
        _assert_solicitud_access(sol, claims, db)
    version = db.get(DocumentoVersion, doc.version_vigente_id)
    logger.info("descarga documento_id=%s object_key=%s", documento_id,
                version.object_key)
    url = store.presigned_get(version.object_key, get_settings().download_url_ttl)
    return {"url": url, "expires_in": get_settings().download_url_ttl}

@router.post("/{version_id}/validar")
def validar(version_id: int, db: Session = Depends(get_db),
            store: ObjectStore = Depends(get_store)):
    try:
        version = validar_version(db, version_id, store)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"object_key": version.object_key, "estado": "EN_REVISION"}
