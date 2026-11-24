from app.documentos.service import validar_documentos_solicitud as _validar
from app.infra.celery_app import celery_app
from app.infra.db import SessionLocal
from app.notificaciones.models import Notificacion

@celery_app.task(name="documentos.validar_solicitud", bind=True, max_retries=3)
def validar_documentos_solicitud(self, solicitud_id: int):
    try:
        _validar(solicitud_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

@celery_app.task(name="notificaciones.enviar", bind=True, max_retries=5)
def enviar_notificacion(self, notificacion_id: int):
    from app.infra.config import get_settings
    from app.infra.email import EmailSender
    from app.infra.whatsapp import WhatsAppMock
    from app.notificaciones.service import enviar_notificacion as _enviar
    with SessionLocal() as db:
        try:
            _enviar(notificacion_id, EmailSender(get_settings()),
                    WhatsAppMock(), db)
        except Exception as exc:
            row = db.get(Notificacion, notificacion_id)
            raise self.retry(exc=exc, countdown=60 * (row.intentos + 1))
