import logging
import csv
import io
import json
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.auditorias.legajo import crear_legajo, leer_legajo
from app.auditorias.models import Auditoria, Observacion
from app.auditorias.service import registrar_auditoria
from app.auth.deps import require_roles
from app.auth.models import Usuario
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.historial.models import HistorialEstado
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.router import get_store
from app.infra.db import get_db
from app.infra.storage import ObjectStore
from app.notificaciones.events import publicar_evento
from app.solicitudes.models import Solicitud
from worker.tasks import enviar_notificacion

router = APIRouter(prefix="/auditorias", tags=["auditorias"], dependencies=[Depends(require_roles("auditor", "admin"))])

class Decision(BaseModel):
    documento_id: int
    version: int
    resultado: str
    motivo: str | None = None

class AuditoriaIn(BaseModel):
    # Se acepta por compatibilidad, pero se ignora: la identidad del auditor
    # se toma siempre del token autenticado.
    auditor_id: int | None = None
    decisiones: list[Decision]

@router.get("/aprobaciones")
def aprobaciones(db: Session = Depends(get_db),
                 claims: dict = Depends(require_roles("auditor", "admin"))):
    auditor_actual = db.query(Usuario).filter_by(email=claims.get("sub"), activo=True).first()
    if auditor_actual is None or auditor_actual.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")

    auditorias = (db.query(Auditoria, Solicitud, Alumno, Usuario)
                  .join(Solicitud, Solicitud.id == Auditoria.solicitud_id)
                  .join(Alumno, Alumno.id == Solicitud.alumno_id)
                  .join(Usuario, Usuario.id == Auditoria.auditor_id)
                  .order_by(Auditoria.fecha.desc(), Auditoria.id.desc()).all())
    observados = set(db.query(Observacion.auditoria_id, Observacion.documento_id).all())
    nombres = {(sol_id, doc_id): nombre for sol_id, doc_id, nombre in
               db.query(Documento.solicitud_id, Documento.id, TipoDocumento.nombre)
               .join(TipoDocumento, TipoDocumento.id == Documento.tipo_documento_id)}
    filas = []
    for audit, sol, alumno, auditor in auditorias:
        try:
            decisiones = json.loads(audit.notas or "[]")
        except ValueError:
            continue
        if not isinstance(decisiones, list):
            continue
        for decision in decisiones:
            if not isinstance(decision, dict):
                continue
            doc_id = decision.get("documento_id")
            resultado = decision.get("resultado") or (
                "OBSERVADO" if isinstance(doc_id, int) and (audit.id, doc_id) in observados else "APROBADO"
            )
            if not isinstance(doc_id, int) or resultado not in ("APROBADO", "RECHAZADO"):
                continue
            nombre = nombres.get((sol.id, doc_id))
            if nombre is None:
                continue
            filas.append({
                "auditoria_id": audit.id, "documento_id": doc_id,
                "solicitud": sol.numero, "alumno": f"{alumno.apellido}, {alumno.nombres}",
                "documento": nombre, "version": decision.get("version"),
                "resultado": resultado, "motivo": decision.get("motivo"),
                "auditor": auditor.email, "fecha": audit.fecha.replace(tzinfo=timezone.utc),
            })
    return filas


ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def celda_csv(valor):
    texto = "" if valor is None else str(valor)
    if texto.lstrip().startswith(("=", "+", "-", "@")) or texto.startswith(("\t", "\r", "\n")):
        return "'" + texto
    return texto


