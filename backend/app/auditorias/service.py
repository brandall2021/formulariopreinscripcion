from sqlalchemy.orm import Session
from app.auditorias.models import Auditoria, Observacion
from app.catalogos.models import TipoDocumento
from app.documentos.models import Documento
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

def registrar_auditoria(db: Session, solicitud_id: int, auditor_id: int,
                        decisiones: list[dict], on_event=None) -> Auditoria:
    sol = db.get(Solicitud, solicitud_id)
    if sol.estado not in ("EN_AUDITORIA", "EN_REAUDITORIA"):
        raise ValueError(f"estado no auditable: {sol.estado}")
    if not decisiones:
        raise ValueError("debe auditar al menos un documento")
    audit = Auditoria(solicitud_id=solicitud_id, auditor_id=auditor_id,
                      resultado="APROBADO")
    db.add(audit)
    db.flush()
    observados = []
    for decision in decisiones:
        doc = db.get(Documento, decision["documento_id"])
        if doc.solicitud_id != solicitud_id:
            raise ValueError("el documento no pertenece a la solicitud")
        resultado = decision["resultado"]
        if resultado == "OBSERVADO":
            motivo = decision.get("motivo", "").strip()
            if not motivo:
                raise ValueError("motivo obligatorio al observar")
            doc.estado = "OBSERVADO"
            db.add(Observacion(auditoria_id=audit.id, documento_id=doc.id,
                               motivo=motivo))
            nombre = db.get(TipoDocumento, doc.tipo_documento_id).nombre
            observados.append({"documento_id": doc.id, "nombre": nombre,
                               "motivo": motivo})
        elif resultado == "APROBADO":
            doc.estado = "APROBADO"
            for obs in db.query(Observacion).filter_by(
                    documento_id=doc.id, resuelta_en=None).all():
                from datetime import datetime
                obs.resuelta_en = datetime.utcnow()
        else:
            raise ValueError(f"resultado inválido: {resultado}")
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
