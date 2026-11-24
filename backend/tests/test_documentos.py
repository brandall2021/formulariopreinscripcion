import hashlib
import pytest
from sqlalchemy.orm import Session
from app.alumnos.models import Alumno
from app.catalogos.models import Carrera, Convocatoria, TipoDocumento
from app.documentos.models import Documento, DocumentoVersion
from app.documentos.service import registrar_documento, validar_version
from app.solicitudes.models import Solicitud

class FakeStore:
    def __init__(self):
        self.objects = {}
    def put_bytes(self, key, data):
        self.objects[key] = data
    def get_bytes(self, key):
        return self.objects[key]
    def exists(self, key):
        return key in self.objects
    def presigned_put(self, key, content_type, expires):
        return f"http://minio/{key}?X-Amz-Expires={expires}"
    def presigned_get(self, key, expires):
        return f"http://minio/{key}?X-Amz-Expires={expires}"


@pytest.fixture
def contexto(db: Session):
    conv = Convocatoria(nombre="2026-doc", anio=2026, activa=True)
    car = Carrera(nombre="Economía", codigo="ECOD", activa=True)
    alumno = Alumno(apellido="Pérez", nombres="Ana", dni="30123456",
                    email="ana-doc@example.com", celular="+5493815555555")
    td = TipoDocumento(codigo="dni", nombre="DNI",
                       formatos="pdf,jpg,png", tamano_maximo_bytes=10485760)
    db.add_all([conv, car, alumno, td])
    db.flush()
    sol = Solicitud(numero="FACE-2026-90001", alumno_id=alumno.id,
                    convocatoria_id=conv.id, carrera_id=car.id,
                    tipo_ingresante="nuevo", dni=alumno.dni, estado="RECIBIDA")
    db.add(sol)
    db.commit()
    return sol, td, FakeStore()


def test_registro_y_validacion(contexto, db: Session):
    sol, td, store = contexto
    data = b"contenido del dni"
    checksum = hashlib.sha256(data).hexdigest()
    doc = registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                              len(data), checksum, "ana-doc@example.com", store)
    assert doc.estado == "RECIBIDO"
    version = db.query(DocumentoVersion).filter_by(documento_id=doc.id).one()
    assert version.object_key.startswith(f"solicitudes/{sol.id}/dni/v1.")
    store.put_bytes(version.object_key, data)
    validar_version(db, version.id, store)
    assert db.get(Documento, doc.id).estado == "EN_REVISION"


def test_rechaza_formato_y_tamano(contexto, db: Session):
    sol, td, store = contexto
    with pytest.raises(ValueError, match="formato no permitido"):
        registrar_documento(db, sol.id, td.id, "dni.gif", "image/gif", 10, "x",
                            "ana-doc@example.com", store)
    with pytest.raises(ValueError, match="archivo demasiado grande"):
        registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                            10485761, "x", "ana-doc@example.com", store)


def test_checksum_invalido(contexto, db: Session):
    sol, td, store = contexto
    doc = registrar_documento(db, sol.id, td.id, "dni.pdf", "application/pdf",
                              4, "mal checksum", "ana-doc@example.com", store)
    version = db.query(DocumentoVersion).filter_by(documento_id=doc.id).one()
    store.put_bytes(version.object_key, b"abcd")
    with pytest.raises(ValueError, match="checksum"):
        validar_version(db, version.id, store)
