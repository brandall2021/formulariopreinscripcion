import hashlib
import json
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.consentimientos.models import Consentimiento
from app.notificaciones.models import Notificacion
from app.notificaciones.templates import plantilla_observaciones, plantilla_aprobada
from app.solicitudes.models import Solicitud

def publicar_evento(db: Session, solicitud_id: int, evento: str,
                    datos: dict, on_enqueue=None) -> list[int]:
    sol = db.get(Solicitud, solicitud_id)
    alumno = db.get(Alumno, sol.alumno_id) if sol else None
    nombre = alumno.nombres if alumno else "estudiante"
    numero = sol.numero if sol else str(solicitud_id)
    if evento == "OBSERVADA":
        asunto, cuerpo = plantilla_observaciones(nombre, numero, datos["observaciones"])
    else:
        asunto, cuerpo = plantilla_aprobada(nombre, numero)
    canales = ["email"]
    if alumno and db.query(Consentimiento).filter_by(
            alumno_id=alumno.id, canal="whatsapp", aceptado=True).first():
        canales.append("whatsapp")
    ids = []
    for canal in canales:
        payload = json.dumps({"evento": evento, "asunto": asunto, "cuerpo": cuerpo},
                             sort_keys=True)
        key = hashlib.sha256(f"{evento}|{canal}|{payload}".encode()).hexdigest()[:64]
        row = db.query(Notificacion).filter_by(idempotency_key=key).one_or_none()
        if row is None:
            row = Notificacion(solicitud_id=solicitud_id, evento=evento, canal=canal,
                               destinatario=alumno.email if alumno else "desconocido@face",
                               estado="PENDIENTE", asunto=asunto, cuerpo=cuerpo,
                               idempotency_key=key)
            db.add(row)
            db.commit()
        ids.append(row.id)
        if on_enqueue is not None:
            on_enqueue(row.id)
    return ids
