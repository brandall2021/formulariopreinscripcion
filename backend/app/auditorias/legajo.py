import json
import logging
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile

from minio.error import S3Error
from sqlalchemy.inspection import inspect

from app.alumnos.models import Alumno
from app.auditorias.models import Auditoria, Observacion
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import nombre_archivo
from app.historial.models import HistorialEstado
from app.solicitudes.models import Solicitud

logger = logging.getLogger(__name__)
EXTENSIONES = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}


def datos_fila(fila, excluir=()):
    return {col.key: getattr(fila, col.key) for col in inspect(type(fila)).column_attrs
            if col.key not in excluir}


def crear_legajo(db, store, alumno: Alumno):
    archivo = SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    solicitudes = []
    faltantes = 0
    try:
        with ZipFile(archivo, "w") as zip_file:
            for sol in db.query(Solicitud).filter_by(alumno_id=alumno.id).order_by(Solicitud.id):
                datos = datos_fila(sol)
                carrera = db.get(Carrera, sol.carrera_id)
                convocatoria = db.get(Convocatoria, sol.convocatoria_id)
                datos["carrera"] = carrera.nombre
                datos["convocatoria"] = convocatoria.nombre
                datos["historial"] = [datos_fila(fila) for fila in db.query(HistorialEstado)
                                      .filter_by(solicitud_id=sol.id).order_by(HistorialEstado.id)]
                datos["auditorias"] = [
                    {**datos_fila(audit), "auditor": email,
                     "observaciones": [datos_fila(obs) for obs in db.query(Observacion)
                                       .filter_by(auditoria_id=audit.id)]}
                    for audit, email in db.query(Auditoria, Usuario.email)
                    .join(Usuario, Usuario.id == Auditoria.auditor_id)
                    .filter(Auditoria.solicitud_id == sol.id).order_by(Auditoria.id)]
                datos["documentos"] = []
                for doc in db.query(Documento).filter_by(solicitud_id=sol.id).order_by(Documento.id):
                    tipo = db.get(TipoDocumento, doc.tipo_documento_id)
                    documento = {**datos_fila(doc), "nombre": tipo.nombre, "versiones": []}
                    for version in db.query(DocumentoVersion).filter_by(documento_id=doc.id).order_by(DocumentoVersion.numero):
                        detalle = datos_fila(version, excluir=("object_key",))
                        extension = EXTENSIONES.get(version.mime, "bin")
                        sufijo = "" if version.numero == doc.version else f"-v{version.numero}"
                        nombre = nombre_archivo(sol.dni, tipo.codigo, extension, sufijo)
                        ruta = f"solicitud-{sol.id}/documento-{doc.id}/{nombre}"
                        try:
                            contenido = store.get_bytes(version.object_key)
                        except S3Error as exc:
                            if exc.code != "NoSuchKey":
                                raise
                            logger.warning("Archivo faltante en legajo version_id=%s", version.id)
                            detalle["archivo"] = None
                            detalle["error"] = "El archivo no está en el almacenamiento."
                            faltantes += 1
                        else:
                            zip_file.writestr(ruta, contenido)
                            detalle["archivo"] = ruta
                        documento["versiones"].append(detalle)
                    datos["documentos"].append(documento)
                solicitudes.append(datos)
            manifiesto = {"alumno": datos_fila(alumno), "archivos_faltantes": faltantes,
                          "solicitudes": solicitudes}
            zip_file.writestr("legajo.json", json.dumps(manifiesto, ensure_ascii=False, indent=2, default=str))
        archivo.seek(0)
        return archivo
    except Exception:
        archivo.close()
        raise


def leer_legajo(archivo):
    with archivo:
        while bloque := archivo.read(64 * 1024):
            yield bloque
