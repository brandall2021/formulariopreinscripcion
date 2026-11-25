import hashlib
from sqlalchemy.orm import Session
from app.catalogos.models import TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.infra.db import SessionLocal
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

EXTENSIONES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}

def registrar_documento(db: Session, solicitud_id: int, tipo_documento_id: int,
                        filename: str, content_type: str, size: int, checksum: str,
                        creado_por: str, store) -> Documento:
    td = db.get(TipoDocumento, tipo_documento_id)
    if content_type not in EXTENSIONES:
        raise ValueError("formato no permitido")
    if size > td.tamano_maximo_bytes:
        raise ValueError("archivo demasiado grande")
    doc = db.query(Documento).filter_by(
        solicitud_id=solicitud_id, tipo_documento_id=tipo_documento_id).one_or_none()
    if doc is None:
        # El modelo inicializa version en 1; empezamos en 0 para que la
        # primera versión cargada sea v1.
        doc = Documento(solicitud_id=solicitud_id, tipo_documento_id=tipo_documento_id,
                        estado="RECIBIDO", version=0)
        db.add(doc)
        db.flush()
    elif doc.estado in ("APROBADO", "OBSERVADO", "REEMPLAZADO"):
        doc.estado = "REEMPLAZADO"
    numero = doc.version + 1
    key = f"solicitudes/{solicitud_id}/{td.codigo}/v{numero}.{EXTENSIONES[content_type]}"
    db.add(DocumentoVersion(documento_id=doc.id, numero=numero, object_key=key,
                            mime=content_type, bytes=size, checksum=checksum,
                            creado_por=creado_por))
    doc.version = numero
    doc.version_vigente_id = None
    db.commit()
    return doc

def validar_version(db: Session, version_id: int, store) -> DocumentoVersion:
    version = db.get(DocumentoVersion, version_id)
    data = store.get_bytes(version.object_key)
    if hashlib.sha256(data).hexdigest() != version.checksum:
        raise ValueError("checksum no coincide")
    if len(data) != version.bytes:
        raise ValueError("tamaño no coincide")
    doc = db.get(Documento, version.documento_id)
    doc.estado = "EN_REVISION"
    doc.version_vigente_id = version.id
    db.commit()
    return version

def validar_documentos_solicitud(solicitud_id: int) -> None:
    with SessionLocal() as db:
        from app.infra.config import get_settings
        from app.infra.storage import ObjectStore
        store = ObjectStore(get_settings())
        sol = db.get(Solicitud, solicitud_id)
        if sol.estado == "RECIBIDA":
            registrar_transicion(db, sol, "EN_VALIDACION", "worker")
        documentos = db.query(Documento).filter_by(solicitud_id=solicitud_id).all()
        for doc in documentos:
            version = db.query(DocumentoVersion).filter_by(
                documento_id=doc.id, numero=doc.version).one()
            validar_version(db, version.id, store)
        if sol.estado == "EN_VALIDACION":
            registrar_transicion(db, sol, "EN_AUDITORIA", "worker")
        elif sol.estado == "REENVIADA":
            registrar_transicion(db, sol, "EN_REAUDITORIA", "worker")
