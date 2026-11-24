from datetime import datetime
from sqlalchemy.orm import Session
from app.notificaciones.models import Notificacion

def enviar_notificacion(notificacion_id: int, sender, whatsapp, db: Session) -> Notificacion:
    row = db.get(Notificacion, notificacion_id)
    if row.estado == "ENVIADA":
        return row
    try:
        if row.canal == "email":
            sender.send(row.destinatario, row.asunto, row.cuerpo)
        else:
            whatsapp.send(row.destinatario, row.cuerpo)
        row.estado = "ENVIADA"
        row.error = None
    except Exception as exc:
        row.intentos += 1
        row.estado = "FALLIDA"
        row.error = str(exc)
        raise
    finally:
        db.commit()
    return row