@router.get("/listado.csv")
def listado(resultado: str | None = None, desde: date | None = None,
            hasta: date | None = None, carrera_id: int | None = None,
            db: Session = Depends(get_db),
            claims: dict = Depends(require_roles("auditor", "admin"))):
    usuario = db.query(Usuario).filter_by(email=claims.get("sub"), activo=True).first()
    if usuario is None or usuario.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")
    estados = {
        "APROBADA": ("DOCUMENTACION_APROBADA", "FINALIZADA"),
        "RECHAZADA": ("RECHAZADA",),
        "OBSERVADA": ("OBSERVADA", "PENDIENTE_ALUMNO"),
    }
    if resultado and resultado not in estados:
        raise HTTPException(422, "Resultado inválido.")
    if desde and hasta and desde > hasta:
        raise HTTPException(422, "La fecha desde debe ser anterior o igual a la fecha hasta.")

    ultimo_resultado = (db.query(HistorialEstado.id)
                        .filter(HistorialEstado.solicitud_id == Solicitud.id,
                                HistorialEstado.estado_nuevo.in_(
                                    ("DOCUMENTACION_APROBADA", "RECHAZADA", "OBSERVADA")))
                        .order_by(HistorialEstado.fecha.desc(), HistorialEstado.id.desc())
                        .limit(1).correlate(Solicitud).scalar_subquery())
    consulta = (db.query(Solicitud, Alumno, Carrera.nombre, Convocatoria.nombre, HistorialEstado)
                .select_from(Solicitud)
                .join(Alumno, Alumno.id == Solicitud.alumno_id)
                .join(Carrera, Carrera.id == Solicitud.carrera_id)
                .join(Convocatoria, Convocatoria.id == Solicitud.convocatoria_id)
                .outerjoin(HistorialEstado, HistorialEstado.id == ultimo_resultado))
    if resultado:
        consulta = consulta.filter(Solicitud.estado.in_(estados[resultado]))
    if carrera_id:
        consulta = consulta.filter(Solicitud.carrera_id == carrera_id)
    if desde:
        inicio = datetime.combine(desde, time.min, ARGENTINA).astimezone(timezone.utc).replace(tzinfo=None)
        consulta = consulta.filter(HistorialEstado.fecha >= inicio)
    if hasta:
        fin = datetime.combine(hasta, time.max, ARGENTINA).astimezone(timezone.utc).replace(tzinfo=None)
        consulta = consulta.filter(HistorialEstado.fecha <= fin)

    salida = io.StringIO(newline="")
    escritor = csv.writer(salida, delimiter=";")
    escritor.writerow(["Apellido", "Nombres", "DNI", "Correo", "Teléfono", "Carrera", "Convocatoria",
                       "Solicitud", "Tipo de ingresante", "Estado actual", "Fecha de resolución (Argentina)",
                       "Motivo", "Fecha de nacimiento", "Domicilio", "Discapacidad"])
    for sol, alumno, carrera, convocatoria, historial in consulta.order_by(Alumno.apellido, Alumno.nombres, Solicitud.id):
        fecha = (historial.fecha.replace(tzinfo=timezone.utc).astimezone(ARGENTINA)
                 .strftime("%Y-%m-%d %H:%M:%S")) if historial else ""
        escritor.writerow(map(celda_csv, [
            alumno.apellido, alumno.nombres, sol.dni, alumno.email, alumno.celular, carrera, convocatoria,
            sol.numero, sol.tipo_ingresante, sol.estado, fecha, historial.motivo if historial else None,
            alumno.fecha_nacimiento, alumno.domicilio, "Sí" if alumno.discapacidad else "No",
        ]))
    logging.getLogger(__name__).info("exportacion_listado_auditoria usuario_id=%s", usuario.id)
    return Response(salida.getvalue().encode("utf-8-sig"), media_type="text/csv", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": 'attachment; filename="listado-auditoria.csv"',
    })


@router.get("/solicitudes")
def listar(estado: str | None = None, carrera_id: int | None = None,
           db: Session = Depends(get_db)):
    query = db.query(Solicitud)
    if estado:
        query = query.filter_by(estado=estado)
    if carrera_id:
        query = query.filter_by(carrera_id=carrera_id)
    return query.all()

@router.get("/solicitudes/{solicitud_id}/legajo")
def exportar_legajo(solicitud_id: int, db: Session = Depends(get_db),
                    store: ObjectStore = Depends(get_store),
                    claims: dict = Depends(require_roles("auditor", "admin"))):
    usuario = db.query(Usuario).filter_by(email=claims.get("sub"), activo=True).first()
    if usuario is None or usuario.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")
    sol = db.get(Solicitud, solicitud_id)
    alumno = db.get(Alumno, sol.alumno_id) if sol else None
    if alumno is None:
        raise HTTPException(404, "Alumno no encontrado.")
    archivo = crear_legajo(db, store, alumno)
    logging.getLogger(__name__).info("exportacion_legajo alumno_id=%s usuario_id=%s", alumno.id, usuario.id)
    return StreamingResponse(leer_legajo(archivo), media_type="application/zip", headers={
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'attachment; filename="legajo-{alumno.id}.zip"',
    })


@router.get("/solicitudes/{solicitud_id}/documentos")
def documentos(solicitud_id: int, db: Session = Depends(get_db)):
    filas = (db.query(Documento, DocumentoVersion)
             .outerjoin(DocumentoVersion,
                        Documento.version_vigente_id == DocumentoVersion.id)
             .filter(Documento.solicitud_id == solicitud_id).all())
    return [{"documento_id": doc.id, "version": doc.version,
             "estado": doc.estado,
             "object_key": version.object_key if version else None,
             "observaciones": [o.motivo for o in db.query(Observacion).filter_by(
                 documento_id=doc.id, resuelta_en=None).all()]}
            for doc, version in filas]

@router.post("/solicitudes/{solicitud_id}")
def auditar(solicitud_id: int, data: AuditoriaIn, db: Session = Depends(get_db),
            claims: dict = Depends(require_roles("auditor", "admin"))):
    auditor = db.query(Usuario).filter_by(email=claims.get("sub"), activo=True).first()
    if auditor is None or auditor.rol not in ("auditor", "admin"):
        raise HTTPException(403, "auditor no autorizado")
    try:
        return registrar_auditoria(
            db, solicitud_id, auditor.id,
            [d.model_dump() for d in data.decisiones],
            on_event=lambda evento, datos: publicar_evento(
                db, solicitud_id, evento, datos,
                on_enqueue=lambda nid: enviar_notificacion.delay(nid)))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
