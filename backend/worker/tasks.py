from app.documentos.service import validar_documentos_solicitud as _validar
from app.infra.celery_app import celery_app

@celery_app.task(name="documentos.validar_solicitud", bind=True, max_retries=3)
def validar_documentos_solicitud(self, solicitud_id: int):
    try:
        _validar(solicitud_id)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
