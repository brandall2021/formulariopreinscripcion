from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria
from app.notificaciones.events import publicar_evento
from app.consentimientos.models import Consentimiento
from app.notificaciones.models import Notificacion
from app.notificaciones.service import enviar_notificacion
from app.solicitudes.models import Solicitud
from app.solicitudes.service import registrar_transicion

class FakeSender:
    def __init__(self): self.enviados = []
    def send(self, to, subject, body): self.enviados.append((to, subject, body))

class FakeWhatsApp:
    def __init__(self): self.enviados = []
    def send(self, to, body): self.enviados.append((to, body))

def test_publicacion_y_envio(db: Session):
    conv = Convocatoria(nombre="2026-not", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECONOT", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                    email="ana-not@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90004", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.flush()
    db.add(Consentimiento(alumno_id=alumno.id, canal="whatsapp", aceptado=True))
    db.commit()
    encolados = []
    ids = publicar_evento(db, sol.id, "OBSERVADA",
                          {"observaciones": [{"documento_id": 7,
                                               "motivo": "DNI ilegible"}]},
                          on_enqueue=encolados.append)
    assert len(ids) == 2 and len(encolados) == 2
    assert {db.get(Notificacion, i).canal for i in ids} == {"email", "whatsapp"}
    email, wa = FakeSender(), FakeWhatsApp()
    for i in ids:
        enviar_notificacion(i, email, wa, db)
    assert len(email.enviados) == 1 and len(wa.enviados) == 1
    assert "DNI ilegible" in email.enviados[0][2]
    assert email.enviados[0][0] == alumno.email
    assert wa.enviados[0][0] == alumno.celular
    assert all(db.get(Notificacion, i).estado == "ENVIADA" for i in ids)

def test_idempotencia(db: Session):
    conv = Convocatoria(nombre="2026-idem", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOIDEM", activa=True)
    alumno = Alumno(apellido="Gómez", nombres="Ana", dni="34123456",
                    email="ana-idem@example.com", celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90007", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="PENDIENTE_ALUMNO")
    db.add(sol)
    db.commit()
    datos = {"observaciones": [{"documento_id": 7, "motivo": "x"}]}
    ids1 = publicar_evento(db, sol.id, "OBSERVADA", datos)
    ids2 = publicar_evento(db, sol.id, "OBSERVADA", datos)
    assert ids1 == ids2


def _solicitud_notificable(db: Session, dni: str, email: str, nombre: str):
    conv = Convocatoria(nombre=f"2026-{nombre}", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo=f"ECO{nombre}", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni=dni, email=email,
                    celular="+5493815555555")
    db.add_all([conv, car, alumno])
    db.flush()
    sol = Solicitud(numero=f"FACE-2026-{nombre}", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=dni, estado="RECIBIDA")
    db.add(sol)
    db.commit()
    return sol


def test_idempotencia_no_reencola(db: Session):
    sol = _solicitud_notificable(db, "35123456", "noencola@example.com", "NOENCOLA")
    datos = {"observaciones": [{"documento_id": 7, "motivo": "x"}]}
    primera, segunda = [], []
    ids1 = publicar_evento(db, sol.id, "OBSERVADA", datos,
                           on_enqueue=primera.append)
    ids2 = publicar_evento(db, sol.id, "OBSERVADA", datos,
                           on_enqueue=segunda.append)
    assert ids1 == ids2 and len(primera) == 1 and segunda == []
    assert db.query(Notificacion).count() == 1


def test_clave_incluye_solicitud_y_version(db: Session):
    sol = _solicitud_notificable(db, "36123456", "clave1@example.com", "CLAVE1")
    otra = _solicitud_notificable(db, "37123456", "clave2@example.com", "CLAVE2")
    datos = {"observaciones": [{"documento_id": 7, "motivo": "mismo motivo"}]}
    id_a = publicar_evento(db, sol.id, "OBSERVADA", datos)
    id_b = publicar_evento(db, otra.id, "OBSERVADA", datos)
    assert id_a != id_b
    registrar_transicion(db, sol, "EN_VALIDACION", "worker")
    id_c = publicar_evento(db, sol.id, "OBSERVADA", datos)
    assert id_c != id_a
    assert db.query(Notificacion).count() == 3
