import json
from datetime import datetime
from sqlalchemy.orm import Session
from app.auditorias.models import Auditoria, Observacion
from app.catalogos.models import TipoDocumento
from app.documentos.models import Documento
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

def registrar_auditoria(db: Session, solicitud_id: int, auditor_id: int,
                        decisiones: list[dict], on_event=None) -> Auditoria:
    sol = db.get(Solicitud, solicitud_id)
    if sol is None:
        raise ValueError("solicitud no encontrada")
    if sol.estado not in ("EN_AUDITORIA", "EN_REAUDITORIA"):
        raise ValueError(f"estado no auditable: {sol.estado}")
    if not decisiones:
        raise ValueError("debe auditar al menos un documento")
    # Pre-validación completa: ninguna decisión muta estado hasta que todas
    # estén verificadas (un documento ajeno o un motivo ausente no dejan
    # filas ni estados a medio aplicar).
    vistos = set()
    for decision in decisiones:
        doc_id = decision.get("documento_id")
        doc = db.get(Documento, doc_id) if doc_id is not None else None
        if doc is None or doc.solicitud_id != solicitud_id:
            raise ValueError("el documento no pertenece a la solicitud")
        if doc.id in vistos:
            raise ValueError("documento duplicado en la auditoría")
        vistos.add(doc.id)
        version = decision.get("version")
        if version != doc.version:
            raise ValueError(f"versión obsoleta para el documento {doc.id}")
        if doc.version_vigente_id is None:
            raise ValueError(f"documento {doc.id} sin versión vigente")
        resultado = decision.get("resultado")
        if resultado not in ("OBSERVADO", "APROBADO"):
            raise ValueError(f"resultado inválido: {resultado}")
        if resultado == "OBSERVADO" and not (decision.get("motivo") or "").strip():
            raise ValueError("motivo obligatorio al observar")
    esperados = {doc.id for doc in db.query(Documento)
                 .filter_by(solicitud_id=solicitud_id).all()}
    if vistos != esperados:
        raise ValueError("debe auditar todos los documentos de la solicitud")
    audit = Auditoria(solicitud_id=solicitud_id, auditor_id=auditor_id,
                      resultado="APROBADO",
                      notas=json.dumps([
                          {"documento_id": d["documento_id"], "version": d["version"]}
                          for d in decisiones
                      ]))
    db.add(audit)
    db.flush()
    observados = []
    for decision in decisiones:
        doc = db.get(Documento, decision["documento_id"])
        resultado = decision["resultado"]
        if resultado == "OBSERVADO":
            motivo = decision["motivo"].strip()
            doc.estado = "OBSERVADO"
            db.add(Observacion(auditoria_id=audit.id, documento_id=doc.id,
                               motivo=motivo))
            nombre = db.get(TipoDocumento, doc.tipo_documento_id).nombre
            observados.append({"documento_id": doc.id, "nombre": nombre,
                               "motivo": motivo})
        else:
            doc.estado = "APROBADO"
            for obs in db.query(Observacion).filter_by(
                    documento_id=doc.id, resuelta_en=None).all():
                obs.resuelta_en = datetime.utcnow()
    if observados:
        audit.resultado = "OBSERVADO"
        registrar_transicion(db, sol, "OBSERVADA", f"auditor:{auditor_id}")
        registrar_transicion(db, sol, "PENDIENTE_ALUMNO", f"auditor:{auditor_id}")
        evento, datos = "OBSERVADA", {"observaciones": observados}
    else:
        registrar_transicion(db, sol, "DOCUMENTACION_APROBADA", f"auditor:{auditor_id}")
        evento, datos = "DOCUMENTACION_APROBADA", {"numero": sol.numero}
    db.commit()
    if on_event is not None:
        on_event(evento, datos)
    return audit
