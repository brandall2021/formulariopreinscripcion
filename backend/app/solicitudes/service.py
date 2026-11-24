import logging
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Convocatoria, RequisitoDocumental
from app.documentos.models import Documento
from app.historial.models import HistorialEstado
from app.solicitudes.models import Solicitud
from app.solicitudes.state import transition

logger = logging.getLogger(__name__)

def _siguiente_numero(db: Session, anio: int, convocatoria_id: int) -> str:
    db.execute(text("CREATE SEQUENCE IF NOT EXISTS solicitud_numero_seq START 1"))
    n = db.execute(text("SELECT nextval('solicitud_numero_seq')")).scalar()
    return f"FACE-{anio}-{n:05d}"

def registrar_transicion(db: Session, sol: Solicitud, nuevo: str,
                         actor: str, motivo: str | None = None,
                         commit: bool = True) -> Solicitud:
    anterior = sol.estado
    estado_final = transition(anterior, nuevo)
    sol.estado = estado_final
    sol.version += 1
    db.add(HistorialEstado(solicitud_id=sol.id, estado_anterior=anterior,
                           estado_nuevo=estado_final, actor=actor, motivo=motivo))
    if commit:
        db.commit()
    return sol

def crear_borrador(db: Session, email: str, data: dict) -> Solicitud:
    alumno = db.query(Alumno).filter_by(email=email.strip().lower()).first()
    if alumno is None:
        alumno = Alumno(apellido=data["apellido"], nombres=data["nombres"],
                        dni=data["dni"], fecha_nacimiento=data.get("fecha_nacimiento"),
                        email=email.strip().lower(), celular=data.get("celular"),
                        domicilio=data.get("domicilio"),
                        discapacidad=bool(data.get("discapacidad", False)))
        db.add(alumno)
        db.flush()
    conv = db.get(Convocatoria, data["convocatoria_id"])
    sol = Solicitud(numero=None, alumno_id=alumno.id, convocatoria_id=conv.id,
                    carrera_id=data["carrera_id"],
                    tipo_ingresante=data["tipo_ingresante"],
                    dni=alumno.dni, estado="BORRADOR")
    db.add(sol)
    db.commit()
    return sol

def confirmar(db: Session, solicitud_id: int, version: int,
              on_confirm=None) -> Solicitud:
    # Un solo bloqueo y un solo commit: número, estado e historial se
    # persisten juntos. La segunda confirmación (reintento/doble click)
    # se rechaza antes de consumir otro número de la secuencia.
    sol = db.execute(
        select(Solicitud).where(Solicitud.id == solicitud_id).with_for_update()
    ).scalar_one_or_none()
    if sol is None:
        raise ValueError("solicitud no encontrada")
    if sol.estado != "BORRADOR":
        raise ValueError("solicitud no confirmable")
    if sol.version != version:
        raise ValueError("versión obsoleta")
    requisitos = db.query(RequisitoDocumental).filter_by(
        convocatoria_id=sol.convocatoria_id, carrera_id=sol.carrera_id,
        tipo_ingresante=sol.tipo_ingresante, obligatorio=True).all()
    ids = {r.tipo_documento_id for r in requisitos}
    cargados = {d.tipo_documento_id for d in db.query(Documento).filter_by(
        solicitud_id=sol.id).all() if d.estado != "PENDIENTE"}
    if ids - cargados:
        raise ValueError(f"requisitos pendientes: {sorted(ids - cargados)}")
    conv = db.get(Convocatoria, sol.convocatoria_id)
    sol.numero = _siguiente_numero(db, conv.anio, conv.id)
    sol = registrar_transicion(db, sol, "RECIBIDA", "alumno", commit=False)
    db.commit()
    if on_confirm is not None:
        try:
            on_confirm(sol.id)
        except Exception:
            # La presentación ya quedó persistida: un fallo del broker
            # no debe devolver 500 ni invitar a reintentar el confirmar.
            logger.exception("no se pudo encolar la validación de %s", sol.id)
    return sol
